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

from eyework import clock, self_check
from eyework.copy_rules import CopyWarning, check_copy, check_note_to_user
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

#: مهلة القراءة لكل جولة. بجهد medium تستغرق الكتابة عادةً بين عشر ثوانٍ وستين.
_TIMEOUT = anthropic.Timeout(90.0, connect=5.0)
#: لا إعادة تلقائية في المكتبة: محاولةٌ انتهت مهلتها ربما فُوترت، وإعادتها
#: خفيةً تُخفي ذلك عن السقوف. المستخدم يعيد بنفسه حين يُقال له.
_MAX_RETRIES = 0
#: الجولات كلها (الكتابة ونتائج أداة الفحص) تنتهي قبل عقد المحاولة في القاعدة
#: (خمس دقائق) بهامشٍ يكفي لكتابة النسخة.
_DEADLINE_SECONDS = 200.0
#: الوجهة مكتوبةٌ هنا لا مقروءةٌ من البيئة: ANTHROPIC_BASE_URL في البيئة
#: يرسل الصورة إلى غير Anthropic. (`config` يرفض الإقلاع إن وُجد أصلاً.)
_BASE_URL = "https://api.anthropic.com"

#: ازدحامٌ مؤقّت: يُعاد المحاولة بعد قليل، ولا يُحسب في حدّ اليوم.
_BUSY = frozenset({429, 503, 529})
#: نتائج لا تُحسب في حدّ اليوم لأن الطلب لم يُعالَج. بعد جولةٍ عولجت فعلاً
#: لا تصحّ: الاستدعاء دُفع، فيُسجَّل OUTPUT_INVALID (يُحسب) لا هذه.
_UNBILLED = frozenset({"UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_ERROR"})


@dataclass(frozen=True, slots=True)
class CopyOutcome:
    outcome: Outcome
    title: str | None = None
    description: str | None = None
    warnings: tuple[CopyWarning, ...] = ()
    #: سبب عدم صلاحية الصورة، من `UNUSABLE_REASONS`.
    reason: str | None = None
    #: كلمة المساعد للمستخدم بعد فحصها، أو None. تُعرض ولا تُنشر.
    note: str | None = None
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


_FIELDS = {"status", "reason", "title", "description", "message_to_user"}


def _parse(request: CopyRequest, message, meta: dict) -> CopyOutcome:
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
    if not isinstance(data, dict) or set(data) != _FIELDS:
        return CopyOutcome("OUTPUT_INVALID", **meta)
    if not all(isinstance(data[key], str) for key in data):
        return CopyOutcome("OUTPUT_INVALID", **meta)

    # كلمة المساعد ثانوية: مخالفتها تُسقطها وحدها ولا تُسقط النصّ.
    note, note_errors = check_note_to_user(data["message_to_user"])
    if note_errors:
        logger.info("كلمةٌ مُسقطة: %s (طلب %s)", ",".join(note_errors), meta["request_id"])

    if data["status"] == "UNUSABLE_PHOTO":
        if data["reason"] not in UNUSABLE_REASONS:
            return CopyOutcome("OUTPUT_INVALID", **meta)
        return CopyOutcome("UNUSABLE_PHOTO", reason=data["reason"], note=note, **meta)
    if data["status"] != "OK":
        return CopyOutcome("OUTPUT_INVALID", **meta)

    title, description = self_check.keep_unchanged(request, data["title"], data["description"])
    check = check_copy(title, description)
    if not check.ok:
        logger.info("نصٌّ مرفوض: %s (طلب %s)", ",".join(check.errors), meta["request_id"])
        return CopyOutcome("OUTPUT_INVALID", **meta)
    return CopyOutcome("OK", title=check.title, description=check.description, warnings=check.warnings,
                       note=note, **meta)


def _failure(error: Exception) -> CopyOutcome:
    """خطأ المكتبة نتيجةً واحدة. ما لم يصل أو رُفض قبل المعالجة لا يُحسب."""
    if isinstance(error, anthropic.APITimeoutError):
        return CopyOutcome("UPSTREAM_TIMEOUT")
    if isinstance(error, anthropic.APIConnectionError):
        return CopyOutcome("UPSTREAM_UNREACHABLE", retry_after_seconds=30)
    if isinstance(error, anthropic.APIStatusError):
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
    raise error


class AnthropicCopywriter:
    """
    الكاتب الحقيقي. `client` يُحقن في اختبار الربط وحده.

    حلقةٌ قصيرة: النموذج يكتب، ويستدعي أداة الفحص الذاتي بما ينوي إرساله،
    فتعود إليه النتيجة، ثم يجيب. الجولات محدودة بعددٍ وبمهلةٍ كلّية، والرموز
    تُجمع من الجولات كلها لأنها كلها تُدفع.
    """

    def __init__(self, api_key: str, *, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key, base_url=_BASE_URL, timeout=_TIMEOUT, max_retries=_MAX_RETRIES
        )

    def write(self, request: CopyRequest) -> CopyOutcome:
        params = build_request(request)
        messages = list(params["messages"])
        started = clock.monotonic()
        meta = {"served_model": None, "request_id": None, "input_tokens": 0, "output_tokens": 0}
        processed = False

        for round_number in range(self_check.MAX_ROUNDS + 1):
            remaining = _DEADLINE_SECONDS - (clock.monotonic() - started)
            if remaining < 10:
                return CopyOutcome("UPSTREAM_TIMEOUT", **meta)
            try:
                message = self._client.beta.messages.create(
                    **{**params, "messages": messages},
                    timeout=anthropic.Timeout(min(90.0, remaining), connect=5.0),
                )
            except anthropic.APIError as error:
                outcome = _failure(error)
                if processed and outcome.outcome in _UNBILLED:
                    # جولةٌ سابقة عولجت ودُفعت؛ الفشل الآن لا يمحو ذلك.
                    return CopyOutcome("OUTPUT_INVALID", **meta)
                return outcome
            processed = True
            meta["served_model"] = getattr(message, "model", None)
            meta["request_id"] = getattr(message, "_request_id", None)
            usage = getattr(message, "usage", None)
            meta["input_tokens"] += (getattr(usage, "input_tokens", 0) or 0) + (
                getattr(usage, "cache_read_input_tokens", 0) or 0) + (
                getattr(usage, "cache_creation_input_tokens", 0) or 0)
            meta["output_tokens"] += getattr(usage, "output_tokens", 0) or 0

            if message.stop_reason != "tool_use":
                return _parse(request, message, meta)
            if round_number == self_check.MAX_ROUNDS:
                logger.info("جولات الفحص تجاوزت الحدّ (طلب %s)", meta["request_id"])
                return CopyOutcome("OUTPUT_INVALID", **meta)

            results = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                if block.name == self_check.TOOL_NAME:
                    content, is_error = self_check.run(block.input, request)
                else:
                    content, is_error = f"لا أداة باسم {block.name}.", True
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": content, "is_error": is_error})
            messages = [*messages, {"role": "assistant", "content": message.content},
                        {"role": "user", "content": results}]
        return CopyOutcome("OUTPUT_INVALID", **meta)
