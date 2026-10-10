"""
Open registration in the database (prototype of tests/db/test_open_registration.py).

Runs with the web role against a database migrated to 0007.
"""

from __future__ import annotations

import datetime
import hashlib
import threading

import psycopg
import pytest
from psycopg import errors

from eyework.tests.conftest import UNUSABLE_HASH, as_user

TERMS = "2026-10-10"
_OPEN = "SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s)"
_CODE = "SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s)"


def _hash(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def register_open(app, login: str = "new@example.sa", *, name: str | None = "سارة",
                  birth: datetime.date = datetime.date(1994, 3, 21), profession: str = "MARKETING",
                  terms: str | None = TERMS):
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute(_OPEN, (_hash(login), UNUSABLE_HASH, name, birth, profession, terms))
        return cursor.fetchone()


def issue_code(owner, code: str) -> bytes:
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO signup_codes (code_hash, expires_at) VALUES (%s, now() + interval '1 day')",
                       (_hash(code),))
    return _hash(code)


def register_code(app, code: bytes, login: str):
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute(_CODE, (code, _hash(login), UNUSABLE_HASH, "سارة", datetime.date(1994, 3, 21),
                               "STOREKEEPER", TERMS))
        return cursor.fetchone()


def seed_ledger(owner, kind: str, count: int, *, age: str = "1 hour") -> None:
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO registration_ledger (occurred_at, kind)"
                       " SELECT now() - %s::interval, %s FROM generate_series(1, %s)", (age, kind, count))


def ledger(owner) -> list[str]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT kind FROM registration_ledger ORDER BY occurred_at, kind")
        return [row[0] for row in cursor.fetchall()]


def users(owner) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        return cursor.fetchone()[0]


def test_open_registration_creates_an_active_self_registered_account(owner, app):
    user_id, outcome = register_open(app)
    assert outcome == "OK"
    with owner.cursor() as cursor:
        cursor.execute("SELECT login_hmac, is_active, activated_at IS NOT NULL, self_registered, registered_via,"
                       " terms_version, profession FROM users WHERE id = %s", (user_id,))
        assert cursor.fetchone() == (_hash("new@example.sa"), True, True, True, "OPEN", TERMS, "MARKETING")
    assert ledger(owner) == ["OPEN"]


def test_the_ledger_holds_no_identity(owner, app):
    user_id, _ = register_open(app)
    with owner.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns"
                       " WHERE table_name = 'registration_ledger' ORDER BY column_name")
        assert [row[0] for row in cursor.fetchall()] == ["kind", "occurred_at"]
        cursor.execute("SELECT count(*) FROM pg_constraint WHERE conrelid = 'registration_ledger'::regclass"
                       " AND contype = 'f'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    assert ledger(owner) == ["OPEN"]


def test_a_link_registration_is_recorded_as_code(owner, app):
    user_id, outcome = register_code(app, issue_code(owner, "c"), "linked@example.sa")
    assert outcome == "OK"
    with owner.cursor() as cursor:
        cursor.execute("SELECT registered_via FROM users WHERE id = %s", (user_id,))
        assert cursor.fetchone()[0] == "CODE"
    assert ledger(owner) == ["CODE"]


@pytest.mark.parametrize("existing", ["active", "invited", "deactivated"])
def test_open_registration_never_takes_over_an_existing_login(owner, app, existing):
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac, password_hash, activated_at, is_active, profession)"
            " VALUES (%s, %s, %s, %s, 'SUPPORT')",
            (_hash("taken@example.sa"), None if existing == "invited" else UNUSABLE_HASH,
             None if existing == "invited" else datetime.datetime.now(datetime.timezone.utc),
             existing != "deactivated"))
    assert register_open(app, "taken@example.sa", profession="MARKETING") == (None, "TAKEN")
    with owner.cursor() as cursor:
        cursor.execute("SELECT profession, self_registered, registered_via FROM users")
        assert cursor.fetchall() == [("SUPPORT", False, None)]
    assert ledger(owner) == ["TAKEN"]


