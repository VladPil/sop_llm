"""Менеджер embedding моделей с batch processing."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch
from loguru import logger

from src.core.config import settings
from src.shared.utils import model_loader, check_model_in_cache
from src.shared.errors import ModelNotLoadedError, ServiceUnavailableError


class EmbeddingManager:
    """Менеджер для управления embedding моделью."""

    def __init__(self) -> None:
        """Инициализация менеджера."""
        self.model: Optional[Any] = None
        self.tokenizer: Optional[Any] = None
        self.device = model_loader.device
        self.model_name: Optional[str] = None

        # Статистика
        self.total_embeddings = 0

        logger.info("EmbeddingManager инициализирован")

    async def load_model(self, model_name: Optional[str] = None) -> None:
        """Загружает embedding модель.

        Args:
            model_name: Имя модели
        """
        self.model_name = model_name or settings.llm.default_embedding_model

        # Проверяем кэш перед загрузкой
        is_cached = check_model_in_cache(self.model_name)
        if is_cached:
            logger.info(f"Модель {self.model_name} уже в кэше, загружаем...")
        else:
            logger.info(
                f"Модель {self.model_name} не в кэше, "
                "будет загружена при первом запросе"
            )

        logger.info(f"Загружаем embedding модель: {self.model_name}")

        self.model, self.tokenizer = await model_loader.load_embedding_model(
            model_name=self.model_name
        )

        logger.info(f"Embedding модель загружена: {self.model_name}")

    def _mean_pooling(
        self, model_output: Any, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Mean pooling для получения sentence embeddings.

        Args:
            model_output: Выход модели
            attention_mask: Маска внимания

        Returns:
            Pooled embeddings
        """
        # Первый элемент model_output содержит все token embeddings
        token_embeddings = model_output[0]

        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        )

        return torch.sum(
            token_embeddings * input_mask_expanded, 1
        ) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    async def get_embedding(self, text: str) -> List[float]:
        """Получает embedding для одного текста.

        Args:
            text: Входной текст

        Returns:
            Список float значений (embedding вектор)

        Raises:
            ModelNotLoadedError: Если модель не загружена
        """
        if not self.model or not self.tokenizer:
            raise ModelNotLoadedError(model_name=self.model_name or "embedding")

        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Получает embeddings для списка текстов (batch processing).

        Args:
            texts: Список текстов

        Returns:
            Список embedding векторов

        Raises:
            ModelNotLoadedError: Если модель не загружена
            ServiceUnavailableError: Если генерация не удалась
        """
        if not self.model or not self.tokenizer:
            raise ModelNotLoadedError(model_name=self.model_name or "embedding")

        if not texts:
            return []

        start_time = datetime.now()

        try:
            logger.info(f"Генерируем embeddings для {len(texts)} текстов", batch_size=len(texts))

            # Запускаем в executor (blocking operation)
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, self._get_embeddings_sync, texts
            )

            self.total_embeddings += len(texts)

            duration = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                f"Сгенерированы embeddings для {len(texts)} текстов",
                duration_ms=round(duration, 2),
                texts_count=len(texts),
                avg_ms_per_text=round(duration / len(texts), 2),
            )

            return embeddings

        except Exception as e:
            logger.error(f"Не удалось сгенерировать embeddings: {e}")
            raise ServiceUnavailableError(
                message=f"Генерация embeddings не удалась: {str(e)}"
            )

    def _get_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """Синхронная генерация embeddings (для executor).

        Args:
            texts: Список текстов

        Returns:
            Список embedding векторов
        """
        # Токенизация
        encoded_input = self.tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
        ).to(self.device)

        # Генерация embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)

        # Mean pooling
        embeddings = self._mean_pooling(model_output, encoded_input["attention_mask"])

        # Нормализация
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        # Конвертируем в список
        embeddings_list = embeddings.cpu().numpy().tolist()

        return embeddings_list

    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Косинусное сходство.

        Args:
            emb1: Первый embedding
            emb2: Второй embedding

        Returns:
            Косинусное сходство (от -1 до 1)
        """
        return float(
            np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        )

    def _euclidean_distance(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Евклидово расстояние (нормализованное от 0 до 1, где 1 - идентичные).

        Args:
            emb1: Первый embedding
            emb2: Второй embedding

        Returns:
            Нормализованное расстояние
        """
        distance = np.linalg.norm(emb1 - emb2)
        # Нормализуем: чем меньше расстояние, тем больше схожесть
        return float(1 / (1 + distance))

    def _manhattan_distance(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Манхэттенское расстояние (нормализованное от 0 до 1).

        Args:
            emb1: Первый embedding
            emb2: Второй embedding

        Returns:
            Нормализованное расстояние
        """
        distance = np.sum(np.abs(emb1 - emb2))
        return float(1 / (1 + distance))

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Коэффициент Жаккара для токенов.

        Args:
            text1: Первый текст
            text2: Второй текст

        Returns:
            Коэффициент Жаккара (от 0 до 1)
        """
        # Токенизируем тексты на слова
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())

        if not tokens1 and not tokens2:
            return 1.0

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        if not union:
            return 0.0

        return float(len(intersection) / len(union))

    def _pearson_correlation(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Корреляция Пирсона.

        Args:
            emb1: Первый embedding
            emb2: Второй embedding

        Returns:
            Корреляция Пирсона (от -1 до 1)
        """
        # Центрируем векторы
        emb1_centered = emb1 - np.mean(emb1)
        emb2_centered = emb2 - np.mean(emb2)

        # Вычисляем корреляцию
        numerator = np.sum(emb1_centered * emb2_centered)
        denominator = np.sqrt(np.sum(emb1_centered**2)) * np.sqrt(
            np.sum(emb2_centered**2)
        )

        if denominator == 0:
            return 0.0

        return float(numerator / denominator)

    def _dot_product(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Скалярное произведение.

        Args:
            emb1: Первый embedding
            emb2: Второй embedding

        Returns:
            Скалярное произведение
        """
        return float(np.dot(emb1, emb2))

    async def compute_similarity(
        self, text1: str, text2: str, method: str = "cosine"
    ) -> Union[float, Dict[str, float]]:
        """Вычисляет схожесть между двумя текстами используя указанный метод.

        Args:
            text1: Первый текст
            text2: Второй текст
            method: Метод вычисления ("cosine", "euclidean", "manhattan",
                   "jaccard", "pearson", "dot_product", "all")

        Returns:
            Схожесть (float) или словарь всех методов (если method="all")
        """
        # Для метода Жаккара не нужны embeddings
        if method == "jaccard":
            return self._jaccard_similarity(text1, text2)

        # Для всех методов сразу
        if method == "all":
            # Получаем embeddings один раз
            embeddings = await self.get_embeddings([text1, text2])
            emb1 = np.array(embeddings[0])
            emb2 = np.array(embeddings[1])

            return {
                "cosine": self._cosine_similarity(emb1, emb2),
                "euclidean": self._euclidean_distance(emb1, emb2),
                "manhattan": self._manhattan_distance(emb1, emb2),
                "jaccard": self._jaccard_similarity(text1, text2),
                "pearson": self._pearson_correlation(emb1, emb2),
                "dot_product": self._dot_product(emb1, emb2),
            }

        # Получаем embeddings
        embeddings = await self.get_embeddings([text1, text2])
        emb1 = np.array(embeddings[0])
        emb2 = np.array(embeddings[1])

        # Вычисляем схожесть по выбранному методу
        if method == "cosine":
            return self._cosine_similarity(emb1, emb2)
        elif method == "euclidean":
            return self._euclidean_distance(emb1, emb2)
        elif method == "manhattan":
            return self._manhattan_distance(emb1, emb2)
        elif method == "pearson":
            return self._pearson_correlation(emb1, emb2)
        elif method == "dot_product":
            return self._dot_product(emb1, emb2)
        else:
            raise ValueError(f"Неизвестный метод схожести: {method}")

    def get_stats(self) -> Dict[str, Any]:
        """Получает статистику менеджера.

        Returns:
            Словарь со статистикой
        """
        return {
            "model_name": self.model_name,
            "device": str(self.device),
            "model_loaded": self.model is not None,
            "total_embeddings": self.total_embeddings,
        }


# Глобальный экземпляр
embedding_manager = EmbeddingManager()
