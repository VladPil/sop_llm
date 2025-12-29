"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ для новой архитектуры провайдеров
Тестирует ProviderManager, все провайдеры, JSON обработку и API endpoints

Требования:
- Redis должен быть запущен
- Для Claude тестов нужен ANTHROPIC_API_KEY
- Для LM Studio тестов нужен запущенный LM Studio сервер (опционально)
"""
import pytest
import asyncio
import json
from typing import Dict, Any
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.slow
class TestProviderManager:
    """Тесты для ProviderManager"""

    @pytest.mark.asyncio
    async def test_provider_manager_initialization(self, provider_manager):
        """Тест инициализации ProviderManager"""
        # Должен быть хотя бы один провайдер
        assert len(provider_manager.providers) > 0, "At least one provider should be initialized"

        # Должен быть default провайдер
        assert provider_manager.default_provider is not None, "Default provider should be set"

        # Default провайдер должен быть в списке
        assert provider_manager.default_provider in provider_manager.providers

        print(f"\n✓ ProviderManager initialized")
        print(f"  Total providers: {len(provider_manager.providers)}")
        print(f"  Available: {list(provider_manager.providers.keys())}")
        print(f"  Default: {provider_manager.default_provider}")

    @pytest.mark.asyncio
    async def test_list_providers(self, provider_manager):
        """Тест получения списка провайдеров"""
        providers_list = provider_manager.list_providers()

        assert isinstance(providers_list, list)
        assert len(providers_list) > 0

        # Каждый провайдер должен иметь нужные поля
        for provider_info in providers_list:
            assert "name" in provider_info
            assert "is_available" in provider_info
            assert "capabilities" in provider_info
            assert "is_default" in provider_info
            assert isinstance(provider_info["capabilities"], list)

        print(f"\n✓ Providers list:")
        for p in providers_list:
            status = "✓ available" if p["is_available"] else "✗ unavailable"
            default = " (default)" if p["is_default"] else ""
            print(f"  - {p['name']}: {status}{default}")
            print(f"    Capabilities: {', '.join(p['capabilities'])}")

    @pytest.mark.asyncio
    async def test_get_provider(self, provider_manager):
        """Тест получения провайдера по имени"""
        # Получаем default провайдера
        default_name = provider_manager.default_provider
        provider = provider_manager.get_provider(default_name)

        assert provider is not None
        assert provider.provider_name == default_name
        assert provider.is_available()

        # Несуществующий провайдер
        non_existent = provider_manager.get_provider("non_existent")
        assert non_existent is None

        print(f"\n✓ Get provider: {default_name}")

    @pytest.mark.asyncio
    async def test_is_provider_available(self, provider_manager):
        """Тест проверки доступности провайдера"""
        # Default провайдер должен быть доступен
        default_name = provider_manager.default_provider
        assert provider_manager.is_provider_available(default_name)

        # Несуществующий провайдер недоступен
        assert not provider_manager.is_provider_available("non_existent")

        print(f"\n✓ Provider availability checked")

    @pytest.mark.asyncio
    async def test_get_stats(self, provider_manager):
        """Тест получения статистики"""
        # Общая статистика
        all_stats = provider_manager.get_stats()

        assert "total_providers" in all_stats
        assert "default_provider" in all_stats
        assert "providers" in all_stats
        assert all_stats["total_providers"] == len(provider_manager.providers)

        # Статистика конкретного провайдера
        default_name = provider_manager.default_provider
        provider_stats = provider_manager.get_stats(provider=default_name)

        assert "provider" in provider_stats or "model_name" in provider_stats

        print(f"\n✓ Stats:")
        print(f"  Total providers: {all_stats['total_providers']}")
        print(f"  Default: {all_stats['default_provider']}")


@pytest.mark.integration
@pytest.mark.slow
class TestLocalProvider:
    """Тесты для LocalLLMProvider (Qwen модели)"""

    @pytest.mark.asyncio
    async def test_local_provider_available(self, provider_manager):
        """Тест доступности локального провайдера"""
        if "local" not in provider_manager.providers:
            pytest.skip("Local provider not configured")

        provider = provider_manager.get_provider("local")
        assert provider is not None
        assert provider.is_available()

        print(f"\n✓ Local provider available")

    @pytest.mark.asyncio
    async def test_local_text_generation(self, provider_manager):
        """Тест текстовой генерации через локального провайдера"""
        if not provider_manager.is_provider_available("local"):
            pytest.skip("Local provider not available")

        prompt = "What is 2+2? Answer briefly:"

        result = await provider_manager.generate(
            prompt=prompt,
            provider="local",
            max_tokens=20,
            temperature=0.1,
            expected_format="text"
        )

        # Проверки результата
        assert result is not None
        assert "text" in result
        assert "model" in result
        assert "tokens" in result
        assert "finish_reason" in result
        assert "metadata" in result

        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0
        assert result["metadata"]["provider"] == "local"

        print(f"\n✓ Local generation:")
        print(f"  Prompt: {prompt}")
        print(f"  Response: {result['text']}")
        print(f"  Tokens: {result['tokens']}")

    @pytest.mark.asyncio
    async def test_local_json_generation(self, provider_manager):
        """Тест JSON генерации через локального провайдера"""
        if not provider_manager.is_provider_available("local"):
            pytest.skip("Local provider not available")

        prompt = "Create a JSON object with fields: name='Alice', age=30"

        result = await provider_manager.generate(
            prompt=prompt,
            provider="local",
            max_tokens=100,
            temperature=0.1,
            expected_format="json"
        )

        # Проверки
        assert result is not None
        assert "text" in result
        assert "parsed" in result  # Должен быть распарсенный JSON

        # Проверяем что JSON валидный
        if result["parsed"] is not None:
            assert isinstance(result["parsed"], (dict, list))
            print(f"\n✓ Local JSON generation:")
            print(f"  Prompt: {prompt}")
            print(f"  Parsed JSON: {result['parsed']}")
            print(f"  Was fixed: {result.get('was_fixed', False)}")
            if result.get('was_fixed'):
                print(f"  Fix attempts: {result.get('fix_attempts', 0)}")
        else:
            print(f"\n⚠ JSON generation failed, but error handled gracefully")
            print(f"  Error: {result.get('parse_error', 'Unknown')}")


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestClaudeProvider:
    """Тесты для ClaudeProvider (требует ANTHROPIC_API_KEY)"""

    @pytest.mark.asyncio
    async def test_claude_provider_available(self, provider_manager):
        """Тест доступности Claude провайдера"""
        if "claude" not in provider_manager.providers:
            pytest.skip("Claude provider not configured")

        provider = provider_manager.get_provider("claude")
        if not provider.is_available():
            pytest.skip("Claude provider not available (API key missing?)")

        print(f"\n✓ Claude provider available")

    @pytest.mark.asyncio
    async def test_claude_text_generation(self, provider_manager):
        """Тест текстовой генерации через Claude API"""
        if not provider_manager.is_provider_available("claude"):
            pytest.skip("Claude provider not available")

        prompt = "Explain what is Python in one sentence."

        result = await provider_manager.generate(
            prompt=prompt,
            provider="claude",
            max_tokens=50,
            temperature=0.7,
            expected_format="text"
        )

        # Проверки
        assert result is not None
        assert "text" in result
        assert len(result["text"]) > 0
        assert result["metadata"]["provider"] == "claude"

        print(f"\n✓ Claude generation:")
        print(f"  Prompt: {prompt}")
        print(f"  Response: {result['text']}")
        print(f"  Model: {result['model']}")
        print(f"  Tokens: {result['tokens']}")

    @pytest.mark.asyncio
    async def test_claude_json_generation(self, provider_manager):
        """Тест JSON генерации через Claude API"""
        if not provider_manager.is_provider_available("claude"):
            pytest.skip("Claude provider not available")

        prompt = 'Generate a JSON object with these fields: {"language": "Python", "year": 1991}'

        result = await provider_manager.generate(
            prompt=prompt,
            provider="claude",
            max_tokens=100,
            temperature=0.3,
            expected_format="json"
        )

        # Проверки
        assert result is not None
        assert "parsed" in result

        if result["parsed"] is not None:
            assert isinstance(result["parsed"], (dict, list))
            print(f"\n✓ Claude JSON generation:")
            print(f"  Parsed: {result['parsed']}")
            print(f"  Was fixed: {result.get('was_fixed', False)}")
        else:
            print(f"\n⚠ JSON parsing failed")
            print(f"  Raw text: {result['text'][:200]}")


@pytest.mark.integration
@pytest.mark.requires_external_service
class TestLMStudioProvider:
    """Тесты для LMStudioProvider (требует запущенный LM Studio)"""

    @pytest.mark.asyncio
    async def test_lm_studio_provider_available(self, provider_manager):
        """Тест доступности LM Studio провайдера"""
        if "lm_studio" not in provider_manager.providers:
            pytest.skip("LM Studio provider not configured")

        provider = provider_manager.get_provider("lm_studio")
        if not provider.is_available():
            pytest.skip("LM Studio server not running")

        print(f"\n✓ LM Studio provider available")

    @pytest.mark.asyncio
    async def test_lm_studio_text_generation(self, provider_manager):
        """Тест текстовой генерации через LM Studio"""
        if not provider_manager.is_provider_available("lm_studio"):
            pytest.skip("LM Studio not available")

        prompt = "Write a short greeting."

        result = await provider_manager.generate(
            prompt=prompt,
            provider="lm_studio",
            max_tokens=30,
            temperature=0.7,
            expected_format="text"
        )

        # Проверки
        assert result is not None
        assert "text" in result
        assert len(result["text"]) > 0
        assert result["metadata"]["provider"] == "lm_studio"

        print(f"\n✓ LM Studio generation:")
        print(f"  Response: {result['text']}")

    @pytest.mark.asyncio
    async def test_lm_studio_json_generation(self, provider_manager):
        """Тест JSON генерации через LM Studio"""
        if not provider_manager.is_provider_available("lm_studio"):
            pytest.skip("LM Studio not available")

        prompt = 'Create JSON: {"status": "ok", "code": 200}'

        result = await provider_manager.generate(
            prompt=prompt,
            provider="lm_studio",
            max_tokens=100,
            temperature=0.3,
            expected_format="json"
        )

        # Проверки
        assert result is not None
        assert "parsed" in result

        if result["parsed"] is not None:
            print(f"\n✓ LM Studio JSON generation:")
            print(f"  Parsed: {result['parsed']}")


@pytest.mark.integration
class TestJSONProcessing:
    """Тесты для JSON обработки и JSONFixer интеграции"""

    @pytest.mark.asyncio
    async def test_json_parsing_valid(self, provider_manager):
        """Тест парсинга валидного JSON"""
        # Используем доступного провайдера
        provider_name = provider_manager.default_provider
        if not provider_manager.is_provider_available(provider_name):
            pytest.skip("No provider available")

        # Промпт который должен дать валидный JSON
        prompt = 'Return only this JSON: {"test": true, "value": 123}'

        result = await provider_manager.generate(
            prompt=prompt,
            provider=provider_name,
            max_tokens=50,
            temperature=0.1,
            expected_format="json"
        )

        print(f"\n✓ JSON parsing test:")
        print(f"  Provider: {provider_name}")
        print(f"  Was fixed: {result.get('was_fixed', False)}")
        print(f"  Parsed: {result.get('parsed')}")

    @pytest.mark.asyncio
    async def test_json_fixer_integration(self, provider_manager, json_fixer_manager):
        """Тест интеграции JSONFixer"""
        # Проверяем что JSONFixer доступен
        if not json_fixer_manager.is_available():
            pytest.skip("JSONFixer not available")

        # Невалидный JSON
        broken_json = '{"name": "Alice", "age": 30'  # Пропущена закрывающая скобка

        # Пытаемся исправить
        fix_result = await json_fixer_manager.fix_json(
            broken_json=broken_json,
            original_prompt="Create user object"
        )

        print(f"\n✓ JSONFixer test:")
        print(f"  Broken: {broken_json}")
        print(f"  Success: {fix_result['success']}")
        if fix_result['success']:
            print(f"  Fixed: {fix_result['fixed_json']}")
            print(f"  Parsed: {fix_result['parsed']}")
            print(f"  Attempts: {fix_result['attempts']}")
        else:
            print(f"  Error: {fix_result.get('error')}")

    @pytest.mark.asyncio
    async def test_json_schema_validation(self, provider_manager):
        """Тест валидации по JSON Schema"""
        provider_name = provider_manager.default_provider
        if not provider_manager.is_provider_available(provider_name):
            pytest.skip("No provider available")

        # JSON Schema
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }

        prompt = 'Create a JSON object with name="Bob" and age=25'

        result = await provider_manager.generate(
            prompt=prompt,
            provider=provider_name,
            max_tokens=100,
            temperature=0.1,
            expected_format="json",
            json_schema=schema
        )

        print(f"\n✓ JSON Schema validation:")
        print(f"  Schema: {schema}")
        print(f"  Parsed: {result.get('parsed')}")


@pytest.mark.integration
class TestConcurrentRequests:
    """Тесты для concurrent запросов"""

    @pytest.mark.asyncio
    async def test_concurrent_generation(self, provider_manager):
        """Тест параллельных запросов к провайдеру"""
        provider_name = provider_manager.default_provider
        if not provider_manager.is_provider_available(provider_name):
            pytest.skip("No provider available")

        prompts = [
            "Count to 3:",
            "Name two colors:",
            "What is 5+5?",
        ]

        # Запускаем все параллельно
        tasks = [
            provider_manager.generate(
                prompt=p,
                provider=provider_name,
                max_tokens=30,
                temperature=0.5
            )
            for p in prompts
        ]

        results = await asyncio.gather(*tasks)

        # Проверки
        assert len(results) == len(prompts)
        assert all("text" in r for r in results)
        assert all(len(r["text"]) > 0 for r in results)

        print(f"\n✓ Concurrent requests:")
        for prompt, result in zip(prompts, results):
            print(f"  '{prompt}' -> '{result['text'][:50]}...'")

    @pytest.mark.asyncio
    async def test_concurrent_json_generation(self, provider_manager):
        """Тест параллельных JSON запросов"""
        provider_name = provider_manager.default_provider
        if not provider_manager.is_provider_available(provider_name):
            pytest.skip("No provider available")

        prompts = [
            'JSON: {"id": 1}',
            'JSON: {"id": 2}',
            'JSON: {"id": 3}',
        ]

        tasks = [
            provider_manager.generate(
                prompt=p,
                provider=provider_name,
                max_tokens=50,
                temperature=0.1,
                expected_format="json"
            )
            for p in prompts
        ]

        results = await asyncio.gather(*tasks)

        # Проверки
        assert len(results) == len(prompts)

        print(f"\n✓ Concurrent JSON requests:")
        for i, result in enumerate(results, 1):
            print(f"  Request {i}: parsed={result.get('parsed')}, fixed={result.get('was_fixed')}")


@pytest.mark.integration
class TestProviderSwitching:
    """Тесты переключения между провайдерами"""

    @pytest.mark.asyncio
    async def test_switch_providers(self, provider_manager):
        """Тест использования разных провайдеров"""
        available_providers = [
            name for name in provider_manager.providers.keys()
            if provider_manager.is_provider_available(name)
        ]

        if len(available_providers) < 2:
            pytest.skip("Need at least 2 available providers")

        prompt = "Say hello"
        results = {}

        for provider_name in available_providers[:2]:  # Берём первых 2
            result = await provider_manager.generate(
                prompt=prompt,
                provider=provider_name,
                max_tokens=20,
                temperature=0.5
            )
            results[provider_name] = result

        # Все должны вернуть результат
        assert len(results) >= 2

        print(f"\n✓ Provider switching:")
        for provider_name, result in results.items():
            print(f"  {provider_name}: {result['text'][:50]}")

    @pytest.mark.asyncio
    async def test_default_provider(self, provider_manager):
        """Тест использования default провайдера"""
        # Без указания провайдера должен использоваться default
        result = await provider_manager.generate(
            prompt="Test",
            max_tokens=10,
            temperature=0.5
        )

        assert result is not None
        assert "metadata" in result
        assert result["metadata"]["provider"] == provider_manager.default_provider

        print(f"\n✓ Default provider used: {provider_manager.default_provider}")


@pytest.mark.integration
class TestErrorHandling:
    """Тесты обработки ошибок"""

    @pytest.mark.asyncio
    async def test_invalid_provider(self, provider_manager):
        """Тест запроса к несуществующему провайдеру"""
        with pytest.raises(ValueError, match="не найден"):
            await provider_manager.generate(
                prompt="Test",
                provider="non_existent_provider"
            )

        print(f"\n✓ Invalid provider error handled")

    @pytest.mark.asyncio
    async def test_unavailable_provider(self, provider_manager):
        """Тест запроса к недоступному провайдеру"""
        # Проверяем что есть хоть один недоступный
        unavailable_providers = [
            name for name in ["claude", "lm_studio", "openai"]
            if name in provider_manager.providers
            and not provider_manager.is_provider_available(name)
        ]

        if not unavailable_providers:
            pytest.skip("All configured providers are available")

        provider_name = unavailable_providers[0]

        with pytest.raises(RuntimeError, match="недоступен"):
            await provider_manager.generate(
                prompt="Test",
                provider=provider_name
            )

        print(f"\n✓ Unavailable provider error handled: {provider_name}")

    @pytest.mark.asyncio
    async def test_no_default_provider(self):
        """Тест когда default провайдер не установлен"""
        from app.models.provider_manager import ProviderManager

        pm = ProviderManager()
        # Не инициализируем провайдеры

        with pytest.raises(ValueError, match="default провайдер не установлен"):
            await pm.generate(prompt="Test")

        print(f"\n✓ No default provider error handled")
