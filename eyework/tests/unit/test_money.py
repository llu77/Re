"""
الميزانية والمدّة
=================
مجالٌ مغلق، وخطواتٌ لا تلتفّ ولا تقصّ بصمت، ومبلغٌ يومي عشريّ يقول متى هو
تقريبي. ومقارنة المجال بنظيره في القاعدة في `db/test_state_machine.py`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from eyework import money


def test_budget_domain_is_36_sorted_unique_values():
    values = money.BUDGET_VALUES
    assert len(values) == 36
    assert list(values) == sorted(set(values))
    assert values[0] == 50 and values[-1] == 5000
    assert 1000 in values and 1100 not in values and 1250 in values


def test_presets_lie_inside_their_domains():
    assert set(money.BUDGET_PRESETS) <= set(money.BUDGET_VALUES)
    assert set(money.DAY_PRESETS) <= set(money.DAY_VALUES)
    assert len(money.BUDGET_PRESETS) == len(money.DAY_PRESETS) == 6


@pytest.mark.parametrize(("value", "valid"), [
    (50, True), (5000, True), (1250, True), (0, False), (49, False), (75, False),
    (1100, False), (5250, False), (True, False), ("500", False), (500.0, False),
])
def test_budget_validity(value, valid):
    assert money.is_valid_budget(value) is valid


def test_days_validity():
    assert all(money.is_valid_days(d) for d in range(1, 31))
    assert not any(money.is_valid_days(d) for d in (0, 31, -1, True, "7"))


def test_steppers_respect_bounds_without_wrapping():
    budgets = money.BUDGET_VALUES
    assert money.step_up(budgets, 1000) == 1250
    assert money.step_down(budgets, 1250) == 1000
    assert money.step_down(budgets, 50) is None
    assert money.step_up(budgets, 5000) is None
    # بلا قيمةٍ بعد: «أكثر» إلى أصغر قيمة، و«أقل» لا شيء — لا افتراض.
    assert money.step_up(budgets, None) == 50
    assert money.step_down(budgets, None) is None


def test_every_value_is_a_few_dwells_from_a_preset():
    """أبعد ميزانيةٍ على خمس نظرات من أقرب خيار، وأبعد مدّةٍ على أربع."""
    def distance(values, presets, target):
        index = values.index(target)
        return min(abs(index - values.index(p)) for p in presets)

    assert max(distance(money.BUDGET_VALUES, money.BUDGET_PRESETS, v) for v in money.BUDGET_VALUES) <= 5
    assert max(distance(money.DAY_VALUES, money.DAY_PRESETS, d) for d in money.DAY_VALUES) <= 4


@pytest.mark.parametrize(("budget", "days", "amount", "exact"), [
    (2500, 14, Decimal("178.57"), False),
    (50, 16, Decimal("3.13"), False),    # ‎3.125 ⇒ 3.13: النصف إلى الأعلى
    (3000, 30, Decimal("100.00"), True),
    (1000, 4, Decimal("250.00"), True),
    (500, 7, Decimal("71.43"), False),
])
def test_daily_amount_is_decimal_half_up_with_exact_flag(budget, days, amount, exact):
    assert money.daily_amount(budget, days) == (amount, exact)


@pytest.mark.parametrize(("days", "short"), [
    (1, "يوم واحد"), (2, "يومان"), (3, "3 أيام"), (10, "10 أيام"), (11, "11 يوماً"), (30, "30 يوماً"),
])
def test_short_day_labels_agree_with_their_number(days, short):
    assert money.days_short(days) == short


def test_short_budget_label():
    assert money.budget_short(2750) == "2,750 ر.س"


def test_choices_cover_both_domains_with_words():
    payload = money.choices()
    assert [v["sar"] for v in payload["budget"]["values"]] == list(money.BUDGET_VALUES)
    assert [v["n"] for v in payload["days"]["values"]] == list(money.DAY_VALUES)
    assert all(v["words"] and not any(c.isdigit() for c in v["words"]) for v in payload["budget"]["values"])
