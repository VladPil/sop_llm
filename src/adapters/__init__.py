"""Adapters Module - адаптация внешних форматов запросов.

Адаптеры преобразуют различные форматы запросов в единый внутренний формат.

Available adapters:
- IntakeAdapter: адаптация SOP Intake-style запросов

Example:
    >>> from src.adapters import IntakeAdapter
    >>> adapter = IntakeAdapter()
    >>> model, prompt, params, conv_data = adapter.adapt_request(request)

"""

from src.adapters.intake_adapter import ConversationData, IntakeAdapter, get_intake_adapter

__all__ = ["ConversationData", "IntakeAdapter", "get_intake_adapter"]
