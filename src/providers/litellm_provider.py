"""LiteLLM Provider - Унифицированный интерфейс для 100+ облачных LLM провайдеров.

Заменяет все кастомные реализации облачных провайдеров (Anthropic, OpenAI и т.д.)
единым провайдером на базе LiteLLM.

Поддерживает: Anthropic, OpenAI, Google Gemini, Mistral, Cohere, Azure и многие другие.
"""

from collections.abc import AsyncIterator
from typing import Any

import litellm
from litellm import ModelResponse, acompletion
from loguru import logger

from src.providers.base import ChatMessage, GenerationParams, GenerationResult, ModelInfo, StreamChunk


class LiteLLMProvider:
    """Унифицированный облачный LLM провайдер на базе LiteLLM.

    Автоматически обрабатывает трансляцию параметров, повторные попытки и маппинг ошибок
    для всех поддерживаемых провайдеров.

    Examples:
        # Anthropic Claude
        provider = LiteLLMProvider(model_name="claude-3-opus-20240229")

        # OpenAI GPT
        provider = LiteLLMProvider(model_name="gpt-4-turbo")

        # Google Gemini
        provider = LiteLLMProvider(model_name="gemini/gemini-pro")

        # Mistral
        provider = LiteLLMProvider(model_name="mistral/mistral-large-latest")

    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 600,
        max_retries: int = 3,
        drop_params: bool = True,
        **extra_params: Any,
    ) -> None:
        """Инициализировать LiteLLM provider.

        Args:
            model_name: Идентификатор модели (например, "claude-3-opus-20240229", "gpt-4")
            api_key: API ключ для провайдера (опционально, если установлен через env var)
            base_url: Кастомный base URL для API (опционально)
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторных попыток при ошибке
            drop_params: Автоматически удалять неподдерживаемые параметры
            **extra_params: Дополнительные специфичные для провайдера параметры

        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_params = extra_params

        # Настроить LiteLLM
        litellm.drop_params = drop_params
        litellm.num_retries = max_retries

        logger.info(
            f"LiteLLMProvider инициализирован: model={model_name}, "
            f"timeout={timeout}s, retries={max_retries}"
        )

    def _prepare_messages(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
    ) -> list[dict[str, str]]:
        """Конвертировать prompt или messages в формат LiteLLM messages.

        Args:
            prompt: Простой текстовый промпт
            messages: Сообщения чата в формате OpenAI

        Returns:
            Список словарей сообщений для LiteLLM

        Raises:
            ValueError: Если не указан ни prompt, ни messages

        """
        if messages:
            return [{"role": msg.role, "content": msg.content} for msg in messages]

        if prompt:
            return [{"role": "user", "content": prompt}]

        raise ValueError("Необходимо указать либо 'prompt', либо 'messages'")

    def _prepare_params(self, params: GenerationParams | None) -> dict[str, Any]:
        """Конвертировать GenerationParams в параметры LiteLLM.

        Args:
            params: Параметры генерации

        Returns:
            Словарь параметров для LiteLLM

        """
        if params is None:
            params = GenerationParams()

        litellm_params: dict[str, Any] = {
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "top_p": params.top_p,
        }

        # Добавить опциональные параметры
        if params.frequency_penalty != 0.0:
            litellm_params["frequency_penalty"] = params.frequency_penalty

        if params.presence_penalty != 0.0:
            litellm_params["presence_penalty"] = params.presence_penalty

        if params.stop_sequences:
            litellm_params["stop"] = params.stop_sequences

        if params.seed is not None:
            litellm_params["seed"] = params.seed

        # Response format для structured output
        if params.response_format:
            litellm_params["response_format"] = params.response_format

        # Top-K (не все провайдеры поддерживают)
        if params.top_k > 0 and params.top_k != 40:
            litellm_params["top_k"] = params.top_k

        # Объединить с дополнительными специфичными для провайдера параметрами
        if params.extra:
            litellm_params.update(params.extra)

        return litellm_params

    def _extract_usage(self, response: ModelResponse) -> dict[str, int]:
        """Извлечь информацию об использовании токенов из ответа LiteLLM.

        Args:
            response: Объект ответа LiteLLM

        Returns:
            Словарь usage с prompt_tokens, completion_tokens, total_tokens

        """
        usage = getattr(response, "usage", None)

        if usage:
            return {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _map_finish_reason(self, reason: str | None) -> str:
        """Преобразовать finish_reason из LiteLLM в стандартный формат.

        Args:
            reason: Причина завершения LiteLLM

        Returns:
            Стандартизированная причина завершения

        """
        if reason == "stop":
            return "stop"
        if reason in ("length", "max_tokens"):
            return "length"
        return "error"

    async def generate(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
        params: GenerationParams | None = None,
    ) -> GenerationResult:
        """Сгенерировать текст используя LiteLLM (без streaming).

        Args:
            prompt: Простой текстовый промпт
            messages: Сообщения чата в формате OpenAI
            params: Параметры генерации

        Returns:
            Результат генерации с текстом и метаданными

        Raises:
            RuntimeError: Если генерация не удалась
            ValueError: Если не указан ни prompt, ни messages

        """
        try:
            messages_list = self._prepare_messages(prompt, messages)
            litellm_params = self._prepare_params(params)

            logger.debug(f"LiteLLM генерация: model={self.model_name}, messages={len(messages_list)}")

            response: ModelResponse = await acompletion(
                model=self.model_name,
                messages=messages_list,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                stream=False,
                **litellm_params,
                **self.extra_params,
            )

            # Извлечь содержимое ответа
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = self._map_finish_reason(choice.finish_reason)
            usage = self._extract_usage(response)

            logger.debug(
                f"LiteLLM генерация завершена: tokens={usage['total_tokens']}, "
                f"finish={finish_reason}"
            )

            return GenerationResult(
                text=text,
                finish_reason=finish_reason,
                usage=usage,
                model=response.model or self.model_name,
                extra={"provider": getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown")},
            )

        except Exception as e:
            logger.error(f"Ошибка генерации LiteLLM: {e}")
            msg = f"Ошибка генерации LiteLLM: {e}"
            raise RuntimeError(msg) from e

    async def generate_stream(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
        params: GenerationParams | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Сгенерировать текст используя LiteLLM (со streaming).

        Args:
            prompt: Простой текстовый промпт
            messages: Сообщения чата в формате OpenAI
            params: Параметры генерации

        Yields:
            Stream chunks с инкрементальным текстом

        Raises:
            RuntimeError: Если генерация не удалась
            ValueError: Если не указан ни prompt, ни messages

        """
        try:
            messages_list = self._prepare_messages(prompt, messages)
            litellm_params = self._prepare_params(params)

            logger.debug(f"LiteLLM stream: model={self.model_name}, messages={len(messages_list)}")

            response = await acompletion(
                model=self.model_name,
                messages=messages_list,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                stream=True,
                **litellm_params,
                **self.extra_params,
            )

            accumulated_tokens = 0

            async for chunk in response:
                delta = chunk.choices[0].delta

                # Извлечь текст из delta
                text = getattr(delta, "content", "") or ""

                # Проверить, является ли это последним chunk
                finish_reason = chunk.choices[0].finish_reason
                is_final = finish_reason is not None

                if text:
                    accumulated_tokens += len(text.split())

                yield StreamChunk(
                    text=text,
                    finish_reason=self._map_finish_reason(finish_reason) if is_final else None,
                    usage=(
                        {
                            "prompt_tokens": 0,
                            "completion_tokens": accumulated_tokens,
                            "total_tokens": accumulated_tokens,
                        }
                        if is_final
                        else None
                    ),
                )

            logger.debug(f"LiteLLM stream завершён: tokens≈{accumulated_tokens}")

        except Exception as e:
            logger.error(f"Ошибка LiteLLM stream: {e}")
            msg = f"Ошибка LiteLLM stream: {e}"
            raise RuntimeError(msg) from e

    async def get_model_info(self) -> ModelInfo:
        """Получить метаданные модели.

        Returns:
            Информация о модели с возможностями и ограничениями

        Note:
            LiteLLM не предоставляет прямого API для метаданных модели,
            поэтому возвращаем разумные значения по умолчанию на основе имени модели.

        """
        # Попытаться определить context window из имени модели
        context_window = 4096  # Default
        max_output = 2048  # Default

        model_lower = self.model_name.lower()

        if "claude-3" in model_lower:
            context_window = 200000
            max_output = 4096
        elif "claude-2" in model_lower:
            context_window = 100000
            max_output = 4096
        elif "gpt-4" in model_lower:
            if "turbo" in model_lower or "1106" in model_lower or "0125" in model_lower:
                context_window = 128000
                max_output = 4096
            else:
                context_window = 8192
                max_output = 4096
        elif "gpt-3.5" in model_lower:
            context_window = 16384 if "16k" in model_lower else 4096
            max_output = 4096
        elif "gemini" in model_lower or "mistral" in model_lower:
            context_window = 32000
            max_output = 8192

        return ModelInfo(
            name=self.model_name,
            provider="litellm",
            context_window=context_window,
            max_output_tokens=max_output,
            supports_streaming=True,
            supports_structured_output="gpt" in model_lower or "gemini" in model_lower,
            loaded=True,  # Cloud models are always "loaded"
            extra={
                "base_url": self.base_url,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            },
        )

    async def health_check(self) -> bool:
        """Проверить доступность модели/провайдера.

        Returns:
            True если провайдер работает

        Note:
            Выполняет минимальный тестовый запрос для проверки подключения.

        """
        try:
            await self.generate(
                messages=[ChatMessage(role="user", content="Hi")],
                params=GenerationParams(max_tokens=1, temperature=0.0),
            )
            return True
        except Exception as e:
            logger.warning(f"Проверка работоспособности LiteLLM не удалась для {self.model_name}: {e}")
            return False

    async def cleanup(self) -> None:
        """Очистить ресурсы.

        Note:
            LiteLLM не имеет состояния, поэтому очистка не требуется.

        """
        logger.debug(f"LiteLLM provider cleanup: {self.model_name}")
