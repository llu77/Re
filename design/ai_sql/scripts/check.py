"""Functional checks of NEXT_ai_layer, run as the real roles against the scratch database.

The owner creates users and a stand-in "track" (a subject table and its three wrappers, as the
inventory and support migrations would write them); everything else runs as eyework_app with
eyework.user_id set inside the transaction, exactly as the web layer does.
"""

import hashlib
import json
import os
import sys
import uuid

import psycopg

DB = "ai_spec_check"
OWNER = f"postgresql://eyework_owner:eyework_dev_owner@localhost:5432/{DB}"
APP = f"postgresql://eyework_app:eyework_dev_app@localhost:5432/{DB}"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def constraint_of(fn) -> str | None:
    try:
        fn()
    except psycopg.Error as exc:
        return exc.diag.constraint_name or exc.sqlstate
    return None


owner = psycopg.connect(OWNER, autocommit=True)
app = psycopg.connect(APP, autocommit=True)


def as_user(uid, sql, params=None):
    with app.transaction(), app.cursor() as cur:
        cur.execute("SELECT set_config('eyework.user_id', %s, true)", (str(uid),))
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None


def owner_exec(sql, params=None):
    with owner.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else None


def new_user(profession: str, open_new: bool = False) -> uuid.UUID:
    login = hashlib.sha256(uuid.uuid4().bytes).digest()
    if open_new:
        row = owner_exec(
            "INSERT INTO users (login_hmac, profession, display_name, self_registered, open_registered,"
            " terms_version, terms_accepted_at, birth_date, ui_size)"
            " VALUES (%s, %s, 'سارة', true, true, '2026-10-09', now(), '1990-01-01', 'GAZE') RETURNING id",
            (login, profession))
    else:
        row = owner_exec("INSERT INTO users (login_hmac, profession, display_name) VALUES (%s, %s, 'سارة') RETURNING id",
                         (login, profession))
    return row[0][0]


# ── a stand-in track: one reviewable document kind ──────────────────────
owner_exec("""
CREATE TABLE check_docs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT'
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
""")

USAGE = json.dumps({"input": 2400, "output": 310, "cache_read": 1900, "cache_write": 0,
                    "model": "claude-opus-5-5", "prompt_version": "2026-10-09.1", "api_request_id": "req_011abc"})


def flag(check_code="PRICE_IMPLAUSIBLE", line=3, reason="سعر الوحدة في السطر 3 أعلى بعشرة أضعاف من آخر شراء.",
         suggestion="تأكّد من سعر الوحدة؛ ربما أُدخل سعر الكرتونة.", severity="HIGH", field="unit_cost"):
    return {"check": check_code, "severity": severity, "field": field, "line": line, "reason": reason,
            "suggestion": suggestion, "evidence": ["آخر سعر شراء: ٤٫٥٠ ريال"]}


