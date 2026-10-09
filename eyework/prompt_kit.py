"""
عدّة المطالبات
==============
ما تشترك فيه كل الأدوات التي تخاطب النموذج: الطلب الواحد (`ModelCall`)،
والجواب الواحد (`ModelReply`)، وبناء كتل التعليمات، وتحييد النصّ الذي يُدرج
بين وسمين.

**الثابت قبل المتغيّر.** كتلتا التعليمات ثابتتان لكل أداة (أو لكل مهنة في
المساعد)، وتنتهيان بنقطة تخزينٍ مؤقّت واحدة؛ وكل ما يخصّ الطلب يأتي بعدها في
رسالة المستخدم. فالبادئة المخزّنة لدى المزوّد لا تحمل بيانات مستخدمٍ قطّ،
وتُقرأ مشتركةً بين كل المستخدمين.

**النصّ بيانات لا تعليمات.** `data()` تُدرج نصّاً أدخله الموظف أو وصله من غيره
بين وسمين لا يستطيع إغلاقهما: الأقواس الزاويّة تُستبدل بنظائرها الطباعية.
كانت `prompt._data` ونُقلت هنا لتخدم كل الأدوات.

وحدةٌ نقية: لا تستورد مكتبة النموذج ولا القاعدة. `model_gateway` وحده يرسل.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

__all__ = [
    "OUTCOMES",
    "Gateway",
    "ModelCall",
    "ModelReply",
    "Outcome",
    "data",
    "system_blocks",
    "tag",
]

Outcome = Literal[
    "OK",
    "REFUSED",
    "OUTPUT_INVALID",
    "UPSTREAM_BUSY",
    "UPSTREAM_UNREACHABLE",
    "UPSTREAM_TIMEOUT",
    "UPSTREAM_ERROR",
]
OUTCOMES: tuple[str, ...] = (
    "OK", "REFUSED", "OUTPUT_INVALID", "UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_TIMEOUT",
    "UPSTREAM_ERROR",
)


def data(text: str) -> str:
    """
    نصٌّ يُدرج بين وسمين لا يستطيع أن يغلقهما.

    الأقواس الزاويّة تُستبدل بنظائرها الطباعية، فـ«‹/subject›» لا يُنهي الوسم
    ولا يفتح غيره. ما سواها يبقى كما كتبه صاحبه.
    """
    return text.replace("<", "‹").replace(">", "›")


def tag(element: str, body: str, **attributes: str) -> str:
    """وسمٌ باسمٍ ثابت من الشيفرة، وقيم سماته بعد `data()`. المحتوى كما يُعطى: من يمرّره يحيّده."""
    rendered = "".join(f' {key}="{data(value)}"' for key, value in attributes.items())
    return f"<{element}{rendered}>{body}</{element}>"


def system_blocks(static: str, per_feature: str) -> tuple[dict, ...]:
    """
    كتلتا التعليمات: الثابتة لكل الأدوات، ثم كتلة الأداة (أو المهنة) وعليها
    نقطة التخزين المؤقّت. معاً تتجاوزان الحدّ الأدنى للتخزين (512 رمزاً)،
    وهما واحدتان لكل المستخدمين فلا تحملان بيانات أحد.
    """
    return (
        {"type": "text", "text": static},
        {"type": "text", "text": per_feature, "cache_control": {"type": "ephemeral"}},
    )


@dataclass(frozen=True, slots=True)
class ModelCall:
    """طلبٌ واحد للنموذج كما تبنيه أداةٌ نقية. لا حقل فيه يخصّ صاحب الطلب."""

    #: رمز الأداة في `ai_features`.
    feature: str
    #: كتل التعليمات؛ الأخيرة الثابتة تحمل `cache_control`.
    system: tuple[dict, ...]
    #: ما يخصّ هذا الطلب، بعد `data()`.
    user: str
    #: مخطّط المخرجات المنظّمة. بلا بيانات مستخدم: يُخزَّن لدى المزوّد 24 ساعة.
    schema: dict
    effort: Literal["low", "medium"]
    max_tokens: int
    deadline_seconds: float
    #: بثٌّ من جهة الخادم وحده؛ لا يصل العميل شيءٌ قبل فحصه.
    stream: bool
    #: نسخة التعليمات، تُحفظ في الدفتر مع كل استدعاء.
    prompt_version: str


@dataclass(frozen=True, slots=True)
class ModelReply:
    """جواب النموذج بعد قراءته بترتيب الكاتب: الرفض، ثم الاقتطاع، ثم JSON."""

    outcome: Outcome
    #: الكائن المقروء حين تكون النتيجة OK.
    data: dict | None
    #: مفاتيح `ew_ai_request_settle` السبعة بالضبط: input, output, cache_read,
    #: cache_write, model, prompt_version, api_request_id.
    usage: dict
    stop_reason: str | None
    refusal_category: str | None
    #: عالجه المزوّد (يُحسب ولو فشل).
    processed: bool
    retry_after_seconds: int | None
    #: حالة HTTP حين يكون الخطأ من المزوّد؛ القاطع يعدّ 5xx لا 4xx.
    status: int | None = None
    #: رموز التفكير، للسجلّ وحده.
    thinking_tokens: int | None = None


class Gateway(Protocol):
    def call(self, request: ModelCall) -> ModelReply: ...
