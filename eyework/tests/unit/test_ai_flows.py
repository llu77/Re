"""
المراجعة والمساعد على قاعدةٍ مصطنعة
====================================
الخدمتان نفسهما بلا PostgreSQL: مؤشّرٌ مصطنع يجيب كل عبارةٍ ثابتة بما تُجيب به
القاعدة، ويرفع ما ترفعه (قيودٌ بأسمائها). يُثبت ترتيب الخطوات حول القاعدة:
ما يُفتح ومتى، وما يُغلق بأيّ نتيجة، ومتى يُعاد المقعد، وما يصل الجواب.
اختبارات الواجهة البرمجية (`tests/api/test_ai_*.py`) تُثبت الشيء نفسه على
القاعدة الحقيقية.
"""

from __future__ import annotations

import datetime
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from psycopg import errors as pg_errors

from eyework import assistant, clock, reviewer
from eyework.assistant_prompt import DONT_KNOW_TEXT
from eyework.model_gateway import Guard
from eyework.professions import Profession
from eyework.reviewer import ISOLATE, MESSAGES, ReviewFeature, ReviewRunner, Snapshot
from eyework.reviewer_prompt import Catalogue, Check
from eyework.service_errors import Conflict, Invalid, NotFound
from eyework.tests.fakes import REASON, FakeGateway, assistant_reply, flag, model_reply, review_reply

USER = uuid4()
DOC = uuid4()
DIGEST = bytes(range(32))
NAME = "سارة"


class _Violation(pg_errors.CheckViolation):
    """خطأ قاعدةٍ باسم قيده، كما تصنعه RAISE EXCEPTION … USING CONSTRAINT."""

    def __init__(self, constraint: str) -> None:
        super().__init__(constraint)
        self._constraint = constraint

    @property
    def diag(self):
        return SimpleNamespace(constraint_name=self._constraint)


class FakeCursor:
    def __init__(self, db: "FakeDatabase") -> None:
        self.db = db
        self._rows: list[dict] = []

    def execute(self, statement: str, params: tuple = ()) -> None:
        self.db.executed.append((statement, params))
        handler = self.db.handlers.get(statement)
        if handler is None:
            raise AssertionError(f"عبارةٌ بلا معالج: {statement[:60]!r}")
        result = handler(params)
        if isinstance(result, BaseException):
            raise result
        self._rows = list(result or [])

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeDatabase:
    """`session()` كما في `eyework.db`: مؤشّرٌ بهوية. المعالجات بعبارتها الثابتة."""

    def __init__(self) -> None:
        self.handlers: dict = {}
        self.executed: list[tuple] = []
        self.sessions: list[UUID | None] = []

    @contextmanager
    def session(self, user_id: UUID | None = None):
        self.sessions.append(user_id)
        yield FakeCursor(self)

    def params_of(self, statement: str) -> list[tuple]:
        return [params for executed, params in self.executed if executed == statement]


# ── الأداة البديلة ───────────────────────────────────────────────────────
CATALOGUE = Catalogue("STOCK_REVIEW", (
    Check("PRICE_IMPLAUSIBLE", frozenset({"CHECK_DOC"}), frozenset({"unit_cost"}), True, "سعر",
          lambda payload, line: ("شاهد من الخادم",)),
), "رقم السطر")
BEGIN, RECORD, DIGEST_SQL = "SELECT begin(%s)", "SELECT record(%s, %s, %s) AS outcome", "SELECT digest(%s) AS digest"


def _load(cursor, user_id, kind, subject_id, expected_row_version) -> Snapshot:
    return Snapshot({"lines": [{"line": 1, "item": "شاي"}]}, DIGEST)


FEATURE = ReviewFeature("STOCK_REVIEW", frozenset({"CHECK_DOC"}), Profession.STOREKEEPER, CATALOGUE, BEGIN, RECORD,
                        DIGEST_SQL, _load, frozenset({"lines"}))


def _flag_row(**overrides) -> dict:
    row = {"id": uuid4(), "check_code": "PRICE_IMPLAUSIBLE", "severity": "HIGH", "field": "unit_cost", "line_no": 1,
           "reason": REASON, "suggestion": None, "evidence": ["شاهد من الخادم"], "content_digest": DIGEST,
           "decision": None}
    row.update(overrides)
    return row


