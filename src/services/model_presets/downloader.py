"""Model Downloader - загрузка моделей с HuggingFace Hub.

Single Responsibility: только скачивание файлов с HuggingFace.
Не выполняет проверку совместимости или загрузку пресетов.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.core.model_presets import LocalModelPreset

logger = get_logger()

# Ленивый импорт huggingface_hub чтобы не падать если не установлен
_hf_hub_available: bool | None = None


def _check_hf_hub() -> bool:
    """Проверить доступность huggingface_hub."""
    global _hf_hub_available
    if _hf_hub_available is None:
        try:
            import huggingface_hub  # noqa: F401

            _hf_hub_available = True
        except ImportError:
            _hf_hub_available = False
    return _hf_hub_available


class DownloadResult(BaseModel):
    """Результат загрузки модели."""

    success: bool = Field(
        description="True если загрузка успешна",
    )

    local_path: Path | None = Field(
        default=None,
        description="Путь к скачанному файлу",
    )

    error_message: str | None = Field(
        default=None,
        description="Сообщение об ошибке если загрузка не удалась",
    )

    file_size_mb: float = Field(
        default=0.0,
        description="Размер файла в MB",
    )

    already_exists: bool = Field(
        default=False,
        description="True если файл уже существовал локально",
    )


class ModelDownloader:
    """Загрузчик моделей с HuggingFace Hub.

    Single Responsibility: только скачивание файлов.

    Example:
        >>> downloader = ModelDownloader(Path("models"))
        >>> result = await downloader.download(
        ...     repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
        ...     filename="qwen2.5-7b-instruct-q4_k_m.gguf"
        ... )
        >>> if result.success:
        ...     print(f"Скачано: {result.local_path}")

    """

    def __init__(
        self,
        models_dir: Path,
        hf_token: str | None = None,
    ) -> None:
        """Инициализировать ModelDownloader.

        Args:
            models_dir: Директория для сохранения моделей
            hf_token: HuggingFace токен (для приватных репозиториев)

        """
        self._models_dir = models_dir
        self._hf_token = hf_token

        # Создать директорию если не существует
        self._models_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "ModelDownloader инициализирован",
            models_dir=str(models_dir),
            has_token=hf_token is not None,
        )

    def model_exists(self, filename: str) -> tuple[bool, Path | None]:
        """Проверить наличие модели локально.

        Args:
            filename: Имя файла модели

        Returns:
            (exists, path) - существует ли файл и путь к нему

        """
        path = self._models_dir / filename
        if path.exists() and path.is_file():
            return True, path
        return False, None

    async def check_availability(
        self,
        repo_id: str,
        filename: str,
    ) -> tuple[bool, str | None]:
        """Проверить доступность файла на HuggingFace.

        Args:
            repo_id: ID репозитория (e.g. "Qwen/Qwen2.5-7B-Instruct-GGUF")
            filename: Имя файла в репозитории

        Returns:
            (available, error_message) - доступен ли файл и ошибка если нет

        """
        if not _check_hf_hub():
            return False, "huggingface_hub не установлен. Установите: pip install huggingface-hub"

        try:
            from huggingface_hub import HfApi

            api = HfApi(token=self._hf_token)

            # Запускаем синхронный вызов в executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: api.hf_hub_url(repo_id, filename),
            )
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "Файл недоступен на HuggingFace",
                repo_id=repo_id,
                filename=filename,
                error=error_msg,
            )
            return False, error_msg

    async def download(
        self,
        repo_id: str,
        filename: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> DownloadResult:
        """Скачать модель с HuggingFace Hub.

        Args:
            repo_id: ID репозитория (e.g. "Qwen/Qwen2.5-7B-Instruct-GGUF")
            filename: Имя файла в репозитории
            progress_callback: Callback для отслеживания прогресса (0.0-1.0)

        Returns:
            DownloadResult с результатом загрузки

        """
        if not _check_hf_hub():
            return DownloadResult(
                success=False,
                error_message="huggingface_hub не установлен. Установите: pip install huggingface-hub",
            )

        # Проверить не существует ли уже
        exists, existing_path = self.model_exists(filename)
        if exists and existing_path:
            file_size_mb = existing_path.stat().st_size / (1024**2)
            logger.info(
                "Модель уже существует локально",
                filename=filename,
                path=str(existing_path),
                size_mb=file_size_mb,
            )
            return DownloadResult(
                success=True,
                local_path=existing_path,
                file_size_mb=file_size_mb,
                already_exists=True,
            )

        try:
            from huggingface_hub import hf_hub_download

            logger.info(
                "Начало загрузки модели",
                repo_id=repo_id,
                filename=filename,
            )

            # Запускаем синхронную загрузку в executor
            loop = asyncio.get_event_loop()
            local_path_str = await loop.run_in_executor(
                None,
                lambda: hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=str(self._models_dir),
                    token=self._hf_token,
                    resume_download=True,  # Продолжить если прервано
                ),
            )

            local_path = Path(local_path_str)
            file_size_mb = local_path.stat().st_size / (1024**2)

            logger.info(
                "Модель успешно загружена",
                filename=filename,
                path=str(local_path),
                size_mb=file_size_mb,
            )

            return DownloadResult(
                success=True,
                local_path=local_path,
                file_size_mb=file_size_mb,
            )

        except Exception as e:
            error_msg = str(e)
            logger.exception(
                "Ошибка загрузки модели",
                repo_id=repo_id,
                filename=filename,
                error=error_msg,
            )
            return DownloadResult(
                success=False,
                error_message=error_msg,
            )

    async def download_if_needed(
        self,
        preset: "LocalModelPreset",
        progress_callback: Callable[[float], None] | None = None,
    ) -> DownloadResult:
        """Скачать модель если её нет локально.

        Convenience метод для работы с пресетами.

        Args:
            preset: Пресет локальной модели
            progress_callback: Callback для отслеживания прогресса

        Returns:
            DownloadResult с результатом

        """
        # Сначала проверить локально
        exists, path = self.model_exists(preset.filename)
        if exists and path:
            file_size_mb = path.stat().st_size / (1024**2)
            return DownloadResult(
                success=True,
                local_path=path,
                file_size_mb=file_size_mb,
                already_exists=True,
            )

        # Скачать
        return await self.download(
            repo_id=preset.huggingface_repo,
            filename=preset.filename,
            progress_callback=progress_callback,
        )

    async def get_model_path(self, preset: "LocalModelPreset") -> Path | None:
        """Получить путь к модели (скачать если нужно).

        Args:
            preset: Пресет модели

        Returns:
            Path к файлу модели или None если не удалось

        """
        result = await self.download_if_needed(preset)
        return result.local_path if result.success else None


# === Initialize + Get паттерн ===

_model_downloader: ModelDownloader | None = None


def create_model_downloader(
    models_dir: Path,
    hf_token: str | None = None,
) -> ModelDownloader:
    """Factory: создать ModelDownloader.

    Args:
        models_dir: Директория для моделей
        hf_token: HuggingFace токен

    Returns:
        Инициализированный ModelDownloader

    """
    return ModelDownloader(models_dir, hf_token)


def get_model_downloader() -> ModelDownloader:
    """Получить singleton ModelDownloader.

    Raises:
        RuntimeError: Если downloader не инициализирован

    Returns:
        ModelDownloader instance

    """
    if _model_downloader is None:
        msg = "ModelDownloader не инициализирован. Вызовите set_model_downloader() в lifespan."
        raise RuntimeError(msg)
    return _model_downloader


def set_model_downloader(downloader: ModelDownloader) -> None:
    """Установить singleton ModelDownloader.

    Вызывается в app.py lifespan при старте приложения.

    Args:
        downloader: Инициализированный ModelDownloader

    """
    global _model_downloader
    _model_downloader = downloader
