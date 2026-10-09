"""
طبقة الذكاء الاصطناعي — في القاعدة (0009)
========================================
ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو النموذج، بدور الويب نفسه الذي
يحمله الخادم:

  • كل استدعاءٍ للنموذج صفٌّ في الدفتر يُفتح قبل الاستدعاء بسقوفه: واحدٌ جارٍ لكل
    مستخدمٍ وأداة، وحدّ عشر دقائق ويومٍ (أضيق للحساب المفتوح الجديد)، وحدّ الأداة في
    التطبيق، والسقف العام الذي يجمع الحملات وهذه معاً في `ew_ai_spend`. ولا محتوى فيه.
  • تنبيه المراجِع مقترحٌ لا قرار: لمحتوىً بعينه، ولا يُكتب إن تغيّر أثناء المراجعة؛
    والاعتماد لا يمرّ وعليه تنبيهٌ لم يُقرَّر فيه «تابع رغم ذلك»، ثم يُغلق التنبيه.
  • القرارات سجلٌّ يُضاف إليه، والتنبيه لا يُعدَّل، ونصّه يُمحى مع نصوص موضوعه،
    ويُنسى مع موضوعه، ويترك حذفُ الحساب أثر ما فُوتر في يومه.
  • العزل بالصفّ مفروضٌ على الكل، ودور الويب لا يكتب جدولاً ولا يستدعي دالّةً
    داخلية.

الموضوع هنا مسارٌ بديل (`check_docs` بأغلفته، كما يكتبها ترحيل أداةٍ حقيقية)
تُنشئه تجهيزةٌ بدور المالك وتُسقطه بعد كل اختبار.
"""

from __future__ import annotations

import json
import re
import threading
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework.tests.conftest import as_user, create_campaign, make_user, register_open
from eyework.tests.db.test_state_machine import blocked_on_a_lock

# ── المسار البديل ───────────────────────────────────────────────────────
_TRACK_UP = """
CREATE TABLE check_docs (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body    text NOT NULL,
    status  text NOT NULL DEFAULT 'DRAFT'
);
ALTER TABLE check_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE check_docs FORCE ROW LEVEL SECURITY;
CREATE POLICY check_docs_own ON check_docs FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY check_docs_owner ON check_docs FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
GRANT SELECT ON check_docs TO eyework_app;
CREATE TRIGGER trg_check_docs_forget AFTER DELETE ON check_docs
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('CHECK_DOC');

CREATE FUNCTION check_digest(p uuid) RETURNS bytea LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT sha256(convert_to(body, 'UTF8')) FROM check_docs WHERE id = p AND status = 'DRAFT'
$$;
CREATE FUNCTION check_review_begin(p uuid) RETURNS TABLE (request_id uuid, digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE d bytea;
BEGIN
    PERFORM 1 FROM check_docs WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'doc' USING ERRCODE = 'no_data_found'; END IF;
    d := check_digest(p);
    RETURN QUERY SELECT ew_ai_request_open('STOCK_REVIEW', 'CHECK_DOC', p, d), d;
END $$;
CREATE FUNCTION check_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r ai_requests%ROWTYPE; d bytea;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = ew_current_user();
    SELECT check_digest(c.id) INTO d FROM check_docs c WHERE c.id = r.subject_id FOR UPDATE;
    RETURN ew_ai_flags_put(p_request, d, p_flags, p_usage);
END $$;
CREATE FUNCTION check_commit(p uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    PERFORM 1 FROM check_docs WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT' FOR UPDATE;
    n := ew_ai_gate('CHECK_DOC', p, check_digest(p));
    UPDATE check_docs SET status = 'POSTED' WHERE id = p;
    RETURN n;
END $$;
CREATE FUNCTION check_edit(p uuid, b text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    UPDATE check_docs SET body = b WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT'
$$;
CREATE FUNCTION check_erase(p uuid) RETURNS integer
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_ai_erase_subject('CHECK_DOC', p)
$$;
GRANT EXECUTE ON FUNCTION check_review_begin(uuid), check_review_record(uuid, jsonb, jsonb), check_commit(uuid),
                          check_edit(uuid, text), check_erase(uuid) TO eyework_app;
"""
_TRACK_DOWN = """
DROP TABLE IF EXISTS check_docs CASCADE;
DROP FUNCTION IF EXISTS check_digest(uuid), check_review_begin(uuid), check_review_record(uuid, jsonb, jsonb),
                        check_commit(uuid), check_edit(uuid, text), check_erase(uuid);
"""

