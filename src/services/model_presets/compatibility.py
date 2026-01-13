"""Compatibility Checker - проверка совместимости модели с GPU.

Single Responsibility: только проверка VRAM и рекомендация квантизации.
Не выполняет загрузку моделей или другие операции.
"""

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.core.model_presets import LocalModelPreset
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.engine.vram_monitor import VRAMMonitor

logger = get_logger()


class CompatibilityResult(BaseModel):
    """Результат проверки совместимости с GPU.

    Содержит информацию о том, поместится ли модель в VRAM,
    и рекомендацию по квантизации если не поместится.
    """

    compatible: bool = Field(
        description="True если модель поместится в доступную VRAM",
    )

    required_vram_mb: int = Field(
        description="Требуемая VRAM в MB",
    )

    available_vram_mb: int = Field(
        description="Доступная VRAM в MB",
    )

    recommended_quantization: str | None = Field(
        default=None,
        description="Рекомендуемая квантизация если модель не помещается (q4_k_m, q5_k_m, q8_0, fp16)",
    )

    warning: str | None = Field(
        default=None,
        description="Предупреждение если модель не помещается",
    )


class CompatibilityChecker:
    """Проверка совместимости модели с GPU.

    Single Responsibility: только проверка VRAM и рекомендация квантизации.

    Использует VRAMMonitor для получения информации о доступной VRAM,
    и vram_requirements из пресета для определения требований модели.

    Example:
        >>> vram_monitor = get_vram_monitor()
        >>> checker = CompatibilityChecker(vram_monitor)
        >>> preset = loader.get_local_preset("qwen2.5-7b-instruct")
        >>> result = checker.check_compatibility(preset)
        >>> if not result.compatible:
        ...     print(f"Рекомендуется: {result.recommended_quantization}")

    """

    # Коэффициенты для оценки VRAM (GB per billion params)
    # Используются если vram_requirements не указаны в пресете
    VRAM_COEFFICIENTS: dict[str, float] = {
        "q4_k_m": 0.5,   # ~0.5 GB per 1B params
        "q5_k_m": 0.6,   # ~0.6 GB per 1B params
        "q8_0": 0.9,     # ~0.9 GB per 1B params
        "fp16": 2.0,     # ~2.0 GB per 1B params
    }

    # Порядок квантизаций от самой компактной к наименее компактной
    QUANTIZATION_ORDER: list[str] = ["q4_k_m", "q5_k_m", "q8_0", "fp16"]

    def __init__(self, vram_monitor: "VRAMMonitor") -> None:
        """Инициализировать CompatibilityChecker.

        Args:
            vram_monitor: VRAMMonitor instance для получения информации о GPU

        """
        self._vram_monitor = vram_monitor

    def estimate_vram_mb(self, size_b: float, quantization: str) -> int:
        """Оценить требования VRAM для модели.

        Используется когда vram_requirements не указаны в пресете.

        Args:
            size_b: Размер модели в миллиардах параметров
            quantization: Тип квантизации (q4_k_m, q5_k_m, q8_0, fp16)

        Returns:
            Оценка требуемой VRAM в MB (с запасом 15%)

        """
        coef = self.VRAM_COEFFICIENTS.get(quantization.lower(), 1.0)
        # Оценка: size_b * coef GB, конвертируем в MB, добавляем 15% запас
        estimated_gb = size_b * coef
        return int(estimated_gb * 1024 * 1.15)

    def extract_quantization(self, filename: str) -> str:
        """Извлечь тип квантизации из имени файла.

        Args:
            filename: Имя GGUF файла

        Returns:
            Тип квантизации (q4_k_m, q5_k_m, q8_0, fp16) или "q4_k_m" по умолчанию

        Example:
            >>> extract_quantization("qwen2.5-7b-instruct-q4_k_m.gguf")
            'q4_k_m'
            >>> extract_quantization("model-Q8_0.gguf")
            'q8_0'

        """
        filename_lower = filename.lower()

        # Паттерны квантизации
        patterns = [
            (r"q4_k_m", "q4_k_m"),
            (r"q5_k_m", "q5_k_m"),
            (r"q8_0", "q8_0"),
            (r"q6_k", "q8_0"),  # q6_k близка к q8_0
            (r"q5_k_s", "q5_k_m"),
            (r"q4_k_s", "q4_k_m"),
            (r"q3_k_m", "q4_k_m"),
            (r"q2_k", "q4_k_m"),
            (r"fp16", "fp16"),
            (r"f16", "fp16"),
        ]

        for pattern, quant in patterns:
            if re.search(pattern, filename_lower):
                return quant

        # По умолчанию предполагаем q4_k_m
        return "q4_k_m"

    def check_compatibility(
        self,
        preset: LocalModelPreset,
        quantization: str | None = None,
    ) -> CompatibilityResult:
        """Проверить совместимость модели с текущим GPU.

        Args:
            preset: Пресет локальной модели
            quantization: Переопределить квантизацию (если None, берётся из filename)

        Returns:
            CompatibilityResult с результатом проверки

        """
        # Определить квантизацию
        quant = quantization or self.extract_quantization(preset.filename)
        quant_lower = quant.lower()

        # Получить требования VRAM
        if quant_lower in preset.vram_requirements:
            required_mb = preset.vram_requirements[quant_lower]
        else:
            # Оценить если не указано в пресете
            required_mb = self.estimate_vram_mb(preset.size_b, quant_lower)
            logger.debug(
                "VRAM requirements оценены",
                model=preset.name,
                quantization=quant_lower,
                estimated_mb=required_mb,
            )

        # Получить доступную VRAM
        try:
            available_mb = int(self._vram_monitor.get_available_vram_mb())
        except Exception as e:
            logger.warning("Не удалось получить VRAM info", error=str(e))
            # Если GPU недоступен, возвращаем несовместимо
            return CompatibilityResult(
                compatible=False,
                required_vram_mb=required_mb,
                available_vram_mb=0,
                warning=f"GPU недоступен: {e}",
            )

        # Проверить совместимость
        compatible = required_mb <= available_mb

        # Если не совместимо - рекомендовать квантизацию
        recommended = None
        warning = None

        if not compatible:
            recommended = self._recommend_quantization(preset, available_mb)
            warning = f"Модель требует {required_mb}MB VRAM, доступно {available_mb}MB"

            if recommended:
                warning += f". Рекомендуется использовать {recommended}"
            else:
                warning += ". Модель не поместится в VRAM даже с q4_k_m"

            logger.warning(
                "Модель несовместима с GPU",
                model=preset.name,
                required_mb=required_mb,
                available_mb=available_mb,
                recommended=recommended,
            )

        return CompatibilityResult(
            compatible=compatible,
            required_vram_mb=required_mb,
            available_vram_mb=available_mb,
            recommended_quantization=recommended,
            warning=warning,
        )

    def _recommend_quantization(
        self,
        preset: LocalModelPreset,
        available_mb: int,
    ) -> str | None:
        """Рекомендовать квантизацию которая поместится в VRAM.

        Перебирает квантизации от самой компактной (q4_k_m) к наименее (fp16)
        и возвращает первую которая помещается.

        Args:
            preset: Пресет модели
            available_mb: Доступная VRAM в MB

        Returns:
            Рекомендуемая квантизация или None если ни одна не помещается

        """
        for quant in self.QUANTIZATION_ORDER:
            # Получить требования для этой квантизации
            if quant in preset.vram_requirements:
                required = preset.vram_requirements[quant]
            else:
                required = self.estimate_vram_mb(preset.size_b, quant)

            if required <= available_mb:
                return quant

        return None

    def get_all_compatible_quantizations(
        self,
        preset: LocalModelPreset,
    ) -> list[str]:
        """Получить список всех совместимых квантизаций.

        Args:
            preset: Пресет модели

        Returns:
            Список совместимых квантизаций (от самой компактной)

        """
        try:
            available_mb = int(self._vram_monitor.get_available_vram_mb())
        except Exception:
            return []

        compatible: list[str] = []

        for quant in self.QUANTIZATION_ORDER:
            if quant in preset.vram_requirements:
                required = preset.vram_requirements[quant]
            else:
                required = self.estimate_vram_mb(preset.size_b, quant)

            if required <= available_mb:
                compatible.append(quant)

        return compatible


# === Initialize + Get паттерн ===

_compatibility_checker: CompatibilityChecker | None = None


def create_compatibility_checker(vram_monitor: "VRAMMonitor") -> CompatibilityChecker:
    """Factory: создать CompatibilityChecker с DI.

    Args:
        vram_monitor: VRAMMonitor instance

    Returns:
        Инициализированный CompatibilityChecker

    """
    return CompatibilityChecker(vram_monitor)


def get_compatibility_checker() -> CompatibilityChecker:
    """Получить singleton CompatibilityChecker.

    Raises:
        RuntimeError: Если checker не инициализирован

    Returns:
        CompatibilityChecker instance

    """
    if _compatibility_checker is None:
        msg = "CompatibilityChecker не инициализирован. Вызовите set_compatibility_checker() в lifespan."
        raise RuntimeError(msg)
    return _compatibility_checker


def set_compatibility_checker(checker: CompatibilityChecker) -> None:
    """Установить singleton CompatibilityChecker.

    Вызывается в app.py lifespan при старте приложения.

    Args:
        checker: Инициализированный CompatibilityChecker

    """
    global _compatibility_checker
    _compatibility_checker = checker
