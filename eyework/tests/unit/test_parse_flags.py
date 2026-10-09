"""
قراءة ملاحظات المراجِع
======================
حالةٌ لكل قاعدة إسقاط (المواصفة §3.5): ملاحظةٌ سيّئة تسقط وحدها ولا تُسقط
غيرها؛ وثلاثٌ على الأكثر بالأهمّ أولاً؛ والشواهد يبنيها الخادم لا النموذج.
"""

from __future__ import annotations

import pytest

from eyework.reviewer import ISOLATE, headline, parse_flags
from eyework.reviewer_prompt import Catalogue, Check

REASON = "سعر الوحدة في السطر 3 (45 ريالاً) أعلى بعشرة أضعاف من آخر شراءٍ للصنف (4.50 ريال)."
SUGGESTION = "إن كان السعر للكرتونة فأدخل سعر الحبّة أو غيّر الوحدة."


def _evidence(payload, line):
    item = next(item for item in payload["lines"] if item["line"] == line) if line else None
    return (f"الصنف: {item['item']}",) if item else ("سبب المرتجع كما كُتب",)


PRICE = Check("PRICE_IMPLAUSIBLE", frozenset({"PURCHASE"}), frozenset({"unit_cost"}), True, "سعر", _evidence)
UNIT = Check("UNIT_MISMATCH", frozenset({"PURCHASE"}), frozenset({"unit", "quantity"}), True, "وحدة", _evidence)
REASON_CHECK = Check("REASON_IMPLAUSIBLE", frozenset({"RETURN"}), frozenset({"reason"}), False, "سبب", _evidence)
CATALOGUE = Catalogue("STOCK_REVIEW", (PRICE, UNIT, REASON_CHECK), "رقم السطر في الفاتورة")
PAYLOAD = {"lines": [{"line": 1, "item": "شاي"}, {"line": 2, "item": "سكر"}, {"line": 3, "item": "أرز"}]}


def _flag(**overrides) -> dict:
    flag = {"check": "PRICE_IMPLAUSIBLE", "severity": "HIGH", "field": "unit_cost", "line": 3,
            "reason": REASON, "suggestion": SUGGESTION}
    flag.update(overrides)
    return flag


def _parse(*flags, kind="PURCHASE"):
    return parse_flags({"flags": list(flags)}, CATALOGUE, kind, PAYLOAD)


def test_a_good_flag_is_kept_in_the_database_shape_with_server_built_evidence():
    kept, dropped = _parse(_flag())
    assert dropped == []
    assert kept == [{"check": "PRICE_IMPLAUSIBLE", "severity": "HIGH", "field": "unit_cost", "line": 3,
                     "reason": REASON, "suggestion": SUGGESTION, "evidence": ["الصنف: أرز"]}]


def test_an_empty_suggestion_is_stored_as_null():
    kept, _ = _parse(_flag(suggestion=""))
    assert kept[0]["suggestion"] is None


