"""
Тесты для JSON Fixer Manager
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.models.json_fixer import JSONFixerManager
from src.utils.errors import GenerationError, ResourceLimitError


@pytest.fixture
def mock_model():
    """Мок модели для тестирования"""
    model = Mock()

    # model.generate должен возвращать тензор-подобный объект
    # который поддерживает индексацию [0]
    mock_output = Mock()
    mock_output.__getitem__ = Mock(return_value=[1, 2, 3])  # Имитация token IDs
    model.generate = Mock(return_value=mock_output)

    return model


@pytest.fixture
def mock_tokenizer():
    """Мок токенайзера для тестирования"""
    tokenizer = Mock()
    tokenizer.eos_token_id = 0

    # Мокируем __call__ для токенизации
    mock_inputs = Mock()
    mock_inputs.to = Mock(return_value={"input_ids": Mock(), "attention_mask": Mock()})
    tokenizer.return_value = mock_inputs

    # Мокируем decode - по умолчанию возвращает валидный JSON
    tokenizer.decode = Mock(return_value='{"key": "value"}')

    return tokenizer


@pytest.fixture
def json_fixer(mock_model, mock_tokenizer):
    """Фикстура JSON Fixer Manager с мок-моделью"""
    fixer = JSONFixerManager()
    fixer.model = mock_model
    fixer.tokenizer = mock_tokenizer
    fixer.is_loaded = True
    fixer.model_name = "test-model"
    fixer.device = "cpu"
    return fixer


class TestJSONValidation:
    """Тесты валидации JSON"""

    def test_validate_correct_json(self):
        """Тест валидации корректного JSON"""
        valid_json = '{"name": "John", "age": 30, "city": "New York"}'
        assert JSONFixerManager.validate_json(valid_json) is True

    def test_validate_correct_json_array(self):
        """Тест валидации корректного JSON массива"""
        valid_json = '[1, 2, 3, 4, 5]'
        assert JSONFixerManager.validate_json(valid_json) is True

    def test_validate_nested_json(self):
        """Тест валидации вложенного JSON"""
        valid_json = '''
        {
            "user": {
                "name": "Alice",
                "contacts": {
                    "email": "alice@example.com",
                    "phone": "+1234567890"
                }
            },
            "items": [1, 2, 3]
        }
        '''
        assert JSONFixerManager.validate_json(valid_json) is True

    def test_validate_invalid_json_missing_comma(self):
        """Тест валидации некорректного JSON с пропущенной запятой"""
        invalid_json = '{"name": "John" "age": 30}'
        assert JSONFixerManager.validate_json(invalid_json) is False

    def test_validate_invalid_json_missing_quote(self):
        """Тест валидации некорректного JSON с пропущенной кавычкой"""
        invalid_json = '{"name": John, "age": 30}'
        assert JSONFixerManager.validate_json(invalid_json) is False

    def test_validate_invalid_json_trailing_comma(self):
        """Тест валидации некорректного JSON с лишней запятой"""
        invalid_json = '{"name": "John", "age": 30,}'
        assert JSONFixerManager.validate_json(invalid_json) is False

    def test_validate_invalid_json_missing_bracket(self):
        """Тест валидации некорректного JSON с пропущенной скобкой"""
        invalid_json = '{"name": "John", "age": 30'
        assert JSONFixerManager.validate_json(invalid_json) is False

    def test_validate_empty_string(self):
        """Тест валидации пустой строки"""
        assert JSONFixerManager.validate_json('') is False

    def test_validate_with_schema_valid(self):
        """Тест валидации с JSON Schema - валидный случай"""
        json_string = '{"name": "John", "age": 30}'
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }
        assert JSONFixerManager.validate_json(json_string, schema) is True

    def test_validate_with_schema_invalid(self):
        """Тест валидации с JSON Schema - невалидный случай"""
        json_string = '{"name": "John", "age": "thirty"}'
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }
        assert JSONFixerManager.validate_json(json_string, schema) is False

    def test_validate_with_schema_missing_required(self):
        """Тест валидации с JSON Schema - отсутствует обязательное поле"""
        json_string = '{"name": "John"}'
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }
        assert JSONFixerManager.validate_json(json_string, schema) is False


class TestJSONCleanup:
    """Тесты очистки JSON от markdown форматирования"""

    def test_clean_json_with_markdown_block(self, json_fixer):
        """Тест очистки JSON с markdown блоком"""
        text = '```json\n{"key": "value"}\n```'
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_with_markdown_no_lang(self, json_fixer):
        """Тест очистки JSON с markdown блоком без языка"""
        text = '```\n{"key": "value"}\n```'
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_with_extra_text_before(self, json_fixer):
        """Тест очистки JSON с текстом перед JSON"""
        text = 'Here is the JSON:\n{"key": "value"}'
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_with_extra_text_after(self, json_fixer):
        """Тест очистки JSON с текстом после JSON"""
        text = '{"key": "value"}\nThis is the result'
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_array(self, json_fixer):
        """Тест очистки JSON массива"""
        text = 'Here is the array: [1, 2, 3]'
        result = json_fixer._clean_json_response(text)
        assert result == '[1, 2, 3]'

    def test_clean_json_nested_with_markdown(self, json_fixer):
        """Тест очистки вложенного JSON с markdown"""
        text = '```json\n{"user": {"name": "John", "age": 30}}\n```'
        result = json_fixer._clean_json_response(text)
        assert result == '{"user": {"name": "John", "age": 30}}'

    def test_clean_json_no_cleanup_needed(self, json_fixer):
        """Тест очистки JSON без необходимости очистки"""
        text = '{"key": "value"}'
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_with_whitespace(self, json_fixer):
        """Тест очистки JSON с пробелами"""
        text = '  \n  {"key": "value"}  \n  '
        result = json_fixer._clean_json_response(text)
        assert result == '{"key": "value"}'


class TestJSONFixing:
    """Тесты исправления JSON"""

    @pytest.mark.asyncio
    async def test_fix_already_valid_json(self, json_fixer):
        """Тест исправления уже валидного JSON"""
        valid_json = '{"name": "John", "age": 30}'

        result = await json_fixer.fix_json(valid_json)

        assert result["success"] is True
        assert result["fixed_json"] == valid_json
        assert result["parsed"] == {"name": "John", "age": 30}
        assert result["attempts"] == 0
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_fix_invalid_json_success(self, json_fixer):
        """Тест успешного исправления некорректного JSON"""
        broken_json = '{"name": "John" "age": 30}'
        fixed_json = '{"name": "John", "age": 30}'

        # Мокируем генерацию исправленного JSON
        json_fixer.tokenizer.decode.return_value = fixed_json

        result = await json_fixer.fix_json(broken_json)

        assert result["success"] is True
        assert result["fixed_json"] == fixed_json
        assert result["parsed"] == {"name": "John", "age": 30}
        assert result["attempts"] == 1
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_fix_json_with_schema(self, json_fixer):
        """Тест исправления JSON с валидацией по схеме"""
        broken_json = '{"name": "John", "age": 30'
        fixed_json = '{"name": "John", "age": 30}'
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        }

        json_fixer.tokenizer.decode.return_value = fixed_json

        result = await json_fixer.fix_json(broken_json, schema=schema)

        assert result["success"] is True
        assert result["fixed_json"] == fixed_json
        assert result["parsed"]["name"] == "John"
        assert result["parsed"]["age"] == 30

    @pytest.mark.asyncio
    async def test_fix_json_with_original_prompt(self, json_fixer):
        """Тест исправления JSON с оригинальным промптом"""
        broken_json = '{"result": "test"'
        fixed_json = '{"result": "test"}'
        original_prompt = "Generate a test JSON"

        json_fixer.tokenizer.decode.return_value = fixed_json

        result = await json_fixer.fix_json(
            broken_json,
            original_prompt=original_prompt
        )

        assert result["success"] is True
        assert result["fixed_json"] == fixed_json

    @pytest.mark.asyncio
    async def test_fix_json_multiple_attempts(self, json_fixer):
        """Тест исправления JSON с несколькими попытками"""
        broken_json = '{"name": "John"'

        # Первая попытка - плохой результат, вторая - хороший
        json_fixer.tokenizer.decode.side_effect = [
            '{"name": "John"',  # Все еще невалидный
            '{"name": "John"}',  # Валидный
        ]

        result = await json_fixer.fix_json(broken_json, max_attempts=2)

        assert result["success"] is True
        assert result["attempts"] == 2
        assert result["parsed"]["name"] == "John"

    @pytest.mark.asyncio
    async def test_fix_json_max_attempts_exceeded(self, json_fixer):
        """Тест исправления JSON с превышением попыток"""
        broken_json = '{"name": "John"'

        # Все попытки возвращают невалидный JSON
        json_fixer.tokenizer.decode.return_value = '{"name": "John"'

        result = await json_fixer.fix_json(broken_json, max_attempts=2)

        assert result["success"] is False
        assert result["parsed"] is None
        assert result["attempts"] == 2
        assert "не удалось исправить" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fix_json_with_markdown_response(self, json_fixer):
        """Тест исправления JSON когда модель возвращает markdown"""
        broken_json = '{"name": "John"'

        # Модель возвращает JSON в markdown блоке
        json_fixer.tokenizer.decode.return_value = '```json\n{"name": "John"}\n```'

        result = await json_fixer.fix_json(broken_json)

        assert result["success"] is True
        assert result["fixed_json"] == '{"name": "John"}'
        assert result["parsed"]["name"] == "John"

    @pytest.mark.asyncio
    async def test_fix_json_model_not_loaded(self):
        """Тест исправления JSON когда модель не загружена"""
        fixer = JSONFixerManager()
        fixer.is_loaded = False
        fixer.model = None
        fixer.tokenizer = None

        with patch.object(fixer, 'load_model', new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = GenerationError("Model not loaded")

            with pytest.raises(GenerationError):
                await fixer.fix_json('{"test": "data"}')

    @pytest.mark.asyncio
    async def test_fix_json_disabled_in_settings(self, json_fixer):
        """Тест когда JSON fixing отключен в настройках"""
        broken_json = '{"name": "John"'

        with patch('app.models.json_fixer.settings') as mock_settings:
            mock_settings.enable_json_fixing = False

            result = await json_fixer.fix_json(broken_json)

            assert result["success"] is False
            assert result["error"] == "JSON fixing отключен в настройках"
            assert result["attempts"] == 0

    @pytest.mark.asyncio
    async def test_fix_json_with_exception(self, json_fixer):
        """Тест обработки исключения при исправлении JSON"""
        broken_json = '{"name": "John"'

        # Мокируем исключение при генерации
        json_fixer.tokenizer.decode.side_effect = Exception("Model error")

        result = await json_fixer.fix_json(broken_json, max_attempts=1)

        assert result["success"] is False
        assert result["parsed"] is None
        assert "Model error" in result["error"]


class TestJSONFixingWithTimeout:
    """Тесты исправления JSON с таймаутом"""

    @pytest.mark.asyncio
    async def test_fix_json_with_timeout_success(self, json_fixer):
        """Тест исправления JSON с таймаутом - успех"""
        valid_json = '{"name": "John", "age": 30}'

        result = await json_fixer.fix_json_with_timeout(
            valid_json,
            timeout=5
        )

        assert result["success"] is True
        assert result["fixed_json"] == valid_json

    @pytest.mark.asyncio
    async def test_fix_json_with_timeout_exceeded(self, json_fixer):
        """Тест исправления JSON с превышением таймаута"""
        broken_json = '{"name": "John"'

        # Мокируем медленное исправление
        async def slow_fix(*args, **kwargs):
            await asyncio.sleep(10)
            return {"success": True, "fixed_json": '{"name": "John"}'}

        with patch.object(json_fixer, 'fix_json', side_effect=slow_fix):
            result = await json_fixer.fix_json_with_timeout(
                broken_json,
                timeout=1
            )

            assert result["success"] is False
            assert "таймаут" in result["error"].lower()
            assert result["attempts"] == 0

    @pytest.mark.asyncio
    async def test_fix_json_with_default_timeout(self, json_fixer):
        """Тест исправления JSON с дефолтным таймаутом"""
        valid_json = '{"test": "data"}'

        with patch('app.models.json_fixer.settings') as mock_settings:
            mock_settings.json_fixer_timeout = 30
            mock_settings.enable_json_fixing = True

            result = await json_fixer.fix_json_with_timeout(valid_json)

            assert result["success"] is True


class TestBuildFixPrompt:
    """Тесты построения промпта для исправления"""

    def test_build_fix_prompt_basic(self, json_fixer):
        """Тест построения базового промпта"""
        broken_json = '{"name": "John"'

        prompt = json_fixer._build_fix_prompt(broken_json)

        assert "исправить некорректный json" in prompt.lower()
        assert broken_json in prompt
        assert "валидный json" in prompt.lower()

    def test_build_fix_prompt_with_original_prompt(self, json_fixer):
        """Тест построения промпта с оригинальным промптом"""
        broken_json = '{"name": "John"'
        original_prompt = "Generate user data"

        prompt = json_fixer._build_fix_prompt(
            broken_json,
            original_prompt=original_prompt
        )

        assert original_prompt in prompt
        assert broken_json in prompt

    def test_build_fix_prompt_with_schema(self, json_fixer):
        """Тест построения промпта со схемой"""
        broken_json = '{"name": "John"'
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }

        prompt = json_fixer._build_fix_prompt(
            broken_json,
            schema=schema
        )

        assert "структура" in prompt.lower()
        assert broken_json in prompt
        # Схема должна быть в JSON формате
        assert '"type"' in prompt

    def test_build_fix_prompt_with_all_params(self, json_fixer):
        """Тест построения промпта со всеми параметрами"""
        broken_json = '{"name": "John"'
        original_prompt = "Generate user data"
        schema = {"type": "object"}

        prompt = json_fixer._build_fix_prompt(
            broken_json,
            original_prompt=original_prompt,
            schema=schema
        )

        assert original_prompt in prompt
        assert broken_json in prompt
        assert '"type"' in prompt


class TestStatistics:
    """Тесты статистики JSON Fixer"""

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, json_fixer):
        """Тест получения начальной статистики"""
        stats = json_fixer.get_stats()

        assert "model_name" in stats
        assert "device" in stats
        assert "model_loaded" in stats
        assert "enabled" in stats
        assert "total_requests" in stats
        assert "successful_fixes" in stats
        assert "failed_fixes" in stats
        assert "success_rate_percent" in stats

        assert stats["model_loaded"] is True
        assert stats["model_name"] == "test-model"

    @pytest.mark.asyncio
    async def test_stats_after_successful_fix(self, json_fixer):
        """Тест статистики после успешного исправления"""
        valid_json = '{"name": "John"}'

        initial_stats = json_fixer.get_stats()
        initial_requests = initial_stats["total_requests"]
        initial_successful = initial_stats["successful_fixes"]

        await json_fixer.fix_json(valid_json)

        stats = json_fixer.get_stats()

        assert stats["total_requests"] == initial_requests + 1
        assert stats["successful_fixes"] == initial_successful + 1

    @pytest.mark.asyncio
    async def test_stats_after_failed_fix(self, json_fixer):
        """Тест статистики после неудачного исправления"""
        broken_json = '{"name": "John"'

        # Мокируем неудачное исправление
        json_fixer.tokenizer.decode.return_value = '{"name": "John"'

        initial_stats = json_fixer.get_stats()
        initial_failed = initial_stats["failed_fixes"]

        await json_fixer.fix_json(broken_json, max_attempts=1)

        stats = json_fixer.get_stats()

        assert stats["failed_fixes"] == initial_failed + 1

    @pytest.mark.asyncio
    async def test_success_rate_calculation(self, json_fixer):
        """Тест расчета success rate"""
        # Сбрасываем счетчики
        json_fixer.total_requests = 0
        json_fixer.successful_fixes = 0
        json_fixer.failed_fixes = 0

        # Успешное исправление
        valid_json = '{"name": "John"}'
        await json_fixer.fix_json(valid_json)

        # Неудачное исправление
        broken_json = '{"name": "John"'
        json_fixer.tokenizer.decode.return_value = '{"name": "John"'
        await json_fixer.fix_json(broken_json, max_attempts=1)

        stats = json_fixer.get_stats()

        # 1 успешный из 2 = 50%
        assert stats["success_rate_percent"] == 50.0

    def test_success_rate_zero_requests(self, json_fixer):
        """Тест success rate при отсутствии запросов"""
        json_fixer.total_requests = 0
        json_fixer.successful_fixes = 0
        json_fixer.failed_fixes = 0

        stats = json_fixer.get_stats()

        assert stats["success_rate_percent"] == 0.0


class TestMemoryCheck:
    """Тесты проверки памяти"""

    @pytest.mark.asyncio
    async def test_memory_check_ok(self, json_fixer):
        """Тест проверки памяти - достаточно памяти"""
        with patch('app.models.json_fixer.model_loader') as mock_loader:
            mock_loader.check_available_memory.return_value = (8.0, 50.0)

            # Не должно быть исключения
            json_fixer._check_memory_availability()

    @pytest.mark.asyncio
    async def test_memory_check_exceeded(self, json_fixer):
        """Тест проверки памяти - недостаточно памяти"""
        with patch('app.models.json_fixer.model_loader') as mock_loader:
            mock_loader.check_available_memory.return_value = (0.5, 95.0)

            with pytest.raises(ResourceLimitError):
                json_fixer._check_memory_availability()


class TestConcurrency:
    """Тесты конкурентности"""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_requests(self, json_fixer):
        """Тест что семафор ограничивает конкурентные запросы"""
        valid_json = '{"name": "John"}'

        # Запускаем несколько запросов параллельно
        tasks = [
            json_fixer.fix_json(valid_json)
            for _ in range(3)
        ]

        results = await asyncio.gather(*tasks)

        # Все должны завершиться успешно
        assert all(r["success"] for r in results)

        # В конце не должно быть активных запросов
        assert json_fixer.active_requests == 0

    @pytest.mark.asyncio
    async def test_active_requests_counter(self, json_fixer):
        """Тест счетчика активных запросов"""
        valid_json = '{"name": "John"}'

        # До запроса
        assert json_fixer.active_requests == 0

        # Во время запроса
        task = asyncio.create_task(json_fixer.fix_json(valid_json))
        await asyncio.sleep(0.01)  # Даем задаче начаться

        await task

        # После запроса
        assert json_fixer.active_requests == 0


class TestEdgeCases:
    """Тесты граничных случаев"""

    @pytest.mark.asyncio
    async def test_fix_very_large_json(self, json_fixer):
        """Тест исправления очень большого JSON"""
        large_json = json.dumps({"items": [{"id": i, "name": f"Item {i}"} for i in range(1000)]})

        result = await json_fixer.fix_json(large_json)

        assert result["success"] is True
        assert len(result["parsed"]["items"]) == 1000

    @pytest.mark.asyncio
    async def test_fix_json_with_unicode(self, json_fixer):
        """Тест исправления JSON с Unicode символами"""
        unicode_json = '{"text": "Привет мир", "emoji": "👋"}'

        result = await json_fixer.fix_json(unicode_json)

        assert result["success"] is True
        assert result["parsed"]["text"] == "Привет мир"
        assert result["parsed"]["emoji"] == "👋"

    @pytest.mark.asyncio
    async def test_fix_json_with_special_characters(self, json_fixer):
        """Тест исправления JSON со специальными символами"""
        special_json = '{"text": "Line 1\\nLine 2\\tTabbed"}'

        result = await json_fixer.fix_json(special_json)

        assert result["success"] is True
        assert "Line 1\nLine 2\tTabbed" == result["parsed"]["text"]

    @pytest.mark.asyncio
    async def test_fix_empty_json_object(self, json_fixer):
        """Тест исправления пустого JSON объекта"""
        empty_json = '{}'

        result = await json_fixer.fix_json(empty_json)

        assert result["success"] is True
        assert result["parsed"] == {}

    @pytest.mark.asyncio
    async def test_fix_empty_json_array(self, json_fixer):
        """Тест исправления пустого JSON массива"""
        empty_array = '[]'

        result = await json_fixer.fix_json(empty_array)

        assert result["success"] is True
        assert result["parsed"] == []

    def test_clean_json_no_json_found(self, json_fixer):
        """Тест очистки когда JSON не найден"""
        text = "This is just text without JSON"
        result = json_fixer._clean_json_response(text)
        assert result == text


class TestInitialization:
    """Тесты инициализации"""

    def test_json_fixer_initialization(self):
        """Тест инициализации JSON Fixer Manager"""
        fixer = JSONFixerManager()

        assert fixer.model is None
        assert fixer.tokenizer is None
        assert fixer.is_loaded is False
        assert fixer.active_requests == 0
        assert fixer.total_requests == 0
        assert fixer.successful_fixes == 0
        assert fixer.failed_fixes == 0

    @pytest.mark.asyncio
    async def test_load_model_already_loaded(self, json_fixer):
        """Тест загрузки модели когда она уже загружена"""
        # Модель уже загружена в фикстуре
        assert json_fixer.is_loaded is True

        # Попытка загрузить снова
        await json_fixer.load_model()

        # Должна остаться загруженной
        assert json_fixer.is_loaded is True
