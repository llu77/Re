
---

## 5. PostgreSQL schema: `NEXT_support_desk`

### 5.1 Design notes

- **The web role reads, and never writes a table.** `eyework_app` has `SELECT` on its own rows of 13 tables, through `FOR SELECT` policies on `user_id = ew_current_user()`.
  - It has no `INSERT`, `UPDATE` or `DELETE` grant on any table here.
  - Every write is one of 32 `SECURITY DEFINER` functions with `SET search_path = public, pg_temp`. Each takes the user from `ew_current_user()`, never from a parameter, does one thing, and writes its audit row in the same transaction.
  - `support_ai_limits` and `support_ticket_transition` have no web grant and no web policy.
- **Forced RLS on all 15 tables, the owner included**, with an owner policy for the `SECURITY DEFINER` functions, triggers and `admin` (the 0001 pattern).
- **Triggers are the second guard, behind the functions, and the owner cannot bypass them.**
  - Insert guards: profession, caps, numbering, SLA.
  - Update guards: managed columns are fixed; the state machines are tables or explicit lists.
  - Append-only: messages, citations, article versions, events.
  - A **deferred constraint trigger** refuses an `ANSWER` draft with no quote at commit.
  - A trigger checks every quote word for word against the **published** version of an article owned by the same user (`ew_kb_norm`: NFKC, lower case, no tashkeel or tatweel, single spaces).
  - A trigger checks every flag's quote against the text it flags.
  - A trigger logs every status change, with the actor `SYSTEM` when there is no session.
- **Idempotent writes.** `client_token` on tickets, messages, replies and articles: a repeated press, or a second dwell, returns the first row.
- **Stale screens are refused.** `row_version` on tickets and articles, checked by every function that changes them (409 `STALE`).
- **The SLA clock is computed by the trigger, not the client:**
  - `first_reply_due_at` comes from the priority's target, and is recomputed from `created_at` when the priority changes and no reply has been sent yet;
  - `wait_seconds` and `clock_since` run in `NEW`, `OPEN` and `ESCALATED` and stop in `PENDING`, `RESOLVED` and `CLOSED` (Zendesk's requester wait time, S6).
- **AI spend.**
  - `support_ai_calls` is a ledger like `generation_attempts`: opened before the call under every cap, settled once (`ew_attempt_settle_once`).
  - Deleting a row writes an identity-free tombstone with `new_account`, so deleting an account refunds nothing.
  - `ew_ai_spend` sums all ledgers, and `ew_begin_generation` (the campaigns) uses it: the 2,000-a-day app cap and the 400-a-day new-account pool are one budget across tools, under the same advisory lock `eyework.generation_global_cap`.
- **`support_ai_calls` has no foreign key to tickets, deliberately.** A settled call cannot change (0002 trigger), and when an account is deleted, an `ON DELETE SET NULL` from the ticket could fire before the call's own cascade and fail the deletion. Calls are purged after 7 days, long before tickets.
- **No free text in the audit.** `support_events.detail` must match `^[A-Z0-9_]{2,40}$`. The trail survives the 30-day text purge and is deleted with its ticket after a year.
- **Down.**
  - It deletes the call ledger first, so the last 24 hours leave tombstones.
  - It restores `ew_begin_generation` with the registration migration's body word for word. The body was extracted from `registration_sql/next/NEXT_open_registration.up.sql` by `awk`, not retyped.
  - It drops the functions that return row types before the tables, and the trigger and constraint functions after them.

### 5.2 Objects

| Table | Holds | Key rules |
|---|---|---|
| `support_settings` | Signature, desk-notice version, next ticket and article numbers | Created on first use; inserting it creates the default SLA rows |
| `support_sla_targets` | Per priority: first-reply and resolution minutes | Values from fixed lists; first reply < resolution |
| `support_ai_limits` | Per AI kind: per-user day, per-new-user day, per-user 10 min, app day | `DRAFT` 60/20/10/800, `REPLY_REVIEW` 60/20/10/600, `ARTICLE_PROPOSAL` 10/3/3/150, `ARTICLE_REVIEW` 20/5/5/200 |
| `support_ticket_transition` | The status machine (18 rows) | Compared with `support_rules.TRANSITIONS` by a test |
| `support_tickets` | Status, priority, category, channel, label, subject, SLA fields, follow-up link | Insert guard (profession, caps 300 open / 200 a day, or 30 / 30 for a new open account); update guard; status events |
| `support_messages` | `CUSTOMER`, `NOTE` (masked text) and `AGENT` (confirmed reply) | No email and no run of 9+ digits in customer or note text; 60 per ticket; 400 typed a day (60 for a new account); append-only |
| `support_ai_calls` | One row per model call | Caps; settle once; tombstone on delete |
| `kb_articles` | State, published and latest version, «تحتاج مراجعة», reuse count | 300 per user; state machine; publishes only the latest version |
| `kb_versions` | Title, issue, environment, resolution, cause, origin, Arabic `tsvector` | 30 per article; append-only; no national ID, card or IBAN |
| `support_drafts` | The AI draft and its classification; suggested priority (written by the trigger); the employee's rejection | Only on an open call for the latest customer message; immutable except one rejection |
| `support_draft_citations` | 1–3 verbatim quotes per draft | From a published version of the user's own article |
| `support_replies` | The final text (`core`, `body`, `body_sha256`), kind, origin, state, review | One live reply per ticket; origin decided by the database; text immutable |
| `support_flags` | Rule and AI flags (code, quote, state, dismiss reason) | Quote verbatim; decided once |
| `support_escalations` | Target, note, return | One open per ticket |
| `support_events` | The audit trail | Codes only; append-only |

Functions granted to `eyework_app`:

- **Domain** (used by checks and generated columns): `ew_support_text_ok`, `ew_support_contact_free`, `ew_support_kb_clean`, `ew_kb_norm`, `ew_support_priority_for`, `ew_support_priority_rank`.
- **Workspace** (32): `ew_support_accept_notice`, `ew_support_save_settings`, `ew_support_create_ticket`, `ew_support_add_message`, `ew_support_set_ticket`, `ew_support_begin_draft`, `ew_support_record_draft`, `ew_support_finish_call`, `ew_support_reject_draft`, `ew_support_prepare_reply`, `ew_support_begin_review`, `ew_support_record_review`, `ew_support_ack_flag`, `ew_support_release_reply`, `ew_support_confirm_reply`, `ew_support_escalate`, `ew_support_return_escalation`, `ew_support_resolve`, `ew_support_reopen`, `ew_support_follow_up`, `ew_support_close_due`, `ew_kb_create`, `ew_kb_add_version`, `ew_kb_publish`, `ew_kb_set_state`, `ew_kb_mark_review`, `ew_kb_search`, `ew_kb_begin_proposal`, `ew_kb_record_proposal`, `ew_kb_begin_review`, `ew_kb_record_review`, `ew_support_my_ai_usage`.

Internal (`REVOKE ALL … FROM PUBLIC`, no grant; the web role gets `permission denied`, which is checked): `ew_support_me`, `ew_support_require_notice`, `ew_support_ticket_for`, `ew_support_log`, `ew_ai_spend`, `ew_support_ai_open`, `ew_support_ai_settle`, and the 18 trigger functions.