USAGE = json.dumps({"input": 2400, "output": 310, "cache_read": 1900, "cache_write": 0,
                    "model": "claude-opus-5-5", "prompt_version": "2026-10-09.1", "api_request_id": "req_011abc"})
REASON = "سعر الوحدة في السطر 3 أعلى بعشرة أضعاف من آخر شراء."
SUGGESTION = "تأكّد من سعر الوحدة؛ ربما أُدخل سعر الكرتونة."


def flag(check_code: str = "PRICE_IMPLAUSIBLE", line: int = 3, reason: str = REASON,
         suggestion: str | None = SUGGESTION, severity: str = "HIGH", field: str = "unit_cost") -> dict:
    """تنبيهٌ كما يعيده الخادم بعد فحص جواب النموذج: مفاتيحه السبعة لا غير."""
    return {"check": check_code, "severity": severity, "field": field, "line": line, "reason": reason,
            "suggestion": suggestion, "evidence": ["آخر سعر شراء: ٤٫٥٠ ريال"]}


@pytest.fixture
def track(owner):
    """المسار البديل: جدول موضوعٍ وأغلفته — مراجعةٌ تبدأ وتُسجَّل، واعتمادٌ يمرّ بالبوابة، وتعديلٌ ومحو."""
    with owner.cursor() as cursor:
        cursor.execute(_TRACK_DOWN)
        cursor.execute(_TRACK_UP)
    try:
        yield
    finally:
        with owner.cursor() as cursor:
            cursor.execute(_TRACK_DOWN)


@pytest.fixture
def keeper(owner) -> UUID:
    return make_user(owner, login=b"keeper", profession="STOREKEEPER")


@pytest.fixture
def other(owner) -> UUID:
    return make_user(owner, login=b"other-keeper", profession="STOREKEEPER")


@pytest.fixture
def marketer(owner) -> UUID:
    return make_user(owner, login=b"marketer", profession="MARKETING")


# ── مساعدات ─────────────────────────────────────────────────────────────
def query(connection, user: UUID | None, statement: str, params: tuple = ()) -> list[tuple]:
    """عبارةٌ بدور الاتصال بهوية صاحب الجلسة (أو بلا هوية)."""
    as_user(connection, user)
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall() if cursor.description else []


def scalar(connection, user: UUID | None, statement: str, params: tuple = ()):
    return query(connection, user, statement, params)[0][0]


def owner_scalar(owner, statement: str, params: tuple = ()):
    with owner.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


def constraint_of(attempt) -> str | None:
    """اسم القيد الذي رُفضت به المحاولة — أو رمز الحالة إن لم يُسمَّ قيد — أو None إن مرّت."""
    try:
        attempt()
    except psycopg.Error as exc:
        return exc.diag.constraint_name or exc.sqlstate
    return None


def ask(app, user: UUID) -> UUID:
    return scalar(app, user, "SELECT ew_assistant_begin()")


def fail(app, user: UUID, request: UUID, outcome: str = "UPSTREAM_BUSY") -> None:
    query(app, user, "SELECT ew_ai_request_fail(%s, %s, NULL)", (request, outcome))