try:
    keeper = new_user("STOREKEEPER")
    other = new_user("STOREKEEPER")
    marketer = new_user("MARKETING")

    # ── the assistant ledger ──
    req = as_user(keeper, "SELECT ew_assistant_begin()")[0][0]
    check("assistant: a second question while one is open is refused",
          constraint_of(lambda: as_user(keeper, "SELECT ew_assistant_begin()")) == "ai_request_in_progress")
    as_user(keeper, "SELECT ew_assistant_finish(%s, 'OK', %s)", (req, USAGE))
    row = owner_exec("SELECT outcome, input_tokens, cache_read_tokens, served_model, new_account FROM ai_requests WHERE id = %s", (req,))[0]
    check("assistant: finish records outcome and numbers, no content columns exist",
          row == ("OK", 2400, 1900, "claude-opus-5-5", False), str(row))
    cols = {r[0] for r in owner_exec("SELECT column_name FROM information_schema.columns WHERE table_name = 'ai_requests'")}
    check("ledger has no text column that could hold content",
          not (cols & {"question", "answer", "prompt", "text", "content", "body"}), str(sorted(cols)))
    check("assistant: finish with a review outcome is refused",
          constraint_of(lambda: as_user(keeper, "SELECT ew_assistant_finish(%s, 'CANNOT_ANSWER', NULL)", (req,)))
          == "ai_outcome_needs_record")
    check("a settled request cannot be settled again",
          constraint_of(lambda: as_user(keeper, "SELECT ew_ai_request_fail(%s, 'UPSTREAM_ERROR', NULL)", (req,)))
          == "ai_request_not_open")

    # rate: 10 in 10 minutes (one used above)
    for _ in range(9):
        r = as_user(keeper, "SELECT ew_assistant_begin()")[0][0]
        as_user(keeper, "SELECT ew_ai_request_fail(%s, 'UPSTREAM_BUSY', NULL)", (r,))
    check("assistant: the eleventh question in ten minutes is refused (ai_rate)",
          constraint_of(lambda: as_user(keeper, "SELECT ew_assistant_begin()")) == "ai_rate")
    usage = dict((f, (d, u)) for f, d, u in as_user(keeper, "SELECT * FROM ew_ai_my_usage()"))
    check("usage: storekeeper sees ASSISTANT and STOCK_REVIEW only; unbillable failures do not count",
          set(usage) == {"ASSISTANT", "STOCK_REVIEW"} and usage["ASSISTANT"] == (60, 1), str(usage))

    # daily cap via the ledger (owner backdates rows to escape the 10-minute window)
    # the settle-once trigger forbids editing settled rows; the owner lifts it for this backdating only
    owner_exec("ALTER TABLE ai_requests DISABLE TRIGGER trg_ai_request_settle")
    owner_exec("UPDATE ai_requests SET started_at = now() - interval '1 hour' WHERE user_id = %s", (keeper,))
    owner_exec("ALTER TABLE ai_requests ENABLE TRIGGER trg_ai_request_settle")
    owner_exec("""INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome)
                  SELECT %s, 'ASSISTANT', now() - interval '2 hours', now() - interval '2 hours', 'OK'
                    FROM generate_series(1, 59)""", (keeper,))
    check("assistant: the 61st billable question in 24 h is refused (ai_daily_cap)",
          constraint_of(lambda: as_user(keeper, "SELECT ew_assistant_begin()")) == "ai_daily_cap")

    fresh = new_user("SUPPORT", open_new=True)
    owner_exec("""INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome, new_account)
                  SELECT %s, 'ASSISTANT', now() - interval '2 hours', now() - interval '2 hours', 'OK', true
                    FROM generate_series(1, 15)""", (fresh,))
    check("new open account: the 16th question is refused (ai_new_account_daily_cap)",
          constraint_of(lambda: as_user(fresh, "SELECT ew_assistant_begin()")) == "ai_new_account_daily_cap")

    # profession
    doc_m = owner_exec("INSERT INTO check_docs (user_id, body) VALUES (%s, 'x') RETURNING id", (marketer,))[0][0]
    check("a marketing account cannot open a STOCK_REVIEW request (ai_feature_profession)",
          constraint_of(lambda: as_user(marketer, "SELECT * FROM check_review_begin(%s)", (doc_m,)))
          == "ai_feature_profession")

    # ── the reviewer ──
    doc = owner_exec("INSERT INTO check_docs (user_id, body) VALUES (%s, 'v1') RETURNING id", (keeper,))[0][0]
    request, digest = as_user(keeper, "SELECT * FROM check_review_begin(%s)", (doc,))[0]
    outcome = as_user(keeper, "SELECT check_review_record(%s, %s, %s)",
                      (request, json.dumps([flag(), flag("UNIT_MISMATCH", 2, "الوحدة «كيلو» لا تناسب صنفاً يُعدّ بالحبّة.",
                                                         None, "MEDIUM", "unit")]), USAGE))[0][0]
    flags = as_user(keeper, "SELECT id, check_code, severity, line_no, position FROM ai_flags ORDER BY position")
    check("review: two flags written, request OK with flags_count 2",
          outcome == "OK" and len(flags) == 2
          and owner_exec("SELECT outcome, flags_count FROM ai_requests WHERE id = %s", (request,))[0] == ("OK", 2),
          str(flags))
    check("RLS: another user sees none of these flags or requests",
          as_user(other, "SELECT count(*) FROM ai_flags")[0][0] == 0
          and as_user(other, "SELECT count(*) FROM ai_requests")[0][0] == 0)
    check("the same content is not reviewed twice (ai_review_current)",
          constraint_of(lambda: as_user(keeper, "SELECT * FROM check_review_begin(%s)", (doc,))) == "ai_review_current")

    # the gate
    check("gate: undecided flags block the commit (ai_flags_undecided)",
          constraint_of(lambda: as_user(keeper, "SELECT check_commit(%s)", (doc,))) == "ai_flags_undecided")
    f1, f2 = flags[0][0], flags[1][0]
    check("UNDO before PROCEED is refused (ai_decision_undo)",
          constraint_of(lambda: as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'UNDO')", (f1,))) == "ai_decision_undo")
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (f1,))
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (f1,))
    check("repeating the standing decision adds no row",
          owner_exec("SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (f1,))[0][0] == 1)
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (f1,))
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (f2,))
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'UNDO')", (f2,))
    check("gate: an undone PROCEED blocks again",
          constraint_of(lambda: as_user(keeper, "SELECT check_commit(%s)", (doc,))) == "ai_flags_undecided")
    check("another user cannot decide on these flags (not found)",
          constraint_of(lambda: as_user(other, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (f1,))) == "P0002")
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (f2,))
    closed = as_user(keeper, "SELECT check_commit(%s)", (doc,))[0][0]
    check("gate: all PROCEED -> commit passes and closes both flags", closed == 2)
    check("a closed flag takes no decision (ai_flag_closed)",
          constraint_of(lambda: as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (f1,))) == "ai_flag_closed")
    trail = owner_exec("SELECT choice FROM ai_flag_decisions WHERE flag_id = %s ORDER BY id", (f2,))
    check("audit trail is append-only and complete", [t[0] for t in trail] == ["PROCEED", "UNDO", "PROCEED"], str(trail))
    check("decisions cannot be updated, even by the owner",
          constraint_of(lambda: owner_exec("UPDATE ai_flag_decisions SET choice = 'EDIT' WHERE flag_id = %s", (f2,)))
          == "42501")
    check("flag texts cannot be rewritten (ai_flag_immutable)",
          constraint_of(lambda: owner_exec("UPDATE ai_flags SET reason = 'سببٌ آخر مختلف تماماً هنا.' WHERE id = %s", (f1,)))
          == "ai_flag_immutable")

    # changed while reviewing -> DISCARDED
    doc2 = owner_exec("INSERT INTO check_docs (user_id, body) VALUES (%s, 'a') RETURNING id", (keeper,))[0][0]
    r2, _ = as_user(keeper, "SELECT * FROM check_review_begin(%s)", (doc2,))[0]
    as_user(keeper, "SELECT check_edit(%s, 'b')", (doc2,))
    out2 = as_user(keeper, "SELECT check_review_record(%s, %s, %s)", (r2, json.dumps([flag()]), USAGE))[0][0]
    check("content changed during the review -> DISCARDED, no flag written",
          out2 == "DISCARDED" and as_user(keeper, "SELECT count(*) FROM ai_flags WHERE subject_id = %s", (doc2,))[0][0] == 0)
    check("gate passes on content with no flags (the AI never blocks by being absent)",
          as_user(keeper, "SELECT check_commit(%s)", (doc2,))[0][0] == 0)

    # shape and text checks
    doc3 = owner_exec("INSERT INTO check_docs (user_id, body) VALUES (%s, 'c') RETURNING id", (keeper,))[0][0]
    r3, _ = as_user(keeper, "SELECT * FROM check_review_begin(%s)", (doc3,))[0]
    check("a reason carrying a link is refused by the table (ai_flag_texts)",
          constraint_of(lambda: as_user(keeper, "SELECT check_review_record(%s, %s, %s)",
                                        (r3, json.dumps([flag(reason="راجع https://example.com قبل التسجيل الآن.")]), USAGE)))
          == "ai_flag_texts")
    check("four flags are refused (ai_flags_shape)",
          constraint_of(lambda: as_user(keeper, "SELECT check_review_record(%s, %s, %s)",
                                        (r3, json.dumps([flag(line=i) for i in (1, 2, 3, 4)]), USAGE)))
          == "ai_flags_shape")
    check("an extra key in a flag is refused (ai_flags_shape)",
          constraint_of(lambda: as_user(keeper, "SELECT check_review_record(%s, %s, %s)",
                                        (r3, json.dumps([{**flag(), "name": "سارة"}]), USAGE)))
          == "ai_flags_shape")
    # lease
    owner_exec("UPDATE ai_requests SET started_at = now() - interval '2 minutes' WHERE id = %s", (r3,))
    check("a successful result after the lease is refused (ai_request_not_open)",
          constraint_of(lambda: as_user(keeper, "SELECT check_review_record(%s, %s, %s)", (r3, json.dumps([flag()]), USAGE)))
          == "ai_request_not_open")
    as_user(keeper, "SELECT ew_ai_request_fail(%s, 'UPSTREAM_TIMEOUT', NULL)", (r3,))
    check("a failure after the lease is still recorded",
          owner_exec("SELECT outcome FROM ai_requests WHERE id = %s", (r3,))[0][0] == "UPSTREAM_TIMEOUT")

    # erase and forget
    doc4 = owner_exec("INSERT INTO check_docs (user_id, body) VALUES (%s, 'd') RETURNING id", (keeper,))[0][0]
    r4, _ = as_user(keeper, "SELECT * FROM check_review_begin(%s)", (doc4,))[0]
    as_user(keeper, "SELECT check_review_record(%s, %s, %s)", (r4, json.dumps([flag()]), USAGE))
    f4 = as_user(keeper, "SELECT id FROM ai_flags WHERE subject_id = %s", (doc4,))[0][0]
    as_user(keeper, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (f4,))
    as_user(keeper, "SELECT check_erase(%s)", (doc4,))
    erased = owner_exec("SELECT reason, suggestion, evidence, check_code, erased_at IS NOT NULL FROM ai_flags WHERE id = %s", (f4,))[0]
    check("erase: texts gone, code and decisions kept",
          erased[:3] == (None, None, []) and erased[3] == "PRICE_IMPLAUSIBLE" and erased[4]
          and owner_exec("SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (f4,))[0][0] == 1, str(erased))
    owner_exec("DELETE FROM check_docs WHERE id = %s", (doc4,))
    check("forget: deleting the subject deletes its flags and their decisions",
          owner_exec("SELECT count(*) FROM ai_flags WHERE id = %s", (f4,))[0][0] == 0
          and owner_exec("SELECT count(*) FROM ai_flag_decisions WHERE flag_id = %s", (f4,))[0][0] == 0)

    # web role cannot write tables or call internals
    for sql, label in (("INSERT INTO ai_requests (user_id, feature) VALUES (%s, 'ASSISTANT')", "insert ai_requests"),
                       ("UPDATE ai_flags SET closed_at = now() WHERE user_id = %s", "update ai_flags"),
                       ("DELETE FROM ai_flag_decisions WHERE user_id = %s", "delete ai_flag_decisions")):
        check(f"web role: {label} is denied", constraint_of(lambda: as_user(keeper, sql, (keeper,))) == "42501")
    for sql in ("SELECT ew_ai_request_open('ASSISTANT', NULL, NULL, NULL)",
                "SELECT ew_ai_gate('CHECK_DOC', gen_random_uuid(), sha256('x'))",
                "SELECT ew_ai_flags_put(gen_random_uuid(), NULL, '[]', NULL)",
                "SELECT ew_ai_spend(false)"):
        check(f"web role cannot call {sql.split('(')[0][7:]}", constraint_of(lambda: as_user(keeper, sql)) == "42501")
    check("web role cannot read ai_features directly",
          constraint_of(lambda: as_user(keeper, "SELECT count(*) FROM ai_features")) == "42501")

    # spend: one function counts all three ledgers
    before = owner_exec("SELECT ew_ai_spend(false)")[0][0]
    owner_exec("INSERT INTO attempt_tombstones (started_at, outcome, new_account) VALUES (now(), 'OK', true)")
    after = owner_exec("SELECT ew_ai_spend(false), ew_ai_spend(true)")[0]
    check("ew_ai_spend counts tombstones and the new-account share", after[0] == before + 1 and after[1] >= 16, str(after))
    # global cap reached -> both the assistant and campaign generation refuse
    owner_exec("""INSERT INTO attempt_tombstones (started_at, outcome)
                  SELECT now(), 'OK' FROM generate_series(1, greatest(0, 2000 - ew_ai_spend(false)::int))""")
    check("global cap counts ai_requests + campaigns + tombstones (generation_global_cap)",
          constraint_of(lambda: as_user(other, "SELECT ew_assistant_begin()")) == "generation_global_cap")
    owner_exec("DELETE FROM attempt_tombstones")

    body = owner_exec("SELECT prosrc FROM pg_proc WHERE proname = 'ew_begin_generation'")[0][0]
    check("campaign generation counts the shared spend (ew_begin_generation calls ew_ai_spend)",
          "ew_ai_spend(false) >= 2000" in body and "fresh AND ew_ai_spend(true) >= 400" in body)

    # deleting an account leaves tombstones for the last 24 h of billable requests
    billable = owner_exec("SELECT count(*) FROM ai_requests WHERE user_id = %s AND ew_is_billable(outcome)"
                          " AND started_at > now() - interval '24 hours'", (keeper,))[0][0]
    owner_exec("DELETE FROM users WHERE id = %s", (keeper,))
    stones = owner_exec("SELECT count(*) FROM attempt_tombstones")[0][0]
    check("account deletion leaves one tombstone per billable request of the last 24 h",
          stones == billable and billable > 0, f"{stones} vs {billable}")
    check("account deletion removes its flags and decisions",
          owner_exec("SELECT count(*) FROM ai_flags WHERE user_id = %s", (keeper,))[0][0] == 0)
finally:
    owner_exec("DROP TABLE IF EXISTS check_docs CASCADE")
    owner_exec("DROP FUNCTION IF EXISTS check_digest(uuid), check_review_begin(uuid), check_review_record(uuid, jsonb, jsonb),"
               " check_commit(uuid), check_edit(uuid, text), check_erase(uuid)")

passed = sum(ok for _, ok, _ in results)
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
print(f"{passed} of {len(results)} checks pass")
sys.exit(0 if passed == len(results) else 1)
