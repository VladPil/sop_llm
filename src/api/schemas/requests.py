"""Request Schemas для SOP LLM Executor API.

Pydantic models для валидации входящих запросов.
"""

from typing import Any

from pydantic import BaseModel, Field

from src.core.constants import (
    DEFAULT_CLEANUP,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_FREQUENCY_PENALTY,
    DEFAULT_PRESENCE_PENALTY,
    DEFAULT_PRIORITY,
    DEFAULT_STREAM,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)
from src.core.enums import ProviderType


class ChatMessageRequest(BaseModel):
    """Сообщение в формате Chat Completions API."""

    role: str = Field(
        description="Роль отправителя: system, user, assistant",
        examples=["user", "assistant", "system"],
    )
    content: str = Field(
        description="Содержание сообщения",
        min_length=1,
    )


class CreateTaskRequest(BaseModel):
    """Запрос на создание задачи генерации текста.

    Создаёт асинхронную задачу для LLM inference. Поддерживает как простые
    текстовые запросы, так и structured output через JSON Schema.

    ## Минимальный запрос
    ```json
    {"model": "gpt-4-turbo", "prompt": "Привет, как дела?"}
    ```

    ## Запрос с контекстом диалога (multi-turn)
    ```json
    {
        "model": "claude-3.5-sonnet",
        "conversation_id": "conv_abc123",
        "prompt": "А что насчёт Python?"
    }
    ```

    ## Запрос с явной историей сообщений
    ```json
    {
        "model": "gpt-4-turbo",
        "messages": [
            {"role": "system", "content": "Ты - помощник программиста"},
            {"role": "user", "content": "Напиши функцию сортировки"},
            {"role": "assistant", "content": "def sort_list(lst): ..."},
            {"role": "user", "content": "Добавь документацию"}
        ]
    }
    ```

    ## Запрос со structured output
    ```json
    {
        "model": "gpt-4-turbo",
        "prompt": "Извлеки данные: Иван, 25 лет, Москва",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "person",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                        "city": {"type": "string"}
                    },
                    "required": ["name", "age", "city"]
                }
            }
        }
    }
    ```
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "gpt-4-turbo",
                    "prompt": "Напиши функцию для сортировки массива на Python",
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                {
                    "model": "claude-3.5-sonnet",
                    "prompt": "Объясни квантовые вычисления простыми словами",
                    "temperature": 0.5,
                    "max_tokens": 2048,
                    "stream": False,
                },
                {
                    "model": "gpt-4-turbo",
                    "prompt": "Извлеки имя, возраст и город из текста: 'Меня зовут Иван, мне 25 лет, живу в Москве'",
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "person_data",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Имя человека"},
                                    "age": {"type": "integer", "description": "Возраст"},
                                    "city": {"type": "string", "description": "Город проживания"},
                                },
                                "required": ["name", "age", "city"],
                            },
                        },
                    },
                    "temperature": 0.0,
                },
            ]
        }
    }

    model: str | None = Field(
        default=None,
        description=(
            "Название модели для генерации. Должна быть зарегистрирована в системе. "
            "Получить список доступных моделей: GET /api/v1/models/"
        ),
        examples=["gpt-4-turbo", "claude-3.5-sonnet", "gemini-pro", "qwen2.5-7b-instruct"],
        json_schema_extra={"x-available-models": "GET /api/v1/models/"},
    )

    prompt: str | None = Field(
        default=None,
        description=(
            "Текст промпта для генерации. Может содержать системные инструкции, "
            "контекст и вопрос пользователя. Поддерживает markdown форматирование.\n\n"
            "**Примечание:** Используйте либо prompt, либо messages, но не оба."
        ),
        min_length=1,
        examples=[
            "Напиши функцию сортировки на Python",
            "Ты — опытный Python разработчик. Напиши unit-тесты для функции calculate_tax()",
            "Переведи на английский: 'Привет, как дела?'",
        ],
    )

    conversation_id: str | None = Field(
        default=None,
        description=(
            "ID существующего диалога для продолжения. При указании conversation_id "
            "система автоматически загрузит историю сообщений и добавит prompt как "
            "новое сообщение пользователя.\n\n"
            "**Создание диалога:** POST /api/v1/conversations/\n"
            "**Получение списка:** GET /api/v1/conversations/"
        ),
        examples=["conv_abc123def456", "conv_xyz789"],
        pattern=r"^conv_[a-f0-9]+$",
    )

    messages: list[ChatMessageRequest] | None = Field(
        default=None,
        description=(
            "Явная история сообщений в формате Chat Completions API. "
            "Используйте для полного контроля над контекстом диалога.\n\n"
            "**Формат сообщения:**\n"
            "• `role`: system | user | assistant\n"
            "• `content`: текст сообщения\n\n"
            "**Примечание:** При указании messages поле prompt игнорируется."
        ),
        examples=[
            [
                {"role": "system", "content": "Ты - полезный ассистент"},
                {"role": "user", "content": "Привет!"},
            ],
            [
                {"role": "user", "content": "Что такое Python?"},
                {"role": "assistant", "content": "Python - это язык программирования..."},
                {"role": "user", "content": "Приведи пример кода"},
            ],
        ],
    )

    save_to_conversation: bool = Field(
        default=True,
        description=(
            "Сохранять ли результат в историю диалога (если указан conversation_id). "
            "При False запрос использует контекст, но не добавляет новые сообщения."
        ),
        examples=[True, False],
    )

    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description=(
            "Температура генерации (0.0-2.0). Контролирует случайность ответа:\n"
            "• 0.0 — детерминированный, точный ответ (для фактов, кода)\n"
            "• 0.3-0.7 — баланс точности и креативности (рекомендуется)\n"
            "• 0.8-1.0 — более креативный ответ (для историй, идей)\n"
            "• >1.0 — очень случайный (обычно не рекомендуется)"
        ),
        examples=[0.0, 0.3, 0.7, 1.0],
    )

    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=128000,
        description=(
            "Максимальное количество токенов в ответе (1-128000). "
            "Примерно: 1 токен ≈ 4 символа английского текста, ≈ 1-2 символа русского. "
            "Рекомендации:\n"
            "• Короткий ответ: 100-500\n"
            "• Средний ответ: 500-2000\n"
            "• Длинный текст: 2000-4000\n"
            "• Код/документация: 4000-8000"
        ),
        examples=[256, 1024, 2048, 4096],
    )

    top_p: float = Field(
        default=DEFAULT_TOP_P,
        ge=0.0,
        le=1.0,
        description=(
            "Nucleus sampling (0.0-1.0). Ограничивает выбор токенов по накопленной вероятности. "
            "Меньшие значения делают ответ более сфокусированным. "
            "Обычно используется ИЛИ temperature, ИЛИ top_p, не оба сразу."
        ),
        examples=[0.9, 0.95, 1.0],
    )

    top_k: int = Field(
        default=DEFAULT_TOP_K,
        ge=0,
        description=(
            "Top-K sampling. Ограничивает выбор K наиболее вероятных токенов. "
            "0 = отключено (по умолчанию). Типичные значения: 10-100."
        ),
        examples=[0, 10, 40, 100],
    )

    frequency_penalty: float = Field(
        default=DEFAULT_FREQUENCY_PENALTY,
        ge=-2.0,
        le=2.0,
        description=(
            "Штраф за частоту токенов (-2.0 до 2.0). "
            "Положительные значения уменьшают повторения слов. "
            "Отрицательные — увеличивают повторения (редко нужно)."
        ),
        examples=[0.0, 0.5, 1.0],
    )

    presence_penalty: float = Field(
        default=DEFAULT_PRESENCE_PENALTY,
        ge=-2.0,
        le=2.0,
        description=(
            "Штраф за присутствие токенов (-2.0 до 2.0). "
            "Положительные значения поощряют новые темы. "
            "Используйте для более разнообразных ответов."
        ),
        examples=[0.0, 0.5, 1.0],
    )

    stop_sequences: list[str] = Field(
        default_factory=list,
        description=(
            "Список стоп-последовательностей. Генерация остановится при встрече "
            "любой из них. Полезно для контроля формата вывода."
        ),
        examples=[
            ["###", "---"],
            ["Human:", "Assistant:"],
            ["</answer>", "\n\n"],
        ],
    )

    seed: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Random seed для воспроизводимости результатов. "
            "При одинаковом seed и параметрах ответ будет идентичным. "
            "Поддерживается не всеми провайдерами."
        ),
        examples=[42, 12345, 0],
    )

    response_format: dict[str, Any] | None = Field(
        default=None,
        description=(
            "JSON Schema для structured output (OpenAI-style). Гарантирует, что ответ "
            "будет валидным JSON по указанной схеме.\n\n"
            "**Формат 1 — простой JSON:**\n"
            '```json\n{"type": "json_object"}\n```\n\n'
            "**Формат 2 — JSON Schema:**\n"
            "```json\n"
            "{\n"
            '  "type": "json_schema",\n'
            '  "json_schema": {\n'
            '    "name": "my_schema",\n'
            '    "schema": {\n'
            '      "type": "object",\n'
            '      "properties": {\n'
            '        "field1": {"type": "string"},\n'
            '        "field2": {"type": "integer"}\n'
            "      },\n"
            '      "required": ["field1"]\n'
            "    }\n"
            "  }\n"
            "}\n"
            "```"
        ),
        examples=[
            {"type": "json_object"},
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                        "required": ["entities"],
                    },
                },
            },
        ],
    )

    grammar: str | None = Field(
        default=None,
        description=(
            "GBNF грамматика для llama.cpp structured output. "
            "Используется только с локальными моделями (provider=local). "
            "Позволяет задать точный формат вывода."
        ),
        examples=[
            'root ::= "yes" | "no"',
            'root ::= "{" ws "\\"answer\\":" ws number ws "}"',
        ],
    )

    stream: bool = Field(
        default=DEFAULT_STREAM,
        description=(
            "Включить streaming генерацию. При stream=true ответ приходит по частям "
            "через SSE (Server-Sent Events). Полезно для real-time отображения."
        ),
        examples=[True, False],
    )

    webhook_url: str | None = Field(
        default=None,
        description=(
            "URL для webhook callback после завершения задачи. "
            "Система отправит POST запрос с результатом на этот URL. "
            "Формат: https://your-server.com/webhook"
        ),
        examples=[
            "https://api.example.com/webhooks/llm-result",
            "https://hooks.slack.com/services/XXX/YYY/ZZZ",
        ],
    )

    idempotency_key: str | None = Field(
        default=None,
        description=(
            "Ключ идемпотентности для дедупликации запросов. "
            "Повторный запрос с тем же ключом вернёт результат предыдущего. "
            "Рекомендуемый формат: {user_id}-{request_id} или UUID."
        ),
        examples=["user-123-request-456", "550e8400-e29b-41d4-a716-446655440000"],
    )

    priority: float = Field(
        default=DEFAULT_PRIORITY,
        ge=0.0,
        le=100.0,
        description=(
            "Приоритет задачи в очереди (0-100). Задачи с большим приоритетом "
            "обрабатываются раньше. По умолчанию: 1.0"
        ),
        examples=[1.0, 5.0, 10.0, 100.0],
    )

    fallback_models: list[str] | None = Field(
        default=None,
        description=(
            "Список резервных моделей для Fallback Strategy. "
            "Если основная модель недоступна или вернула ошибку, "
            "система автоматически попробует следующую модель из списка.\n\n"
            "**Пример использования:**\n"
            "```json\n"
            "{\n"
            '  "model": "gpt-4-turbo",\n'
            '  "fallback_models": ["claude-3.5-sonnet", "gemini-pro"],\n'
            '  "prompt": "..."\n'
            "}\n"
            "```\n\n"
            "**Порядок вызова:**\n"
            "1. gpt-4-turbo (основная)\n"
            "2. claude-3.5-sonnet (первый fallback)\n"
            "3. gemini-pro (второй fallback)\n\n"
            "**Когда срабатывает fallback:**\n"
            "• Модель недоступна (503)\n"
            "• Rate limit (429)\n"
            "• Таймаут\n"
            "• Внутренняя ошибка провайдера (500)"
        ),
        examples=[
            ["claude-3.5-sonnet", "gemini-pro"],
            ["gpt-4o-mini"],
            ["local-qwen-7b", "gpt-4-turbo"],
        ],
    )

    input_text: str | None = Field(
        default=None,
        description=(
            "[Intake-style] Отдельное поле для контекста/текста для анализа. "
            "Используется вместе с prompt для разделения инструкции и данных."
        ),
        examples=["Текст документа для анализа...", "Код для ревью..."],
    )

    output_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "[Intake-style] JSON Schema для structured output. "
            "Альтернатива полю response_format."
        ),
    )

    provider_config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "[Intake-style] Конфигурация провайдера. "
            'Пример: {"model_name": "gpt-4", "temperature": 0.7}'
        ),
    )

    generation_params: dict[str, Any] | None = Field(
        default=None,
        description=(
            "[Intake-style] Параметры генерации. "
            'Пример: {"max_tokens": 1024, "top_p": 0.9}'
        ),
    )

    extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Дополнительные provider-specific параметры. "
            "Передаются напрямую в API провайдера без изменений. "
            'Пример для OpenAI: {"logprobs": true, "top_logprobs": 5}'
        ),
        examples=[
            {"logprobs": True, "top_logprobs": 5},
            {"tools": [{"type": "function", "function": {"name": "get_weather"}}]},
        ],
    )


class RegisterModelRequest(BaseModel):
    """Запрос на регистрацию новой модели в системе.

    Динамически добавляет модель в registry для использования в задачах генерации.

    ## Регистрация OpenAI модели
    ```json
    {
        "name": "my-gpt4",
        "provider": "openai",
        "config": {
            "api_key": "sk-...",
            "model_name": "gpt-4-turbo",
            "base_url": "https://api.openai.com/v1"
        }
    }
    ```

    ## Регистрация Anthropic модели
    ```json
    {
        "name": "my-claude",
        "provider": "anthropic",
        "config": {
            "api_key": "sk-ant-...",
            "model_name": "claude-3-5-sonnet-20241022"
        }
    }
    ```

    ## Регистрация локальной GGUF модели
    ```json
    {
        "name": "local-qwen",
        "provider": "local",
        "config": {
            "model_path": "/models/qwen2.5-7b-instruct.gguf",
            "context_window": 8192,
            "gpu_layers": -1
        }
    }
    ```

    ## Регистрация OpenAI-совместимого API
    ```json
    {
        "name": "local-ollama",
        "provider": "openai_compatible",
        "config": {
            "model_name": "llama3.1",
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama"
        }
    }
    ```
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "my-gpt4",
                    "provider": "openai",
                    "config": {
                        "api_key": "sk-proj-...",
                        "model_name": "gpt-4-turbo",
                        "base_url": "https://api.openai.com/v1",
                        "timeout": 120,
                        "max_retries": 3,
                    },
                },
                {
                    "name": "my-claude",
                    "provider": "anthropic",
                    "config": {
                        "api_key": "sk-ant-...",
                        "model_name": "claude-3-5-sonnet-20241022",
                    },
                },
                {
                    "name": "local-qwen",
                    "provider": "local",
                    "config": {
                        "model_path": "/models/qwen2.5-7b-instruct-q4_k_m.gguf",
                        "context_window": 8192,
                        "gpu_layers": -1,
                    },
                },
            ]
        }
    }

    name: str = Field(
        description=(
            "Уникальное название модели в системе. Это имя используется в поле 'model' "
            "при создании задач. Рекомендуется использовать понятные имена без пробелов."
        ),
        examples=["gpt-4-turbo", "claude-3.5-sonnet", "local-qwen-7b", "my-custom-model"],
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )

    provider: ProviderType = Field(
        description=(
            "Тип провайдера для модели:\n"
            "• **openai** — OpenAI API (GPT-4, GPT-3.5)\n"
            "• **anthropic** — Anthropic API (Claude)\n"
            "• **openai_compatible** — любой OpenAI-совместимый API (Ollama, vLLM, LM Studio)\n"
            "• **local** — локальная GGUF модель через llama.cpp"
        ),
        examples=["openai", "anthropic", "openai_compatible", "local"],
    )

    config: dict[str, Any] = Field(
        description=(
            "Конфигурация провайдера. Набор полей зависит от типа провайдера:\n\n"
            "**Для openai/anthropic:**\n"
            "• `api_key` (str, required) — API ключ провайдера\n"
            "• `model_name` (str, required) — название модели в API провайдера\n"
            "• `base_url` (str, optional) — базовый URL API\n"
            "• `timeout` (int, optional) — таймаут запроса в секундах (default: 120)\n"
            "• `max_retries` (int, optional) — количество повторов (default: 3)\n\n"
            "**Для openai_compatible:**\n"
            "• `model_name` (str, required) — название модели\n"
            "• `base_url` (str, required) — URL OpenAI-совместимого API\n"
            "• `api_key` (str, optional) — API ключ (если требуется)\n\n"
            "**Для local:**\n"
            "• `model_path` (str, required) — путь к GGUF файлу модели\n"
            "• `context_window` (int, optional) — размер контекста (default: 4096)\n"
            "• `gpu_layers` (int, optional) — слоёв на GPU (-1 = все, 0 = CPU only)"
        ),
        examples=[
            {
                "api_key": "sk-proj-xxxx",
                "model_name": "gpt-4-turbo",
                "base_url": "https://api.openai.com/v1",
                "timeout": 120,
                "max_retries": 3,
            },
            {
                "api_key": "sk-ant-xxxx",
                "model_name": "claude-3-5-sonnet-20241022",
            },
            {
                "model_name": "llama3.1",
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
            },
            {
                "model_path": "/models/qwen2.5-7b-instruct-q4_k_m.gguf",
                "context_window": 8192,
                "gpu_layers": -1,
            },
        ],
    )


