"""
بوّابة النموذج — الحدّ الخارجي الوحيد
=====================================
الوحدة الوحيدة في التطبيق التي تستورد `anthropic`، والوحيدة التي يغادر منها
شيءٌ إلى خارج بنيتنا (اختبارٌ معماري يفرض ذلك). كانت هذه الحدود في
`copywriter.py`؛ انتقل منه إلى هنا كل ما يخصّ المزوّد — العميل، ووجهته
الثابتة، وتصنيف أخطائه، وعدّ رموزه — وبقيت له حلقته ونتائجه؛ وأُضيف مدخلٌ
واحد للأدوات الجديدة: `AnthropicGateway.call(ModelCall) -> ModelReply`.

**شكل الطلب ثابت.** النموذج `claude-opus-5-5` عبر `client.beta.messages`
بالبديل من جهة الخادم والمخرجات المنظّمة والجهد الصريح. لا `thinking`
(التفكير دائمٌ على هذا النموذج، وتحديده يعيد 400)، ولا أدوات ولا إجبار
(400 كذلك)، ولا معاملات عيّنة. `max_retries=0`: محاولةٌ انتهت مهلتها ربما
فُوتر، وإعادتها خفيةً تُخفي ذلك عن السقوف.

**البثّ من جهة الخادم وحده** للاستدعاءات الطويلة (مسودات الدعم): يُفحص الوقت
مع كل حدث، وبعد المهلة يُغلق الردّ وتُسجَّل مهلةٌ محسوبة. لا يصل العميل حرفٌ
قبل فحصه، ولا يتحرّك نصٌّ تحت نظرٍ مستقرّ.

**القاطع والمقاعد.** في انقطاع المزوّد تعود كل ضغطة «راجع» فوراً بـ«غير
متاح» بدل أن تنتظر اثنتي عشرة ثانية لشيءٍ لن يأتي؛ والمقاعد الثمانية تحدّ
الاستدعاءات المتزامنة في العملية الواحدة قبل أن يُفتح صفٌّ في الدفتر.

لا يُسجَّل نصٌّ: الأرقام ومعرّف الطلب لدى المزوّد وحدها، عبر `ai_log`.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from typing import NamedTuple

import anthropic

from eyework import ai_log, clock
from eyework.ai_limits import (
    AI_SLOTS,
    BREAKER_FAILURES,
    BREAKER_OPEN_SECONDS,
    BREAKER_WINDOW_SECONDS,
    STREAM_TIMEOUT_SECONDS,
)
from eyework.prompt_kit import Gateway, ModelCall, ModelReply

__all__ = [
    "BETAS",
    "MODEL",
    "APIError",
    "AnthropicGateway",
    "Breaker",
    "Failure",
    "Gateway",
    "Guard",
    "ModelCall",
    "ModelReply",
    "Timeout",
    "failure_outcome",
    "new_client",
    "token_counts",
]

MODEL = "claude-opus-5-5"
#: البديل الآمن من جهة الخادم: طلبٌ ترفضه مصنّفات النموذج يُعاد على النموذج
#: الذي توصي به Anthropic بدل أن يعود رفضاً.
BETAS = ("server-side-fallback-2026-07-01",)
Timeout = anthropic.Timeout
APIError = anthropic.APIError

#: الوجهة مكتوبةٌ هنا لا مقروءةٌ من البيئة: ANTHROPIC_BASE_URL في البيئة
#: يرسل الصورة إلى غير Anthropic. (`config` يرفض الإقلاع إن وُجد أصلاً.)
_BASE_URL = "https://api.anthropic.com"
#: لا إعادة تلقائية في المكتبة: محاولةٌ انتهت مهلتها ربما فُوتر، وإعادتها
#: خفيةً تُخفي ذلك عن السقوف. المستخدم يعيد بنفسه حين يُقال له.
_MAX_RETRIES = 0
#: مهلة الاتصال: ثلاث ثوانٍ تكفي لفتح القناة؛ ما بعدها مهلة القراءة لكل أداة.
_CONNECT_SECONDS = 3.0

#: ازدحامٌ مؤقّت: يُعاد المحاولة بعد قليل، ولا يُحسب في حدّ اليوم.
_BUSY = frozenset({429, 503, 529})
#: نتائج لا تُحسب في حدّ اليوم لأن الطلب لم يُعالَج. بعد جولةٍ عولجت فعلاً
#: لا تصحّ: الاستدعاء دُفع، فيُسجَّل OUTPUT_INVALID (يُحسب) لا هذه.
_UNBILLED = frozenset({"UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_ERROR"})
#: ما يعدّه القاطع إخفاقاً من المزوّد. خطأ 4xx خللٌ في طلبنا لا في المزوّد، فلا يُعدّ.
_TRIPPING = frozenset({"UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_TIMEOUT", "UPSTREAM_ERROR"})


def new_client(api_key: str, *, timeout: anthropic.Timeout) -> anthropic.Anthropic:
    """العميل كما يُبنى في الإنتاج: وجهةٌ ثابتة، وبلا إعادة، ومفتاحٌ صريح."""
    return anthropic.Anthropic(api_key=api_key, base_url=_BASE_URL, timeout=timeout, max_retries=_MAX_RETRIES)


def _retry_after(error: anthropic.APIStatusError) -> int | None:
    value = error.response.headers.get("retry-after") if error.response is not None else None
    try:
        return max(1, min(600, int(float(value)))) if value else None
    except ValueError:
        return None


def token_counts(usage) -> dict[str, int]:
    """
    رموز الجولة كلها بأنواعها. بعد رفضٍ وبديل تحمل `usage.iterations` كل
    محاولة — ومنها محاولة النموذج الذي رفض، وتُدفع — والأرقام العليا للبديل وحده.
    """
    def count(item) -> dict[str, int]:
        def get(name):
            return getattr(item, name, None) or 0
        return {"input": get("input_tokens"), "cache_read": get("cache_read_input_tokens"),
                "cache_write": get("cache_creation_input_tokens"), "output": get("output_tokens")}

    totals = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "thinking_tokens": 0}
    if usage is None:
        return totals
    iterations = getattr(usage, "iterations", None) or []
    for item in iterations or [usage]:
        for key, value in count(item).items():
            totals[key] += value
    details = getattr(usage, "output_tokens_details", None)
    totals["thinking_tokens"] = getattr(details, "thinking_tokens", None) or 0
    return totals


def _tokens(usage) -> tuple[int, int]:
    """(ما دخل بكل أنواعه، وما خرج) — ما يعدّه كاتب النصّ."""
    counts = token_counts(usage)
    return counts["input"] + counts["cache_read"] + counts["cache_write"], counts["output"]


class Failure(NamedTuple):
    outcome: str
    retry_after_seconds: int | None
    request_id: str | None
    status: int | None


def failure_outcome(error: Exception) -> Failure:
    """
    خطأ المكتبة نتيجةً واحدة. ما لم يصل أو رُفض قبل المعالجة لا يُحسب.
    ما ليس خطأ المكتبة يُرفع كما هو: ليس ممّا نعرف كيف نصنّفه.
    """
    if isinstance(error, anthropic.APITimeoutError):
        return Failure("UPSTREAM_TIMEOUT", None, None, None)
    if isinstance(error, anthropic.APIConnectionError):
        return Failure("UPSTREAM_UNREACHABLE", 30, None, None)
    if isinstance(error, anthropic.APIStatusError):
        status = error.status_code
        if status in _BUSY:
            return Failure("UPSTREAM_BUSY", _retry_after(error) or 30, error.request_id, status)
        if status == 504:
            return Failure("UPSTREAM_TIMEOUT", None, error.request_id, status)
        if status >= 500:
            ai_log.event("upstream_error", level="error", status=status, api_request_id=error.request_id)
            return Failure("UPSTREAM_ERROR", None, error.request_id, status)
        # 4xx: خللٌ في الإعداد أو في شكل الطلب — ومنه بلوغ حدّ الإنفاق في مساحة
        # العمل — لا في المحتوى. يُسجَّل معرّفه وحده.
        ai_log.event("upstream_rejected", level="critical", status=status, api_request_id=error.request_id)
        return Failure("UPSTREAM_ERROR", None, error.request_id, status)
    raise error


def _usage(message, request: ModelCall, request_id: str | None) -> tuple[dict, int]:
    """مفاتيح `ew_ai_request_settle` السبعة، ورموز التفكير للسجلّ."""
    counts = token_counts(getattr(message, "usage", None))
    usage = {
        "input": counts["input"], "output": counts["output"],
        "cache_read": counts["cache_read"], "cache_write": counts["cache_write"],
        "model": getattr(message, "model", None), "prompt_version": request.prompt_version,
        "api_request_id": request_id,
    }
    return usage, counts["thinking_tokens"]


def _read(message, request: ModelCall, request_id: str | None) -> ModelReply:
    """ترتيب الكاتب: الرفض أولاً، ثم الاقتطاع، ثم JSON. فحص الأداة بعد ذلك عند صاحبها."""
    usage, thinking = _usage(message, request, request_id)
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        # نموذج البديل كان مشغولاً فعاد الرفض كما هو: المحاولة لاحقاً قد تنجح.
        retry = 30 if getattr(details, "recommended_model", None) else None
        return ModelReply("REFUSED", None, usage, "refusal", getattr(details, "category", None), True, retry,
                          thinking_tokens=thinking)
    if message.stop_reason == "max_tokens":
        return ModelReply("OUTPUT_INVALID", None, usage, "max_tokens", None, True, None, thinking_tokens=thinking)
    text = next((block.text for block in message.content if block.type == "text"), None)
    try:
        parsed = json.loads(text) if text is not None else None
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return ModelReply("OUTPUT_INVALID", None, usage, message.stop_reason, None, True, None,
                          thinking_tokens=thinking)
    return ModelReply("OK", parsed, usage, message.stop_reason, None, True, None, thinking_tokens=thinking)


class AnthropicGateway:
    """البوّابة الحقيقية. `client` يُحقن في اختبار الربط وحده."""

    def __init__(self, api_key: str, *, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or new_client(api_key, timeout=Timeout(STREAM_TIMEOUT_SECONDS, connect=_CONNECT_SECONDS))

    @staticmethod
    def params(request: ModelCall) -> dict:
        """جسم الطلب كما يغادر. ما ليس هنا لا يُرسل."""
        return {
            "model": MODEL,
            "max_tokens": request.max_tokens,
            "betas": list(BETAS),
            "fallbacks": "default",
            "output_config": {"effort": request.effort, "format": {"type": "json_schema", "schema": request.schema}},
            "system": list(request.system),
            "messages": [{"role": "user", "content": request.user}],
        }

    def _stream(self, params: dict, deadline: float):
        """
        يقرأ الأحداث ويفحص الوقت مع كل حدث؛ أحداث ping تصل أثناء التفكير فلا تنقطع
        القراءة. بعد المهلة يخرج من السياق فيُغلق الردّ، ويُعيد ما عُرف من الرسالة
        حتى الآن (رموز الدخل تُعرف من أول حدث) ليُحسب.
        """
        started = clock.monotonic()
        with self._client.beta.messages.stream(
            **params, timeout=Timeout(STREAM_TIMEOUT_SECONDS, connect=_CONNECT_SECONDS),
        ) as stream:
            for _event in stream:
                if clock.monotonic() - started > deadline:
                    try:
                        snapshot = stream.current_message_snapshot
                    except AssertionError:
                        snapshot = None
                    return snapshot, True, stream.request_id
            return stream.get_final_message(), False, stream.request_id

    def call(self, request: ModelCall) -> ModelReply:
        params = self.params(request)
        started = clock.monotonic()
        try:
            if request.stream:
                message, timed_out, request_id = self._stream(params, request.deadline_seconds)
            else:
                message = self._client.beta.messages.create(
                    **params, timeout=Timeout(request.deadline_seconds, connect=_CONNECT_SECONDS),
                )
                timed_out, request_id = False, getattr(message, "_request_id", None)
        except anthropic.APIError as error:
            failure = failure_outcome(error)
            # لا أرقام: لم تصل رسالة. النسخة ومعرّف الطلب إن عُرف.
            usage = {"prompt_version": request.prompt_version, "api_request_id": failure.request_id}
            reply = ModelReply(failure.outcome, None, usage, None, None, failure.outcome not in _UNBILLED,
                               failure.retry_after_seconds, failure.status)
        else:
            if timed_out:
                usage, thinking = _usage(message, request, request_id)
                reply = ModelReply("UPSTREAM_TIMEOUT", None, usage, None, None, True, None, thinking_tokens=thinking)
            else:
                reply = _read(message, request, request_id)
        ai_log.event(
            "model_call", feature=request.feature, outcome=reply.outcome, prompt_version=request.prompt_version,
            served_model=reply.usage.get("model"), api_request_id=reply.usage.get("api_request_id"),
            input_tokens=reply.usage.get("input"), output_tokens=reply.usage.get("output"),
            cache_read=reply.usage.get("cache_read"), cache_write=reply.usage.get("cache_write"),
            thinking_tokens=reply.thinking_tokens, stop_reason=reply.stop_reason,
            refusal_category=reply.refusal_category, status=reply.status,
            latency_ms=int((clock.monotonic() - started) * 1000),
        )
        return reply


class Breaker:
    """
    قاطع دارةٍ واحد لكل عملية. يفتح بعد `failures` إخفاقاتٍ متتالية من المزوّد
    في `window_seconds`، ويبقى مفتوحاً `open_seconds`؛ ثم يسمح باستدعاءٍ واحد
    تجريبي: نجاحه يغلقه، وفشله يفتحه من جديد. نجاحٌ في أيّ وقتٍ يغلقه.

    إذن التجربة يُعاد إن لم يُستدعَ به شيء (`cancel_trial`: مراجعةٌ مخزونة، أو سقفٌ،
    أو لا مقعد)، وإلا فإذنٌ لم يُستعمل يُبطل العمل حتى إعادة التشغيل. وإن ضاع
    الإذن رغم ذلك عاد بعد مدّة فتحٍ أخرى.
    """

    def __init__(self, *, failures: int = BREAKER_FAILURES, window_seconds: float = BREAKER_WINDOW_SECONDS,
                 open_seconds: float = BREAKER_OPEN_SECONDS) -> None:
        self._failures = failures
        self._window = window_seconds
        self._open_seconds = open_seconds
        self._lock = threading.Lock()
        self._recent: deque[float] = deque()
        self._opened_at: float | None = None
        self._trialing = False
        self._trial_at: float | None = None

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._opened_at is not None

    def allow(self) -> bool:
        now = clock.monotonic()
        with self._lock:
            if self._opened_at is None:
                return True
            if now - self._opened_at < self._open_seconds:
                return False
            # تجربةٌ واحدة في كل مدّة فتح: إذنٌ قائم لم يُسجَّل له شيء يُجدَّد بعد مدّة فتحٍ أخرى.
            if not self._trialing or now - (self._trial_at or now) >= self._open_seconds:
                self._trialing = True
                self._trial_at = now
                return True
            return False

    def cancel_trial(self) -> None:
        """إذن تجربةٍ أُخذ ولم يُستدعَ به شيء يعود، فتأخذه الضغطة التالية."""
        with self._lock:
            if self._opened_at is not None and self._trialing:
                self._trialing = False
                self._trial_at = None

    def record(self, reply: ModelReply) -> None:
        failed = reply.outcome in _TRIPPING and not (
            reply.outcome == "UPSTREAM_ERROR" and reply.status is not None and reply.status < 500)
        now = clock.monotonic()
        with self._lock:
            if not failed:
                self._recent.clear()
                self._opened_at = None
                self._trialing = False
                return
            if self._opened_at is not None:
                # فشل الاستدعاء التجريبي: يبقى مفتوحاً مدّةً كاملة أخرى. وفشلُ استدعاءٍ بدأ
                # قبل الفتح لا يمدّه: المدّة ستّون ثانية من الفتح لا من آخر فشلٍ يصل.
                if self._trialing:
                    self._opened_at = now
                    self._trialing = False
                    self._trial_at = None
                return
            self._recent.append(now)
            while self._recent and self._recent[0] <= now - self._window:
                self._recent.popleft()
            if len(self._recent) >= self._failures:
                self._opened_at = now
                self._recent.clear()

    def reset(self) -> None:
        with self._lock:
            self._recent.clear()
            self._opened_at = None
            self._trialing = False
            self._trial_at = None


class Guard:
    """
    ما يُفحص قبل أن يُفتح صفٌّ في الدفتر: القاطع ثم مقعدٌ من المقاعد. المقعد
    يُحجز قبل الفتح فلا يُحسب استدعاءٌ لم يبدأ، ويُعاد حين ينتهي الاستدعاء.
    """

    def __init__(self, *, slots: int = AI_SLOTS, breaker: Breaker | None = None) -> None:
        self.breaker = breaker or Breaker()
        self._slots = threading.BoundedSemaphore(slots)

    def acquire(self) -> str | None:
        """None ومقعدٌ محجوز، أو سبب الامتناع: DOWN (القاطع مفتوح) أو BUSY (لا مقعد)."""
        if not self.breaker.allow():
            return "DOWN"
        if not self._slots.acquire(blocking=False):
            # إذنٌ بلا مقعد: يعود إلى القاطع فلا تضيع التجربة على ضغطةٍ لم تستدعِ شيئاً.
            self.breaker.cancel_trial()
            return "BUSY"
        return None

    def release(self, *, called: bool = True) -> None:
        """يعيد المقعد؛ و`called=False` حين لم يصل الاستدعاء إلى المزوّد فيعود إذن التجربة معه."""
        self._slots.release()
        if not called:
            self.breaker.cancel_trial()

    def record(self, reply: ModelReply) -> None:
        self.breaker.record(reply)
