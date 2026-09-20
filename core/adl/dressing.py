"""
ترتيب اللبس — القاعدة النقية
==============================
«يُلبَس الطرف المصاب أولاً، ويُخلَع آخراً.» قاعدة إعادة تأهيل أساسية: القميص
يمرّ على الذراع الضعيفة وهي مسترخية والكمّ واسع، ثم تُدخَل السليمة؛ وعند الخلع
تخرج السليمة أولاً فتبقى الضعيفة في أوسع وضع. عكسُها يعني شدّ كتفٍ مصاب داخل
كمٍّ مشدود — وهذا في كتف نصف مشلول بابُ خلعٍ أو تمزّق، لا إزعاجٌ فقط.

**وحدة القياس هي القطعة لا البرنامج.** لو فحصنا أول خطوة في البرنامج كلّه
لكفى أن تُصدَّر قطعةٌ واحدة صحيحة الترتيب ليمرّ ما بعدها مهما خالف. فخطوات كل
قطعة تسلسلٌ يُفحص وحده، مقطوعاً عند كل تغيّر فعل — فالقطعة التي تُلبَس ثم
تُخلَع ثم تُلبَس ثلاثةُ تسلسلات، والثالث يُفحص كما يُفحص الأول.

لا قاعدة بيانات هنا ولا فاعل: مدخلات ومخرجات فقط، فتُختبر القاعدة مباشرة.
`core.adl.gate` هو الذي يقرأ ويسجّل.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from core.adl.types import (
    DRESSING_ACTIONS,
    SIDED,
    STEP_SIDES,
    DressingAction,
    DressingOrderViolation,
    DressingRejected,
    StepSide,
)

__all__ = [
    "DressingStep",
    "check_order",
    "parse_steps",
    "verify_program",
]


@dataclass(frozen=True, slots=True)
class DressingStep:
    """خطوة واحدة: فعلٌ على قطعةٍ من جانب."""

    action: DressingAction
    side: StepSide
    garment: str

    def __str__(self) -> str:
        return f"{self.action} {self.garment} ({self.side})"


def parse_steps(payload: Mapping[str, Any]) -> tuple[DressingStep, ...]:
    """
    يستخرج خطوات برنامج لبس من حمولة مقترح.

    الشكل المتوقَّع:
    `{"module": "DRESSING", "steps": [{"action": ..., "side": ..., "garment": ...}]}`

    كل انحراف عن الشكل رفضٌ صريح. حمولةٌ لا تُقرأ لا تُفحص، وفحصٌ يمرّ على
    لا شيء يمنح ختماً بلا معنى.
    """
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise DressingRejected("برنامج اللبس بلا خطوات أو بشكل غير متوقَّع")

    parsed: list[DressingStep] = []
    for number, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            raise DressingRejected(f"الخطوة {number} ليست كائناً")

        action, side, garment = raw.get("action"), raw.get("side"), raw.get("garment")
        if action not in DRESSING_ACTIONS:
            raise DressingRejected(
                f"الخطوة {number}: فعل غير معروف {action!r} — المسموح {sorted(DRESSING_ACTIONS)}"
            )
        if side not in STEP_SIDES:
            raise DressingRejected(
                f"الخطوة {number}: جانب غير معروف {side!r} — المسموح {sorted(STEP_SIDES)}"
            )
        if not isinstance(garment, str) or not garment.strip():
            raise DressingRejected(f"الخطوة {number}: بلا اسم قطعة")

        parsed.append(DressingStep(action=action, side=side, garment=garment.strip()))
    return tuple(parsed)


def check_order(steps: Sequence[DressingStep]) -> None:
    """
    يرفع `DressingOrderViolation` عند أبكر مخالفة، أو يعود صامتاً.

    الصمت هنا هو النجاح: الدالة لا تُرجع حكماً يمكن تجاهله بالخطأ.

    «أبكر» بترتيب البرنامج لا بترتيب القطع: الممارس يقرأ من أول السطر، ومخالفةٌ
    تُسمّى في الخطوة 7 بينما الخطوة 3 مخالفة أيضاً ترسل إليه إلى الموضع الخطأ.
    """
    violations = []
    for sequence in _sequences(steps):
        sided = [(number, step) for number, step in sequence if step.side in SIDED]
        if not sided:
            continue  # قطعة بلا جانب — قبّعة أو وشاح — لا ترتيب لها.

        action = sequence[0][1].action
        number, step = sided[0] if action == "DON" else sided[-1]
        if step.side != "AFFECTED":
            violations.append((number, action, step))

    if not violations:
        return

    number, action, step = min(violations, key=lambda violation: violation[0])
    position = "أول" if action == "DON" else "آخر"
    rule = (
        "اللبس يبدأ بالجانب المصاب"
        if action == "DON"
        else "الخلع ينتهي بالجانب المصاب"
    )
    raise DressingOrderViolation(
        f"الخطوة {number} «{step.garment}»: {rule}، وهي {position} خطوة ذات "
        f"جانب في تسلسلها وجانبها {step.side}",
        step_number=number,
        step=step,
    )


def verify_program(payload: Mapping[str, Any]) -> tuple[DressingStep, ...]:
    """يقرأ ثم يفحص. يُرجع الخطوات كما فُهمت، فيُسجَّل ما فُحص لا ما يُظنّ."""
    steps = parse_steps(payload)
    check_order(steps)
    return steps


def _sequences(
    steps: Sequence[DressingStep],
) -> Iterator[list[tuple[int, DressingStep]]]:
    """
    يقسّم البرنامج إلى تسلسلات: خطوات قطعةٍ واحدة، مقطوعةً عند كل تغيّر فعل.

    التجميع بالقطعة أولاً لا بالتجاور، وهذا فرقٌ يقرّر أحكاماً:

      • برنامجٌ يتنقّل بين قطعتين (المصاب في القميص، ثم المصاب في البنطال،
        ثم السليم في القميص) صحيحٌ سريرياً. لو قُسّم بالتجاور لصار كل خطوة
        تسلسلاً وحدها ولرُفض البرنامج — ورفضُ الصحيح في بوابة سلامة يدفع
        إلى إعادة ترتيبٍ يُرضي الآلة لا المريض.

      • والقطع عند تغيّر الفعل ضروري: قطعةٌ تُلبَس فتُخلَع فتُلبَس مرة أخرى
        ثلاثةُ تسلسلات، والثالث يُفحص كما يُفحص الأول. لولاه لمرّ اللبس
        الثاني لأن الأول كان صحيحاً.

    الأرقام المرافقة مواضع الخطوات في البرنامج كاملاً، حتى تسمّي رسالة
    المخالفة ما يراه الممارس على الشاشة.
    """
    by_garment: dict[str, list[tuple[int, DressingStep]]] = {}
    for number, step in enumerate(steps, start=1):
        by_garment.setdefault(step.garment, []).append((number, step))

    for garment_steps in by_garment.values():
        segment: list[tuple[int, DressingStep]] = []
        for number, step in garment_steps:
            if segment and step.action != segment[-1][1].action:
                yield segment
                segment = []
            segment.append((number, step))
        if segment:
            yield segment
