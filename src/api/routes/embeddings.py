"""Embeddings API Routes для SOP LLM Executor.

Endpoints для генерации векторных представлений текстов.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import EmbeddingRequest
from src.api.schemas.responses import EmbeddingResponse, ErrorResponse
from src.providers.registry import get_provider_registry
from src.utils.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Генерация embeddings",
    description="Генерирует векторные представления для списка текстов",
    responses={
        200: {"description": "Embeddings сгенерированы успешно"},
        400: {"model": ErrorResponse, "description": "Невалидный запрос"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
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
