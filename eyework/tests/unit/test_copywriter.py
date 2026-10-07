"""
كاتب النصّ عبر نقلٍ مصطنع
=========================
الكاتب الحقيقي نفسه، والمكتبة نفسها، ونقل HTTP مصطنع بدل الشبكة: يُختبر
تحويل كل استجابةٍ وكل خطأ إلى نتيجةٍ من السبع كما يحدث في الإنتاج.
"""

from __future__ import annotations

import json

import anthropic
import httpx
import pytest

from eyework.copy_rules import CopyWarning, EditPreset
from eyework.copywriter import AnthropicCopywriter
from eyework.prompt import CopyRequest, PreviousCopy

JPEG = b"\xff\xd8\xff\xe0fake"
GOOD = {
    "status": "OK",
    "reason": "NONE",
    "title": "حقيبة جلدية بنية أنيقة",
    "description": "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف.",
    "message_to_user": "أبرزتُ الخامة واللون، ولم أذكر المقاس لأنه لا يظهر في الصورة.",
}


def _writer(handler) -> AnthropicCopywriter:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx.MockTransport(handler)),
    )
    return AnthropicCopywriter("unused", client=client)


def _message(text, stop_reason="end_turn"):
    def handler(request: httpx.Request) -> httpx.Response:
        handler.seen = request
        return httpx.Response(200, headers={"request-id": "req_ok"}, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "text", "text": text},
            ],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 300},
        })
    return handler


def _error(status, headers=None):
    def handler(request):
        return httpx.Response(status, headers={"request-id": "req_err", **(headers or {})},
                              json={"type": "error", "error": {"type": "x", "message": "m"}})
    return handler


def test_ok_carries_the_served_model_and_request_id():
    handler = _message(json.dumps(GOOD, ensure_ascii=False))
    outcome = _writer(handler).write(CopyRequest(jpeg=JPEG))
    assert outcome.outcome == "OK"
    assert (outcome.title, outcome.description) == (GOOD["title"], GOOD["description"])
    assert outcome.served_model == "claude-opus-5-5"
    assert outcome.request_id == "req_ok"
    assert outcome.note == GOOD["message_to_user"]
    assert (outcome.input_tokens, outcome.output_tokens) == (1200, 300)

    sent = json.loads(handler.seen.content)
    assert handler.seen.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert sent["fallbacks"] == "default"
    assert "thinking" not in sent


def test_refusal_is_checked_before_content():
    assert _writer(_message("", "refusal")).write(CopyRequest(jpeg=JPEG)).outcome == "REFUSED"


@pytest.mark.parametrize(("text", "stop_reason"), [
    ('{"status": "OK", "reason"', "max_tokens"),
    ("not json", "end_turn"),
    (json.dumps({**GOOD, "extra": 1}), "end_turn"),
    (json.dumps({**GOOD, "title": "قصير"}, ensure_ascii=False), "end_turn"),
    (json.dumps({**GOOD, "description": GOOD["description"] + " https://x.example"}, ensure_ascii=False), "end_turn"),
    (json.dumps({**GOOD, "status": "UNUSABLE_PHOTO", "reason": "NONE"}), "end_turn"),
])
def test_invalid_output_is_rejected_never_truncated(text, stop_reason):
    assert _writer(_message(text, stop_reason)).write(CopyRequest(jpeg=JPEG)).outcome == "OUTPUT_INVALID"


def test_unusable_photo_carries_its_reason():
    text = json.dumps({"status": "UNUSABLE_PHOTO", "reason": "MULTIPLE_PRODUCTS", "title": "", "description": "",
                       "message_to_user": "صوّر المنتج وحده على خلفيةٍ سادة."}, ensure_ascii=False)
    outcome = _writer(_message(text)).write(CopyRequest(jpeg=JPEG))
    assert (outcome.outcome, outcome.reason) == ("UNUSABLE_PHOTO", "MULTIPLE_PRODUCTS")
    assert outcome.note == "صوّر المنتج وحده على خلفيةٍ سادة."


def test_warnings_travel_with_valid_copy():
    text = json.dumps({**GOOD, "description": GOOD["description"] + " وهو علاج طبيعي."}, ensure_ascii=False)
    outcome = _writer(_message(text)).write(CopyRequest(jpeg=JPEG))
    assert outcome.outcome == "OK"
    assert CopyWarning.HEALTH_CLAIM in outcome.warnings


