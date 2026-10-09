"""
بوّابة النموذج عبر نقلٍ مصطنع
=============================
البوّابة الحقيقية نفسها، والمكتبة نفسها، ونقل HTTP مصطنع بدل الشبكة: يُثبت شكل
الطلب حرفاً حرفاً (ما ليس فيه لا يغادر)، وترتيب قراءة الجواب، وتصنيف كل خطأ
مع محسوبيته، وعدّ الرموز عبر محاولات البديل، ومهلة البثّ على الساعة المحقونة،
والقاطع والمقاعد.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from eyework import clock
from eyework.model_gateway import (
    AnthropicGateway,
    Breaker,
    Guard,
    ModelCall,
    ModelReply,
    failure_outcome,
    new_client,
    token_counts,
)
from eyework.prompt_kit import system_blocks

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["flags"],
          "properties": {"flags": {"type": "array", "items": {"type": "string"}}}}


def _call(**overrides) -> ModelCall:
    fields = dict(feature="STOCK_REVIEW", system=system_blocks("ثابت " * 200, "<checks/>"), user="<subject/>",
                  schema=SCHEMA, effort="low", max_tokens=3000, deadline_seconds=30.0, stream=False,
                  prompt_version="rv-test")
    fields.update(overrides)
    return ModelCall(**fields)


def _gateway(handler) -> AnthropicGateway:
    client = anthropic.Anthropic(
        api_key="test-key", max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(handler)),
    )
    return AnthropicGateway("unused", client=client)


def _message(text, stop_reason="end_turn", *, usage=None, stop_details=None, model="claude-opus-5-5"):
    def handler(request: httpx.Request) -> httpx.Response:
        handler.seen = request
        body = {
            "id": "msg_1", "type": "message", "role": "assistant", "model": model,
            "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": usage or {"input_tokens": 1200, "output_tokens": 300, "cache_read_input_tokens": 900,
                               "cache_creation_input_tokens": 0, "output_tokens_details": {"thinking_tokens": 250}},
        }
        if stop_details is not None:
            body["stop_details"] = stop_details
        return httpx.Response(200, headers={"request-id": "req_ok"}, json=body)
    return handler


def _error(status, headers=None):
    def handler(request):
        return httpx.Response(status, headers={"request-id": "req_err", **(headers or {})},
                              json={"type": "error", "error": {"type": "x", "message": "m"}})
    return handler


# ── شكل الطلب ───────────────────────────────────────────────────────────
def test_the_request_body_is_exactly_the_documented_shape():
    handler = _message(json.dumps({"flags": []}))
    call = _call()
    _gateway(handler).call(call)
    sent = json.loads(handler.seen.content)
    assert sent["model"] == "claude-opus-5-5"
    assert sent["fallbacks"] == "default"
    assert sent["max_tokens"] == 3000
    assert sent["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert sent["system"] == list(call.system)
    assert sent["messages"] == [{"role": "user", "content": "<subject/>"}]
    assert handler.seen.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    for absent in ("thinking", "tools", "tool_choice", "temperature", "top_p", "top_k", "metadata", "stop_sequences"):
        assert absent not in sent, absent
    # المهلة لكل أداة: القراءة بمهلة الأداة والاتصال بثلاث ثوانٍ.
    timeout = handler.seen.extensions["timeout"]
    assert (timeout["read"], timeout["connect"]) == (30.0, 3.0)


def test_the_destination_retries_and_key_are_fixed_in_code(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "platform-key")
    gateway = AnthropicGateway("eyework-key")
    assert str(gateway._client.base_url).rstrip("/") == "https://api.anthropic.com"
    assert gateway._client.max_retries == 0
    assert gateway._client.api_key == "eyework-key"
    assert new_client("k", timeout=anthropic.Timeout(1.0, connect=1.0)).max_retries == 0


# ── قراءة الجواب بترتيبه ───────────────────────────────────────────────
def test_a_successful_reply_carries_the_parsed_object_and_the_ledger_usage():
    reply = _gateway(_message(json.dumps({"flags": ["x"]}))).call(_call())
    assert reply.outcome == "OK" and reply.data == {"flags": ["x"]} and reply.processed
    assert reply.usage == {"input": 1200, "output": 300, "cache_read": 900, "cache_write": 0,
                           "model": "claude-opus-5-5", "prompt_version": "rv-test", "api_request_id": "req_ok"}
    assert reply.thinking_tokens == 250 and reply.stop_reason == "end_turn"


def test_a_refusal_is_read_before_the_content_and_marked_retryable_when_the_fallback_was_busy():
    plain = _gateway(_message(json.dumps({"flags": []}), "refusal",
                              stop_details={"type": "refusal", "category": "cyber"})).call(_call())
    assert (plain.outcome, plain.refusal_category, plain.retry_after_seconds, plain.processed) == (
        "REFUSED", "cyber", None, True)
    busy = _gateway(_message("", "refusal", stop_details={
        "type": "refusal", "category": "cyber", "recommended_model": "claude-opus-4-8"})).call(_call())
    assert (busy.outcome, busy.retry_after_seconds) == ("REFUSED", 30)


@pytest.mark.parametrize(("text", "stop_reason"), [
    ('{"flags": [', "max_tokens"),
    ("ليس JSON", "end_turn"),
    ("[1, 2]", "end_turn"),
    ('"نصّ"', "end_turn"),
])
def test_truncated_or_non_object_output_is_invalid_and_billable(text, stop_reason):
    reply = _gateway(_message(text, stop_reason)).call(_call())
    assert reply.outcome == "OUTPUT_INVALID" and reply.processed and reply.data is None


# ── تصنيف الأخطاء ──────────────────────────────────────────────────────
@pytest.mark.parametrize(("handler", "outcome", "retry_after", "processed", "status"), [
    pytest.param(_error(429, {"retry-after": "12"}), "UPSTREAM_BUSY", 12, False, 429, id="429"),
    pytest.param(_error(503), "UPSTREAM_BUSY", 30, False, 503, id="503"),
    pytest.param(_error(529), "UPSTREAM_BUSY", 30, False, 529, id="529"),
    pytest.param(_error(504), "UPSTREAM_TIMEOUT", None, True, 504, id="504"),
    pytest.param(_error(500), "UPSTREAM_ERROR", None, False, 500, id="500"),
    pytest.param(_error(400), "UPSTREAM_ERROR", None, False, 400, id="400-spend-limit"),
    pytest.param(_error(401), "UPSTREAM_ERROR", None, False, 401, id="401"),
])
def test_http_errors_map_to_outcomes_with_their_billability(handler, outcome, retry_after, processed, status):
    reply = _gateway(handler).call(_call())
    assert (reply.outcome, reply.retry_after_seconds, reply.processed, reply.status) == (
        outcome, retry_after, processed, status)
    assert reply.usage["api_request_id"] == "req_err" and "input" not in reply.usage


def test_timeout_and_connection_errors():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("down", request=request)

    slow = _gateway(timeout).call(_call())
    assert (slow.outcome, slow.processed) == ("UPSTREAM_TIMEOUT", True)
    down = _gateway(refused).call(_call())
    assert (down.outcome, down.processed, down.retry_after_seconds) == ("UPSTREAM_UNREACHABLE", False, 30)


def test_an_unknown_exception_is_not_classified_but_raised():
    with pytest.raises(RuntimeError):
        failure_outcome(RuntimeError("bug"))


# ── الرموز ──────────────────────────────────────────────────────────────
def test_tokens_are_summed_across_the_iterations_of_a_fallback():
    usage = {"input_tokens": 1500, "output_tokens": 400, "iterations": [
        {"type": "message", "model": "claude-opus-5-5", "input_tokens": 1500, "output_tokens": 900,
         "cache_read_input_tokens": 100},
        {"type": "fallback_message", "model": "claude-opus-4-8", "input_tokens": 1500, "output_tokens": 400},
    ]}
    reply = _gateway(_message(json.dumps({"flags": []}), usage=usage, model="claude-opus-4-8")).call(_call())
    assert reply.usage["input"] == 3000 and reply.usage["output"] == 1300 and reply.usage["cache_read"] == 100
    assert reply.usage["model"] == "claude-opus-4-8"


def test_token_counts_tolerate_a_missing_usage():
    assert token_counts(None) == {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "thinking_tokens": 0}


# ── البثّ ───────────────────────────────────────────────────────────────
class _Stream:
    """بثٌّ مصطنع: أحداث ping لا تنتهي، ولقطة رسالةٍ بأرقام الدخل، ويسجّل إغلاقه."""

    def __init__(self, events: int, final) -> None:
        self.events = events
        self.final = final
        self.closed = False
        self.request_id = "req_stream"
        self.current_message_snapshot = SimpleNamespace(usage=SimpleNamespace(input_tokens=700, output_tokens=0),
                                                        model="claude-opus-5-5")

    def __iter__(self):
        for _ in range(self.events):
            yield SimpleNamespace(type="ping")

    def get_final_message(self):
        return self.final

    def close(self):
        self.closed = True


class _Manager:
    def __init__(self, stream) -> None:
        self.stream = stream

    def __enter__(self):
        return self.stream

    def __exit__(self, *exc):
        self.stream.close()


def _streaming_gateway(stream, seen: dict) -> AnthropicGateway:
    def stream_factory(**params):
        seen.update(params)
        return _Manager(stream)
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream_factory)))
    return AnthropicGateway("unused", client=client)


def test_a_stream_past_its_deadline_is_closed_and_counted_as_a_timeout(monkeypatch):
    times = iter([0.0, 0.0, 10.0, 50.0, 130.0, 131.0, 132.0])
    monkeypatch.setattr(clock, "monotonic", lambda: next(times))
    stream = _Stream(events=100, final=None)
    seen: dict = {}
    reply = _streaming_gateway(stream, seen).call(_call(stream=True, deadline_seconds=120.0))
    assert reply.outcome == "UPSTREAM_TIMEOUT" and reply.processed and stream.closed
    assert reply.usage["input"] == 700 and reply.usage["api_request_id"] == "req_stream"
    # مهلة القراءة بين حدثين عشرون ثانية، لا مهلة الأداة كلّها.
    assert (seen["timeout"].read, seen["timeout"].connect) == (20.0, 3.0)
    assert "thinking" not in seen


def test_a_stream_that_finishes_in_time_is_read_like_a_plain_reply(monkeypatch):
    monkeypatch.setattr(clock, "monotonic", lambda: 0.0)
    final = SimpleNamespace(
        stop_reason="end_turn", model="claude-opus-5-5", stop_details=None,
        content=[SimpleNamespace(type="text", text=json.dumps({"flags": []}))],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    stream = _Stream(events=3, final=final)
    reply = _streaming_gateway(stream, {}).call(_call(stream=True, deadline_seconds=120.0))
    assert reply.outcome == "OK" and reply.data == {"flags": []} and stream.closed


# ── القاطع والمقاعد ────────────────────────────────────────────────────
def _reply(outcome: str, status: int | None = None) -> ModelReply:
    return ModelReply(outcome, None, {}, None, None, outcome == "OK", None, status)


def test_the_breaker_opens_after_three_failures_in_the_window_and_closes_on_a_success(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    breaker = Breaker()
    for _ in range(2):
        breaker.record(_reply("UPSTREAM_TIMEOUT"))
    assert breaker.allow()
    now[0] = 130.0   # الإخفاقان الأوّلان خرجا من نافذة الدقيقتين فلا يُعدّان
    breaker.record(_reply("UPSTREAM_BUSY"))
    breaker.record(_reply("UPSTREAM_UNREACHABLE"))
    assert breaker.allow() and not breaker.is_open
    breaker.record(_reply("UPSTREAM_ERROR", 500))
    assert breaker.is_open and not breaker.allow()
    now[0] = 189.0
    assert not breaker.allow()
    now[0] = 190.0   # بعد ستين ثانية: استدعاءٌ واحد تجريبي
    assert breaker.allow() and not breaker.allow()
    breaker.record(_reply("OK"))
    assert not breaker.is_open and breaker.allow()


def test_a_failed_trial_reopens_the_breaker_for_a_full_period(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    breaker = Breaker()
    for _ in range(3):
        breaker.record(_reply("UPSTREAM_ERROR", 503))
    now[0] = 61.0
    assert breaker.allow()
    breaker.record(_reply("UPSTREAM_TIMEOUT"))
    now[0] = 100.0
    assert not breaker.allow()
    now[0] = 122.0
    assert breaker.allow()


def test_client_errors_refusals_and_invalid_output_never_trip_the_breaker():
    breaker = Breaker()
    for reply in (_reply("UPSTREAM_ERROR", 400), _reply("UPSTREAM_ERROR", 401), _reply("REFUSED"),
                  _reply("OUTPUT_INVALID"), _reply("UPSTREAM_ERROR", 404)):
        for _ in range(3):
            breaker.record(reply)
    assert not breaker.is_open


def test_a_trial_permit_not_used_for_a_call_returns_to_the_breaker(monkeypatch):
    """مراجعةٌ مخزونة أو سقفٌ أخذ الإذن ولم يستدعِ شيئاً: الضغطة التالية تجد الإذن، لا «غير متاح» إلى الأبد."""
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    guard = Guard(slots=1)
    for _ in range(3):
        guard.record(_reply("UPSTREAM_TIMEOUT"))
    now[0] = 61.0
    assert guard.acquire() is None                 # الإذن التجريبي
    guard.release(called=False)                    # لم يصل شيءٌ إلى المزوّد
    assert guard.acquire() is None                 # يعود في الحال
    guard.release()                                # استدعاءٌ لم يُسجَّل: ضاع الإذن
    assert guard.acquire() == "DOWN"
    now[0] = 122.0                                 # مدّة فتحٍ أخرى تجدّده
    assert guard.acquire() is None
    guard.record(_reply("OK"))
    guard.release()
    assert guard.acquire() is None and not guard.breaker.is_open


def test_a_trial_permit_without_a_free_slot_is_not_consumed(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    guard = Guard(slots=1)
    assert guard.acquire() is None                 # المقعد الوحيد مشغول باستدعاءٍ قديم
    for _ in range(3):
        guard.record(_reply("UPSTREAM_TIMEOUT"))
    now[0] = 61.0
    assert guard.acquire() == "BUSY"               # إذنٌ بلا مقعد يعود إلى القاطع
    guard.release()
    assert guard.acquire() is None
    guard.release(called=False)


def test_a_failure_of_a_call_begun_before_the_opening_does_not_extend_the_open_period(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    breaker = Breaker()
    for _ in range(3):
        breaker.record(_reply("UPSTREAM_TIMEOUT"))
    now[0] = 30.0
    breaker.record(_reply("UPSTREAM_ERROR", 503))  # استدعاءٌ كان في الطيران عند الفتح
    now[0] = 60.0
    assert breaker.allow()                         # التجربة الأولى عند الستين لا التسعين


def test_the_guard_refuses_without_a_slot_and_while_the_breaker_is_open():
    guard = Guard(slots=1)
    assert guard.acquire() is None
    assert guard.acquire() == "BUSY"
    guard.release()
    assert guard.acquire() is None
    guard.release()
    for _ in range(3):
        guard.record(_reply("UPSTREAM_TIMEOUT"))
    assert guard.acquire() == "DOWN"