def seed_requests(owner, user: UUID, count: int, *, outcome: str = "OK", feature: str = "ASSISTANT",
                  new_account: bool = False, age: str = "2 hours") -> None:
    """استدعاءاتٌ مُغلقة قبل ساعتين: خارج نافذة الدقائق العشر، داخل اليوم."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome, new_account)"
            " SELECT %s, %s, now() - %s::interval, now() - %s::interval, %s, %s FROM generate_series(1, %s)",
            (user, feature, age, age, outcome, new_account, count))


def new_doc(owner, user: UUID, body: str = "v1") -> UUID:
    return owner_scalar(owner, "INSERT INTO check_docs (user_id, body) VALUES (%s, %s) RETURNING id", (user, body))


def review(app, user: UUID, doc: UUID) -> tuple[UUID, bytes]:
    return query(app, user, "SELECT * FROM check_review_begin(%s)", (doc,))[0]


def record(app, user: UUID, request: UUID, flags: list[dict]) -> str:
    return scalar(app, user, "SELECT check_review_record(%s, %s, %s)", (request, json.dumps(flags), USAGE))


def flags_of(app, user: UUID, doc: UUID) -> list[tuple]:
    return query(app, user, "SELECT id, check_code, severity, line_no, position FROM ai_flags"
                            " WHERE subject_id = %s ORDER BY position", (doc,))


def decide(app, user: UUID, flag_id: UUID, choice: str) -> tuple:
    return query(app, user, "SELECT * FROM ew_ai_decide(%s, %s)", (flag_id, choice))[0]


def commit(app, user: UUID, doc: UUID) -> int:
    return scalar(app, user, "SELECT check_commit(%s)", (doc,))


def reviewed_doc(owner, app, user: UUID) -> tuple[UUID, UUID, UUID, UUID]:
    """مسودةٌ روجعت فكُتب عليها تنبيهان: (الموضوع، الاستدعاء، الأول، الثاني)."""
    doc = new_doc(owner, user)
    request, _ = review(app, user, doc)
    assert record(app, user, request, [
        flag(), flag("UNIT_MISMATCH", 2, "الوحدة «كيلو» لا تناسب صنفاً يُعدّ بالحبّة.", None, "MEDIUM", "unit"),
    ]) == "OK"
    first, second = (row[0] for row in flags_of(app, user, doc))
    return doc, request, first, second


# ── دفتر المساعد ────────────────────────────────────────────────────────
def test_a_second_question_while_one_is_open_is_refused(app, keeper):
    """ضغطةٌ مكرّرة لا تفتح استدعاءً ثانياً للمستخدم والأداة نفسيهما."""
    ask(app, keeper)
    assert constraint_of(lambda: ask(app, keeper)) == "ai_request_in_progress"


def test_finishing_a_question_records_its_outcome_and_numbers_only(owner, app, keeper):
    request = ask(app, keeper)
    query(app, keeper, "SELECT ew_assistant_finish(%s, 'OK', %s)", (request, USAGE))
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, input_tokens, cache_read_tokens, served_model, new_account, finished_at IS NOT NULL"
                       " FROM ai_requests WHERE id = %s", (request,))
        assert cursor.fetchone() == ("OK", 2400, 1900, "claude-opus-5-5", False, True)


def test_the_ledger_has_no_column_that_could_hold_content(owner):
    """لا سؤال ولا جواب ولا نصّ: ما لا عمود له لا يُخزَّن بخطأ."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_requests'")
        columns = {row[0] for row in cursor.fetchall()}
    assert not (columns & {"question", "answer", "prompt", "text", "content", "body"}), sorted(columns)


def test_a_question_cannot_finish_with_a_review_outcome(app, keeper):
    request = ask(app, keeper)
    assert constraint_of(lambda: query(app, keeper, "SELECT ew_assistant_finish(%s, 'CANNOT_ANSWER', NULL)",
                                       (request,))) == "ai_outcome_needs_record"


def test_a_settled_request_cannot_be_settled_again(app, keeper):
    request = ask(app, keeper)
    query(app, keeper, "SELECT ew_assistant_finish(%s, 'OK', %s)", (request, USAGE))
    assert constraint_of(lambda: fail(app, keeper, request, "UPSTREAM_ERROR")) == "ai_request_not_open"


def test_the_eleventh_question_in_ten_minutes_is_refused(app, keeper):
    for _ in range(10):
        fail(app, keeper, ask(app, keeper))
    assert constraint_of(lambda: ask(app, keeper)) == "ai_rate"


