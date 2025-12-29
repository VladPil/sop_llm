"""SOP LLM - Similarity Endpoints.

Endpoints для вычисления схожести текстов.
"""

from typing import Any, Dict

from fastapi import APIRouter, status
from loguru import logger

from src.api.schemas import SimilarityMethod, SimilarityRequest
from src.core.dependencies import EmbeddingManagerDep, RedisCacheDep

router = APIRouter(prefix="/similarity", tags=["Similarity"])


@router.post(
    "",
    summary="Вычислить сходство",
    description="Вычисляет косинусное сходство между двумя текстами",
    status_code=status.HTTP_200_OK,
)
async def compute_similarity(
    request: SimilarityRequest,
    embedding_manager: EmbeddingManagerDep,
    cache: RedisCacheDep,
) -> Dict[str, Any]:
    """Вычисляет схожесть между двумя текстами используя выбранный метод.

    Args:
        request: Запрос на вычисление схожести.
        embedding_manager: Embedding manager instance.
        cache: Redis cache instance.

    Returns:
        Результат вычисления схожести.

    """
    logger.info(
        "Вычисление схожести",
        method=request.method.value,
        use_cache=request.use_cache,
    )

    # Применяем предобработку текста если нужно
    text1 = request.text1
    text2 = request.text2

    if request.preprocess_text and request.preprocess_text is not False:
        # TODO: Реализовать text_preprocessor
        logger.warning("Text preprocessing не реализован, используем исходные тексты")
        # preset = (
        #     request.preprocess_text
        #     if isinstance(request.preprocess_text, str)
        #     else "standard"
        # )

    # Проверяем кэш если включен
    cached_result = None
    if request.use_cache:
        # Генерируем уникальный ключ для пары текстов и метода (с учётом предобработки)
        cache_text = f"{text1}||{text2}||{request.method}||{request.preprocess_text}"
        cached_result = await cache.get(
            text=cache_text,
            model=request.model or "default",
            task_type="similarity",
        )

    if cached_result:
        logger.info(
            "Кэш найден для вычисления сходства",
            method=request.method.value,
        )
        return cached_result

    # Вычисляем схожесть используя выбранный метод
    similarity_result = await embedding_manager.compute_similarity(
        text1,
        text2,
        method=request.method.value,  # Преобразуем Enum в строку
    )

    # Формируем результат в зависимости от метода
    if request.method == SimilarityMethod.ALL:
        # Если все методы - возвращаем словарь со всеми значениями
        result = {
            "methods": similarity_result,
            "text1_preview": request.text1[:100],
            "text2_preview": request.text2[:100],
            "best_match": {
                "method": max(similarity_result, key=similarity_result.get),
                "score": max(similarity_result.values()),
            },
        }
    else:
        # Если конкретный метод - возвращаем одно значение
        result = {
            "similarity": similarity_result,
            "method": request.method.value,
            "text1_preview": request.text1[:100],
            "text2_preview": request.text2[:100],
        }

    # Сохраняем в кэш если нужно
    if request.use_cache:
        cache_text = f"{request.text1}||{request.text2}||{request.method}"
        await cache.set(
            text=cache_text,
            model=request.model or "default",
            task_type="similarity",
            result=result,
        )

    logger.info(
        "Схожесть вычислена",
        method=request.method.value,
        similarity=(
            result.get("similarity")
            if request.method != SimilarityMethod.ALL
            else result.get("best_match", {}).get("score")
        ),
    )

    return result
