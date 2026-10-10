"""
مكتب الدعم الفني — في القاعدة (0011)
===================================
ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو سيمبول، بدور الويب نفسه الذي يحمله الخادم:

  • المكتب لحساب الدعم الفني وحده، بعد إشعار المكتب، وكل صفٍّ لصاحبه؛ ولا يكتب دور الويب جدولاً.
  • كلام العميل لا يُخزَّن ببريدٍ أو رقم هاتف، ولا مقالةٌ برقم هويةٍ أو بطاقة.
  • لا شيء يصل العميل إلا بضغطة الموظف: الردّ يُجهَّز، ثم يُنسخ النصّ المحفوظ بعينه، ثم يؤكّد
    الموظف أنه أرسله؛ والمسودة وحدها لا تغيّر حالة التذكرة.
  • المسودة التي تجيب لا تُحفظ بلا اقتباسٍ حرفيٍّ من مقالةٍ منشورة، ولآخر رسالةٍ من العميل.
  • كل استدعاءٍ لسيمبول صفٌّ في الدفتر الواحد (0009)، وتنبيهاته في ai_flags: الإطلاق والنشر
    بوّابتهما ew_ai_gate. وتنبيهات القواعد في support_flags بإقرارها.

منقولةٌ من فحوص المسودة (checks/*.sql، سبعون فحصاً) بعد إعادة التأسيس على طبقة الذكاء.
"""

from __future__ import annotations

import json
import threading
import uuid
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework.tests.conftest import make_user
from eyework.tests.db.test_ai_layer import constraint_of, owner_scalar, query, scalar
from eyework.tests.db.test_state_machine import blocked_on_a_lock

NOTICE = "2026-10-09"
USAGE = json.dumps({"input": 100, "output": 50, "model": "claude-opus-5-5", "prompt_version": "support-2026-10-09.1",
                    "api_request_id": "req_1"})
OUTAGE = "الإنترنت مقطوع عن كل أجهزة المكتب منذ الصباح بعد تحديث KB5034441، ولا أحد يستطيع العمل"
ROUTER = ("1. أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية. 2. إن بقي الانقطاع فاتصل بمزوّد الخدمة على الرقم "
          "المكتوب على الموجّه.")
ANSWER = "أعد تشغيل الموجّه بفصله عن الكهرباء ثلاثين ثانية، ثم أخبرنا بالنتيجة."
QUOTE = "أعد تشغيل   الموجّه بفصله عن الكهرباء ثلاثين ثانية"
ASK = "هل تظهر أضواء الموجّه كلها باللون الأخضر؟ وما رسالة الخطأ التي تظهر في الحاسوب بالضبط؟"
REVIEW_FLAG = json.dumps([{"check": "KIND_MISMATCH", "severity": "MEDIUM", "field": "body", "line": None,
                           "reason": "الردّ يسأل العميل ولا يجيب عمّا طلبه في رسالته.",
                           "suggestion": "أجب أولاً ثم اسأل.", "evidence": ["بالضبط"]}])
_RECORD = ("SELECT ew_support_record_draft(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}', NULL, NULL,"
           " %s::jsonb, %s::jsonb)")


# ── أدوات ───────────────────────────────────────────────────────────────
def desk_user(owner, login: bytes, *, profession: str = "SUPPORT", notice: bool = True, app=None) -> UUID:
    user = make_user(owner, login=login, profession=profession)
    if notice and app is not None:
        query(app, user, "SELECT ew_support_accept_notice(%s)", (NOTICE,))
    return user


def ticket(app, user, body: str = OUTAGE, *, token: UUID | None = None, channel: str = "MESSAGING",
           label: str | None = "سارة") -> UUID:
    return scalar(app, user, "SELECT ew_support_create_ticket(%s, %s, 'NORMAL', NULL, %s, NULL, %s, 0::smallint)",
                  (token or uuid.uuid4(), channel, label, body))


def rv(app, user, table: str, row: UUID) -> int:
    return scalar(app, user, f"SELECT row_version FROM {table} WHERE id = %s", (row,))


def published(app, user, title: str = "انقطاع الإنترنت عن المكتب كله", resolution: str = ROUTER) -> UUID:
    article = scalar(app, user, "SELECT ew_kb_create(%s, %s, 'الإنترنت مقطوع عن كل الأجهزة في المكتب', NULL, %s,"
                                " NULL, NULL)", (uuid.uuid4(), title, resolution))
    query(app, user, "SELECT ew_kb_publish(%s, %s, 1::smallint)", (article, rv(app, user, "kb_articles", article)))
    return article


def begin_draft(app, user, t: UUID) -> tuple[UUID, UUID]:
    return query(app, user, "SELECT request_id, based_on_message_id FROM ew_support_begin_draft(%s, %s)",
                 (t, rv(app, user, "support_tickets", t)))[0]


def record_draft(app, user, request, based_on, *, result="DRAFT", kind="ANSWER", body=ANSWER, note=None,
                 impact="WIDESPREAD", urgency="STOPPED", citations=None) -> UUID:
    return scalar(app, user, _RECORD, (request, based_on, result, kind, body, "انقطاع الإنترنت", note, "NETWORK", impact,
                                       urgency, False, None, "AR", citations, USAGE))


