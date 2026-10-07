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
    text = json.dumps({"status": "UNUSABLE_PHOTO", "reason": "MULTIPLE_PRODUCTS", "title": "", "description": ""})
    outcome = _writer(_message(text)).write(CopyRequest(jpeg=JPEG))
    assert (outcome.outcome, outcome.reason) == ("UNUSABLE_PHOTO", "MULTIPLE_PRODUCTS")


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