@pytest.fixture
def db(monkeypatch) -> FakeDatabase:
    monkeypatch.setitem(reviewer.FEATURES, "STOCK_REVIEW", FEATURE)
    # الأداة البديلة وحدها: ما تسجّله مساحة المخزون لنوع المرتجع لا يُرى هنا.
    monkeypatch.setattr(reviewer, "KIND_FEATURES", {})
    fake = FakeDatabase()
    fake.handlers[reviewer._STORED_REVIEW] = lambda params: []
    fake.handlers[reviewer._DISPLAY_NAME] = lambda params: [{"name": NAME}]
    fake.handlers[reviewer._USAGE] = lambda params: [{"per_day": 30, "used_today": 1}]
    fake.handlers[reviewer._FAIL] = lambda params: []
    fake.handlers[BEGIN] = lambda params: [{"request_id": uuid4(), "digest": DIGEST}]
    fake.handlers[RECORD] = lambda params: [{"outcome": "OK"}]
    fake.handlers[reviewer._FLAGS_FOR_REQUEST] = lambda params: [_flag_row()]
    fake.handlers[reviewer._FLAGS_FOR_DIGEST] = lambda params: [_flag_row()]
    return fake


@pytest.fixture
def runner():
    runner = ReviewRunner(FakeGateway(), Guard(slots=2), wait_seconds=5.0)
    runner.start()
    yield runner
    runner.close()


def _review(db, runner):
    return reviewer.review(db, runner, USER, "STOCK_REVIEW", "CHECK_DOC", DOC, 1)


def _slots_free(runner) -> bool:
    if runner.guard.acquire() is not None:
        return False
    runner.guard.release()
    return True


# ── المراجعة ────────────────────────────────────────────────────────────
def test_a_full_review_opens_records_and_answers_done_with_the_headline(db, runner):
    runner.gateway.queue(review_reply(flag(line=1)))
    body = _review(db, runner)
    assert body["review"] == {"status": "DONE", "reason": None, "message": None}
    assert body["subject"]["digest"] == DIGEST.hex()
    (shown,) = body["flags"]
    assert shown["headline"] == f"يا {ISOLATE[0]}{NAME}{ISOLATE[1]}، {REASON}" and shown["evidence"] == ["شاهد من الخادم"]
    assert body["usage"] == {"per_day": 30, "used_today": 1}

    ((request_id, flags_json, usage_json),) = db.params_of(RECORD)
    assert isinstance(request_id, UUID)
    assert json.loads(flags_json) == [{"check": "PRICE_IMPLAUSIBLE", "severity": "HIGH", "field": "unit_cost",
                                       "line": 1, "reason": REASON, "suggestion": flag()["suggestion"],
                                       "evidence": ["شاهد من الخادم"]}]
    assert set(json.loads(usage_json)) == {"input", "output", "cache_read", "cache_write", "model", "prompt_version",
                                           "api_request_id"}
    assert db.params_of(reviewer._FAIL) == [] and _slots_free(runner)
    assert all(session == USER for session in db.sessions)


def test_a_stored_review_is_returned_without_a_call_or_a_row(db, runner):
    db.handlers[reviewer._STORED_REVIEW] = lambda params: [{"?column?": 1}]
    body = _review(db, runner)
    assert body["review"]["status"] == "DONE" and len(body["flags"]) == 1
    assert runner.gateway.calls == [] and db.params_of(BEGIN) == [] and _slots_free(runner)


def test_an_open_breaker_or_no_slot_opens_nothing(db, runner):
    for _ in range(3):
        runner.guard.record(model_reply("UPSTREAM_TIMEOUT"))
    down = _review(db, runner)["review"]
    assert down == {"status": "UNAVAILABLE", "reason": "DOWN", "message": MESSAGES["DOWN"]}
    runner.guard.breaker.reset()
    assert runner.guard.acquire() is None and runner.guard.acquire() is None
    try:
        assert _review(db, runner)["review"]["reason"] == "BUSY"
    finally:
        runner.guard.release()
        runner.guard.release()
    assert db.params_of(BEGIN) == [] and runner.gateway.calls == []