def test_usage_shows_the_professions_features_and_counts_billable_requests_only(app, keeper):
    """أمين المخزون يرى المساعد ومراجعة المخزون وحدهما؛ وفشلٌ لم يُفوتر لا يُعدّ."""
    query(app, keeper, "SELECT ew_assistant_finish(%s, 'OK', %s)", (ask(app, keeper), USAGE))
    for _ in range(3):
        fail(app, keeper, ask(app, keeper))
    usage = {feature: (per_day, used) for feature, per_day, used in query(app, keeper, "SELECT * FROM ew_ai_my_usage()")}
    assert usage == {"ASSISTANT": (60, 1), "STOCK_REVIEW": (30, 0)}


def test_the_sixty_first_billable_question_in_a_day_is_refused(owner, app, keeper):
    seed_requests(owner, keeper, 60)
    assert constraint_of(lambda: ask(app, keeper)) == "ai_daily_cap"


def test_a_new_open_account_asks_fifteen_times_a_day(owner, app):
    fresh, _ = register_open(app, "fresh@example.sa", profession="SUPPORT")
    seed_requests(owner, fresh, 15, new_account=True)
    assert constraint_of(lambda: ask(app, fresh)) == "ai_new_account_daily_cap"
    assert dict((f, p) for f, p, _ in query(app, fresh, "SELECT * FROM ew_ai_my_usage()"))["ASSISTANT"] == 15


def test_a_feature_of_another_profession_cannot_be_opened(owner, app, track, marketer):
    doc = new_doc(owner, marketer)
    assert constraint_of(lambda: review(app, marketer, doc)) == "ai_feature_profession"


# ── المراجِع ────────────────────────────────────────────────────────────
def test_a_review_writes_its_flags_and_settles_the_request_with_their_count(owner, app, track, keeper):
    doc, request, _, _ = reviewed_doc(owner, app, keeper)
    assert [row[1:] for row in flags_of(app, keeper, doc)] == [("PRICE_IMPLAUSIBLE", "HIGH", 3, 1),
                                                              ("UNIT_MISMATCH", "MEDIUM", 2, 2)]
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, flags_count, input_tokens FROM ai_requests WHERE id = %s", (request,))
        assert cursor.fetchone() == ("OK", 2, 2400)


def test_another_user_sees_none_of_the_flags_or_requests(owner, app, track, keeper, other):
    reviewed_doc(owner, app, keeper)
    assert scalar(app, other, "SELECT count(*) FROM ai_flags") == 0
    assert scalar(app, other, "SELECT count(*) FROM ai_requests") == 0
    assert scalar(app, keeper, "SELECT count(*) FROM ai_flags") == 2


def test_the_same_content_is_not_reviewed_twice(owner, app, track, keeper):
    doc, _, _, _ = reviewed_doc(owner, app, keeper)
    assert constraint_of(lambda: review(app, keeper, doc)) == "ai_review_current"


def test_undecided_flags_block_the_commit(owner, app, track, keeper):
    doc, _, _, _ = reviewed_doc(owner, app, keeper)
    assert constraint_of(lambda: commit(app, keeper, doc)) == "ai_flags_undecided"
    assert owner_scalar(owner, "SELECT status FROM check_docs WHERE id = %s", (doc,)) == "DRAFT"


def test_undo_before_proceed_is_refused(owner, app, track, keeper):
    _, _, first, _ = reviewed_doc(owner, app, keeper)
    assert constraint_of(lambda: decide(app, keeper, first, "UNDO")) == "ai_decision_undo"


def test_repeating_the_standing_decision_adds_no_row(owner, app, track, keeper):
    _, _, first, _ = reviewed_doc(owner, app, keeper)
    once = decide(app, keeper, first, "EDIT")
    assert decide(app, keeper, first, "EDIT") == once
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (first,)) == 1


def test_an_undone_proceed_blocks_the_commit_again(owner, app, track, keeper):
    doc, _, first, second = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    decide(app, keeper, second, "PROCEED")
    decide(app, keeper, second, "UNDO")
    assert constraint_of(lambda: commit(app, keeper, doc)) == "ai_flags_undecided"


def test_another_user_cannot_decide_on_the_flags(owner, app, track, keeper, other):
    _, _, first, _ = reviewed_doc(owner, app, keeper)
    with pytest.raises(errors.NoDataFound):
        decide(app, other, first, "PROCEED")
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flag_decisions") == 0


