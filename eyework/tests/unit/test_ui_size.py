"""
طريقة الاستخدام
===============
قيمتان لا ثالث لهما، لكلٍّ اسمها وسطرها، وهما ما يقبله القيد `ui_size_known` في
الترحيل 0008 حرفاً بحرف: قيمةٌ تُضاف هنا وتردّها القاعدة تُكتشف هنا لا عند المستخدم.
"""

from __future__ import annotations

import re
from pathlib import Path

from eyework.ui_size import CHOICES, UiSize

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0008_open_registration.up.sql"


def test_every_size_has_a_name_and_a_detail_line():
    assert set(CHOICES) == set(UiSize) == {UiSize.COMPACT, UiSize.GAZE}
    for name, detail in CHOICES.values():
        assert name.strip() == name and detail.strip() == detail
        assert 0 < len(name) <= 20 and 0 < len(detail) <= 60


def test_the_sizes_are_the_values_the_database_accepts():
    sql = MIGRATION.read_text(encoding="utf-8")
    check = re.search(r"CONSTRAINT ui_size_known CHECK \(ui_size IN \(([^)]*)\)\)", sql)
    assert check, "القيد ui_size_known غير موجود في الترحيل"
    assert set(re.findall(r"'([A-Z]+)'", check.group(1))) == {size.value for size in UiSize}


def test_a_size_is_its_own_code_and_nothing_else_is_one():
    assert UiSize("GAZE") is UiSize.GAZE
    assert str(UiSize.COMPACT) == "COMPACT"
    for value in ("gaze", "LARGE", "", None):
        try:
            UiSize(value)
        except ValueError:
            continue
        raise AssertionError(value)