@pytest.mark.parametrize(("constraint", "reason"), [
    ("ai_rate", "RATE"), ("ai_daily_cap", "DAILY"), ("ai_new_account_daily_cap", "DAILY"),
    ("ai_feature_app_cap", "APP"), ("generation_global_cap", "APP"), ("generation_new_accounts_cap", "APP"),
])
def test_a_cap_raised_by_the_database_is_unavailable_with_its_reason(db, runner, constraint, reason):
    db.handlers[BEGIN] = lambda params: _Violation(constraint)
    body = _review(db, runner)
    assert body["review"] == {"status": "UNAVAILABLE", "reason": reason, "message": MESSAGES[reason]}
    assert runner.gateway.calls == [] and _slots_free(runner)


def test_a_review_already_running_is_pending_for_the_same_subject_and_busy_for_another(db, runner):
    db.handlers[BEGIN] = lambda params: _Violation("ai_request_in_progress")
    db.handlers[reviewer._IN_FLIGHT] = lambda params: [
        {"subject_kind": "CHECK_DOC", "subject_id": DOC, "content_digest": DIGEST}]
    assert _review(db, runner)["review"] == {"status": "PENDING", "reason": None, "message": MESSAGES["PENDING"]}
    db.handlers[reviewer._IN_FLIGHT] = lambda params: [
        {"subject_kind": "CHECK_DOC", "subject_id": uuid4(), "content_digest": DIGEST}]
    assert _review(db, runner)["review"]["reason"] == "BUSY"
    assert _slots_free(runner)


def test_a_review_that_completed_meanwhile_is_done_from_the_store(db, runner):
    db.handlers[BEGIN] = lambda params: _Violation("ai_review_current")
    body = _review(db, runner)
    assert body["review"]["status"] == "DONE" and len(body["flags"]) == 1


def test_an_unknown_constraint_and_a_missing_subject_propagate(db, runner):
    db.handlers[BEGIN] = lambda params: _Violation("something_else")
    with pytest.raises(pg_errors.CheckViolation):
        _review(db, runner)
    db.handlers[BEGIN] = lambda params: pg_errors.NoDataFound("doc")
    with pytest.raises(NotFound):
        _review(db, runner)
    assert _slots_free(runner)


def test_a_held_review_is_pending_and_records_late(db, runner):
    runner.wait_seconds = 0.05
    runner.gateway.hold()
    runner.gateway.queue(review_reply(flag(line=1)))
    recorded = threading.Event()
    db.handlers[RECORD] = lambda params: (recorded.set(), [{"outcome": "OK"}])[1]
    body = _review(db, runner)
    assert body["review"] == {"status": "PENDING", "reason": None, "message": MESSAGES["PENDING"]}
    assert body["flags"] == [] and db.params_of(RECORD) == []
    runner.gateway.release()
    assert recorded.wait(5.0) and _slots_free(runner)


@pytest.mark.parametrize(("reply", "reason"), [
    (model_reply("UPSTREAM_TIMEOUT"), "DOWN"), (model_reply("UPSTREAM_BUSY", retry_after=30), "DOWN"),
    (model_reply("REFUSED"), "FAILED"), (model_reply("OUTPUT_INVALID"), "FAILED"),
])
def test_a_failed_call_closes_the_request_with_its_outcome(db, runner, reply, reason):
    runner.gateway.queue(reply)
    body = _review(db, runner)
    assert body["review"]["reason"] == reason and body["review"]["message"] == MESSAGES[reason]
    ((request_id, outcome, usage_json),) = db.params_of(reviewer._FAIL)
    assert outcome == reply.outcome and isinstance(request_id, UUID)
    assert json.loads(usage_json)["prompt_version"] == "rv-2026-10-09.1"
    assert db.params_of(RECORD) == [] and _slots_free(runner)


