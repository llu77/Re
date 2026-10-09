# Open registration, the size mode, and consent

Track spec for eyework. Date: 2026-10-09.

**Status: ready to implement, with one gate.** The three workspace tracks must supply their lines of the consent notice before release (§9.3). Until they do, `TERMS_VERSION` cannot be set and the notice cannot ship.

UI copy is Modern Standard Arabic; everything else is English.

---

## 0. Summary

The owner asked for registration that needs no invitation. A later brief, on the evening of 2026-10-08, added four changes. This spec covers all of it end to end.

### 0.1 What the 2026-10-08 brief changed (new in this version)

- **Landing.** After sign-up, the user lands directly in the unified workspace of the profession chosen at sign-up. There is no portal page and no welcome in between (§8.6).
  - Per the owner's update of 2026-10-09, that workspace's home is action buttons; the tasks and skills screens are gone. The profession step at sign-up therefore shows a work line, not "tasks and skills" (§9.3 H).
- **Size mode.**
  - A new step right after the consent notice, «كيف تستخدم الجهاز؟», with the options «باللمس» (`COMPACT`) and «بتتبّع العين» (`GAZE`). The notice first tells the user that this is stored.
  - The choice is stored per account in `users.ui_size` and is changeable from «حسابي» (§6, §8.8).
  - Accounts with no size yet are asked once, at their next sign-in, and are never shrunk silently (§8.7). That covers every existing account and every invited one.
- **React screens.**
  - The sign-up screens are now React components from the visual track: a welcome screen with «ادخل» and «أنشئ حساباً», the adapted AuthForm, and the steps (§8).
  - The static client's sign-up is retired when the React client is served (§7.13).
- **Consent notice.**
  - The notice now names what each workspace sends to Anthropic: product photos and text (marketing), customer messages (support), and invoice lines for the AI reviewer (inventory).
  - It is now served by the server (`eyework/terms.py`) and split over two screens, «ما يُحفظ هنا» and «ما يُرسَل إلى Anthropic». Both fit at the large size in the narrowest frame (§8.9).
  - Consent takes a deliberate press: «قرأتُه», then «أوافق وأتابع» (§8.5).
  - The three workspace tracks must each supply their exact line. **§9.3 is the clearly marked list of what each track supplies.**
  - `TERMS_VERSION` is bumped. Existing and invited accounts accept the new version at their next sign-in, before anything of theirs is sent to the model. The server enforces this (§7.10).

### 0.2 Unchanged from the 2026-10-08 draft

- **Modes.** `EYEWORK_REGISTRATION=open|code|closed`, with `open` as the default.
  - `EYEWORK_SUPPORT_CONTACT` is required in `open` mode. An upgraded deployment without it refuses to start, so registration never opens by accident (§2).
  - Operator links (`#signup=CODE`) keep working in every mode except `closed`.
- **Database limits.** Every registration cap counts from an identity-free `registration_ledger`, so deleting an account frees no room.
  - Registrations: 200 a day in total, at most 150 of them without a link.
  - Open registration pauses after 60 "email taken" answers in a day.
  - A new open account, in its first 7 days, gets 10 AI generations a day. All new accounts together share 400 a day out of the app-wide 2,000. Each gets 3 open campaigns.
- **Per network** (an IPv4 address or an IPv6 /64): 5 registrations an hour, 10 a day, and 3 "email taken" answers a day.
- **The enumeration trade-off is stated plainly (§4).** In `open` mode, anyone can learn whether an email has an account here.

### 0.3 Verified before writing (evidence in §13)

- **The migration cycles exactly.**
  - `NEXT_open_registration` goes up, down and up with byte-identical `pg_dump --schema-only` snapshots, from 0006 and from a full rollback to empty.
  - Run with the repo's own runner (`python3 -m eyework.migrations.run`) on PostgreSQL 16, in the scratch database `reg_v2_test`, from a worktree of `origin/main` at `d543356`.
- **29 of 29 functional checks pass, run as the real `eyework_app` role.**
- **Main's database suite was run against the new schema.** 572 tests pass and 23 fail.
  - 21 of the 23 come from one test helper that calls the old 7-argument `ew_register`.
  - With that helper fixed, exactly two tests fail. Both are expected: the daily cap now counts the ledger, not used codes.
  - The other two failures are the declared function list and the tombstone columns. §10.2 lists every change.
- **The other track's draft migration still applies.**
  - The work-tools draft `work_sql/0008_work_tools.up.sql` calls this migration's names (`ew_new_open_account`, `new_account`, `generation_new_accounts_cap`).
  - It applies on top of NEXT after one unrelated parse fix in the draft itself (§9.3, item I).
- **The new screens fit.** The size step and both notice screens fit with no scroll and nothing clipped, at both sizes, in all four handheld frames.
  - This is an estimate measured with the v2 tokens and the bundled fonts (§8.9).
  - At the large size in the 320×635 frame, each workspace line may be up to 63 characters if there are four lines.

---

## 1. Baseline and inputs

