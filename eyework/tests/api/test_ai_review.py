"""
المراجِع عبر الواجهة البرمجية
=============================
التطبيق الحقيقي بالبوّابة المصطنعة، وموضوعٌ بديل (`ai_api_docs`) تُنشئه
التجهيزة بدوالّه الثلاث كما تكتبها مساحات العمل (المواصفة §7.3)، لأن لا قائمة
فحوصٍ قبل الحزمة الثالثة. يُثبت: DONE بملاحظاتٍ وبدونها، وPENDING ثم النتيجة
المتأخّرة التي تحجز الاعتماد (409) حتى يُبتّ، و«غير متاح» لكل سببٍ والعمل يتابع،
والإبطال حين يتغيّر المحتوى، والقرارات بقواعدها، وبوّابة الموافقة والمهنة،
والاسم من القاعدة لا من النموذج، وسجلٌّ بلا محتوى.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
import json
import logging
import time
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, Request
from fastapi.routing import APIRoute
from psycopg import errors as pg_errors

from eyework import auth, config, reviewer
from eyework.db import Database
from eyework.model_gateway import Guard
from eyework.professions import Profession
from eyework.reviewer import ISOLATE, MESSAGES, ReviewFeature, Snapshot
from eyework.reviewer_prompt import Catalogue, Check
from eyework.service_errors import Conflict, Invalid, NotFound
from eyework.tests.api.conftest import LOGIN_KEY, ORIGIN, add_user, expect, log_in
from eyework.tests.conftest import app_url_for
from eyework.tests.fakes import REASON, SUGGESTION, FakeGateway, flag, model_reply, review_reply
from eyework.web.app import create_app
from eyework.web.deps import require_user

KEEPER = "keeper@example.sa"
OTHER = "other-keeper@example.sa"
MARKETER = "marketer@example.sa"
NAME = "سارة"
CANARY = "CANARY-9e1d4c"

# ── الموضوع البديل: جدولٌ ودوالّه الثلاث كما تكتبها مساحة عمل ─────────
_TRACK_UP = """
CREATE TABLE ai_api_docs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT',
    row_version integer NOT NULL DEFAULT 1
);
ALTER TABLE ai_api_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_api_docs FORCE ROW LEVEL SECURITY;
CREATE POLICY ai_api_docs_own ON ai_api_docs FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY ai_api_docs_owner ON ai_api_docs FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
GRANT SELECT ON ai_api_docs TO eyework_app;
CREATE TRIGGER trg_ai_api_docs_forget AFTER DELETE ON ai_api_docs
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('CHECK_DOC');

CREATE FUNCTION ai_api_digest(p uuid) RETURNS bytea
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT sha256(convert_to(body, 'UTF8')) FROM ai_api_docs
     WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT'
