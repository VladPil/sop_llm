"""Embedding Provider для sentence-transformers моделей.

Поддерживает генерацию векторных представлений текстов.
"""

from typing import Any

from src.utils.logging import get_logger

logger = get_logger()


class SentenceTransformerProvider:
    """Provider для sentence-transformers embedding моделей.

    Поддерживает модели типа:
    - intfloat/multilingual-e5-large
    - sentence-transformers/all-MiniLM-L6-v2
    - и др. модели из HuggingFace

    Attributes:
        model_name: Название модели из HuggingFace
        model: Загруженная модель sentence-transformers
        dimensions: Размерность векторов

    """

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        """Инициализация provider.

        Args:
            model_name: Название модели из HuggingFace
            device: Устройство для inference ('cpu', 'cuda', 'cuda:0', etc.)
            normalize_embeddings: Нормализовать векторы (L2 normalization)

        """
        self.model_name = model_name
        self.device = device or "cpu"
        self.normalize_embeddings = normalize_embeddings
        self.model = None
        self.dimensions = 0

        logger.info(
            "SentenceTransformerProvider инициализирован",
            model=model_name,
            device=self.device,
            normalize=normalize_embeddings,
        )

    async def load(self) -> None:
        """Загрузить модель в память.

        Raises:
            ImportError: Если sentence-transformers не установлен
            Exception: При ошибке загрузки модели

        """
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as e:
            msg = (
                "sentence-transformers не установлен. "
                "Установите: pip install sentence-transformers"
            )
            logger.exception("Ошибка импорта sentence-transformers")
            raise ImportError(msg) from e

        try:
            logger.info("Загрузка embedding модели", model=self.model_name, device=self.device)

            self.model = SentenceTransformer(self.model_name, device=self.device)

            # Определить dimensions
            if self.model is not None:
                test_embedding = self.model.encode("test", normalize_embeddings=self.normalize_embeddings)
                self.dimensions = len(test_embedding)

            logger.info(
                "Embedding модель загружена",
                model=self.model_name,
                dimensions=self.dimensions,
                device=self.device,
            )

        except Exception as e:
            logger.exception("Ошибка загрузки embedding модели", model=self.model_name, error=str(e))
            raise

    async def cleanup(self) -> None:
        """Очистить ресурсы модели."""
        if self.model is not None:
            logger.info("Очистка embedding модели", model=self.model_name)
            del self.model
            self.model = None

            # Очистить CUDA cache если использовался GPU
            if "cuda" in self.device:
                try:
                    import torch  # noqa: PLC0415

                    torch.cuda.empty_cache()
                except ImportError:
                    pass

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Сгенерировать embeddings для списка текстов.

        Args:
            texts: Список текстов для кодирования

        Returns:
            Список векторных представлений (embeddings)

        Raises:
            ValueError: Если модель не загружена

        """
        if self.model is None:
            msg = "Модель не загружена. Вызовите load() перед генерацией embeddings"
            raise ValueError(msg)

        if not texts:
            return []

        try:
            logger.debug(
                "Генерация embeddings",
                model=self.model_name,
                texts_count=len(texts),
            )

            # Генерация embeddings
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            # Конвертировать в list[list[float]]
            result = [emb.tolist() for emb in embeddings]

            logger.debug(
                "Embeddings сгенерированы",
                model=self.model_name,
                count=len(result),
                dimensions=len(result[0]) if result else 0,
            )

            return result

        except Exception as e:
            logger.exception(
                "Ошибка генерации embeddings",
                model=self.model_name,
                error=str(e),
            )
            raise

    def get_info(self) -> dict[str, Any]:
        """Получить информацию о provider.

        Returns:
            Словарь с метаданными provider

        """
        return {
            "model_name": self.model_name,
            "provider_type": "sentence-transformers",
            "dimensions": self.dimensions,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "loaded": self.model is not None,
        }
