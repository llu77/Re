"""
«سيمبول» واسم المستخدم (الترحيل 0003)
======================================
الاسم الذي يناديه به المساعد يبقى في قاعدة التطبيق: دور الويب لا يقرأ جدول
المستخدمين، ويصله اسم صاحب الجلسة وحده عبر `ew_my_display_name`. وكلمة المساعد
تُحفظ مع النسخة، قصيرةً وفي سطرٍ واحد.
"""

from __future__ import annotations

import pytest
from psycopg import errors

from eyework.tests.conftest import as_user, make_user


def _name(owner, user, value):
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = %s WHERE id = %s", (value, user))


def _my_name(app):
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_my_display_name()")
        return cursor.fetchone()[0]


def test_each_user_reads_only_their_own_name(owner, app, two_users):
    mine, theirs = two_users
    _name(owner, mine, "عمر")
    _name(owner, theirs, "سارة")
    as_user(app, mine)
    assert _my_name(app) == "عمر"
    as_user(app, theirs)
    assert _my_name(app) == "سارة"


@pytest.mark.parametrize("who", ["anonymous", "inactive"])
def test_no_name_without_an_active_identity(owner, app, two_users, who):
    user, _ = two_users
    _name(owner, user, "عمر")
    if who == "inactive":
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET is_active = false WHERE id = %s", (user,))
    as_user(app, None if who == "anonymous" else user)
    assert _my_name(app) is None


def test_the_app_still_cannot_read_the_users_table(app, two_users):
    user, _ = two_users
    as_user(app, user)
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute("SELECT display_name FROM users")


@pytest.mark.parametrize("value", ["عمر", "Omar Ali", "عبد الله", "ا" * 30])
def test_a_name_people_are_called_by_is_accepted(owner, value):
    user = make_user(owner, login=b"named")
    _name(owner, user, value)


@pytest.mark.parametrize("value", ["", " عمر", "عمر ", "عبد  الله", "عمر1", "عُمر", "ـعمر", "o@x", "ا" * 31])
def test_anything_else_is_refused(owner, value):
    user = make_user(owner, login=b"named")
    with pytest.raises(errors.CheckViolation) as caught:
        _name(owner, user, value)
    assert caught.value.diag.constraint_name == "display_name_shape"


def _version_with_note(app, user, campaign, note):
    """نسخةٌ أولى بالمسار الإنتاجي، بكلمة المساعد المعطاة."""
    from eyework.tests.conftest import DESCRIPTION, TITLE, row_version

    as_user(app, user)
    with app.transaction(), app.cursor() as cursor:
        cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, row_version(app, campaign)))
        attempt = cursor.fetchone()[0]
    try:
        with app.transaction(), app.cursor() as cursor:
            cursor.execute(
                "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
                " served_model, prompt_version, assistant_note)"
                " VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test', %s)",
                (campaign, user, attempt, TITLE, DESCRIPTION, note),
            )
            cursor.execute("SELECT ew_finish_generation(%s, 'OK', 0, 0)", (attempt,))
    finally:
        with app.cursor() as cursor:
            cursor.execute("SELECT ew_finish_generation(%s, 'OUTPUT_INVALID', 0, 0)"
                           " FROM generation_attempts WHERE id = %s AND finished_at IS NULL", (attempt, attempt))


@pytest.mark.parametrize("note", ["", "ا" * 121, "سطرٌ\nثانٍ"], ids=["empty", "121", "two-lines"])
def test_a_long_or_multiline_assistant_note_is_refused(app, two_users, note):
    from eyework.tests.conftest import create_campaign

    user, _ = two_users
    campaign = create_campaign(app, user)
    with pytest.raises(errors.CheckViolation) as caught:
        _version_with_note(app, user, campaign, note)
    assert caught.value.diag.constraint_name == "assistant_note_shape"


@pytest.mark.parametrize("note", [None, "ا" * 120], ids=["none", "120"])
def test_a_short_assistant_note_or_none_is_stored(app, two_users, note):
    from eyework.tests.conftest import create_campaign

    user, _ = two_users
    campaign = create_campaign(app, user)
    _version_with_note(app, user, campaign, note)
    with app.cursor() as cursor:
        cursor.execute("SELECT assistant_note FROM copy_versions WHERE campaign_id = %s", (campaign,))
        assert cursor.fetchone()[0] == note
