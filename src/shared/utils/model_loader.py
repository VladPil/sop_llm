"""Model Loader утилиты для загрузки моделей."""

import asyncio
import psutil
import torch
from typing import Any, Tuple
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer


class ModelLoader:
    """Утилита для загрузки и управления моделями."""

    def __init__(self):
        """Инициализация ModelLoader."""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"ModelLoader инициализирован с device: {self.device}")

    def check_available_memory(self) -> Tuple[float, float]:
        """Проверяет доступную память системы.

        Returns:
            Tuple[float, float]: (доступная память в ГБ, процент использования)
        """
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        memory_percent = memory.percent
        return available_gb, memory_percent

    async def load_llm_model(
        self,
        model_name: str,
        load_in_8bit: bool = False,
    ) -> Tuple[Any, Any]:
        """Загружает LLM модель асинхронно.

        Args:
            model_name: Имя или путь к модели
            load_in_8bit: Загружать в 8-bit режиме

        Returns:
            Tuple[model, tokenizer]: Загруженная модель и токенизатор
        """
        logger.info(f"Загрузка LLM модели {model_name} (8-bit: {load_in_8bit})")

        def _load():
            kwargs = {
                "trust_remote_code": True,
                "device_map": "auto" if torch.cuda.is_available() else None,
            }
            if load_in_8bit:
                kwargs["load_in_8bit"] = True

            tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)

            if not torch.cuda.is_available():
                model = model.to(self.device)

            return model, tokenizer

        # Запускаем загрузку в executor для неблокирующей работы
        model, tokenizer = await asyncio.get_event_loop().run_in_executor(None, _load)

        logger.success(f"Модель {model_name} успешно загружена")
        return model, tokenizer

    async def load_embedding_model(
        self,
        model_name: str,
    ) -> Tuple[Any, Any]:
        """Загружает Embedding модель асинхронно.

        Args:
            model_name: Имя или путь к модели

        Returns:
            Tuple[model, tokenizer]: Загруженная модель и токенизатор
        """
        from sentence_transformers import SentenceTransformer

        logger.info(f"Загрузка Embedding модели {model_name}")

        def _load():
            model = SentenceTransformer(model_name, device=str(self.device))
            return model, None  # У SentenceTransformer нет отдельного tokenizer

        model, tokenizer = await asyncio.get_event_loop().run_in_executor(None, _load)

        logger.success(f"Embedding модель {model_name} успешно загружена")
        return model, tokenizer


# Глобальный экземпляр
model_loader = ModelLoader()


def check_model_in_cache(model_name: str) -> bool:
    """Проверяет наличие модели в кэше (заглушка).

    Args:
        model_name: Имя модели

    Returns:
        bool: Всегда False (кэширование не реализовано)
    """
    # TODO: Реализовать проверку кэша моделей
    return False
