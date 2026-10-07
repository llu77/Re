"""
كاتب النصّ — الحدّ الخارجي الوحيد
=================================
الوحدة الوحيدة في التطبيق التي تستورد `anthropic`، والوحيدة التي يغادر منها
شيءٌ إلى خارج بنيتنا. سؤال «ما الذي يُرسَل؟» جوابه هنا وفي `prompt.py`: صورة
المنتج بعد تنظيفها، ونصوص المنتج. لا هوية.

**الحقن لا المفتاح البيئي.** `create_app(copywriter=...)` يستقبل الكاتب،
فالاختبارات تحقن كاتباً مصطنعاً ولا يوجد في مسار الإنتاج مفتاحٌ يبدّل
السلوك. والمفتاح يُمرَّر صراحةً من `EYEWORK_ANTHROPIC_API_KEY`؛
`ANTHROPIC_API_KEY` لا يُقرأ أبداً.

**الترتيب في قراءة الاستجابة:** الرفض أولاً، ثم الاقتطاع، ثم JSON، ثم قواعد
النصّ. ونتيجةٌ واحدة من سبع، لكلٍّ رسالتها العربية في طبقة الويب.

لا يُسجَّل نصٌّ ولا صورة: معرّف الطلب لدى Anthropic يكفي للتتبّع.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic

from eyework.copy_rules import CopyWarning, EditPreset, check_copy
from eyework.prompt import UNUSABLE_REASONS, CopyRequest, build_request

__all__ = ["AnthropicCopywriter", "CopyOutcome", "Copywriter", "Outcome"]

logger = logging.getLogger("eyework.copywriter")

Outcome = Literal[
    "OK",
    "UNUSABLE_PHOTO",
    "REFUSED",
    "OUTPUT_INVALID",
    "UPSTREAM_BUSY",
    "UPSTREAM_UNREACHABLE",
    "UPSTREAM_TIMEOUT",
    "UPSTREAM_ERROR",
]

#: مهلة القراءة. بجهد medium تستغرق الكتابة عادةً بين عشر ثوانٍ وستين؛ ومع
#: إعادة محاولةٍ واحدة يبقى الأسوأ (نحو 185 ثانية) دون عقد المحاولة في القاعدة
#: (أربع دقائق)، فلا تنتهي المحاولة في القاعدة والطلب ما زال جارياً.
_TIMEOUT = anthropic.Timeout(90.0, connect=5.0)
_MAX_RETRIES = 1

#: ازدحامٌ مؤقّت: يُعاد المحاولة بعد قليل، ولا يُحسب في حدّ اليوم.
_BUSY = frozenset({429, 503, 529})


@dataclass(frozen=True, slots=True)
class CopyOutcome:
    outcome: Outcome
    title: str | None = None
    description: str | None = None
    warnings: tuple[CopyWarning, ...] = ()
    #: سبب عدم صلاحية الصورة، من `UNUSABLE_REASONS`.
    reason: str | None = None
    served_model: str | None = None
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_after_seconds: int | None = None


class Copywriter(Protocol):
    def write(self, request: CopyRequest) -> CopyOutcome: ...


def _retry_after(error: anthropic.APIStatusError) -> int | None:
    value = error.response.headers.get("retry-after") if error.response is not None else None
    try:
        return max(1, min(600, int(float(value)))) if value else None
    except ValueError:
        return None


def _keep_unchanged(request: CopyRequest, title: str, description: str) -> tuple[str, str]:
    """
    «عنوانٌ آخر فقط» يعني أن الوصف لا يتغيّر — حرفاً بحرف.

    لا يُطلب ذلك من النموذج ويُصدَّق: يُعاد الحقل الثابت من النسخة السابقة
    هنا، والقاعدة تتحقّق من تطابقه بقيدٍ في محفّز الإدراج.
    """
    if request.previous is not None:
        if EditPreset.NEW_TITLE in request.presets:
            description = request.previous.description
        if EditPreset.NEW_DESCRIPTION in request.presets:
            title = request.previous.title
    return title, description


def _parse(request: CopyRequest, message) -> CopyOutcome:
    meta = {
        "served_model": getattr(message, "model", None),
        "request_id": getattr(message, "_request_id", None),
        "input_tokens": getattr(message.usage, "input_tokens", None) if message.usage else None,
        "output_tokens": getattr(message.usage, "output_tokens", None) if message.usage else None,
    }
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        # الفئة وحدها: لا نصّ ولا صورة في السجلّ.
        logger.info("رفضٌ من فئة %s (طلب %s)", getattr(details, "category", None), meta["request_id"])
        return CopyOutcome("REFUSED", **meta)
    if message.stop_reason == "max_tokens":
        return CopyOutcome("OUTPUT_INVALID", **meta)

    text = next((block.text for block in message.content if block.type == "text"), None)
    try:
        data = json.loads(text) if text is not None else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or set(data) != {"status", "reason", "title", "description"}:
        return CopyOutcome("OUTPUT_INVALID", **meta)
    if not all(isinstance(data[key], str) for key in data):
        return CopyOutcome("OUTPUT_INVALID", **meta)

    if data["status"] == "UNUSABLE_PHOTO":
        if data["reason"] not in UNUSABLE_REASONS:
            return CopyOutcome("OUTPUT_INVALID", **meta)
        return CopyOutcome("UNUSABLE_PHOTO", reason=data["reason"], **meta)
    if data["status"] != "OK":
        return CopyOutcome("OUTPUT_INVALID", **meta)

    title, description = _keep_unchanged(request, data["title"], data["description"])
    check = check_copy(title, description)
    if not check.ok:
        logger.info("نصٌّ مرفوض: %s (طلب %s)", ",".join(check.errors), meta["request_id"])
        return CopyOutcome("OUTPUT_INVALID", **meta)
    return CopyOutcome("OK", title=check.title, description=check.description, warnings=check.warnings, **meta)


class AnthropicCopywriter:
    """الكاتب الحقيقي. `client` يُحقن في اختبار الربط وحده."""

    def __init__(self, api_key: str, *, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=_TIMEOUT, max_retries=_MAX_RETRIES
        )

    def write(self, request: CopyRequest) -> CopyOutcome:
        try:
            message = self._client.beta.messages.create(**build_request(request))
        except anthropic.APITimeoutError:
            return CopyOutcome("UPSTREAM_TIMEOUT")
        except anthropic.APIConnectionError:
            # لم يصل الطلب: لا فوترة، فلا يُحسب في حدّ اليوم.
            return CopyOutcome("UPSTREAM_UNREACHABLE", retry_after_seconds=30)
        except anthropic.RateLimitError as error:
            return CopyOutcome("UPSTREAM_BUSY", retry_after_seconds=_retry_after(error) or 30,
                               request_id=error.request_id)
        except anthropic.APIStatusError as error:
            status = error.status_code
            if status in _BUSY:
                return CopyOutcome("UPSTREAM_BUSY", retry_after_seconds=_retry_after(error) or 30,
                                   request_id=error.request_id)
            if status == 504:
                return CopyOutcome("UPSTREAM_TIMEOUT", request_id=error.request_id)
            if status >= 500:
                logger.error("خطأ لدى خدمة الكتابة: %s (طلب %s)", status, error.request_id)
                return CopyOutcome("UPSTREAM_ERROR", request_id=error.request_id)
            # 4xx: خللٌ في الإعداد أو في شكل الطلب، لا في الصورة. يُسجَّل معرّفه وحده.
            logger.critical("خدمة الكتابة رفضت الطلب: %s (طلب %s)", status, error.request_id)
            return CopyOutcome("UPSTREAM_ERROR", request_id=error.request_id)
        return _parse(request, message)
