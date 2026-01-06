"""Embeddings API Routes для SOP LLM Executor.

Endpoints для генерации векторных представлений текстов.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import EmbeddingRequest
from src.api.schemas.responses import EmbeddingResponse, ErrorResponse
from src.providers.registry import get_provider_registry
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/",
    response_model=EmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Генерация векторных представлений (embeddings)",
    description="""
Генерирует векторные представления (embeddings) для списка текстов.

## Что такое embeddings

Embeddings — это числовые векторы, представляющие семантическое значение текста.
Тексты с похожим смыслом имеют близкие векторы в многомерном пространстве.

## Применение

- **Семантический поиск** — поиск документов по смыслу, а не по ключевым словам
- **RAG** — Retrieval-Augmented Generation для LLM
- **Кластеризация** — группировка похожих текстов
- **Дедупликация** — обнаружение дубликатов контента
- **Рекомендации** — поиск похожих товаров/статей

## Доступные модели

| Модель | Dimensions | Языки | Описание |
|--------|------------|-------|----------|
| `multilingual-e5-large` | 1024 | 100+ | Лучшее качество, мультиязычная |
| `all-MiniLM-L6-v2` | 384 | EN | Быстрая, компактная |

## Параметры запроса

| Параметр | Тип | Описание |
|----------|-----|----------|
| `texts` | list[str] | Список текстов для векторизации (макс. 100) |
| `model_name` | string | Имя зарегистрированной embedding модели |

## Формат ответа

| Поле | Описание |
|------|----------|
| `embeddings` | Список векторов (по одному на текст) |
| `model` | Использованная модель |
| `dimensions` | Размерность вектора |

## Рекомендации

- **Нормализация** — удаляйте лишние пробелы и переносы строк
- **Батчинг** — отправляйте тексты группами по 32-64 штуки
- **Кэширование** — сохраняйте embeddings в БД, не генерируйте повторно
- **E5 модели** — добавляйте префикс "query: " или "passage: "

## Ошибки

| Код | Описание |
|-----|----------|
| 400 | Невалидный запрос (пустой список, слишком много текстов) |
| 404 | Embedding модель не зарегистрирована |
| 500 | Ошибка генерации (проблемы с моделью или GPU) |

## Регистрация embedding модели

Перед использованием модель должна быть зарегистрирована через:
- `/models/register-from-preset` — из готового пресета
- `/models/register` — вручную с указанием конфигурации
""",
    responses={
        200: {
            "description": "Embeddings успешно сгенерированы",
            "content": {
                "application/json": {
                    "example": {
                        "embeddings": [
                            [0.0123, -0.0456, 0.0789, 0.0111, -0.0222],
                            [0.0321, -0.0654, 0.0987, 0.0333, -0.0444],
                        ],
                        "model": "multilingual-e5-large",
                        "dimensions": 1024,
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Невалидный запрос (пустой список текстов, превышен лимит)"},
        404: {"model": ErrorResponse, "description": "Embedding модель не зарегистрирована в системе"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка при генерации embeddings"},
    },
)
async def generate_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """Сгенерировать embeddings для текстов.

    Args:
        request: Параметры запроса (texts, model_name)

    Returns:
        EmbeddingResponse с векторными представлениями

    Raises:
        HTTPException: 404 если модель не найдена

    """
    registry = get_provider_registry()

    # Проверить наличие модели в registry
    if request.model_name not in registry.list_providers():
        logger.warning(
            "Embedding модель не найдена",
            model=request.model_name,
            available_models=registry.list_providers(),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding модель '{request.model_name}' не зарегистрирована. "
            f"Зарегистрируйте модель через POST /api/v1/models/register",
        )

    try:
        provider = registry.get(request.model_name)

        # Проверить что provider поддерживает embeddings
        if not hasattr(provider, "generate_embeddings"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Модель '{request.model_name}' не поддерживает генерацию embeddings",
            )

        # Генерация embeddings
        logger.info(
            "Генерация embeddings",
            model=request.model_name,
            texts_count=len(request.texts),
        )

        embeddings = await provider.generate_embeddings(request.texts)

        # Определить dimensions
        dimensions = len(embeddings[0]) if embeddings else 0

        logger.info(
            "Embeddings сгенерированы",
            model=request.model_name,
            count=len(embeddings),
            dimensions=dimensions,
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=request.model_name,
            dimensions=dimensions,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Ошибка генерации embeddings", error=str(e), model=request.model_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации embeddings: {e}",
        ) from e