def test_a_discarded_record_is_unavailable_and_a_broken_record_still_closes_the_request(db, runner):
    db.handlers[RECORD] = lambda params: [{"outcome": "DISCARDED"}]
    assert _review(db, runner)["review"]["reason"] == "FAILED"
    # المزوّد عالج الاستدعاء ثم تعذّر تسجيله: يُغلق OUTPUT_INVALID بما استُهلك، فيُعدّ في السقوف.
    db.handlers[RECORD] = lambda params: RuntimeError("connection lost")
    assert _review(db, runner)["review"]["reason"] == "FAILED"
    ((_, outcome, usage_json),) = db.params_of(reviewer._FAIL)
    assert outcome == "OUTPUT_INVALID" and json.loads(usage_json)["prompt_version"] == "rv-2026-10-09.1"
    assert _slots_free(runner)
    # ولم يصل الاستدعاء إلى المزوّد أصلاً: انقطاعٌ بلا استهلاك.
    runner.gateway.call = lambda request: (_ for _ in ()).throw(RuntimeError("reset"))
    assert _review(db, runner)["review"]["reason"] == "FAILED"
    assert db.params_of(reviewer._FAIL)[-1][1:] == ("UPSTREAM_ERROR", None) and _slots_free(runner)


def test_a_review_that_calls_nothing_during_the_trial_returns_the_permit(db, runner, monkeypatch):
    """بعد فتح القاطع: مراجعةٌ مخزونة أو سقفٌ لا يستهلك الإذن التجريبي، فالضغطة التالية تصل المزوّد."""
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    for _ in range(3):
        runner.guard.record(model_reply("UPSTREAM_TIMEOUT"))
    now[0] = 61.0
    db.handlers[reviewer._STORED_REVIEW] = lambda params: [{"?column?": 1}]
    assert _review(db, runner)["review"]["status"] == "DONE"
    db.handlers[reviewer._STORED_REVIEW] = lambda params: []
    db.handlers[BEGIN] = lambda params: _Violation("ai_rate")
    assert _review(db, runner)["review"]["reason"] == "RATE"
    assert runner.gateway.calls == [] and runner.guard.breaker.is_open
    db.handlers[BEGIN] = lambda params: [{"request_id": uuid4(), "digest": DIGEST}]
    assert _review(db, runner)["review"]["status"] == "DONE"
    assert len(runner.gateway.calls) == 1 and not runner.guard.breaker.is_open


def test_an_unknown_feature_or_kind_is_not_found_before_any_slot(db, runner):
    with pytest.raises(NotFound):
        reviewer.review(db, runner, USER, "SUPPORT_REPLY_REVIEW", "REPLY", DOC, None)
    with pytest.raises(NotFound):
        reviewer.review(db, runner, USER, "STOCK_REVIEW", "RETURN", DOC, None)
    assert db.executed == []


# ── القرارات ───────────────────────────────────────────────────────────
def _flag_record(**overrides) -> dict:
    row = {"id": uuid4(), "feature": "STOCK_REVIEW", "subject_kind": "CHECK_DOC", "subject_id": DOC,
           "content_digest": DIGEST, "closed_at": None}
    row.update(overrides)
    return row


def test_decisions_check_closure_and_both_digests_before_the_database_decides(db):
    decided = datetime.datetime(2026, 10, 9, 8, 12, 3, tzinfo=datetime.timezone.utc)
    flag_id = uuid4()
    db.handlers[reviewer._FLAG] = lambda params: [_flag_record(id=flag_id)]
    db.handlers[DIGEST_SQL] = lambda params: [{"digest": DIGEST}]
    db.handlers[reviewer._DECIDE] = lambda params: [{"choice": params[1], "decided_at": decided}]
    assert reviewer.decide(db, USER, flag_id, "PROCEED", DIGEST.hex()) == {
        "flag_id": str(flag_id), "decision": "PROCEED", "decided_at": "2026-10-09T08:12:03+00:00"}
    assert db.params_of(reviewer._DECIDE) == [(flag_id, "PROCEED")]

    with pytest.raises(Conflict) as stale:
        reviewer.decide(db, USER, flag_id, "PROCEED", "00" * 32)
    assert stale.value.code == "FLAG_STALE"
    db.handlers[DIGEST_SQL] = lambda params: [{"digest": None}]
    with pytest.raises(Conflict) as moved:
        reviewer.decide(db, USER, flag_id, "EDIT", DIGEST.hex())
    assert moved.value.code == "FLAG_STALE"
    db.handlers[reviewer._FLAG] = lambda params: [_flag_record(closed_at=decided)]
    with pytest.raises(Conflict) as closed:
        reviewer.decide(db, USER, flag_id, "EDIT", DIGEST.hex())
    assert closed.value.code == "FLAG_CLOSED"
    db.handlers[reviewer._FLAG] = lambda params: []
    with pytest.raises(NotFound):
        reviewer.decide(db, USER, flag_id, "EDIT", DIGEST.hex())
    assert len(db.params_of(reviewer._DECIDE)) == 1