def cite(article: UUID, quote: str = QUOTE) -> str:
    return json.dumps([{"article_id": str(article), "version": 1, "quote": quote}])


def answered(app, user, t: UUID, article: UUID) -> UUID:
    """مسودةٌ تجيب من المقالة لآخر رسالة."""
    request, based_on = begin_draft(app, user, t)
    return record_draft(app, user, request, based_on, citations=cite(article))


def prepare(app, user, t: UUID, *, draft=None, kind="ANSWER", core=ANSWER, body=None, flags=None, template=False) -> UUID:
    return scalar(app, user, "SELECT ew_support_prepare_reply(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                  (t, rv(app, user, "support_tickets", t), uuid.uuid4(), draft, kind, template, core, body or core, flags))


def sha(app, user, reply: UUID) -> bytes:
    return scalar(app, user, "SELECT body_sha256 FROM support_replies WHERE id = %s", (reply,))


def release(app, user, reply: UUID, digest: bytes | None = None) -> None:
    query(app, user, "SELECT ew_support_release_reply(%s, 'COPY', %s)", (reply, digest or sha(app, user, reply)))


def backdate(owner, statement: str, params: tuple) -> None:
    """يُرجع وقتاً إلى الوراء بلا محفّزات الجدول (تكتب أوقاته بنفسها)، ثم يعيدها مهما حدث."""
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("ALTER TABLE support_tickets DISABLE TRIGGER USER")
        cursor.execute(statement, params)
        cursor.execute("ALTER TABLE support_tickets ENABLE TRIGGER USER")


def refusal(app, user, statement: str, params: tuple = ()) -> str | None:
    return constraint_of(lambda: query(app, user, statement, params))


# ── المهنة والإشعار والعزل ──────────────────────────────────────────────
def test_the_desk_is_for_support_accounts_after_the_notice_and_each_sees_only_its_own(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    s2 = desk_user(owner, b"s2", notice=False)
    marketer = desk_user(owner, b"m1", profession="MARKETING", notice=False)
    create = "SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, %s, 0::smallint)"

    assert refusal(app, s2, create, ("الطابعة لا تطبع منذ الصباح",)) == "support_notice_required"
    assert refusal(app, marketer, create, ("لا تعمل الطابعة منذ الأمس",)) == "support_needs_support"
    assert refusal(app, None, "SELECT ew_support_accept_notice(%s)", (NOTICE,)) == "support_needs_support"
    assert refusal(app, s1, "INSERT INTO support_tickets (user_id, client_token, channel) VALUES (%s, gen_random_uuid(), 'EMAIL')",
                   (s1,)) == "42501"
    for internal in ("SELECT ew_support_request_for(%s, gen_random_uuid(), NULL)", "SELECT ew_kb_version_digest(%s, 1::smallint)",
                     "SELECT ew_support_log(%s, NULL, NULL, 'NOTE_ADDED', NULL, NULL, NULL, NULL, NULL)"):
        assert refusal(app, s1, internal, (s1,)) == "42501", internal

    t1 = ticket(app, s1)
    a1 = published(app, s1)
    query(app, s2, "SELECT ew_support_accept_notice(%s)", (NOTICE,))
    assert scalar(app, s2, "SELECT count(*) FROM support_tickets") == 0
    assert scalar(app, s2, "SELECT count(*) FROM kb_articles") == 0
    assert scalar(app, s2, "SELECT count(*) FROM ew_kb_search('الإنترنت', 3)") == 0
    assert refusal(app, s2, "SELECT ew_support_reopen(%s, 1)", (t1,)) == "P0002"
    assert refusal(app, s2, "SELECT ew_kb_publish(%s, 1, 1::smallint)", (a1,)) == "P0002"
    assert scalar(app, None, "SELECT count(*) FROM support_tickets") == 0


# ── التذاكر ─────────────────────────────────────────────────────────────
def test_customer_text_is_kept_without_contact_details_and_a_ticket_is_created_once(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    create = "SELECT ew_support_create_ticket(gen_random_uuid(), %s, 'NORMAL', NULL, %s, NULL, %s, 0::smallint)"
    assert refusal(app, s1, create, ("EMAIL", None, "راسلني على ali@example.com لو سمحت")) == "support_message_contact_free"
    assert refusal(app, s1, create, ("MESSAGING", None, "جوالي 055 123 4567 اتصل بي")) == "support_message_contact_free"
    assert refusal(app, s1, create, ("MESSAGING", "0551234567", "الطابعة لا تطبع منذ الصباح")) == "support_customer_label_shape"

    token = uuid.uuid4()
    t1 = ticket(app, s1, token=token)
    status, number, due_hours = query(app, s1, "SELECT status, number, extract(epoch FROM first_reply_due_at - now()) / 3600"
                                               " FROM support_tickets WHERE id = %s", (t1,))[0]
    assert (status, number) == ("NEW", 1) and due_hours > 7
    # رقم تحديثٍ من سبعة أرقام ليس هاتفاً: يبقى في النصّ.
    assert "KB5034441" in scalar(app, s1, "SELECT body FROM support_messages WHERE ticket_id = %s", (t1,))
    assert ticket(app, s1, "نصٌّ آخر لا يُحفظ أبداً", token=token) == t1
    assert scalar(app, s1, "SELECT count(*) FROM support_messages WHERE ticket_id = %s", (t1,)) == 1


def test_a_new_open_account_holds_at_most_thirty_open_tickets(owner, app):
    fresh = desk_user(owner, b"n1")
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET self_registered = true, open_registered = true, terms_version = %s,"
                       " terms_accepted_at = now() WHERE id = %s", (NOTICE, fresh))
    query(app, fresh, "SELECT ew_support_accept_notice(%s)", (NOTICE,))
    for i in range(30):
        ticket(app, fresh, f"رسالة تجربة رقم {i + 1}", channel="EMAIL", label=None)
    assert refusal(app, fresh, "SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL,"
                               " 'رسالة زائدة', 0::smallint)") == "support_open_ticket_cap"


# ── قاعدة المعرفة ───────────────────────────────────────────────────────
def test_articles_are_published_by_the_employee_and_only_published_ones_are_searched(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    a1 = scalar(app, s1, "SELECT ew_kb_create(%s, 'انقطاع الإنترنت عن المكتب كله', 'الإنترنت مقطوع عن كل الأجهزة في المكتب',"
                         " NULL, %s, NULL, NULL)", (uuid.uuid4(), ROUTER))
    assert query(app, s1, "SELECT state, latest_version, number FROM kb_articles WHERE id = %s", (a1,))[0] == ("DRAFT", 1, 1)
    assert scalar(app, s1, "SELECT count(*) FROM ew_kb_search('انقطع الانترنت في المكتب', 3)") == 0
    assert refusal(app, s1, "SELECT ew_kb_publish(%s, %s, 2::smallint)", (a1, rv(app, s1, "kb_articles", a1))) == "stale_row_version"
    query(app, s1, "SELECT ew_kb_publish(%s, %s, 1::smallint)", (a1, rv(app, s1, "kb_articles", a1)))
    assert query(app, s1, "SELECT state, published_version FROM kb_articles WHERE id = %s", (a1,))[0] == ("PUBLISHED", 1)
    assert scalar(app, s1, "SELECT count(*) FROM ew_kb_search('انقطع الانترنت في المكتب', 3)") == 1
    assert refusal(app, s1, "SELECT ew_kb_create(gen_random_uuid(), 'عنوانٌ للتجربة', 'مشكلةٌ في الدخول إلى الحساب', NULL,"
                            " 'اكتب رقم هويتك 1012345678 في الخانة ثم اضغط دخول', NULL, NULL)") == "kb_version_clean"
    query(app, s1, "SELECT ew_kb_set_state(%s, %s, 'ARCHIVED')", (a1, rv(app, s1, "kb_articles", a1)))
    assert scalar(app, s1, "SELECT count(*) FROM ew_kb_search('انقطع الانترنت في المكتب', 3)") == 0


# ── المسودات ────────────────────────────────────────────────────────────
def test_a_draft_answers_only_from_a_verbatim_published_quote_and_settles_its_request(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    request, based_on = begin_draft(app, s1, t1)
    row = query(app, s1, "SELECT feature, subject_kind, subject_id, content_digest, finished_at FROM ai_requests WHERE id = %s",
                (request,))[0]
    assert row == ("SUPPORT_DRAFT", "SUPPORT_TICKET", t1, None, None)
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", None, USAGE)) == "support_answer_needs_citation"
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", cite(a1, "أعد تشغيل الحاسوب مرتين"),
                                      USAGE)) == "support_citation_not_verbatim"
    # اقتباسٌ لا يبقى منه شيءٌ بعد التوحيد (تطويلٌ وتشكيل) يحويه كل نصّ، فلا يُسند الإجابة.
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", cite(a1, "ـــــــــَُِ   ـــ"),
                                      USAGE)) == "support_citation_not_verbatim"
    d1 = record_draft(app, s1, request, based_on, citations=cite(a1))
    assert query(app, s1, "SELECT suggested_priority, seq, served_model, prompt_version, call_id FROM support_drafts"
                          " WHERE id = %s", (d1,))[0] == ("URGENT", 1, "claude-opus-5-5", "support-2026-10-09.1", request)
    assert query(app, s1, "SELECT outcome, input_tokens FROM ai_requests WHERE id = %s", (request,))[0] == ("OK", 100)
    assert scalar(app, s1, "SELECT status FROM support_tickets WHERE id = %s", (t1,)) == "NEW"
    # الطلب نفسه لا يُكتب مرتين.
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", cite(a1), USAGE)) == "ai_request_not_open"