$$;
CREATE FUNCTION ai_api_review_begin(p uuid) RETURNS TABLE (request_id uuid, digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE d bytea;
BEGIN
    PERFORM 1 FROM ai_api_docs WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'doc' USING ERRCODE = 'no_data_found'; END IF;
    d := ai_api_digest(p);
    RETURN QUERY SELECT ew_ai_request_open('STOCK_REVIEW', 'CHECK_DOC', p, d), d;
END $$;
CREATE FUNCTION ai_api_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r ai_requests%ROWTYPE; d bytea;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = ew_current_user();
    SELECT ai_api_digest(c.id) INTO d FROM ai_api_docs c WHERE c.id = r.subject_id FOR UPDATE;
    RETURN ew_ai_flags_put(p_request, d, p_flags, p_usage);
END $$;
CREATE FUNCTION ai_api_commit(p uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    PERFORM 1 FROM ai_api_docs WHERE id = p AND user_id = ew_current_user() AND status = 'DRAFT' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'doc' USING ERRCODE = 'no_data_found'; END IF;
    n := ew_ai_gate('CHECK_DOC', p, ai_api_digest(p));
    UPDATE ai_api_docs SET status = 'POSTED' WHERE id = p;
    RETURN n;
END $$;
GRANT EXECUTE ON FUNCTION ai_api_digest(uuid), ai_api_review_begin(uuid), ai_api_review_record(uuid, jsonb, jsonb),
                          ai_api_commit(uuid) TO eyework_app;
"""
_TRACK_DOWN = """
DROP TABLE IF EXISTS ai_api_docs CASCADE;
DROP FUNCTION IF EXISTS ai_api_digest(uuid), ai_api_review_begin(uuid), ai_api_review_record(uuid, jsonb, jsonb),
                        ai_api_commit(uuid);
"""


def _evidence(payload, line):
    item = next((item for item in payload["lines"] if item["line"] == line), None)
    return () if item is None else (f"الصنف: {item['item']}",)


CATALOGUE = Catalogue("STOCK_REVIEW", (
    Check("PRICE_IMPLAUSIBLE", frozenset({"CHECK_DOC"}), frozenset({"unit_cost"}), True, "سعر الوحدة", _evidence),
), "رقم السطر في المستند")


def _load(cursor, user_id: UUID, kind: str, subject_id: UUID, expected_row_version: int | None) -> Snapshot:
    """المحمّل كما تكتبه مساحة عمل: الفحص الحتمي، ثم أقلّ ما يلزم، والبصمة من القاعدة."""
    cursor.execute("SELECT body, status, row_version, ai_api_digest(id) AS digest FROM ai_api_docs WHERE id = %s",
                   (subject_id,))
    row = cursor.fetchone()
    if row is None or row["status"] != "DRAFT":
        raise NotFound
    if expected_row_version is not None and row["row_version"] != expected_row_version:
        raise Conflict
    if not row["body"].strip():
        raise Invalid("EMPTY", field="body")
    lines = [{"line": number, "item": text, "unit_cost": "4.50"}
             for number, text in enumerate(row["body"].split("\n"), 1)]
    return Snapshot({"lines": lines}, bytes(row["digest"]))


def _fixture(cursor, user_id: UUID) -> UUID:
    """موضوعٌ نموذجي بدور المالك، لاختبار المحمّل على ما يحمّله فعلاً."""
    cursor.execute("INSERT INTO ai_api_docs (user_id, body) VALUES (%s, 'شاي\nسكر') RETURNING id", (user_id,))
    return cursor.fetchone()[0]


FEATURE = ReviewFeature(
    code="STOCK_REVIEW", kinds=frozenset({"CHECK_DOC"}), profession=Profession.STOREKEEPER, catalogue=CATALOGUE,
    begin_sql="SELECT request_id, digest FROM ai_api_review_begin(%s)",
    record_sql="SELECT ai_api_review_record(%s, %s, %s) AS outcome",
    digest_sql="SELECT ai_api_digest(%s) AS digest",
    load=_load, payload_keys=frozenset({"lines", "line", "item", "unit_cost"}), fixture=_fixture,
)


def _keys(value, found: set[str]) -> set[str]:
    if isinstance(value, dict):
        for key, inner in value.items():
            found.add(key)
            _keys(inner, found)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            _keys(inner, found)
    return found


def check_loader_keys(db, user_id: UUID, feature: ReviewFeature, subject_id: UUID) -> None:
    """
    ما يحمّله المحمّل فعلاً (المواصفة §6.2): مفاتيحه، على عمقها كلّه، هي المعلَنة بالضبط،
    وليس فيها مفتاح هوية. كل أداة مراجعةٍ تُسجَّل تستدعي هذا على موضوعٍ من `fixture`.
    """
    from eyework.tests.architecture.test_rules import _identity_key

    with db.session(user_id) as cursor:
        snapshot = feature.load(cursor, user_id, sorted(feature.kinds)[0], subject_id, None)
    found = _keys(snapshot.payload, set())
    assert found == set(feature.payload_keys), found ^ set(feature.payload_keys)
    assert not [key for key in found if _identity_key(key)]


# ── التجهيزات ───────────────────────────────────────────────────────────
@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def server(owner, owner_url, writer, gateway):
    """التطبيق نفسه، والبوّابة المصطنعة محقونة مع الكاتب المصطنع."""
    settings = config.Settings(app_database_url=app_url_for(owner_url), login_key=LOGIN_KEY,
                               anthropic_api_key=None, public_origin=ORIGIN)
    database = Database(settings.app_database_url)
    try:
        yield create_app(settings, copywriter=writer, gateway=gateway, database=database)
    finally:
        database.close()


@pytest.fixture
def stand_in(owner, server, monkeypatch):
    """الموضوع البديل في القاعدة، وأداته في السجلّ، ومسار اعتمادٍ يتصرّف كمسار مساحة عمل."""
    with owner.cursor() as cursor:
        cursor.execute(_TRACK_UP)
    monkeypatch.setitem(reviewer.FEATURES, "STOCK_REVIEW", FEATURE)

    def commit(doc_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
        db = request.app.state.db
        try:
            with db.session(user_id) as cursor:
                cursor.execute("SELECT ai_api_commit(%s) AS closed", (doc_id,))
                return {"closed": cursor.fetchone()["closed"]}
        except pg_errors.CheckViolation as exc:
            if exc.diag.constraint_name != "ai_flags_undecided":
                raise
            with db.session(user_id) as cursor:
                cursor.execute("SELECT ai_api_digest(%s) AS digest", (doc_id,))
                digest = bytes(cursor.fetchone()["digest"])
            raise reviewer.flags_undecided(db, user_id, "CHECK_DOC", doc_id, digest) from exc

    # قبل كل المسارات: الملفات الساكنة مثبّتة على "/" آخراً وتلتقط ما يُضاف بعدها.
    server.router.routes.insert(0, APIRoute("/api/test/commit/{doc_id}", commit, methods=["POST"]))
    try:
        yield
    finally:
        with owner.cursor() as cursor:
            cursor.execute(_TRACK_DOWN)


def _accept_terms(owner, user_id: UUID, name: str | None = NAME) -> None:
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = %s, terms_version = %s, terms_accepted_at = now() WHERE id = %s",
                       (name, auth.TERMS_VERSION, user_id))


def _signed_in(owner, browser, username: str = KEEPER, *, profession: str = "STOREKEEPER", terms: bool = True,
               name: str | None = NAME):
    # `terms=False`: حساب دعوةٍ لم يوافق قطّ (add_user يوافق على النسخة الحالية افتراضاً).
    user_id = add_user(owner, username, profession=profession, terms_version=None)
    if terms:
        _accept_terms(owner, user_id, name)
    client = browser()
    assert log_in(client, username).status_code == 204
    return client, user_id


@pytest.fixture
def keeper(owner, browser, stand_in):
    return _signed_in(owner, browser)


def _doc(owner, user_id: UUID, body: str = "شاي\nسكر\nأرز") -> UUID:
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO ai_api_docs (user_id, body) VALUES (%s, %s) RETURNING id", (user_id, body))
        return cursor.fetchone()[0]


def _review(client, doc: UUID, *, feature: str = "STOCK_REVIEW", kind: str = "CHECK_DOC", row_version: int | None = 1):
    body = {"feature": feature, "subject_kind": kind, "subject_id": str(doc)}
    if row_version is not None:
        body["expected_row_version"] = row_version
    return client.post("/api/ai/review", json=body)


def _decide(client, flag_id: str, choice: str, digest: str | None = None):
    """الجسم كما في المواصفة §8.2؛ `digest=None` يُسقط الحقل ليُختبر رفضه."""
    body = {"choice": choice}
    if digest is not None:
        body["digest"] = digest
    return client.post(f"/api/ai/flags/{flag_id}/decision", json=body)


def _commit(client, doc: UUID):
    return client.post(f"/api/test/commit/{doc}", json={})


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _requests(owner, user_id: UUID | None = None) -> list[tuple]:
    """(النتيجة، عدد الملاحظات، نوع الموضوع) لكل صفٍّ في الدفتر بترتيب بدئه."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, flags_count, subject_kind FROM ai_requests"
                       " WHERE %s::uuid IS NULL OR user_id = %s ORDER BY started_at", (user_id, user_id))
        return [tuple(row) for row in cursor.fetchall()]


def _wait_for_outcome(owner, doc: UUID, seconds: float = 5.0) -> str:
    """ينتظر أن تُغلق المراجعة الجارية في الخلفية ويُرجع نتيجتها."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with owner.cursor() as cursor:
            cursor.execute("SELECT outcome FROM ai_requests WHERE subject_id = %s ORDER BY started_at DESC LIMIT 1",
                           (doc,))
            row = cursor.fetchone()
        if row and row[0] is not None:
            return row[0]
        time.sleep(0.05)
    raise AssertionError("المراجعة لم تُغلق في الخلفية")


def _backdate(owner, user_id: UUID, feature: str, rows: int, *, minutes: int, outcome: str = "OK") -> None:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome)"
            " SELECT %s, %s, now() - make_interval(mins => %s), now() - make_interval(mins => %s), %s"
            "   FROM generate_series(1, %s)", (user_id, feature, minutes, minutes, outcome, rows))


# ── DONE ────────────────────────────────────────────────────────────────
def test_a_review_with_flags_addresses_the_user_by_name_from_the_database(keeper, owner, gateway):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    gateway.queue(review_reply(flag(line=2)))
    body = expect(_review(client, doc))

    assert body["review"] == {"status": "DONE", "reason": None, "message": None}
    assert body["subject"] == {"kind": "CHECK_DOC", "id": str(doc), "digest": _digest("شاي\nسكر\nأرز")}
    (shown,) = body["flags"]
    assert shown["headline"] == f"يا {ISOLATE[0]}{NAME}{ISOLATE[1]}، {REASON}"
    assert shown["suggestion"] == SUGGESTION and shown["evidence"] == ["الصنف: سكر"]
    assert (shown["check"], shown["severity"], shown["field"], shown["line"], shown["decision"]) == (
        "PRICE_IMPLAUSIBLE", "HIGH", "unit_cost", 2, None)
    assert body["usage"] == {"per_day": 30, "used_today": 1}
    assert _requests(owner) == [("OK", 1, "CHECK_DOC")]

    # ما غادر: الموضوع في رسالة المستخدم وحدها، وبلا اسمٍ في أيّ موضع.
    (call,) = gateway.calls
    assert "سكر" in call.user and NAME not in call.user
    assert NAME not in json.dumps(call.system, ensure_ascii=False) and NAME not in json.dumps(call.schema)


def test_a_review_with_no_flags_is_done_with_an_empty_list(keeper, owner, gateway):
    client, user_id = keeper
    body = expect(_review(client, _doc(owner, user_id)))
    assert body["review"]["status"] == "DONE" and body["flags"] == [] and body["review"]["message"] is None
    assert _requests(owner) == [("OK", 0, "CHECK_DOC")]


def test_pressing_again_on_unchanged_content_returns_the_stored_flags_without_a_call(keeper, owner, gateway):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    gateway.queue(review_reply(flag(line=1)))
    first = expect(_review(client, doc))
    second = expect(_review(client, doc))
    assert second["review"]["status"] == "DONE" and second["flags"] == first["flags"]
    assert len(gateway.calls) == 1 and _requests(owner) == [("OK", 1, "CHECK_DOC")]


def test_without_a_display_name_the_reason_stands_alone(owner, browser, stand_in, gateway):
    client, user_id = _signed_in(owner, browser, name=None)
    gateway.queue(review_reply(flag(line=1)))
    (shown,) = expect(_review(client, _doc(owner, user_id)))["flags"]
    assert shown["headline"] == REASON


# ── PENDING والنتيجة المتأخّرة والبوّابة ─────────────────────────────
def test_a_late_result_is_stored_and_caught_at_commit_until_the_user_proceeds(keeper, owner, gateway, server):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    server.state.review_runner.wait_seconds = 0.05
    gateway.hold()
    gateway.queue(review_reply(flag(line=3)))

    pending = expect(_review(client, doc))
    assert pending["review"] == {"status": "PENDING", "reason": None, "message": MESSAGES["PENDING"]}
    assert pending["flags"] == [] and _requests(owner) == [(None, None, "CHECK_DOC")]

    gateway.release()
    assert _wait_for_outcome(owner, doc) == "OK"

    blocked = _commit(client, doc)
    assert blocked.status_code == 409
    body = blocked.json()
    assert body["code"] == "FLAGS_UNDECIDED" and body["detail"] == reviewer.FLAGS_UNDECIDED
    (shown,) = body["flags"]
    assert shown["headline"].startswith(f"يا {ISOLATE[0]}{NAME}") and shown["line"] == 3 and shown["decision"] is None

    decided = expect(_decide(client, shown["id"], "PROCEED", _digest("شاي\nسكر\nأرز")))
    assert decided["decision"] == "PROCEED" and decided["flag_id"] == shown["id"]
    assert expect(_commit(client, doc)) == {"closed": 1}

    closed = _decide(client, shown["id"], "EDIT", _digest("شاي\nسكر\nأرز"))
    assert closed.status_code == 409 and closed.json()["code"] == "FLAG_CLOSED"


def test_a_review_still_running_for_the_same_subject_is_pending_and_for_another_is_busy(keeper, owner, gateway):
    client, user_id = keeper
    doc, other = _doc(owner, user_id), _doc(owner, user_id, "ملح")
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO ai_requests (user_id, feature, subject_kind, subject_id, content_digest)"
                       " VALUES (%s, 'STOCK_REVIEW', 'CHECK_DOC', %s, sha256(convert_to('شاي\nسكر\nأرز', 'UTF8')))",
                       (user_id, doc))
    assert expect(_review(client, doc))["review"]["status"] == "PENDING"
    busy = expect(_review(client, other))["review"]
    assert busy == {"status": "UNAVAILABLE", "reason": "BUSY", "message": MESSAGES["BUSY"]}
    assert gateway.calls == []


# ── غير متاح، والعمل يتابع ─────────────────────────────────────────
def test_an_open_breaker_answers_at_once_and_opens_nothing(keeper, owner, gateway, server):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    for _ in range(3):
        server.state.ai_guard.record(model_reply("UPSTREAM_TIMEOUT"))
    body = expect(_review(client, doc))
    assert body["review"] == {"status": "UNAVAILABLE", "reason": "DOWN", "message": MESSAGES["DOWN"]}
    assert _requests(owner) == [] and gateway.calls == []
    assert expect(_commit(client, doc)) == {"closed": 0}


def test_no_free_slot_answers_busy_and_opens_nothing(keeper, owner, gateway, server):
    client, user_id = keeper
    guard: Guard = server.state.ai_guard
    held = 0
    while guard.acquire() is None:
        held += 1
    try:
        body = expect(_review(client, _doc(owner, user_id)))
        assert body["review"]["reason"] == "BUSY" and _requests(owner) == [] and gateway.calls == []
    finally:
        for _ in range(held):
            guard.release()


def test_each_database_cap_is_unavailable_with_its_reason_and_the_commit_passes(keeper, owner, gateway):
    client, user_id = keeper
    _backdate(owner, user_id, "STOCK_REVIEW", 6, minutes=5)
    rate = expect(_review(client, _doc(owner, user_id)))["review"]
    assert rate == {"status": "UNAVAILABLE", "reason": "RATE", "message": MESSAGES["RATE"]}

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    _backdate(owner, user_id, "STOCK_REVIEW", 30, minutes=60)
    doc = _doc(owner, user_id)
    daily = expect(_review(client, doc))["review"]
    assert daily == {"status": "UNAVAILABLE", "reason": "DAILY", "message": MESSAGES["DAILY"]}
    assert expect(_commit(client, doc)) == {"closed": 0}

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM ai_requests")
    other = add_user(owner, OTHER, profession="STOREKEEPER")
    _backdate(owner, other, "STOCK_REVIEW", 600, minutes=60)
    app = expect(_review(client, _doc(owner, user_id)))["review"]
    assert app == {"status": "UNAVAILABLE", "reason": "APP", "message": MESSAGES["APP"]}
    assert gateway.calls == []


@pytest.mark.parametrize(("reply", "reason", "outcome"), [
    pytest.param(model_reply("UPSTREAM_TIMEOUT"), "DOWN", "UPSTREAM_TIMEOUT", id="timeout"),
    pytest.param(model_reply("UPSTREAM_BUSY", retry_after=30), "DOWN", "UPSTREAM_BUSY", id="busy"),
    pytest.param(model_reply("REFUSED", refusal_category="cyber"), "FAILED", "REFUSED", id="refused"),
    pytest.param(model_reply("OUTPUT_INVALID"), "FAILED", "OUTPUT_INVALID", id="invalid"),
])
def test_an_upstream_failure_closes_the_request_and_is_unavailable(keeper, owner, gateway, reply, reason, outcome):
    client, user_id = keeper
    gateway.queue(reply)
    body = expect(_review(client, _doc(owner, user_id)))
    assert body["review"] == {"status": "UNAVAILABLE", "reason": reason, "message": MESSAGES[reason]}
    assert _requests(owner) == [(outcome, None, "CHECK_DOC")]


# ── الفحص الحتمي والإبطال ─────────────────────────────────────────────
def test_invalid_content_is_422_with_its_field_and_neither_a_row_nor_a_call(keeper, owner, gateway):
    client, user_id = keeper
    response = _review(client, _doc(owner, user_id, "   "))
    assert response.status_code == 422
    assert response.json() == {"code": "INVALID", "detail": "في العمل ما يُصلَح قبل المراجعة.", "field": "body"}
    assert _requests(owner) == [] and gateway.calls == []


def test_a_stale_row_version_and_a_foreign_document_are_refused_before_any_call(keeper, owner, browser, gateway):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    stale = _review(client, doc, row_version=2)
    assert stale.status_code == 409 and stale.json()["code"] == "STALE"
    other_client, _ = _signed_in(owner, browser, OTHER)
    assert _review(other_client, doc).status_code == 404
    assert gateway.calls == [] and _requests(owner) == []


def test_content_changed_during_the_review_discards_the_result(keeper, owner, gateway, server):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    server.state.review_runner.wait_seconds = 0.05
    gateway.hold()
    gateway.queue(review_reply(flag(line=1)))
    assert expect(_review(client, doc))["review"]["status"] == "PENDING"
    with owner.cursor() as cursor:
        cursor.execute("UPDATE ai_api_docs SET body = 'شاي مختلف' WHERE id = %s", (doc,))
    gateway.release()
    assert _wait_for_outcome(owner, doc) == "DISCARDED"
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM ai_flags")
        assert cursor.fetchone()[0] == 0
    assert expect(_commit(client, doc)) == {"closed": 0}


# ── القرارات ───────────────────────────────────────────────────────────
def test_edit_proceed_and_undo_follow_their_rules(keeper, owner, browser, gateway):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    gateway.queue(review_reply(flag(line=1)))
    (shown,) = expect(_review(client, doc))["flags"]
    digest = _digest("شاي\nسكر\nأرز")

    first = expect(_decide(client, shown["id"], "EDIT", digest))
    again = expect(_decide(client, shown["id"], "EDIT", digest))
    assert first["decision"] == "EDIT" and again == first          # تكرار القرار القائم لا يُضيف صفّاً
    undo_first = _decide(client, shown["id"], "UNDO", digest)
    assert undo_first.status_code == 409 and undo_first.json()["code"] == "UNDO_INVALID"
    assert expect(_decide(client, shown["id"], "PROCEED", digest))["decision"] == "PROCEED"
    assert expect(_decide(client, shown["id"], "UNDO", digest))["decision"] == "UNDO"
    assert _commit(client, doc).status_code == 409                   # التراجع يحجز الاعتماد من جديد

    stale = _decide(client, shown["id"], "PROCEED", "0" * 64)
    assert stale.status_code == 409 and stale.json() == {"code": "FLAG_STALE", "detail": reviewer.FLAG_STALE}
    other_client, _ = _signed_in(owner, browser, OTHER)
    assert _decide(other_client, shown["id"], "PROCEED", digest).status_code == 404
    assert _decide(client, str(uuid4()), "PROCEED", digest).status_code == 404

    with owner.cursor() as cursor:
        cursor.execute("SELECT choice FROM ai_flag_decisions ORDER BY id")
        assert [row[0] for row in cursor.fetchall()] == ["EDIT", "PROCEED", "UNDO"]
        cursor.execute("UPDATE ai_api_docs SET body = 'شاي\nسكر' WHERE id = %s", (doc,))
    # بصمة الملاحظة نفسها، لكن الموضوع تغيّر بعدها: لا قرار على ما لم يعد يُرى.
    changed = _decide(client, shown["id"], "PROCEED", digest)
    assert changed.status_code == 409 and changed.json()["code"] == "FLAG_STALE"


def test_a_decision_needs_the_digest_and_a_registered_feature(keeper, owner, gateway, monkeypatch):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    gateway.queue(review_reply(flag(line=1)))
    (shown,) = expect(_review(client, doc))["flags"]
    missing = _decide(client, shown["id"], "PROCEED")
    assert missing.status_code == 422 and missing.json()["code"] == "INVALID"
    monkeypatch.delitem(reviewer.FEATURES, "STOCK_REVIEW")
    gone = _decide(client, shown["id"], "PROCEED", _digest("شاي\nسكر\nأرز"))
    assert gone.status_code == 404 and gone.json()["detail"] == reviewer.NO_REVIEW
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM ai_flag_decisions")
        assert cursor.fetchone()[0] == 0


def test_a_reply_the_provider_processed_but_the_record_refused_is_closed_billable(keeper, owner, gateway, monkeypatch):
    """خطأٌ بعد ردٍّ معالَج (قيدٌ في القاعدة أو عطلٌ) يُغلق OUTPUT_INVALID بأرقامه: دُفع ثمنه فيُعدّ."""
    client, user_id = keeper
    doc = _doc(owner, user_id)
    broken = replace(FEATURE, record_sql="SELECT 1 / 0 AS outcome WHERE %s::text <> '' AND %s::text <> ''"
                                         " AND %s::text <> ''")
    monkeypatch.setitem(reviewer.FEATURES, "STOCK_REVIEW", broken)
    gateway.queue(review_reply(flag(line=1)))
    body = expect(_review(client, doc))
    assert (body["review"]["status"], body["review"]["reason"]) == ("UNAVAILABLE", "FAILED")
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, ew_is_billable(outcome), input_tokens FROM ai_requests WHERE subject_id = %s",
                       (doc,))
        outcome, billable, tokens = cursor.fetchone()
    assert (outcome, billable) == ("OUTPUT_INVALID", True) and tokens is not None


def test_the_stand_in_loader_emits_exactly_its_declared_keys(keeper, owner, server):
    _, user_id = keeper
    with owner.cursor() as cursor:
        doc = FEATURE.fixture(cursor, user_id)
    check_loader_keys(server.state.db, user_id, FEATURE, doc)


# ── البوّابات والمدخلات ───────────────────────────────────────────────
def test_the_consent_gate_covers_the_review_and_not_the_decision(owner, browser, stand_in):
    client, user_id = _signed_in(owner, browser, terms=False)
    response = _review(client, _doc(owner, user_id))
    assert response.status_code == 403 and response.json()["code"] == "TERMS"
    assert _decide(client, str(uuid4()), "EDIT", "0" * 64).status_code == 404


def test_another_profession_is_forbidden_and_unknown_features_or_kinds_are_not_found(owner, browser, stand_in):
    marketer, _ = _signed_in(owner, browser, MARKETER, profession="MARKETING")
    forbidden = _review(marketer, uuid4())
    assert forbidden.status_code == 403 and forbidden.json()["code"] == "PROFESSION"
    client, user_id = _signed_in(owner, browser)
    doc = _doc(owner, user_id)
    assert _review(client, doc, feature="SUPPORT_REPLY_REVIEW").status_code == 404
    assert _review(client, doc, kind="RETURN").status_code == 404


def test_the_ai_limiter_allows_twenty_a_minute_per_user(keeper, owner):
    client, user_id = keeper
    doc = _doc(owner, user_id)
    for _ in range(20):
        assert _review(client, doc, feature="NOT_A_FEATURE").status_code == 404
    throttled = _review(client, doc, feature="NOT_A_FEATURE")
    assert throttled.status_code == 429 and throttled.headers["Retry-After"]


def test_nothing_of_the_subject_reaches_the_log(keeper, owner, gateway, caplog, capsys):
    client, user_id = keeper
    caplog.set_level(logging.DEBUG)
    gateway.queue(review_reply(flag(line=1, reason=f"سعر السطر 1 غريبٌ لصنف {CANARY} بعشرة أضعاف."),
                               flag(line=2, reason="يا سارة، سعر السطر 2 غريبٌ بعشرة أضعاف.")))
    body = expect(_review(client, _doc(owner, user_id, f"{CANARY}\nسكر")))
    assert len(body["flags"]) == 1
    assert CANARY not in caplog.text and CANARY not in capsys.readouterr().out
    assert "flags_dropped=1" in caplog.text and "drop_codes=REASON_VOCATIVE" in caplog.text
