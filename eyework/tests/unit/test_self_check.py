"""
أداة الفحص الذاتي
=================
ما تُرجعه للنموذج هو ما سيُرفض به جوابه لو أرسله: القواعد نفسها، والأرقام
نفسها، بجملٍ تقول ما يُغيَّر.
"""

from __future__ import annotations

import json

from eyework import self_check
from eyework.copy_rules import EditPreset
from eyework.prompt import CopyRequest, PreviousCopy

TITLE = "حقيبة جلدية بنية أنيقة"
DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف."
REQUEST = CopyRequest(jpeg=b"x")


def _run(title=TITLE, description=DESCRIPTION, note="", request=REQUEST):
    content, is_error = self_check.run(
        {"title": title, "description": description, "message_to_user": note}, request)
    return json.loads(content), is_error


def test_valid_copy_is_ok_with_its_counts():
    report, is_error = _run()
    assert not is_error
    assert report == {"ok": True, "title_chars": len(TITLE), "description_chars": len(DESCRIPTION),
                      "problems": [], "cautions": []}


def test_each_problem_says_what_to_change():
    report, _ = _run(title="قصير", description=DESCRIPTION + " اتصل 0551234567 أو زر shop.com")
    assert report["ok"] is False
    joined = " ".join(report["problems"])
    assert "العنوان 4 حرفاً" in joined and "أرقام الهواتف" in joined and "الروابط" in joined


def test_soft_warnings_come_back_as_cautions_not_problems():
    report, _ = _run(description=DESCRIPTION + " وهي الأفضل في السوق.")
    assert report["ok"] is True and report["problems"] == []
    assert any("مبالغة" in caution for caution in report["cautions"])


def test_a_bad_note_blocks_ok():
    report, _ = _run(note="زر موقعنا www.shop.example")
    assert report["ok"] is False


def test_the_fixed_field_is_checked_as_it_will_be_sent():
    """في «عنوان جديد» الوصف لا يتغيّر؛ يُفحص الوصف السابق لا ما كتبه النموذج."""
    request = CopyRequest(jpeg=b"x", previous=PreviousCopy(TITLE, DESCRIPTION), presets=(EditPreset.NEW_TITLE,))
    report, _ = _run(title="حقيبة يد جلدية بنية", description="قصير", request=request)
    assert report["ok"] is True and report["description_chars"] == len(DESCRIPTION)


def test_malformed_arguments_are_an_error_and_nothing_runs():
    for arguments in (None, {"title": TITLE}, {"title": 1, "description": "", "message_to_user": ""},
                      {"title": TITLE, "description": DESCRIPTION, "message_to_user": "", "extra": ""}):
        content, is_error = self_check.run(arguments, REQUEST)
        assert is_error and "title" in content
