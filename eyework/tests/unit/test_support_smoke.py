"""
قياس مسوّدات الدعم (scripts/support_smoke.py) بلا مفتاح
=======================================================
الحالات الأربع عشرة تمرّ بمسار الإنتاج على بوّابةٍ مصطنعة تجيب كما يُنتظر فتنجح كلّها، وجوابٌ يقتبس من
مقالةٍ أخرى أو يخالف النوع يُعدّ مخالفاً؛ ورسائل الحالات نفسها بلا بيانات اتصال.
"""

from __future__ import annotations

from eyework import support_rules as rules
from eyework.scripts import support_smoke as smoke
from eyework.tests.fakes import FakeGateway, draft_reply

FIRST_STEP = {a.id: a.resolution.split("\n")[0].split(". ", 1)[1].rstrip(".") for a in smoke.KB}


def _expected(case: smoke.Case):
    english = rules.language_of(case.message) == "EN"
    if case.status == "NOT_SUPPORT":
        return draft_reply("NOT_SUPPORT", "NONE", "", (), note="رسالة شكرٍ أو سؤالٌ ليس عن مشكلةٍ تقنية.")
    if case.status == "CANNOT_ANSWER":
        body = "What exactly does the error message say?" if english else "لنساعدكم بسرعة، ما نصّ رسالة الخطأ كما تظهر على الشاشة؟"
        return draft_reply("CANNOT_ANSWER", case.kind or "ASK_INFO", body, ())
    step = FIRST_STEP[case.article]
    body = ("Please try the steps in our guide, starting with the first one, and tell us if the problem stays."
            if english else f"جرّبوا ما يلي من دليلنا:\n1. {step}.\nثم أخبرونا إن بقيت المشكلة.")
    return draft_reply("DRAFT", case.kind or "ANSWER", body, ({"article": f"A{[a.id for a in smoke.KB].index(case.article) + 1}", "quote": step},))


def test_the_fourteen_cases_pass_when_the_drafts_are_as_expected(capsys):
    gateway = FakeGateway(*(_expected(case) for case in smoke.CASES))
    assert smoke.run(gateway) == 0
    assert "14 من 14 كما يُنتظر." in capsys.readouterr().out
    assert all(call.feature == "SUPPORT_DRAFT" for call in gateway.calls)


def test_a_draft_that_quotes_the_wrong_article_or_kind_fails_the_run(capsys):
    printer = smoke.CASES[0]
    wrong = draft_reply("DRAFT", "ANSWER", f"جرّبوا ما يلي:\n1. {FIRST_STEP['vpn']}.", ({"article": "A2", "quote": FIRST_STEP["vpn"]},))
    summary, problems = smoke.check(printer, FakeGateway(wrong))
    assert summary == "DRAFT/ANSWER" and problems == ["لم يقتبس من «printer»"]
    summary, problems = smoke.check(smoke.CASES[1], FakeGateway(_expected(smoke.CASES[0])))
    assert "النتيجة DRAFT والمنتظر CANNOT_ANSWER" in problems


def test_the_cases_hold_no_contact_data():
    for case in smoke.CASES:
        assert rules.mask(case.message)[0] == case.message, case.name
