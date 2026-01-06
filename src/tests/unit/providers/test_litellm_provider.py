"""Тесты для LiteLLM Provider.

Покрывает:
- Инициализацию провайдера
- generate (non-streaming)
- generate_stream (streaming)
- get_model_info
- health_check
- Обработку ошибок
"""

from unittest.mock import Mock, patch

import pytest

from src.providers.base import ChatMessage, GenerationParams
from src.providers.litellm_provider import LiteLLMProvider


class TestLiteLLMProviderInit:
    """Тесты инициализации LiteLLMProvider."""

    def test_init_basic(self):
        """Тестирует базовую инициализацию."""
        provider = LiteLLMProvider(model_name="gpt-4")

        assert provider.model_name == "gpt-4"
        assert provider.api_key is None
        assert provider.base_url is None
        assert provider.timeout == 600
        assert provider.max_retries == 3

    def test_init_with_api_key(self):
        """Тестирует инициализацию с API ключом."""
        provider = LiteLLMProvider(model_name="gpt-4", api_key="sk-test123")

        assert provider.api_key == "sk-test123"

    def test_init_with_custom_params(self):
        """Тестирует инициализацию с кастомными параметрами."""
        provider = LiteLLMProvider(
            model_name="claude-3",
            api_key="sk-ant-test",
            base_url="https://api.anthropic.com",
            timeout=300,
            max_retries=5,
            drop_params=False,
        )

        assert provider.model_name == "claude-3"
        assert provider.api_key == "sk-ant-test"
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.timeout == 300
        assert provider.max_retries == 5

    @patch("src.providers.litellm_provider.litellm")
    def test_init_configures_litellm(self, mock_litellm):
        """Тестирует что инициализация конфигурирует LiteLLM."""
        LiteLLMProvider(model_name="gpt-4", max_retries=5, drop_params=False)

        assert mock_litellm.drop_params is False
        assert mock_litellm.num_retries == 5


