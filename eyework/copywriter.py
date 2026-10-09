"""
كاتب النصّ
==========
الكاتب الوحيد لنصّ الحملة: صورة المنتج بعد تنظيفها، ونصوص المنتج. لا هوية.
سؤال «ما الذي يُرسَل؟» جوابه هنا وفي `prompt.py`؛ أما الحدّ الخارجي نفسه —
العميل، ووجهته الثابتة، وتصنيف أخطاء المزوّد، وعدّ الرموز — ففي
`model_gateway.py`، الوحدة الوحيدة التي تستورد `anthropic`، ويستوردها الكاتب
من هناك ويبقي حلقته ونتائجه كما هي.

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
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

from eyework import clock, self_check
from eyework.copy_rules import CopyWarning, check_copy, check_note_to_user
from eyework.model_gateway import _UNBILLED, APIError, Timeout, _tokens, failure_outcome, new_client
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
_TIMEOUT = Timeout(90.0, connect=5.0)
#: الجولات كلها (الكتابة ونتائج أداة الفحص) تنتهي قبل عقد المحاولة في القاعدة
#: (خمس دقائق) بهامشٍ يكفي لكتابة النسخة.
_DEADLINE_SECONDS = 200.0


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


_FIELDS = {"status", "reason", "title", "description", "message_to_user"}


def _parse(request: CopyRequest, message, meta: dict) -> CopyOutcome:
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        # الفئة وحدها: لا نصّ ولا صورة في السجلّ.
        logger.info("رفضٌ من فئة %s (طلب %s)", getattr(details, "category", None), meta["request_id"])
        # نموذج البديل كان مشغولاً فعاد الرفض كما هو: المحاولة لاحقاً قد تنجح.
        retry = 30 if getattr(details, "recommended_model", None) else None
        return CopyOutcome("REFUSED", retry_after_seconds=retry, **meta)
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


#: ما يُسقط قبل آخر كتلة `fallback` حين يُعاد دور المساعد (وثائق Anthropic،
#: «Refusals and fallback»، Continuing the conversation). في الطلبات غير
#: المتدفّقة تأتي الكتلة أولاً فلا يسقط شيء؛ والقاعدة مكتوبةٌ كاملةً لتبقى صحيحة.
_DROP_BEFORE_FALLBACK = frozenset({"thinking", "redacted_thinking", "connector_text", "tool_use"})


def _echo(content) -> list:
    """محتوى دور المساعد كما يُعاد في الطلب التالي."""
    blocks = list(content)
    last = max((index for index, block in enumerate(blocks) if block.type == "fallback"), default=-1)
    return [block for index, block in enumerate(blocks)
            if index > last or block.type not in _DROP_BEFORE_FALLBACK]


def _failure(error: Exception) -> CopyOutcome:
    """خطأ المكتبة نتيجةً واحدة، كما تصنّفه البوّابة. ما لم يصل أو رُفض قبل المعالجة لا يُحسب."""
    outcome, retry_after, request_id, _ = failure_outcome(error)
    return CopyOutcome(outcome, retry_after_seconds=retry_after, request_id=request_id)


class AnthropicCopywriter:
    """
    الكاتب الحقيقي. `client` يُحقن في اختبار الربط وحده.

    حلقةٌ قصيرة: النموذج يكتب، ويستدعي أداة الفحص الذاتي بما ينوي إرساله،
    فتعود إليه النتيجة، ثم يجيب. الجولات محدودة بعددٍ وبمهلةٍ كلّية، والرموز
    تُجمع من الجولات كلها لأنها كلها تُدفع.
    """

    def __init__(self, api_key: str, *, client: Any = None) -> None:
        self._client = client or new_client(api_key, timeout=_TIMEOUT)

    def write(self, request: CopyRequest) -> CopyOutcome:
        params = build_request(request)
        messages = list(params["messages"])
        started = clock.monotonic()
        meta = {"served_model": None, "request_id": None, "input_tokens": 0, "output_tokens": 0}
        processed = False

        # جولات الأداة، ثم جولةٌ أخيرة بلا أدوات (tool_choice: none) إن بقي
        # النموذج يفحص: جوابٌ يُفحص في الشيفرة خيرٌ من استدعاءٍ مدفوع يُرمى.
        for round_number in range(self_check.MAX_ROUNDS + 1):
            remaining = _DEADLINE_SECONDS - (clock.monotonic() - started)
            if remaining < 10:
                return CopyOutcome("UPSTREAM_TIMEOUT", **meta)
            final = round_number == self_check.MAX_ROUNDS
            request_params = {**params, "messages": messages}
            if final:
                request_params["tool_choice"] = {"type": "none"}
            try:
                message = self._client.beta.messages.create(
                    **request_params,
                    timeout=Timeout(min(90.0, remaining), connect=5.0),
                )
            except APIError as error:
                outcome = _failure(error)
                if not processed:
                    return outcome
                # جولةٌ سابقة عولجت ودُفعت؛ الفشل الآن لا يمحو ذلك: تبقى رموزها
                # ونموذجها معها، ولا تصير نتيجةً «غير محسوبة».
                if outcome.outcome in _UNBILLED:
                    return CopyOutcome("OUTPUT_INVALID", **meta)
                return replace(outcome, served_model=meta["served_model"], input_tokens=meta["input_tokens"],
                               output_tokens=meta["output_tokens"],
                               request_id=outcome.request_id or meta["request_id"])
            processed = True
            meta["served_model"] = getattr(message, "model", None)
            meta["request_id"] = getattr(message, "_request_id", None)
            tokens_in, tokens_out = _tokens(getattr(message, "usage", None))
            meta["input_tokens"] += tokens_in
            meta["output_tokens"] += tokens_out

            if message.stop_reason != "tool_use":
                return _parse(request, message, meta)
            if final:
                logger.info("أداةٌ بعد منعها (طلب %s)", meta["request_id"])
                return CopyOutcome("OUTPUT_INVALID", **meta)

            # النتائج لما يُعاد من الدور وحده: استدعاءٌ أسقطه `_echo` بلا نتيجة،
            # وإلا رفضت الواجهة نتيجةً لا استدعاء لها في الدور السابق (400).
            echoed = _echo(message.content)
            results = []
            for block in echoed:
                if block.type != "tool_use":
                    continue
                if block.name == self_check.TOOL_NAME:
                    content, is_error = self_check.run(block.input, request)
                else:
                    content, is_error = f"لا أداة باسم {block.name}.", True
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": content, "is_error": is_error})
            messages = [*messages, {"role": "assistant", "content": echoed},
                        {"role": "user", "content": results}]
        return CopyOutcome("OUTPUT_INVALID", **meta)