def test_new_title_keeps_the_description_byte_for_byte():
    previous = PreviousCopy(GOOD["title"], GOOD["description"])
    text = json.dumps({**GOOD, "title": "حقيبة يد جلدية بنية",
                       "description": "وصفٌ آخر كتبه النموذج مع أنه لم يُطلب منه تغيير الوصف أصلاً."}, ensure_ascii=False)
    outcome = _writer(_message(text)).write(
        CopyRequest(jpeg=JPEG, previous=previous, presets=(EditPreset.NEW_TITLE,)))
    assert outcome.title == "حقيبة يد جلدية بنية"
    assert outcome.description == GOOD["description"]


@pytest.mark.parametrize(("handler", "expected", "retry_after"), [
    pytest.param(_error(429, {"retry-after": "12"}), "UPSTREAM_BUSY", 12, id="429"),
    pytest.param(_error(503), "UPSTREAM_BUSY", 30, id="503"),
    pytest.param(_error(529), "UPSTREAM_BUSY", 30, id="529"),
    pytest.param(_error(504), "UPSTREAM_TIMEOUT", None, id="504"),
    pytest.param(_error(500), "UPSTREAM_ERROR", None, id="500"),
    pytest.param(_error(400), "UPSTREAM_ERROR", None, id="400"),
    pytest.param(_error(401), "UPSTREAM_ERROR", None, id="401"),
    pytest.param(_error(403), "UPSTREAM_ERROR", None, id="403"),
    pytest.param(_error(404), "UPSTREAM_ERROR", None, id="404"),
    pytest.param(_error(413), "UPSTREAM_ERROR", None, id="413"),
])
def test_http_errors_map_to_outcomes(handler, expected, retry_after):
    outcome = _writer(handler).write(CopyRequest(jpeg=JPEG))
    assert outcome.outcome == expected
    assert outcome.retry_after_seconds == retry_after


def test_timeout_and_connection_errors():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("down", request=request)

    assert _writer(timeout).write(CopyRequest(jpeg=JPEG)).outcome == "UPSTREAM_TIMEOUT"
    # لم يصل الطلب: نتيجةٌ مستقلّة لا تُحسب في حدّ اليوم.
    assert _writer(refused).write(CopyRequest(jpeg=JPEG)).outcome == "UPSTREAM_UNREACHABLE"


