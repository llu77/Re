"""
أنواع وحدتَي النشاط اليومي — اللبس والمطبخ
===========================================
وحدتان تلتقيان في مبدأ واحد: **الخطر يُفتح بقرار إنسان، لا بتقدّم المريض.**
المطبخ مُدرَّج بأربعة مستويات لا يفتح أحدها إلا بتفويض ممارس مسمّى، واللبس
مرتَّب بقاعدة سريرية يرفض المخطط ما يخالفها.

الجانب هنا **رمزي لا اتجاهي**: `AFFECTED` و`SOUND` لا «يمين» و«يسار». برنامج
اللبس يُكتب مرة فيصلح لكل مريض، والفحص يصير مقارنةَ رمز بدل مطابقة نصّ عربي
تكسرها مسافةٌ أو مرادف. البوابة تحلّ الرمز إلى الذراع المعنية من
`affected_side` عند العرض، وهناك وحده يظهر الاتجاه.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

__all__ = [
    "AdlModule",
    "AdlTask",
    "DRESSING_ACTIONS",
    "DressingAction",
    "DressingOrderViolation",
    "DressingRejected",
    "KITCHEN_TIERS",
    "KitchenAuthorization",
    "KitchenTier",
    "SIDED",
    "STEP_SIDES",
    "StepSide",
    "SUSPENDED_ON_RED_FLAG",
    "TierNotAuthorized",
]

AdlModule = Literal["DRESSING", "KITCHEN"]

DressingAction = Literal["DON", "DOFF"]
StepSide = Literal["AFFECTED", "SOUND", "BOTH"]

DRESSING_ACTIONS: frozenset[str] = frozenset({"DON", "DOFF"})
STEP_SIDES: frozenset[str] = frozenset({"AFFECTED", "SOUND", "BOTH"})

#: الجوانب التي تميّز طرفاً بعينه. `BOTH` ليست منها عمداً: خطوة يشترك فيها
#: الطرفان (سحب البنطال لأعلى) لا ترتيب لها، فإقحامها في القاعدة يرفض
#: برامج سليمة.
SIDED: frozenset[str] = frozenset({"AFFECTED", "SOUND"})


class DressingRejected(Exception):
    """برنامج لبس لا يصلح للفحص أو لا يجتازه. لا يتقدّم خطوة واحدة."""


class DressingOrderViolation(DressingRejected):
    """
    خطوة تخالف ترتيب اللبس السريري، مسمّاة برقمها.

    الرقم رقم الخطوة في البرنامج كاملاً (يبدأ من 1) لا داخل تسلسلها، لأن
    الممارس يقرأ البرنامج كاملاً لا مقسَّماً.
    """

    def __init__(self, message: str, *, step_number: int, step: object) -> None:
        super().__init__(message)
        self.step_number = step_number
        self.step = step


class TierNotAuthorized(Exception):
    """مستوى مطبخ لم يُفوَّض لهذا المريض. الرفض هنا تكرارٌ لما يمنعه المخطط."""


@dataclass(frozen=True, slots=True)
class KitchenTier:
    """
    مستوى واحد من تدرّج المطبخ.

    `suspends_on_red_flag` هي سياسة التعليق: مستوىً يحمل حرارة يُحجب ما دام
    هناك بلاغ علامة حمراء لم يستلمه إنسان. وهي بيان واحد يُبذَر في جدول
    `kitchen_tier`، والعرض يقرأ العمود لا رقم المستوى — فلا ينحرف النصّ هنا
    عن الشرط هناك.
    """

    tier: int
    label_ar: str
    hazard: str
    suspends_on_red_flag: bool


#: التدرّج كما أُقرّ: أربعة مستويات يفصل بينها الخطر لا الصعوبة.
#:
#: الفاصل بين 2 و3 هو الحدّ الذي يعلَّق عنده كل شيء: الحدّ يجرح، والحرارة
#: تحرق وتُشعل ولا تُوقَف بالانتباه وحده.
KITCHEN_TIERS: tuple[KitchenTier, ...] = (
    KitchenTier(
        tier=1,
        label_ar="تحضير بارد: بلا أداة حادّة وبلا حرارة",
        hazard="لا حرارة ولا حدّ — الخطر انزلاق أو إجهاد وقوف",
        suspends_on_red_flag=False,
    ),
    KitchenTier(
        tier=2,
        label_ar="أدوات حادّة بلا حرارة",
        hazard="الجرح والقطع",
        suspends_on_red_flag=False,
    ),
    KitchenTier(
        tier=3,
        label_ar="حرارة: موقد أو فرن أو ميكروويف",
        hazard="الحرق والحريق وانسكاب السوائل الساخنة",
        suspends_on_red_flag=True,
    ),
    KitchenTier(
        tier=4,
        label_ar="طبخ كامل مستقل",
        hazard="حرارة وحدّ وتعدّد مهام متزامن بلا إشراف",
        suspends_on_red_flag=True,
    ),
)

#: المستويات التي يعلّقها بلاغٌ غير مُستلَم. نظيرها في المخطط عمودٌ لا ثابت،
#: واختبار يقارن الاثنين فيمنع انحرافهما.
SUSPENDED_ON_RED_FLAG: frozenset[int] = frozenset(
    tier.tier for tier in KITCHEN_TIERS if tier.suspends_on_red_flag
)


@dataclass(frozen=True, slots=True)
class AdlTask:
    """مهمة من الكتالوج. `tier` للمطبخ وحده — مهمة لبس بمستوى تدّعي تدرّجاً."""

    code: str
    module: AdlModule
    label_ar: str
    tier: int | None = None
    hazard: str | None = None


@dataclass(frozen=True, slots=True)
class KitchenAuthorization:
    """
    تفويض مستوىً واحدٍ لمريض واحد، بأساسه ومَن منحه.

    `is_active` لا تكفي وحدها لفتح المهمة: التعليق عند بلاغٍ غير مُستلَم
    شرطٌ في العرض لا في هذا الصفّ، فالتفويض يبقى قائماً والمهمة محجوبة. هذا
    مقصود — الاستلام يرفع الحجب بلا أن يعيد أحدٌ منح شيء.
    """

    id: UUID
    tenant_id: UUID
    patient_id: UUID
    tier: int
    basis: str
    granted_by: UUID
    granted_at: datetime
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
