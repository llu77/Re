"""
الحذف الدوري (`python -m eyework.admin purge`)
==============================================
ما يُحذف يُحذف بلا رجعة، فيُختبر حدّه من الجانبين: الحملة الخاملة فعلاً تُحذف،
والتي عُمل عليها — بتغيير صورتها أو بمحاولة كتابة — تبقى. وما تعدّه السقوف من
محاولات اليوم لا يُمحى بحذف حملته.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta

import pytest

from eyework import admin
from eyework.tests.conftest import add_version, as_user, create_campaign, sample_jpeg


@pytest.fixture
def purge(owner_url, monkeypatch):
    monkeypatch.setenv("EYEWORK_OWNER_DATABASE_URL", owner_url)
    return admin.purge


@contextmanager
def guards_off(owner, table: str, *triggers: str):
    """الحرّاس يكتبون الأوقات بأنفسهم؛ الاختبار يعيدها إلى الماضي بيد مالك الجدول."""
    with owner.cursor() as cursor:
        for trigger in triggers:
            cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    try:
        yield
    finally:
        with owner.cursor() as cursor:
            for trigger in triggers:
                cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")


def age_campaign(owner, campaign, by: timedelta, *, column="updated_at"):
    with guards_off(owner, "campaigns", "trg_campaign_guard"), owner.cursor() as cursor:
        cursor.execute(f"UPDATE campaigns SET {column} = now() - %s WHERE id = %s", (by, campaign))


def age_image(owner, campaign, by: timedelta):
    with guards_off(owner, "campaign_images", "trg_image_touch", "trg_image_guard"), owner.cursor() as cursor:
        cursor.execute("UPDATE campaign_images SET updated_at = now() - %s WHERE campaign_id = %s", (by, campaign))


def age_attempts(owner, campaign, by: timedelta):
    with guards_off(owner, "generation_attempts", "trg_attempt_settle"), owner.cursor() as cursor:
        cursor.execute("UPDATE generation_attempts SET started_at = started_at - %s,"
                       " finished_at = finished_at - %s WHERE campaign_id = %s", (by, by, campaign))


def exists(owner, campaign) -> bool:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaigns WHERE id = %s", (campaign,))
        return cursor.fetchone()[0] == 1


def test_a_draft_idle_for_thirty_days_is_deleted(owner, app, two_users, purge):
    user, _ = two_users
    campaign = create_campaign(app, user)
    age_image(owner, campaign, timedelta(days=31))
    age_campaign(owner, campaign, timedelta(days=31))
    purge()
    assert not exists(owner, campaign)


def test_a_draft_whose_photo_changed_today_is_kept(owner, app, two_users, purge):
    """استبدال الصورة لا يغيّر الحملة نفسها؛ كان الحذف يراها خاملةً منذ إنشائها."""
    user, _ = two_users
    campaign = create_campaign(app, user)
    # الصورة نفسها قديمة أيضاً: لا يجعلها حديثةً إلا محفّز اللمس عند الاستبدال.
    age_image(owner, campaign, timedelta(days=31))
    age_campaign(owner, campaign, timedelta(days=31))
    import hashlib

    jpeg = sample_jpeg()
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("UPDATE campaign_images SET jpeg = %s, sha256 = %s WHERE campaign_id = %s",
                       (jpeg, hashlib.sha256(jpeg + b"x").digest(), campaign))
    purge()
    assert exists(owner, campaign)


def test_without_the_touch_trigger_that_draft_would_be_deleted(owner, app, two_users, purge):
    """يثبت أن الاختبار السابق يحرس المحفّز: بدونه تُحذف المسودة نفسها."""
    import hashlib

    user, _ = two_users
    campaign = create_campaign(app, user)
    age_image(owner, campaign, timedelta(days=31))
    age_campaign(owner, campaign, timedelta(days=31))
    jpeg = sample_jpeg()
    as_user(app, user)
    with guards_off(owner, "campaign_images", "trg_image_touch"), app.cursor() as cursor:
        cursor.execute("UPDATE campaign_images SET jpeg = %s, sha256 = %s WHERE campaign_id = %s",
                       (jpeg, hashlib.sha256(jpeg + b"x").digest(), campaign))
    purge()
    assert not exists(owner, campaign)


def test_a_campaign_with_a_recent_attempt_is_kept(owner, app, two_users, purge):
    user, _ = two_users
    campaign = create_campaign(app, user)
    add_version(app, user, campaign)
    age_image(owner, campaign, timedelta(days=40))
    age_attempts(owner, campaign, timedelta(days=2))
    age_campaign(owner, campaign, timedelta(days=40))
    purge()
    assert exists(owner, campaign)


def test_todays_counted_attempts_survive_even_on_a_final_campaign(owner, app, two_users, purge):
    """حذفها يستردّ لصاحبها حصّةً دُفعت، ويُنقص العدّ العام."""
    user, _ = two_users
    campaign = create_campaign(app, user)
    add_version(app, user, campaign)
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s", (campaign,))
    age_campaign(owner, campaign, timedelta(days=91), column="cancelled_at")
    purge()
    assert exists(owner, campaign)
    age_attempts(owner, campaign, timedelta(days=2))
    purge()
    assert not exists(owner, campaign)


@pytest.mark.parametrize(("age", "deleted"), [(timedelta(days=89), False), (timedelta(days=91), True)])
def test_cancelled_campaigns_go_after_ninety_days(owner, app, two_users, purge, age, deleted):
    user, _ = two_users
    campaign = create_campaign(app, user)
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s", (campaign,))
    age_campaign(owner, campaign, age, column="cancelled_at")
    purge()
    assert exists(owner, campaign) is not deleted