def test_a_flag_of_an_unregistered_feature_is_not_decided(db, monkeypatch):
    """بلا دالّة بصمةٍ للموضوع لا يُعرف إن تغيّر، فلا قرار: 404 لا قرارٌ مسجَّل على محتوىً لم يعد يُرى."""
    flag_id = uuid4()
    db.handlers[reviewer._FLAG] = lambda params: [_flag_record(id=flag_id)]
    monkeypatch.delitem(reviewer.FEATURES, "STOCK_REVIEW")
    with pytest.raises(NotFound) as gone:
        reviewer.decide(db, USER, flag_id, "PROCEED", DIGEST.hex())
    assert gone.value.detail == reviewer.NO_REVIEW and db.params_of(reviewer._DECIDE) == []


def test_the_undecided_conflict_carries_only_flags_without_proceed(db):
    db.handlers[reviewer._FLAGS_FOR_DIGEST] = lambda params: [
        _flag_row(decision="PROCEED"), _flag_row(decision="UNDO"), _flag_row(decision=None)]
    conflict = reviewer.flags_undecided(db, USER, "CHECK_DOC", DOC, DIGEST)
    assert conflict.code == "FLAGS_UNDECIDED" and conflict.detail == reviewer.FLAGS_UNDECIDED
    assert [item["decision"] for item in conflict.extra["flags"]] == ["UNDO", None]


# ── المساعد ─────────────────────────────────────────────────────────────
@pytest.fixture
def assistant_db() -> FakeDatabase:
    fake = FakeDatabase()
    fake.handlers[assistant._PROFESSION] = lambda params: [{"profession": "MARKETING"}]
    fake.handlers[assistant._CAMPAIGN_COUNTS] = lambda params: [{"status": "READY", "n": 2}]
    fake.handlers[assistant._RECENT_CAMPAIGNS] = lambda params: [
        {"status": "READY", "title": "حقيبة جلدية", "updated": datetime.date(2026, 10, 9)}]
    fake.handlers[assistant._BEGIN] = lambda params: [{"request": uuid4()}]
    fake.handlers[assistant._FINISH] = lambda params: []
    fake.handlers[assistant._FAIL] = lambda params: []
    fake.handlers[reviewer._USAGE] = lambda params: [{"per_day": 60, "used_today": 1}]
    return fake


def _ask(db, gateway, guard=None, **options):
    options = {"screen_kind": "HOME", "screen_id": None, "question": None, "ready": 0, **options}
    return assistant.ask(db, gateway, guard or Guard(), USER, options["screen_kind"], options["screen_id"],
                         options["question"], options["ready"])


def test_a_question_sends_the_screens_lines_and_closes_the_request_ok(assistant_db):
    gateway = FakeGateway()
    body = _ask(assistant_db, gateway, question="هل أتصل بالعميل على 0551234567؟", ready=None)
    assert body["status"] == "ANSWER" and body["question_sent"] == "هل أتصل بالعميل على [رقم]؟"
    assert body["usage"] == {"per_day": 60, "used_today": 1}
    (call,) = gateway.calls
    assert "حملاتك: 2 جاهزة" in call.user and "حقيبة جلدية" in call.user and "0551234567" not in call.user
    ((_, outcome, usage_json),) = assistant_db.params_of(assistant._FINISH)
    assert outcome == "OK" and json.loads(usage_json)["prompt_version"] == "as-2026-10-09.1"


