"""Unit тесты для providers/base.py - Pydantic models и Protocol."""

import pytest

from src.core.enums import FinishReason, ProviderType
from src.providers.base import (
    GenerationParams,
    GenerationResult,
    ModelInfo,
    StreamChunk,
)


class TestGenerationParams:
    """Тесты для GenerationParams model."""

    def test_default_values(self) -> None:
        """Тест дефолтных значений параметров."""
        params = GenerationParams()

        assert params.temperature == 0.1
        assert params.max_tokens == 2048
        assert params.top_p == 1.0
        assert params.top_k == 40
        assert params.frequency_penalty == 0.0
        assert params.presence_penalty == 0.0
        assert params.stop_sequences == []
        assert params.seed is None
        assert params.response_format is None
        assert params.grammar is None
        assert params.extra == {}

    def test_custom_values(self) -> None:
        """Тест кастомных значений."""
        params = GenerationParams(
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,
            stop_sequences=["###", "END"],
            seed=42,
        )

        assert params.temperature == 0.7
        assert params.max_tokens == 1024
        assert params.top_p == 0.9
        assert params.stop_sequences == ["###", "END"]
        assert params.seed == 42

    def test_validation_temperature(self) -> None:
        """Тест валидации temperature (должна быть 0.0-2.0)."""
        # Валидные значения
        GenerationParams(temperature=0.0)
        GenerationParams(temperature=2.0)

        # Невалидные значения
        with pytest.raises(ValueError):
            GenerationParams(temperature=-0.1)

        with pytest.raises(ValueError):
            GenerationParams(temperature=2.1)

    def test_validation_top_p(self) -> None:
        """Тест валидации top_p (должна быть 0.0-1.0)."""
        # Валидные значения
        GenerationParams(top_p=0.0)
        GenerationParams(top_p=1.0)

        # Невалидные значения
        with pytest.raises(ValueError):
            GenerationParams(top_p=-0.1)

        with pytest.raises(ValueError):
            GenerationParams(top_p=1.1)

    def test_json_schema_support(self) -> None:
        """Тест поддержки JSON schema."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        params = GenerationParams(response_format=schema)

        assert params.response_format == schema

    def test_gbnf_grammar_support(self) -> None:
        """Тест поддержки GBNF грамматики."""
        grammar = "root ::= name age\nname ::= [a-zA-Z]+"
        params = GenerationParams(grammar=grammar)

        assert params.grammar == grammar


class TestGenerationResult:
    """Тесты для GenerationResult model."""

    def test_creation(self) -> None:
        """Тест создания result."""
        result = GenerationResult(
            text="Hello, world!",
            finish_reason=FinishReason.STOP,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            model="test-model",
        )

        assert result.text == "Hello, world!"
        assert result.finish_reason == FinishReason.STOP
        assert result.usage["total_tokens"] == 15
        assert result.model == "test-model"

    def test_extra_metadata(self) -> None:
        """Тест дополнительных метаданных."""
        result = GenerationResult(
            text="Test",
            finish_reason=FinishReason.LENGTH,
            usage={"prompt_tokens": 10, "completion_tokens": 100, "total_tokens": 110},
            model="test-model",
            extra={"vram_used_mb": 1024.5, "inference_time_ms": 250},
        )

        assert result.extra["vram_used_mb"] == 1024.5
        assert result.extra["inference_time_ms"] == 250


class TestStreamChunk:
    """Тесты для StreamChunk model."""

    def test_intermediate_chunk(self) -> None:
        """Тест промежуточного chunk (без finish_reason)."""
        chunk = StreamChunk(text="Hello")

        assert chunk.text == "Hello"
        assert chunk.finish_reason is None
        assert chunk.usage is None

    def test_final_chunk(self) -> None:
        """Тест финального chunk (с finish_reason и usage)."""
        chunk = StreamChunk(
            text=" world!",
            finish_reason=FinishReason.STOP,
            usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        )

        assert chunk.text == " world!"
        assert chunk.finish_reason == FinishReason.STOP
        assert chunk.usage is not None
        assert chunk.usage["total_tokens"] == 15


class TestModelInfo:
    """Тесты для ModelInfo model."""

    def test_local_model(self) -> None:
        """Тест метаданных local модели."""
        info = ModelInfo(
            name="qwen2.5-7b-instruct",
            provider=ProviderType.LOCAL,
            context_window=8192,
            max_output_tokens=2048,
            supports_streaming=True,
            supports_structured_output=True,
            loaded=True,
            extra={"vram_usage": {"used_mb": 4096}, "quantization": "Q4_K_M"},
        )

        assert info.name == "qwen2.5-7b-instruct"
        assert info.provider == ProviderType.LOCAL
        assert info.context_window == 8192
        assert info.supports_streaming is True
        assert info.supports_structured_output is True
        assert info.loaded is True
        assert info.extra["quantization"] == "Q4_K_M"

    def test_remote_model(self) -> None:
        """Тест метаданных remote модели."""
        info = ModelInfo(
            name="gpt-4-turbo",
            provider=ProviderType.OPENAI,
            context_window=128000,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_structured_output=True,
            loaded=True,  # Remote модели всегда "loaded"
        )

        assert info.provider == ProviderType.OPENAI
        assert info.context_window == 128000
        assert info.loaded is True