def test_a_draft_is_for_the_latest_customer_message_within_its_lease(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    request, based_on = begin_draft(app, s1, t1)
    query(app, s1, "SELECT ew_support_add_message(%s, %s, 'CUSTOMER', 'وجرّبت إعادة التشغيل ولم ينجح', 0::smallint,"
                   " gen_random_uuid())", (t1, rv(app, s1, "support_tickets", t1)))
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", cite(a1), USAGE)) == "support_draft_stale"
    # الخادم يغلق المسودة التي سبقتها رسالةٌ DISCARDED بكلفتها، فلا يبقى الطلب مفتوحاً يحجز التالي حتى ينقضي أجله.
    query(app, s1, "SELECT ew_support_finish_call(%s, 'DISCARDED', %s::jsonb)", (request, USAGE))
    assert query(app, s1, "SELECT outcome, input_tokens FROM ai_requests WHERE id = %s", (request,))[0] == ("DISCARDED", 100)

    request, based_on = begin_draft(app, s1, t1)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE ai_requests SET started_at = now() - interval '151 seconds' WHERE id = %s", (request,))
    assert refusal(app, s1, _RECORD, (request, based_on, "DRAFT", "ANSWER", ANSWER, "انقطاع الإنترنت", None, "NETWORK",
                                      "WIDESPREAD", "STOPPED", False, None, "AR", cite(a1), USAGE)) == "support_draft_needs_open_call"


def test_failures_settle_the_request_and_a_ticket_has_at_most_eight_drafts_a_day(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    # ما لم يصل النموذج (سيمبول متوقّف أو مشغول) لا يُحسب على التذكرة.
    for _ in range(2):
        request, _ = begin_draft(app, s1, t1)
        query(app, s1, "SELECT ew_support_finish_call(%s, 'UPSTREAM_ERROR', NULL)", (request,))
    for _ in range(8):
        request, _ = begin_draft(app, s1, t1)
        # النتيجة الناجحة تُكتب بدالّة أثرها وحدها.
        assert refusal(app, s1, "SELECT ew_support_finish_call(%s, 'OK', NULL)", (request,)) == "ai_outcome_needs_record"
        query(app, s1, "SELECT ew_support_finish_call(%s, 'OUTPUT_INVALID', NULL)", (request,))
        assert scalar(app, s1, "SELECT outcome FROM ai_requests WHERE id = %s", (request,)) == "OUTPUT_INVALID"
    assert scalar(app, s1, "SELECT count(*) FROM support_events WHERE ticket_id = %s AND event = 'DRAFT_FAILED'", (t1,)) == 10
    # سقف التذكرة يُفحص قبل سقف الدقائق العشر للميزة (عشرة).
    assert refusal(app, s1, "SELECT * FROM ew_support_begin_draft(%s, %s)",
                   (t1, rv(app, s1, "support_tickets", t1))) == "support_ticket_draft_cap"


def test_rejecting_a_draft_for_wrong_information_marks_its_articles(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t2 = ticket(app, s1, "الإنترنت مقطوع عن جهازي فقط، وزملائي يعملون عادي", channel="EMAIL", label=None)
    a1 = published(app, s1)
    request, based_on = begin_draft(app, s1, t2)
    d4 = record_draft(app, s1, request, based_on, impact="SINGLE", citations=cite(a1))
    assert scalar(app, s1, "SELECT suggested_priority FROM support_drafts WHERE id = %s", (d4,)) == "HIGH"
    query(app, s1, "SELECT ew_support_reject_draft(%s, 'WRONG_INFO', 'المشكلة في جهازٍ واحد لا في الموجّه')", (d4,))
    assert query(app, s1, "SELECT needs_review, needs_review_reason FROM kb_articles WHERE id = %s", (a1,))[0] == (
        True, "DRAFT_WRONG_INFO")
    assert refusal(app, s1, "SELECT ew_support_reject_draft(%s, 'OTHER', 'سببٌ آخر')", (d4,)) == "support_draft_immutable"


# ── التصنيف ─────────────────────────────────────────────────────────────
def test_lowering_the_suggested_priority_raises_a_rule_flag(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    d1 = answered(app, s1, t1, published(app, s1))
    set_ticket = "SELECT ew_support_set_ticket(%s, %s, 'NETWORK', %s, 'انقطاع الإنترنت', %s)"
    assert refusal(app, s1, set_ticket, (t1, rv(app, s1, "support_tickets", t1), "LOW", d1)) == "support_suggestion_mismatch"
    query(app, s1, set_ticket, (t1, rv(app, s1, "support_tickets", t1), "LOW", None))
    assert scalar(app, s1, "SELECT count(*) FROM support_flags WHERE ticket_id = %s AND code = 'PRIORITY_BELOW_SUGGESTION'"
                           " AND state = 'OPEN'", (t1,)) == 1
    assert scalar(app, s1, "SELECT first_reply_due_at > created_at + interval '23 hours' FROM support_tickets WHERE id = %s",
                  (t1,))
    query(app, s1, set_ticket, (t1, rv(app, s1, "support_tickets", t1), "URGENT", d1))
    assert scalar(app, s1, "SELECT priority FROM support_tickets WHERE id = %s", (t1,)) == "URGENT"


# ── الردود ──────────────────────────────────────────────────────────────
def test_the_saved_reply_is_released_by_its_hash_and_sending_it_resolves_the_ticket(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    d1 = answered(app, s1, t1, a1)
    body = f"مرحباً سارة،\n\n{ANSWER}\n\nفريق الدعم الفني"
    r1 = prepare(app, s1, t1, draft=d1, body=body)
    assert query(app, s1, "SELECT origin, state FROM support_replies WHERE id = %s", (r1,))[0] == ("AS_IS", "READY")
    assert refusal(app, s1, "SELECT ew_support_prepare_reply(%s, %s, gen_random_uuid(), NULL, 'UPDATE', false, %s, %s, NULL)",
                   (t1, rv(app, s1, "support_tickets", t1), "نعمل على المشكلة الآن وسنعود إليك قريباً.",
                    "نعمل على المشكلة الآن وسنعود إليك قريباً.")) == "support_one_live_reply"
    assert refusal(app, s1, "SELECT ew_support_release_reply(%s, 'COPY', sha256('x'::bytea))", (r1,)) == "support_reply_hash_mismatch"
    assert refusal(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (r1,)) == "support_reply_transition"
    release(app, s1, r1)
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (r1,))
    status, resolution, first, clock = query(app, s1, "SELECT status, resolution, first_replied_at, clock_since"
                                                      " FROM support_tickets WHERE id = %s", (t1,))[0]
    assert (status, resolution, first is not None, clock) == ("RESOLVED", "REPLIED", True, None)
    assert scalar(app, s1, "SELECT count(*) FROM support_messages m JOIN support_replies r ON r.id = m.reply_id"
                           " WHERE m.ticket_id = %s AND m.author = 'AGENT' AND m.body = r.body", (t1,)) == 1
    assert scalar(app, s1, "SELECT reuse_count FROM kb_articles WHERE id = %s", (a1,)) == 1
    assert scalar(app, s1, "SELECT count(*) FROM support_events WHERE ticket_id = %s AND event = 'STATUS_CHANGED'"
                           " AND to_status = 'RESOLVED'", (t1,)) == 1
    query(app, s1, "SELECT ew_support_add_message(%s, %s, 'CUSTOMER', 'جرّبت ولم ينجح، ما زال الانقطاع', 0::smallint,"
                   " gen_random_uuid())", (t1, rv(app, s1, "support_tickets", t1)))
    assert query(app, s1, "SELECT status, resolution, resolved_at FROM support_tickets WHERE id = %s", (t1,))[0] == (
        "OPEN", None, None)


def test_an_edited_reply_waits_for_its_rule_flags_and_for_a_decision_on_each_symbol_note(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    request, based_on = begin_draft(app, s1, t1)
    d2 = record_draft(app, s1, request, based_on, result="CANNOT_ANSWER", kind="ASK_INFO",
                      body="هل تظهر أضواء الموجّه كلها باللون الأخضر؟ وما رسالة الخطأ التي تظهر في الحاسوب؟",
                      note="قاعدة المعرفة لا تذكر ما يُفعل إن لم تنفع إعادة التشغيل.")
    assert scalar(app, s1, "SELECT outcome FROM ai_requests WHERE id = %s", (request,)) == "CANNOT_ANSWER"
    r2 = prepare(app, s1, t1, draft=d2, kind="ASK_INFO", core=ASK, flags='[{"code": "NO_QUESTION", "evidence": null}]')
    assert scalar(app, s1, "SELECT origin FROM support_replies WHERE id = %s", (r2,)) == "EDITED"
    assert constraint_of(lambda: release(app, s1, r2)) == "support_flags_open"
    query(app, s1, "SELECT ew_support_ack_flag(id, 'DISMISSED', 'FALSE_ALARM') FROM support_flags WHERE reply_id = %s", (r2,))

    review, digest = query(app, s1, "SELECT request_id, content_digest FROM ew_support_review_begin(%s)", (r2,))[0]
    assert digest == sha(app, s1, r2)
    assert scalar(app, s1, "SELECT ew_support_review_record(%s, %s::jsonb, %s::jsonb)", (review, REVIEW_FLAG, USAGE)) == "OK"
    flag = scalar(app, s1, "SELECT id FROM ai_flags WHERE subject_kind = 'SUPPORT_REPLY' AND subject_id = %s", (r2,))
    assert scalar(app, s1, "SELECT count(*) FROM support_events WHERE reply_id = %s AND event = 'REVIEW_DONE'", (r2,)) == 1
    # ما رُوجع لا يُراجَع ثانيةً.
    assert refusal(app, s1, "SELECT * FROM ew_support_review_begin(%s)", (r2,)) == "ai_review_current"
    assert constraint_of(lambda: release(app, s1, r2)) == "ai_flags_undecided"
    query(app, s1, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (flag,))
    assert constraint_of(lambda: release(app, s1, r2)) == "ai_flags_undecided"
    query(app, s1, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (flag,))
    release(app, s1, r2)
    assert scalar(app, s1, "SELECT closed_at IS NOT NULL FROM ai_flags WHERE id = %s", (flag,))
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (r2,))
    assert query(app, s1, "SELECT status, clock_since FROM support_tickets WHERE id = %s", (t1,))[0] == ("PENDING", None)


def test_symbol_never_blocks_and_only_edited_or_written_replies_are_reviewed(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    d1 = answered(app, s1, t1, published(app, s1))
    as_is = prepare(app, s1, t1, draft=d1)
    assert refusal(app, s1, "SELECT * FROM ew_support_review_begin(%s)", (as_is,)) == "P0002"
    query(app, s1, "SELECT ew_support_confirm_reply(%s, false)", (as_is,))
    manual = prepare(app, s1, t1, kind="UPDATE", core="نعمل على المشكلة الآن وسنعود إليك قريباً.")
    # مراجعةٌ بدأت ولم تنتهِ لا تمنع الإطلاق، وما تقوله بعد الإطلاق يُسقط.
    review = scalar(app, s1, "SELECT request_id FROM ew_support_review_begin(%s)", (manual,))
    release(app, s1, manual)
    assert scalar(app, s1, "SELECT ew_support_review_record(%s, %s::jsonb, %s::jsonb)", (review, REVIEW_FLAG, USAGE)) == "DISCARDED"
    assert scalar(app, s1, "SELECT count(*) FROM ai_flags WHERE subject_id = %s", (manual,)) == 0


# ── الحلّ والتصعيد ──────────────────────────────────────────────────────
def test_resolving_and_escalating_follow_the_conversation(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    resolve = "SELECT ew_support_resolve(%s, %s, %s, %s)"
    assert refusal(app, s1, resolve, (t1, rv(app, s1, "support_tickets", t1), "NOT_SUPPORT", False)) == "support_resolve_unanswered"
    assert refusal(app, s1, resolve, (t1, rv(app, s1, "support_tickets", t1), "NO_RESPONSE", True)) == "support_ticket_transition"
    query(app, s1, "SELECT ew_support_escalate(%s, %s, 'VENDOR', 'الأضواء حمراء بعد إعادة التشغيل؛ يحتاج مزوّد الخدمة إلى فحص الخط.')",
          (t1, rv(app, s1, "support_tickets", t1)))
    assert query(app, s1, "SELECT status, escalation_target FROM support_tickets WHERE id = %s", (t1,))[0] == ("ESCALATED", "VENDOR")
    assert refusal(app, s1, "SELECT ew_support_prepare_reply(%s, %s, gen_random_uuid(), NULL, 'ANSWER', false, %s, %s, NULL)",
                   (t1, rv(app, s1, "support_tickets", t1), "أصلح المزوّد الخط، والإنترنت يعمل الآن في المكتب.",
                    "أصلح المزوّد الخط، والإنترنت يعمل الآن في المكتب.")) == "support_escalation_open"
    query(app, s1, "SELECT ew_support_return_escalation(%s, %s, 'أصلح المزوّد الخط صباح اليوم.')",
          (t1, rv(app, s1, "support_tickets", t1)))
    assert query(app, s1, "SELECT status, escalation_target FROM support_tickets WHERE id = %s", (t1,))[0] == ("OPEN", None)
    query(app, s1, resolve, (t1, rv(app, s1, "support_tickets", t1), "DUPLICATE", True))
    assert query(app, s1, "SELECT status, resolution FROM support_tickets WHERE id = %s", (t1,))[0] == ("RESOLVED", "DUPLICATE")
    # الحلّ بلا ردٍّ على رسالةٍ قائمة يُسجَّل تنبيهاً أُقِرّ بتأكيده.
    assert query(app, s1, "SELECT code, state, dismiss_reason FROM support_flags WHERE ticket_id = %s", (t1,))[0] == (
        "RESOLVE_UNANSWERED", "DISMISSED", "CONFIRMED")


# ── اقتراح المقالة ونشرها ────────────────────────────────────────────────
def test_a_proposed_article_is_reviewed_and_each_version_is_published_through_the_gate(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    assert refusal(app, s1, "SELECT ew_kb_begin_proposal(%s)", (t1,)) == "kb_proposal_needs_source"
    r1 = prepare(app, s1, t1, draft=answered(app, s1, t1, published(app, s1)))
    release(app, s1, r1)
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (r1,))

    proposal = scalar(app, s1, "SELECT ew_kb_begin_proposal(%s)", (t1,))
    a2 = scalar(app, s1, "SELECT ew_kb_record_proposal(%s, %s, %s, NULL, %s, NULL, %s::jsonb)",
                (proposal, "الأضواء الحمراء في الموجّه بعد إعادة تشغيله", "الموجّه أضواؤه حمراء والإنترنت مقطوع بعد إعادة التشغيل",
                 "1. تأكّد من توصيل سلك الخط بالموجّه. 2. أعد تشغيله مرةً واحدة. 3. إن بقيت الأضواء حمراء فالمشكلة في الخط:"
                 " صعّد التذكرة إلى مزوّد الخدمة.", USAGE))
    assert query(app, s1, "SELECT a.state, v.origin, v.call_id FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id"
                          " WHERE a.id = %s", (a2,))[0] == ("PROPOSED", "AI", proposal)
    assert scalar(app, s1, "SELECT count(*) FROM ew_kb_search('الأضواء الحمراء الموجّه', 5) WHERE article_id = %s", (a2,)) == 0

    review, digest = query(app, s1, "SELECT request_id, content_digest FROM ew_kb_review_begin(%s, 1::smallint)", (a2,))[0]
    assert digest == owner_scalar(owner, "SELECT ew_kb_version_digest(%s, 1::smallint)", (a2,))
    flags = json.dumps([{"check": "UNCLEAR_STEPS", "severity": "MEDIUM", "field": "resolution", "line": 2,
                         "reason": "الخطوة الثانية لا تقول كم ينتظر قبل إعادة التوصيل.", "suggestion": None,
                         "evidence": ["أعد تشغيله مرةً واحدة"]}])
    assert scalar(app, s1, "SELECT ew_kb_review_record(%s, %s::jsonb, %s::jsonb)", (review, flags, USAGE)) == "OK"
    assert refusal(app, s1, "SELECT ew_kb_publish(%s, %s, 1::smallint)", (a2, rv(app, s1, "kb_articles", a2))) == "ai_flags_undecided"

    # الموظف يعدّل: نسخةٌ ثانية ببصمةٍ أخرى، وما قيل عن الأولى لا يحجزها.
    query(app, s1, "SELECT ew_kb_add_version(%s, %s, %s, %s, NULL, %s, NULL)",
          (a2, rv(app, s1, "kb_articles", a2), "الأضواء الحمراء في الموجّه بعد إعادة تشغيله",
           "الموجّه أضواؤه حمراء والإنترنت مقطوع بعد إعادة التشغيل",
           "1. تأكّد من توصيل سلك الخط بالموجّه جيداً. 2. افصل الموجّه عن الكهرباء ثلاثين ثانية ثم أعد توصيله."
           " 3. إن بقيت الأضواء حمراء فالمشكلة في الخط: صعّد التذكرة إلى مزوّد الخدمة."))
    assert query(app, s1, "SELECT state, latest_version FROM kb_articles WHERE id = %s", (a2,))[0] == ("DRAFT", 2)
    assert refusal(app, s1, "SELECT ew_kb_publish(%s, %s, 1::smallint)", (a2, rv(app, s1, "kb_articles", a2))) == "stale_row_version"
    query(app, s1, "SELECT ew_kb_publish(%s, %s, 2::smallint)", (a2, rv(app, s1, "kb_articles", a2)))
    assert scalar(app, s1, "SELECT count(*) FROM ew_kb_search('الأضواء حمراء', 5) WHERE article_id = %s", (a2,)) == 1

    second = scalar(app, s1, "SELECT ew_kb_begin_proposal(%s)", (t1,))
    query(app, s1, "SELECT ew_support_finish_call(%s, 'CANNOT_ANSWER', %s::jsonb)", (second, USAGE))
    assert scalar(app, s1, "SELECT outcome FROM ai_requests WHERE id = %s", (second,)) == "CANNOT_ANSWER"
    assert refusal(app, s1, "SELECT ew_kb_begin_proposal(%s)", (t1,)) == "kb_ticket_proposal_cap"


# ── الإغلاق والمتابعة والمحو ─────────────────────────────────────────────
def test_closing_purging_and_deleting_forget_what_symbol_said(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    request, based_on = begin_draft(app, s1, t1)
    d2 = record_draft(app, s1, request, based_on, result="CANNOT_ANSWER", kind="ASK_INFO", body=ASK,
                      note="قاعدة المعرفة لا تذكر ما يُفعل إن لم تنفع إعادة التشغيل.")
    r2 = prepare(app, s1, t1, draft=d2, kind="ASK_INFO", core=ASK + " وما نوع الموجّه؟")
    review = scalar(app, s1, "SELECT request_id FROM ew_support_review_begin(%s)", (r2,))
    query(app, s1, "SELECT ew_support_review_record(%s, %s::jsonb, %s::jsonb)", (review, REVIEW_FLAG, USAGE))
    assert scalar(app, s1, "SELECT count(*) FROM ai_flags WHERE subject_id = %s", (r2,)) == 1

    # الدفتر يُمحى بعد ثلاثين يوماً: المسودة تبقى بلا رقم استدعائها.
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    assert scalar(app, s1, "SELECT call_id FROM support_drafts WHERE id = %s", (d2,)) is None
    # محو نصوص التذكرة يحذف ردودها، وما قاله سيمبول عنها معها.
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM support_replies WHERE ticket_id = %s", (t1,))
    assert scalar(app, s1, "SELECT count(*) FROM ai_flags WHERE subject_id = %s", (r2,)) == 0

    query(app, s1, "SELECT ew_support_resolve(%s, %s, 'BY_PHONE', false)", (t1, rv(app, s1, "support_tickets", t1)))
    backdate(owner, "UPDATE support_tickets SET resolved_at = now() - interval '5 days' WHERE id = %s", (t1,))
    assert scalar(app, s1, "SELECT ew_support_close_due()") == 1
    assert query(app, s1, "SELECT status, close_reason FROM support_tickets WHERE id = %s", (t1,))[0] == ("CLOSED", "AFTER_RESOLVED")
    follow = scalar(app, s1, "SELECT ew_support_follow_up(%s, gen_random_uuid(), 'عاد الانقطاع اليوم مرة أخرى', 0::smallint)", (t1,))
    assert scalar(app, s1, "SELECT follow_up_of FROM support_tickets WHERE id = %s", (follow,)) == t1

    review, _ = query(app, s1, "SELECT request_id, content_digest FROM ew_kb_review_begin(%s, 1::smallint)",
                      (scalar(app, s1, "SELECT ew_kb_create(gen_random_uuid(), 'عنوانٌ آخر للمقالة', 'مشكلةٌ في الطباعة من الحاسوب',"
                                       " NULL, '1. افتح قائمة الطابعات. 2. اختر الطابعة الافتراضية ثم اطبع صفحة تجربة.', NULL, NULL)"),))[0]
    query(app, s1, "SELECT ew_kb_review_record(%s, %s::jsonb, %s::jsonb)",
          (review, json.dumps([{"check": "UNCLEAR_STEPS", "severity": "MEDIUM", "field": "resolution", "line": 1,
                                "reason": "لا تذكر الخطوة أين توجد قائمة الطابعات.", "suggestion": None, "evidence": []}]), USAGE))
    assert scalar(app, s1, "SELECT count(*) FROM ai_flags WHERE subject_kind = 'KB_ARTICLE'") == 1
    query(app, s1, "SELECT ew_delete_me()")
    for table in ("support_tickets", "kb_articles", "support_events", "ai_flags"):
        assert owner_scalar(owner, f"SELECT count(*) FROM {table} WHERE user_id = %s", (s1,)) == 0, table


def test_leaving_support_closes_the_desk(owner, app):
    s4 = desk_user(owner, b"s4", app=app)
    t = ticket(app, s4)
    reply = prepare(app, s4, t, kind="UPDATE", core="نعمل على المشكلة الآن وسنعود إليك قريباً.")
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (s4,))
        cursor.execute("UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now()"
                       " WHERE user_id = %s AND state IN ('READY', 'RELEASED')", (s4,))
        cursor.execute("UPDATE support_tickets SET status = 'CLOSED', close_reason = 'PROFESSION_CHANGED'"
                       " WHERE user_id = %s AND status <> 'CLOSED'", (s4,))
        cursor.execute("UPDATE users SET profession = 'MARKETING' WHERE id = %s", (s4,))
    assert owner_scalar(owner, "SELECT state FROM support_replies WHERE id = %s", (reply,)) == "WITHDRAWN"
    assert owner_scalar(owner, "SELECT close_reason FROM support_tickets WHERE id = %s", (t,)) == "PROFESSION_CHANGED"
    assert refusal(app, s4, "SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL,"
                            " 'رسالة بعد تغيير المهنة', 0::smallint)") == "support_needs_support"


# ── التزامن ─────────────────────────────────────────────────────────────
def test_two_drafts_for_one_employee_wait_for_each_other_and_only_one_is_in_flight(owner, app, app_url):
    s2 = desk_user(owner, b"s2", app=app)
    first, second = ticket(app, s2), ticket(app, s2, "البريد لا يصلني منذ أمس", channel="EMAIL", label=None)
    outcome: dict[str, object] = {}
    connected = threading.Event()
    with psycopg.connect(app_url) as holder:
        query(holder, s2, "SELECT * FROM ew_support_begin_draft(%s, 1)", (first,))   # يبقى مفتوحاً في معاملته

        def racer() -> None:
            with psycopg.connect(app_url, autocommit=True) as other:
                outcome["pid"] = other.info.backend_pid
                connected.set()
                outcome["constraint"] = constraint_of(
                    lambda: query(other, s2, "SELECT * FROM ew_support_begin_draft(%s, 1)", (second,)))

        thread = threading.Thread(target=racer)
        thread.start()
        assert connected.wait(5)
        assert blocked_on_a_lock(app, outcome["pid"], thread)
        holder.commit()
        thread.join(5)
    assert outcome["constraint"] == "ai_request_in_progress"


def test_the_web_role_reads_no_ledger_of_its_own_and_writes_no_table(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    for statement in ("UPDATE support_tickets SET status = 'CLOSED'", "DELETE FROM support_messages",
                      "UPDATE support_flags SET state = 'HEEDED'", "INSERT INTO kb_articles (user_id) VALUES (ew_current_user())"):
        with pytest.raises(errors.InsufficientPrivilege):
            query(app, s1, statement)
    assert scalar(app, s1, "SELECT status FROM support_tickets WHERE id = %s", (t1,)) == "NEW"
    assert owner_scalar(owner, "SELECT to_regclass('support_ai_calls') IS NULL AND to_regclass('support_ai_limits') IS NULL")
