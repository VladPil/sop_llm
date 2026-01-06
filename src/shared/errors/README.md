# Errors Module

Модуль обработки исключений для sop_llm проекта, реализованный по стандарту wiki-engine.

## Структура

```
src/shared/errors/
├── __init__.py              # Публичный API
├── base.py                  # AppException с авто-генерацией кодов
├── domain_errors.py         # Стандартные доменные ошибки
├── llm_errors.py            # LLM-specific ошибки
└── mapping.py               # Маппинг инфраструктурных ошибок
```

## Возможности

### 1. Автоматическая генерация error_code

Каждое исключение автоматически генерирует `error_code` из имени класса:

```python
class ValidationError(AppException):
    """Ошибка валидации входных данных."""
    status_code = 422

error = ValidationError(message="Некорректный email")
# error.code = "validation_error" (автоматически)
```

### 2. Default message из docstring

Если не указано сообщение, оно извлекается из первой строки docstring:

```python
class NotFoundError(AppException):
    """Запрашиваемый ресурс не найден."""
    status_code = 404

error = NotFoundError()
# error.message = "Запрашиваемый ресурс не найден."
```

### 3. Pydantic схема для HTTP ответов

```python
error = ValidationError(
    message="Неверный формат данных",
    details={"field": "email", "value": "invalid"}
)

response = error.to_response()
# ErrorResponse(
#     error_code="validation_error",
#     message="Неверный формат данных",
#     details={"field": "email", "value": "invalid"}
# )
```

## Использование

### Базовые доменные ошибки

```python
from src.shared.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ServiceUnavailableError,
    RateLimitError,
)

# Простое использование
raise NotFoundError(message="Пользователь не найден")

# С деталями
raise ValidationError(
    message="Неверный формат email",
    details={"field": "email", "value": "test"}
)
```

### LLM-специфичные ошибки

```python
from src.shared.errors import (
    ModelNotFoundError,
    ProviderUnavailableError,
    TokenLimitExceededError,
    GenerationFailedError,
)

# Модель не найдена
raise ModelNotFoundError(model_name="gpt-4")
# message: "Модель 'gpt-4' не найдена в реестре"
# details: {"model_name": "gpt-4"}

# Превышен лимит токенов
raise TokenLimitExceededError(tokens_used=5000, tokens_limit=4096)
# message: "Превышен лимит токенов: 5000/4096"
# details: {"tokens_used": 5000, "tokens_limit": 4096}

# Провайдер недоступен
raise ProviderUnavailableError(provider_name="anthropic")
# message: "Провайдер 'anthropic' недоступен"
# details: {"provider": "anthropic"}

# Ошибка генерации
raise GenerationFailedError(
    model_name="gpt-3.5-turbo",
    reason="Connection timeout"
)
```

### Маппинг инфраструктурных ошибок

```python
from src.shared.errors import map_exception
import asyncpg
import redis.exceptions
import litellm.exceptions

# PostgreSQL
try:
    # Операция с БД
    pass
except asyncpg.UniqueViolationError as e:
    raise map_exception(e)  # Преобразуется в ConflictError

# Redis
try:
    # Операция с кэшем
    pass
except redis.exceptions.ConnectionError as e:
    raise map_exception(e)  # Преобразуется в ServiceUnavailableError

# LiteLLM
try:
    # Запрос к LLM
    pass
except litellm.exceptions.RateLimitError as e:
    raise map_exception(e)  # Преобразуется в RateLimitError
```

### Интеграция с FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.shared.errors import AppException

app = FastAPI()

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Обработчик доменных исключений."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response().model_dump(),
    )

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = await get_user_from_db(user_id)
    if not user:
        raise NotFoundError(
            message=f"Пользователь {user_id} не найден",
            details={"user_id": user_id}
        )
    return user
```

### Расширение ExceptionMapper

```python
from src.shared.errors import exception_mapper, AppException

# Регистрация кастомного маппинга
class CustomInfraError(Exception):
    pass

class CustomDomainError(AppException):
    status_code = 503

exception_mapper.register(CustomInfraError, CustomDomainError)

# Теперь CustomInfraError будет автоматически маппиться
try:
    raise CustomInfraError("Something went wrong")
except Exception as e:
    raise map_exception(e)  # Преобразуется в CustomDomainError
```

## Доступные ошибки

### Доменные ошибки (domain_errors.py)

| Класс | HTTP Код | Описание |
|-------|----------|----------|
| `ValidationError` | 422 | Ошибка валидации входных данных |
| `NotFoundError` | 404 | Запрашиваемый ресурс не найден |
| `ConflictError` | 409 | Конфликт с текущим состоянием ресурса |
| `ServiceUnavailableError` | 503 | Сервис временно недоступен |
| `RateLimitError` | 429 | Превышен лимит запросов |
| `UnauthorizedError` | 401 | Требуется аутентификация |
| `ForbiddenError` | 403 | Доступ запрещен |
| `BadRequestError` | 400 | Некорректный запрос |
| `InternalServerError` | 500 | Внутренняя ошибка сервера |
| `TimeoutError` | 504 | Превышено время ожидания операции |

### LLM-ошибки (llm_errors.py)

| Класс | HTTP Код | Описание |
|-------|----------|----------|
| `ModelNotFoundError` | 404 | Модель не найдена в реестре |
| `ProviderUnavailableError` | 503 | Провайдер LLM недоступен |
| `TokenLimitExceededError` | 422 | Превышен лимит токенов |
| `GenerationFailedError` | 500 | Ошибка при генерации ответа |
| `InvalidModelConfigError` | 422 | Некорректная конфигурация модели |
| `ProviderAuthenticationError` | 401 | Ошибка аутентификации с провайдером |
| `ContextLengthExceededError` | 422 | Превышена максимальная длина контекста |

## Маппинг инфраструктурных ошибок

### PostgreSQL (asyncpg)

- `UniqueViolationError` → `ConflictError`
- `ForeignKeyViolationError` → `ConflictError`
- `IntegrityConstraintViolationError` → `ConflictError`
- `PostgresConnectionError` → `ServiceUnavailableError`
- `TooManyConnectionsError` → `ServiceUnavailableError`
- `InvalidSQLStatementNameError` → `BadRequestError`
- `UndefinedTableError` → `BadRequestError`
- `PostgresError` → `ServiceUnavailableError`

### Redis

- `ConnectionError` → `ServiceUnavailableError`
- `TimeoutError` → `TimeoutError`
- `RedisError` → `ServiceUnavailableError`

### LiteLLM

- `NotFoundError` → `ModelNotFoundError`
- `AuthenticationError` → `ProviderAuthenticationError`
- `RateLimitError` → `RateLimitError`
- `ServiceUnavailableError` → `ProviderUnavailableError`
- `Timeout` → `TimeoutError`
- `ContextWindowExceededError` → `ContextLengthExceededError`
- `BadRequestError` → `BadRequestError`
- `APIError` → `GenerationFailedError`

## Особенности реализации

1. **Auto-generation error_code**: Преобразование `CamelCase` → `snake_case`
2. **Default message из docstring**: Первая строка docstring используется как сообщение по умолчанию
3. **Type hints везде**: Полная типизация для поддержки mypy
4. **Pydantic ErrorResponse**: Готовая схема для JSON сериализации
5. **Документация на русском**: Google Style docstrings
6. **Паттерны из wiki-engine**: Следование архитектуре референсного проекта
