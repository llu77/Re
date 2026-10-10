"""
مكتب الدعم: ما بين الخادم والقاعدة
==================================
ما يحسبه الخادم وتعيد القاعدة حسابه يتّفقان (تطبيع الاقتباس، والأولوية المقترحة، وجدول
الانتقالات)؛ وكل قيدٍ ترفعه 0011 أو يسمّيه جدولٌ فيها له رسالةٌ في `SUPPORT_CONSTRAINTS`؛ وخطوات
`admin purge` للدعم تمحو نصوص التذكرة بعد ثلاثين يوماً من إغلاقها والتذكرة بعد سنة، و`admin
set-profession` يغلق المكتب حين يغادره صاحبه.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

from eyework import admin, support_rules
from eyework.grounding import kb_norm
from eyework.tests.db.test_ai_layer import owner_scalar, query, scalar
from eyework.tests.db.test_support_desk import backdate, desk_user, prepare, ticket
from eyework.web.errors import SUPPORT_CONSTRAINTS

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0011_support_desk.up.sql"
TABLES = ("support_settings", "support_sla_targets", "support_tickets", "support_messages", "kb_articles", "kb_versions",
          "support_drafts", "support_draft_citations", "support_replies", "support_flags", "support_escalations",
          "support_events")
#: قيود لا يبلغها طلبٌ ولا تحتاج رسالة: مفاتيح الصفوف والروابط، والتكرار الذي تمنعه الدوالّ قبلها.
UNREACHABLE = re.compile(r"_(pkey|fkey|key)$|^support_message_reply_fk$")


@pytest.fixture
def purge(owner_url, monkeypatch):
    monkeypatch.setenv("EYEWORK_OWNER_DATABASE_URL", owner_url)
    return admin.purge


@pytest.mark.parametrize("text", [
    "أعد تشغيل   الموجّه بفصله عن الكهرباء", "الطابعة تطبَعُ صفحاتٍ فارغةً", "رقم ١٢٣٤ والخطأ 0x80070005",
    "Restart the ROUTER\n\nthen wait", "ﻻ تعمل الطابعة",
])
def test_the_quote_is_normalised_alike_in_the_server_and_the_database(owner, text):
    assert owner_scalar(owner, "SELECT ew_kb_norm(%s)", (text,)) == kb_norm(text)


def test_the_suggested_priority_and_the_transitions_agree_with_the_database(owner):
    for impact in ("WIDESPREAD", "SINGLE"):
        for urgency in ("STOPPED", "DEGRADED", "REQUEST"):
            for security in (True, False):
                assert owner_scalar(owner, "SELECT ew_support_priority_for(%s, %s, %s)", (impact, urgency, security)) \
                    == support_rules.priority_for(impact, urgency, security)
    with owner.cursor() as cursor:
        cursor.execute("SELECT from_status, to_status FROM support_ticket_transition")
        assert set(cursor.fetchall()) == support_rules.TRANSITIONS


def test_every_constraint_of_the_desk_has_its_message(owner):
    raised = set(re.findall(r"CONSTRAINT = '([a-z0-9_]+)'", MIGRATION.read_text(encoding="utf-8")))
    with owner.cursor() as cursor:
        cursor.execute("SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid"
                       " WHERE t.relname = ANY(%s) AND c.contype <> 't'", (list(TABLES),))
        named = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = ANY(%s) AND indexdef LIKE 'CREATE UNIQUE%%'",
                       (list(TABLES),))
        named |= {row[0] for row in cursor.fetchall() if not row[0].endswith("_pkey")}
    reachable = {name for name in raised | named if not UNREACHABLE.search(name)}
    # قيود الطبقة المشتركة (0009) ترفعها دوالّها هنا أيضاً، ورسائلها في الجدول نفسه.
    missing = sorted(name for name in reachable if name not in SUPPORT_CONSTRAINTS
                     and not name.startswith(("support_tickets_", "support_messages_", "support_drafts_",
                                              "support_replies_", "support_events_", "support_flags_",
                                              "support_escalations_", "support_settings_", "kb_articles_",
                                              "support_draft_citations_", "support_sla_targets_")))
    assert not missing, missing


def test_the_purge_forgets_ticket_texts_thirty_days_after_closing_and_the_ticket_after_a_year(owner, app, purge):
    agent = desk_user(owner, b"purge-agent", app=app)
    old, recent = ticket(app, agent), ticket(app, agent)
    prepare(app, agent, old, kind="UPDATE", core="نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة.")
    for t, days in ((old, 31), (recent, 5)):
        backdate(owner, "UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE', clock_since = NULL,"
                        " closed_at = now() - make_interval(days => %s) WHERE id = %s", (days, t))
    counts = purge()
    assert counts["support_messages"] == 1 and counts["support_texts_purged"] == 1 and counts["support_replies"] == 1
    assert owner_scalar(owner, "SELECT texts_purged_at IS NOT NULL AND customer_label IS NULL FROM support_tickets"
                               " WHERE id = %s", (old,))
    assert owner_scalar(owner, "SELECT count(*) FROM support_messages WHERE ticket_id = %s", (recent,)) == 1
    assert owner_scalar(owner, "SELECT count(*) FROM support_events WHERE ticket_id = %s AND event = 'TEXTS_PURGED'",
                        (old,)) == 1
    backdate(owner, "UPDATE support_tickets SET closed_at = now() - interval '366 days' WHERE id = %s", (old,))
    assert purge()["support_tickets"] == 1
    assert owner_scalar(owner, "SELECT count(*) FROM support_tickets WHERE id = %s", (old,)) == 0


def test_a_discarded_article_is_deleted_after_thirty_days(owner, app, purge):
    agent = desk_user(owner, b"purge-kb", app=app)
    article = scalar(app, agent, "SELECT ew_kb_create(gen_random_uuid(), 'الطابعة لا تطبع', 'الطابعة لا تطبع أيّ صفحة.',"
                                 " NULL, '1. أعد تشغيل الطابعة. 2. اطبع صفحة اختبار.', NULL, NULL)")
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("ALTER TABLE kb_articles DISABLE TRIGGER USER")
        cursor.execute("UPDATE kb_articles SET state = 'DISCARDED', discarded_at = now() - interval '29 days' WHERE id = %s",
                       (article,))
        cursor.execute("ALTER TABLE kb_articles ENABLE TRIGGER USER")
    assert purge()["kb_articles_deleted"] == 0
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("ALTER TABLE kb_articles DISABLE TRIGGER USER")
        cursor.execute("UPDATE kb_articles SET discarded_at = now() - interval '31 days' WHERE id = %s", (article,))
        cursor.execute("ALTER TABLE kb_articles ENABLE TRIGGER USER")
    assert purge()["kb_articles_deleted"] == 1


def test_leaving_support_withdraws_live_replies_and_closes_the_tickets(owner, app, owner_url, monkeypatch):
    monkeypatch.setenv("EYEWORK_OWNER_DATABASE_URL", owner_url)
    monkeypatch.setenv("EYEWORK_LOGIN_KEY", base64.b64encode(b"k" * 32).decode())
    monkeypatch.setenv("EYEWORK_PUBLIC_ORIGIN", "https://eyework.example")
    from eyework import auth

    key = admin._settings()[0]
    agent = desk_user(owner, auth.login_hmac(key, "leaving@example.sa"), app=app)
    t = ticket(app, agent)
    reply = prepare(app, agent, t, kind="UPDATE", core="نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة.")
    assert admin.set_profession("leaving@example.sa", "MARKETING") == 1
    assert owner_scalar(owner, "SELECT state FROM support_replies WHERE id = %s", (reply,)) == "WITHDRAWN"
    assert owner_scalar(owner, "SELECT close_reason FROM support_tickets WHERE id = %s", (t,)) == "PROFESSION_CHANGED"


CONTACT_SAMPLES = (
    "الطابعة لا تعمل", "اتصلوا بي على (050) 123-4567", "Tel: +966 (11) 234 – 5678", "050\u00a0123\u00a04567",
    "050\u200b123\u200b4567", "جوال ０５５１２３٤٥٦٧", "رقمي 050.123.4567", "الآيبان SA03.8000.0000.6080.1016.7519",
    "بريدي a.b@x.com", "الرابط accounts.example.com/reset?token=8f3a91", "الرابطhttps://portal.example.com/u?s=1",
    "www.example.com", "الإصدار 10.0.19045.3803", "العنوان 192.168.1.10", "العنوان 192.168.100.200",
    "الخطأ 0x80070005 والتحديث KB5034441", "الملف report.pdf وموقع example.com", "الخطأ بدأ 2024-10-09 12:30",
)


@pytest.mark.parametrize("text", CONTACT_SAMPLES)
def test_the_contact_check_agrees_in_the_server_and_the_database_and_passes_whatever_masking_keeps(owner, text):
    """الحاجز الثاني نظير الأول حرفاً بحرف، وكل ما يُبقيه الحذف يقبله؛ فلا يُرفض نصٌّ حذف الخادم ما فيه."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT ew_support_contact_free(%s), ew_support_contact_free(%s)", (text, support_rules.mask(text)[0]))
        raw, masked = cursor.fetchone()
    assert raw == support_rules.contact_free(text)
    assert masked and support_rules.contact_free(support_rules.mask(text)[0])
