"""Unit тесты для API schemas."""

import pytest
from src.api.schemas.requests import CreateTaskRequest, RegisterModelRequest
from src.api.schemas.responses import (
    ErrorResponse,
    GenerationResult,
    HealthCheckResponse,
    ModelInfo,
    TaskResponse,
)


class TestCreateTaskRequest:
    """Тесты для CreateTaskRequest schema."""

    def test_minimal_request(self) -> None:
        """Тест минимального валидного запроса."""
        request = CreateTaskRequest(
            model="test-model",
            prompt="Test prompt",
        )

        assert request.model == "test-model"
        assert request.prompt == "Test prompt"
        assert request.temperature == 0.1  # default
        assert request.max_tokens == 2048  # default
        assert request.stream is False  # default

    def test_full_request(self) -> None:
        """Тест полного запроса со всеми параметрами."""
        request = CreateTaskRequest(
            model="test-model",
            prompt="Test prompt",
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,
            stop_sequences=["###"],
            stream=True,
            webhook_url="https://example.com/webhook",
            idempotency_key="test-key-123",
            priority=10.0,
        )

        assert request.temperature == 0.7
        assert request.max_tokens == 1024
        assert request.stream is True
        assert request.webhook_url == "https://example.com/webhook"
        assert request.idempotency_key == "test-key-123"
        assert request.priority == 10.0

    def test_validation_temperature(self) -> None:
        """Тест валидации temperature."""
        # Валидная
        CreateTaskRequest(model="test", prompt="test", temperature=0.5)

        # Невалидная
        with pytest.raises(ValueError):
            CreateTaskRequest(model="test", prompt="test", temperature=-0.1)

        with pytest.raises(ValueError):
            CreateTaskRequest(model="test", prompt="test", temperature=2.1)

    def test_empty_prompt_validation(self) -> None:
        """Тест что пустой промпт не проходит валидацию."""
        with pytest.raises(ValueError):
            CreateTaskRequest(model="test", prompt="")


class TestRegisterModelRequest:
    """Тесты для RegisterModelRequest schema."""

    def test_local_provider(self) -> None:
        """Тест регистрации local provider."""
        request = RegisterModelRequest(
            name="qwen-7b",
            provider="local",
            config={
                "model_path": "/models/qwen.gguf",
                "context_window": 8192,
                "gpu_layers": -1,
            },
        )

        assert request.name == "qwen-7b"
        assert request.provider == "local"
        assert request.config["model_path"] == "/models/qwen.gguf"
        assert request.config["gpu_layers"] == -1

    def test_openai_provider(self) -> None:
        """Тест регистрации OpenAI provider."""
        request = RegisterModelRequest(
            name="gpt-4",
            provider="openai",
            config={
                "api_key": "sk-xxx",
                "model_name": "gpt-4-turbo",
            },
        )

        assert request.provider == "openai"
        assert request.config["api_key"] == "sk-xxx"


class TestTaskResponse:
    """Тесты для TaskResponse schema."""

    def test_pending_task(self) -> None:
        """Тест ответа для pending задачи."""
        response = TaskResponse(
            task_id="task-123",
            status="pending",
            model="test-model",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )

        assert response.task_id == "task-123"
        assert response.status == "pending"
        assert response.result is None
        assert response.error is None

    def test_completed_task(self) -> None:
        """Тест ответа для completed задачи."""
        response = TaskResponse(
            task_id="task-123",
            status="completed",
            model="test-model",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:01:00",
            finished_at="2024-01-01T00:01:00",
            result={
                "text": "Generated text",
                "finish_reason": "stop",
                "usage": {"total_tokens": 100},
            },
        )

        assert response.status == "completed"
        assert response.result is not None
        assert response.result["text"] == "Generated text"
        assert response.finished_at is not None

    def test_failed_task(self) -> None:
        """Тест ответа для failed задачи."""
        response = TaskResponse(
            task_id="task-123",
            status="failed",
            model="test-model",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:01:00",
            finished_at="2024-01-01T00:01:00",
            error="Model not found",
        )

        assert response.status == "failed"
        assert response.error == "Model not found"
        assert response.result is None


class TestHealthCheckResponse:
    """Тесты для HealthCheckResponse schema."""

    def test_healthy_system(self) -> None:
        """Тест ответа для healthy системы."""
        response = HealthCheckResponse(
            status="healthy",
            redis=True,
            providers={"model-1": True, "model-2": True},
            gpu={"available": True, "vram_used_percent": 45.5},
        )

        assert response.status == "healthy"
        assert response.redis is True
        assert all(response.providers.values())

    def test_degraded_system(self) -> None:
        """Тест ответа для degraded системы."""
        response = HealthCheckResponse(
            status="degraded",
            redis=True,
            providers={"model-1": True, "model-2": False},
        )

        assert response.status == "degraded"
        assert response.providers["model-1"] is True
        assert response.providers["model-2"] is False

    def test_unhealthy_system(self) -> None:
        """Тест ответа для unhealthy системы."""
        response = HealthCheckResponse(
            status="unhealthy",
            redis=False,
            providers={},
        )

        assert response.status == "unhealthy"
        assert response.redis is False


class TestErrorResponse:
    """Тесты для ErrorResponse schema."""

    def test_basic_error(self) -> None:
        """Тест базовой ошибки."""
        error = ErrorResponse(
            error="NotFoundError",
            message="Model not found",
        )

        assert error.error == "NotFoundError"
        assert error.message == "Model not found"
        assert error.details is None

    def test_error_with_details(self) -> None:
        """Тест ошибки с деталями."""
        error = ErrorResponse(
            error="ValidationError",
            message="Invalid request",
            details={"field": "temperature", "reason": "value out of range"},
        )

        assert error.details is not None
        assert error.details["field"] == "temperature"
