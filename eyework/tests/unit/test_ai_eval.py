"""
تقييم الإصدار يطبع كل نتيجة
===========================
`ai_eval` يُقرأ قبل الاعتماد ليُعرف ما يفعله النموذج على التجهيزات؛ فلا تُخفي
نتيجةٌ نتيجةً: كل نوعٍ من النتائج له سطرٌ باسمه، وأعدادٌ في الختام.
"""

from __future__ import annotations

from collections import deque

import pytest

from eyework.scripts import ai_eval
from eyework.tests.fakes import assistant_reply, model_reply

#: ردٌّ لكل سؤالٍ من الأسئلة المضمّنة بترتيبها؛ التاسع يطلب فعلاً فيُجاب بادّعاء فعل.
REPLIES = [
    assistant_reply("ANSWER"),
    assistant_reply("DONT_KNOW"),
    assistant_reply("OUT_OF_SCOPE"),
    assistant_reply("ANSWER", answer="زر https://x.example الآن"),   # يسقط في الفحص
    model_reply("REFUSED"),
    model_reply("OUTPUT_INVALID"),
    model_reply("UPSTREAM_BUSY"),
    model_reply("UPSTREAM_UNREACHABLE"),
    assistant_reply("ANSWER", answer="حفظتُ الفاتورة الآن كما طلبت."),
    model_reply("UPSTREAM_TIMEOUT"),
    model_reply("UPSTREAM_ERROR", status=500),
]


class _Gateway:
    def __init__(self, key: str) -> None:
        self.replies = deque(REPLIES)
        self.efforts: list[str] = []

    def call(self, request):
        self.efforts.append(request.effort)
        return self.replies.popleft() if self.replies else assistant_reply()


@pytest.fixture
def run(monkeypatch, capsys):
    monkeypatch.setenv("EYEWORK_ANTHROPIC_API_KEY", "test-key")
    gateways: list[_Gateway] = []

    def factory(key: str) -> _Gateway:
        gateway = _Gateway(key)
        gateways.append(gateway)
        return gateway

    monkeypatch.setattr(ai_eval, "AnthropicGateway", factory)

    def go(*argv: str) -> tuple[int, str, list[_Gateway]]:
        code = ai_eval.main(list(argv))
        return code, capsys.readouterr().out, gateways
    return go


def test_every_outcome_kind_is_printed_with_the_counts(run):
    code, out, gateways = run("--feature", "ASSISTANT", "--profession", "STOREKEEPER", "--effort", "medium")
    assert code == 0
    for kind in ai_eval.OUTCOME_KINDS:
        assert kind in out, kind
    assert "cases: 11" in out and "acted: 1" in out and "drops: 1" in out and "p90_ms" in out
    assert set(gateways[0].efforts) == {"medium"}


def test_a_missing_key_or_profession_stops_before_any_call(run, monkeypatch):
    code, _, gateways = run("--feature", "ASSISTANT")
    assert code == 2 and gateways == []
    monkeypatch.delenv("EYEWORK_ANTHROPIC_API_KEY")
    code, _, gateways = run("--feature", "ASSISTANT", "--profession", "SUPPORT")
    assert code == 2 and gateways == []


def test_an_unregistered_review_feature_is_refused_before_any_client_is_built(run):
    code, _, gateways = run("--feature", "STOCK_REVIEW")
    assert code == 2 and gateways == []
