"""
حدود الأدوات وإعداداتها
=======================
نظير جدول `ai_features` في الترحيل 0009، واختبارٌ يقارنهما فلا ينحرفان؛ ومعه
إعدادات الاستدعاء لكل عائلةٍ من الأدوات: الجهد، والسقف، والمهلة، والبثّ،
ونسخة التعليمات.

**السقوف في القاعدة لا هنا.** ما كلفته مال يُفرض في `ew_ai_request_open`
فيصمد مهما تعدّدت العمليات؛ القائمة هنا للعرض وللاختبار، لا للفرض.

**الجهد مثبّتٌ لكل أداة** ولا يتغيّر من طلبٍ إلى طلب: تغييره يُبطل البادئة
المخزّنة لدى المزوّد. `low` للمراجِع والمساعد لأنهما داخل ضغطة من يعمل
بعينيه؛ وتقييم الإصدار (`scripts/ai_eval.py`) يقارن `low` بـ`medium` قبل
الاعتماد.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "AI_SLOTS",
    "ANSWER_LENGTH",
    "ANSWER_MAX_LINES",
    "ASSISTANT",
    "ASSISTANT_PROMPT_VERSION",
    "BREAKER_FAILURES",
    "BREAKER_OPEN_SECONDS",
    "BREAKER_WINDOW_SECONDS",
    "DRAFT",
    "FEATURES",
    "KB_CHARS",
    "MAX_FLAGS",
    "QUESTION_LENGTH",
    "QUOTE_LENGTH",
    "READY_QUESTIONS_MAX",
    "REASON_LENGTH",
    "REVIEW",
    "REVIEW_PROMPT_VERSION",
    "REVIEW_WAIT_SECONDS",
    "SCREEN_DATA_CHARS",
    "STREAM_TIMEOUT_SECONDS",
    "SUGGESTION_LENGTH",
    "CallSettings",
    "FeatureLimits",
]


@dataclass(frozen=True, slots=True)
class FeatureLimits:
    #: None: لكل مهنة (المساعد). وإلا فلأصحاب مهنتها وحدهم.
    profession: str | None
    per_user_10min: int
    per_user_day: int
    per_new_user_day: int
    app_day: int
    #: عقد الاستدعاء بالثواني: بعده لا يُعدّ جارياً، ولا تُكتب نتيجته الناجحة.
    lease_seconds: int


#: صفوف `ai_features` حرفاً بحرف (الترحيل 0009). الحملة خارجها بسقوفها في
#: `ew_begin_generation`، ويجمعهما السقف العام: ألفان في اليوم، منها أربعمئة للجدد.
FEATURES: dict[str, FeatureLimits] = {
    "ASSISTANT": FeatureLimits(None, 10, 60, 15, 1000, 60),
    "STOCK_REVIEW": FeatureLimits("STOREKEEPER", 6, 30, 10, 600, 60),
    "SUPPORT_DRAFT": FeatureLimits("SUPPORT", 10, 60, 10, 800, 150),
    "SUPPORT_REPLY_REVIEW": FeatureLimits("SUPPORT", 10, 60, 10, 600, 60),
    "SUPPORT_ARTICLE_PROPOSAL": FeatureLimits("SUPPORT", 3, 10, 3, 150, 150),
    "SUPPORT_ARTICLE_REVIEW": FeatureLimits("SUPPORT", 5, 20, 5, 200, 60),
}


@dataclass(frozen=True, slots=True)
class CallSettings:
    effort: Literal["low", "medium"]
    #: يتّسع للتفكير أيضاً: الجواب الظاهر بضع مئات من الرموز.
    max_tokens: int
    deadline_seconds: float
    stream: bool
    prompt_version: str


#: تُرفع عند أيّ تغييرٍ في نصّ التعليمات أو المخطّط أو الإعدادات.
REVIEW_PROMPT_VERSION = "rv-2026-10-09.1"
ASSISTANT_PROMPT_VERSION = "as-2026-10-09.1"

#: المراجِع: داخل ضغطة الاعتماد، فجهدٌ منخفض ومهلةٌ قصيرة. ينتظره الطلب
#: `REVIEW_WAIT_SECONDS` ثم يكمل في الخلفية حتى مهلته.
REVIEW = CallSettings("low", 3_000, 30.0, False, REVIEW_PROMPT_VERSION)
#: المساعد: الطلب كلّه ينتظره، بحالة انشغالٍ على زرّ «اسأل».
ASSISTANT = CallSettings("low", 3_000, 25.0, False, ASSISTANT_PROMPT_VERSION)
#: مسودات الدعم (الحزمة 4): أطول، فتُبثّ من جهة الخادم ويُفحص الوقت مع كل حدث.
#: نسخة تعليماتها في مواصفة الدعم.
DRAFT = CallSettings("medium", 8_000, 120.0, True, "support")

#: ما ينتظره طلب «راجع» قبل أن يجيب PENDING ويترك المراجعة تكمل. قيمة بدايةٍ
#: تُقاس لا تُحفظ: بوّابة الإصدار p90 ≤ 12 ثانية على التجهيزات.
REVIEW_WAIT_SECONDS = 12.0
#: مهلة القراءة بين حدثين في البثّ؛ أحداث ping تصل أثناء التفكير.
STREAM_TIMEOUT_SECONDS = 20.0

#: مقاعد الاستدعاء المتزامن للأدوات الجديدة في العملية الواحدة (الحملة لها مقاعدها).
AI_SLOTS = 8
#: القاطع: ثلاثة إخفاقاتٍ متتالية من المزوّد في دقيقتين تفتحه دقيقةً كاملة، فلا
#: تنتظر كل ضغطة «راجع» اثنتي عشرة ثانية لشيءٍ لن يأتي.
BREAKER_FAILURES = 3
BREAKER_WINDOW_SECONDS = 120.0
BREAKER_OPEN_SECONDS = 60.0

#: ما يكتبه النموذج ويُعرض: حدود الخادم أشدّ من حدود القاعدة (ew_ai_text_ok).
MAX_FLAGS = 3
REASON_LENGTH = (12, 160)
SUGGESTION_LENGTH = (8, 140)
ANSWER_LENGTH = (1, 320)
ANSWER_MAX_LINES = 6
#: سؤال المساعد بعد التوحيد والقصّ.
QUESTION_LENGTH = (3, 300)
READY_QUESTIONS_MAX = 3
#: بيانات الشاشة التي تُرسل مع السؤال: بنودٌ كاملة حتى هذا الحدّ، ثم سطر عدد.
SCREEN_DATA_CHARS = 3_000
#: مقالات قاعدة المعرفة في مسودة الدعم: مقالاتٌ كاملة حتى هذا الحدّ.
KB_CHARS = 12_000
#: الاقتباس الحرفي الذي تُثبت به المسودة مصدرها.
QUOTE_LENGTH = (8, 300)
