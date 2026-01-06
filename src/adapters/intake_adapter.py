"""Intake Adapter - адаптация SOP Intake-style запросов.

Адаптирует запросы от SOP Intake к внутреннему формату SOP LLM:
- Определяет модель (provider_config.model_name > model field)
- Объединяет prompt и input_text
- Адаптирует response_format (output_schema > response_format)
- Извлекает параметры генерации с приоритетами
- Применяет model defaults

Example:
    >>> adapter = IntakeAdapter()
    >>> model, prompt, params = adapter.adapt_request(request)

See Also:
    - DOC-02-09: Стандарты документирования

"""

from typing import Any

from src.api.schemas.requests import CreateTaskRequest
from src.core.model_defaults import get_model_defaults
from src.providers.base import GenerationParams
from src.shared.logging import get_logger

logger = get_logger()


class IntakeAdapter:
    """Adapter для преобразования Intake-style запросов.

    Intake-style запросы имеют:
    - provider_config: {model_name, temperature, ...}
    - generation_params: {max_tokens, top_p, ...}
    - input_text: отдельный контекст (не промпт)
    - output_schema: alias для response_format

    Single Responsibility: адаптация формата запроса.
    НЕ отвечает за валидацию моделей, execution.
    """

    def __init__(self) -> None:
        """Инициализировать IntakeAdapter."""
        logger.info("IntakeAdapter инициализирован")

    def adapt_request(
        self,
        request: CreateTaskRequest,
    ) -> tuple[str, str, GenerationParams]:
        """Адаптировать Intake-style запрос к SOP LLM формату.

        Процесс адаптации:
        1. Определить модель (приоритет: provider_config.model_name > model)
        2. Объединить prompt и input_text (если есть)
        3. Адаптировать response_format
        4. Извлечь параметры генерации с приоритетами:
           - Прямые поля (temperature, max_tokens)
           - generation_params dict
           - provider_config dict
           - Model defaults
        5. Применить окончательные defaults

        Args:
            request: CreateTaskRequest от клиента

        Returns:
            tuple[model, prompt, params] для выполнения

        Raises:
            ValueError: Если не указана модель

        """
        # 1. Определить модель
        model_name = self._determine_model(request)

        # 2. Объединить промпт и input_text
        full_prompt = self._combine_prompt(request)

        # 3. Определить response_format
        response_format = self._determine_response_format(request)

        # 4. Извлечь параметры генерации
        params = self._extract_generation_params(
            request=request,
            model_name=model_name,
            response_format=response_format,
        )

        logger.debug(
            "Запрос адаптирован",
            model=model_name,
            prompt_length=len(full_prompt),
            has_input_text=request.input_text is not None,
            has_response_format=response_format is not None,
        )

        return model_name, full_prompt, params

    def _determine_model(self, request: CreateTaskRequest) -> str:
        """Определить название модели.

        Приоритет:
        1. provider_config.model_name
        2. model field

        Args:
            request: CreateTaskRequest

        Returns:
            Название модели

        Raises:
            ValueError: Если модель не указана

        """
        model_name = request.model

        # Проверить provider_config (приоритет выше)
        if request.provider_config and "model_name" in request.provider_config:
            model_name = request.provider_config["model_name"]

        if not model_name:
            msg = "Модель не указана: укажите 'model' или 'provider_config.model_name'"
            raise ValueError(msg)

        return model_name

    def _combine_prompt(self, request: CreateTaskRequest) -> str:
        """Объединить prompt и input_text.

        Если input_text указан, добавляется к промпту через двойной перевод строки.

        Args:
            request: CreateTaskRequest

        Returns:
            Полный промпт

        """
        full_prompt = request.prompt

        if request.input_text:
            # ВАЖНО: Это временный костыль для совместимости с Intake
            # В будущем нужно использовать PromptService с templates
            full_prompt = f"{request.prompt}\n\n{request.input_text}"

            logger.debug(
                "input_text объединён с prompt",
                prompt_length=len(request.prompt),
                input_text_length=len(request.input_text),
                total_length=len(full_prompt),
            )

        return full_prompt

    def _determine_response_format(self, request: CreateTaskRequest) -> dict[str, Any] | None:
        """Определить response_format.

        Приоритет:
        1. output_schema (Intake-style)
        2. response_format (OpenAI-style)

        Args:
            request: CreateTaskRequest

        Returns:
            Response format dict или None

        """
        if request.output_schema:
            return request.output_schema

        return request.response_format

    def _extract_generation_params(
        self,
        request: CreateTaskRequest,
        model_name: str,
        response_format: dict[str, Any] | None,
    ) -> GenerationParams:
        """Извлечь параметры генерации с приоритетами.

        Приоритет (от высшего к низшему):
        1. Прямые поля (request.temperature, request.max_tokens)
        2. generation_params dict
        3. provider_config dict
        4. Model defaults (из конфигурации)
        5. GenerationParams defaults

        Args:
            request: CreateTaskRequest
            model_name: Название модели
            response_format: Response format (уже определён)

        Returns:
            GenerationParams с параметрами

        """
        # Получить model defaults
        model_defaults = get_model_defaults(model_name)

        # Извлечь из различных источников
        temperature = (
            request.temperature
            or (request.generation_params or {}).get("temperature")
            or (request.provider_config or {}).get("temperature")
            or model_defaults.get("temperature")
        )

        max_tokens = (
            request.max_tokens
            or (request.generation_params or {}).get("max_tokens")
            or (request.provider_config or {}).get("max_tokens")
            or model_defaults.get("max_tokens")
        )

        # Остальные параметры (с defaults из request или model_defaults)
        top_p = request.top_p or model_defaults.get("top_p", 1.0)
        top_k = request.top_k or model_defaults.get("top_k", 40)
        frequency_penalty = request.frequency_penalty or model_defaults.get("frequency_penalty", 0.0)
        presence_penalty = request.presence_penalty or model_defaults.get("presence_penalty", 0.0)

        # Собрать параметры
        params = GenerationParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop_sequences=request.stop_sequences,
            seed=request.seed,
            response_format=response_format,
            grammar=request.grammar,
            extra=request.extra_params,
        )

        logger.debug(
            "Параметры генерации извлечены",
            model=model_name,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            has_response_format=response_format is not None,
        )

        return params


# Singleton instance
_adapter_instance: IntakeAdapter | None = None


def get_intake_adapter() -> IntakeAdapter:
    """Получить singleton instance IntakeAdapter.

    Returns:
        Глобальный экземпляр IntakeAdapter

    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = IntakeAdapter()
    return _adapter_instance