def test_proceed_on_every_flag_lets_the_commit_pass_and_closes_them(owner, app, track, keeper):
    doc, _, first, second = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    decide(app, keeper, second, "PROCEED")
    assert commit(app, keeper, doc) == 2
    assert owner_scalar(owner, "SELECT status FROM check_docs WHERE id = %s", (doc,)) == "POSTED"
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flags WHERE subject_id = %s AND closed_at IS NULL", (doc,)) == 0


def test_a_closed_flag_takes_no_decision(owner, app, track, keeper):
    doc, _, first, second = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    decide(app, keeper, second, "PROCEED")
    commit(app, keeper, doc)
    assert constraint_of(lambda: decide(app, keeper, first, "EDIT")) == "ai_flag_closed"


def test_the_audit_trail_is_complete_and_in_order(owner, app, track, keeper):
    _, _, _, second = reviewed_doc(owner, app, keeper)
    for choice in ("PROCEED", "UNDO", "PROCEED"):
        decide(app, keeper, second, choice)
    with owner.cursor() as cursor:
        cursor.execute("SELECT choice FROM ai_flag_decisions WHERE flag_id = %s ORDER BY id", (second,))
        assert [row[0] for row in cursor.fetchall()] == ["PROCEED", "UNDO", "PROCEED"]


def test_decisions_cannot_be_updated_even_by_the_owner(owner, app, track, keeper):
    _, _, first, _ = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    with pytest.raises(errors.InsufficientPrivilege), owner.cursor() as cursor:
        cursor.execute("UPDATE ai_flag_decisions SET choice = 'EDIT' WHERE flag_id = %s", (first,))


def test_flag_texts_cannot_be_rewritten_even_by_the_owner(owner, app, track, keeper):
    _, _, first, _ = reviewed_doc(owner, app, keeper)
    with pytest.raises(errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("UPDATE ai_flags SET reason = 'سببٌ آخر مختلف تماماً هنا.' WHERE id = %s", (first,))
    assert caught.value.diag.constraint_name == "ai_flag_immutable"


def test_content_changed_during_the_review_is_discarded_and_writes_no_flag(owner, app, track, keeper):
    """تنبيهٌ عن محتوىً آخر لا يُعرض: البصمة الحالية غير بصمة البدء فيُغلق الاستدعاء DISCARDED."""
    doc = new_doc(owner, keeper, "a")
    request, _ = review(app, keeper, doc)
    query(app, keeper, "SELECT check_edit(%s, 'b')", (doc,))
    assert record(app, keeper, request, [flag()]) == "DISCARDED"
    assert flags_of(app, keeper, doc) == []
    assert owner_scalar(owner, "SELECT outcome FROM ai_requests WHERE id = %s", (request,)) == "DISCARDED"


def test_the_gate_passes_content_with_no_flags(owner, app, track, keeper):
    """المساعد لا يمنع بغيابه: ما لا تنبيه عليه يُعتمد."""
    doc = new_doc(owner, keeper, "clean")
    assert commit(app, keeper, doc) == 0
    assert owner_scalar(owner, "SELECT status FROM check_docs WHERE id = %s", (doc,)) == "POSTED"


def test_a_reason_carrying_a_link_is_refused_by_the_table(owner, app, track, keeper):
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    assert constraint_of(lambda: record(app, keeper, request, [flag(reason="راجع https://example.com قبل التسجيل الآن.")])) \
        == "ai_flag_texts"


def test_a_fourth_flag_is_refused(owner, app, track, keeper):
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    assert constraint_of(lambda: record(app, keeper, request, [flag(line=i) for i in (1, 2, 3, 4)])) == "ai_flags_shape"


def test_an_extra_key_in_a_flag_is_refused(owner, app, track, keeper):
    """مفتاحٌ زائد — اسمٌ مثلاً — لا يدخل التنبيه: الاسم يضيفه الخادم عند العرض لا قبله."""
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    assert constraint_of(lambda: record(app, keeper, request, [{**flag(), "name": "سارة"}])) == "ai_flags_shape"


def test_a_successful_result_after_the_lease_is_refused(owner, app, track, keeper):
    """بعد عقد الاستدعاء لا يُعدّ جارياً، ولا تُكتب نتيجةٌ ناجحة جاءت متأخّرة."""
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE ai_requests SET started_at = now() - interval '2 minutes' WHERE id = %s", (request,))
    assert constraint_of(lambda: record(app, keeper, request, [flag()])) == "ai_request_not_open"
    assert flags_of(app, keeper, doc) == []


def test_a_failure_after_the_lease_is_still_recorded(owner, app, track, keeper):
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE ai_requests SET started_at = now() - interval '2 minutes' WHERE id = %s", (request,))
    fail(app, keeper, request, "UPSTREAM_TIMEOUT")
    assert owner_scalar(owner, "SELECT outcome FROM ai_requests WHERE id = %s", (request,)) == "UPSTREAM_TIMEOUT"


def test_erasing_the_subject_removes_the_texts_and_keeps_the_code_and_decisions(owner, app, track, keeper):
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    record(app, keeper, request, [flag()])
    flag_id = flags_of(app, keeper, doc)[0][0]
    decide(app, keeper, flag_id, "PROCEED")
    assert scalar(app, keeper, "SELECT check_erase(%s)", (doc,)) == 1
    with owner.cursor() as cursor:
        cursor.execute("SELECT reason, suggestion, evidence, check_code, erased_at IS NOT NULL FROM ai_flags WHERE id = %s",
                       (flag_id,))
        assert cursor.fetchone() == (None, None, [], "PRICE_IMPLAUSIBLE", True)
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (flag_id,)) == 1