def test_a_taken_answer_on_a_link_is_counted_on_the_code_not_in_the_ledger(owner, app):
    register_open(app, "taken@example.sa")
    code = issue_code(owner, "probe")
    assert register_code(app, code, "taken@example.sa") == (None, "TAKEN")
    with owner.cursor() as cursor:
        cursor.execute("SELECT taken_count FROM signup_codes")
        assert cursor.fetchone()[0] == 1
    assert ledger(owner) == ["OPEN"]


@pytest.mark.parametrize("channel", ["open", "code"])
def test_the_daily_cap_counts_both_doors_in_the_ledger(owner, app, channel):
    seed_ledger(owner, "CODE", 100)
    seed_ledger(owner, "OPEN", 49)
    seed_ledger(owner, "OPEN", 30, age="25 hours")
    first = (register_open(app, "a@example.sa") if channel == "open"
             else register_code(app, issue_code(owner, "a"), "a@example.sa"))
    assert first[1] == "OK"
    seed_ledger(owner, "CODE", 50)
    with pytest.raises(errors.CheckViolation) as caught:
        if channel == "open":
            register_open(app, "b@example.sa")
        else:
            register_code(app, issue_code(owner, "b"), "b@example.sa")
    assert caught.value.diag.constraint_name == "registration_daily_cap"


def test_deleting_an_open_account_does_not_make_room(owner, app):
    seed_ledger(owner, "CODE", 199)
    user_id, outcome = register_open(app, "the-200th@example.sa")
    assert outcome == "OK"
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    with pytest.raises(errors.CheckViolation) as caught:
        register_open(app, "the-201st@example.sa")
    assert caught.value.diag.constraint_name == "registration_daily_cap"


def test_open_registrations_have_their_own_cap_and_links_keep_working(owner, app):
    seed_ledger(owner, "OPEN", 150)
    with pytest.raises(errors.CheckViolation) as caught:
        register_open(app, "late@example.sa")
    assert caught.value.diag.constraint_name == "registration_open_daily_cap"
    assert register_code(app, issue_code(owner, "c"), "linked@example.sa")[1] == "OK"


@pytest.mark.parametrize("email", ["free@example.sa", "taken@example.sa"])
def test_fifty_taken_answers_pause_open_registration_for_every_email(owner, app, email):
    register_open(app, "taken@example.sa")
    seed_ledger(owner, "TAKEN", 50)
    with pytest.raises(errors.CheckViolation) as caught:
        register_open(app, email)
    assert caught.value.diag.constraint_name == "registration_open_paused"
    assert ledger(owner).count("TAKEN") == 50
    assert register_code(app, issue_code(owner, "c"), "linked@example.sa")[1] == "OK"


def test_taken_answers_older_than_a_day_do_not_pause(owner, app):
    seed_ledger(owner, "TAKEN", 50, age="25 hours")
    assert register_open(app)[1] == "OK"


def test_the_open_state_is_ok_full_or_paused(owner, app):
    def state():
        as_user(app, None)
        with app.cursor() as cursor:
            cursor.execute("SELECT ew_open_registration_state()")
            return cursor.fetchone()[0]
    assert state() == "OK"
    seed_ledger(owner, "TAKEN", 50)
    assert state() == "PAUSED"
    seed_ledger(owner, "OPEN", 150)
    assert state() == "FULL"


@pytest.mark.parametrize(("overrides", "constraint"), [
    ({"name": None}, "registration_needs_name"),
    ({"name": "سارة2"}, "display_name_shape"),
    ({"birth": datetime.date(2999, 1, 1)}, "registration_birth_date"),
    ({"terms": None}, "registration_needs_consent"),
])
def test_an_invalid_open_registration_leaves_no_trace(owner, app, overrides, constraint):
    with pytest.raises(errors.CheckViolation) as caught:
        register_open(app, **overrides)
    assert caught.value.diag.constraint_name == constraint
    assert users(owner) == 0
    assert ledger(owner) == []