class TestPrepareMessages:
    """Тесты для _prepare_messages."""

    def test_prepare_from_prompt(self):
        """Тестирует подготовку сообщений из простого prompt."""
        provider = LiteLLMProvider(model_name="gpt-4")

        messages = provider._prepare_messages(prompt="Hello, world!")

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello, world!"

    def test_prepare_from_chat_messages(self):
        """Тестирует подготовку из ChatMessage объектов."""
        provider = LiteLLMProvider(model_name="gpt-4")

        chat_messages = [
            ChatMessage(role="system", content="You are a helpful assistant"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
        ]

        messages = provider._prepare_messages(messages=chat_messages)

        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_prepare_raises_without_input(self):
        """Тестирует что ValueError поднимается без prompt или messages."""
        provider = LiteLLMProvider(model_name="gpt-4")

        with pytest.raises(ValueError) as exc_info:
            provider._prepare_messages()

        assert "Необходимо указать либо 'prompt', либо 'messages'" in str(exc_info.value)


class TestPrepareParams:
    """Тесты для _prepare_params."""

    def test_prepare_params_default(self):
        """Тестирует подготовку параметров по умолчанию."""
        provider = LiteLLMProvider(model_name="gpt-4")

        params = provider._prepare_params(None)

        # Дефолты из GenerationParams: temperature=0.1, max_tokens=2048, top_p=1.0
        assert params["temperature"] == 0.1
        assert params["max_tokens"] == 2048
        assert params["top_p"] == 1.0

    def test_prepare_params_custom(self):
        """Тестирует подготовку кастомных параметров."""
        provider = LiteLLMProvider(model_name="gpt-4")

        gen_params = GenerationParams(temperature=0.5, max_tokens=2048, top_p=0.9, top_k=50)

        params = provider._prepare_params(gen_params)

        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 2048
        assert params["top_p"] == 0.9
        assert params["top_k"] == 50

    def test_prepare_params_with_penalties(self):
        """Тестирует подготовку с penalty параметрами."""
        provider = LiteLLMProvider(model_name="gpt-4")

        gen_params = GenerationParams(frequency_penalty=0.5, presence_penalty=0.3)

        params = provider._prepare_params(gen_params)

        assert params["frequency_penalty"] == 0.5
        assert params["presence_penalty"] == 0.3

    def test_prepare_params_with_stop_sequences(self):
        """Тестирует подготовку с stop sequences."""
        provider = LiteLLMProvider(model_name="gpt-4")

        gen_params = GenerationParams(stop_sequences=["STOP", "END"])

        params = provider._prepare_params(gen_params)

        assert params["stop"] == ["STOP", "END"]

    def test_prepare_params_with_seed(self):
        """Тестирует подготовку с seed."""
        provider = LiteLLMProvider(model_name="gpt-4")

        gen_params = GenerationParams(seed=42)

        params = provider._prepare_params(gen_params)

        assert params["seed"] == 42

    def test_prepare_params_ignores_zero_penalties(self):
        """Тестирует что нулевые penalties не добавляются."""
        provider = LiteLLMProvider(model_name="gpt-4")

        gen_params = GenerationParams(frequency_penalty=0.0, presence_penalty=0.0)

        params = provider._prepare_params(gen_params)

        assert "frequency_penalty" not in params
        assert "presence_penalty" not in params


class TestExtractUsage:
    """Тесты для _extract_usage."""

    def test_extract_usage_with_data(self):
        """Тестирует извлечение usage когда данные есть."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_response = Mock()
        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30
        mock_response.usage = mock_usage

        usage = provider._extract_usage(mock_response)

        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    def test_extract_usage_without_data(self):
        """Тестирует извлечение usage когда данных нет."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_response = Mock()
        mock_response.usage = None

        usage = provider._extract_usage(mock_response)

        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0


class TestMapFinishReason:
    """Тесты для _map_finish_reason."""

    def test_map_stop(self):
        """Тестирует маппинг 'stop'."""
        provider = LiteLLMProvider(model_name="gpt-4")
        assert provider._map_finish_reason("stop") == "stop"

    def test_map_length(self):
        """Тестирует маппинг 'length'."""
        provider = LiteLLMProvider(model_name="gpt-4")
        assert provider._map_finish_reason("length") == "length"

    def test_map_max_tokens(self):
        """Тестирует маппинг 'max_tokens'."""
        provider = LiteLLMProvider(model_name="gpt-4")
        assert provider._map_finish_reason("max_tokens") == "length"

    def test_map_unknown(self):
        """Тестирует маппинг неизвестной причины."""
        provider = LiteLLMProvider(model_name="gpt-4")
        assert provider._map_finish_reason("unknown") == "error"

    def test_map_none(self):
        """Тестирует маппинг None."""
        provider = LiteLLMProvider(model_name="gpt-4")
        assert provider._map_finish_reason(None) == "error"


@pytest.mark.asyncio
class TestGenerate:
    """Тесты для generate (non-streaming)."""

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_with_prompt(self, mock_acompletion):
        """Тестирует генерацию с простым prompt."""
        provider = LiteLLMProvider(model_name="gpt-4")

        # Mock response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Generated response"
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 5
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 15
        mock_response.usage = mock_usage

        mock_acompletion.return_value = mock_response

        result = await provider.generate(prompt="Test prompt")

        assert result.text == "Generated response"
        assert result.finish_reason == "stop"
        assert result.usage["total_tokens"] == 15
        assert result.model == "gpt-4"

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_with_messages(self, mock_acompletion):
        """Тестирует генерацию с chat messages."""
        provider = LiteLLMProvider(model_name="gpt-4")

        # Mock response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Response to chat"
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        mock_acompletion.return_value = mock_response

        messages = [ChatMessage(role="user", content="Hello")]
        result = await provider.generate(messages=messages)

        assert result.text == "Response to chat"
        mock_acompletion.assert_called_once()

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_with_params(self, mock_acompletion):
        """Тестирует генерацию с параметрами."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Response"
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=5, completion_tokens=5, total_tokens=10)

        mock_acompletion.return_value = mock_response

        params = GenerationParams(temperature=0.5, max_tokens=100)
        await provider.generate(prompt="Test", params=params)

        # Проверяем что параметры переданы
        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 100

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_handles_error(self, mock_acompletion):
        """Тестирует обработку ошибки при генерации."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_acompletion.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError) as exc_info:
            await provider.generate(prompt="Test")

        assert "Ошибка генерации LiteLLM" in str(exc_info.value)


@pytest.mark.asyncio
class TestGenerateStream:
    """Тесты для generate_stream."""

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_stream_yields_chunks(self, mock_acompletion):
        """Тестирует что streaming генерирует chunks."""
        provider = LiteLLMProvider(model_name="gpt-4")

        # Mock streaming response
        async def mock_stream():
            # Chunk 1
            chunk1 = Mock()
            delta1 = Mock()
            delta1.content = "Hello"
            choice1 = Mock()
            choice1.delta = delta1
            choice1.finish_reason = None
            chunk1.choices = [choice1]

            # Chunk 2
            chunk2 = Mock()
            delta2 = Mock()
            delta2.content = " world"
            choice2 = Mock()
            choice2.delta = delta2
            choice2.finish_reason = None
            chunk2.choices = [choice2]

            # Final chunk
            chunk3 = Mock()
            delta3 = Mock()
            delta3.content = ""
            choice3 = Mock()
            choice3.delta = delta3
            choice3.finish_reason = "stop"
            chunk3.choices = [choice3]

            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk

        mock_acompletion.return_value = mock_stream()

        chunks = []
        async for chunk in provider.generate_stream(prompt="Test"):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].text == "Hello"
        assert chunks[1].text == " world"
        assert chunks[2].finish_reason == "stop"

    @patch("src.providers.litellm_provider.acompletion")
    async def test_generate_stream_handles_error(self, mock_acompletion):
        """Тестирует обработку ошибки в streaming."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_acompletion.side_effect = Exception("Stream error")

        with pytest.raises(RuntimeError) as exc_info:
            async for _chunk in provider.generate_stream(prompt="Test"):
                pass

        assert "Ошибка LiteLLM stream" in str(exc_info.value)


@pytest.mark.asyncio
class TestGetModelInfo:
    """Тесты для get_model_info."""

    async def test_get_model_info_claude_3(self):
        """Тестирует информацию для Claude 3."""
        provider = LiteLLMProvider(model_name="claude-3-opus-20240229")

        info = await provider.get_model_info()

        assert info.name == "claude-3-opus-20240229"
        assert info.provider == "litellm"
        assert info.context_window == 200000
        assert info.max_output_tokens == 4096
        assert info.supports_streaming is True

    async def test_get_model_info_gpt4_turbo(self):
        """Тестирует информацию для GPT-4 Turbo."""
        provider = LiteLLMProvider(model_name="gpt-4-turbo")

        info = await provider.get_model_info()

        assert info.context_window == 128000
        assert info.max_output_tokens == 4096

    async def test_get_model_info_gpt35(self):
        """Тестирует информацию для GPT-3.5."""
        provider = LiteLLMProvider(model_name="gpt-3.5-turbo")

        info = await provider.get_model_info()

        assert info.context_window == 4096

    async def test_get_model_info_default(self):
        """Тестирует дефолтную информацию для неизвестной модели."""
        provider = LiteLLMProvider(model_name="unknown-model")

        info = await provider.get_model_info()

        assert info.context_window == 4096  # Default
        assert info.max_output_tokens == 2048  # Default


@pytest.mark.asyncio
class TestHealthCheck:
    """Тесты для health_check."""

    @patch("src.providers.litellm_provider.acompletion")
    async def test_health_check_success(self, mock_acompletion):
        """Тестирует успешную health check."""
        provider = LiteLLMProvider(model_name="gpt-4")

        # Mock successful response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Hi"
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        mock_acompletion.return_value = mock_response

        result = await provider.health_check()

        assert result is True

    @patch("src.providers.litellm_provider.acompletion")
    async def test_health_check_failure(self, mock_acompletion):
        """Тестирует неудачную health check."""
        provider = LiteLLMProvider(model_name="gpt-4")

        mock_acompletion.side_effect = Exception("Connection failed")

        result = await provider.health_check()

        assert result is False


@pytest.mark.asyncio
class TestCleanup:
    """Тесты для cleanup."""

    async def test_cleanup(self):
        """Тестирует cleanup (должен быть no-op для LiteLLM)."""
        provider = LiteLLMProvider(model_name="gpt-4")

        # Не должно быть ошибок
        await provider.cleanup()
