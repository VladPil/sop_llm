"""SOP LLM - Model Endpoints.

Endpoints для получения информации о моделях и провайдерах.
"""

from fastapi import APIRouter, status
from loguru import logger

from src.api.schemas import (
    ModelInfo,
    ModelsListResponse,
    ProviderInfo,
    ProvidersListResponse,
)
from src.core.dependencies import (
    EmbeddingManagerDep,
    JSONFixerDep,
    LLMManagerDep,
    ProviderManagerDep,
    SettingsDep,
)

router = APIRouter(prefix="/models", tags=["Models"])


@router.get(
    "",
    summary="Список моделей",
    description="Возвращает информацию о загруженных моделях",
    status_code=status.HTTP_200_OK,
)
async def list_models(
    llm_manager: LLMManagerDep,
    embedding_manager: EmbeddingManagerDep,
    json_fixer: JSONFixerDep,
    settings: SettingsDep,
) -> ModelsListResponse:
    """Возвращает список загруженных моделей и их статус.

    Args:
        llm_manager: LLM manager instance.
        embedding_manager: Embedding manager instance.
        json_fixer: JSON fixer instance.
        settings: Settings instance.

    Returns:
        Список моделей.

    """
    logger.debug("Получение списка моделей")
    models = []

    # LLM модель
    llm_stats = llm_manager.get_stats()
    models.append(
        ModelInfo(
            name=llm_stats.get("model_name") or settings.default_llm_model,
            type="llm",
            loaded=llm_stats.get("model_loaded", False),
            device=llm_stats.get("device", "unknown"),
            stats=llm_stats,
        )
    )

    # Embedding модель
    emb_stats = embedding_manager.get_stats()
    models.append(
        ModelInfo(
            name=emb_stats.get("model_name") or settings.default_embedding_model,
            type="embedding",
            loaded=emb_stats.get("model_loaded", False),
            device=emb_stats.get("device", "unknown"),
            stats=emb_stats,
        )
    )

    # JSON Fixer модель
    json_fixer_stats = json_fixer.get_stats()
    models.append(
        ModelInfo(
            name=json_fixer_stats.get("model_name") or settings.json_fixer_model,
            type="json_fixer",
            loaded=json_fixer_stats.get("model_loaded", False),
            device=json_fixer_stats.get("device", "unknown"),
            stats=json_fixer_stats,
        )
    )

    return ModelsListResponse(models=models)


@router.get(
    "/providers",
    summary="Список доступных провайдеров",
    description="Возвращает список всех LLM провайдеров (local, claude, lm_studio)",
    status_code=status.HTTP_200_OK,
)
async def list_providers(
    provider_manager: ProviderManagerDep,
) -> ProvidersListResponse:
    """Возвращает список всех доступных провайдеров с их возможностями.

    Новая архитектура с ProviderManager:
    - local: Локальные модели через HuggingFace (Qwen)
    - claude: Anthropic Claude API
    - lm_studio: LM Studio (OpenAI-compatible API)

    Каждый провайдер имеет:
    - name: Имя провайдера
    - is_available: Доступность (инициализирован и готов)
    - capabilities: Список возможностей
    - is_default: Является ли default провайдером

    Args:
        provider_manager: Provider manager instance.

    Returns:
        Список провайдеров.

    """
    logger.debug("Получение списка провайдеров")

    # Получаем список провайдеров от ProviderManager
    providers_list = provider_manager.list_providers()

    # Преобразуем в Pydantic модели
    providers_info = [ProviderInfo(**p) for p in providers_list]

    return ProvidersListResponse(
        providers=providers_info,
        total=len(providers_info),
    )
