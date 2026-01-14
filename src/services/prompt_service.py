"""Prompt Management Service с Langfuse integration.

Управление промптами через Langfuse:
- Загрузка prompt templates из Langfuse
- Версионирование промптов
- Provider-specific форматирование (Claude, GPT, local models)
- Jinja2 templating для переменных
- Кэширование промптов

Example:
    >>> from src.services.prompt_service import PromptService
    >>> service = PromptService()
    >>>
    >>> # Получить промпт из Langfuse
    >>> prompt = await service.get_prompt("task_generation", version=2)
    >>>
    >>> # Скомпилировать с переменными
    >>> compiled = await service.compile_prompt(
    ...     prompt_name="task_generation",
    ...     variables={"task": "Analyze data", "context": "CSV file"},
    ...     provider_type="litellm"
    ... )

See Also:
    - DOC-02-09: Стандарты документирования
    - Langfuse Prompts: https://langfuse.com/docs/prompts

"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal

from jinja2 import Environment, StrictUndefined, Template, meta
from langfuse import Langfuse
from pydantic import BaseModel, Field

from src.providers.base import ChatMessage
from src.services.observability import get_langfuse_client
from src.shared.logging import get_logger

logger = get_logger()


class PromptTemplate(BaseModel):
    """Prompt template из Langfuse.

    Attributes:
        name: Название промпта в Langfuse
        version: Версия промпта
        template: Jinja2 template строка
        variables: Список переменных в template
        config: Дополнительная конфигурация (system_prompt, role, etc.)
        created_at: Дата создания

    """

    name: str = Field(description="Название промпта")
    version: int = Field(description="Версия промпта")
    template: str = Field(description="Jinja2 template строка")
    variables: list[str] = Field(default_factory=list, description="Переменные в template")
    config: dict[str, Any] = Field(default_factory=dict, description="Дополнительная конфигурация")
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")


class CompiledPrompt(BaseModel):
    """Скомпилированный промпт, готовый для отправки в LLM.

    Attributes:
        text: Финальный текст промпта (для simple providers)
        messages: Chat messages (для Chat Completions API)
        metadata: Метаданные (prompt_name, version, variables)

    """

    text: str | None = Field(default=None, description="Финальный текст промпта")
    messages: list[ChatMessage] | None = Field(default=None, description="Chat messages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Метаданные")


ProviderType = Literal["litellm", "local", "custom"]


class PromptService:
    """Service для управления промптами через Langfuse.

    Основные возможности:
    - Загрузка prompt templates из Langfuse
    - Версионирование промптов (production/staging)
    - Provider-specific форматирование
    - Jinja2 templating с валидацией переменных
    - LRU кэширование для производительности

    Attributes:
        langfuse_client: Langfuse клиент для API
        jinja_env: Jinja2 environment для templating
        cache_ttl: TTL для кэша промптов (секунды)

    """

    def __init__(
        self,
        langfuse_client: Langfuse | None = None,
        cache_ttl: int = 300,  # 5 минут
    ) -> None:
        """Инициализировать PromptService.

        Args:
            langfuse_client: Langfuse клиент (если None - создаётся автоматически)
            cache_ttl: TTL для кэша промптов в секундах

        """
        self.langfuse_client = langfuse_client or get_langfuse_client()
        self.cache_ttl = cache_ttl

        self.jinja_env = Environment(
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._template_cache: dict[tuple[str, int | None], tuple[PromptTemplate, datetime]] = {}

        logger.info(
            "PromptService инициализирован",
            cache_ttl=cache_ttl,
            langfuse_enabled=self.langfuse_client is not None,
        )

    async def get_prompt(
        self,
        name: str,
        version: int | None = None,
        fallback: str | None = None,
    ) -> PromptTemplate:
        """Получить prompt template из Langfuse.

        Args:
            name: Название промпта в Langfuse
            version: Версия промпта (None = latest production)
            fallback: Fallback template если промпт не найден в Langfuse

        Returns:
            PromptTemplate с template и метаданными

        Raises:
            ValueError: Если промпт не найден и нет fallback

        Note:
            Результаты кэшируются на cache_ttl секунд.

        """
        cache_key = (name, version)

        if cache_key in self._template_cache:
            template, expiry = self._template_cache[cache_key]
            if datetime.now() < expiry:
                logger.debug("Промпт получен из кэша", name=name, version=version)
                return template

        try:
            if self.langfuse_client is None:
                raise RuntimeError("Langfuse client не инициализирован")

            langfuse_prompt = self.langfuse_client.get_prompt(
                name=name,
                version=version,
                label="production" if version is None else None,
            )

            template_str = langfuse_prompt.prompt
            variables = self._extract_variables(template_str)
            config = langfuse_prompt.config or {}

            template = PromptTemplate(
                name=name,
                version=langfuse_prompt.version,
                template=template_str,
                variables=variables,
                config=config,
            )

            self._template_cache[cache_key] = (template, datetime.now() + timedelta(seconds=self.cache_ttl))

            logger.info(
                "Промпт загружен из Langfuse",
                name=name,
                version=template.version,
                variables=variables,
            )

            return template

        except Exception as e:
            logger.warning(
                "Ошибка загрузки промпта из Langfuse",
                name=name,
                version=version,
                error=str(e),
            )

            if fallback is not None:
                logger.info("Используется fallback template", name=name)
                variables = self._extract_variables(fallback)
                return PromptTemplate(
                    name=name,
                    version=0,
                    template=fallback,
                    variables=variables,
                    config={},
                )

            msg = f"Промпт '{name}' не найден в Langfuse и нет fallback"
            raise ValueError(msg) from e

    async def compile_prompt(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        provider_type: ProviderType = "litellm",
        version: int | None = None,
        fallback_template: str | None = None,
    ) -> CompiledPrompt:
        """Скомпилировать промпт с переменными для конкретного provider.

        Процесс:
        1. Загрузить template из Langfuse (или fallback)
        2. Скомпилировать Jinja2 template с переменными
        3. Форматировать для конкретного provider (Claude, GPT, local)

        Args:
            prompt_name: Название промпта в Langfuse
            variables: Переменные для Jinja2 template
            provider_type: Тип провайдера для форматирования
            version: Версия промпта (None = latest production)
            fallback_template: Fallback если промпт не найден

        Returns:
            CompiledPrompt с text или messages

        Raises:
            ValueError: Если отсутствуют обязательные переменные

        Example:
            >>> compiled = await service.compile_prompt(
            ...     prompt_name="task_generation",
            ...     variables={"task": "Analyze data", "context": "CSV file"},
            ...     provider_type="litellm"
            ... )

        """
        template = await self.get_prompt(
            name=prompt_name,
            version=version,
            fallback=fallback_template,
        )

        try:
            jinja_template: Template = self.jinja_env.from_string(template.template)
            compiled_text = jinja_template.render(**variables)
        except Exception as e:
            logger.exception(
                "Ошибка компиляции Jinja2 template",
                prompt_name=prompt_name,
                variables=list(variables.keys()),
                error=str(e),
            )
            msg = f"Ошибка компиляции промпта '{prompt_name}': {e}"
            raise ValueError(msg) from e

        formatter = self._get_formatter(provider_type)
        compiled = formatter(
            text=compiled_text,
            config=template.config,
        )

        # Добавить метаданные
        compiled.metadata = {
            "prompt_name": prompt_name,
            "prompt_version": template.version,
            "variables": list(variables.keys()),
            "provider_type": provider_type,
        }

        logger.debug(
            "Промпт скомпилирован",
            prompt_name=prompt_name,
            version=template.version,
            provider_type=provider_type,
        )

        return compiled

    def _extract_variables(self, template: str) -> list[str]:
        """Извлечь список переменных из Jinja2 template.

        Args:
            template: Jinja2 template строка

        Returns:
            Список имён переменных

        """
        try:
            ast = self.jinja_env.parse(template)
            return sorted(meta.find_undeclared_variables(ast))
        except Exception:
            return []

    def _get_formatter(self, provider_type: ProviderType) -> Callable[..., CompiledPrompt]:
        """Получить formatter функцию для конкретного provider.

        Args:
            provider_type: Тип провайдера

        Returns:
            Formatter функция

        """
        formatters = {
            "litellm": self._format_for_litellm,
            "local": self._format_for_local,
            "custom": self._format_simple,
        }

        return formatters.get(provider_type, self._format_simple)

    def _format_for_litellm(self, text: str, config: dict[str, Any]) -> CompiledPrompt:
        """Форматировать промпт для LiteLLM (Chat Completions API).

        LiteLLM поддерживает OpenAI-style messages с ролями system/user/assistant.

        Args:
            text: Скомпилированный текст промпта
            config: Конфигурация из Langfuse (может содержать system_prompt)

        Returns:
            CompiledPrompt с messages

        """
        messages = []

        system_prompt = config.get("system_prompt")
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))

        messages.append(ChatMessage(role="user", content=text))

        return CompiledPrompt(messages=messages)

    def _format_for_local(self, text: str, config: dict[str, Any]) -> CompiledPrompt:
        """Форматировать промпт для локальных моделей (llama.cpp).

        Локальные модели требуют специальных токенов для разных ролей.
        Формат зависит от модели (Llama, Mistral, etc.).

        Args:
            text: Скомпилированный текст промпта
            config: Конфигурация из Langfuse

        Returns:
            CompiledPrompt с text (форматированный с токенами)

        """
        system_prompt = config.get("system_prompt")
        model_type = config.get("model_type", "llama")

        if model_type == "llama":
            if system_prompt:
                formatted = f"<|system|>\n{system_prompt}\n<|user|>\n{text}\n<|assistant|>\n"
            else:
                formatted = f"<|user|>\n{text}\n<|assistant|>\n"
        elif model_type == "mistral":
            formatted = f"[INST] {system_prompt}\n\n{text} [/INST]" if system_prompt else f"[INST] {text} [/INST]"
        elif system_prompt:
            formatted = f"{system_prompt}\n\n{text}"
        else:
            formatted = text

        return CompiledPrompt(text=formatted)

    def _format_simple(self, text: str, config: dict[str, Any]) -> CompiledPrompt:
        """Простой форматтер - возвращает text as-is.

        Args:
            text: Скомпилированный текст промпта
            config: Конфигурация (игнорируется)

        Returns:
            CompiledPrompt с text

        """
        return CompiledPrompt(text=text)

    def clear_cache(self) -> None:
        """Очистить кэш промптов."""
        self._template_cache.clear()
        logger.info("Кэш промптов очищен")


_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService:
    """Получить singleton instance PromptService.

    Returns:
        Глобальный экземпляр PromptService

    """
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


def set_prompt_service(service: PromptService) -> None:
    """Установить custom instance PromptService (для тестов).

    Args:
        service: Custom PromptService instance

    """
    global _prompt_service
    _prompt_service = service
