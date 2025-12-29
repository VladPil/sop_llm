"""Менеджер провайдеров - центральный фасад для управления всеми LLM провайдерами.

Реализует Facade Pattern и Strategy Pattern.
"""

from typing import Any

from loguru import logger

from src.modules.llm.formatters import JSONResponseParser
from src.modules.llm.providers import BaseLLMProvider, LLMProviderFactory
from src.modules.llm.services.json_fixer import json_fixer
from src.shared.errors import NotFoundError, ProviderUnavailableError


class ProviderManager:
    """Менеджер для управления всеми LLM провайдерами."""

    def __init__(self) -> None:
        """Инициализация менеджера."""
        self.providers: dict[str, BaseLLMProvider] = {}
        self.default_provider: str | None = None
        self.json_parser = JSONResponseParser()
        self.json_fixer = json_fixer

    async def initialize(self, providers_config: list[dict[str, Any]]) -> None:
        """Инициализация провайдеров из конфигурации."""
        logger.info(f"Инициализация ProviderManager с {len(providers_config)} провайдерами")

        initialized_count = 0

        for provider_config in providers_config:
            name = provider_config.get("name")
            enabled = provider_config.get("enabled", True)

            if not enabled:
                logger.info(f"Провайдер {name} отключён в конфигурации")
                continue

            if not name:
                logger.warning("Пропущен провайдер без имени в конфигурации")
                continue

            config = provider_config.get("config", {})

            try:
                provider = LLMProviderFactory.create(name, config)
                await provider.initialize()
                self.providers[name] = provider
                initialized_count += 1

                if self.default_provider is None:
                    self.default_provider = name
                    logger.info(f"Провайдер {name} установлен как default")

                logger.info(f"Провайдер {name} успешно инициализирован")

            except ValueError as e:
                logger.warning(f"Провайдер {name} не инициализирован: {e}")
            except Exception as e:
                logger.error(f"Не удалось инициализировать провайдер {name}: {e}", exc_info=True)

        logger.info(
            f"ProviderManager инициализирован: {initialized_count}/{len(providers_config)} провайдеров готовы"
        )

        if not self.providers:
            raise RuntimeError("Ни один провайдер не был инициализирован")

    async def generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        expected_format: str = "text",
        json_schema: dict | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Генерация текста через указанного провайдера."""
        provider_name = provider or self.default_provider

        if not provider_name:
            raise ValueError("Провайдер не указан и default провайдер не установлен")

        if provider_name not in self.providers:
            available = ", ".join(self.providers.keys())
            raise NotFoundError(resource_type="provider", resource_id=provider_name, details=f"Доступные: {available}")

        provider_instance = self.providers[provider_name]

        if not provider_instance.is_available():
            raise ProviderUnavailableError(provider_name=provider_name)

        logger.info(f"Генерация через провайдера '{provider_name}', model={model}, max_tokens={max_tokens}")

        result = await provider_instance.generate(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            expected_format=expected_format,
            **kwargs,
        )

        if expected_format == "json":
            result = await self._process_json_response(
                result=result, json_schema=json_schema, original_prompt=prompt
            )

        return result

    async def _process_json_response(
        self, result: dict[str, Any], json_schema: dict | None, original_prompt: str
    ) -> dict[str, Any]:
        """Обрабатывает JSON ответ: парсит, валидирует, исправляет при необходимости."""
        generated_text = result["text"]

        try:
            parsed = self.json_parser.parse(
                generated_text, expected_format="json", json_schema=json_schema
            )
            result["parsed"] = parsed
            result["was_fixed"] = False
            result["fix_attempts"] = 0
            logger.info("JSON успешно распарсен без исправлений")
            return result

        except Exception as parse_error:
            logger.warning(f"Не удалось распарсить JSON: {parse_error}")

        logger.info("Вызываем JSONFixer для исправления невалидного JSON...")

        try:
            fix_result = await self.json_fixer.fix_json(
                broken_json=generated_text, original_prompt=original_prompt, schema=json_schema
            )

            if fix_result["success"]:
                logger.info(f"JSON успешно исправлен после {fix_result['attempts']} попыток")
                result["text"] = fix_result["fixed_json"]
                result["parsed"] = fix_result["parsed"]
                result["was_fixed"] = True
                result["fix_attempts"] = fix_result["attempts"]
            else:
                logger.error(f"Не удалось исправить JSON: {fix_result['error']}")
                result["parsed"] = None
                result["was_fixed"] = False
                result["fix_attempts"] = fix_result.get("attempts", 0)
                result["parse_error"] = fix_result["error"]

        except Exception as fixer_error:
            logger.error(f"Ошибка при вызове JSONFixer: {fixer_error}", exc_info=True)
            result["parsed"] = None
            result["was_fixed"] = False
            result["fix_attempts"] = 0
            result["parse_error"] = f"JSONFixer error: {fixer_error!s}"

        return result

    def list_providers(self) -> list[dict[str, Any]]:
        """Получение списка всех провайдеров с информацией."""
        result = []

        for name, provider in self.providers.items():
            result.append(
                {
                    "name": name,
                    "is_available": provider.is_available(),
                    "capabilities": [cap.value for cap in provider.capabilities],
                    "is_default": name == self.default_provider,
                }
            )

        return result

    def get_provider(self, name: str) -> BaseLLMProvider | None:
        """Получение провайдера по имени."""
        return self.providers.get(name)

    def is_provider_available(self, name: str) -> bool:
        """Проверка доступности провайдера."""
        provider = self.providers.get(name)
        return provider is not None and provider.is_available()

    def get_stats(self, provider: str | None = None) -> dict[str, Any]:
        """Получение статистики провайдеров."""
        if provider:
            provider_instance = self.providers.get(provider)
            if not provider_instance:
                return {"error": f"Provider {provider} not found"}
            return provider_instance.get_stats()

        all_stats = {
            "total_providers": len(self.providers),
            "default_provider": self.default_provider,
            "providers": {},
        }

        for name, provider_instance in self.providers.items():
            all_stats["providers"][name] = provider_instance.get_stats()

        return all_stats

    async def cleanup(self) -> None:
        """Очистка всех провайдеров."""
        logger.info("Очистка всех провайдеров...")

        for name, provider in self.providers.items():
            try:
                await provider.cleanup()
                logger.info(f"Провайдер {name} очищен")
            except Exception as e:
                logger.error(f"Ошибка при очистке провайдера {name}: {e}")

        self.providers.clear()
        self.default_provider = None

        logger.info("Все провайдеры очищены")


# Глобальный экземпляр
provider_manager = ProviderManager()