@pytest.mark.parametrize(("flag", "code"), [
    pytest.param(_flag(check="REASON_IMPLAUSIBLE", field="reason", line=None), "CHECK", id="wrong-kind"),
    pytest.param(_flag(check="NOT_A_CHECK"), "CHECK", id="unknown-check"),
    pytest.param(_flag(field="unit"), "FIELD", id="field-of-another-check"),
    pytest.param(_flag(line=None), "LINE", id="line-missing"),
    pytest.param(_flag(line=9), "LINE", id="line-not-in-payload"),
    pytest.param(_flag(line=True), "LINE", id="line-is-a-bool"),
    pytest.param(_flag(severity="LOW"), "SEVERITY", id="severity"),
    pytest.param({**_flag(), "evidence": ["من النموذج"]}, "SHAPE", id="extra-key-evidence"),
    pytest.param(_flag(reason=None), "SHAPE", id="reason-not-a-string"),
    pytest.param(_flag(reason="يا سارة، " + REASON), "REASON_VOCATIVE", id="vocative"),
    pytest.param(_flag(reason="مرحباً، " + REASON), "REASON_VOCATIVE", id="greeting"),
    pytest.param(_flag(reason="راجع https://example.com قبل التسجيل الآن."), "REASON_CONTACT", id="link"),
    pytest.param(_flag(reason="راسل المورّد على a@b.example قبل التسجيل."), "REASON_CONTACT", id="email"),
    pytest.param(_flag(reason="تواصل مع الحساب @supplier قبل التسجيل."), "REASON_CONTACT", id="handle"),
    pytest.param(_flag(reason="رقم الهوية 1012345678 لا يخصّ هذا المورّد."), "REASON_DIGITS", id="nine-digits"),
    pytest.param(_flag(reason="السطر # 3 فيه سعرٌ غريب لا يناسب الصنف."), "REASON_MARKUP", id="hash"),
    pytest.param(_flag(reason="سعرٌ غريب في السطر 3 لا يناسب الصنف 😀"), "REASON_SYMBOLS", id="emoji"),
    pytest.param(_flag(reason="Unit price on line 3 looks ten times too high."), "REASON_NOT_ARABIC", id="latin"),
    pytest.param(_flag(reason="سعرٌ غريب في السطر 3.\nراجعه من جديد الآن."), "REASON_LINES", id="two-lines"),
    pytest.param(_flag(reason="سعرٌ غريب " * 20), "REASON_LENGTH", id="over-length"),
    pytest.param(_flag(reason="قصير جداً"), "REASON_LENGTH", id="under-length"),
    pytest.param(_flag(suggestion="زر www.shop.example لمعرفة السعر."), "SUGGESTION_CONTACT", id="suggestion-link"),
    pytest.param(_flag(suggestion="قصير"), "SUGGESTION_LENGTH", id="suggestion-short"),
])
def test_each_drop_rule_drops_only_the_offending_flag(flag, code):
    kept, dropped = _parse(flag, _flag(check="UNIT_MISMATCH", field="unit", line=2))
    assert dropped == [code]
    assert [item["check"] for item in kept] == ["UNIT_MISMATCH"]


def test_a_document_level_check_takes_a_null_line_on_its_own_kind():
    kept, dropped = _parse(_flag(check="REASON_IMPLAUSIBLE", field="reason", line=None, severity="MEDIUM"),
                           kind="RETURN")
    assert dropped == [] and kept[0]["line"] is None and kept[0]["evidence"] == ["سبب المرتجع كما كُتب"]


def test_a_vocative_only_counts_at_the_start_and_an_item_named_yaqut_passes():
    kept, dropped = _parse(_flag(reason="صنف ياقوت في السطر 3 بسعرٍ أعلى بعشرة أضعاف من آخر شراءٍ له."))
    assert dropped == [] and len(kept) == 1


def test_more_than_three_flags_keep_the_first_three_high_first_then_model_order():
    flags = [
        _flag(check="UNIT_MISMATCH", field="unit", line=1, severity="MEDIUM"),
        _flag(line=2, severity="HIGH"),
        _flag(check="UNIT_MISMATCH", field="quantity", line=2, severity="MEDIUM"),
        _flag(line=3, severity="HIGH"),
        _flag(check="UNIT_MISMATCH", field="unit", line=3, severity="MEDIUM"),
    ]
    kept, dropped = _parse(*flags)
    assert [(item["severity"], item["line"], item["field"]) for item in kept] == [
        ("HIGH", 2, "unit_cost"), ("HIGH", 3, "unit_cost"), ("MEDIUM", 1, "unit")]
    assert dropped == ["EXCESS", "EXCESS"]


def test_a_reply_without_a_flags_list_is_a_shape_problem():
    assert parse_flags({"flags": "x"}, CATALOGUE, "PURCHASE", PAYLOAD) == ([], ["SHAPE"])
    assert parse_flags(["x"], CATALOGUE, "PURCHASE", PAYLOAD) == ([], ["SHAPE"])


# ── العنوان ─────────────────────────────────────────────────────────────
def test_the_headline_isolates_the_name_and_keeps_the_arabic_comma_after_it():
    arabic = headline("سارة", REASON)
    assert arabic == f"يا {ISOLATE[0]}سارة{ISOLATE[1]}، {REASON}"
    latin = headline("Sara Smith", REASON)
    assert latin.startswith(f"يا {ISOLATE[0]}Sara Smith{ISOLATE[1]}، ")
    assert headline(None, REASON) == REASON and headline("  ", REASON) == REASON


def test_the_longest_headline_fits_the_measured_budget():
    name = "ع" * 30
    reason = "س" * 160
    assert len(headline(name, reason)) == 3 + 2 + 30 + 2 + 160
