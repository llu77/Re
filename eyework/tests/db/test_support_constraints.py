"""
مكتب الدعم: قيود 0011 التي لم يبلغها اختبارٌ بعد
=============================================
كل قيدٍ هنا يُبلَغ كما يبلغه الموظف من الواجهة: بدوالّ دور الويب، حتى يُرفض الطلب باسم قيده. وما لا تبلغه دالّة
(حاجز محفّزٍ خلف الدوالّ) يكتبه المالك مباشرةً فيُرفض هو أيضاً. والسقوف تُملأ بالدوالّ نفسها، أو بصفوفٍ قديمة يكتبها
المالك حين تطول الحلقة. وضغطتان معاً على ردٍّ واحد (نسخٌ أو تأكيد إرسال) لا تكتبان حدثين ولا تعدّان مرتين.
"""

from __future__ import annotations

import json
import threading
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework.tests.db.test_ai_layer import constraint_of, owner_scalar, query, scalar
from eyework.tests.db.test_state_machine import blocked_on_a_lock
from eyework.tests.db.test_support_desk import (ANSWER, NOTICE, QUOTE, ROUTER, answered, backdate, begin_draft, cite,
                                                desk_user, prepare, published, record_draft, refusal, release, rv, sha,
                                                ticket)

UPDATE = "نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة."
ADD = "SELECT ew_support_add_message(%s, %s, %s, %s, 0::smallint, gen_random_uuid())"
CREATE = "SELECT ew_support_create_ticket(gen_random_uuid(), 'EMAIL', 'NORMAL', NULL, NULL, NULL, %s, 0::smallint)"
FOLLOW_UP = "SELECT ew_support_follow_up(%s, gen_random_uuid(), 'عاد الانقطاع اليوم مرة أخرى', 0::smallint)"
FROM_DRAFT = "SELECT ew_support_prepare_reply(%s, %s, gen_random_uuid(), %s, %s, false, %s, %s, NULL)"
KB_CREATE = ("SELECT ew_kb_create(gen_random_uuid(), %s, 'الطابعة لا تطبع أيّ صفحة.', NULL, '1. أعد تشغيل الطابعة.',"
             " NULL, NULL)")
KB_ADD = ("SELECT ew_kb_add_version(%s, %s, 'انقطاع الإنترنت عن المكتب كله', 'الإنترنت مقطوع عن كل الأجهزة في المكتب',"
          " NULL, %s, NULL)")
SET_STATE = "SELECT ew_kb_set_state(%s, %s, %s)"
PUBLISH = "SELECT ew_kb_publish(%s, %s, %s::smallint)"


# ── أدوات ───────────────────────────────────────────────────────────────
def account(owner, app, *, fresh: bool) -> UUID:
    """حساب دعمٍ قرأ الإشعار؛ fresh: سجّل نفسه اليوم من التسجيل المفتوح، فسقوفه أدنى."""
    user = desk_user(owner, b"s1", app=app)
    if fresh:
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET self_registered = true, open_registered = true, terms_version = %s,"
                           " terms_accepted_at = now() WHERE id = %s", (NOTICE, user))
    return user


def add(app, user, t: UUID, body: str, author: str = "CUSTOMER") -> UUID:
    return scalar(app, user, ADD, (t, rv(app, user, "support_tickets", t), author, body))


def owner_refusal(owner, statement: str, params: tuple) -> str | None:
    """كتابةٌ مباشرة بالمالك يردّها حاجز المحفّز: يُرجَع اسم قيدها."""
    with owner.cursor() as cursor, pytest.raises(errors.CheckViolation) as refused:
        cursor.execute(statement, params)
    return refused.value.diag.constraint_name


