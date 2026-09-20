"""
وحدات النشاط اليومي — اللبس والمطبخ المتدرّج.

القاعدة النقية في `dressing`، والفرض في `gate` و`kitchen`. ما يصل المريض من
مهام يمرّ بـ`core.delivery.list_adl_tasks` وحدها، كما يمرّ المحتوى المعتمد.
"""

from core.adl.dressing import DressingStep, check_order, parse_steps, verify_program
from core.adl.types import (
    AdlTask,
    DressingOrderViolation,
    DressingRejected,
    KITCHEN_TIERS,
    KitchenTier,
    SUSPENDED_ON_RED_FLAG,
    TierNotAuthorized,
)

__all__ = [
    "AdlTask",
    "DressingOrderViolation",
    "DressingRejected",
    "DressingStep",
    "KITCHEN_TIERS",
    "KitchenTier",
    "SUSPENDED_ON_RED_FLAG",
    "TierNotAuthorized",
    "check_order",
    "parse_steps",
    "verify_program",
]