def test_deleting_the_subject_deletes_its_flags_and_their_decisions(owner, app, track, keeper):
    doc = new_doc(owner, keeper)
    request, _ = review(app, keeper, doc)
    record(app, keeper, request, [flag()])
    flag_id = flags_of(app, keeper, doc)[0][0]
    decide(app, keeper, flag_id, "PROCEED")
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM check_docs WHERE id = %s", (doc,))
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flags WHERE id = %s", (flag_id,)) == 0
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (flag_id,)) == 0


# ── دور الويب ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("statement", [
    "INSERT INTO ai_requests (user_id, feature) VALUES (%s, 'ASSISTANT')",
    "UPDATE ai_flags SET closed_at = now() WHERE user_id = %s",
    "DELETE FROM ai_flag_decisions WHERE user_id = %s",
])
def test_the_web_role_cannot_write_the_ai_tables(app, keeper, statement):
    """كل كتابةٍ دالّة: استدعاءٌ يُكتب مباشرةً يتخطّى السقوف، وتنبيهٌ يُغلق مباشرةً يتخطّى القرار."""
    as_user(app, keeper)
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement, (keeper,))
    assert "permission denied" in (caught.value.diag.message_primary or "")


@pytest.mark.parametrize("statement", [
    "SELECT ew_ai_request_open('ASSISTANT', NULL, NULL, NULL)",
    "SELECT ew_ai_gate('CHECK_DOC', gen_random_uuid(), sha256('x'::bytea))",
    "SELECT ew_ai_flags_put(gen_random_uuid(), NULL, '[]', NULL)",
    "SELECT ew_ai_spend(false)",
])
def test_the_web_role_cannot_call_the_internal_functions(app, keeper, statement):
    as_user(app, keeper)
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement)
    assert "permission denied" in (caught.value.diag.message_primary or "")


def test_the_web_role_cannot_read_the_feature_table(app, keeper):
    """السقوف تصل الويب عبر ew_ai_my_usage بحصّة صاحب الجلسة، لا بجدول الأدوات كلّه."""
    as_user(app, keeper)
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM ai_features")
    assert "permission denied" in (caught.value.diag.message_primary or "")