def test_dont_know_is_recorded_as_such_and_an_invalid_answer_fails_billable(assistant_db):
    gateway = FakeGateway(assistant_reply("DONT_KNOW"), assistant_reply(answer="زر https://x.example"))
    body = _ask(assistant_db, gateway)
    assert (body["status"], body["text"], body["sources"]) == ("DONT_KNOW", DONT_KNOW_TEXT, [])
    assert assistant_db.params_of(assistant._FINISH)[0][1] == "DONT_KNOW"
    with pytest.raises(assistant.AssistantError) as error:
        _ask(assistant_db, gateway)
    assert error.value.code == "AI_INVALID"
    assert assistant_db.params_of(assistant._FAIL)[0][1] == "OUTPUT_INVALID"


def test_an_upstream_failure_and_a_crash_close_the_request_and_free_the_slot(assistant_db):
    guard = Guard(slots=1)
    gateway = FakeGateway(model_reply("UPSTREAM_BUSY", retry_after=20))
    with pytest.raises(assistant.AssistantError) as error:
        _ask(assistant_db, gateway, guard)
    assert (error.value.code, error.value.retry_after_seconds) == ("AI_UNAVAILABLE", 20)
    assert assistant_db.params_of(assistant._FAIL)[0][1] == "UPSTREAM_BUSY"

    class _Exploding:
        def call(self, request):
            raise RuntimeError("reset")

    with pytest.raises(RuntimeError):
        _ask(assistant_db, _Exploding(), guard)
    assert assistant_db.params_of(assistant._FAIL)[1][1] == "UPSTREAM_ERROR"
    assert guard.acquire() is None


def test_a_question_refused_before_the_call_returns_the_trial_permit(assistant_db, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(clock, "monotonic", lambda: now[0])
    guard = Guard(slots=1)
    for _ in range(3):
        guard.record(model_reply("UPSTREAM_TIMEOUT"))
    now[0] = 61.0
    assistant_db.handlers[assistant._BEGIN] = lambda params: _Violation("ai_daily_cap")
    with pytest.raises(_Violation):                # السقف يُترجم في طبقة الويب؛ هنا يصل كما هو
        _ask(assistant_db, FakeGateway(), guard)
    assert guard.acquire() is None                 # الإذن عاد، ولم يُستهلك على سقفٍ
    guard.release(called=False)


def test_the_guard_refuses_before_any_database_access(assistant_db):
    guard = Guard(slots=1)
    for _ in range(3):
        guard.record(model_reply("UPSTREAM_TIMEOUT"))
    with pytest.raises(assistant.AssistantError) as error:
        _ask(assistant_db, FakeGateway(), guard)
    assert error.value.code == "AI_UNAVAILABLE" and assistant_db.executed == []


def test_screens_outside_the_profession_or_without_their_id_are_refused(assistant_db):
    with pytest.raises(NotFound):
        _ask(assistant_db, FakeGateway(), screen_kind="TICKET")
    with pytest.raises(Invalid) as error:
        _ask(assistant_db, FakeGateway(), screen_kind="CAMPAIGN")
    assert (error.value.code, error.value.field) == ("SCREEN_ID", "screen")
    with pytest.raises(Invalid) as error:
        _ask(assistant_db, FakeGateway(), ready=3)
    assert error.value.field == "ready_question"
    assistant_db.handlers[assistant._PROFESSION] = lambda params: [{"profession": "STOREKEEPER"}]
    with pytest.raises(NotFound):
        _ask(assistant_db, FakeGateway(), screen_kind="CAMPAIGN", screen_id=uuid4())
    assert assistant_db.params_of(assistant._BEGIN) == []


def test_fit_keeps_whole_items_and_counts_the_rest():
    assert assistant.fit(["أ" * 10, "ب" * 10, "ج" * 10], budget=25) == ("أ" * 10, "ب" * 10, "و1 بنداً آخر")
    assert assistant.fit(["أ" * 10], budget=25) == ("أ" * 10,)
