"""
AI spend for brand-new open accounts (prototype of tests/db/test_newcomer_caps.py).
"""

from __future__ import annotations

import datetime
import hashlib
from datetime import timedelta

import pytest
from psycopg import errors

from eyework.tests.conftest import UNUSABLE_HASH, as_user, make_user
from eyework.tests.db.test_generation_caps import begin, finish, new_campaign, seed_attempts

TERMS = "2026-10-10"
PAST_RATE_WINDOW = timedelta(minutes=11)


def open_account(app, login: str = "new@example.sa"):
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT new_user FROM ew_register_open(%s, %s, %s, %s, %s, %s)",
                       (hashlib.sha256(login.encode()).digest(), UNUSABLE_HASH, "سارة",
                        datetime.date(1990, 1, 1), "MARKETING", TERMS))
        return cursor.fetchone()[0]


def age_account(owner, user, hours: int) -> None:
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET created_at = now() - make_interval(hours => %s) WHERE id = %s",
                       (hours, user))


def my_cap(app, user):
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_my_generation_cap()")
        return cursor.fetchone()[0]


def seed_tombstones(owner, count: int, *, newcomer: bool, outcome: str = "OUTPUT_INVALID") -> None:
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome, newcomer)"
                       " SELECT now() - interval '1 hour', %s, %s FROM generate_series(1, %s)",
                       (outcome, newcomer, count))


def test_an_open_account_gets_ten_a_day_for_its_first_three_days(owner, app):
    user = open_account(app)
    campaign = new_campaign(app, user)
    seed_attempts(owner, user, new_campaign(app, user, with_image=False), 9,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(minutes=37))
    tenth = begin(app, user, campaign)
    finish(app, user, tenth, "UPSTREAM_TIMEOUT")
    with pytest.raises(errors.CheckViolation) as caught:
        begin(app, user, campaign)
    assert caught.value.diag.constraint_name == "generation_daily_cap"


def test_after_three_days_an_open_account_gets_forty(owner, app):
    user = open_account(app)
    age_account(owner, user, 73)
    campaign = new_campaign(app, user)
    seed_attempts(owner, user, new_campaign(app, user, with_image=False), 10,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(minutes=37))
    attempt = begin(app, user, campaign)
    with owner.cursor() as cursor:
        cursor.execute("SELECT newcomer FROM generation_attempts WHERE id = %s", (attempt,))
        assert cursor.fetchone()[0] is False


@pytest.mark.parametrize("kind", ["invited", "link"])
def test_invited_and_link_accounts_are_never_newcomers(owner, app, kind):
    if kind == "invited":
        user = make_user(owner, login=b"invited")
    else:
        user = open_account(app)
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET registered_via = 'CODE' WHERE id = %s", (user,))
    assert my_cap(app, user) == 40
    attempt = begin(app, user, new_campaign(app, user))
    with owner.cursor() as cursor:
        cursor.execute("SELECT newcomer FROM generation_attempts WHERE id = %s", (attempt,))
        assert cursor.fetchone()[0] is False


def test_the_cap_is_read_for_the_session_alone(owner, app):
    user = open_account(app)
    assert my_cap(app, user) == 10
    age_account(owner, user, 73)
    assert my_cap(app, user) == 40
    assert my_cap(app, None) is None


def test_the_newcomer_flag_is_fixed_when_the_attempt_starts(owner, app):
    user = open_account(app)
    attempt = begin(app, user, new_campaign(app, user))
    age_account(owner, user, 73)
    with owner.cursor() as cursor:
        cursor.execute("SELECT newcomer FROM generation_attempts WHERE id = %s", (attempt,))
        assert cursor.fetchone()[0] is True


def test_newcomers_share_four_hundred_a_day_and_others_are_unaffected(owner, app):
    newcomer = open_account(app)
    regular = make_user(owner, login=b"regular")
    seed_tombstones(owner, 399, newcomer=True)
    last = begin(app, newcomer, new_campaign(app, newcomer))
    finish(app, newcomer, last, "OUTPUT_INVALID")
    other = open_account(app, "second@example.sa")
    with pytest.raises(errors.CheckViolation) as caught:
        begin(app, other, new_campaign(app, other))
    assert caught.value.diag.constraint_name == "generation_newcomer_pool"
    assert begin(app, regular, new_campaign(app, regular)) is not None


def test_unbilled_outcomes_do_not_fill_the_pool(owner, app):
    seed_tombstones(owner, 400, newcomer=True, outcome="UPSTREAM_BUSY")
    seed_tombstones(owner, 400, newcomer=False)
    user = open_account(app)
    assert begin(app, user, new_campaign(app, user)) is not None


def test_deleting_a_newcomer_keeps_its_attempts_in_the_pool(owner, app):
    user = open_account(app)
    attempt = begin(app, user, new_campaign(app, user))
    finish(app, user, attempt, "OUTPUT_INVALID")
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user,))
        cursor.execute("SELECT outcome, newcomer FROM attempt_tombstones")
        assert cursor.fetchall() == [("OUTPUT_INVALID", True)]
    seed_tombstones(owner, 399, newcomer=True)
    other = open_account(app, "second@example.sa")
    with pytest.raises(errors.CheckViolation) as caught:
        begin(app, other, new_campaign(app, other))
    assert caught.value.diag.constraint_name == "generation_newcomer_pool"