class UnregisterModelRequest(BaseModel):
    """Запрос на удаление модели из registry.

    Удаляет зарегистрированную модель и опционально освобождает ресурсы.

    **Примечание:** Нельзя удалить модель, которая сейчас обрабатывает задачу.
    """

    cleanup: bool = Field(
        default=DEFAULT_CLEANUP,
        description=(
            "Очистить ресурсы модели при удалении:\n"
            "• **true** — выгрузить модель из памяти/VRAM, закрыть соединения\n"
            "• **false** — только удалить из registry (ресурсы останутся в памяти)"
        ),
        examples=[True, False],
    )


class EmbeddingRequest(BaseModel):
    """Запрос на генерацию векторных представлений (embeddings).

    Генерирует числовые векторы для текстов, которые можно использовать
    для семантического поиска, кластеризации и сравнения текстов.

    ## Простой запрос
    ```json
    {
        "texts": ["Первый текст", "Второй текст"],
        "model_name": "intfloat/multilingual-e5-large"
    }
    ```

    ## Для семантического поиска
    ```json
    {
        "texts": [
            "query: Как приготовить борщ?",
            "passage: Рецепт классического борща с мясом",
            "passage: Инструкция по установке Windows"
        ],
        "model_name": "intfloat/multilingual-e5-large"
    }
    ```

    **Совет:** Для E5 моделей добавляйте префиксы `query:` и `passage:`
    для лучшего качества семантического поиска.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "texts": [
                        "Машинное обучение — это раздел искусственного интеллекта",
                        "Глубокое обучение использует многослойные нейронные сети",
                    ],
                    "model_name": "intfloat/multilingual-e5-large",
                },
                {
                    "texts": [
                        "query: Что такое квантовые вычисления?",
                        "passage: Квантовые компьютеры используют кубиты вместо битов",
                        "passage: Рецепт приготовления пиццы",
                    ],
                    "model_name": "intfloat/multilingual-e5-large",
                },
            ]
        }
    }

    texts: list[str] = Field(
        description=(
            "Список текстов для генерации embeddings. Каждый текст будет преобразован "
            "в числовой вектор фиксированной размерности.\n\n"
            "**Рекомендации:**\n"
            "• Максимальная длина текста зависит от модели (обычно 512 токенов)\n"
            "• Для E5 моделей используйте префиксы `query:` и `passage:`\n"
            "• Батч до 32 текстов обрабатывается эффективнее"
        ),
        min_length=1,
        max_length=100,
        examples=[
            ["Текст для анализа"],
            ["Первый документ", "Второй документ", "Третий документ"],
            ["query: поисковый запрос", "passage: текст документа"],
        ],
    )

    model_name: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description=(
            "Название embedding модели. Модель должна быть зарегистрирована в системе.\n\n"
            "**Популярные модели:**\n"
            "• `intfloat/multilingual-e5-large` — мультиязычная, 1024 dims (рекомендуется)\n"
            "• `intfloat/multilingual-e5-base` — мультиязычная, 768 dims, быстрее\n"
            "• `sentence-transformers/all-MiniLM-L6-v2` — английская, 384 dims, очень быстрая"
        ),
        examples=[
            "intfloat/multilingual-e5-large",
            "intfloat/multilingual-e5-base",
            "sentence-transformers/all-MiniLM-L6-v2",
        ],
    )


class RegisterFromPresetRequest(BaseModel):
    """Запрос на регистрацию модели из YAML пресета.

    Регистрирует модель используя предопределённую конфигурацию из YAML файлов.
    Автоматически скачивает локальные модели с HuggingFace Hub если нужно.

    ## Регистрация локальной модели (автозагрузка)
    ```json
    {
        "preset_name": "qwen2.5-7b-instruct",
        "auto_download": true
    }
    ```

    ## Регистрация облачной модели
    ```json
    {
        "preset_name": "claude-3.5-sonnet"
    }
    ```

    ## Регистрация с переопределением квантизации
    ```json
    {
        "preset_name": "qwen2.5-14b-instruct",
        "quantization": "q4_k_m"
    }
    ```
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "preset_name": "qwen2.5-7b-instruct",
                    "auto_download": True,
                },
                {
                    "preset_name": "claude-3.5-sonnet",
                },
                {
                    "preset_name": "qwen2.5-14b-instruct",
                    "quantization": "q4_k_m",
                    "auto_download": True,
                },
            ]
        }
    }

    preset_name: str = Field(
        description=(
            "Имя пресета из YAML конфигурации. Получить список доступных пресетов: "
            "GET /api/v1/models/presets"
        ),
        examples=[
            "qwen2.5-7b-instruct",
            "claude-3.5-sonnet",
            "gpt-4o",
            "llama-3.2-8b-instruct",
        ],
        min_length=1,
        max_length=100,
    )

    auto_download: bool = Field(
        default=True,
        description=(
            "Автоматически скачать модель с HuggingFace Hub если она отсутствует локально. "
            "Применяется только для локальных моделей (GGUF)."
        ),
    )

    quantization: str | None = Field(
        default=None,
        description=(
            "Переопределить квантизацию модели. Используется для выбора версии "
            "модели с другим уровнем квантизации.\n\n"
            "**Доступные варианты:**\n"
            "• `q4_k_m` — минимальный размер, хорошее качество\n"
            "• `q5_k_m` — баланс размера и качества\n"
            "• `q8_0` — высокое качество, больший размер\n"
            "• `fp16` — полная точность, максимальный размер"
        ),
        examples=["q4_k_m", "q5_k_m", "q8_0", "fp16"],
    )