# ── الإنفاق والسقف العام ────────────────────────────────────────────────
def test_ew_ai_spend_counts_every_ledger_and_the_new_account_share(owner, app, keeper, marketer):
    """دالّةٌ واحدة تجمع محاولات الحملة ودفتر الأدوات وأثر المحذوف — في يومها وممّا ربما فُوتر."""
    campaign = create_campaign(app, marketer, with_image=False)
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at,"
            " outcome, new_account) VALUES (%s, %s, 'INITIAL', sha256('x'::bytea), now() - interval '1 hour',"
            " now() - interval '1 hour', 'OK', true)", (campaign, marketer))
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome, new_account) VALUES"
                       " (now() - interval '1 hour', 'OK', true), (now() - interval '25 hours', 'OK', true)")
    seed_requests(owner, keeper, 1, new_account=True)
    seed_requests(owner, keeper, 1, new_account=False)
    seed_requests(owner, keeper, 1, outcome="UPSTREAM_BUSY", new_account=True)
    with owner.cursor() as cursor:
        cursor.execute("SELECT ew_ai_spend(false), ew_ai_spend(true)")
        assert cursor.fetchone() == (4, 3)


def test_the_global_cap_counts_requests_campaigns_and_tombstones_together(owner, app, keeper):
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome)"
                       " SELECT now(), 'OK' FROM generate_series(1, 2000 - ew_ai_spend(false)::int)")
    assert constraint_of(lambda: ask(app, keeper)) == "generation_global_cap"


def test_campaign_generation_counts_the_shared_spend(owner):
    """ew_begin_generation يعدّ بالدالّة الموحّدة نفسها، فلا سقفان يختلفان."""
    body = owner_scalar(owner, "SELECT prosrc FROM pg_proc WHERE proname = 'ew_begin_generation'")
    assert "ew_ai_spend(false) >= 2000" in body
    assert "fresh AND ew_ai_spend(true) >= 400" in body


