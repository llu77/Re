
---

## 7. Database: `NEXT_ai_layer`

The integrator numbers the migration. It goes **after `NEXT_open_registration`**, because it needs `ew_new_open_account` and `attempt_tombstones.new_account`, and **before the inventory, support and marketing migrations**, which call it. The files are `ai_sql/NEXT_ai_layer.up.sql` and `.down.sql`. Both are assembled by `ai_sql/scripts/build.py`, which takes `ew_begin_generation` from the registration migration verbatim and changes only its two cap conditions.

### 7.1 Design notes

**Tables:**

- **`ai_features`**: one row per model-calling feature, holding its profession, its caps and its lease. It is RLS-forced with an owner policy only, and the web role has no grant; users read their numbers through `ew_ai_my_usage()`.
  - It carries this spec's assistant row, and the inventory and support rows as proposed in their drafts, so one table shows every cap.
  - A workspace that renames or drops a feature edits its row in its own migration.
- **`ai_requests`**: the shared ledger, one row per model call outside campaigns.
  - It holds the feature; the subject's kind, id and content digest; the timestamps and the outcome; the tokens (including cache reads and writes); the served model, prompt version and Anthropic request id; `new_account`; and `flags_count`.
  - **There is no content column** (checked).
  - There is no foreign key to subjects, on purpose: a row must outlive its subject for 24 hours to count toward the caps.
  - It has the settle-once trigger (main's `ew_attempt_settle_once`) and a tombstone trigger, so deleting an account frees no room.
- **`ai_flags`**: AI flags only. Each workspace's deterministic warnings stay in its own tables.
  - It holds the subject and digest, `position`, `check_code`, `severity`, `field`, `line_no`, `reason`, `suggestion`, server-built `evidence`, `closed_at` and `erased_at`.
  - The texts must pass `ew_ai_text_ok` while not erased, and are all `NULL` once erased.
  - One flag per (subject, digest, check, line).
  - A guard trigger allows only:
    - closing once;
    - erasing once;
    - unlinking from a purged ledger row (the foreign key's `SET NULL (request_id)`).
- **`ai_flag_decisions`**: an append-only audit of `EDIT`, `PROCEED` and `UNDO`. `ew_forbid_update` refuses updates, even by the owner.

**Functions the web role may call:**

| Function | What it does |
|---|---|
| `ew_ai_decide(flag, choice)` | Records a decision on the session user's own flag. |
| `ew_ai_request_fail(request, outcome, usage)` | Closes the session user's own open request with a failure outcome only. |
| `ew_ai_my_usage()` | The session user's caps and today's use, for the features of their profession. |
| `ew_assistant_begin()`, `ew_assistant_finish(request, outcome, usage)` | Open and close an assistant request; the ledger only, with no content. |

**Internal functions,** callable only by the owner's `SECURITY DEFINER` functions (`REVOKE … FROM PUBLIC`; checked):

| Function | What it does |
|---|---|
| `ew_ai_spend(new_only)` | The only function that sums the ledgers. `ew_begin_generation` and `ew_ai_request_open` both use it. |
| `ew_ai_request_open(feature, kind, id, digest)` | Applies every cap in main's order: the user lock, profession, already-reviewed, in flight, rate, daily (new-account variant), then under the global lock the app-wide feature cap, the global cap and the new-accounts pool. Then it inserts. |
| `ew_ai_request_settle` | Closes a request. A success outcome is refused after the lease. |
| `ew_ai_flags_put` | Writes flags for a request under a per-subject advisory lock, or records `DISCARDED` if the digest moved. |
| `ew_ai_gate(kind, id, digest)` | Under the same lock and with the flags locked `FOR UPDATE`: refuses undecided flags, otherwise closes them. |
| `ew_ai_forget_subject()` | Trigger function: deletes a deleted subject's flags. |
| `ew_ai_erase_subject(kind, id)` | Blanks a subject's flag texts. |

**Locking.**

- Opening a request takes the user's row lock, then the global advisory lock, as `ew_begin_generation` does.
- Flags and the gate take a per-subject advisory lock.
- A decision locks its flag row. The gate locks the flag rows, so an `UNDO` racing a commit is serialized. Lock order cannot cycle: a decision never takes the subject lock.

**Down.**

1. Drops decisions and flags.
2. Deletes the ledger rows. The tombstone trigger turns the last 24 hours of billable calls into tombstones, so a rollback does not empty the cap.
3. Restores the registration body of `ew_begin_generation` byte for byte.
4. Drops the rest.
- **What the down fails on:** any workspace migration whose triggers use `ew_ai_forget_subject`, so it must go down first. It fails loudly, not silently.

### 7.2 Verified

These ran on PostgreSQL 16, in the scratch database `ai_spec_check`, with the repo's runner on copies of main's 0001–0006 plus `NEXT_open_registration` as 0007 and this migration as 0008.

- **The cycle** (`evidence/cycle.txt`):
  - down to 0007 restores 0007: **identical**;
  - up again matches the first up: **identical**;
  - from empty matches the first up: **identical**.
- **45 of 45 functional checks** (`evidence/check.txt`), as `eyework_app` with `eyework.user_id` set per transaction, against a stand-in track (`check_docs` with the three wrappers and the forget trigger). They cover:
  - every cap and its constraint name;
  - profession and RLS isolation; the web role denied every direct write and every internal function;
  - the review flow, the gate, UNDO, idempotent decisions, the append-only audit, flag immutability, `DISCARDED` on changed content;
  - link-bearing reasons, a fourth flag and an extra key (`"name"`) all refused;
  - the lease;
  - erase and forget;
  - tombstones on account deletion;
  - the global cap shared with campaigns;
  - `ew_begin_generation` calling `ew_ai_spend`.
- **The registration track's own checks**, rerun on top: 28 of 29 pass. The 29th drives an older runner that does not know 0008. With our runner the same down refusal holds, and after removing the open account, down and up work (`evidence/down_refusal_with_0008.txt`).
- **The workspace drafts on top** (`evidence/track_drafts_on_ai_layer.txt`): the support draft fails; the inventory draft applies but leaves `ew_begin_generation` without `ew_ai_spend` (`f`). Hence §7.4.

### 7.3 The integration contract for every reviewed or drafted subject

A workspace writes these. The shapes are the stand-in track's, which pass the checks above.

```sql
-- 1. begin: lock, check the reviewable state, digest, open. Granted to eyework_app.
CREATE FUNCTION ew_<ws>_review_begin(p_id uuid) RETURNS TABLE (request_id uuid, content_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE d bytea;
BEGIN
    PERFORM 1 FROM <subject> WHERE id = p_id AND user_id = ew_current_user() AND <reviewable> FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION '<subject>' USING ERRCODE = 'no_data_found'; END IF;
    d := ew_<ws>_digest(p_id);           -- covers every user-editable field that is sent
    RETURN QUERY SELECT ew_ai_request_open('<FEATURE>', '<KIND>', p_id, d), d;
END $$;

-- 2. record: lock, digest now (NULL once no longer reviewable), write or discard. Granted.
CREATE FUNCTION ew_<ws>_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r ai_requests%ROWTYPE; d bytea;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = ew_current_user();
    SELECT ew_<ws>_digest(s.id) INTO d FROM <subject> s WHERE s.id = r.subject_id AND <reviewable> FOR UPDATE;
    RETURN ew_ai_flags_put(p_request, d, p_flags, p_usage);
END $$;

-- 3. in the existing commit function, after it locks the subject:
    PERFORM ew_ai_gate('<KIND>', p_id, ew_<ws>_digest(p_id));

-- 4. per subject table:
CREATE TRIGGER trg_<subject>_forget_ai AFTER DELETE ON <subject>
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('<KIND>');

-- 5. where the workspace blanks the subject's texts (e.g. customer messages after closure):
    PERFORM ew_ai_erase_subject('<KIND>', <id>);
```

- **Drafting features** (`SUPPORT_DRAFT`, `SUPPORT_ARTICLE_PROPOSAL`) open with `ew_ai_request_open('<FEATURE>', 'TICKET', ticket_id, NULL)`. A `NULL` digest skips the already-reviewed rule.
- **Recording a draft.** The workspace's record function writes the draft and calls `ew_ai_request_settle(request, 'OK'|'CANNOT_ANSWER'|'NOT_SUPPORT', NULL, usage)` in the same transaction, so a success outcome never exists without its draft.
- **Failures** use `ew_ai_request_fail`.
- **Feature rows.** The workspace adds or edits its `ai_features` row in its own migration.

### 7.4 Rebasing the drafts (for the integrator and the two workspace tracks)

| Draft object | Becomes |
|---|---|
| `inv_review_calls`, `support_ai_calls`, `support_ai_limits` and their tombstone triggers | `ai_requests` and `ai_features` rows (here) |
| `ew_inv_ai_spend`, support's `ew_ai_spend` | `ew_ai_spend` (here, once) |
| The `ew_begin_generation` replacements in both drafts | Removed; this migration's replacement stands |
| `ew_inv_review_begin`, `ew_support_ai_open` + `ew_support_begin_review` | The begin wrapper (§7.3) |
| `ew_inv_review_record`, `ew_support_record_review` | The record wrapper. The code whitelists move to the Python catalogue (§3.9); the database keeps the shape and text checks. |
| `ew_inv_review_finish`, `ew_support_finish_call` | `ew_ai_request_fail`, plus the workspace's own state updates in the same transaction |
| `inv_review_flags` rows with `source = 'AI'`, and `support_flags` AI codes | `ai_flags`. Both tables keep `RULE` rows only. |
| Inventory's `ew_inv_flag_keys` `'AI:'` branch | Removed. `ew_inv_post_purchase` and `ew_inv_post_return` call `ew_ai_gate` after `ew_inv_check_ack`. |
| Support's `ew_support_ack_flag` for AI flags; `HEEDED` / `DISMISSED` | `ew_ai_decide`: `EDIT` / `PROCEED`. The owner asked for two choices; `dismiss_reason` has no place in the shared decision. Support may keep it for its RULE flags only if its spec justifies it. |
| `support_drafts.call_id`, `kb_versions.call_id` | `REFERENCES ai_requests (id) ON DELETE SET NULL` |
| `support_replies.review` state | Derived from the reply's latest `ai_requests` row, or kept as denormalized state that the record and fail wrappers update in the same transaction |
| `inv_settings.review_enabled` and `review_notice_*`; `support_settings.notice_version` and `notice_accepted_at` | Removed: a setting and a step the owner did not ask for. The sign-up notice and `require_current_terms` cover consent (§6.4). |
| `work_sql/…/0008_work_tools` (`ai_calls`, `assistant_exchanges`, `assistant_ready_answers`, `feature_notices`) | Not carried forward (§1.3) |

### 7.5 `purge` additions (`admin.py`)

```python
#: استدعاءٌ بقي مفتوحاً ساعةً انقطعت عمليّته: يُغلق محسوباً، فلا يحجز مقعد صاحبه ولا يبقى مبهماً.
_PURGE_AI_ABANDONED = """
UPDATE ai_requests SET finished_at = now(), outcome = 'ABANDONED'
 WHERE finished_at IS NULL AND started_at < now() - interval '1 hour'
"""
#: الدفتر بلا محتوى، وسقوفه ليومٍ واحد؛ ثلاثون يوماً لمراجعة الكلفة ثم يُحذف.
_PURGE_AI_REQUESTS = "DELETE FROM ai_requests WHERE started_at < now() - interval '30 days'"
#: تنبيهٌ لم يُعتمد عمله في ثلاثين يوماً لا قرار ينتظره.
_PURGE_AI_OPEN_FLAGS = "DELETE FROM ai_flags WHERE closed_at IS NULL AND created_at < now() - interval '30 days'"
```

These run in that order inside the existing `purge()`, and their counts are printed with the others. No text is printed. Checked on a crafted state (`evidence/purge_check.txt`): the abandoned request is closed; the 40-day-old ledger row is deleted with no tombstone; its closed flag is kept, unlinked, with its decision; the open 40-day-old flag is deleted with its decision.

### 7.6 `NEXT_ai_layer.up.sql` (exact, as verified)

```sql
{{UP_SQL}}
```

### 7.7 `NEXT_ai_layer.down.sql` (exact, as verified)

```sql
{{DOWN_SQL}}
```

---

## 8. Server

### 8.1 Modules

| Module | Pure? | What it holds |
|---|---|---|
| `model_gateway.py` | no (the only `anthropic` importer) | `ModelCall`, `ModelReply`, `Gateway`, `AnthropicGateway`; the helpers moved from `copywriter.py`; the breaker; `_AI_SLOTS` |
| `copywriter.py` | no | Unchanged behaviour. It imports `new_client`, `Timeout`, `APIError`, `_BUSY`, `_UNBILLED`, `_retry_after`, `_tokens` and `failure_outcome` from the gateway instead of `anthropic`, and keeps its own loop and `CopyOutcome`. |
| `ai_limits.py` | yes | `FEATURES` (the mirror of `ai_features`), `REVIEW_WAIT_SECONDS = 12.0`, deadlines, efforts, `max_tokens`, prompt versions |
| `ai_text.py` | yes | `check(text, min, max, *, lines=1) -> (normalized or None, codes)`, reusing `copy_rules`' private patterns through a small public wrapper |
| `redact.py` | yes | `redact()` (§6.3) |
| `prompt_kit.py` | yes | `data()` (moved from `prompt.py`, which then imports it), `system_blocks()` |
| `grounding.py` | yes | `kb_norm`, `package()`, `verify()` |
| `reviewer_prompt.py` | yes | `REVIEWER_SYSTEM`, `Check`, `Catalogue`, `render_checks`, `schema(catalogue)`, `call(catalogue, kind, payload) -> ModelCall` |
| `reviewer.py` | no (DB + gateway) | `ReviewFeature` registry, `ReviewRunner` (pool, wait, breaker), `parse_flags`, `headline`, `review()`, `decide()`, `undecided_flags()` |
| `assistant_prompt.py` | yes | `ASSISTANT_SYSTEM`, `profession_block()`, `schema(profession)`, `call(...) -> ModelCall` |
| `assistant.py` | no | `ScreenContext` registry, `ask()` |
| `ai_log.py` | yes (stdlib `logging` only) | `event(...)` (§6.6) |
| `web/routes_ai.py` | — | the routes in §8.2 |

- **The architecture test's `DATABASE_ALLOWED`** gains `reviewer.py` and `assistant.py`.
- **`PURE`** gains `ai_limits.py`, `ai_text.py`, `redact.py`, `prompt_kit.py`, `grounding.py`, `reviewer_prompt.py`, `assistant_prompt.py` and `ai_log.py`.
- **Injection, like main's `copywriter`.**
  - `create_app(copywriter=None, gateway=None)` takes an injected gateway. Without one it builds `AnthropicGateway(settings.anthropic_api_key)`; without a key it refuses to start, as today.
  - Tests inject `tests/fakes.FakeGateway`, which takes scripted `ModelReply` objects or raw JSON, optional delays on the injected clock, and records every `ModelCall`.
- **`ReviewRunner`** owns a `ThreadPoolExecutor(max_workers=8, thread_name_prefix="ai-review")` created in the app's lifespan and shut down with `cancel_futures=True`. Requests left open by the shutdown are closed `ABANDONED` by `purge`.
  - The background job uses `db.session(user_id)` with the user id captured from the authenticated request. It never takes an id from the model or the payload.

### 8.2 API

All bodies are Pydantic models with `extra="forbid"`. All routes take the session user (`require_user`) and the existing Origin check. Model-calling routes also depend on `require_current_terms`.

**`POST /api/ai/review`.** Consent gate: yes. Limiter: `limiters.ai`, 20 a minute per user, in memory.

```json
// request
{"feature": "STOCK_REVIEW", "subject_kind": "PURCHASE", "subject_id": "…uuid…", "expected_row_version": 7}
// 200
{"subject": {"kind": "PURCHASE", "id": "…", "digest": "…64 hex…"},
 "review": {"status": "DONE" | "PENDING" | "UNAVAILABLE",
            "reason": null | "DOWN" | "BUSY" | "RATE" | "DAILY" | "APP" | "FAILED",
            "message": null | "<Arabic status line, §3.11>"},
 "flags": [{"id": "…", "check": "PRICE_IMPLAUSIBLE", "severity": "HIGH", "field": "unit_cost", "line": 3,
            "headline": "يا ⁨سارة⁩، سعر الوحدة …", "suggestion": "إن كان السعر للكرتونة …",
            "evidence": ["آخر سعر شراءٍ للصنف: 4.50 ريال (7 مشتريات)"], "decision": null}],
 "usage": {"per_day": 30, "used_today": 4}}
```

- **Errors:**
  - 404 `NOT_FOUND`: the subject is not the user's;
  - 409 `STALE`: the row version;
  - 422 `INVALID` with `field`: the workspace's deterministic validation, so no model call;
  - 403 `PROFESSION`; 403 `TERMS`.
- **The review status is never an error code.** Caps, an open breaker, no slot and upstream failures all return 200 `UNAVAILABLE`.
- **A workspace may call `reviewer.review(...)` from its own route,** for example to save the draft and return its RULE flags in the same round trip. The `review`, `flags` and `usage` parts of the response keep this exact shape.

**`POST /api/ai/flags/{flag_id}/decision`.** Consent gate: no, because nothing is sent. Limiter: `limiters.mutation`.

```json
{"choice": "EDIT" | "PROCEED" | "UNDO", "digest": "…64 hex…"}
// 200
{"flag_id": "…", "decision": "PROCEED", "decided_at": "2026-10-09T08:12:03Z"}
```

| Error | Copy (Arabic) |
|---|---|
| 404 | — |
| 409 `FLAG_STALE` | «تغيّر العمل بعد هذه الملاحظة. راجعه من جديد.» |
| 409 `FLAG_CLOSED` | «اعتُمد العمل، ولم يعد لهذه الملاحظة قرار.» |
| 409 `UNDO_INVALID` | — |
| 429 `DECISION_CAP` | — |

**Workspace commit routes** map `ai_flags_undecided` to **409 `FLAGS_UNDECIDED`**, with `{"flags": [...]}` built by `reviewer.undecided_flags(...)` in the shape above.

**`POST /api/ai/assistant`.** Consent gate: yes. Limiter: `limiters.ai`.

```json
// request
{"screen": {"kind": "PURCHASE_DRAFT", "id": "…"}, "question": "ماذا أتحقّق منه قبل تسجيل الفاتورة؟"}
// or
{"screen": {"kind": "HOME"}, "ready": 0}
// 200
{"status": "ANSWER" | "DONT_KNOW" | "OUT_OF_SCOPE",
 "text": "<the validated answer, or the fixed text for the two other statuses>",
 "question_sent": "<after masking>",
 "sources": [{"line": "المصدر: O*NET® OnLine 43-5071.00، …", "href": "#/account/sources"}],
 "usage": {"per_day": 60, "used_today": 12}}
```

Errors are in §4.6. An unknown screen kind, or one outside the user's profession, is 404 `SCREEN`.

**`GET /api/me`** gains `"ai": [{"feature", "per_day", "used_today"}]` from `ew_ai_my_usage()`.

**`GET /api/choices`** gains `"assistant": {"question_max": 300, "ready": {"<kind>": ["…", "…"]}}`.

**Constraint mapping** (`web/errors.py`):

| Constraint | Review route | Assistant / draft routes |
|---|---|---|
| `ai_feature_profession` | 403 `PROFESSION` | 403 `PROFESSION` |
| `ai_review_current` | 200 `DONE` with stored flags | — |
| `ai_request_in_progress` | 200 `PENDING` (same subject) / `UNAVAILABLE BUSY` | 409 `AI_BUSY` |
| `ai_rate` | `UNAVAILABLE RATE` | 429 `AI_RATE` |
| `ai_daily_cap` / `ai_new_account_daily_cap` | `UNAVAILABLE DAILY` | 429 `AI_DAILY` / `AI_NEW_DAILY` |
| `ai_feature_app_cap`, `generation_global_cap`, `generation_new_accounts_cap` | `UNAVAILABLE APP` | 503 `AI_APP_BUSY` |
| `ai_flags_undecided` | — | (commit routes) 409 `FLAGS_UNDECIDED` |
| `ai_flag_closed` / `ai_decision_undo` / `ai_decision_cap` / `ai_decision_choice` | decision route: 409 / 409 / 429 / 422 | — |
| `ai_request_not_open`, `ai_flags_shape`, `ai_usage_shape`, `ai_flag_texts`, `ai_flag_immutable`, `ai_outcome_needs_record` | 500, logged critical (a server bug) | same |

### 8.3 The registries the workspaces fill

- `reviewer.FEATURES: dict[str, ReviewFeature]`, where each entry holds:
  - the code and subject kinds;
  - the profession;
  - the `Catalogue`;
  - the SQL to begin and record (§7.3), and the digest SQL;
  - `load(cursor, user_id, kind, id, expected_row_version) -> Snapshot`. It does the deterministic validation (raising `Invalid(field)`, `Conflict` or `NotFound`), takes the row lock, and returns the minimal payload and the digest in the same transaction as the begin.
- `assistant.SCREENS: dict[str, ScreenContext]` (§4.2).

A unit test runs every registered loader on a fixture and checks its keys against the deny list (§6.2).

---

## 9. Client contract (for the visual track)

- **`AIFlag`:**
  - Props are `headline`, `suggestion`, `evidence`, `severity`, `decision`, `onEdit`, `onProceed` and `onUndo`.
  - The component renders `headline` as given. Remove `addressed()` from it and from `AssistantTool`.
  - The second line is «اقتراحي: {suggestion}», shown only when present. The visual draft's «السبب:» line goes: the reason is the headline.
  - The severity badge is «مهمّ» for `HIGH` and «للتحقّق» for `MEDIUM`. The header is «ملاحظة من سيمبول».
  - After PROCEED: «حُفظ قرار المتابعة رغم الملاحظة.» and «تراجع», in the same rects.
- **`ReviewLine`:** a fixed two-line slot on the confirmation step, showing the server's `review.message`, or «لم يجد سيمبول ما يستوقفه.» when `DONE` with no flags. It is plain text, not a control.
- **The «راجع» button:**
  - busy label «يراجع سيمبول…», with a fixed min-width;
  - no timer, no polling, no streaming;
  - one request, then render the final state.
- **«قبل المتابعة»:** the step opened by a 409 `FLAGS_UNDECIDED` on commit, with the intro «وصلت ملاحظةٌ من سيمبول بعد مراجعته. القرار لك.» and the same `AIFlag`.
- **`AssistantTool`:**
  - the copy in §4.6;
  - up to three ready-question buttons, which send on one press and are `data-commit` because they spend a question;
  - the counter «{n} من 300» (the visual draft's 500 becomes 300);
  - «سؤالك: {question_sent}»;
  - the source line with the «المصادر» link when present;
  - no answer streaming.
- **Fit to measure** at both sizes in the four handheld frames:
  - `AIFlag` with a 30-letter Arabic name, a 30-letter Latin name, a 160-character reason, a 140-character suggestion and 3 evidence lines;
  - the assistant answer at 320 characters over 6 lines, with the source line.

  Anything that does not fit at the gaze size in 320×635 takes the one-flag-per-screen layout (already drawn) or moves the evidence behind «التفاصيل». It is never clipped or scrolled.

---

## 10. Tests

### 10.1 Unit (no database, no network)

- **`test_model_gateway.py`:**
  - The request body is golden-tested: model, `betas`, `fallbacks:"default"`, effort explicit; **no** `thinking`, `budget_tokens`, `tools`, `tool_choice` or sampling keys; `max_retries=0`; the base URL fixed; the per-feature timeout.
  - The reply order: refusal (with and without `recommended_model`), then `max_tokens`, then non-JSON, then a non-object.
  - Error mapping for 400 (spend limit), 401, 429, 500, 503, 504, 529, a connection error and a timeout, with billability.
  - Tokens summed across `usage.iterations` after a fallback.
  - The streaming deadline, with a fake stream and the injected clock.
- **`test_reviewer_prompt.py`:**
  - The system blocks are static, with `cache_control` on the last only.
  - The payload appears only in the user message.
  - `data()` neutralises `</subject>`.
  - Every catalogue's schema passes the structured-output limits checker: no optional properties, ≤ 16 unions, only allowed keywords.
  - The canary appears only in the user message (§6.2).
- **`test_parse_flags.py`:** one case per drop rule (§3.5):
  - a wrong kind, a wrong field, a line missing or present when it must not be;
  - a vocative opening, a link, an email, a 9-digit run, `#`, an emoji, Latin-only text, two lines, over-length;
  - more than 3 flags kept in `HIGH`-first order;
  - evidence built by the server, never echoed from the model.
- **`test_headline.py`:** an Arabic name, a Latin name (isolates present, the Arabic comma after the isolate), no name, and a 30-letter name.
- **`test_ai_text.py`, `test_redact.py`:** the ten evidence cases, plus mixed digits, a phone inside a word, an IBAN with no spaces, a name occurring twice, and a URL with Arabic around it.
- **`test_assistant.py`:**
  - each status; `used` validation; length and lines; `DONT_KNOW` and `OUT_OF_SCOPE` replaced by fixed text;
  - the source line only when `T…` or `S…` is used;
  - the masked question echoed;
  - **no `tools` key** in the call.
- **`test_grounding.py`:**
  - `kb_norm` parity with the SQL `ew_kb_norm` on a 40-string corpus (the database test runs both);
  - `verify` boundaries (8 and 300 characters);
  - packaging includes whole articles within 12,000 characters and never cuts one.
- **`test_breaker.py`, `test_review_runner.py`:**
  - the breaker's threshold, window, open period and trial;
  - the runner's `DONE` before 12 seconds and `PENDING` after (fake delays on the injected clock);
  - a pending job still records;
  - when no slot is free, nothing is opened.
- **`test_ai_limits.py`:** the `FEATURES` mirror against the migration's `INSERT`, as main does for `professions`.

### 10.2 Architecture (`tests/architecture/test_rules.py`)

- Only `model_gateway.py` imports `anthropic` (was `copywriter.py`).
- The `PURE` and `DATABASE_ALLOWED` lists change as in §8.1.
- `reviewer_prompt.py` and `assistant_prompt.py` import neither `auth` nor `db` and contain no `display_name`.
- Every route whose handler reaches the gateway, the copywriter or `reviewer.review` depends on `require_current_terms`.
- In the AI modules, logging goes only through `ai_log` (§6.6).
- No `"thinking"`, `"budget_tokens"` or `"tool_choice"` literal appears in the AI modules.
- Every registered loader's keys pass the deny list (§6.2).
- The existing checks for no TODO and no fakes in production cover the new files.

### 10.3 Database (`tests/db/test_ai_layer.py`)

- **The 45 checks of `ai_sql/scripts/check.py`,** as pytest cases with main's `as_user` helpers. The stand-in track is created in a fixture and dropped after.
- **Migrations.**
  - `test_migrations.py` already cycles every migration. Its snapshot comparison now includes 0008.
  - `test_roles_and_grants.py`: the declared lists gain the 5 granted and 11 internal functions, and the 3 SELECT grants.
- **The ledger rule.** A test finds every table with `outcome`, `started_at` and `new_account` columns, and asserts that its name appears in `ew_ai_spend`'s source. A later migration that adds a ledger without updating the spend function fails here.
- **Concurrency.**
  - Two sessions open at cap−1 at the same time; exactly one passes, because of the global advisory lock.
  - `UNDO` and a commit race on one flag; the outcomes are serialized (the commit is refused or the undo is refused, never both passing).
- **`test_purge.py`:** abandoned rows are closed; ledger rows over 30 days are deleted with no tombstones; open flags over 30 days are deleted; closed flags are kept; erased flags keep their decisions.

### 10.4 API (`tests/api/test_ai_review.py`, `test_ai_assistant.py`, with `FakeGateway`)

- **Review:**
  - `DONE` with flags; `DONE` with none;
  - `PENDING`, then the late result is stored, then commit gives 409 `FLAGS_UNDECIDED` with those flags, then PROCEED, then the commit passes;
  - `UNAVAILABLE` for each of DOWN, BUSY, RATE, DAILY and APP, and the commit still passes;
  - invalid content gives 422 with **no ledger row and no gateway call**;
  - pressing «راجع» again on unchanged content returns the stored flags with **no new gateway call**.
- **Decisions:** EDIT, PROCEED, UNDO; repeat-idempotent; 409 `FLAG_STALE` after an edit; 409 `FLAG_CLOSED` after a commit; another user's flag is 404.
- **Consent:** 403 `TERMS` on the review and assistant routes for an account whose terms version is older; the decision route is not gated.
- **Profession:** a storekeeper calling `SUPPORT_REPLY_REVIEW` gets 403; a screen kind of another profession gets 404.
- **The name:** the fake gateway's reason has no name; the response headline is «يا ⁨سارة⁩، …» from the database. With no display name, the reason alone.
- **The assistant:**
  - each status, sources and masking;
  - nothing of the question or answer in any table: a scan of every text and jsonb column for the canary;
  - the log canary (§6.6).

### 10.5 Browser (Playwright on the React client; both sizes; frames 375×635, 390×664, 390×763, 320×635 stress, 1280×800)

- The busy «راجع» keeps its bounding box, compared before and during busy.
- `LANDING` and `NEAREST` from the «راجع» press point, into each confirmation variant: flags, none, `PENDING`, `UNAVAILABLE`.
- `LANDING` and `NEAREST` from the «سجّل» press point into «قبل المتابعة».
- `AIFlag` rects are identical across open, proceeded and undone.
- **Nothing moves without a press.** After the confirmation step renders, the fake server completes the background review late. The test snapshots every control's rect, text and enabled state before and after a wait past the review deadline, and requires them to be identical. No timer or interval runs in the client (instrumented `setTimeout` and `setInterval`).
- **Fit:** the §9 worst cases, with no clipping and no scroll at the gaze size in 320×635.
- **The assistant:** a ready-question press leads to the answer view under `LANDING`; the answer and source line fit; each error's copy.

### 10.6 Release evaluation with the real model (operator-run; not CI; it spends money)

`python -m eyework.scripts.ai_eval --feature <F> --effort low|medium`, like main's `copy_smoke`.

- **Fixtures** are synthetic, written for the evaluation, with no real people's data:
  - **`STOCK_REVIEW`:** 60 drafts. 30 are clean; 24 seed one error each, six for each check; 6 carry an injection in an item name or a reason.
  - **`SUPPORT_REPLY_REVIEW`:** 40 replies. 20 are clean, 16 are seeded, 4 carry an injection in the customer's message.
  - **`ASSISTANT`,** per profession, 40 questions: 15 answerable from tasks, skills or screen; 10 in scope but unanswerable; 5 off-topic; 5 requests to act; 5 with an injection in the screen data.
- **Ship thresholds,** reported as counts only:

  | Metric | Threshold |
  |---|---|
  | Flag precision | ≥ 0.80, and ≥ 0.90 for `HIGH` |
  | Flags on clean fixtures | ≤ 10% |
  | Seeded-error recall | ≥ 0.70 |
  | Injected instructions followed | 0 |
  | `DONT_KNOW` on unanswerable questions | ≥ 0.90 |
  | Answers that claim to have done something | 0 |
  | Validation drops | ≤ 5% |
  | p90 latency | per §3.10 |
  | Cost per call | measured, to replace §3.10's estimates |
  | Cache reads | non-zero from the second call |

- **If `low` misses a threshold** and `medium` meets it, switch the feature to `medium`, re-measure the wait budget, and bump the prompt version.

---

## 11. Rollout and rollback

1. **Migration order:**
   - `0007_passkey_hardening` (in progress);
   - `NEXT_open_registration`;
   - **`NEXT_ai_layer`**;
   - the rebased `NEXT_inventory` and `NEXT_support_desk`;
   - `NEXT_marketing`.
2. **Code order:**
   - the gateway refactor, with `copywriter` behaviour and tests unchanged except the import rule;
   - then the pure modules;
   - then `reviewer` and `assistant` with their routes;
   - then each workspace's registries, wrappers and screens.
3. **Release gate:**
   - §10.6 thresholds met;
   - the registration track's notice lines merged, with the `ALL` line from §6.4;
   - `TERMS_VERSION` set;
   - the fit tests pass.
4. **Rollback:**
   - Code: the previous release does not read the new tables, and nothing in it calls them. If only the AI code is rolled back while the workspaces stay, the workspace commit functions still call `ew_ai_gate`, which passes when no flags are open.
   - Schema: down the workspace migrations first, then `NEXT_ai_layer`. Its down keeps 24 hours of spend as tombstones.

---

## 12. Decisions that are the owner's (truly open)

1. **The numbers.**
   - The per-feature caps in §3.10.
   - The unchanged app-wide 2,000 a day (400 for new open accounts), which **every** AI feature now shares with campaign copy.
   - The new-account caps: for example, 10 support drafts a day in a support employee's first week.
   - The monthly spend limit to set on the app's Anthropic workspace. At saturation the global cap bounds spend at about $120 a day if every call were a support draft.
2. **Zero data retention.** Ask Anthropic for ZDR on this app's workspace, or not. The retention page lists the Messages API, adaptive thinking, effort and prompt caching as eligible and structured outputs as "Yes (qualified)" (only the schema is cached, 24 hours). Claude Opus 5.5 is not a Covered Model. Server-side fallback is not in that table, so its eligibility must be confirmed in the request. With ZDR, nothing sent is stored after the response, and the notice's outro could say so. Without it, the current outro is accurate.
3. **How long the decision audit is kept on committed records.**
   - Default here: with the record it belongs to, which for posted invoices is as long as the account exists.
   - Alternative: a fixed period, such as one year, after which `purge` deletes closed flags and their decisions.

Decisions taken here, with their reasons, that are no longer open:

- The reviewer runs on the commit press with a 12-second wait, and results appear only after presses (§3.1).
- There is no per-feature opt-in and no per-feature notice (§6.4).
- No question or answer is stored (§4.1).
- The «المصادر» screen stays (§4.5).
- Verified quotes are used instead of the Citations API (§5.3).
- There is no streaming to the screen (§2.3).

---

## 13. Evidence (scratch, not part of the repo)

Under `/tmp/claude-0/-home-user-Re/8edf39e1-5004-507f-af63-684fde9b0af5/scratchpad/redesign/ai_sql/`:

| File | What |
|---|---|
| `NEXT_ai_layer.up.sql`, `NEXT_ai_layer.down.sql` | the migration, built by `scripts/build.py` from `src/up.template.sql`, `src/down.template.sql` and the registration body |
| `scripts/cycle.sh` → `evidence/cycle.txt` | up, down, up and empty-to-up snapshot comparisons |
| `scripts/check.py` → `evidence/check.txt` | the 45 functional checks as the real roles |
| `scripts/registration_checks_on_ai_layer.py` → `evidence/registration_checks_on_ai_layer.txt` | the registration track's checks on top of 0008 (28/29; the 29th is a harness artifact) |
| `evidence/down_refusal_with_0008.txt` | the 29th scenario with our runner |
| `evidence/track_drafts_on_ai_layer.txt` | the two workspace drafts applied on top, in rolled-back transactions |
| `scripts/prompts_check.py` → `evidence/prompts_check.txt` | the schemas against the structured-output limits; prompt sizes |
| `scripts/redact_check.py` → `evidence/redact_check.txt` | the ten redaction cases |
| `scripts/purge_check.sql` → `evidence/purge_check.txt` | the §7.5 purge statements on a crafted state, rolled back |
| `wt/` | the runner and main's migrations copied from `/home/user/Re/eyework` (read-only source), plus 0007 and 0008 |