def test_registered_via_matches_self_registered(owner):
    with owner.cursor() as cursor:
        with pytest.raises(errors.CheckViolation) as caught:
            cursor.execute("INSERT INTO users (login_hmac, profession, self_registered, terms_version,"
                           " terms_accepted_at) VALUES (%s, 'MARKETING', true, %s, now())", (_hash("x"), TERMS))
        assert caught.value.diag.constraint_name == "registered_via_iff_self"
        with pytest.raises(errors.CheckViolation) as caught:
            cursor.execute("INSERT INTO users (login_hmac, profession, registered_via) VALUES (%s, 'MARKETING', 'OPEN')",
                           (_hash("y"),))
        assert caught.value.diag.constraint_name == "registered_via_iff_self"


@pytest.mark.parametrize("statement", [
    "SELECT * FROM registration_ledger",
    "INSERT INTO registration_ledger (kind) VALUES ('OPEN')",
    "UPDATE registration_ledger SET kind = 'CODE'",
    "DELETE FROM registration_ledger",
    "SELECT ew_registration_refusal('OPEN')",
    "SELECT ew_register_account('OPEN', sha256('x'::bytea), NULL, 'سارة', DATE '1990-01-01', 'MARKETING', '2026-10-10')",
    "SELECT ew_is_newcomer(gen_random_uuid())",
    "SELECT ew_generation_cap(gen_random_uuid())",
])
def test_the_web_role_cannot_touch_the_ledger_or_the_internal_helpers(app, statement):
    as_user(app, None)
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute(statement)


def test_two_concurrent_open_registrations_cannot_both_take_the_last_place(owner, app_url):
    seed_ledger(owner, "OPEN", 149)
    first = psycopg.connect(app_url)
    second = psycopg.connect(app_url, autocommit=True)
    try:
        with first.cursor() as cursor:
            cursor.execute(_OPEN, (_hash("one@example.sa"), UNUSABLE_HASH, "سارة", datetime.date(1990, 1, 1),
                                   "MARKETING", TERMS))
            assert cursor.fetchone()[1] == "OK"
        outcome = {}

        def other():
            try:
                with second.cursor() as cursor:
                    cursor.execute(_OPEN, (_hash("two@example.sa"), UNUSABLE_HASH, "ليلى",
                                           datetime.date(1990, 1, 1), "MARKETING", TERMS))
                    outcome["result"] = cursor.fetchone()
            except errors.CheckViolation as exc:
                outcome["result"] = exc.diag.constraint_name

        thread = threading.Thread(target=other)
        thread.start()
        thread.join(timeout=1.0)
        assert thread.is_alive(), "the second registration must wait on the first one's lock"
        first.commit()
        thread.join(timeout=10)
        assert outcome["result"] == "registration_open_daily_cap"
    finally:
        first.close()
        second.close()
    assert users(owner) == 1


def test_revoking_open_registration_closes_it_and_the_state_says_so(owner, app):
    """`admin open-registration off`: the operator's stop, in the database itself, without a restart."""
    signature = "ew_register_open(bytea, text, text, date, text, text)"
    with owner.cursor() as cursor:
        cursor.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM eyework_app")
    try:
        as_user(app, None)
        with app.cursor() as cursor:
            cursor.execute("SELECT ew_open_registration_state()")
            assert cursor.fetchone()[0] == "CLOSED"
        with pytest.raises(errors.InsufficientPrivilege) as caught:
            register_open(app)
        assert caught.value.diag.constraint_name is None
        assert register_code(app, issue_code(owner, "c"), "linked@example.sa")[1] == "OK"
    finally:
        with owner.cursor() as cursor:
            cursor.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO eyework_app")
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_open_registration_state()")
        assert cursor.fetchone()[0] == "OK"