def test_every_ledger_with_a_new_account_flag_is_counted_by_ew_ai_spend(owner):
    """ترحيلٌ يضيف دفتراً آخر (أعمدة outcome وstarted_at وnew_account) يعيد كتابة ew_ai_spend، وإلا فشل هنا."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT table_name FROM information_schema.columns WHERE table_schema = 'public'"
                       " AND column_name IN ('outcome', 'started_at', 'new_account')"
                       " GROUP BY table_name HAVING count(*) = 3 ORDER BY table_name")
        ledgers = [row[0] for row in cursor.fetchall()]
    source = owner_scalar(owner, "SELECT prosrc FROM pg_proc WHERE proname = 'ew_ai_spend'")
    assert {"ai_requests", "attempt_tombstones", "generation_attempts"} <= set(ledgers)
    assert [table for table in ledgers if not re.search(rf"\bFROM {table}\b", source)] == []


def test_deleting_an_account_leaves_one_tombstone_per_billable_request_of_the_day(owner, app, keeper):
    seed_requests(owner, keeper, 1, outcome="OK", new_account=True, age="1 hour")
    seed_requests(owner, keeper, 1, outcome="REFUSED", age="2 hours")
    seed_requests(owner, keeper, 1, outcome="UPSTREAM_BUSY", age="3 hours")
    seed_requests(owner, keeper, 1, outcome="OK", age="25 hours")
    with owner.cursor() as cursor:
        cursor.execute("SELECT started_at, outcome, new_account FROM ai_requests"
                       " WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours' ORDER BY started_at")
        expected = cursor.fetchall()
    assert [row[1] for row in expected] == ["REFUSED", "OK"]
    query(app, keeper, "SELECT ew_delete_me()")
    with owner.cursor() as cursor:
        cursor.execute("SELECT started_at, outcome, new_account FROM attempt_tombstones ORDER BY started_at")
        assert cursor.fetchall() == expected


def test_deleting_an_account_removes_its_flags_and_decisions(owner, app, track, keeper):
    _, _, first, second = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    query(app, keeper, "SELECT ew_delete_me()")
    with owner.cursor() as cursor:
        cursor.execute("SELECT (SELECT count(*) FROM ai_flags), (SELECT count(*) FROM ai_flag_decisions),"
                       "       (SELECT count(*) FROM ai_requests), (SELECT count(*) FROM check_docs)")
        assert cursor.fetchone() == (0, 0, 0, 0)


# ── السباقات ────────────────────────────────────────────────────────────
def test_two_requests_at_one_below_the_global_cap_are_serialized(owner, app, app_url, keeper, other):
    """طلبان لمستخدمَين يريان الإنفاق نفسه فيمرّان معاً لولا القفل العام؛ الثاني ينتظر الأول ثم يُرفض."""
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome) SELECT now(), 'OK' FROM generate_series(1, 1999)")
    outcome = {}
    with psycopg.connect(app_url) as first, psycopg.connect(app_url) as second:
        for connection, user in ((first, keeper), (second, other)):
            as_user(connection, user)
            connection.commit()
        # بلا autocommit: الأول معاملةٌ مفتوحة تحمل القفل العام حتى تُثبَّت.
        with first.cursor() as cursor:
            cursor.execute("SELECT ew_assistant_begin()")

        def ask_second() -> None:
            try:
                with second.cursor() as cursor:
                    cursor.execute("SELECT ew_assistant_begin()")
                second.commit()
                outcome["opened"] = True
            except errors.CheckViolation as exc:
                second.rollback()
                outcome["constraint"] = exc.diag.constraint_name

        racer = threading.Thread(target=ask_second)
        racer.start()
        waited = blocked_on_a_lock(app, second.info.backend_pid, racer)
        first.commit()
        racer.join(timeout=10)
    assert waited
    assert outcome == {"constraint": "generation_global_cap"}
    assert owner_scalar(owner, "SELECT count(*) FROM ai_requests") == 1


@pytest.mark.parametrize("leader", ["commit", "undo"])
def test_an_undo_and_a_commit_racing_on_one_flag_are_serialized(owner, app, app_url, track, keeper, leader):
    """
    «تراجع» عن «تابع رغم ذلك» والاعتمادُ في اللحظة نفسها: من سبق قفل صفّ التنبيه،
    والثاني ينتظره ثم يُرفض — فلا يُعتمد عملٌ تُرُوجع عن تنبيهه، ولا يُتراجع عمّا اعتُمد.
    """
    doc, _, first, second = reviewed_doc(owner, app, keeper)
    decide(app, keeper, first, "PROCEED")
    decide(app, keeper, second, "PROCEED")
    outcome = {}
    with psycopg.connect(app_url) as committer, psycopg.connect(app_url) as undoer:
        for connection in (committer, undoer):
            as_user(connection, keeper)
            connection.commit()
        commit_sql, undo_sql = ("SELECT check_commit(%s)", (doc,)), ("SELECT * FROM ew_ai_decide(%s, 'UNDO')", (first,))
        if leader == "commit":
            lead, follow, lead_sql, follow_sql = committer, undoer, commit_sql, undo_sql
        else:
            lead, follow, lead_sql, follow_sql = undoer, committer, undo_sql, commit_sql
        with lead.cursor() as cursor:
            cursor.execute(*lead_sql)
            outcome["lead"] = cursor.fetchone()

        def follow_up() -> None:
            try:
                with follow.cursor() as cursor:
                    cursor.execute(*follow_sql)
                    outcome["follow"] = cursor.fetchone()
                follow.commit()
            except errors.CheckViolation as exc:
                follow.rollback()
                outcome["follow"] = exc.diag.constraint_name

        racer = threading.Thread(target=follow_up)
        racer.start()
        waited = blocked_on_a_lock(app, follow.info.backend_pid, racer)
        lead.commit()
        racer.join(timeout=10)
    assert waited
    status = owner_scalar(owner, "SELECT status FROM check_docs WHERE id = %s", (doc,))
    trail = [row[0] for row in query(app, keeper, "SELECT choice FROM ai_flag_decisions WHERE flag_id = %s ORDER BY id",
                                     (first,))]
    if leader == "commit":
        assert (outcome["lead"], outcome["follow"], status, trail) == ((2,), "ai_flag_closed", "POSTED", ["PROCEED"])
    else:
        assert outcome["lead"][0] == "UNDO"
        assert (outcome["follow"], status, trail) == ("ai_flags_undecided", "DRAFT", ["PROCEED", "UNDO"])
