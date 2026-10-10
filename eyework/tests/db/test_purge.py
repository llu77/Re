"""
الحذف الدوري (`python -m eyework.admin purge`)
==============================================
ما يُحذف يُحذف بلا رجعة، فيُختبر حدّه من الجانبين: الحملة الخاملة فعلاً تُحذف،
والتي عُمل عليها — بتغيير صورتها أو بمحاولة كتابة — تبقى. وما تعدّه السقوف من
محاولات اليوم لا يُمحى بحذف حملته. ودفتر التسجيل يذهب بعد يومه، ودفتر استدعاءات
النموذج بعد ثلاثين يوماً بلا أثر، والتنبيه الذي لم يُعتمد عمله بعد ثلاثين يوماً
بقراراته؛ والمعتمد يبقى بقراراته وإن حُذف دفتره أو مُحيت نصوصه.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from eyework import admin
from eyework.tests.conftest import add_version, as_user, create_campaign, make_user, sample_jpeg


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



@pytest.mark.parametrize(("created", "used", "deleted"), [
    (timedelta(days=61), None, True),                  # انتهى قبل 31 يوماً
    (timedelta(days=50), None, False),                 # انتهى قبل 20 يوماً
    (timedelta(days=40), timedelta(days=31), True),    # استُعمل قبل 31 يوماً
    (timedelta(days=20), timedelta(days=10), False),   # استُعمل قبل 10 أيام
])
def test_signup_codes_go_thirty_days_after_they_expire_or_are_used(owner, purge, created, used, deleted):
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO signup_codes (code_hash, created_at, expires_at, used_at)"
            " VALUES (%s, now() - %s, now() - %s + interval '30 days', now() - %s::interval)",
            (b"c" * 32, created, created, used))
    assert purge()["signup_codes"] == (1 if deleted else 0)
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM signup_codes")
        assert cursor.fetchone()[0] == (0 if deleted else 1)


def test_traces_of_deleted_attempts_go_after_their_day(owner, purge):
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome) VALUES"
                       " (now() - interval '25 hours', 'OK'), (now() - interval '1 hour', 'OK')")
    assert purge()["attempt_tombstones"] == 1
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM attempt_tombstones")
        assert cursor.fetchone()[0] == 1


@pytest.mark.parametrize(("age", "deleted"), [
    (timedelta(minutes=4), False),                     # ما زال في مهلته
    (timedelta(minutes=6), True),                      # انتهت مهلته قبل دقيقة
])
@pytest.mark.parametrize("used", [False, True])
def test_passkey_challenges_go_once_their_five_minutes_are_over(owner, purge, age, deleted, used):
    """الحذف بالمهلة وحدها، مستعملاً كان التحدّي أو لا: ما في مهلته قد يكون طقساً لم يكتمل بعد."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO passkey_challenges (challenge_hash, purpose, created_at, expires_at, used_at)"
            " VALUES (%s, 'LOGIN', now() - %s, now() - %s + interval '5 minutes',"
            "         CASE WHEN %s THEN now() - %s END)",
            (b"p" * 32, age, age, used, age))
    assert purge()["passkey_challenges"] == (1 if deleted else 0)
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM passkey_challenges")
        assert cursor.fetchone()[0] == (0 if deleted else 1)


# ── دفتر التسجيل (0008) ──────────────────────────────────────────────────
def test_registration_ledger_rows_go_after_their_day(owner, purge):
    """السقوف تُعدّ من آخر يوم وحده؛ صفٌّ أقدم لا يُقرأ لشيء، وما في يومه يبقى ليُعدّ — بنتيجته أيّاً كانت."""
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO registration_ledger (occurred_at, via, outcome) VALUES"
                       " (now() - interval '25 hours', 'OPEN', 'OK'), (now() - interval '25 hours', 'CODE', 'OK'),"
                       " (now() - interval '23 hours', 'OPEN', 'TAKEN'), (now() - interval '1 hour', 'OPEN', 'OK')")
    assert purge()["registration_ledger"] == 2
    with owner.cursor() as cursor:
        cursor.execute("SELECT via, outcome FROM registration_ledger ORDER BY occurred_at")
        assert cursor.fetchall() == [("OPEN", "TAKEN"), ("OPEN", "OK")]


# ── دفتر استدعاءات النموذج وتنبيهاته (0009) ─────────────────────────────
REASON = "سعر الوحدة في السطر 1 أعلى بكثير من المعتاد لهذا الصنف."


