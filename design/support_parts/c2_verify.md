
`admin set-profession`, when an account leaves `SUPPORT`, runs this in its existing transaction, after locking the user row (`FOR UPDATE`) and before changing `users.profession`:

```sql
-- خروج الحساب من الدعم الفني: تُسحب ردوده الحيّة وتُغلق تذاكره المفتوحة (لا تُحذف؛ يمحو purge نصوصها بعد ثلاثين يوماً).
UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now()
 WHERE user_id = %s AND state IN ('READY', 'RELEASED');
UPDATE support_tickets SET status = 'CLOSED', close_reason = 'PROFESSION_CHANGED'
 WHERE user_id = %s AND status <> 'CLOSED';
```

### 5.6 Verified on PostgreSQL 16.13 (scratch database `support_spec_check`, dropped afterwards)

Base: main's 0001–0006 (unchanged since `fa84cd1`), then the registration track's current `NEXT_open_registration` from `registration_sql/next/` (its `ew_begin_generation` is identical to the draft 0007's). The script `design/support_tools/run_all.sh` reproduces everything below.

- **Schema cycle.**
  - Up, then down: the `pg_dump --schema-only` snapshot equals the base snapshot.
  - Up a second time: equals the first up.
  - Down through the base to empty, then everything up again: equals the first up.
  - Down **with live data** (32 tickets, drafts, replies, articles, calls): equals the base; the last day's calls left their tombstones.
- **Functional checks run as the real `eyework_app` role (70 pass, 0 fail).** They cover:
  - the web role cannot write any table, or call the internal functions or `ew_ai_spend`;
  - masking guards: email, spaced phone, phone-like label, national ID in an article; a 7-digit "KB5034441" survives;
  - numbering, idempotency and the SLA due time;
  - the notice gate for customer text, and separately for model calls;
  - an `ANSWER` without a quote is refused at commit, and a non-verbatim quote is refused;
  - the suggested priority is computed by the trigger (WIDESPREAD+STOPPED → URGENT; SINGLE+STOPPED → HIGH);
  - accepting a suggestion that does not match it is refused; a priority below the suggestion raises a flag;
  - `AS_IS` versus `EDITED`; one live reply per ticket; the hash check; confirming before release is refused;
  - sending an `ANSWER` resolves the ticket, counts reuse and logs the event;
  - a customer message reopens a resolved ticket; a reply on an old draft is refused;
  - a review is required before release, a non-verbatim AI flag is refused, and an open flag blocks release;
  - `ASK_INFO` makes the ticket pending and stops the clock;
  - the resolve rules; escalation, with an `ANSWER` refused while escalated;
  - rejecting a draft as wrong marks the quoted article;
  - isolation between two support accounts, a marketing account and no session;
  - the new-open-account ticket cap (31st refused) and the usage report (20);
  - an AI proposal is invisible until published; publishing is blocked by a running review and by an open flag; only the latest version publishes; archiving removes an article from search; a third proposal from one ticket is refused;
  - a model call is refused when the notice is withdrawn;
  - the global cap at 2,000 refuses a support draft (`generation_global_cap`);
  - after a change of profession, the desk refuses the account.
- **Owner-side checks.**
  - Automatic close happens after 4 days, with actor `SYSTEM`; a follow-up is linked.
  - The purge runs in three passes: close, then texts at 30 days (messages, drafts and replies go to 0, events stay, quotes are cleared), then metadata at 365 days. The ledger empties, and proposals go `PROPOSED` → `DISCARDED` → deleted.
  - The call ledger purge detaches the AI article version.
  - Account deletion removes everything and leaves one tombstone for the last day's call.
  - `set-profession` closes all 30 of the account's open tickets.
- **Concurrency.** Two sessions of one account start a draft at the same moment. The second waits on the user-row lock, then gets `support_ai_in_progress`. One call is open.
- **Digests** (SHA-256, first 16 hex digits): `NEXT_support_desk.up.sql` `8d81474ab5d2d49f`, `NEXT_support_desk.down.sql` `a1244a4d29afecf9`, purge SQL `f2c4cf7daa7d45ca`. The SQL in §5.3–5.5 is these files verbatim.