class CreateConversationRequest(BaseModel):
    """Запрос на создание нового диалога.

    Создаёт диалог для хранения истории сообщений (multi-turn conversations).

    ## Минимальный запрос
    ```json
    {}
    ```

    ## Запрос с системным промптом
    ```json
    {
        "system_prompt": "Ты - опытный Python разработчик",
        "model": "claude-3.5-sonnet"
    }
    ```

    ## Запрос с метаданными
    ```json
    {
        "system_prompt": "Ты - ассистент по продажам",
        "model": "gpt-4-turbo",
        "metadata": {
            "user_id": "user_123",
            "session_type": "support"
        }
    }
    ```
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {},
                {
                    "system_prompt": "Ты - опытный Python разработчик",
                    "model": "claude-3.5-sonnet",
                },
                {
                    "system_prompt": "Ты - ассистент по продажам",
                    "model": "gpt-4-turbo",
                    "metadata": {"user_id": "user_123"},
                },
            ]
        }
    }

    model: str | None = Field(
        default=None,
        description=(
            "Модель по умолчанию для диалога. Если указана, будет использоваться "
            "для всех запросов в диалоге, если не переопределена в CreateTaskRequest."
        ),
        examples=["gpt-4-turbo", "claude-3.5-sonnet"],
    )

    system_prompt: str | None = Field(
        default=None,
        description=(
            "Системный промпт для диалога. Добавляется как первое сообщение "
            "и отправляется с каждым запросом в контексте."
        ),
        examples=[
            "Ты - полезный ассистент",
            "Ты - опытный Python разработчик. Пиши чистый, документированный код.",
        ],
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Дополнительные метаданные для диалога. Можно использовать для "
            "хранения user_id, session_type, tags и других custom полей."
        ),
        examples=[
            {"user_id": "user_123"},
            {"session_type": "support", "priority": "high"},
        ],
    )


class UpdateConversationRequest(BaseModel):
    """Запрос на обновление диалога.

    PATCH /api/v1/conversations/{conversation_id}
    """

    model: str | None = Field(
        default=None,
        description="Новая модель по умолчанию",
    )

    system_prompt: str | None = Field(
        default=None,
        description="Новый системный промпт",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Новые метаданные (полностью заменяют старые)",
    )


class AddMessageRequest(BaseModel):
    """Запрос на добавление сообщения в диалог.

    POST /api/v1/conversations/{conversation_id}/messages
    """

    role: str = Field(
        description="Роль: system, user, assistant",
        examples=["user", "assistant", "system"],
    )

    content: str = Field(
        description="Текст сообщения",
        min_length=1,
    )


class CheckCompatibilityRequest(BaseModel):
    """Запрос на проверку совместимости модели с GPU.

    Проверяет, поместится ли модель в доступную VRAM, и рекомендует
    оптимальную квантизацию если модель слишком большая.

    ## Проверка совместимости
    ```json
    {
        "preset_name": "qwen2.5-14b-instruct"
    }
    ```

    ## Проверка конкретной квантизации
    ```json
    {
        "preset_name": "qwen2.5-14b-instruct",
        "quantization": "fp16"
    }
    ```
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "preset_name": "qwen2.5-7b-instruct",
                },
                {
                    "preset_name": "qwen2.5-14b-instruct",
                    "quantization": "fp16",
                },
            ]
        }
    }

    preset_name: str = Field(
        description=(
            "Имя локального пресета для проверки совместимости. "
            "Должен быть локальной моделью (GGUF)."
        ),
        examples=["qwen2.5-7b-instruct", "llama-3.2-8b-instruct", "qwen2.5-14b-instruct"],
        min_length=1,
        max_length=100,
    )

    quantization: str | None = Field(
        default=None,
        description=(
            "Квантизация для проверки. Если не указана, определяется автоматически "
            "из имени файла пресета."
        ),
        examples=["q4_k_m", "q5_k_m", "q8_0", "fp16"],
    )
