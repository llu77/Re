"""
الأعداد بالكلمات
================
المبلغ يُعاد بالكلمات قبل الاعتماد لأن الرقم يُقرأ خطأً بسهولة. فإن أخطأت
الكلمات صار التحقّق نفسه مصدر خطأ — ولذلك يُختبر كل ما يمكن أن يظهر.
"""

from __future__ import annotations

import pytest

from eyework.arabic_numbers import DAY, RIYAL, in_words
from eyework.money import BUDGET_VALUES, DAY_VALUES

DAYS = {
    1: "يوم واحد", 2: "يومان", 3: "ثلاثة أيام", 4: "أربعة أيام", 5: "خمسة أيام",
    6: "ستة أيام", 7: "سبعة أيام", 8: "ثمانية أيام", 9: "تسعة أيام", 10: "عشرة أيام",
    11: "أحد عشر يوماً", 12: "اثنا عشر يوماً", 13: "ثلاثة عشر يوماً", 14: "أربعة عشر يوماً",
    15: "خمسة عشر يوماً", 19: "تسعة عشر يوماً", 20: "عشرون يوماً", 21: "واحد وعشرون يوماً",
    22: "اثنان وعشرون يوماً", 23: "ثلاثة وعشرون يوماً", 29: "تسعة وعشرون يوماً", 30: "ثلاثون يوماً",
}

RIYALS = {
    50: "خمسون ريالاً",
    100: "مئة ريال",
    150: "مئة وخمسون ريالاً",
    200: "مئتا ريال",
    250: "مئتان وخمسون ريالاً",
    300: "ثلاثمئة ريال",
    500: "خمسمئة ريال",
    550: "خمسمئة وخمسون ريالاً",
    1000: "ألف ريال",
    1050: "ألف وخمسون ريالاً",
    1200: "ألف ومئتا ريال",
    1250: "ألف ومئتان وخمسون ريالاً",
    2000: "ألفا ريال",
    2500: "ألفان وخمسمئة ريال",
    3000: "ثلاثة آلاف ريال",
    5550: "خمسة آلاف وخمسمئة وخمسون ريالاً",
    4750: "أربعة آلاف وسبعمئة وخمسون ريالاً",
    5000: "خمسة آلاف ريال",
    10000: "عشرة آلاف ريال",
}


@pytest.mark.parametrize(("n", "expected"), DAYS.items())
def test_days_agree_with_their_number(n, expected):
    assert in_words(n, DAY) == expected


@pytest.mark.parametrize(("n", "expected"), RIYALS.items())
def test_riyals_agree_with_their_number(n, expected):
    assert in_words(n, RIYAL) == expected


def test_budget_noun_takes_the_accusative_exactly_after_fifty():
    """في المجال المغلق صيغتان فقط: «ريالاً» إن انتهى المبلغ بخمسين، و«ريال» غير ذلك."""
    for budget in BUDGET_VALUES:
        words = in_words(budget, RIYAL)
        expected = "ريالاً" if budget % 100 == 50 else "ريال"
        assert words.split()[-1] == expected, (budget, words)
        assert "مائة" not in words and "ريالات" not in words


def test_every_value_the_interface_can_show_is_supported():
    """
    كل ميزانية وكل مدّة يمكن أن تختارها الواجهة لها كلمات، بلا رقمٍ واحد فيها.

    المجال المغلق في `in_words` يرفض ما ينتهي بواحدٍ أو اثنين بعد المئة؛
    هذا الاختبار يثبت أن الواجهة لا تبلغه.
    """
    for budget in BUDGET_VALUES:
        words = in_words(budget, RIYAL)
        assert words and not any(ch.isdigit() for ch in words), budget
    for days in DAY_VALUES:
        words = in_words(days, DAY)
        assert words and not any(ch.isdigit() for ch in words), days


@pytest.mark.parametrize("value", [0, -1, 1_000_000, 101, 1002, True, 2.0, "5"])
def test_out_of_domain_is_refused_not_guessed(value):
    with pytest.raises(ValueError):
        in_words(value, RIYAL)