- **Code of record.** `origin/main` at `d543356`: migrations 0001–0006, `TERMS_VERSION = "2026-10-09"`, and the static client.
  - Main has since moved to `8c8f3f5` (#11 merged the React client, then #12). `git diff d543356 8c8f3f5` shows that none of the files this spec changes moved: the migrations, `auth.py`, `web/`, `config.py`, `admin.py`, `campaigns.py`, `rate_limit.py`, `test_terms.py` and the database tests are unchanged. The only change is four lines of font preloads in `static/index.html`. The evidence holds for `8c8f3f5`.
  - The local branch `main` in `/home/user/Re` is the old platform branch, not eyework's main.
- **React client.** `a519ddb` adds `eyework/client`, with the 21st.dev AuthForm and DropdownNavigation.
  - The visual track's v2 client (`redesign/v2/client`, in progress) defines the two sizes:
    - `:root[data-size="compact"]`: 44–48 px targets, 12 px gaps, 16 px body text. This is the default.
    - `:root[data-size="gaze"]`: 72 px targets, 24 px gaps, 18 px body text.
  - Its `lib/size.tsx` already names the server field `ui_size` and the route `PUT /api/me/ui-size`. This spec uses those names.
- **Workspace tracks** (inventory, marketing, support). Their specs did not exist when this was written (2026-10-09, 00:40 UTC).
  - This spec defines generic interfaces they plug into: the notice lines, the consent gate, the new-account AI flag, and the landing screen.
  - §9.3 lists exactly what each track must supply.
- **Design choice for 0007: A, not B.** The previous run left two designs.
  - **Design A** is this spec's text from 2026-10-08: `open_registered boolean`, a `via`/`outcome` ledger, 7 days, a pause at 60, and 3 campaigns.
  - **Design B** was a later prototype: `registered_via text`, a single `kind` ledger, 72 hours, a pause at 50, and a switch that revokes EXECUTE.
  - **Why A.**
    1. The work-tools draft 0008 already calls A's names.
    2. B's constraint `registered_via_iff_self` breaks main's own fixtures. `test_admin_professions` fails on it; see `superseded_B/evidence/existing_db_suite.log`.
    3. B's database switch adds little (§3).
  - B and its prototype tests are kept under `registration_sql/superseded_B/` for the record.
- **Migration name and number.** The file is `NEXT_open_registration`; the integrator numbers it.
  - 0007 is reserved for passkey hardening (owner brief, migration numbering of 2026-10-09), so this migration will be 0008 or later.
  - That file does not exist yet, so this one was verified directly on top of 0006, running locally as `0007`. It touches neither `sessions` nor any passkey function, so the two are independent. The integrator re-runs `scripts/cycle.sh` on the final sequence.
  - It must come before any migration that calls `ew_new_open_account` or `new_account`, such as the work-tools draft.

---

## 2. Modes

| | `open` (default) | `code` | `closed` |
|---|---|---|---|
| «أنشئ حساباً» on the welcome screen | shown | absent; the line «التسجيل هنا برابطٍ ممّن يدير التطبيق.» | absent; the line «الحسابات هنا بدعوةٍ ممّن يدير التطبيق.» |
| `#signup=CODE` link | works, and the account is not "open" | works | refused (403 `REGISTER_CLOSED`) |
| `GET /api/auth/registration` | 204, or 503 `REGISTER_FULL` / `REGISTER_PAUSED` | 403 `REGISTER_LINK` | 403 `REGISTER_CLOSED` |
| `POST /api/auth/register` without `code` | open path | 403 `REGISTER_LINK` | 403 `REGISTER_CLOSED` |
| `POST /api/auth/register` with `code` | code path | code path | 403 `REGISTER_CLOSED` |
| `POST /api/auth/signup-code` | unchanged | unchanged | 403 `REGISTER_CLOSED` |
| `EYEWORK_SUPPORT_CONTACT` | **required** | optional | optional |
| Invitations (`admin create-user`) | unchanged | unchanged | unchanged |

**Boot rules (`config.load`).**

- If `EYEWORK_REGISTRATION` is unset or empty, the mode is `open`. Any other value outside the three modes raises `ConfigError`.
- `EYEWORK_SUPPORT_CONTACT` must have the shape of a login email. After NFKC and lowercasing it matches `^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$` and is at most 254 characters.
  - It is the operator's address, so showing it reveals nothing about users.
- **Upgrades.** A deployment that upgrades without changing its environment refuses to start, with a `ConfigError` naming `EYEWORK_SUPPORT_CONTACT`. The operator either sets a contact, which opens registration, or sets `EYEWORK_REGISTRATION=code`.
  - This follows from the owner's ask (open by default) and is not an open decision.

**The server decides the mode.** `ew_register` still answers `CODE` without a valid code. The open path is a separate function, `ew_register_open`, which the server calls only in `open` mode.

---

## 3. Guarantees: what holds, what moves

| Guarantee | Before (0005/0006) | After (NEXT) |
|---|---|---|
| No account without a valid code | DB (`ew_register`) | `ew_register` unchanged in this respect. In `code` and `closed` modes the server never calls `ew_register_open`, and API and UI tests prove it. In `open` mode the guarantee is dropped on purpose. |
| Registration never takes over an existing login or a pending invitation | DB (`ON CONFLICT DO NOTHING`) | DB, in both functions |
| Name shape, birth date (not in the future by Riyadh's date, not before 1900), consent, existing profession | DB | DB, in both functions |
| **Every new account has a size, chosen by its owner** | — | DB: both register functions refuse without one (`registration_needs_ui_size`), and the value is checked (`ui_size_known`). After that, only `ew_set_my_ui_size` changes it, for the session user. |
| At most 200 self-registrations in 24 h, and deleting accounts makes no room | DB, from used codes | DB, from `registration_ledger`. Used codes from the last day are backfilled at migration time. |
| At most 150 registrations without a link in 24 h | — | DB, from the ledger |
| "Email taken" answers are bounded | 3 per code (DB) | Codes: unchanged. Open path: 3 per network a day (server memory), and 60 a day app-wide, after which open registration pauses (DB). |
| The web role learns nothing about other users | DB grants | The ledger has no grant and no web-role policy. Every new function returns app-wide state or the session user's own row. The column `ui_size` has no grant. |
| AI spend | 2,000 a day app-wide, 40 per user (DB) | Unchanged, plus for new open accounts: 10 a day each, 400 a day for all of them together (deleted ones included), and 3 open campaigns each (DB) |
| **Nothing of an account is sent to the model before it accepts the current notice** | Registration only: consent recorded at sign-up | Server: every route that calls the model depends on `require_current_terms` (§7.10). DB: the accepted version is recorded for the session user only, and never moves backwards (`ew_accept_terms`). |
| A down migration never leaves an account the older schema does not describe | 0005 down refuses | NEXT down also refuses while any `open_registered` account exists |

**No database-side mode switch (alternative considered; design B had one).**

- B's switch revoked EXECUTE on `ew_register_open`. That would hold even against a compromised web role, which a setting the web role can write would not.
- But a compromised web role can already read and change every account's rows by setting `eyework.user_id`, so stopping it from creating accounts adds almost nothing.
- Meanwhile the operator would have a second switch to keep in step with `EYEWORK_REGISTRATION`.
- Closing open registration takes `EYEWORK_REGISTRATION=code` and a restart. The route tests in §10 cover the route bug that a database switch would catch.

---

## 4. A taken email

### 4.1 What the server returns

Unchanged from the code path:

- `409 REGISTER_TAKEN` with `field: "TAKEN"` and the message «يوجد حسابٌ بهذا البريد. ادخل به، أو اكتب بريداً آخر.»
- The client returns to the email step with that alert.

On the open path, the answer also:

1. writes one ledger row `(OPEN, TAKEN)`, which counts toward the app-wide pause;
2. records one event in the per-network budget `taken_open_net`.

### 4.2 The trade-off, plainly

- **Who can ask.** In `open` mode, anyone can find out whether a given email has an account here.
  - The user list is health information, because the people on it often work with their eyes. "Does X use this app?" is a sensitive question.
- **Why it cannot be closed.** The app sends no email, so it cannot check that the person registering owns the address. When the email is the unique login name, "created" and "not created" are different outcomes, and that difference is the answer.
- **What could close it.** Only a different design (§4.5).
- **Sign-in** keeps its guarantee of equal timing and one message for every failure. In `open` mode, though, registration is a second way to ask.

### 4.3 Mitigations (all in this spec)

1. **No "is this email free?" endpoint.** The only way to ask is a full `POST /api/auth/register`.
   - It must pass every field check: name, birth date, email shape, a password of 12 or more characters, an existing profession, a size, `accept_terms: true` and the current `terms_version`.
   - The server computes scrypt before asking the database.
2. **Asking about a free email creates a real account.** That costs one of the 150 open places for the day and one of the network's 10 daily registrations.
3. **Per network** (an IPv4 address or an IPv6 /64): 5 registrations an hour, 10 a day, and 3 "email taken" answers a day.
   - After that, every open registration from that network gets `429 RATE` before the database is touched.
   - These limits are checked after the field checks, so a typo costs nothing.
4. **App-wide, in the database.** 60 `(OPEN, TAKEN)` answers in 24 h pause open registration for everyone with `503 REGISTER_PAUSED`. Operator links keep working.
5. **The same answer whatever the email.** The caps and the pause are checked before the insert, so on a full or paused day a taken email and a free email get the same response.
6. **Users are told.**
   - «ما يُحفظ هنا» says «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.»
   - Existing users see the same line when they accept the new version at their next sign-in (§8.7).
   - The email step adds under its field: «من يحاول التسجيل بهذا البريد يعرف أن له حساباً هنا. إن كان ذلك يضرّك فاختر بريداً لا يعرفه غيرك.»
7. **A database leak still reveals no emails.** Only HMACs are stored (0001).

### 4.4 What is not mitigated

- **A single targeted question.** One request from a new network answers it.
- **Squatting.** Someone can register another person's email first. The owner of the address then writes to `EYEWORK_SUPPORT_CONTACT` from it, and the operator replies to confirm. The operator then runs `admin delete-user --login <email> --confirm-delete-all-data`.
- **Existing accounts, including invited ones, become askable** as soon as the mode is `open`. They learn this at their next sign-in, from «ما يُحفظ هنا» (§8.7).

### 4.5 Alternatives (owner decision 1)

| Option | Removes the yes/no answer? | Cost |
|---|---|---|
| A. **This spec:** email as the login name, an honest 409, the limits in §4.3 | No | A single targeted question gets an answer |
| B. Verify the email by sending a one-time code; registration always answers "check your inbox" | Yes | An email provider learns who registers for this app: a third party holding health information. It also needs a sending domain, and handling for bounces and abuse. |
| C. The app generates the login name, kept by Safari Keychain or a passkey | Yes | Users must keep a random name; losing the Keychain loses the account; typing it by gaze is slow |
| D. Keep `code` mode | Yes (only code holders can ask, 3 times per code) | Every account still needs the operator |

### 4.6 Recovery for an open account

- The help text on the sign-in screen and on the review step sends the user to `EYEWORK_SUPPORT_CONTACT`, writing from the account's own address.
- The operator replies to that address. On confirmation, the operator runs `reissue-activation --login <email> --owner-verified`.

---

## 5. Abuse limits

### 5.1 Registration volume (database)

All counts are over the last 24 h of `registration_ledger`. They run under the advisory lock shared with the code path (`eyework.registration_daily_cap`).

| Constraint (error) | Counts | Limit | Applies to |
|---|---|---|---|
| `registration_daily_cap` (503 `REGISTER_FULL`) | `outcome = 'OK'`, both routes | 200 | both routes |
| `registration_open_daily_cap` (503 `REGISTER_FULL`) | `via = 'OPEN' AND outcome = 'OK'` | 150 | open route; operator links always keep at least 50 a day |
| `registration_open_paused` (503 `REGISTER_PAUSED`) | `via = 'OPEN' AND outcome = 'TAKEN'` | 60 | open route |

### 5.2 Per network and per user (server memory)

| Limiter | Key | Limit | Counted when |
|---|---|---|---|
| `register_open_net` | `client_network()` | 5 / hour | each open registration that passes the field checks |
| `register_open_net_day` | `client_network()` | 10 / 24 h | same |
| `taken_open_net` | `client_network()` | 3 / 24 h | after a TAKEN answer; checked before the database call |
| `registration_check_net` | `client_network()` | 30 / hour | `GET /api/auth/registration` |
| `register_ip`, `signup_code_ip` | `client_ip()` | 20 / hour (unchanged) | code path |
| `ui_size_user` | the user id | 30 / hour | `PUT /api/me/ui-size` |
| `terms_user` | the user id | 10 / hour | `POST /api/me/terms` |

- **`client_network()`** maps an IPv4 address to itself, an IPv6 address to its /64, and an IPv4-mapped IPv6 address to its IPv4 address.
- **Scope.** These limits sit behind the trusted proxy (`--proxy-headers`) and are per process.
- **`taken_open_net` overshoot.** It uses a new pair of calls, `blocked()` then `record()`. Two concurrent requests from one network can both pass, overshooting by at most the number in flight; `register_open_net` still bounds that.

### 5.3 AI spend for new accounts (database)

A **new open account** is `open_registered` and was created less than 7 days ago (`ew_new_open_account`).

| Constraint (error) | Limit |
|---|---|
| `generation_new_account_cap` (429 `AI_NEW_DAILY`, Retry-After 3600) | 10 billable marketing generations per 24 h for that account |
| `generation_new_accounts_cap` (503 `AI_NEW_BUSY`, Retry-After 3600) | 400 billable generations per 24 h across all new open accounts. Counted from `generation_attempts.new_account` plus `attempt_tombstones.new_account`, so deleting an account refunds nothing. |
| `new_account_campaign_cap` (409 `NEW_OPEN_CAP`) | 3 open campaigns (DRAFT, COPY_PROPOSED, COPY_APPROVED) instead of 20 |

- **Other workspaces.** The inventory reviewer, the support drafts and any shared tools spend from the same budget.
  - Each track's model-calling function must mark its rows `new_account` with `ew_new_open_account(uid)` at start, and count the 400 pool under the same lock (`eyework.generation_global_cap`).
  - Each track sets its own per-feature new-account cap (§9.3, item E). The work-tools draft already does this with `ai_calls.new_account`.
- **What the user sees.** `/api/me` returns `generation_limit` (10 or 40) and `generations_left`, from `ew_my_generation_limit()`.

### 5.4 Storage

- With the 3-campaign cap, a new account holds at most 9 MB of images in its first week. 150 such accounts a day add at most 1.35 GB a day.
- After the first week an account can hold 20 campaigns, or 60 MB. The daily cap and the 30-day purge of idle drafts still bound the total.
- A global ceiling is part of owner decision 3.

---

## 6. Migration `NEXT_open_registration`

### 6.1 Design notes

- **`registration_ledger(occurred_at, via, outcome)`.**
  - It holds no account, no HMAC and no address.
  - A CHECK (`registration_ledger_taken_is_open`) forbids `(CODE, TAKEN)`, because a TAKEN answer through a link is counted on the code itself.
  - RLS is enabled and forced, with an owner policy only. The web role has no grant and no policy. `purge` deletes rows older than 24 h.
  - It is backfilled from `signup_codes.used_at` for the last 24 h, including codes whose account was deleted.
- **`ew_register_open`.**
  - Order: the field checks (name, birth, consent, size), then the caps under the shared lock, then `INSERT … ON CONFLICT DO NOTHING`.
  - Each OK and each TAKEN writes one ledger row. A refusal raises, rolls back and writes nothing.
  - `auth.register` raises `RegistrationTaken` after the commit, so the TAKEN row stays.
- **`ew_register`.**
  - The body is 0005's, plus the size check and the size column; the cap now comes from `ew_registration_blocker('CODE')`, and an OK writes `(CODE, OK)`.
  - **Its signature changes** (a new last argument, `p_size`). So the old 7-argument function is dropped, not replaced, and the new one gets the same REVOKE/GRANT that 0005 gave the old one.
  - This leaves no route that can create an account without a size, and a check proves the old signature is gone.
- **`ew_registration_blocker(p_via)`** is shared by both register functions and by `ew_open_registration_blocker()`. The availability check therefore cannot disagree with the registration.
- **`users.ui_size`** is `text NULL` with `CHECK (ui_size IN ('COMPACT', 'GAZE'))` (`ui_size_known`).
  - NULL means "not chosen yet". It is not a default. Existing and invited accounts are asked at their next sign-in (§8.7) rather than silently shrunk or kept large.
  - The web role has no grant on the column. `ew_my_ui_size()` reads the session user's own value, and `ew_set_my_ui_size(p_size)` sets it for the session user only.
  - It is never sent to the model (§9.2).
- **Consent to a newer notice.**
  - `ew_my_terms_version()` returns the version the session user accepted, or NULL for an invited account.
  - `ew_accept_terms(p_version)` records a newer version, with `terms_accepted_at = now()`, for the session user only. It refuses NULL (`registration_needs_consent`) and refuses to go backwards (`terms_version_backwards`).
  - The database does not know the current version. The server passes its own `TERMS_VERSION` and is the gate (§7.10).
- **Columns for new accounts.**
  - `users.open_registered`, with `CHECK (NOT open_registered OR self_registered)`.
  - `generation_attempts.new_account`, written only by `ew_begin_generation`.
  - `attempt_tombstones.new_account`, copied by `ew_attempt_tombstone`.
- **Replaced in place (`CREATE OR REPLACE`, so their privileges carry over):** `ew_attempt_tombstone`, `ew_campaign_insert_guard` and `ew_begin_generation`. Each is 0005's body plus the marked lines.
- **Grants.**
  - `REVOKE ALL … FROM PUBLIC` on all ten new functions, including the new `ew_register`.
  - `GRANT EXECUTE` to `eyework_app` on eight of them: `ew_register`, `ew_register_open`, `ew_open_registration_blocker`, `ew_my_generation_limit`, `ew_my_ui_size`, `ew_set_my_ui_size`, `ew_my_terms_version` and `ew_accept_terms`.
  - `ew_new_open_account` and `ew_registration_blocker` are called only by owner functions.
- **Down.**
  1. It locks `users` and refuses while any `open_registered` account exists, with a HINT.
  2. It drops the 8-argument `ew_register`, recreates 0005's 7-argument one with 0005's exact text and grants, and restores the three replaced functions word for word.
  3. It drops the new functions, the `ui_size` column, the new-account columns and the ledger.
  - The down is generated from main's 0005 by `scripts/build_down.py`, not retyped.
  - Consent versions accepted through `ew_accept_terms` stay. They are valid 0006 values.

### 6.2 `NEXT_open_registration.up.sql` (exact)

```sql
-- ════════════════════════════════════════════════════════════════════════
-- NEXT_open_registration — التسجيل المفتوح بلا رابط، وطريقة الاستخدام
-- ════════════════════════════════════════════════════════════════════════
-- يُنشئ الزائر حسابه بلا رمزٍ من المشغّل حين يكون EYEWORK_REGISTRATION=open.
-- الوضع يقرّره الخادم: ew_register_open دالّةٌ مستقلّة لا يستدعيها في وضعي
-- code وclosed، وew_register برمزه باقٍ على شرطه: لا حساب به بلا رمزٍ صالح.
--
-- ما تضمنه القاعدة في الطريقين: لا يُستولى على بريدٍ قائم (ولا على دعوةٍ لم
-- تُفعَّل)، والاسم والتاريخ والموافقة والمهنة وطريقة الاستخدام تُفحص قبل الإدراج،
-- وسقوفٌ يومية للحسابات الجديدة لا يُفرغها حذف.
--
-- **دفتر التسجيل.** صفٌّ لكل تسجيلٍ نجح، ولكل جواب «البريد مأخوذ» بلا رمز:
-- وقته وطريقه ونتيجته فقط — لا حساب ولا بريد ولا عنوان. منه تُعدّ السقوف، فلا
-- يُفرغها حذف الحساب، ويحذفه purge بعد يومه.
--
-- **الحساب المفتوح الجديد** (open_registered، في أيامه السبعة الأولى): عشرة
-- طلبات كتابةٍ في اليوم بدل أربعين، وأربعمئة في اليوم للحسابات الجديدة كلّها
-- من ألفي التطبيق، وثلاث حملاتٍ مفتوحة بدل عشرين. فحساباتٌ تُنشأ بالجملة لا
-- تستنفد ما لأصحاب الحسابات القائمة، ولا تملأ القرص بالصور.
--
-- **طريقة الاستخدام** (ui_size): باللمس (COMPACT) أو بتتبّع العين (GAZE)،
-- يختارها صاحب الحساب ويغيّرها بنفسه. فارغةٌ حتى يختار: الحسابات القائمة وحسابات
-- الدعوة تُسأل عند دخولها التالي، والتسجيل لا يتمّ بدونها.
--
-- **الموافقة على النسخة الجديدة.** من وافق على نسخةٍ أقدم من «قبل أن تبدأ»، أو لم
-- يوافق قطّ، يوافق على الحالية لحسابه وحده قبل أن يُرسَل له شيء (ew_accept_terms).
-- ════════════════════════════════════════════════════════════════════════

-- ── دفتر التسجيل ────────────────────────────────────────────────────────
CREATE TABLE registration_ledger (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    via         text NOT NULL CONSTRAINT registration_ledger_via CHECK (via IN ('CODE', 'OPEN')),
    outcome     text NOT NULL CONSTRAINT registration_ledger_outcome CHECK (outcome IN ('OK', 'TAKEN')),
    -- «مأخوذ» برمزٍ يُعدّ على الرمز نفسه (0005)، فلا صفّ له هنا.
    CONSTRAINT registration_ledger_taken_is_open CHECK (outcome = 'OK' OR via = 'OPEN')
);
CREATE INDEX registration_ledger_time ON registration_ledger (occurred_at);
ALTER TABLE registration_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE registration_ledger FORCE  ROW LEVEL SECURITY;
CREATE POLICY registration_ledger_owner_access ON registration_ledger FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- ما كان سقف 0005 يعدّه في آخر يوم: الرموز المستعملة، ومنها ما حُذف حسابه.
INSERT INTO registration_ledger (occurred_at, via, outcome)
SELECT used_at, 'CODE', 'OK' FROM signup_codes WHERE used_at > now() - interval '24 hours';

-- ── الحساب المفتوح ──────────────────────────────────────────────────────
-- أنشأه صاحبه بلا رابط: لا مشغّل يعرفه، فله حدودٌ أضيق في أسبوعه الأول.
ALTER TABLE users ADD COLUMN open_registered boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD CONSTRAINT open_registered_is_self_registered
    CHECK (NOT open_registered OR self_registered);

-- المحاولة تحمل أنها من حسابٍ جديد، وأثرها بعد الحذف كذلك: حصّة الحسابات
-- الجديدة لا يُفرغها حذفُ حسابٍ بعد استهلاك.
ALTER TABLE generation_attempts ADD COLUMN new_account boolean NOT NULL DEFAULT false;
ALTER TABLE attempt_tombstones  ADD COLUMN new_account boolean NOT NULL DEFAULT false;

-- ── طريقة الاستخدام ─────────────────────────────────────────────────────
-- COMPACT: باللمس، بأهدافٍ لا تصغر عن 44 نقطة. GAZE: بتتبّع العين، أهدافٌ 72px
-- وبينها 24px. لا افتراض: من لم يختر بعد يُسأل، والواجهة قبل جوابه بالحجم الكبير
-- لأنه يصلح للطريقتين. ولا تُرسَل إلى مزوّد النموذج أبداً.
ALTER TABLE users ADD COLUMN ui_size text
    CONSTRAINT ui_size_known CHECK (ui_size IN ('COMPACT', 'GAZE'));

-- طريقة صاحب الجلسة وحده، أو NULL إن لم يختر بعد.
CREATE FUNCTION ew_my_ui_size() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ui_size FROM users WHERE id = ew_current_user() AND is_active
$$;

-- يغيّرها صاحب الجلسة لحسابه وحده: الحساب من الجلسة، لا من معامل.
CREATE FUNCTION ew_set_my_ui_size(p_size text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'ui_size_known';
    END IF;
    UPDATE users SET ui_size = p_size WHERE id = ew_current_user() AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
END
$$;

-- ── الموافقة على نسخةٍ أحدث من «قبل أن تبدأ» ────────────────────────────
-- نسخةٌ جديدة تسمّي ما يُرسَل في كل بوابة، فمن وافق على أقدم منها — أو لم يوافق
-- قطّ، كحساب الدعوة — يوافق عليها عند دخوله التالي قبل أن يُرسَل له شيء. والخادم
-- يقارن النسخة بنسخته الحالية (القاعدة لا تعرفها) ويرفض ما يُرسَل إلى النموذج قبلها.
CREATE FUNCTION ew_my_terms_version() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT terms_version FROM users WHERE id = ew_current_user() AND is_active
$$;

-- الخادم يمرّر نسخته الحالية وحدها. ولا رجوع إلى نسخةٍ أقدم ممّا وافق عليه صاحبه.
CREATE FUNCTION ew_accept_terms(p_version text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    accepted text;
BEGIN
    IF p_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    SELECT terms_version INTO accepted FROM users WHERE id = ew_current_user() AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF accepted > p_version THEN
        RAISE EXCEPTION 'older' USING ERRCODE = 'check_violation', CONSTRAINT = 'terms_version_backwards';
    END IF;
    UPDATE users SET terms_version = p_version, terms_accepted_at = now() WHERE id = ew_current_user();
END
$$;

-- حسابٌ مفتوحٌ عمره دون سبعة أيام. تستدعيها دوالّ المالك وحدها.
CREATE FUNCTION ew_new_open_account(p_user uuid) RETURNS boolean
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT coalesce((SELECT open_registered AND created_at > now() - interval '7 days'
                       FROM users WHERE id = p_user), false)
$$;

-- ما يمنع تسجيلاً بهذا الطريق الآن، باسم قيده، أو NULL. من الدفتر وحده.
CREATE FUNCTION ew_registration_blocker(p_via text) RETURNS text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT CASE
        WHEN count(*) FILTER (WHERE outcome = 'OK') >= 200 THEN 'registration_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'OK') >= 150
            THEN 'registration_open_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'TAKEN') >= 60
            THEN 'registration_open_paused'
    END
      FROM registration_ledger
     WHERE occurred_at > now() - interval '24 hours'
$$;

-- تسألها الواجهة قبل الخطوة الأولى من التسجيل المفتوح، فلا يكتب أحدٌ عشر شاشاتٍ
-- بالنظر ليسمع في آخرها أن اليوم اكتمل. حالُ التطبيق كلّه، لا شيء عن أحد.
CREATE FUNCTION ew_open_registration_blocker() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_registration_blocker('OPEN')
$$;

-- ── التسجيل برمز: كما في 0005، ومعه طريقة الاستخدام، والسقف من الدفتر ─────
-- التوقيع يتغيّر (p_size)، فتُسقط القديمة: لا يبقى طريقٌ يُنشئ حساباً بلا طريقة.
DROP FUNCTION ew_register(bytea, bytea, text, text, date, text, text);
CREATE FUNCTION ew_register(
    p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text, p_size text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid;
    code    signup_codes%ROWTYPE;
    blocker text;
BEGIN
    SELECT * INTO code FROM signup_codes WHERE code_hash = p_code FOR UPDATE;
    IF NOT FOUND OR code.used_at IS NOT NULL OR code.expires_at <= now() OR code.taken_count >= 3 THEN
        RETURN QUERY SELECT NULL::uuid, 'CODE'::text;
        RETURN;
    END IF;
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_ui_size';
    END IF;
    -- قفلٌ واحد للطريقين: تسجيلان متزامنان لا يريان العدّ نفسه فيمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('CODE');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       ui_size, self_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession,
            p_size, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    INSERT INTO registration_ledger (via, outcome) VALUES ('CODE', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- ── التسجيل المفتوح ─────────────────────────────────────────────────────
-- النتيجة: (الحساب، 'OK') أو (NULL، 'TAKEN') لبريدٍ مأخوذ — وهذه تُكتب في الدفتر،
-- وستّون منها في يومٍ توقف التسجيل المفتوح كلّه: لا يصير أداة سؤالٍ عن الناس.
-- السقوف تُفحص قبل الإدراج، فالجواب عند امتلائها واحدٌ لكل بريد.
CREATE FUNCTION ew_register_open(
    p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text,
    p_terms_version text, p_size text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid;
    blocker text;
BEGIN
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    IF p_size IS NULL THEN
        RAISE EXCEPTION 'size' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_ui_size';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('OPEN');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       ui_size, self_registered, open_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession,
            p_size, true, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'TAKEN');
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- حدّ طلبات الكتابة اليومي لصاحب الجلسة وحده: 10 لحسابٍ مفتوحٍ جديد، و40 لغيره.
CREATE FUNCTION ew_my_generation_limit() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT CASE WHEN ew_new_open_account(id) THEN 10 ELSE 40 END
      FROM users WHERE id = ew_current_user() AND is_active
$$;

-- ── أثر المحاولة المحذوفة يحمل أنها من حسابٍ جديد ───────────────────────
CREATE OR REPLACE FUNCTION ew_attempt_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;

-- ── ثلاث حملاتٍ مفتوحة للحساب المفتوح الجديد ────────────────────────────
CREATE OR REPLACE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل):
    -- إمّا تنتظره الحملة فتُرفض بالمهنة الجديدة، وإمّا ينتظرها فيلغيها.
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    IF ew_new_open_account(NEW.user_id)
       AND (SELECT count(*) FROM campaigns
             WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 3 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'new_account_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

-- ── حدود الكتابة للحساب المفتوح الجديد ──────────────────────────────────
CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
    fresh   boolean;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- الكلفة تُفرض حيث تقع: حسابٌ نُقل إلى مهنةٍ أخرى لا يكتب لحملةٍ قديمة.
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    SELECT * INTO c FROM campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_kind NOT IN ('INITIAL','EDIT')
       OR (p_kind = 'INITIAL' AND (c.status <> 'DRAFT' OR p_expected_version IS NOT NULL))
       OR (p_kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED' OR c.current_version_id IS DISTINCT FROM p_expected_version)) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_wrong_state';
    END IF;
    SELECT sha256 INTO image FROM campaign_images WHERE campaign_id = p_campaign;
    IF image IS NULL THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_needs_image';
    END IF;
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE user_id = uid AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_in_progress';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_rate';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 40 THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- الحساب المفتوح الجديد: عشرة في اليوم. وقفل صفّ المستخدم أعلاه يجعل العدّ والإدراج ذرّيين.
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256, new_account)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image, fresh)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

-- ── المنح ───────────────────────────────────────────────────────────────
-- الدفتر بلا منح ولا سياسةٍ لدور الويب. ew_new_open_account وew_registration_blocker
-- تستدعيهما دوالّ المالك بصلاحيته؛ دور الويب لا يحتاجهما. وطريقة الاستخدام لا منح
-- على عمودها: تُقرأ وتُكتب لصاحب الجلسة عبر دالّتيها وحدهما.
REVOKE ALL ON FUNCTION ew_new_open_account(uuid), ew_registration_blocker(text),
                       ew_open_registration_blocker(),
                       ew_register(bytea, bytea, text, text, date, text, text, text),
                       ew_register_open(bytea, text, text, date, text, text, text),
                       ew_my_generation_limit(),
                       ew_my_ui_size(), ew_set_my_ui_size(text),
                       ew_my_terms_version(), ew_accept_terms(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_open_registration_blocker(),
                          ew_register(bytea, bytea, text, text, date, text, text, text),
                          ew_register_open(bytea, text, text, date, text, text, text),
                          ew_my_generation_limit(),
                          ew_my_ui_size(), ew_set_my_ui_size(text),
                          ew_my_terms_version(), ew_accept_terms(text) TO eyework_app;
```

### 6.3 `NEXT_open_registration.down.sql` (exact)

```sql
-- ════════════════════════════════════════════════════════════════════════
-- NEXT_open_registration — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- 0005 يضمن ألّا حساب يُسجَّل بلا رمز. حسابٌ مفتوح بعد التراجع يخالف ما يصفه
-- مخطّطه، ويفقد حدود أسبوعه الأول بصمت. فلا تراجع وفي القاعدة واحدٌ منه. والقفل
-- أولاً: تسجيلٌ لم يُثبَّت بعد لا يراه العدّ، فينتظره التراجع ثم يعدّه.
-- وطريقة الاستخدام تُسقط مع عمودها: الواجهة قبلها بالحجم الكبير للجميع.
LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE
    n integer;
BEGIN
    SELECT count(*) INTO n FROM users WHERE open_registered;
    IF n > 0 THEN
        RAISE EXCEPTION 'في القاعدة % حساباً مسجَّلاً بلا رابط لا يصفه مخطّط 0006', n
            USING HINT = 'البريد لا يُخزَّن فلا يجدها delete-user؛ تُحذف بدور المالك: '
                         'DELETE FROM users WHERE open_registered';
    END IF;
END
$$;

-- ew_register كما كانت في 0005، حرفاً بحرف، بمنحها.
DROP FUNCTION IF EXISTS ew_register(bytea, bytea, text, text, date, text, text, text);
CREATE FUNCTION ew_register(
    p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid;
    code signup_codes%ROWTYPE;
BEGIN
    SELECT * INTO code FROM signup_codes WHERE code_hash = p_code FOR UPDATE;
    IF NOT FOUND OR code.used_at IS NOT NULL OR code.expires_at <= now() OR code.taken_count >= 3 THEN
        RETURN QUERY SELECT NULL::uuid, 'CODE'::text;
        RETURN;
    END IF;
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    -- قفلٌ واحد للجميع: بلا هذا يرى تسجيلان متزامنان العدَّ نفسه ويمرّان معاً.
    -- والعدّ من الرموز المستعملة لا من الحسابات: الحساب يُحذف بيد صاحبه، والرمز
    -- يبقى مستعملاً (user_id يصير NULL)، فلا يُفرغ الحذفُ السقفَ.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    IF (SELECT count(*) FROM signup_codes WHERE used_at > now() - interval '24 hours') >= 200 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_daily_cap';
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;
REVOKE ALL ON FUNCTION ew_register(bytea, bytea, text, text, date, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_register(bytea, bytea, text, text, date, text, text) TO eyework_app;

-- والثلاث التي استُبدلت، كما كانت في 0005، حرفاً بحرف.
CREATE OR REPLACE FUNCTION ew_attempt_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome) VALUES (OLD.started_at, OLD.outcome);
    END IF;
    RETURN OLD;
END
$$;

CREATE OR REPLACE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل):
    -- إمّا تنتظره الحملة فتُرفض بالمهنة الجديدة، وإمّا ينتظرها فيلغيها.
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- الكلفة تُفرض حيث تقع: حسابٌ نُقل إلى مهنةٍ أخرى لا يكتب لحملةٍ قديمة.
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    SELECT * INTO c FROM campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_kind NOT IN ('INITIAL','EDIT')
       OR (p_kind = 'INITIAL' AND (c.status <> 'DRAFT' OR p_expected_version IS NOT NULL))
       OR (p_kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED' OR c.current_version_id IS DISTINCT FROM p_expected_version)) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_wrong_state';
    END IF;
    SELECT sha256 INTO image FROM campaign_images WHERE campaign_id = p_campaign;
    IF image IS NULL THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_needs_image';
    END IF;
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE user_id = uid AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_in_progress';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_rate';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 40 THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

DROP FUNCTION IF EXISTS ew_accept_terms(text);
DROP FUNCTION IF EXISTS ew_my_terms_version();
DROP FUNCTION IF EXISTS ew_set_my_ui_size(text);
DROP FUNCTION IF EXISTS ew_my_ui_size();
DROP FUNCTION IF EXISTS ew_my_generation_limit();
DROP FUNCTION IF EXISTS ew_register_open(bytea, text, text, date, text, text, text);
DROP FUNCTION IF EXISTS ew_open_registration_blocker();
DROP FUNCTION IF EXISTS ew_registration_blocker(text);
DROP FUNCTION IF EXISTS ew_new_open_account(uuid);

ALTER TABLE users DROP COLUMN IF EXISTS ui_size;
ALTER TABLE attempt_tombstones  DROP COLUMN IF EXISTS new_account;
ALTER TABLE generation_attempts DROP COLUMN IF EXISTS new_account;
ALTER TABLE users DROP CONSTRAINT IF EXISTS open_registered_is_self_registered;
ALTER TABLE users DROP COLUMN IF EXISTS open_registered;

DROP TABLE IF EXISTS registration_ledger;
```

### 6.4 Verified on PostgreSQL 16 (`reg_v2_test`, dropped afterwards)

- **Cycle** (`scripts/cycle.sh`, the repo's runner from a worktree of `d543356`).
  - 0001–0006 up; NEXT up; down to 0006; up again; then down `--all` and up from empty.
  - Down restores 0006 identically. The second up and the up from empty both match the first, with byte-identical `pg_dump --schema-only`.
- **29 functional checks as `eyework_app`** (`scripts/check_next.py`, 29/29). The previous run's 20, with the new signatures:
  - creation and its ledger row;
  - no takeover of a login or a pending invitation;
  - the field checks, with no ledger row on refusal;
  - the open cap, the total cap, and that deletion makes no room;
  - the pause, while links still work;
  - availability;
  - a code TAKEN counting only on the code;
  - every web-role denial;
  - a ledger with no identity;
  - two concurrent registrations serialised on the lock;
  - the 10/40/NULL limit;
  - the new-account daily cap, and 40 after a week;
  - the pool of 400, counting a deleted account's traces;
  - the 3-campaign cap;
  - `open_registered ⇒ self_registered`.
- **Plus 9 new checks:**
  - both routes store the chosen size, refuse NULL by name and refuse an unknown value, with no ledger row;
  - the 7-argument `ew_register` no longer exists;
  - existing and invited accounts have NULL, and `ew_my_ui_size` returns only the session user's value;
  - `ew_set_my_ui_size` changes the session user's row only, and refuses NULL and unknown values by name;
  - with no session it raises `insufficient_privilege`, and the same for an inactive user;
  - the web role cannot SELECT or UPDATE `ui_size` directly;
  - `ew_accept_terms` changes only the session user's row, is idempotent, refuses to go backwards, refuses NULL, and raises with no session;
  - down refuses with an open account («1 حساباً مسجَّلاً بلا رابط» and the HINT) and the database stays at the new version; after the delete, down and up both succeed.
- **Main's database suite against the new schema** (`evidence/existing_db_suite.txt`). 572 pass and 23 fail, all accounted for in §10.2.
  - The checks that every function's `search_path` is pinned and that no function is executable by PUBLIC both pass.
- **The work-tools draft 0008 applies on top of NEXT** after its own parse error is fixed (§9.3 I), inside a rolled-back transaction.

---

## 7. Server changes

### 7.1 `config.py`

```python
REGISTRATION_MODES = ("open", "code", "closed")
_CONTACT = re.compile(r"^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")

@dataclass(frozen=True, slots=True)
class Settings:
    app_database_url: str
    login_key: bytes
    anthropic_api_key: str | None
    public_origin: str
    #: open: «أنشئ حساباً» بلا رابط، وروابط المشغّل تعمل معه. code: برابط المشغّل وحده. closed: بالدعوة وحدها.
    registration: str = "open"
    #: بريد المشغّل الذي يكتب إليه من نسي كلمة مروره أو وجد بريده مأخوذاً. مطلوبٌ مع open (يفحصه load).
    support_contact: str | None = None


def _registration() -> str:
    value = os.environ.get("EYEWORK_REGISTRATION", "").strip().lower() or "open"
    if value not in REGISTRATION_MODES:
        raise ConfigError("EYEWORK_REGISTRATION يجب أن يكون open أو code أو closed")
    return value


def _support_contact(mode: str) -> str | None:
    """
    لا مشغّل يعرف صاحب حسابٍ أنشأه بلا رابط: هذا البريد طريقه الوحيد إليه. فالتسجيل
    المفتوح لا يُقلع بدونه، ونشرٌ قديم لا ينفتح تسجيله بصمتٍ حين يُحدَّث.
    """
    value = unicodedata.normalize("NFKC", os.environ.get("EYEWORK_SUPPORT_CONTACT", "")).strip().lower()
    if not value:
        if mode == "open":
            raise ConfigError("EYEWORK_SUPPORT_CONTACT مطلوبٌ مع EYEWORK_REGISTRATION=open"
                              " (أو اضبط EYEWORK_REGISTRATION=code)")
        return None
    if len(value) > 254 or not _CONTACT.match(value):
        raise ConfigError("EYEWORK_SUPPORT_CONTACT ليس بريداً صالحاً")
    return value
```

`load()` reads the mode once and passes `registration=mode, support_contact=_support_contact(mode)`. The field `registration_open: bool` is removed, and callers read `settings.registration`.

### 7.2 `eyework/ui_size.py` (new)

```python
"""
طريقة الاستخدام
===============
باللمس (COMPACT) أو بتتبّع العين (GAZE). يختارها صاحب الحساب عند التسجيل أو عند
دخوله الأول، ويغيّرها من «حسابي». تُحفظ مع حسابه (users.ui_size) ولا تُرسَل إلى
مزوّد النموذج أبداً. والواجهة لا تخمّنها من الجهاز: تسأل.
"""
from enum import StrEnum


class UiSize(StrEnum):
    COMPACT = "COMPACT"
    GAZE = "GAZE"


#: الاسم وسطرٌ يشرحه، كما تعرضهما خطوة «كيف تستخدم الجهاز؟» وشاشة «حسابي».
CHOICES: dict[UiSize, tuple[str, str]] = {
    UiSize.COMPACT: ("باللمس", "أزرارٌ وخطٌّ بالحجم المعتاد."),
    UiSize.GAZE: ("بتتبّع العين", "أزرارٌ أكبر بينها مسافات، تُضغط بالنظر."),
}
```

Database test 25 (§10.1) checks that `UiSize` and the CHECK `ui_size_known` list the same values.

### 7.3 `eyework/terms.py` (new): the notice as data

- **Why move the notice.** Until now its text lived in `static/index.html`, and `test_terms.py` hashed the HTML.
  - The React client replaces that page, and the notice now has one line per workspace, supplied by other tracks.
  - So the server holds the text, serves it in `/api/choices`, and hashes it in Python.
- **Effects.**
  - The client renders exactly the version the server records, and there is one source of truth.
  - The client sends back the `terms_version` it displayed. A deploy between reading and creating the account is caught (409 `REGISTER_TERMS`, §7.7).

```python
"""
«قبل أن تبدأ»: نصّه ونسخته
===========================
ما يوافق عليه صاحب الحساب: ما يُحفظ هنا، وما يُرسَل إلى مزوّد النموذج في كل بوابة.
النصّ هنا وحده، يخدمه /api/choices وتعرضه الواجهة كما هو، فلا يختلف ما يُقرأ عمّا
يُحفظ. ولكل نسخةٍ بصمة نصّها (tests/unit/test_terms.py): تغيير حرفٍ يُفشل الاختبار
حتى تُرفع النسخة.

النسخة تاريخ سريانها. ومن وافق على أقدم منها يوافق على الحالية عند دخوله التالي،
قبل أن يُرسَل له شيء (web/deps.require_current_terms).
"""
import re

from eyework.professions import Profession

#: تاريخ إصدار هذا النصّ (YYYY-MM-DD)، بعد كل نسخةٍ في DIGESTS. يُضبط عند الإصدار (المواصفة §9.4).
TERMS_VERSION = "…"

KEPT: tuple[str, ...] = (…)          # §9.2، حرفاً بحرف
SENT_INTRO = "…"                      # §9.2
#: سطرٌ لكل بوابة (Profession)، أو لكل البوابات (None). يكتبه مسار البوابة (§9.3).
SENT: tuple[tuple[Profession | None, str], ...] = (…)
SENT_OUTRO = "…"                      # §9.2


def notice() -> dict:
    return {
        "version": TERMS_VERSION,
        "kept": list(KEPT),
        "sent": {
            "intro": SENT_INTRO,
            "items": [{"scope": scope.value if scope else "ALL", "text": text} for scope, text in SENT],
            "outro": SENT_OUTRO,
        },
    }


def normalized_text() -> str:
    """النصّ كلّه بترتيب عرضه، بمسافاتٍ موحّدة: ما تُحسب بصمته."""
    parts = [*KEPT, SENT_INTRO, *(text for _, text in SENT), SENT_OUTRO]
    return "\n".join(re.sub(r"\s+", " ", part).strip() for part in parts)
```

The notice shows every workspace's line to every user, whatever the chosen profession.

- The operator can move an account to another profession (`admin set-profession`), and one version must be true for every account.
- Showing only the chosen profession's line would need a new consent on every profession change.

### 7.4 `auth.py`

- **New SQL constants.**
  - `_REGISTER = "SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s, %s)"`, now with 8 arguments.
  - `_REGISTER_OPEN = "SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s, %s)"`
  - `_OPEN_BLOCKER = "SELECT ew_open_registration_blocker() AS blocker"`
  - `_UI_SIZE = "SELECT ew_my_ui_size() AS ui_size"` and `_SET_UI_SIZE = "SELECT ew_set_my_ui_size(%s)"`
  - `_TERMS = "SELECT ew_my_terms_version() AS version"` and `_ACCEPT_TERMS = "SELECT ew_accept_terms(%s)"`
- **`TERMS_VERSION`** is re-exported from `terms` (`from eyework.terms import TERMS_VERSION`), so existing imports keep working.
- **`register(db, key, *, code: str | None, name, birth_date, email, password, profession, ui_size: UiSize)`.**
  - With `code is None` it calls `_REGISTER_OPEN` with `(login_hmac(key, email), password_hash, name, birth_date, profession.value, TERMS_VERSION, ui_size.value)`.
  - Otherwise it calls `_REGISTER` with the code first and `ui_size.value` last.
  - The scrypt hash is computed before the database call. The exception is raised after the `with` block, which keeps the TAKEN ledger row.
- **New functions.**
  - `open_registration_blocker(db) -> str | None`.
  - `ui_size_of(db, user_id) -> UiSize | None` and `set_ui_size(db, user_id, ui_size)`.
  - `terms_version_of(db, user_id) -> str | None` and `accept_terms(db, user_id)`, which passes `TERMS_VERSION` and nothing else.
- **Docstrings.**
  - The module paragraph «حسابٌ بالتسجيل أو بالدعوة» adds the third route.
  - `RegistrationTaken` says it is counted on the code, or in the ledger and the network budget.

### 7.5 `campaigns.py`

```python
#: نظيرا ew_begin_generation وew_my_generation_limit. اختبارٌ يقارنهما بالقاعدة.
DAILY_GENERATIONS = 40
NEW_ACCOUNT_DAILY_GENERATIONS = 10
_LIMIT = "SELECT ew_my_generation_limit() AS daily"

def generation_allowance(db: Database, user_id: UUID) -> tuple[int, int]:
    """(حدّ اليوم، وما بقي منه) لصاحب الجلسة، كما يعدّهما ew_begin_generation."""
    with db.session(user_id) as cursor:
        cursor.execute(_LIMIT)
        daily = cursor.fetchone()["daily"] or 0
        cursor.execute(_REMAINING)
        used = cursor.fetchone()["used"]
    return daily, max(0, daily - used)
```

`remaining_generations` is removed. Its only caller, `/api/me`, uses `generation_allowance` instead.

### 7.6 `rate_limit.py` (stays pure)

```python
    def blocked(self, key: str) -> float | None:
        """ثوانٍ حتى يفرغ مكانٌ لهذا المفتاح، أو None إن كان فيه مكان. لا يسجّل شيئاً."""
        timestamp = monotonic()
        cutoff = timestamp - self._limit.window_seconds
        with self._lock:
            window = self._events.get(key)
            while window and window[0] <= cutoff:
                window.popleft()
            if not window or len(window) < self._limit.max_events:
                return None
            return window[0] + self._limit.window_seconds - timestamp

    def record(self, key: str) -> None:
        """يسجّل حدثاً بلا فحص: لما يُعدّ بعد وقوعه (جواب «البريد مأخوذ»)."""
        timestamp = monotonic()
        with self._lock:
            if len(self._events) > _SWEEP_ABOVE:
                self._sweep(timestamp - self._limit.window_seconds)
            self._events.setdefault(key, deque()).append(timestamp)
```

### 7.7 `web/errors.py`

```python
# REGISTRATION (field → step)
"LINK_REQUIRED": ErrorSpec(403, "REGISTER_LINK", "التسجيل هنا برابطٍ ممّن يدير التطبيق. اطلبه منه."),
"UI_SIZE": ErrorSpec(422, "REGISTER_INVALID", "اختر كيف تستخدم الجهاز: باللمس أو بتتبّع العين."),
"TERMS": ErrorSpec(409, "REGISTER_TERMS", "تغيّر نصّ «قبل أن تبدأ» منذ قرأته. اقرأه من جديد، ثم وافق."),

# REGISTRATION_CONSTRAINTS (constraint → field)
"registration_needs_ui_size": "UI_SIZE",
"ui_size_known": "UI_SIZE",

# CONSTRAINTS
"registration_open_daily_cap": ErrorSpec(503, "REGISTER_FULL",
                                         "اكتمل عدد الحسابات الجديدة لهذا اليوم. حاول غداً.", 3600),
"registration_open_paused": ErrorSpec(503, "REGISTER_PAUSED", "إنشاء الحسابات متوقّفٌ مؤقتاً. حاول غداً.", 3600),
"generation_new_account_cap": ErrorSpec(429, "AI_NEW_DAILY",
                                        "للحساب الجديد عشرة طلبات كتابةٍ في اليوم خلال أسبوعه الأول. حاول غداً.", 3600),
"generation_new_accounts_cap": ErrorSpec(503, "AI_NEW_BUSY",
                                         "بلغت الحسابات الجديدة حدّها من طلبات الكتابة اليوم. حاول غداً.", 3600),
"new_account_campaign_cap": ErrorSpec(409, "NEW_OPEN_CAP",
                                      "للحساب الجديد ثلاث حملاتٍ مفتوحة في أسبوعه الأول. أكمل إحداها أو ألغِها أولاً."),
"terms_version_backwards": ErrorSpec(409, "TERMS_STALE", "وافقتَ على نسخةٍ أحدث من هذه. أعد تحميل الصفحة."),

# Not a constraint: the consent gate (§7.10)
TERMS_REQUIRED = ErrorSpec(403, "TERMS", "تغيّر ما يُرسَل إلى Anthropic منذ وافقت. اقرأه ووافق عليه أولاً.")
```

- The existing `registration_daily_cap` entry is unchanged.
- Every new constraint reaches the existing `IntegrityError` handler by name. That handler logs only the constraint name and the path.

### 7.8 `web/schemas.py`

```python
TermsVersion = Annotated[StrictStr, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]

class RegisterBody(_Body):
    """… الرمز غائبٌ في التسجيل المفتوح. والنسخة ما عُرض على صاحب الطلب: إن تغيّرت منذ عرضها فلا حساب."""
    code: SignupCode | None = None
    name: Annotated[StrictStr, Field(min_length=1, max_length=60)]
    birth_date: Annotated[StrictStr, Field(min_length=10, max_length=10)]
    email: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=EMAIL_MAX)]
    password: Annotated[StrictStr, Field(min_length=1, max_length=PASSWORD_MAX)]
    profession: Profession
    ui_size: UiSize
    accept_terms: Literal[True]
    terms_version: TermsVersion


class UiSizeBody(_Body):
    ui_size: UiSize


class TermsBody(_Body):
    #: ما عُرض ووافق عليه: يُقبل إن كان النسخة الحالية وحدها.
    terms_version: TermsVersion
```

`extra="forbid"` stays on every body.

### 7.9 `web/deps.py`

```python
    #: التسجيل بلا رابط لكل شبكة (عنوان IPv4، أو /64 من IPv6): خمسٌ في الساعة، وعشرٌ في اليوم.
    register_open_net: RateLimiter
    register_open_net_day: RateLimiter
    #: أجوبة «البريد مأخوذ» بلا رابط لكل شبكة: ثلاثٌ في اليوم ثم لا جواب — نظير قفل الرمز بعد ثلاث.
    taken_open_net: RateLimiter
    #: «هل يُنشأ حسابٌ بلا رابطٍ الآن؟» قبل الخطوة الأولى.
    registration_check_net: RateLimiter
    #: تغيير طريقة الاستخدام، والموافقة على نسخةٍ جديدة: لكل حساب.
    ui_size_user: RateLimiter
    terms_user: RateLimiter
    # default():
    #   register_open_net=RateLimiter(RateLimit(5, 3600.0)),
    #   register_open_net_day=RateLimiter(RateLimit(10, 86400.0)),
    #   taken_open_net=RateLimiter(RateLimit(3, 86400.0)),
    #   registration_check_net=RateLimiter(RateLimit(30, 3600.0)),
    #   ui_size_user=RateLimiter(RateLimit(30, 3600.0)),
    #   terms_user=RateLimiter(RateLimit(10, 3600.0)),


def client_network(request: Request) -> str:
    """
    العنوان IPv4 نفسه، أو الـ/64 من IPv6: الهاتف على شبكة IPv6 يغيّر عنوانه داخلها
    متى شاء، فالحدّ لكل عنوانٍ منها لا يحدّ شيئاً. وIPv4 المغلَّف في IPv6 هو عنوانه.
    """
    host = client_ip(request)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if address.version == 6:
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def refuse_if_full(limiter: RateLimiter, key: str) -> None:
    """429 كـenforce إن لم يبقَ مكان، ولا يسجّل شيئاً."""
    wait = limiter.blocked(key)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE", "detail": "طلباتٌ كثيرة. حاول بعد قليل."},
            headers={"Retry-After": str(int(wait) + 1)},
        )
```

### 7.10 The consent gate: `require_current_terms`

```python
def require_current_terms(request: Request, user_id: UUID = Depends(require_user)) -> UUID:
    """
    لا يُرسَل شيءٌ لصاحب الجلسة إلى مزوّد النموذج قبل أن يوافق على النسخة الحالية من
    «قبل أن تبدأ». من وافق على أقدم — أو لم يوافق قطّ، كحساب الدعوة — يُردّ إلى الموافقة.
    """
    accepted = auth.terms_version_of(request.app.state.db, user_id)
    # أحدث من الحالية يكفي: بعد تراجعٍ عن إصدار لا يُحبس من وافق على الأحدث، والقاعدة
    # لا تقبل الرجوع إلى أقدم (terms_version_backwards). والتواريخ YYYY-MM-DD تُقارن نصّاً.
    if accepted is None or accepted < terms.TERMS_VERSION:
        spec = TERMS_REQUIRED
        raise HTTPException(spec.status, detail={"code": spec.code, "detail": spec.detail})
    return user_id
```

- **Where it applies.** It is a dependency of every route that sends anything to the model.
  - Today: `POST /api/campaigns/{id}/copy` and `POST /api/campaigns/{id}/copy/edit`.
  - Tomorrow: every model-calling route of the inventory, marketing and support tracks (§9.3, item D).
- **What it does not gate.** Routes that send nothing to the model: the workspace's own data, `/api/me*`, sign-out, deleting the account and passkeys. The client shows the consent screens before the workspace anyway (§8.7).
- **Why the server.** The database does not know the current version. The check is one indexed read per model call.
- **At or after, not equal.** If the code is rolled back to an older release, users who accepted the newer notice must not be locked out. They cannot accept the older one, because the database refuses to go backwards, so a newer accepted version counts as current.
- **Architecture test.** Every route whose handler reaches `state.copywriter`, or any other model client the tracks add, depends on `require_current_terms`.

### 7.11 `web/routes_auth.py`

```python
def _constraint_error(name: str) -> JSONResponse:
    spec = CONSTRAINTS[name]
    headers = {"Retry-After": str(spec.retry_after)} if spec.retry_after else None
    return JSONResponse(status_code=spec.status, headers=headers, content={"code": spec.code, "detail": spec.detail})


@router.get("/auth/registration", status_code=status.HTTP_204_NO_CONTENT)
async def registration(request: Request) -> Response:
    """
    هل يُنشأ حسابٌ بلا رابطٍ الآن؟ تسأله الواجهة قبل الخطوة الأولى، فلا يكتب أحدٌ إحدى عشرة
    شاشةً بالنظر ليسمع في آخرها أن اليوم اكتمل. حال التطبيق كلّه: لا بريد فيه ولا يقول شيئاً عن أحد.
    """
    state = request.app.state
    if state.settings.registration == "closed":
        return _registration_error("CLOSED")
    if state.settings.registration == "code":
        return _registration_error("LINK_REQUIRED")
    enforce(state.limiters.registration_check_net, client_network(request))
    blocker = await run_in_threadpool(auth.open_registration_blocker, state.db)
    return _constraint_error(blocker) if blocker else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/register", status_code=status.HTTP_204_NO_CONTENT)
async def register(body: RegisterBody, request: Request) -> Response:
    state = request.app.state
    mode = state.settings.registration
    if mode == "closed":
        return _registration_error("CLOSED")
    if body.code is None and mode != "open":
        return _registration_error("LINK_REQUIRED")
    # ما وافق عليه هو ما عُرض عليه: نسخةٌ تغيّرت منذ عرضها لا تُنشئ حساباً.
    if body.terms_version != terms.TERMS_VERSION:
        return _registration_error("TERMS")
    try:
        name = auth.check_name(body.name)
        birth_date = auth.check_birth_date(body.birth_date)
        email = auth.check_email(body.email)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    # الحدّ بعد فحص الشكل: خطأٌ في حقلٍ لا يمسّ القاعدة ولا يستهلك محاولة.
    limiters = state.limiters
    net = client_network(request) if body.code is None else None
    if net is None:
        enforce(limiters.register_ip, client_ip(request))
    else:
        for limiter in (limiters.register_open_net, limiters.register_open_net_day, limiters.taken_open_net):
            refuse_if_full(limiter, net)
        limiters.register_open_net.record(net)
        limiters.register_open_net_day.record(net)
    try:
        token = await run_in_threadpool(
            auth.register, state.db, state.settings.login_key, code=body.code, name=name,
            birth_date=birth_date, email=email, password=body.password, profession=body.profession,
            ui_size=body.ui_size)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    except auth.RegistrationCodeInvalid:
        return _registration_error("CODE")
    except auth.RegistrationTaken:
        if net is not None:
            limiters.taken_open_net.record(net)
        return _registration_error("TAKEN")
    previous = session_token(request)
    if previous:
        await run_in_threadpool(auth.logout, state.db, previous)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_session(response, token)
    return response


@router.put("/me/ui-size", status_code=status.HTTP_204_NO_CONTENT)
def set_ui_size(body: UiSizeBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """طريقة الاستخدام لصاحب الجلسة وحده. لا تحتاج موافقةً حالية: لا تُرسَل إلى أحد."""
    state = request.app.state
    enforce(state.limiters.ui_size_user, str(user_id))
    auth.set_ui_size(state.db, user_id, body.ui_size)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/terms", status_code=status.HTTP_204_NO_CONTENT)
def accept_terms(body: TermsBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """الموافقة على النسخة الحالية من «قبل أن تبدأ»، لمن وافق على أقدم أو لم يوافق قطّ."""
    state = request.app.state
    enforce(state.limiters.terms_user, str(user_id))
    if body.terms_version != terms.TERMS_VERSION:
        return _registration_error("TERMS")
    auth.accept_terms(state.db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**Order of checks on `POST /api/auth/register`, which matters for the enumeration guarantees:**

1. the mode;
2. the request schema (422 `INVALID`);
3. the terms version (409 `REGISTER_TERMS`);
4. the field checks (422 per field; no limiter is consumed);
5. the per-network limiters (429);
6. the database: the field checks again, then the caps and the pause (503, the same for every email), then the insert (409 TAKEN, or 204).

**Other routes.**

- `signup_code` tests `state.settings.registration == "closed"`.
- `GET /api/me` returns:

  ```json
  {"display_name": "…", "profession": "STOREKEEPER", "generations_left": 10, "generation_limit": 10,
   "ui_size": "GAZE", "terms_current": true}
  ```

  - `ui_size` is `null` until chosen.
  - `terms_current` is true when the accepted version is not NULL and is at or after `TERMS_VERSION`, the same rule as the gate (§7.10).
  - Neither the email nor the birth date is ever returned, as today.
- `GET /api/choices` adds:

  ```json
  {"registration": {"mode": "open", "name_max": 30, "password_min": 12, "earliest_year": 1900,
                    "terms_version": "…"},
   "registration_open": true,
   "support_contact": "help@example.sa",
   "ui_sizes": [{"code": "COMPACT", "name": "باللمس", "detail": "أزرارٌ وخطٌّ بالحجم المعتاد."},
                {"code": "GAZE", "name": "بتتبّع العين", "detail": "أزرارٌ أكبر بينها مسافات، تُضغط بالنظر."}],
   "notice": {"version": "…", "kept": ["…"], "sent": {"intro": "…", "items": [{"scope": "MARKETING", "text": "…"}],
                                                      "outro": "…"}}}
  ```

  - `registration_open` now means `mode != "closed"`.
  - `support_contact` is `null` unless set.

### 7.12 `admin.py`

- `purge` adds `("registration_ledger", "DELETE FROM registration_ledger WHERE occurred_at < now() - interval '24 hours'")`.
- **The docstring:**
  - names the open route;
  - keeps `--owner-verified` for self-registered accounts;
  - describes the squatting process (§4.4).
- **`create-user` is unchanged.** It sets no size and no consent; the invited person chooses both at first sign-in (§8.7).
- No new command. Pauses and full days show in the existing warning log («قيد registration_open_paused على /api/auth/register»).

### 7.13 Serving the React client, and retiring the static sign-up

- **Breaking change.** `RegisterBody` now requires `ui_size` and `terms_version`. This breaks the static client's sign-up, which sends neither.
- **Ordering.** These server changes land in the same release in which FastAPI starts serving the React client. That switch is the visual and client track's job, under the same CSP (`'self'` only).
- **What is removed with it.** The static client's sign-in, sign-up and notice markup (`static/index.html` sections `login`, `signup-*`) and their code in `app.js` and `portal.js`.
- **The probe** (`static/probe/`) is not affected.

### 7.14 Other server files

- `tests/conftest.py`: `_CLEAN = "TRUNCATE users, attempt_tombstones, registration_ledger RESTART IDENTITY CASCADE"`.
- **`README.md`:**
  - «التسجيل» covers three routes, the modes, `EYEWORK_SUPPORT_CONTACT`, the limits in §5 and the trade-off in §4.
  - It explains «طريقة الاستخدام» and the next-sign-in questions.
  - The retention table gets a row: «دفتر التسجيل (وقت كل تسجيلٍ وكل جواب «مأخوذ» بلا رابط، بلا هوية) — بعد 24 ساعة (`purge`)».
  - The paragraph «التسجيل المفتوح بلا رابط» under «ما لم يُبنَ» is removed.
  - «ما يُخزَّن عن الشخص» adds «وطريقة الاستخدام» and «وفي الوضع المفتوح يعرف من يحاول التسجيل ببريدٍ أن له حساباً».

---

## 8. Client (React, `eyework/client`)

### 8.1 Who owns what

- **The visual track owns** the screens' look, the components (21st.dev ports on shadcn/ui), the size tokens, the frame (top and bottom bars) and the landing attributes. The attributes are `data-commit` for what cannot be undone with one press, `data-value` for what changes a visible value in place, and `data-safe` for everything else (v2 `button.tsx`).
- **This track owns** the routes, the step order, the state and its rules, the requests, the error mapping, the copy below, and the consent and landing rules for these screens.
- Where the visual track's current draft conflicts with this spec, the conflict is named here (§8.5, §8.11).

### 8.2 The size, before and after sign-in

| Moment | Size shown | Source |
|---|---|---|
| Welcome, sign-in, activation, the two notice screens and the size step | the visual track's pre-account size: compact by default, large after «حجمٌ أكبر» | the visual track (`lib/size.tsx`), carried in the URL, never stored on the device |
| Sign-up steps after the size step | the size chosen at that step | `state.signup.ui_size`. «التالي» on the size step applies it and writes the visual track's URL parameter. |
| Signed in, `ui_size` set | the account's size | `GET /api/me` → `ui_size` |
| Signed in, `ui_size` is `null` | as before sign-in, until answered | the start sequence asks (§8.7) |

- **No guessing; the user confirms.**
  - The size step starts with the size the screen is shown in: the pre-account size, which the user set with «حجمٌ أكبر» or left as it was. «التالي» confirms it.
  - The app never infers the mode from the device or from behaviour.
- **No auto-apply on selection.** Selecting an option changes nothing on screen; only «التالي», or «طبّق» on «حسابي», applies the size. A selection that resized the whole screen under a resting gaze could flip back and forth under it. The visual draft already works this way.
- **A `null` size is not compact.** The draft `fromServer()` in v2 maps anything other than `GAZE` to `compact`, including `null`. It must keep `null` as "ask": the client routes to the start sequence (§8.7) and does not render the workspace.
- **The URL parameter must not say "gaze".** The draft writes `?size=gaze`.
  - A URL lands in Safari's history. On a shared device, "this browser's user uses eye tracking" is the same health information the app refuses to keep in storage.
  - Use a neutral value such as `?size=large`, which matches the «حجمٌ أكبر» label.

### 8.3 Welcome screen

- **`#welcome-signup` «أنشئ حساباً»** goes to `#/signup/new`. It is safe, and is shown only when `choices.registration.mode === "open"`.
  - In `code` mode it is absent and the screen shows «التسجيل هنا برابطٍ ممّن يدير التطبيق.»
  - In `closed` mode it is absent and the screen shows «الحسابات هنا بدعوةٍ ممّن يدير التطبيق.»
- **`#welcome-login` «ادخل»** goes to `#/login` and is safe.
- **Placement is the visual track's.** Its draft (`v2/client/src/screens/auth.tsx`) puts both buttons under the heading, which suits this spec. The rule that matters: after `#welcome-signup`, nothing that commits sits under the pressed spot or nearest to it on «ما يُحفظ هنا» (§8.10).
- **Both listen to click only**, so touch, gaze and switch control behave the same.
- **The welcome text** must not promise the tasks and skills screens, which the owner removed on 2026-10-09. The visual draft's text («عملك اليومي في بوابةٍ واحدة», and one work line per profession) already complies.

### 8.4 Sign-in (the adapted AuthForm)

- **One entry, one name.**
  - The 21st.dev AuthForm's two-button group «تسجيل الدخول / حساب جديد» goes.
  - The visual draft keeps a sign-up entry on this screen: «أنشئ حساباً» (`#login-signup`) in the top-end slot, which is right. It is shown in `open` mode only, goes to `#/signup/new`, is safe, and must pass §8.10.
  - The name is «أنشئ حساباً» everywhere, as the owner's brief writes it.
- **«رجوع»**, where the frame has one, returns to `#/welcome`.
- **The help line under the form.**
  - In `open` mode with a contact: «نسيت كلمة المرور؟ اكتب إلى ‹contact› من بريد حسابك.» The contact is in `<bdi dir="ltr">`; the visual draft does this.
  - Otherwise: «تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل.» The visual draft shows nothing here; it must show this line.
- **After a successful sign-in,** `location.replace("/")` as today. Boot then applies the account's size from `/api/me` before drawing anything; the client cannot know it earlier.

### 8.5 The sign-up steps

**Routes.**

- `#/signup/new` starts a fresh sign-up without a link, in every mode: `state.signup = blankSignup(null, from)`, then `go("#/signup/kept", { replace: true })`.
- `#signup=CODE` (an operator link) is captured as today. The code is kept in memory and erased from the URL, then the client goes to `#/signup/kept`.
- Every other step is `#/signup/<step>`. A step the state does not allow yet redirects to the first missing step (`firstMissingStep()`).

**State (memory only; nothing is sent before the last step).**

```ts
interface SignupState {
  code: string | null; from: "welcome" | "login"; checked: boolean;
  kept_seen: boolean;   // «التالي» on «ما يُحفظ هنا» was pressed
  read: boolean;        // «قرأتُه» is on
  agreed: boolean;      // «أوافق وأتابع» was pressed
  terms_version: string | null;   // the version displayed when «أوافق وأتابع» was pressed
  ui_size: "COMPACT" | "GAZE" | null;   // confirmed on the size step
  name: string; year: number | null; month: number | null; day: number | null;
  profession: string | null; email: string; alert: string | null;
}
```

**The order: the notice first, then the size.** The notice tells the user that their usage mode is stored («طريقة الاستخدام») before they are asked for it. The visual draft uses this order too.

**The eleven screens.**

| # | Step and route | Content (copy in §8.5.1) | Bottom start | Bottom end |
|---|---|---|---|---|
| 1 | `kept` (`#/signup/kept`) | «ما يُحفظ هنا»: `choices.notice.kept`, one line each | — | «التالي» `#signup-kept-next`, safe |
| 2 | `sent` | «ما يُرسَل إلى Anthropic»: intro, items, outro | «قرأتُه» `#signup-read`, `data-value`, `aria-pressed` | «أوافق وأتابع» `#signup-agree`, **`data-commit`**, disabled until «قرأتُه» is on |
| 3 | `use` | «كيف تستخدم الجهاز؟»: the two options from `choices.ui_sizes`, with `data-value` and `aria-pressed` (`#signup-use-COMPACT`, `#signup-use-GAZE`), starting with the size shown; the help line | — | «التالي» `#signup-use-next`, safe; it applies the size |
| 4 | `name` | as on main | — | «التالي» |
| 5–7 | `year`, `month`, `day` | as on main. In the compact size the visual track may merge them into one screen; the request is unchanged. | — | «التالي» |
| 8 | `profession` | each profession's name and **work line** (§9.3 H); help «تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ ممّن يدير التطبيق.» | — | «التالي» |
| 9 | `email` | as on main, plus `#signup-email-help` (§4.3, item 6) | — | «التالي» |
| 10 | `review` | name, birth date, profession, «طريقة الاستخدام: ‹name›», email, and the recovery help (§8.5.1) | — | «التالي» |
| 11 | `password` | as on main; `#signup-create` «أنشئ حسابي: ‹profession›», `data-commit`, in the content area | — | — |

- **Slots are the visual track's.** The "bottom start" and "bottom end" columns give the relation that §8.10 needs: «قرأتُه» and «أوافق وأتابع» side by side in the bottom bar, and «التالي» where every step has it. The visual draft puts «التالي» at the end of the content; that works if §8.10 holds.
- **«رجوع»** goes to the previous step, or from step 1 to `#/welcome`, or `#/login` when `from === "login"`. The two notice screens are labelled «قبل أن تبدأ»; the visual track's stepper numbers the others.
- **Review before password.** The review step comes before the password step, as on main, because `#signup-create` on the password step is the commit. The visual demo lists `password` before `review`; it must follow main.
- **`firstMissingStep()`** checks, in order: `kept_seen` (kept), `agreed` (sent), `ui_size` (use), then main's checks (name, year, month, day, profession, email).

**Why consent takes two presses («قرأتُه», then «أوافق وأتابع»).**

- **The problem.** «أوافق وأتابع» appears on the screen right after a press of «التالي» at the same place. On main it is `data-safe` in the bottom-end slot. A resting gaze after that press would land on it, recording consent to text nobody read.
- **The fix.**
  - «أوافق وأتابع» becomes `data-commit`: it records a legal consent.
  - It is disabled until «قرأتُه» is on. Whatever press opens «ما يُرسَل», only a disabled control can be under it. The nearest enabled control is «قرأتُه» beside it, which is not a commit.
  - After «قرأتُه», the gaze rests on «قرأتُه» itself, the same element in its place, which the landing rule allows.
- **The rule holds in any layout and at both sizes,** and the browser tests in §10.4 enforce it. «قرأتُه» sits in the bottom bar, not the content, because in the content it does not fit at the large size in the 320×635 frame (§8.9).
- **Going back.** Returning to «ما يُرسَل» with «رجوع» keeps `read` and `agreed`. Changing nothing does not ask again.

**The check before the first step.** On entering `kept` with `checked === false`:

```ts
const s = getState().signup
const result = s.code
  ? await api("POST", "/api/auth/signup-code", { code: s.code })
  : await api("GET", "/api/auth/registration")
if (nav !== getState().nav || getState().signup !== s) return
if (result.status !== 204) {
  const code = (result.data as ApiError | null)?.code
  const final = result.status === 422 ||
    ["REGISTER_CODE", "REGISTER_CLOSED", "REGISTER_LINK", "REGISTER_FULL", "REGISTER_PAUSED"].includes(code ?? "")
  const back = s.from === "login" ? "#/login" : "#/welcome"
  if (final) setState({ signup: null })            // no point trying again today
  go(back, { replace: true })
  let message = result.status === 422 ? SIGNUP_LINK_INVALID : detail(result)
  if (final && s.code && getState().choices?.registration.mode === "open")
    message += " ويمكنك إنشاء حسابٍ بلا رابط من «أنشئ حساباً»."
  showAlert(back.slice(2), final ? message : `${message} «حسناً» تعيد المحاولة.`)
  return
}
patchSignup({ checked: true })
```

On the welcome or sign-in screen, «حسناً» retries an unchecked sign-up that is still in memory.

**Reload in the middle.** If the hash is `#/signup/<step>` but there is no state:

- In `open` mode, the sign-up restarts at `kept` with the alert «أُعيد تحميل الصفحة، فبدأ التسجيل من أوله.»
- In `code` mode, the client goes to sign-in with «افتح رابط التسجيل من جديد.»
- Nothing is lost either way: nothing was sent.

**Creating the account (`#signup-create`).**

```ts
const json: Record<string, unknown> = {
  name: s.name, birth_date: birthDate(), email: s.email, password, profession: s.profession,
  ui_size: s.ui_size, accept_terms: true, terms_version: s.terms_version,
}
if (s.code) json.code = s.code
```

**Error → step** (`FIELD_STEPS`):

| `field` | step |
|---|---|
| `NAME` | `name` |
| `BIRTH` | `year` |
| `EMAIL`, `TAKEN` | `email` |
| `PASSWORD` | `password` |
| `CONSENT` | `sent` |
| `UI_SIZE` | `use` |
| `TERMS` | `kept`, after clearing `kept_seen`, `read`, `agreed` and `terms_version` and reloading `/api/choices` |

- `REGISTER_CODE` ends the sign-up and shows sign-in.
- `REGISTER_FULL`, `REGISTER_PAUSED` and `RATE` stay on the password screen as an alert.

**After 204:** `setState({ signup: null })`, then `location.replace("/")`, plus the size parameter when `ui_size === "GAZE"`.

- A full navigation, not a hash change, so Safari offers to save the password and nothing from the sign-up stays in memory.
- The workspace opens next (§8.6).

#### 8.5.1 Copy

| Where | Text |
|---|---|
| Kept, heading | «ما يُحفظ هنا» |
| Sent, heading | «ما يُرسَل إلى Anthropic» («Anthropic» in `<bdi dir="ltr">`) |
| Sent, toggle | «قرأتُه» (lucide `Square` / `SquareCheck`, with the state in `aria-pressed`) |
| Sent, consent | «أوافق وأتابع» |
| Use, heading | «كيف تستخدم الجهاز؟» (the owner's brief; the visual draft's «اختر حجم الواجهة» becomes this) |
| Use, options | from `choices.ui_sizes`: «باللمس» / «أزرارٌ وخطٌّ بالحجم المعتاد.», and «بتتبّع العين» / «أزرارٌ أكبر بينها مسافات، تُضغط بالنظر.» (icons: lucide `Hand`, `ScanEye`). The visual draft's «عادي / كبير» become these; its drawn preview of each size may stay. |
| Use, help | «تُحفظ مع حسابك لتُفتح بوابتك بحجمها، ولا تُرسَل إلى مزوّد النموذج. وتغيّرها متى شئت من «حسابي».» |
| Email, help | «من يحاول التسجيل بهذا البريد يعرف أن له حساباً هنا. إن كان ذلك يضرّك فاختر بريداً لا يعرفه غيرك.» |
| Review, size line | «طريقة الاستخدام: ‹name›» |
| Review, help with a contact | «لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به. إن نُسيت كلمة المرور فاكتب إلى ‹contact› من هذا البريد.» |
| Review, help without one | main's text |
| Reload | «أُعيد تحميل الصفحة، فبدأ التسجيل من أوله.» |

The notice lines and the size names come from `/api/choices` (§7.11, §9.2). The client writes no notice text of its own.

### 8.6 Landing in the workspace

- **What boot does after a successful sign-up.** It reads `/api/choices` and `/api/me`. The new account has `ui_size` set and `terms_current: true`, so the client applies the size and renders `#/`: the home of `me.profession`'s unified workspace.
  - There is no welcome, no portal list and no tour in between.
  - No screen is drawn before `/api/me` answers, so the user never sees a frame at the wrong size.
- **The home is action buttons** (owner update, 2026-10-09). Buttons that start real work, with nothing to read first; each workspace track defines its set (§9.3 F). The owner's examples:
  - storekeeper: «فاتورة شراء جديدة», «مرتجع من فاتورة», «صنف جديد», «المخزون», «المصاريف», «المجاميع»;
  - marketing: «حملة جديدة», «حملاتي», «ما ينتظر الاعتماد», «أدخل النتائج», «تقويم المحتوى»;
  - support: «التذاكر المفتوحة», «تذكرة جديدة», «بانتظار قراري», «قاعدة المعرفة».
  - A brand-new account sees the same buttons. Screens with no data yet show their own empty state.
- **Landing rule across the reload.** iOS keeps the pointer where the gaze rests across the full navigation.
  - On each workspace's home, nothing `data-commit` or `data-value` may sit under the spot where `#signup-create` was, and the nearest enabled control to that spot may not be `data-commit`.
  - The home buttons open working screens and are safe, so this mostly constrains the floating tools button and anything the tracks add to the home.
  - This holds at both sizes and in every handheld frame, and the browser tests check it for every profession.

### 8.7 First sign-in without current consent, or without a size (the start sequence)

**Who sees it.** An account signed in with `terms_current === false`, or with `ui_size === null`. That is every existing account after this release, every invited account at first sign-in, and every account when `TERMS_VERSION` changes again.

| # | Route | Shown when | Same component as | On the commit |
|---|---|---|---|---|
| 1 | `#/start/kept` | `!terms_current` | sign-up step 1 | «التالي» → next |
| 2 | `#/start/sent` | `!terms_current` | sign-up step 2 | «أوافق وأتابع» → `POST /api/me/terms {terms_version}` → next |
| 3 | `#/start/use` | `ui_size === null` | sign-up step 3 | «التالي» → `PUT /api/me/ui-size {ui_size}` → apply → `#/` |

- **Bars.**
  - The two notice screens are labelled «قبل أن تتابع».
  - On the first screen of the sequence, the top start holds «حسابي» (safe). It opens `#/account`, where signing out and deleting the account work without accepting.
  - Later screens have «رجوع».
- **Errors.**
  - A 409 `REGISTER_TERMS` reloads `/api/choices` and returns to `#/start/kept`.
  - A 403 `TERMS` from any model-calling route at any time routes to `#/start/kept`.
- **Existing users learn of the open registration here,** from «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.» on «ما يُحفظ هنا» (§4.4).
- **Size for existing users.** Main's users have so far worked at the large size. Until they answer, the screens are shown at the pre-account size, so the welcome's and sign-in's «حجمٌ أكبر» matters for them. The visual track keeps it in the same corner at both sizes.

### 8.8 «حسابي»: show and change the size

- **The account screen** shows the current size by its name from `choices.ui_sizes` («باللمس» or «بتتبّع العين»), under the heading «طريقة الاستخدام». The visual draft's heading «حجم الواجهة» and its «عادي / كبير» become these, so the account screen and the sign-up use the same words.
- **The two options** are `data-value` with `aria-pressed`, and start with the current size.
- **«طبّق»** (the visual draft's «طبّق الحجم», `#account-ui-size-apply`) is `data-commit`, and disabled until the selection differs from the current size; the draft does this.
  - It sends `PUT /api/me/ui-size`. On 204 the client applies the size and writes the URL parameter.
  - The landing rule applies across the size change: after «طبّق», nothing that commits is under or nearest to the pressed spot at the new size.

### 8.9 Fit at both sizes (measured estimate)

- **Method.** `registration_fit/fit.py` renders the three new screens as plain HTML, using:
  - the v2 tokens (`v2/client/src/styles/globals.css`: compact and gaze);
  - the bundled Noto Sans Arabic;
  - lucide's own icon shapes;
  - main's handheld frames.
- **It is not the visual design.** It answers whether the content fits. The visual track's own audit in §10.4 is the test of record.

| Screen | Compact, 320×635 | Compact, 375×635 | Gaze, 320×635 | Gaze, 375×635 | Gaze, 390×664 | Gaze, 390×763 |
|---|---|---|---|---|---|---|
| use | fits, 247 px spare | fits, 247 | fits, 92 | fits, 140 | fits, 169 | fits, 268 |
| kept | fits, 193 | fits, 203 | fits, 54 | fits, 77 | fits, 106 | fits, 205 |
| sent (three draft workspace lines) | fits, 222 | fits, 252 | fits, 84 | fits, 105 | fits, 134 | fits, 233 |

- **The longest workspace line on «ما يُرسَل»** that still fits at the large size in the 320×635 frame is 95 characters each with three lines, and 63 characters each with four lines (three workspaces and an "all workspaces" line). Hence the budget of 60 characters in §9.3.
- **The first layout failed.** With «قرأتُه» as a full-width button in the content, «ما يُرسَل» overflowed by 43 px at the large size in the 320×635 frame, even with the short drafts. That is why it is in the bottom bar.
- **Text Size.** v2 does not scale with iOS Text Size (it has no `-apple-system-body`). If the visual track adopts Text Size the way main's static client did (body capped at 19 px), the budget must be measured again by the real audit.
- **Renders at 375×635:** `registration_fit/signup_{use,kept,sent}_{compact,gaze}_375x635.png`.

### 8.10 Gaze contract for these screens

- **Main's contract, ported by the visual track,** applies to every screen in this spec at the large size:
  - 72 px targets, 24 px gaps, 16 px edges, at most 10 targets, no scroll and nothing clipped;
  - no timers and no hover listeners;
  - click only.
- **The landing rules apply after every press** (main's `flow.py` `LANDING` and `NEAREST`):
  - nothing `data-commit` or `data-value` under the pressed spot, except the same element;
  - no `data-commit` as the nearest enabled control.
- **Specific to this spec:**
  1. After `#welcome-signup` (and `#login-signup`): on «ما يُحفظ هنا», nothing that commits is under the pressed spot or nearest to it.
  2. After `#signup-kept-next`: on «ما يُرسَل», `#signup-agree` is disabled and the nearest enabled control is `#signup-read`, not a commit.
  3. After `#signup-read`: the nearest control is `#signup-read` itself.
  4. After `#signup-agree`: on the size step, no option (`data-value`) is under the pressed spot, and nothing that commits is nearest.
  5. After `#signup-use-next`, which may change the size: on `name`, nothing that commits or changes a value is under or nearest.
  6. After `#signup-create`: the workspace rule in §8.6.
  7. The start sequence: the same rules as 1–5.
  8. After «طبّق» on «حسابي»: §8.8.
- **In the compact size,** the visual track defines which of these rules apply. The consent and landing rules above hold at both sizes, because they are about consent, not size.

### 8.11 21st.dev

- **Porting, not importing.** The CSP is `'self'` only, so components are copied into the repo and rebuilt on the v2 tokens. Nothing loads from 21st.dev, a CDN or Google Fonts.
- **The gaze contract overrides component defaults.**
  - The usual 21st.dev «Don't have an account? Sign up» inline link fails it: the target is too small and often sits next to the commit button. It becomes the welcome's «أنشئ حساباً».
  - The AuthForm's tab pair goes (§8.4).

---

## 9. Consent notice and `TERMS_VERSION`

### 9.1 Where the text lives

The notice lives in `eyework/terms.py` (§7.3) and is served in `/api/choices.notice`. One version covers all three modes and every profession.

### 9.2 The text

**«ما يُحفظ هنا» (`KEPT`), final:**

1. «يُحفظ: الاسم، وتاريخ الميلاد، والمهنة، وطريقة الاستخدام، وكلمة المرور مجزّأة.»
2. «البريد لا يُحفظ، بل بصمته للدخول: لا يصله شيء، ولا يُستردّ الحساب به.»
3. «وما تعمله في بوابتك لحسابك وحده، لا يراه مستخدمٌ غيرك.»
4. «تحذف حسابك وبياناته متى شئت من «حسابي»، أو يحذفه بطلبك مَن يدير التطبيق؛ والنسخ الاحتياطية الأقدم تبقى حتى تُحذف.»
5. «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.»

**«ما يُرسَل إلى Anthropic»:**

- `SENT_INTRO`, final: «يُرسَل إلى Anthropic خارج المملكة ما يحتاجه المساعد وحده، بلا اسمك ولا ميلادك ولا طريقة استخدامك:»
- `SENT`: one line per workspace. **The text is supplied by each track (§9.3).** These drafts were used for the fit:
  - `MARKETING`: «التسويق: صورة المنتج ونصّ الحملة.»
  - `SUPPORT`: «الدعم الفني: رسائل العملاء وردودك عليها.»
  - `STOREKEEPER`: «المخزون: بنود الفواتير ليراجعها المساعد.»
  - `ALL`: only if some tool sends something in every workspace (§9.3, item C).
- `SENT_OUTRO`, final: «وتحذفه خلال 30 يوماً، إلا ما تُبقيه سياستها أو القانون.»

**Notes.**

- **«طريقة الاستخدام» is listed as stored.** "Uses eye tracking" is health-adjacent information, so it is named, and the intro says it is never sent.
- **Line 3 is true because work data is private to each account under forced RLS** (the owner's decision). Linking accounts to an employer later would make it false and needs a new version.
- **«خارج المملكة» and the 30-day retention are main's existing claims, kept.** Before release, check them against Anthropic's commercial terms on the release date. If the API retention period is shorter, the sentence stays true; if it is longer, the line must change.

### 9.3 ★ WHAT EACH TRACK MUST SUPPLY ★

> **This section is the hand-off.** The notice cannot ship, and `TERMS_VERSION` cannot be set, until A and B are supplied by the inventory, marketing and support tracks. C–I are rules each track's own spec must state that it meets.

| | Inventory (storekeeper) | Marketing | Support |
|---|---|---|---|
| **A. Exact data sent to Anthropic, per model-calling feature** | Every field of every invoice line the AI reviewer sends: item name, quantity, unit price, line total? Also say whether the supplier name, the invoice number or date, notes, or other invoices (for comparison) are sent. The same for any other feature, such as reading a receipt photo. | Photo and text are on main. List every other field the new campaign tools send: audience, budget, channel, earlier campaigns? | Every field of a customer message that is sent: the text only, or also the customer's name, contact, order number or attachments? Also the history of the conversation, the employee's draft edits, and knowledge-base articles. State the redaction applied to third-party personal data (phone numbers, emails, national IDs) before sending, or say that there is none. |
| **B. The notice line** | One line in MSA, starting «المخزون:», at most **60 characters**, true for every feature of the workspace | starting «التسويق:», at most 60 characters | starting «الدعم الفني:», at most 60 characters |

- **C. Tools in every workspace.** If the floating tools button or an assistant sends anything to the model in every workspace, one track (the one that owns those tools) supplies an `ALL` line in the same form, at most 60 characters. With four lines the measured budget is 63 characters each (§8.9). If no such tool exists, there is no `ALL` line.
- **D. The consent gate.** Every route that sends anything to the model depends on `require_current_terms` (§7.10). The architecture test enforces this.
- **E. New open accounts** (first 7 days, `ew_new_open_account(uid)`).
  - Each model call records `new_account` at its start and counts toward the 400-a-day pool under the lock `eyework.generation_global_cap`, as `ew_begin_generation` does.
  - Each feature has a per-new-account daily cap that still lets a real new employee work. The work-tools draft's `REPLY` cap of 5 a day would stop a support employee in their first week; owner decision 3 names this.
- **F. The first screen and its empty state.** Each track names its workspace's first screen (§8.6) and shows that it meets the landing rule after `#signup-create` and after the start sequence's «أوافق وأتابع», at both sizes.
- **G. Never sent; the reviewer's name.**
  - The user's display name, birth date, `ui_size` and email fingerprint are never sent.
  - The AI reviewer's flag "addressed to the user by name" inserts the display name on our side, after the model's text, from `ew_my_display_name()`, never in the prompt. That is how main's persona already handles «سيمبول».
- **H. The profession's work line at sign-up.** `professions.TAGLINES` still reads «مهامّ … ومهاراته من المصادر الرسمية», which promises the screens the owner removed on 2026-10-09. The sign-up profession step shows it.
  - Each track replaces its tagline with one line saying what the workspace does: at most 40 characters, with no tasks, skills or sources in it.
  - The visual draft's welcome already has good candidates: «فواتير الشراء والأصناف والمرتجعات», «حملاتٌ من صورة المنتج إلى الإطلاق» and «ردودٌ يكتبها سيمبول وتعتمدها أنت».
- **I. The work-tools draft** (`work_sql/migrations/0008_work_tools.up.sql`, line 159), for whichever track inherits it: `IF … >= CASE WHEN fresh THEN … END THEN` does not parse in PL/pgSQL, because the IF condition ends at the first THEN. Wrapping the CASE in parentheses fixes it; it was verified with a minimal reproduction. With that fix, the draft applies on top of NEXT.
- **Anything new stored about the user** (not their work data) needs a line in `KEPT`. Ask this track for it, since this track owns the version.

### 9.4 Version, digest, and procedure

1. Merge the lines from §9.3 into `terms.SENT`.
2. Set `TERMS_VERSION` to the release date (YYYY-MM-DD). It must be later than every key in `DIGESTS` (`2026-10-08`, `2026-10-09`).
   - Never reuse a date that is already on main. A new date costs nothing.
3. Run `tests/unit/test_terms.py`. It prints the digest of `terms.normalized_text()`. Add `"<date>": "<digest>"` to `DIGESTS` and keep the old entries.
4. Run the fit tests (§10.4) at the large size in the 320×635 frame.
5. Release. Existing accounts accept the new version at their next sign-in (§8.7). Until then, `require_current_terms` refuses their model calls with 403 `TERMS`.

### 9.5 Rules for any later change of the text

- Any change of a character needs a new version and a new digest.
- Every account then accepts it again at its next sign-in, because the gate compares versions. There is no "minor change" path; that is the safe default.

---

## 10. Tests

What each test proves is in *italics*.

### 10.1 Database: `tests/db/test_open_registration.py` (new)

1. `test_an_open_registration_creates_an_active_open_account_and_one_ledger_row`: *the account is active, `self_registered`, `open_registered`, carries the terms version and the chosen `ui_size`; the ledger has exactly one `(OPEN, OK)` row.*
2. `test_an_open_registration_never_takes_over_an_account_or_a_pending_invitation`: *both come back TAKEN; the name, profession, password, `ui_size` and `self_registered` are untouched; one `(OPEN, TAKEN)` row each.*
3. `test_an_open_registration_checks_name_birth_consent_size_and_profession`, parametrised over: no name, a bad name shape, no consent, before 1900, tomorrow in Riyadh, no size, an unknown size, an unknown profession. *Each raises its named constraint (or a FK violation).*
4. `test_a_refused_open_registration_leaves_no_ledger_row`.
5. `test_the_open_daily_cap_counts_open_accounts_of_the_last_day`: *149 `(OPEN, OK)` rows, plus TAKEN rows and rows older than 24 h → the 150th succeeds and the 151st raises `registration_open_daily_cap`; a code registration still succeeds.*
6. `test_the_total_daily_cap_counts_both_ways`: *100 `(OPEN, OK)` + 99 `(CODE, OK)` → the 200th by code succeeds; the next by either route raises `registration_daily_cap`.*
7. `test_deleting_accounts_makes_no_room_under_either_cap`.
8. `test_sixty_taken_answers_pause_open_registration_but_not_links`.
9. `test_the_availability_check_names_the_blocker_or_nothing`: *callable by the web role without a session.*
10. `test_a_taken_answer_through_a_link_counts_on_the_link_only`.
11. `test_a_code_registration_writes_one_ledger_row_and_stores_the_size`.
12. `test_the_old_seven_argument_register_is_gone`: *calling it raises `UndefinedFunction`.*
13. `test_the_web_role_cannot_touch_the_ledger_or_the_internal_helpers_or_ui_size`, parametrised:
    - SELECT, INSERT, DELETE and TRUNCATE on the ledger;
    - `ew_registration_blocker` and `ew_new_open_account`;
    - `SELECT open_registered FROM users`, `SELECT ui_size FROM users` and `UPDATE users SET ui_size = 'GAZE'`.
    - *Each raises `permission denied`.*
14. `test_the_ledger_holds_no_identity`: *the columns are exactly `occurred_at, outcome, via`, and `(CODE, TAKEN)` is refused by name.*
15. `test_two_open_registrations_cannot_both_take_the_last_place` (uses `test_state_machine.blocked_on_a_lock`).
16. `test_the_generation_limit_is_ten_for_a_new_open_account_and_forty_otherwise`: *10 / 40 / NULL; equal to `campaigns.NEW_ACCOUNT_DAILY_GENERATIONS` and `DAILY_GENERATIONS`.*
17. `test_the_new_account_week_is_measured_by_the_database`: *7 days minus 1 minute is new; plus 1 minute is not.*
18. `test_a_new_open_account_writes_ten_times_a_day_then_forty_after_its_first_week`.
19. `test_unbilled_failures_do_not_count_toward_the_new_account_limits`.
20. `test_new_open_accounts_share_four_hundred_a_day_counting_deleted_ones`.
21. `test_a_new_open_account_opens_three_campaigns_and_others_twenty`.
22. `test_open_registered_implies_self_registered`.
23. `test_existing_and_invited_accounts_have_no_size_until_chosen`: *`ew_my_ui_size()` is NULL for them, the session user's own value otherwise, and NULL with no session.*
24. `test_a_user_sets_their_own_size_and_nobody_else_s`: *one row changes; NULL and unknown values raise `ui_size_known`; no session and an inactive user raise `insufficient_privilege`.*
25. `test_ui_size_values_match_the_python_enum`: *the CHECK's values equal `UiSize`.*
26. `test_accepting_a_newer_notice_changes_the_session_users_row_only`: *it sets the version and the time; the same version again is harmless; an older one raises `terms_version_backwards`; NULL raises `registration_needs_consent`; no session raises `insufficient_privilege`; an invited account (NULL) can accept.*

### 10.2 Changes to existing database tests (measured: §6.4)

Run against the new schema, main's suite gives 572 passed and 23 failed. Each failure and each required change:

| File | Measured failures | Change |
|---|---|---|
| `test_registration.py` | 21: the helper `_register` calls the 7-argument `ew_register` (`UndefinedFunction`) | `_REGISTER` takes 8 placeholders, and `_register(…, ui_size="GAZE")` passes it last. With only this change, 30 pass and 2 fail. |
| `test_registration.py` | of those, 2 remain: `test_the_daily_cap_counts_the_codes_used_in_the_last_day` and `test_deleting_an_account_does_not_make_room_under_the_daily_cap` | Rename the first to `test_the_daily_cap_counts_the_ledger_of_the_last_day`. Both seed `(CODE, OK)` ledger rows instead of used codes. *The cap's source moved; the old spec's claim that the deletion test passes unchanged was wrong.* |
| `test_roles_and_grants.py` | 1: `test_app_executes_exactly_the_declared_interface` | `APP_FUNCTIONS` adds `ew_register_open`, `ew_open_registration_blocker`, `ew_my_generation_limit`, `ew_my_ui_size`, `ew_set_my_ui_size`, `ew_my_terms_version` and `ew_accept_terms`, with a comment for the NEXT migration. `ALL_TABLES` and the DELETE/TRUNCATE parameters add `registration_ledger`. |
| `test_generation_caps.py` | 1: the tombstone columns | It now expects `["new_account", "outcome", "started_at"]`. *A flag, not an identity.* |
| `test_rls.py` | none | `RLS_TABLES` adds `public.registration_ledger`. *The ledger has RLS enabled and forced.* |
| `test_purge.py` | none | New `test_registration_ledger_rows_go_after_their_day`. |
| `test_migrations.py` | none (it already cycles the new migration) | `SNAPSHOT_MUST_COVER` adds `ALTER TABLE ONLY public.registration_ledger FORCE ROW LEVEL SECURITY;`. New `test_next_backfills_the_ledger_from_codes_used_in_the_last_day`, `test_next_down_refuses_while_open_accounts_exist`, and `test_next_down_waits_for_an_open_account_being_created_and_still_refuses`. |
| `test_admin_professions.py` | none | none (design A keeps main's fixtures valid) |

### 10.3 API

**`tests/api/test_open_registration_api.py` (new).** The API `browser` factory gains an `address` argument (`TestClient(client=(address, 50000))`).

1. `test_registering_without_a_link_signs_in_with_the_new_account_limits_and_size`: *204 and a cookie; `/api/me` returns `generations_left: 10`, `generation_limit: 10`, the chosen `ui_size` and `terms_current: true`, and no email or birth date.*
2. `test_a_link_still_works_in_open_mode_and_its_account_is_not_new`.
3. `test_an_unusable_link_is_refused_even_in_open_mode`: *410 and no users.*
4. `test_code_mode_refuses_registration_without_a_link_before_anything_else`.
5. `test_closed_mode_refuses_every_route`.
6. `test_the_choices_name_the_mode_contact_sizes_and_notice`: *`registration.mode`, `support_contact`, `ui_sizes` equal to `ui_size.CHOICES`, and `notice` equal to `terms.notice()`.*
7. `test_a_taken_email_is_refused_without_touching_the_account_and_counted`.
8. `test_three_taken_answers_close_the_open_path_for_that_network`.
9. `test_open_registrations_are_limited_per_network_and_field_errors_do_not_count`.
10. `test_the_daily_per_network_limit_holds_after_the_hourly_one_resets`.
11. `test_ipv6_addresses_in_one_64_share_a_budget`.
12. `test_a_full_day_answers_the_same_for_taken_and_free_emails`.
13. `test_a_paused_day_answers_the_same_for_taken_and_free_emails_and_links_still_work`.
14. `test_the_availability_check_is_limited_per_network`.
15. `test_the_availability_check_changes_nothing_and_needs_no_write_headers`.
16. `test_each_invalid_field_names_itself_without_a_link`.
17. `test_registering_without_a_link_needs_the_write_headers`.
18. `test_a_new_open_marketing_account_writes_ten_times_a_day`.
19. `test_a_new_open_account_opens_three_campaigns`.
20. `test_registration_without_a_size_or_with_an_unknown_one_is_refused`: *422; no user; no ledger row.*
21. `test_registration_with_a_stale_terms_version_is_refused_before_anything_else`: *409 `REGISTER_TERMS`; no limiter consumed; no user.*
22. `test_a_user_changes_their_own_size`: *`PUT /api/me/ui-size` → 204 and `/api/me` shows it; an unknown value → 422; no cookie → 401; no write headers → 403; the 31st request in an hour → 429.*
23. `test_an_account_without_current_consent_cannot_reach_the_model`: *an invited account (terms NULL) and an account on `2026-10-09` get 403 `TERMS` from `/copy` and `/copy/edit`, and the copywriter is never called; after `POST /api/me/terms` with the current version, `/copy` succeeds.*
24. `test_accepting_the_notice_takes_only_the_current_version`: *another date → 409 `REGISTER_TERMS`; the current one → 204, `terms_current: true`.*
25. `test_routes_that_send_nothing_to_the_model_work_without_current_consent`: *`/api/me`, `PUT /api/me/ui-size`, logout, `/api/me/delete` and the campaign list.*
26. `test_a_newer_accepted_version_counts_as_current`: *with the server's version patched to an earlier date, a user who accepted the later one still reaches `/copy`, and `terms_current` is true.*

**Changes to existing API tests.**

- `conftest.add_user` sets `terms_version` to `terms.TERMS_VERSION` (an owner UPDATE after `make_user`). The campaign flow keeps working, and test 23 covers the gate.
- `test_registration_api.py`:
  - `closed_server` builds `Settings(..., registration="closed")`;
  - `_body` sends `code` only when given, plus `ui_size` and `terms_version`;
  - `/api/me` expects `generation_limit: 40`, `ui_size` and `terms_current`.

### 10.4 Browser: the React client (Playwright, main's frames and `flow.py` rules, ported by the visual track)

1. `test_signing_up_from_the_welcome_screen_to_the_workspace`, for every profession, at both sizes, in all five frames:
   - *every screen passes the audit for its size;*
   - *on handheld frames, the landing and nearest-control rules hold after every press;*
   - *no timers and no hover listeners;*
   - *exactly one `GET /api/auth/registration` before `use`, and one `POST /api/auth/register`, whose body has no `code` key and has `ui_size` and `terms_version`;*
   - *the first screen after the reload is that profession's workspace, at the chosen size, with the §8.6 landing rule.*
2. `test_the_notice_cannot_be_agreed_by_a_resting_gaze`: *after `#welcome-signup`, `#login-signup` and `#signup-kept-next`, `#signup-agree` is never under the pressed spot or nearest to it; it is disabled until `#signup-read`.*
3. `test_the_size_applies_only_on_next_or_apply`: *selecting an option changes no `data-size`; «التالي» or «طبّق» does; the step starts with the size shown.*
4. `test_back_from_the_first_notice_screen_returns_to_the_welcome_with_nothing_committing_nearest`.
5. `test_the_entry_is_absent_in_code_and_closed_modes`: *`#welcome-signup` is not visible and the mode line shows. Typing `#/signup/new` makes one GET to the check route and leads to sign-in with the server's own text (403 `REGISTER_LINK` or `REGISTER_CLOSED`); the client writes no copy of its own for this.*
6. `test_a_full_or_paused_day_is_said_before_the_first_step`.
7. `test_a_failed_check_keeps_the_sign_up_and_tries_again`.
8. `test_reloading_in_the_middle_starts_over_at_the_first_notice_screen`.
9. `test_a_taken_email_returns_to_the_email_step_and_a_new_one_succeeds`.
10. `test_a_stale_notice_returns_to_kept_and_asks_again`: *the server's version changes mid-sign-up → `REGISTER_TERMS` → `kept`, with `read` off.*
11. `test_the_contact_is_shown_where_recovery_is_explained`.
12. `test_a_used_link_in_open_mode_offers_signing_up_without_it`.
13. `test_a_second_press_while_the_check_is_in_flight_sends_nothing_more`.
14. `test_an_existing_account_accepts_the_new_notice_and_chooses_its_size_once`: *a pre-release account (size NULL, terms `2026-10-09`) signs in → `#/start/kept` → `sent` → `use` → the workspace. The POST and the PUT are each sent once; the next sign-in goes straight to the workspace.*
15. `test_an_invited_account_answers_both_at_first_sign_in`.
16. `test_a_null_size_never_renders_the_workspace` (the §8.2 `fromServer` rule).
17. `test_the_account_screen_changes_the_size_and_the_landing_rule_holds`.
18. `test_a_model_route_refused_for_consent_routes_to_the_notice`: *a 403 `TERMS` (via `page.route`) → `#/start/kept`.*
19. `test_the_size_url_parameter_does_not_name_gaze` (the §8.2 rule).
20. `test_the_notice_fits_at_both_sizes`: *«ما يُرسَل» with the real lines passes the audit at the large size in the 320×635 frame (§8.9).*

`test_touch.py` gains the welcome → workspace walk by tap alone, at the compact size.

### 10.5 Unit and architecture

- `tests/unit/test_config_registration.py` (new): *unset means open and requires a contact; code and closed work without one; an unknown mode fails; an invalid contact fails; the contact is normalised.*
- `tests/unit/test_config_sdk_env.py`: `base_env` sets `EYEWORK_SUPPORT_CONTACT`.
- `tests/unit/test_rate_limit.py` (new): *`blocked()` records nothing and returns the wait; `record()` counts.*
- `tests/unit/test_client_network.py` (new).
- **`tests/unit/test_terms.py`, rewritten.** It hashes `terms.normalized_text()` instead of parsing `index.html`.
  - *The current version has a digest.*
  - *`KEPT` contains «مَن يدير التطبيق» and «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا».*
  - *`SENT` has exactly one line per profession that has a model-calling feature, each starting with that workspace's name and a colon, each at most 60 characters.*
  - *No line is empty or still the draft placeholder «…».*
- **Architecture (new):**
  - *every FastAPI route whose handler reaches a model client depends on `require_current_terms`;*
  - *the client contains no copy of the notice text (it renders `/api/choices.notice`).*
  - The existing rules still hold: no timers, no storage, click only, no wall clock, no SQL formatting, nothing unfinished.
- **Client unit tests (vitest):**
  - `firstMissingStep` order;
  - `FIELD_STEPS`;
  - `fromServer(null)` is "ask", not compact;
  - the URL parameter value.

---

## 11. Rollout and rollback

1. **Before release,** complete §9.4: the lines from §9.3, the version and the digest.
2. **Ship** the server, the migration and the React client together (§7.13), and run `python -m eyework.migrations.run up` with the owner role.
3. **Existing deployments** must choose before restarting:
   - set `EYEWORK_SUPPORT_CONTACT`, which opens registration; or
   - set `EYEWORK_REGISTRATION=code`, which keeps today's behaviour.

   A restart with neither fails with a `ConfigError` that names the variable.
4. **Existing users,** at their next sign-in, choose their size and accept the new notice (§8.7). Until they accept, their model calls get 403 `TERMS`. Nothing else in their workspace changes.
5. **`purge`** also clears the ledger. The daily schedule stays as it is.
6. **Rollback.**
   - `EYEWORK_REGISTRATION=code` stops open registration with no migration.
   - To go below NEXT, delete the open accounts as the down's HINT says, then `down --to <previous>`. Sizes are dropped (the older client is large for everyone), and accepted consent versions stay.

---

## 12. Decisions that are the owner's (truly open)

1. **The enumeration trade-off.**
   - In open mode, anyone can learn whether an email has an account in this app, and a single targeted question cannot be stopped (§4.2).
   - Accept it with the mitigations in §4.3 (this spec), or choose B (verify the email through an email provider), C (login names the app generates) or D (stay in `code` mode).
2. **Who answers `EYEWORK_SUPPORT_CONTACT`.**
   - Name the mailbox and the person behind it.
   - Accept the recovery process: reply to the account's own address before `reissue-activation --owner-verified` or `delete-user` (§4.4, §4.6). The mailbox's provider sees what users choose to write.
3. **The numbers.**
   - Registrations: 200 a day in total, at most 150 without a link.
   - The pause: 60 "email taken" answers a day.
   - Per network: 5 an hour, 10 a day, and 3 "email taken" answers a day.
   - New open accounts: 7 days long, 10 marketing generations a day each, 400 a day for all of them together, and 3 open campaigns each.
   - The new-account caps for the other workspaces' AI features. A support employee needs enough AI drafts in their first week to work.
   - Whether the worst case of 1.35 GB of images a day (§5.4) needs a global ceiling.

Decisions taken in this version, with their reasons, that are no longer open:

- `open` is the default, and an upgrade without a contact refuses to start (§2).
- Operator-link accounts do not get the new-account limits, because the operator vouched for them.
- Existing users are told through the start sequence (§8.7).
- The version is a new date, never a reused one (§9.4).
- Every account accepts the new notice before the model sees its data (§7.10).
- A missing size means "ask", never a silent default (§6.1).

---

## 13. Evidence (scratch, not part of the repo)

All paths are under `/tmp/claude-0/-home-user-Re/8edf39e1-5004-507f-af63-684fde9b0af5/scratchpad/redesign/`.

- **`registration_sql/next/NEXT_open_registration.up.sql` and `.down.sql`:** the exact SQL in §6.
- **`registration_sql/scripts/`:**
  - `build_down.py` generates the down from main's 0005.
  - `cycle.sh` runs the up/down/up and empty/up cycle with the repo's runner from the worktree `scratchpad/reg_v2_main` (`d543356`) on `reg_v2_test`.
  - `check_next.py` runs the 29 functional checks as `eyework_app`.
- **`registration_sql/evidence/`:**
  - `cycle.txt`: three comparisons, all identical.
  - `check_next.txt`: 29/29.
  - `existing_db_suite.txt`: main's database suite against NEXT, 572 passed and 23 failed, as in §10.2.
  - `s6.sql`, `s6b.sql`, `s7.sql`, `s7b.sql`, `s7c.sql` and `s0.sql`: the snapshots.
- **`registration_sql/superseded_B/`:** design B, its prototype tests, its evidence, the previous run's copies of main's migrations (`migrations_harness/`), and the 2026-10-08 version of this spec (`evidence/registration_spec_2026-10-08.md`).
- **`registration_fit/`:**
  - `fit.py`, `icons.mjs` and `icons.json`: the fit estimate in §8.9.
  - `fit_results.json`: its raw output.
  - Six renders, `signup_{use,kept,sent}_{compact,gaze}_375x635.png`.
- **`registration_check/` and `registration_measure/`:** the previous run's measurements of the static client. They are superseded by the React client (§7.13) and kept for the record.
