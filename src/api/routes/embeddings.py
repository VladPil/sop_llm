"""Embeddings API Routes для SOP LLM Executor.

Endpoints для генерации векторных представлений текстов.
"""

import math

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.docs import embeddings as docs
from src.api.schemas.requests import EmbeddingRequest
from src.api.schemas.responses import EmbeddingResponse, ErrorResponse


class SimilarityRequest(BaseModel):
    """Запрос на вычисление сходства текстов."""

    text1: str = Field(description="Первый текст для сравнения")
    text2: str = Field(description="Второй текст для сравнения")
    model_name: str = Field(description="Имя embedding модели")


class SimilarityResponse(BaseModel):
    """Ответ с результатом вычисления сходства."""

    similarity: float = Field(description="Косинусное сходство (0.0 - 1.0)")
    model: str = Field(description="Использованная модель")
    text1_preview: str = Field(description="Превью первого текста (первые 100 символов)")
    text2_preview: str = Field(description="Превью второго текста (первые 100 символов)")


from src.providers.registry import get_provider_registry
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/",
    response_model=EmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Генерация векторных представлений (embeddings)",
    description=docs.GENERATE_EMBEDDINGS,
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


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Вычислить косинусное сходство двух векторов.

    Args:
        vec1: Первый вектор
        vec2: Второй вектор

    Returns:
        Косинусное сходство (0.0 - 1.0)
    """
    if len(vec1) != len(vec2):
        raise ValueError("Векторы должны иметь одинаковую размерность")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    similarity = dot_product / (magnitude1 * magnitude2)
    # Нормализовать в диапазон [0, 1]
    return (similarity + 1) / 2


@router.post(
    "/similarity",
    response_model=SimilarityResponse,
    status_code=status.HTTP_200_OK,
    summary="Вычислить сходство двух текстов",
    description=docs.CALCULATE_SIMILARITY,
    responses={
        200: {
            "description": "Сходство успешно вычислено",
            "content": {
                "application/json": {
                    "example": {
                        "similarity": 0.85,
                        "model": "multilingual-e5-large",
                        "text1_preview": "Машинное обучение - это область...",
                        "text2_preview": "ML является частью AI",
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Невалидный запрос"},
        404: {"model": ErrorResponse, "description": "Embedding модель не зарегистрирована"},
        500: {"model": ErrorResponse, "description": "Ошибка вычисления сходства"},
    },
)
async def calculate_similarity(request: SimilarityRequest) -> SimilarityResponse:
    """Вычислить сходство между двумя текстами.

    Args:
        request: Параметры запроса (text1, text2, model_name)

    Returns:
        SimilarityResponse с результатом сходства

    Raises:
        HTTPException: 404 если модель не найдена
    """
    registry = get_provider_registry()

    # Проверить наличие модели
    if request.model_name not in registry.list_providers():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding модель '{request.model_name}' не зарегистрирована",
        )

    try:
        provider = registry.get(request.model_name)

        # Проверить что provider поддерживает embeddings
        if not hasattr(provider, "generate_embeddings"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Модель '{request.model_name}' не поддерживает генерацию embeddings",
            )

        logger.info(
            "Вычисление сходства",
            model=request.model_name,
            text1_len=len(request.text1),
            text2_len=len(request.text2),
        )

        # Генерация embeddings для обоих текстов
        embeddings = await provider.generate_embeddings([request.text1, request.text2])

        # Вычисление косинусного сходства
        similarity = _cosine_similarity(embeddings[0], embeddings[1])

        logger.info(
            "Сходство вычислено",
            model=request.model_name,
            similarity=similarity,
        )

        return SimilarityResponse(
            similarity=round(similarity, 4),
            model=request.model_name,
            text1_preview=request.text1[:100] + "..." if len(request.text1) > 100 else request.text1,
            text2_preview=request.text2[:100] + "..." if len(request.text2) > 100 else request.text2,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Ошибка вычисления сходства", error=str(e), model=request.model_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вычисления сходства: {e}",
        ) from e