def test_the_platform_key_is_never_read(monkeypatch):
    """`ANTHROPIC_API_KEY` في البيئة لا يصل الطلب: المفتاح يُمرَّر صراحةً."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "platform-key")
    writer = AnthropicCopywriter("eyework-key")
    assert writer._client.api_key == "eyework-key"


# ── حلقة أداة الفحص الذاتي ──────────────────────────────────────────────


def _tool_use(title, description, note="", tool="check_copy", block_id="toolu_1"):
    return {"type": "tool_use", "id": block_id, "name": tool,
            "input": {"title": title, "description": description, "message_to_user": note}}


def _sequence(*responses):
    """يُرجع الردود بالترتيب، ويحفظ كل طلبٍ وصل. ردٌّ = (محتوى، سبب التوقّف) أو استثناء."""
    def handler(request: httpx.Request) -> httpx.Response:
        handler.seen.append(json.loads(request.content))
        item = responses[len(handler.seen) - 1]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        content, stop_reason = item
        return httpx.Response(200, headers={"request-id": f"req_{len(handler.seen)}"}, json={
            "id": f"msg_{len(handler.seen)}", "type": "message", "role": "assistant",
            "model": "claude-opus-5-5", "content": content, "stop_reason": stop_reason,
            "stop_sequence": None, "usage": {"input_tokens": 1000, "output_tokens": 100},
        })
    handler.seen = []
    return handler


def _final(data=GOOD):
    return ([{"type": "text", "text": json.dumps(data, ensure_ascii=False)}], "end_turn")


def test_the_model_fixes_what_the_check_reports_then_answers():
    too_long = "حقيبة جلدية بنية أنيقة بحزام كتف عريض وجيوب داخلية متعددة للأغراض اليومية"
    handler = _sequence(([_tool_use(too_long, GOOD["description"])], "tool_use"), _final())
    outcome = _writer(handler).write(CopyRequest(jpeg=JPEG))

    assert outcome.outcome == "OK" and outcome.title == GOOD["title"]
    assert (outcome.input_tokens, outcome.output_tokens) == (2000, 200)   # الجولتان تُدفعان
    first, second = handler.seen
    assert second["messages"][:1] == first["messages"]                   # البادئة نفسها فتُقرأ مخزّنة
    assistant, results = second["messages"][1:]
    assert assistant["role"] == "assistant" and assistant["content"][0]["type"] == "tool_use"
    (result,) = results["content"]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1"
    report = json.loads(result["content"])
    assert report["ok"] is False and report["title_chars"] == len(too_long)
    assert any("طول العنوان" in problem and "60" in problem for problem in report["problems"])


def test_a_model_that_keeps_checking_is_asked_to_answer_without_tools():
    """بعد ثلاث جولات يُطلب الجواب بلا أدوات، فلا يُرمى استدعاءٌ مدفوع."""
    loop = ([_tool_use(GOOD["title"], GOOD["description"])], "tool_use")
    handler = _sequence(loop, loop, loop, _final())
    outcome = _writer(handler).write(CopyRequest(jpeg=JPEG))
    assert outcome.outcome == "OK"
    assert [request.get("tool_choice") for request in handler.seen] == [None, None, None, {"type": "none"}]
    assert all(request["tools"] == handler.seen[0]["tools"] for request in handler.seen)


def test_a_tool_call_after_tools_were_refused_is_invalid():
    loop = ([_tool_use(GOOD["title"], GOOD["description"])], "tool_use")
    handler = _sequence(loop, loop, loop, loop)
    assert _writer(handler).write(CopyRequest(jpeg=JPEG)).outcome == "OUTPUT_INVALID"
    assert len(handler.seen) == 4


def test_after_a_fallback_the_turn_is_echoed_by_the_documented_rule():
    """قبل آخر كتلة fallback: يُسقط التفكير واستدعاء الأداة؛ وبعدها يبقى كل شيء."""
    content = [
        {"type": "thinking", "thinking": "", "signature": "a"},
        _tool_use(GOOD["title"], GOOD["description"], block_id="toolu_old"),
        {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-4-8"}},
        {"type": "thinking", "thinking": "", "signature": "b"},
        _tool_use(GOOD["title"], GOOD["description"], block_id="toolu_new"),
    ]
    handler = _sequence((content, "tool_use"), _final())
    assert _writer(handler).write(CopyRequest(jpeg=JPEG)).outcome == "OK"
    echoed = handler.seen[1]["messages"][1]["content"]
    assert [(block["type"], block.get("id") or block.get("signature")) for block in echoed] == [
        ("fallback", None), ("thinking", "b"), ("tool_use", "toolu_new"),
    ]


def test_an_unknown_tool_is_answered_with_an_error_not_run():
    handler = _sequence(([_tool_use(GOOD["title"], GOOD["description"], tool="publish_ad")], "tool_use"),
                        _final())
    assert _writer(handler).write(CopyRequest(jpeg=JPEG)).outcome == "OK"
    (result,) = handler.seen[1]["messages"][2]["content"]
    assert result["is_error"] is True


def test_a_failure_after_a_processed_round_still_counts():
    """الجولة الأولى عولجت ودُفعت؛ ازدحامٌ بعدها لا يجعل المحاولة غير محسوبة."""
    busy = httpx.Response(529, headers={"request-id": "req_busy"},
                          json={"type": "error", "error": {"type": "overloaded_error", "message": "m"}})
    handler = _sequence(([_tool_use(GOOD["title"], GOOD["description"])], "tool_use"), busy)
    assert _writer(handler).write(CopyRequest(jpeg=JPEG)).outcome == "OUTPUT_INVALID"


def test_the_whole_exchange_has_one_deadline(monkeypatch):
    from eyework import clock

    times = iter([0.0, 0.0, 195.0])   # البداية، ثم الجولة الأولى، ثم الثانية بعد 195 ثانية
    monkeypatch.setattr(clock, "monotonic", lambda: next(times))
    handler = _sequence(([_tool_use(GOOD["title"], GOOD["description"])], "tool_use"), _final())
    assert _writer(handler).write(CopyRequest(jpeg=JPEG)).outcome == "UPSTREAM_TIMEOUT"
    assert len(handler.seen) == 1


def test_a_bad_note_is_dropped_and_the_copy_kept():
    handler = _sequence(_final({**GOOD, "message_to_user": "زر موقعنا www.shop.example للمزيد"}))
    outcome = _writer(handler).write(CopyRequest(jpeg=JPEG))
    assert outcome.outcome == "OK" and outcome.note is None


def test_the_destination_and_retries_are_fixed_in_code(monkeypatch):
    """ANTHROPIC_BASE_URL في البيئة لا يغيّر وجهة الصورة، ولا إعادة خفية."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example")
    writer = AnthropicCopywriter("eyework-key")
    assert str(writer._client.base_url).rstrip("/") == "https://api.anthropic.com"
    assert writer._client.max_retries == 0
