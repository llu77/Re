"""
الميزانية والمدّة
=================
ميزانيةٌ إجمالية واحدة بالريال السعودي، بريالاتٍ صحيحة، ومدّةٌ بالأيام.

**إجمالية لا يومية — افتراضٌ معلَن.** الرقم الذي يعتمده المستخدم هو أقصى ما
يمكن أن يُنفق؛ أمّا ميزانيةٌ يومية تُضرب في الأيام فتُضاعف أيّ خطأ في
أيٍّ منهما. والمبلغ اليومي يُشتقّ للعرض فقط ولا يُعتمد.

**مجالٌ مغلق من ستٍّ وثلاثين قيمة.** من خمسين إلى ألف بخطوات الخمسين، ثم
إلى خمسة آلاف بخطوات المئتين والخمسين. كل قيمةٍ على خمس نظراتٍ على الأكثر
من أقرب خيارٍ جاهز، ولكلّ قيمةٍ كلماتٌ مختبَرة واحدةً واحدة. رفعُ السقف
ترحيلٌ وتغييرُ ثابت، لا خطأٌ صامت.

المجال هنا، ونظيره في القاعدة الدالّة `ew_budget_allowed`؛ واختبارٌ يقارن
الاثنين على كل عددٍ من صفرٍ إلى ستة آلاف.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from eyework.arabic_numbers import DAY, RIYAL, in_words

__all__ = [
    "BUDGET_PRESETS",
    "BUDGET_VALUES",
    "DAY_PRESETS",
    "DAY_VALUES",
    "budget_in_words",
    "budget_short",
    "choices",
    "daily_amount",
    "days_in_words",
    "days_short",
    "is_valid_budget",
    "is_valid_days",
    "step_down",
    "step_up",
]

BUDGET_VALUES: tuple[int, ...] = (*range(50, 1001, 50), *range(1250, 5001, 250))
BUDGET_PRESETS: tuple[int, ...] = (100, 250, 500, 1000, 2500, 5000)

DAY_VALUES: tuple[int, ...] = tuple(range(1, 31))
DAY_PRESETS: tuple[int, ...] = (1, 3, 7, 14, 21, 30)

_HALALA = Decimal("0.01")
_BUDGETS = frozenset(BUDGET_VALUES)
_DAYS = frozenset(DAY_VALUES)


def _is_int(value: object) -> bool:
    # bool فرعٌ من int في بايثون؛ `True` ليست ميزانية.
    return isinstance(value, int) and not isinstance(value, bool)


def is_valid_budget(value: object) -> bool:
    return _is_int(value) and value in _BUDGETS


def is_valid_days(value: object) -> bool:
    return _is_int(value) and value in _DAYS


def _step(values: tuple[int, ...], current: int | None, delta: int) -> int | None:
    """
    القيمة المجاورة في المجال، أو `None` عند الحدّ — لا التفاف ولا قصٌّ صامت.

    بلا قيمةٍ بعد، لا يتقدّم إلا «أكثر» إلى أصغر قيمة: لا قيمة افتراضية
    يقبلها المستخدم دون أن يختارها.
    """
    if current is None:
        return values[0] if delta > 0 else None
    index = values.index(current) + delta
    return values[index] if 0 <= index < len(values) else None


def step_up(values: tuple[int, ...], current: int | None) -> int | None:
    return _step(values, current, +1)


def step_down(values: tuple[int, ...], current: int | None) -> int | None:
    return _step(values, current, -1)


def budget_in_words(budget: int) -> str:
    if not is_valid_budget(budget):
        raise ValueError(f"ميزانية خارج المجال: {budget!r}")
    return in_words(budget, RIYAL)


def days_in_words(days: int) -> str:
    if not is_valid_days(days):
        raise ValueError(f"مدّة خارج المجال: {days!r}")
    return in_words(days, DAY)


def budget_short(budget: int) -> str:
    """أرقامٌ غربية مجمّعة ورمز العملة: «2,500 ر.س». الكلمات تُعرض بجانبها."""
    if not is_valid_budget(budget):
        raise ValueError(f"ميزانية خارج المجال: {budget!r}")
    return f"{budget:,} ر.س"


def days_short(days: int) -> str:
    """«يوم واحد» · «يومان» · «3 أيام» · «14 يوماً» — الرقم والمعدود متّفقان."""
    if not is_valid_days(days):
        raise ValueError(f"مدّة خارج المجال: {days!r}")
    if days == 1:
        return "يوم واحد"
    if days == 2:
        return "يومان"
    return f"{days} أيام" if days <= 10 else f"{days} يوماً"


def daily_amount(budget: int, days: int) -> tuple[Decimal, bool]:
    """
    المبلغ اليومي بالهللة، وهل القسمة تامّة.

    `Decimal` لا `float`: ‎1000/7 بالفاصلة العائمة لا يُقرّب عشرياً كما يُتوقّع.
    والتقريب إلى الأعلى عند النصف هو ما يتوقّعه قارئ مبلغٍ على شاشة.
    القسمة غير التامّة تُعرض بكلمة «نحو»، فلا يُفهم الرقم وعداً دقيقاً.
    """
    if not is_valid_budget(budget) or not is_valid_days(days):
        raise ValueError("ميزانية أو مدّة خارج المجال")
    exact = Decimal(budget) / Decimal(days)
    rounded = exact.quantize(_HALALA, rounding=ROUND_HALF_UP)
    return rounded, rounded == exact


def choices() -> dict:
    """
    كل ما تعرضه الواجهة للميزانية والمدّة، محسوباً هنا مرةً واحدة.

    الواجهة تبحث في هذا الجدول ولا تحسب: لا كلمة ولا حدّ ولا خطوة تُشتقّ في
    المتصفّح.
    """
    return {
        "budget": {
            "values": [
                {"sar": v, "short": budget_short(v), "words": budget_in_words(v)} for v in BUDGET_VALUES
            ],
            "presets": list(BUDGET_PRESETS),
        },
        "days": {
            "values": [{"n": d, "short": days_short(d), "words": days_in_words(d)} for d in DAY_VALUES],
            "presets": list(DAY_PRESETS),
        },
    }
