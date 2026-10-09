"""
أداة المشغّل والمهن
===================
حساب الدعوة يسمّي مهنته عند الإنشاء، وتغييرها للمشغّل وحده — بالأمر نفسه الذي
يُشغَّل في الإنتاج.
"""

from __future__ import annotations

import base64
import threading
import time

import psycopg
import pytest
from psycopg import errors

from eyework import admin, auth, campaigns
from eyework.tests.conftest import as_user, make_user
from eyework.tests.db.test_state_machine import blocked_on_a_lock

KEY = b"a" * 32


@pytest.fixture
def operator(owner, owner_url, monkeypatch):
    monkeypatch.setenv("EYEWORK_OWNER_DATABASE_URL", owner_url)
    monkeypatch.setenv("EYEWORK_LOGIN_KEY", base64.b64encode(KEY).decode())
    monkeypatch.setenv("EYEWORK_PUBLIC_ORIGIN", "https://work.example.sa")
    return owner


def _profession(owner, login: str) -> str:
    with owner.cursor() as cursor:
        cursor.execute("SELECT profession FROM users WHERE login_hmac = %s", (auth.login_hmac(KEY, login),))
        return cursor.fetchone()[0]


def test_create_user_records_the_profession(operator, capsys):
    code = admin.main(["create-user", "--login", "keeper@example.sa", "--profession", "STOREKEEPER"])
    assert code == 0
    assert capsys.readouterr().out.startswith("https://work.example.sa/#activate=")
    assert _profession(operator, "keeper@example.sa") == "STOREKEEPER"


def test_create_user_needs_a_known_profession(operator):
    with pytest.raises(SystemExit):
        admin.main(["create-user", "--login", "x@example.sa"])
    with pytest.raises(SystemExit):
        admin.main(["create-user", "--login", "x@example.sa", "--profession", "ASTRONAUT"])
    with operator.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 0


def test_set_profession_moves_the_account(operator, capsys):
    admin.main(["create-user", "--login", "agent@example.sa", "--profession", "MARKETING"])
    assert admin.main(["set-profession", "--login", "agent@example.sa", "--profession", "SUPPORT"]) == 0
    assert "الدعم الفني" in capsys.readouterr().out
    assert _profession(operator, "agent@example.sa") == "SUPPORT"


def test_set_profession_on_an_unknown_account_fails_cleanly(operator, capsys):
    assert admin.main(["set-profession", "--login", "nobody@example.sa", "--profession", "SUPPORT"]) == 1
    assert "خطأ" in capsys.readouterr().err


def test_set_profession_to_the_same_profession_is_refused(operator, capsys):
    admin.main(["create-user", "--login", "agent@example.sa", "--profession", "SUPPORT"])
    assert admin.main(["set-profession", "--login", "agent@example.sa", "--profession", "SUPPORT"]) == 1
    assert "أصلاً" in capsys.readouterr().err


def test_leaving_marketing_cancels_open_campaigns_and_keeps_ready_ones(operator, app, capsys):
    from eyework.tests.conftest import add_version, create_campaign
    from eyework.tests.db.test_generation_caps import move_to

    admin.main(["create-user", "--login", "seller@example.sa", "--profession", "MARKETING"])
    with operator.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE login_hmac = %s", (auth.login_hmac(KEY, "seller@example.sa"),))
        seller = cursor.fetchone()[0]
        cursor.execute("UPDATE users SET password_hash = %s, activated_at = now() WHERE id = %s",
                       ("scrypt$" + "0" * 32 + "$" + "0" * 128, seller))
    open_one = create_campaign(app, seller)
    ready_one = create_campaign(app, seller)
    add_version(app, seller, ready_one)
    move_to(app, seller, ready_one, "READY")

    assert admin.main(["set-profession", "--login", "seller@example.sa", "--profession", "STOREKEEPER"]) == 0
    assert "وأُلغيت 1 حملةً مفتوحة" in capsys.readouterr().out
    with operator.cursor() as cursor:
        cursor.execute("SELECT id, status FROM campaigns ORDER BY status")
        assert dict(cursor.fetchall()) == {open_one: "CANCELLED", ready_one: "READY"}
        cursor.execute("SELECT count(*) FROM campaign_images WHERE campaign_id = %s", (open_one,))
        assert cursor.fetchone()[0] == 0


def _the_operator_waits_on_a_lock(owner, racer: threading.Thread) -> bool:
    """أمر المشغّل يتّصل بدور المالك، فحالته تُرى من اتصال المالك."""
    deadline = time.monotonic() + 5
    while racer.is_alive() and time.monotonic() < deadline:
        with owner.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                           " AND datname = current_database() AND usename = current_user")
            if cursor.fetchone()[0]:
                return True
        time.sleep(0.01)
    return False


def _seller(operator):
    return make_user(operator, login=auth.login_hmac(KEY, "seller@example.sa"), profession="MARKETING")