def race(app, app_url, user, statement: str, params: tuple) -> str | None:
    """الضغطة الأولى في معاملةٍ مفتوحة والثانية معها من اتصالٍ آخر: تنتظرها حتى تلتزم، ثم يُرجَع ما رُفضت به."""
    outcome: dict[str, object] = {}
    connected = threading.Event()
    with psycopg.connect(app_url) as holder:
        query(holder, user, statement, params)   # تبقى معاملتها مفتوحة

        def racer() -> None:
            with psycopg.connect(app_url, autocommit=True) as other:
                outcome["pid"] = other.info.backend_pid
                connected.set()
                outcome["constraint"] = constraint_of(lambda: query(other, user, statement, params))

        thread = threading.Thread(target=racer)
        thread.start()
        assert connected.wait(5)
        assert blocked_on_a_lock(app, outcome["pid"], thread)
        holder.commit()
        thread.join(5)
    assert not thread.is_alive()
    return outcome["constraint"]


def events(app, user, reply: UUID, event: str) -> int:
    return scalar(app, user, "SELECT count(*) FROM support_events WHERE reply_id = %s AND event = %s", (reply, event))


# ── المسودة والردّ ──────────────────────────────────────────────────────
def test_a_reply_is_prepared_only_from_the_latest_standing_draft_that_has_text(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    d1 = answered(app, s1, t1, a1)
    d2 = answered(app, s1, t1, a1)
    # مسودةٌ جاءت بعدها أحدث منها.
    assert refusal(app, s1, FROM_DRAFT, (t1, rv(app, s1, "support_tickets", t1), d1, "ANSWER", ANSWER, ANSWER)) \
        == "support_reply_draft_not_current"
    # الأحدث بعد أن رفضها الموظف.
    query(app, s1, "SELECT ew_support_reject_draft(%s, 'TONE', NULL)", (d2,))
    assert refusal(app, s1, FROM_DRAFT, (t1, rv(app, s1, "support_tickets", t1), d2, "ANSWER", ANSWER, ANSWER)) \
        == "support_reply_draft_not_current"
    # مسودة تذكرةٍ أخرى.
    t2 = ticket(app, s1, "البريد لا يصلني منذ أمس", channel="EMAIL", label=None)
    other = answered(app, s1, t2, a1)
    assert refusal(app, s1, FROM_DRAFT, (t1, rv(app, s1, "support_tickets", t1), other, "ANSWER", ANSWER, ANSWER)) \
        == "support_reply_draft_not_current"
    # الأحدث وليس فيها نصٌّ للعميل (الرسالة ليست طلب دعم).
    request, based_on = begin_draft(app, s1, t1)
    d3 = record_draft(app, s1, request, based_on, result="NOT_SUPPORT", kind=None, body=None,
                      note="الرسالة إعلانٌ وليست طلب دعم.")
    assert refusal(app, s1, FROM_DRAFT, (t1, rv(app, s1, "support_tickets", t1), d3, "UPDATE", UPDATE, UPDATE)) \
        == "support_reply_draft_not_current"
    assert scalar(app, s1, "SELECT count(*) FROM support_replies WHERE ticket_id = %s", (t1,)) == 0

    d4 = answered(app, s1, t1, a1)
    reply = prepare(app, s1, t1, draft=d4)
    assert scalar(app, s1, "SELECT origin FROM support_replies WHERE id = %s", (reply,)) == "AS_IS"


def test_a_rule_flag_quotes_the_reply_it_is_raised_on(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    core = "نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة خلال ساعة."
    body = f"مرحباً سارة،\n\n{core}\n\nفريق الدعم الفني"
    elsewhere = json.dumps([{"code": "PROMISE", "evidence": "سنحلّ المشكلة اليوم حتماً"}])
    assert constraint_of(lambda: prepare(app, s1, t1, kind="UPDATE", core=core, body=body, flags=elsewhere)) \
        == "support_flag_evidence_verbatim"
    # لا ردٌّ ولا تنبيهٌ بقيا من المحاولة.
    assert scalar(app, s1, "SELECT count(*) FROM support_replies WHERE ticket_id = %s", (t1,)) == 0
    assert scalar(app, s1, "SELECT count(*) FROM support_flags WHERE ticket_id = %s", (t1,)) == 0

    # الاقتباس حرفيٌّ بعد التوحيد (المسافات واحدة).
    spaced = json.dumps([{"code": "PROMISE", "evidence": "وسنعود   إليكم بالنتيجة خلال ساعة"}])
    reply = prepare(app, s1, t1, kind="UPDATE", core=core, body=body, flags=spaced)
    assert scalar(app, s1, "SELECT count(*) FROM support_flags WHERE reply_id = %s AND code = 'PROMISE'", (reply,)) == 1


def test_a_draft_cites_only_the_version_published_now_of_its_own_articles(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    s2 = desk_user(owner, b"s2", app=app)
    t1 = ticket(app, s1)
    live = published(app, s1)
    unpublished = scalar(app, s1, "SELECT ew_kb_create(gen_random_uuid(), 'انقطاع الإنترنت في الفرع',"
                                  " 'الإنترنت مقطوع عن كل الأجهزة في الفرع', NULL, %s, NULL, NULL)", (ROUTER,))
    archived = published(app, s1, "انقطاع الإنترنت بعد التحديث")
    query(app, s1, SET_STATE, (archived, rv(app, s1, "kb_articles", archived), "ARCHIVED"))
    foreign = published(app, s2)
    # نسخةٌ ثانية لم تُنشر، والأولى منشورةٌ بعد.
    query(app, s1, KB_ADD, (live, rv(app, s1, "kb_articles", live), ROUTER + " 3. إن عاد الانقطاع فسجّل وقت حدوثه."))
    newer = json.dumps([{"article_id": str(live), "version": 2, "quote": QUOTE}])

    request, based_on = begin_draft(app, s1, t1)
    for citations in (cite(unpublished), cite(archived), cite(foreign), newer):
        assert constraint_of(lambda c=citations: record_draft(app, s1, request, based_on, citations=c)) \
            == "support_citation_not_published", citations
    draft = record_draft(app, s1, request, based_on, citations=cite(live))
    assert query(app, s1, "SELECT article_id, article_version FROM support_draft_citations WHERE draft_id = %s",
                 (draft,)) == [(live, 1)]


def test_an_agent_message_is_only_the_sent_reply_itself_even_for_the_owner(owner, app):
    """رسالة الموظف يكتبها تأكيد الإرسال وحده: لا دالّة تكتبها غيره، فالحاجز يُختبر بكتابة المالك."""
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    t2 = ticket(app, s1, "البريد لا يصلني منذ أمس", channel="EMAIL", label=None)
    reply = prepare(app, s1, t1, kind="UPDATE", core=UPDATE)
    release(app, s1, reply)
    body = scalar(app, s1, "SELECT body FROM support_replies WHERE id = %s", (reply,))
    insert = "INSERT INTO support_messages (ticket_id, user_id, author, body, reply_id) VALUES (%s, %s, 'AGENT', %s, %s)"
    # نُسخ ولم يؤكّد الموظف إرساله.
    assert owner_refusal(owner, insert, (t1, s1, body, reply)) == "support_agent_message_needs_sent_reply"
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (reply,))
    # نصٌّ غير الذي أُرسل، أو ردُّ تذكرةٍ أخرى.
    assert owner_refusal(owner, insert, (t1, s1, "نصٌّ آخر غير الذي أرسله الموظف إلى العميل.", reply)) \
        == "support_agent_message_needs_sent_reply"
    assert owner_refusal(owner, insert, (t2, s1, body, reply)) == "support_agent_message_needs_sent_reply"
    assert owner_scalar(owner, "SELECT count(*) FROM support_messages WHERE author = 'AGENT'") == 1


def test_a_draft_in_a_live_or_sent_reply_cannot_be_rejected(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    reject = "SELECT ew_support_reject_draft(%s, 'WRONG_INFO', NULL)"
    d1 = answered(app, s1, t1, a1)
    r1 = prepare(app, s1, t1, draft=d1)
    assert refusal(app, s1, reject, (d1,)) == "support_draft_in_use"        # جاهز
    query(app, s1, "SELECT ew_support_confirm_reply(%s, false)", (r1,))
    query(app, s1, "SELECT ew_support_reject_draft(%s, 'TONE', NULL)", (d1,))   # سُحب ردّها فتُرفض

    d2 = answered(app, s1, t1, a1)
    r2 = prepare(app, s1, t1, draft=d2)
    release(app, s1, r2)
    assert refusal(app, s1, reject, (d2,)) == "support_draft_in_use"        # منسوخ
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (r2,))
    assert refusal(app, s1, reject, (d2,)) == "support_draft_in_use"        # مرسل
    assert scalar(app, s1, "SELECT rejected_at IS NULL FROM support_drafts WHERE id = %s", (d2,))
    # الرفض المردود لا يعلّم المقالة.
    assert scalar(app, s1, "SELECT needs_review FROM kb_articles WHERE id = %s", (a1,)) is False


def test_a_follow_up_is_opened_only_from_a_closed_ticket(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    assert refusal(app, s1, FOLLOW_UP, (t1,)) == "support_follow_up_needs_closed"
    # المحلولة لم تُغلق بعد: ردّ العميل يعيد فتحها، لا يفتح متابعة.
    query(app, s1, "SELECT ew_support_resolve(%s, %s, 'BY_PHONE', false)", (t1, rv(app, s1, "support_tickets", t1)))
    assert refusal(app, s1, FOLLOW_UP, (t1,)) == "support_follow_up_needs_closed"
    assert scalar(app, s1, "SELECT count(*) FROM support_tickets") == 1

    backdate(owner, "UPDATE support_tickets SET resolved_at = now() - interval '5 days' WHERE id = %s", (t1,))
    assert scalar(app, s1, "SELECT ew_support_close_due()") == 1
    follow = scalar(app, s1, FOLLOW_UP, (t1,))
    assert scalar(app, s1, "SELECT follow_up_of FROM support_tickets WHERE id = %s", (follow,)) == t1


# ── قاعدة المعرفة ───────────────────────────────────────────────────────
def test_only_the_latest_version_is_published_even_by_the_owner(owner, app):
    """الدالّة تردّ النسخة الأقدم قبل المحفّز (ما رآه الموظف ليس الأحدث)، فالحاجز يُختبر بكتابة المالك."""
    s1 = desk_user(owner, b"s1", app=app)
    article = scalar(app, s1, "SELECT ew_kb_create(gen_random_uuid(), 'انقطاع الإنترنت عن المكتب كله',"
                              " 'الإنترنت مقطوع عن كل الأجهزة في المكتب', NULL, %s, NULL, NULL)", (ROUTER,))
    query(app, s1, KB_ADD, (article, rv(app, s1, "kb_articles", article), ROUTER + " 3. إن عاد الانقطاع فسجّل وقته."))
    assert refusal(app, s1, PUBLISH, (article, rv(app, s1, "kb_articles", article), 1)) == "stale_row_version"
    assert owner_refusal(owner, "UPDATE kb_articles SET state = 'PUBLISHED', published_version = 1 WHERE id = %s",
                         (article,)) == "kb_publish_latest_only"
    query(app, s1, PUBLISH, (article, rv(app, s1, "kb_articles", article), 2))
    # والمنشورة لا تُعاد إلى نسختها الأقدم.
    assert owner_refusal(owner, "UPDATE kb_articles SET published_version = 1 WHERE id = %s", (article,)) \
        == "kb_publish_latest_only"
    assert scalar(app, s1, "SELECT published_version FROM kb_articles WHERE id = %s", (article,)) == 2


def test_an_article_moves_only_along_its_states(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    draft = scalar(app, s1, KB_CREATE, ("الطابعة لا تطبع",))
    live = published(app, s1)

    def to(article: UUID, state: str) -> str | None:
        return refusal(app, s1, SET_STATE, (article, rv(app, s1, "kb_articles", article), state))

    assert to(draft, "ARCHIVED") == "kb_article_transition"     # لم تُنشر قط
    assert to(draft, "PUBLISHED") == "kb_article_transition"    # النشر بـew_kb_publish وحدها
    assert to(live, "DISCARDED") == "kb_article_transition"     # المنشورة تُؤرشف ولا تُهمل
    query(app, s1, SET_STATE, (draft, rv(app, s1, "kb_articles", draft), "DISCARDED"))
    # المهملة لا تعود ولا تُنشر ولا تُضاف إليها نسخة.
    assert to(draft, "ARCHIVED") == "kb_article_transition"
    assert refusal(app, s1, PUBLISH, (draft, rv(app, s1, "kb_articles", draft), 1)) == "kb_article_transition"
    assert refusal(app, s1, KB_ADD, (draft, rv(app, s1, "kb_articles", draft), ROUTER)) == "kb_article_transition"
    query(app, s1, SET_STATE, (live, rv(app, s1, "kb_articles", live), "ARCHIVED"))
    assert to(live, "DISCARDED") == "kb_article_transition"
    # المؤرشفة تُنشر ثانيةً.
    query(app, s1, PUBLISH, (live, rv(app, s1, "kb_articles", live), 1))
    assert query(app, s1, "SELECT id, state, latest_version FROM kb_articles ORDER BY number") == [
        (draft, "DISCARDED", 1), (live, "PUBLISHED", 1)]


def test_the_knowledge_base_holds_at_most_three_hundred_live_articles(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    # مئتان وتسعٌ وتسعون مقالةً كُتبت قبل أيام: سقف اليوم من النسخ (مئة) لا يمنع ما بعدها.
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("INSERT INTO kb_articles (user_id) SELECT %s FROM generate_series(1, 299)", (s1,))
        cursor.execute("INSERT INTO kb_versions (article_id, user_id, title, issue, resolution)"
                       " SELECT id, user_id, 'الطابعة لا تطبع ' || number, 'الطابعة لا تطبع أيّ صفحة.',"
                       " '1. أعد تشغيل الطابعة.' FROM kb_articles WHERE user_id = %s", (s1,))
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("ALTER TABLE kb_versions DISABLE TRIGGER USER")
        cursor.execute("UPDATE kb_versions SET created_at = now() - interval '3 days' WHERE user_id = %s", (s1,))
        cursor.execute("ALTER TABLE kb_versions ENABLE TRIGGER USER")
    query(app, s1, KB_CREATE, ("الطابعة لا تطبع 300",))
    assert refusal(app, s1, KB_CREATE, ("الطابعة لا تطبع 301",)) == "kb_article_cap"
    assert scalar(app, s1, "SELECT count(*) FROM kb_articles") == 300
    # المهملة لا تُحسب.
    old = scalar(app, s1, "SELECT id FROM kb_articles WHERE number = 1")
    query(app, s1, SET_STATE, (old, rv(app, s1, "kb_articles", old), "DISCARDED"))
    query(app, s1, KB_CREATE, ("الطابعة لا تطبع 301",))
    assert refusal(app, s1, KB_CREATE, ("الطابعة لا تطبع 302",)) == "kb_article_cap"


# ── السقوف ──────────────────────────────────────────────────────────────
def test_a_ticket_holds_at_most_sixty_messages(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    for n in range(59):
        add(app, s1, t1, f"رسالة رقم {n + 2} في المحادثة", "NOTE" if n % 2 else "CUSTOMER")
    assert scalar(app, s1, "SELECT count(*) FROM support_messages WHERE ticket_id = %s", (t1,)) == 60
    for author in ("CUSTOMER", "NOTE"):
        assert refusal(app, s1, ADD, (t1, rv(app, s1, "support_tickets", t1), author, "رسالة بعد الحدّ")) \
            == "support_message_cap", author
    # الحدّ للتذكرة لا للحساب.
    add(app, s1, ticket(app, s1, "البريد لا يصلني منذ أمس", channel="EMAIL", label=None), "وما زال لا يصل")
    # والردّ الذي أُرسل من القناة يُؤكَّد ولو بلغت التذكرة حدّها.
    reply = prepare(app, s1, t1, kind="UPDATE", core=UPDATE)
    release(app, s1, reply)
    query(app, s1, "SELECT ew_support_confirm_reply(%s, true)", (reply,))
    assert scalar(app, s1, "SELECT state FROM support_replies WHERE id = %s", (reply,)) == "SENT"
    assert scalar(app, s1, "SELECT count(*) FROM support_messages WHERE ticket_id = %s", (t1,)) == 61


@pytest.mark.parametrize("fresh, cap", [(True, 60), (False, 400)], ids=["new-open-account", "established"])
def test_customer_messages_a_day_are_capped_across_tickets(owner, app, fresh, cap):
    user = account(owner, app, fresh=fresh)
    tickets: list[UUID] = []
    for n in range(cap):   # خمسون رسالةً في كل تذكرة: دون حدّ التذكرة (ستون)
        if n % 50 == 0:
            tickets.append(ticket(app, user, f"رسالة العميل رقم {n + 1}"))
        else:
            add(app, user, tickets[-1], f"رسالة العميل رقم {n + 1}", "NOTE" if n % 7 == 0 else "CUSTOMER")
    last = tickets[-1]
    for author in ("CUSTOMER", "NOTE"):
        assert refusal(app, user, ADD, (last, rv(app, user, "support_tickets", last), author, "رسالة بعد الحدّ")) \
            == "support_daily_message_cap", author
    # ولا تذكرةٌ جديدة: رسالتها الأولى فوق الحدّ.
    assert refusal(app, user, CREATE, ("رسالة في تذكرة جديدة",)) == "support_daily_message_cap"
    assert scalar(app, user, "SELECT count(*) FROM support_tickets") == len(tickets)
    # ما مضى عليه يومٌ لا يُحسب.
    with owner.transaction(), owner.cursor() as cursor:
        cursor.execute("ALTER TABLE support_messages DISABLE TRIGGER USER")
        cursor.execute("UPDATE support_messages SET created_at = now() - interval '25 hours' WHERE ticket_id = %s",
                       (tickets[0],))
        cursor.execute("ALTER TABLE support_messages ENABLE TRIGGER USER")
    add(app, user, last, "رسالة في اليوم التالي")


@pytest.mark.parametrize("fresh, cap", [(True, 30), (False, 200)], ids=["new-open-account", "established"])
def test_tickets_opened_in_a_day_are_capped_even_once_closed(owner, app, fresh, cap):
    user = account(owner, app, fresh=fresh)
    first = ticket(app, user, "رسالة العميل رقم 1")
    for n in range(1, cap):
        ticket(app, user, f"رسالة العميل رقم {n + 1}")
    # كلها مغلقة: ليس حدّ المفتوحة ما يمنع التالية.
    backdate(owner, "UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE', clock_since = NULL,"
                    " closed_at = now() WHERE user_id = %s", (user,))
    assert refusal(app, user, CREATE, ("رسالة زائدة اليوم",)) == "support_daily_ticket_cap"
    assert refusal(app, user, FOLLOW_UP, (first,)) == "support_daily_ticket_cap"
    assert scalar(app, user, "SELECT count(*) FROM support_tickets") == cap
    # ما فُتح قبل يومٍ لا يُحسب.
    backdate(owner, "UPDATE support_tickets SET created_at = now() - interval '25 hours' WHERE user_id = %s", (user,))
    ticket(app, user, "رسالة في اليوم التالي")


# ── التزامن ─────────────────────────────────────────────────────────────
def test_two_releases_of_one_reply_at_once_release_it_once(owner, app, app_url):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    reply = prepare(app, s1, t1, kind="UPDATE", core=UPDATE)
    digest = sha(app, s1, reply)
    # الثانية تنتظر قفل الردّ، ثم تجده منسوخاً فتُردّ.
    assert race(app, app_url, s1, "SELECT ew_support_release_reply(%s, 'COPY', %s)", (reply, digest)) \
        == "support_reply_transition"
    assert scalar(app, s1, "SELECT state FROM support_replies WHERE id = %s", (reply,)) == "RELEASED"
    assert events(app, s1, reply, "REPLY_RELEASED") == 1


def test_two_confirmations_of_one_reply_at_once_send_it_once(owner, app, app_url):
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    a1 = published(app, s1)
    reply = prepare(app, s1, t1, draft=answered(app, s1, t1, a1))
    release(app, s1, reply)
    # الثانية تنتظر قفل الردّ، ثم تجده مرسلاً فتُردّ.
    assert race(app, app_url, s1, "SELECT ew_support_confirm_reply(%s, true)", (reply,)) == "support_reply_transition"
    assert scalar(app, s1, "SELECT state FROM support_replies WHERE id = %s", (reply,)) == "SENT"
    assert events(app, s1, reply, "REPLY_SENT") == 1
    assert events(app, s1, reply, "RESOLVED") == 1
    assert scalar(app, s1, "SELECT count(*) FROM support_messages WHERE reply_id = %s", (reply,)) == 1
    assert scalar(app, s1, "SELECT reuse_count FROM kb_articles WHERE id = %s", (a1,)) == 1
    assert scalar(app, s1, "SELECT count(*) FROM support_events WHERE ticket_id = %s AND event = 'STATUS_CHANGED'"
                           " AND to_status = 'RESOLVED'", (t1,)) == 1


def test_a_ticket_with_a_reply_not_yet_confirmed_is_neither_resolved_nor_returned(owner, app):
    """الردّ الجاهز أو المنسوخ يُرسل أو يُسحب أولاً: لا حلٌّ دونه ولا إعادةٌ من التصعيد."""
    s1 = desk_user(owner, b"s1", app=app)
    t1 = ticket(app, s1)
    live = prepare(app, s1, t1, kind="UPDATE", core=UPDATE)
    assert refusal(app, s1, "SELECT ew_support_resolve(%s, %s, 'BY_PHONE', true)",
                   (t1, rv(app, s1, "support_tickets", t1))) == "support_live_reply_exists"
    query(app, s1, "SELECT ew_support_confirm_reply(%s, false)", (live,))
    query(app, s1, "SELECT ew_support_escalate(%s, %s, 'VENDOR', 'الأضواء حمراء بعد إعادة التشغيل؛ يحتاج المزوّد إلى فحص الخط.')",
          (t1, rv(app, s1, "support_tickets", t1)))
    notice = prepare(app, s1, t1, kind="UPDATE", core=UPDATE)
    release(app, s1, notice)
    assert refusal(app, s1, "SELECT ew_support_return_escalation(%s, %s, 'أصلح المزوّد الخط.')",
                   (t1, rv(app, s1, "support_tickets", t1))) == "support_live_reply_exists"


def test_new_versions_of_an_article_count_toward_the_daily_version_cap(owner, app):
    s1 = desk_user(owner, b"s1", app=app)
    article = scalar(app, s1, KB_CREATE, ("الطابعة لا تطبع",))
    version = ("SELECT ew_kb_add_version(%s, %s, %s, 'الطابعة لا تطبع أيّ صفحة.', NULL, '1. أعد تشغيل الطابعة.', NULL)")
    for n in range(29):
        query(app, s1, version, (article, rv(app, s1, "kb_articles", article), f"الطابعة لا تطبع {n}"))
    for n in range(70):
        scalar(app, s1, KB_CREATE, (f"الماسح لا يعمل {n}",))
    # مئة نسخةٍ اليوم (ثلاثون لمقالةٍ وسبعون مقالة): الحادية بعد المئة تُردّ، نسخةً كانت أو مقالة.
    other = scalar(app, s1, "SELECT id FROM kb_articles WHERE latest_version = 1 ORDER BY number DESC LIMIT 1")
    assert refusal(app, s1, version, (other, rv(app, s1, "kb_articles", other), "الماسح لا يعمل أبداً")) \
        == "kb_daily_version_cap"