def seed_request(owner, user: UUID, *, age: timedelta, outcome: str | None = "OK", feature: str = "ASSISTANT",
                 subject: UUID | None = None) -> UUID:
    """صفٌّ في الدفتر بعمره: مفتوحٌ (بلا نتيجة) أو مُغلقٌ في وقته. المراجعة تحمل موضوعها وبصمته."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_requests (user_id, feature, subject_kind, subject_id, content_digest, started_at,"
            " finished_at, outcome)"
            " VALUES (%s, %s, CASE WHEN %s::uuid IS NULL THEN NULL ELSE 'PURCHASE' END, %s,"
            "         CASE WHEN %s::uuid IS NULL THEN NULL ELSE sha256('body'::bytea) END, now() - %s,"
            "         CASE WHEN %s::text IS NULL THEN NULL ELSE now() - %s END, %s)"
            " RETURNING id",
            (user, feature, subject, subject, subject, age, outcome, age, outcome))
        return cursor.fetchone()[0]


def seed_flag(owner, user: UUID, request: UUID, subject: UUID, *, age: timedelta, closed: bool,
              erased: bool = False, check_code: str = "PRICE_IMPLAUSIBLE", decision: str | None = None) -> UUID:
    """تنبيهٌ على الموضوع بعمره: مفتوحٌ أو مُغلقٌ بعد يومٍ من كتابته، بنصّه أو ممحوّاً، وبقرارٍ واحدٍ إن سُمّي."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_flags (user_id, request_id, feature, subject_kind, subject_id, content_digest, position,"
            " check_code, severity, field, reason, created_at, closed_at, erased_at)"
            " VALUES (%s, %s, 'STOCK_REVIEW', 'PURCHASE', %s, sha256('body'::bytea), 1, %s, 'HIGH', 'unit_cost',"
            "         CASE WHEN %s THEN NULL ELSE %s END, now() - %s,"
            "         CASE WHEN %s THEN now() - %s + interval '1 day' END, CASE WHEN %s THEN now() - %s END)"
            " RETURNING id",
            (user, request, subject, check_code, erased, REASON, age, closed, age, erased, age))
        flag = cursor.fetchone()[0]
        if decision is not None:
            cursor.execute("INSERT INTO ai_flag_decisions (flag_id, user_id, choice) VALUES (%s, %s, %s)",
                           (flag, user, decision))
        return flag


def test_a_request_open_for_an_hour_is_closed_as_abandoned_and_still_counts(owner, purge):
    """عمليّةٌ انقطعت تترك استدعاءها مفتوحاً: بعد ساعةٍ يُغلق ABANDONED محسوباً، وما في مهلته يبقى مفتوحاً."""
    user = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    stale = seed_request(owner, user, age=timedelta(minutes=61), outcome=None)
    fresh = seed_request(owner, user, age=timedelta(minutes=59), outcome=None)
    assert purge()["ai_abandoned"] == 1
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, finished_at IS NOT NULL, ew_is_billable(outcome) FROM ai_requests"
                       " WHERE id = %s", (stale,))
        assert cursor.fetchone() == ("ABANDONED", True, True)
        cursor.execute("SELECT outcome, finished_at FROM ai_requests WHERE id = %s", (fresh,))
        assert cursor.fetchone() == (None, None)


@pytest.mark.parametrize(("age", "deleted"), [(timedelta(days=29), False), (timedelta(days=31), True)])
def test_ai_requests_go_after_thirty_days_and_leave_no_tombstone(owner, purge, age, deleted):
    """الدفتر لمراجعة الكلفة ثلاثين يوماً؛ وحذفه بعدها لا يكتب أثراً: الأثر لما يُعدّ في يومه وحده."""
    user = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    seed_request(owner, user, age=age)
    assert purge()["ai_requests"] == (1 if deleted else 0)
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM ai_requests")
        assert cursor.fetchone()[0] == (0 if deleted else 1)
        cursor.execute("SELECT count(*) FROM attempt_tombstones")
        assert cursor.fetchone()[0] == 0


def test_open_flags_go_after_thirty_days_with_their_decisions(owner, purge):
    """تنبيهٌ لم يُعتمد موضوعه في ثلاثين يوماً لا قرار ينتظره؛ وما دون ذلك يبقى بقراره."""
    user = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    old_subject, young_subject = uuid4(), uuid4()
    old_request = seed_request(owner, user, age=timedelta(days=40), feature="STOCK_REVIEW", subject=old_subject)
    young_request = seed_request(owner, user, age=timedelta(days=20), feature="STOCK_REVIEW", subject=young_subject)
    seed_flag(owner, user, old_request, old_subject, age=timedelta(days=40), closed=False, decision="EDIT")
    young = seed_flag(owner, user, young_request, young_subject, age=timedelta(days=20), closed=False, decision="EDIT")
    counts = purge()
    assert (counts["ai_requests"], counts["ai_open_flags"]) == (1, 1)
    with owner.cursor() as cursor:
        cursor.execute("SELECT id, request_id FROM ai_flags")
        assert cursor.fetchall() == [(young, young_request)]
        cursor.execute("SELECT flag_id FROM ai_flag_decisions")
        assert cursor.fetchall() == [(young,)]