def test_a_campaign_created_while_leaving_marketing_is_still_cancelled(operator, app_url):
    """الحملة تُدرَج ولم تُثبَّت بعد، والمشغّل ينقل الحساب: ينتظرها الأمر ثم يلغيها، فلا تبقى مسودةٌ بصورتها."""
    seller = _seller(operator)
    with psycopg.connect(app_url) as web:
        as_user(web, seller)
        with web.cursor() as cursor:
            cursor.execute(campaigns._INSERT_CAMPAIGN, (seller,))
        mover = threading.Thread(target=admin.set_profession, args=("seller@example.sa", "SUPPORT"))
        mover.start()
        waited = _the_operator_waits_on_a_lock(operator, mover)
        web.commit()
        mover.join(timeout=10)
    assert waited
    with operator.cursor() as cursor:
        cursor.execute("SELECT u.profession, c.status FROM campaigns c JOIN users u ON u.id = c.user_id")
        assert cursor.fetchall() == [("SUPPORT", "CANCELLED")]


def test_a_campaign_cannot_start_while_the_account_leaves_marketing(operator, app, owner_url, app_url):
    """المشغّل قفل الصفّ ولم يُثبِّت: الإدراج ينتظره ثم يقرأ المهنة الجديدة فيُرفض."""
    seller = _seller(operator)
    outcome = {}
    with psycopg.connect(owner_url) as mover, psycopg.connect(app_url) as web:
        as_user(web, seller)
        web.commit()
        with mover.cursor() as cursor:
            cursor.execute(admin._PROFESSION_OF, (seller,))
            cursor.execute(admin._CANCEL_OPEN_CAMPAIGNS, (seller,))
            cursor.execute(admin._SET_PROFESSION, ("STOREKEEPER", seller))

        def insert() -> None:
            try:
                with web.cursor() as cursor:
                    cursor.execute(campaigns._INSERT_CAMPAIGN, (seller,))
                web.commit()
                outcome["inserted"] = True
            except errors.InsufficientPrivilege as exc:
                web.rollback()
                outcome["constraint"] = exc.diag.constraint_name

        racer = threading.Thread(target=insert)
        racer.start()
        waited = blocked_on_a_lock(app, web.info.backend_pid, racer)
        mover.commit()
        racer.join(timeout=10)
    assert waited
    assert outcome == {"constraint": "campaign_needs_marketing"}
    with operator.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaigns")
        assert cursor.fetchone()[0] == 0


def test_issue_signup_codes_prints_one_link_per_code_and_stores_only_hashes(operator, capsys):
    assert admin.main(["issue-signup-codes", "--count", "3", "--hours", "48", "--label", "riyadh-oct"]) == 0
    links = capsys.readouterr().out.split()
    assert len(links) == 3 and len(set(links)) == 3
    codes = [link.split("#signup=", 1)[1] for link in links]
    assert all(link.startswith("https://work.example.sa/#signup=") for link in links)
    with operator.cursor() as cursor:
        cursor.execute("SELECT code_hash, label, expires_at - created_at FROM signup_codes")
        rows = cursor.fetchall()
    assert {bytes(row[0]) for row in rows} == {auth.hash_token(code) for code in codes}
    assert {row[1] for row in rows} == {"riyadh-oct"}
    assert {row[2].total_seconds() for row in rows} == {48 * 3600}


@pytest.mark.parametrize("arguments", [["--count", "0"], ["--count", "201"], ["--count", "1", "--hours", "721"],
                                       ["--count", "1", "--label", "رياض"]])
def test_issue_signup_codes_refuses_out_of_range_requests(operator, capsys, arguments):
    assert admin.main(["issue-signup-codes", *arguments]) == 1
    with operator.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM signup_codes")
        assert cursor.fetchone()[0] == 0


def test_reissue_for_a_self_registered_account_needs_the_operators_word(operator, capsys):
    with operator.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac, password_hash, activated_at, profession, self_registered,"
            " terms_version, terms_accepted_at) VALUES (%s, %s, now(), 'SUPPORT', true, '2026-10-08', now())",
            (auth.login_hmac(KEY, "self@example.sa"), "scrypt$" + "0" * 32 + "$" + "0" * 128))
    assert admin.main(["reissue-activation", "--login", "self@example.sa"]) == 1
    assert "--owner-verified" in capsys.readouterr().err
    with operator.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM activation_tokens")
        assert cursor.fetchone()[0] == 0
    assert admin.main(["reissue-activation", "--login", "self@example.sa", "--owner-verified"]) == 0
    assert "#activate=" in capsys.readouterr().out


def test_create_user_over_an_existing_account_does_not_suggest_a_reissue(operator, capsys):
    admin.main(["create-user", "--login", "dup@example.sa", "--profession", "MARKETING"])
    capsys.readouterr()
    assert admin.main(["create-user", "--login", "dup@example.sa", "--profession", "MARKETING"]) == 1
    message = capsys.readouterr().err
    assert "reissue" not in message and "التحقّق" in message