def test_closed_flags_are_kept_unlinked_with_their_decisions_when_their_request_goes(owner, purge):
    """التنبيه المعتمد سجلٌّ مع موضوعه: يبقى بقراراته — ومحوُ نصوصه لا يمحو قراراته — ويُفكّ عن دفترٍ حُذف."""
    user = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    subject = uuid4()
    request = seed_request(owner, user, age=timedelta(days=40), feature="STOCK_REVIEW", subject=subject)
    kept = seed_flag(owner, user, request, subject, age=timedelta(days=40), closed=True, decision="PROCEED")
    erased = seed_flag(owner, user, request, subject, age=timedelta(days=40), closed=True, erased=True,
                       check_code="UNIT_MISMATCH", decision="PROCEED")
    counts = purge()
    assert (counts["ai_requests"], counts["ai_open_flags"]) == (1, 0)
    with owner.cursor() as cursor:
        cursor.execute("SELECT id, request_id, closed_at IS NOT NULL, erased_at IS NOT NULL, reason,"
                       "       (SELECT count(*) FROM ai_flag_decisions d WHERE d.flag_id = f.id)"
                       "  FROM ai_flags f ORDER BY check_code")
        assert cursor.fetchall() == [(kept, None, True, False, REASON, 1), (erased, None, True, True, None, 1)]


def test_inventory_drafts_idle_for_thirty_days_go_and_posted_documents_stay(owner, app, purge):
    """مسودة فاتورةٍ ومسودة مرتجعٍ خاملتان منذ ٣١ يوماً تُحذفان بأسطرهما؛ والحديثة والمسجّلة تبقيان ولو قدمت."""
    keeper = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    as_user(app, keeper)
    with app.cursor() as cursor:
        cursor.execute("INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)")
        cursor.execute("INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'مؤسسة النور') RETURNING id")
        supplier = cursor.fetchone()[0]
        cursor.execute("INSERT INTO inv_items (user_id, name, kind, unit, price_halalas, vat_category)"
                       " VALUES (ew_current_user(), 'كرتونة ماء', 'STOCK', 'CARTON', 1000, 'S') RETURNING id")
        item = cursor.fetchone()[0]

        def purchase(number: str) -> UUID:
            cursor.execute("INSERT INTO inv_purchases (user_id, supplier_id, supplier_invoice_no, invoice_date, printed_total_halalas)"
                           " VALUES (ew_current_user(), %s, %s, ew_riyadh_today(), 1150) RETURNING id", (supplier, number))
            created = cursor.fetchone()[0]
            cursor.execute("INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category)"
                           " VALUES (%s, ew_current_user(), %s, 1000, 1000, 'S')", (created, item))
            return created

        idle, fresh, posted = purchase("P-1"), purchase("P-2"), purchase("P-3")
        cursor.execute("SELECT row_version FROM inv_purchases WHERE id = %s", (posted,))
        version = cursor.fetchone()[0]
        cursor.execute("SELECT ew_inv_post_purchase(%s, %s, ew_inv_flag_keys(%s, NULL))", (posted, version, posted))
        cursor.execute("INSERT INTO inv_returns (user_id, purchase_id, reason) VALUES (ew_current_user(), %s, 'EXCESS') RETURNING id",
                       (posted,))
        idle_return = cursor.fetchone()[0]
    month = timedelta(days=31)
    with guards_off(owner, "inv_purchases", "trg_inv_purchase_guard"), owner.cursor() as cursor:
        cursor.execute("UPDATE inv_purchases SET updated_at = now() - %s WHERE id IN (%s, %s)", (month, idle, posted))
    with guards_off(owner, "inv_returns", "trg_inv_return_guard"), owner.cursor() as cursor:
        cursor.execute("UPDATE inv_returns SET updated_at = now() - %s WHERE id = %s", (month, idle_return))

    counts = purge()
    assert (counts["inv_purchase_drafts"], counts["inv_return_drafts"]) == (1, 1)
    with owner.cursor() as cursor:
        cursor.execute("SELECT id FROM inv_purchases ORDER BY supplier_invoice_no")
        assert [row[0] for row in cursor.fetchall()] == [fresh, posted]
        cursor.execute("SELECT count(*) FROM inv_purchase_lines WHERE purchase_id = %s", (idle,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT count(*) FROM inv_returns")
        assert cursor.fetchone()[0] == 0
