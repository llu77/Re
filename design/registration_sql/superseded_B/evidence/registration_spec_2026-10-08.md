# Open registration without an invitation

Track spec for eyework. Status: ready to implement. Date: 2026-10-08.
UI copy is Modern Standard Arabic; everything else is English.

---

## 0. Summary

The owner asked for registration that needs no invitation. This spec covers it end to end:

- **Modes.** `EYEWORK_REGISTRATION=open|code|closed`, with `open` as the new default. A new `EYEWORK_SUPPORT_CONTACT` setting is required in `open` mode. Without it, an upgraded deployment refuses to start, so registration can never open by accident on upgrade.
- **Entry.** A «أنشئ حساباً» button goes in the top-end slot of the sign-in screen, the same slot that «حسابي» uses on the home screen. If the design track adds a welcome screen, it gets the same entry. The button starts the same nine steps with no code. Operator links (`#signup=CODE`) keep working in every mode except `closed`.
- **Migration 0007.**
  - A separate `ew_register_open` function. `ew_register` still requires a valid code, as it does today.
  - A `registration_ledger` with no identity in it. Every registration cap counts from it, so deleting an account frees no room.
  - App-wide limits: 200 self-registrations a day in total (as today), 150 of them at most without a link. After 60 "email taken" answers in a day, open registration pauses for everyone.
  - Tighter limits for accounts registered without a link, in their first 7 days: 10 AI generations a day instead of 40, 400 a day across all such accounts (out of the app-wide 2,000), and 3 open campaigns instead of 20. The database enforces all of this.
  - Grants: no new table grant and no new policy for the web role. Three new EXECUTE grants: `ew_register_open`, `ew_open_registration_blocker` and `ew_my_generation_limit`.
- **Per-network limits on the open path.** A network is an IPv4 address or an IPv6 /64. Each gets 5 registrations an hour, 10 a day, and 3 "email taken" answers a day. The third limit replaces the code's three-strikes lock for registrations without a link.
- **Taken email.** The server still answers 409 `REGISTER_TAKEN`. In open mode this tells anyone whether an email has an account. §4 states that trade-off plainly and lists the mitigations.
- **Consent notice.** It now names «مَن يدير التطبيق» instead of the person who gave the link. It also says that anyone who tries to register with your email learns that you have an account. `TERMS_VERSION` is bumped.
- **Baseline.** `origin/main` `d543356` (§1).
- **Verified before writing.**
  - 0007 goes up, down and up again with the schema matching exactly. Tested on PostgreSQL 16 on top of main's 0001–0006 (unchanged since `fa84cd1`), both from 0006 and from a full rollback to empty.
  - 20 functional checks pass, run as the real `eyework_app` role.
  - The new copy fits. It was measured with the repo's own gaze audit at 320, 375 and 390 px widths and at iOS Text Size 17, 23 and 53.
  - The entry's landing and nearest-control geometry was measured with the repo's `LANDING` and `NEAREST` scripts. The evidence is listed in §13.

---

## 1. Baseline

- **Code of record.** `origin/main` at `d543356` (PR #10 merged). It contains:
  - migrations 0001–0006, unchanged since `fa84cd1`. Migration 0007 builds on them, and its down migration restores their 0005 functions word for word;
  - the notice at `TERMS_VERSION = "2026-10-09"`, digest `baba6ba6…`, from `03a12ec`;
  - the two-step sign-out, also from `03a12ec`.
- **What my measurements ran on.** The static client from `fa84cd1`, with main's notice text applied. I reproduced the `2026-10-09` digest exactly from that text. Between `fa84cd1` and `d543356`, the sign-in markup and `styles.css` did not change (checked with `git diff`), so the measurements hold for main.
- **This spec's notice** is main's text plus two edits (§9). If main's text changes before this lands, apply the same two edits and run the checks in §10.4 again.
- **The React client.** `a519ddb` on the working branch adds `eyework/client`: a Vite, React and shadcn client with the 21st.dev AuthForm and DropdownNavigation. FastAPI does not serve it yet; the static pages stay the app until the redesign moves screens over. §8.5 says what the client needs from this spec.
- **No welcome screen on main.** The sign-in screen alone is enough to open registration. §8.3 sets the rules a welcome screen's entry must meet if the design track adds one.

---

## 2. Modes

| | `open` (default) | `code` | `closed` |
|---|---|---|---|
| «أنشئ حساباً» on sign-in (and welcome) | shown | hidden | hidden |
| `#signup=CODE` link | works; the account is not "open" | works | refused (403 `REGISTER_CLOSED`) |
| `GET /api/auth/registration` | 204, or 503 `REGISTER_FULL` / `REGISTER_PAUSED` | 403 `REGISTER_LINK` | 403 `REGISTER_CLOSED` |
| `POST /api/auth/register` without `code` | open path | 403 `REGISTER_LINK` | 403 `REGISTER_CLOSED` |
| `POST /api/auth/register` with `code` | code path (unchanged) | code path (unchanged) | 403 `REGISTER_CLOSED` |
| `POST /api/auth/signup-code` | unchanged | unchanged | 403 `REGISTER_CLOSED` |
| `EYEWORK_SUPPORT_CONTACT` | **required** | optional | optional |
| Invitations (`admin create-user`) | unchanged | unchanged | unchanged |

**Boot rules (`config.load`):**

- If `EYEWORK_REGISTRATION` is unset or empty, the mode is `open`. Any value outside the three modes raises `ConfigError`.
- `EYEWORK_SUPPORT_CONTACT` must be an email address of the same shape as a login name: after NFKC and lowercasing, it matches `^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$` and is at most 254 characters. It is the operator's address, not a user's, so showing it in the interface reveals nothing about users.
- The new default has a consequence for existing deployments. One that upgrades without changing its environment refuses to start, with a `ConfigError` naming `EYEWORK_SUPPORT_CONTACT`. It stays down until the operator either sets a contact, which accepts open registration, or sets `EYEWORK_REGISTRATION=code`.

**The server decides the mode; the database does not know it.** `ew_register` still answers `CODE` without a valid code. The open path is a different function, which the server calls only in `open` mode. §3 explains why there is no database-side switch.

---

## 3. Guarantees: what holds, what moves

| Guarantee | Before (0005/0006) | After (0007) |
|---|---|---|
| No account without a valid code | DB (`ew_register`) | `ew_register` is unchanged in this respect. In `code` and `closed` modes the server never calls `ew_register_open`; API and UI tests prove it. In `open` mode the guarantee is dropped on purpose. |
| Registration never takes over an existing login or a pending invitation | DB (`ON CONFLICT DO NOTHING`) | DB, in both functions |
| Name shape, birth date (not in the future by Riyadh's date, not before 1900), consent, profession that exists | DB | DB, in both functions |
| At most 200 self-registrations in 24 h, and deleting accounts makes no room | DB, counted from used codes | DB, counted from `registration_ledger`. Used codes from the last day are backfilled at migration time. |
| At most 150 registrations without a link in 24 h, and deletion makes no room | — | DB, from the ledger |
| "Email taken" answers are bounded | 3 per code (DB) | Codes: unchanged. Open path: 3 per network per day (server memory), and 60 a day app-wide, after which open registration pauses (DB) |
| The web role learns nothing about other users | DB grants | The ledger has no grant and no web-role policy. The new functions return either app-wide state or the session user's own limit. |
| AI spend | 2,000 a day app-wide, 40 per user (DB) | Unchanged, plus for new open accounts: 10 a day each, 400 a day for all of them together (deleted ones included), and 3 open campaigns each (DB) |
| A down migration never leaves an account the older schema does not describe | 0005 down refuses | 0007 down also refuses while any `open_registered` account exists |

**No database-side mode switch (alternative considered).** The web role already sets `eyework.user_id` itself; that is how row isolation works here. A mode check in the database therefore cannot hold against a compromised server. It would only catch a route bug, and the cost is a second setting the operator must keep in step with the environment. The tests in §10 cover that route bug.

---

## 4. A taken email

### 4.1 What the server returns

Unchanged from the code path:

- `409 REGISTER_TAKEN`, `field: "TAKEN"`, with the message «يوجد حسابٌ بهذا البريد. ادخل به، أو اكتب بريداً آخر.»
- The client goes back to the email step with that alert (`FIELD_STEPS.TAKEN = 'email'`, already in place).

On the open path, the answer also does two things:

1. Writes one ledger row `(OPEN, TAKEN)`, which counts toward the app-wide pause.
2. Records one event in the per-network budget `taken_open_net`.

### 4.2 The trade-off, plainly

- **Who can ask.** In `open` mode, anyone can find out whether a given email has an account in this app. The list of users is health information: the people on it work with their eyes. So "does X use eyework?" is a sensitive question.
- **Why it cannot be closed.** The app sends no email, so it cannot check that the person registering owns the address. When the email is the unique login name, "account created" and "not created" are different outcomes, and that difference is the answer. A vaguer error message would hide nothing.
- **What could close it.** Only a different design, listed in §4.5: verifying the email by sending a code, which needs an email provider; login names the app generates; or staying in `code` mode.
- **The login endpoint.** Sign-in keeps its own guarantee: equal timing and one message for every failure. In `open` mode, though, that guarantee no longer hides the user list, because registration is a second way to ask.

### 4.3 Mitigations (all in this spec)

1. **No "is this email free?" endpoint.** The only way to ask is a full `POST /api/auth/register`. It must pass every field check (name, birth date, email shape, a 12+ character password, an existing profession, `accept_terms: true`), and the server computes scrypt before asking the database.
2. **Asking about a free email creates a real account.** That costs the asker one of the 150 open places for the day and one of their network's 10 daily registrations, and the account cannot be taken back without deleting it.
3. **Per network** (IPv4 address, IPv6 /64): 5 registrations an hour, 10 a day, and 3 "email taken" answers a day. After that, every open registration from that network gets `429 RATE` before the database is touched. These limits live in memory and are checked after the field checks, so a typo costs nothing.
4. **App-wide, in the database:** 60 `(OPEN, TAKEN)` answers in 24 h pause open registration for everyone with `503 REGISTER_PAUSED`. The pause survives restarts and holds across processes. Operator links keep working.
5. **The same answer whatever the email when it matters.** The caps and the pause are checked before the insert. On a full or paused day, a taken email and a free email get the same response; an API test asserts this.
6. **Users are told.**
   - The notice says «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.»
   - The email step adds, under the field: «من يحاول التسجيل بهذا البريد يعرف أن له حساباً هنا. إن كان ذلك يضرّك فاختر بريداً لا يعرفه غيرك.»
7. **A database leak still reveals no emails.** Only HMACs are stored (0001); nothing changes there.

### 4.4 What is not mitigated

- **A single targeted question.** One request from a new network answers "does this person have an account?". Rate limits only stop asking in bulk.
- **Squatting.** Someone can register another person's email first. The real owner then sees «يوجد حسابٌ بهذا البريد». The remedy is a process, not code. The owner writes to `EYEWORK_SUPPORT_CONTACT` from that address. The operator replies to that address to confirm the request came from it, then runs `admin delete-user --login <email> --confirm-delete-all-data`. The email lookup already works through the HMAC. The person can then register.
- **Existing accounts, including invited ones, become askable** as soon as the mode is `open`. Under `code`, only someone holding a code could ask, and only 3 times per code. Whether to tell existing users is decision 6 in §12.

### 4.5 Alternatives (owner decision 1)

| Option | Removes the yes/no answer? | Cost |
|---|---|---|
| A. **This spec:** email as the login name, honest 409, the limits in §4.3 | No | A single targeted question gets an answer |
| B. Verify the email: send a one-time code; registration always answers "check your inbox" | Yes | An email provider learns who registers for a disability app. That is a third party holding health information, and it conflicts with the rule that data stays on owned infrastructure. It also needs a sending domain and handling for bounces and abuse. |
| C. The app generates the login name (for example «ew-7Q4K-93HD»), saved by Safari Keychain or used with a passkey | Yes | Users must keep a random name. Losing the Keychain loses the account. Typing it by gaze is slow. |
| D. Keep `code` mode | Yes (only code holders can ask, 3 times per code) | Every account still needs the operator |

### 4.6 Recovery for an open account

- Nothing about the account is known outside the system, so the operator cannot recognise its owner.
- The help text on the review step and on the sign-in screen sends the user to `EYEWORK_SUPPORT_CONTACT`, asking them to write from the account's own address.
- The operator replies to that address. If the person confirms, the operator runs `reissue-activation --login <email> --owner-verified`. That flag is already required for self-registered accounts.
- The operator's mailbox is a third party, but it only sees what the user chooses to send. This is decision 3.

---

## 5. Abuse limits

### 5.1 Registration volume (database)

All counts are over the last 24 h of `registration_ledger`. The checks run under one advisory lock shared with the code path (`eyework.registration_daily_cap`), so two registrations at the same moment cannot both take the last place; a test checks this.

| Constraint (error) | Counts | Limit | Applies to |
|---|---|---|---|
| `registration_daily_cap` (503 `REGISTER_FULL`) | `outcome = 'OK'`, both routes | 200 | both routes |
| `registration_open_daily_cap` (503 `REGISTER_FULL`) | `via = 'OPEN' AND outcome = 'OK'` | 150 | open route. Operator links always keep at least 50 a day. |
| `registration_open_paused` (503 `REGISTER_PAUSED`) | `via = 'OPEN' AND outcome = 'TAKEN'` | 60 | open route |

### 5.2 Per network (server memory)

| Limiter | Key | Limit | Counted when |
|---|---|---|---|
| `register_open_net` | `client_network()` | 5 / hour | each open registration that passes the field checks |
| `register_open_net_day` | `client_network()` | 10 / 24 h | same |
| `taken_open_net` | `client_network()` | 3 / 24 h | after a TAKEN answer. It is checked before the database call, which records nothing. |
| `registration_check_net` | `client_network()` | 30 / hour | `GET /api/auth/registration` |
| `register_ip`, `signup_code_ip` | `client_ip()` | 20 / hour (unchanged) | code path |

- `client_network()` maps IPv4 to the address itself, IPv6 to its /64, and an IPv4-mapped IPv6 address to the IPv4 address. A phone on an IPv6 network can change addresses within its /64 at will, so the /64 is the unit to limit.
- As today, these limits sit behind a trusted proxy (`--proxy-headers`). They are per process.
- `taken_open_net` uses a new pair, `blocked()` then `record()`. Two concurrent requests from one network can therefore both pass, overshooting by at most the number in flight; `register_open_net` (5 an hour) still bounds that.

### 5.3 AI spend for new accounts (database)

A **new open account** is `open_registered` and created less than 7 days ago (`ew_new_open_account`).

| Constraint (error) | Limit |
|---|---|
| `generation_new_account_cap` (429 `AI_NEW_DAILY`, Retry-After 3600) | 10 billable generations per 24 h for that account, under the existing lock on its user row |
| `generation_new_accounts_cap` (503 `AI_NEW_BUSY`, Retry-After 3600) | 400 billable generations per 24 h across all new open accounts. It is counted from `generation_attempts.new_account` plus `attempt_tombstones.new_account`, so deleting an account refunds nothing. It runs under the existing app-wide lock. |
| `new_account_campaign_cap` (409 `NEW_OPEN_CAP`) | 3 open campaigns (DRAFT, COPY_PROPOSED, COPY_APPROVED) instead of 20 |

**Effect.** Accounts registered without a link can spend at most 400 generations a day, so established users keep at least 1,600 of the 2,000. The per-user rate (6 in 10 minutes, one at a time) and the global cap are unchanged. Accounts from operator links and invitations are not affected (decision 5).

**What the user sees.**

- `/api/me` returns `generation_limit` (10 or 40) and `generations_left` from `ew_my_generation_limit()`, so the interface never promises 40 to an account that has 10.
- The error messages in §7.6 say what applies and when it ends.

### 5.4 Storage

- Without the campaign cap, 150 accounts a day × 20 drafts × 3 MB (`images.MAX_OUTPUT_BYTES`) could add 9 GB a day.
- With 3 open campaigns, a new account holds at most 9 MB in its first week, which is at most 1.35 GB a day.
- After the first week an account can hold 20 campaigns (60 MB). The 150-a-day cap and the purge of drafts idle for 30 days still bound the total.
- A global storage ceiling is decision 8. It is not in this spec.

---

## 6. Migration 0007

### 6.1 Design notes

- **`registration_ledger(occurred_at, via, outcome)`.**
  - It holds no account, no HMAC and no address. A CHECK (`registration_ledger_taken_is_open`) forbids `(CODE, TAKEN)` rows, because a TAKEN answer through a link is counted on the code itself.
  - RLS is enabled and forced, with an owner policy only. The web role has no grant and no policy.
  - `purge` deletes rows older than 24 h.
  - At migration time it is backfilled from `signup_codes.used_at` for the last 24 h. Codes whose account was deleted are included, so the cap the day of the switch is exactly the cap 0005 counted.
- **`ew_register_open`.**
  - It runs the field checks first, then the caps under the shared lock, then `INSERT … ON CONFLICT DO NOTHING`.
  - Each OK and each TAKEN writes one ledger row. A refused call (a field check, a cap, the pause) raises an exception, which rolls back and writes nothing.
  - As on the code path, `auth.register` raises `RegistrationTaken` only after the transaction commits, so the TAKEN row stays.
- **`ew_register`.** The function body is 0005's, except that the cap now comes from `ew_registration_blocker('CODE')` and an OK writes `(CODE, OK)`.
- **`ew_registration_blocker(p_via)`** is shared by both register functions and by `ew_open_registration_blocker()`. The limits therefore live in one place, and the availability check cannot disagree with the registration.
- **Columns.**
  - `users.open_registered` comes with `CHECK (NOT open_registered OR self_registered)`.
  - `generation_attempts.new_account` is written only by `ew_begin_generation`. The web role has no INSERT on that table. Its table-level SELECT now also shows its own attempts' `new_account`, which is harmless.
  - `attempt_tombstones.new_account` is copied by `ew_attempt_tombstone`. The tombstone still holds no identity.
- **Replaced functions.** All of these are `CREATE OR REPLACE`, so their existing privileges carry over: `ew_register`, `ew_attempt_tombstone`, `ew_campaign_insert_guard` and `ew_begin_generation`. Each is 0005's body plus the marked lines.
- **Grants.**
  - `REVOKE ALL … FROM PUBLIC` on all five new functions.
  - `GRANT EXECUTE` to `eyework_app` on three of them: `ew_register_open`, `ew_open_registration_blocker` and `ew_my_generation_limit`.
  - `ew_new_open_account` and `ew_registration_blocker` are called only by owner functions. The web role gets `permission denied` on them; this is checked.
- **Down.** It locks `users` like 0005's down does, and refuses while any `open_registered` account exists, with a HINT on how to delete those accounts. It then restores the four functions from 0005 word for word, drops the new functions and columns, and drops the ledger.

### 6.2 `migrations/0007_open_registration.up.sql` (exact)

```sql
-- ════════════════════════════════════════════════════════════════════════
-- 0007_open_registration — التسجيل المفتوح بلا رابط
-- ════════════════════════════════════════════════════════════════════════
-- يُنشئ الزائر حسابه بلا رمزٍ من المشغّل حين يكون EYEWORK_REGISTRATION=open.
-- الوضع يقرّره الخادم: ew_register_open دالّةٌ مستقلّة لا يستدعيها في وضعي
-- code وclosed، وew_register برمزه باقٍ على شرطه: لا حساب به بلا رمزٍ صالح.
--
-- ما تضمنه القاعدة في الطريقين: لا يُستولى على بريدٍ قائم (ولا على دعوةٍ لم
-- تُفعَّل)، والاسم والتاريخ والموافقة والمهنة تُفحص كما في 0005، وسقوفٌ يومية
-- للحسابات الجديدة لا يُفرغها حذف.
--
-- **دفتر التسجيل.** صفٌّ لكل تسجيلٍ نجح، ولكل جواب «البريد مأخوذ» بلا رمز:
-- وقته وطريقه ونتيجته فقط — لا حساب ولا بريد ولا عنوان. منه تُعدّ السقوف، فلا
-- يُفرغها حذف الحساب، ويحذفه purge بعد يومه.
--
-- **الحساب المفتوح الجديد** (open_registered، في أيامه السبعة الأولى): عشرة
-- طلبات كتابةٍ في اليوم بدل أربعين، وأربعمئة في اليوم للحسابات الجديدة كلّها
-- من ألفي التطبيق، وثلاث حملاتٍ مفتوحة بدل عشرين. فحساباتٌ تُنشأ بالجملة لا
-- تستنفد ما لأصحاب الحسابات القائمة، ولا تملأ القرص بالصور.
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

-- تسألها الواجهة قبل الخطوة الأولى من التسجيل المفتوح، فلا يكتب أحدٌ تسع شاشاتٍ
-- بالنظر ليسمع في آخرها أن اليوم اكتمل. حالُ التطبيق كلّه، لا شيء عن أحد.
CREATE FUNCTION ew_open_registration_blocker() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_registration_blocker('OPEN')
$$;

-- ── التسجيل برمز: كما في 0005، والسقف من الدفتر ─────────────────────────
CREATE OR REPLACE FUNCTION ew_register(
    p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text
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
    -- قفلٌ واحد للطريقين: تسجيلان متزامنان لا يريان العدّ نفسه فيمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('CODE');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
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
    p_terms_version text
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
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('OPEN');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, open_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession, true, true, p_terms_version, now())
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
-- تستدعيهما دوالّ المالك بصلاحيته؛ دور الويب لا يحتاجهما.
REVOKE ALL ON FUNCTION ew_new_open_account(uuid), ew_registration_blocker(text),
                       ew_open_registration_blocker(),
                       ew_register_open(bytea, text, text, date, text, text),
                       ew_my_generation_limit() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_open_registration_blocker(),
                          ew_register_open(bytea, text, text, date, text, text),
                          ew_my_generation_limit() TO eyework_app;
```

### 6.3 `migrations/0007_open_registration.down.sql` (exact)

The four functions in the middle are copied word for word from main's `0005_registration.up.sql`, with `CREATE FUNCTION` changed to `CREATE OR REPLACE FUNCTION` where 0005 created them. They were generated, not retyped (§13).

```sql
-- ════════════════════════════════════════════════════════════════════════
-- 0007_open_registration — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- 0005 يضمن ألّا حساب يُسجَّل بلا رمز. حسابٌ مفتوح بعد التراجع يخالف ما يصفه
-- مخطّطه، ويفقد حدود أسبوعه الأول بصمت. فلا تراجع وفي القاعدة واحدٌ منه. والقفل
-- أولاً: تسجيلٌ لم يُثبَّت بعد لا يراه العدّ، فينتظره التراجع ثم يعدّه.
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

-- الدوالّ الأربع كما كانت في 0005، حرفاً بحرف.
CREATE OR REPLACE FUNCTION ew_attempt_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome) VALUES (OLD.started_at, OLD.outcome);
    END IF;
    RETURN OLD;
END
$$;

CREATE OR REPLACE FUNCTION ew_register(
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

DROP FUNCTION IF EXISTS ew_my_generation_limit();
DROP FUNCTION IF EXISTS ew_register_open(bytea, text, text, date, text, text);
DROP FUNCTION IF EXISTS ew_open_registration_blocker();
DROP FUNCTION IF EXISTS ew_registration_blocker(text);
DROP FUNCTION IF EXISTS ew_new_open_account(uuid);

ALTER TABLE attempt_tombstones  DROP COLUMN IF EXISTS new_account;
ALTER TABLE generation_attempts DROP COLUMN IF EXISTS new_account;
ALTER TABLE users DROP CONSTRAINT IF EXISTS open_registered_is_self_registered;
ALTER TABLE users DROP COLUMN IF EXISTS open_registered;

DROP TABLE IF EXISTS registration_ledger;
```

### 6.4 Verified on PostgreSQL 16.13 (scratch database `regspec0007_check`, dropped afterwards)

- 0001–0006 from main, then 0007 up, down, up: the `pg_dump --schema-only` after down is identical to the one before up, and the second up is identical to the first.
- A full down from 0007 to empty and back up reproduces the 0007 schema exactly.
- 0007 down with one open account refuses with the HINT, and the database stays at 0007. After deleting that account, down succeeds and up succeeds again.
- Twenty functional checks pass as `eyework_app` (§13: `check_0007.py`). They cover:
  - creation and the ledger row;
  - no takeover of an existing account or a pending invitation;
  - field checks, with no ledger row on refusal;
  - the open cap, the total cap, and that deletion makes no room;
  - the pause, and that operator links still work while it is on;
  - the availability check;
  - TAKEN through a code counting only on the code;
  - every web-role denial (SELECT, INSERT, DELETE and TRUNCATE on the ledger, the two internal helpers, `users.open_registered`);
  - the ledger's columns and its CHECK;
  - two concurrent registrations, where one waits on the lock and is then refused;
  - `ew_my_generation_limit` (10, 40, NULL);
  - the new-account daily cap, and 40 after 7 days;
  - the pool of 400, counting the traces of a deleted account, with established accounts unaffected;
  - the 3-campaign cap;
  - `open_registered ⇒ self_registered`.

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

`load()` reads the mode once and passes it to both: `registration=mode, support_contact=_support_contact(mode)`. The field `registration_open: bool` is removed. Callers read `settings.registration`.

### 7.2 `auth.py`

- **New SQL constants:**
  - `_REGISTER_OPEN = "SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s)"`
  - `_OPEN_BLOCKER = "SELECT ew_open_registration_blocker() AS blocker"`
- **`register(db, key, *, code: str | None, name, birth_date, email, password, profession)`.**
  - With `code is None`, it calls `_REGISTER_OPEN` with `(login_hmac(key, email), password_hash, name, birth_date, profession.value, TERMS_VERSION)`. Otherwise it is unchanged.
  - The scrypt hash is still computed before the database call, so a request costs the same either way.
  - The exception is still raised after the `with` block, which keeps the TAKEN ledger row.
- **`open_registration_blocker(db) -> str | None`** returns the name of the constraint that blocks open registration right now, or `None`.
- **`TERMS_VERSION`** is bumped (§9).
- **Docstrings.**
  - The module's «حسابٌ بالتسجيل أو بالدعوة» paragraph adds the third route.
  - `RegistrationTaken` says it is counted on the code, or in the ledger and the network budget.

### 7.3 `campaigns.py`

```python
#: نظيرا ew_begin_generation وew_my_generation_limit (0007). اختبارٌ يقارنهما بالقاعدة.
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

`remaining_generations` is removed, and its only caller (`/api/me`) uses `generation_allowance` instead.

### 7.4 `rate_limit.py` (stays pure)

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

### 7.5 `web/deps.py`

```python
    #: التسجيل بلا رابط لكل شبكة (عنوان IPv4، أو /64 من IPv6): خمسٌ في الساعة، وعشرٌ في اليوم.
    register_open_net: RateLimiter
    register_open_net_day: RateLimiter
    #: أجوبة «البريد مأخوذ» بلا رابط لكل شبكة: ثلاثٌ في اليوم ثم لا جواب — نظير قفل الرمز بعد ثلاث.
    taken_open_net: RateLimiter
    #: «هل يُنشأ حسابٌ بلا رابطٍ الآن؟» قبل الخطوة الأولى.
    registration_check_net: RateLimiter
    # default():
    #   register_open_net=RateLimiter(RateLimit(5, 3600.0)),
    #   register_open_net_day=RateLimiter(RateLimit(10, 86400.0)),
    #   taken_open_net=RateLimiter(RateLimit(3, 86400.0)),
    #   registration_check_net=RateLimiter(RateLimit(30, 3600.0)),


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

### 7.6 `web/errors.py`

```python
# REGISTRATION
"LINK_REQUIRED": ErrorSpec(403, "REGISTER_LINK", "التسجيل هنا برابطٍ ممّن يدير التطبيق. اطلبه منه."),

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
```

The existing `registration_daily_cap` entry is unchanged. Every constraint raised by 0007 reaches the existing `IntegrityError` handler by name. That handler logs only the constraint name and the path; no email, no address.

### 7.7 `web/schemas.py`

`RegisterBody.code: SignupCode | None = None`. The docstring says the code is absent on the open path. `extra="forbid"` stays.

### 7.8 `web/routes_auth.py`

```python
def _constraint_error(name: str) -> JSONResponse:
    spec = CONSTRAINTS[name]
    headers = {"Retry-After": str(spec.retry_after)} if spec.retry_after else None
    return JSONResponse(status_code=spec.status, headers=headers, content={"code": spec.code, "detail": spec.detail})


@router.get("/auth/registration", status_code=status.HTTP_204_NO_CONTENT)
async def registration(request: Request) -> Response:
    """
    هل يُنشأ حسابٌ بلا رابطٍ الآن؟ تسأله الواجهة قبل الخطوة الأولى، فلا يكتب أحدٌ تسع شاشاتٍ
    بالنظر ليسمع في آخرها أن اليوم اكتمل. حال التطبيق كلّه: لا بريد فيه ولا يقول شيئاً عن أحد.
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
            birth_date=birth_date, email=email, password=body.password, profession=body.profession)
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
```

**Order of checks, which matters for the enumeration guarantees:**

1. Mode.
2. Request schema (422 `INVALID`).
3. Field checks (422 per field; no limiter is consumed).
4. Per-network limiters (429), checked before anything reaches the database.
5. The database, in this order: the field checks again, the caps and the pause (503, the same for every email), then the insert (409 TAKEN, or 204).

**Other routes:**

- `signup_code` changes its test to `state.settings.registration == "closed"`.
- `/api/choices`:
  - `registration_open` stays, now meaning `mode != "closed"`.
  - New `support_contact`.
  - New `registration.mode`.
- `/api/me` returns `{"generations_left": left, "generation_limit": daily, "display_name": …, "profession": …}`. Neither the email nor the birth date is ever returned, as today.

### 7.9 `admin.py`

- `purge` adds `("registration_ledger", "DELETE FROM registration_ledger WHERE occurred_at < now() - interval '24 hours'")`.
- The module docstring:
  - names the open route;
  - keeps `--owner-verified` for recovering self-registered accounts;
  - describes the squatting process (§4.4).
- No new command. The operator sees pauses and full days in the existing warning log («قيد registration_open_paused على /api/auth/register»).

### 7.10 Other server files

- `tests/conftest.py`: `_CLEAN = "TRUNCATE users, attempt_tombstones, registration_ledger RESTART IDENTITY CASCADE"`.
- `README.md`:
  - «التسجيل» covers three routes, the modes, `EYEWORK_SUPPORT_CONTACT`, the limits in §5 and the trade-off in §4.
  - The retention table gets a row: «دفتر التسجيل (وقت كل تسجيلٍ وكل جواب «مأخوذ» بلا رابط، بلا هوية) — بعد 24 ساعة (`purge`)».
  - The paragraph «التسجيل المفتوح بلا رابط» under «ما لم يُبنَ» is removed.
  - The «ما يُخزَّن عن الشخص» paragraph adds: «وفي الوضع المفتوح يعرف من يحاول التسجيل ببريدٍ أن له حساباً».

---

## 8. Client changes (vanilla `static/`, the code of record)

### 8.1 Sign-in screen (`index.html`, `app.js`)

```html
<header class="bar bar--top">
    <div class="slot"></div>
    <p class="step"></p>
    <!-- «أنشئ حساباً» في الطرف الأعلى الأيسر كـ«حسابي» في الرئيسية: موضعه في الإشعار
         فارغ، وأقرب ما إليه هناك «رجوع» لا «أوافق وأتابع». يظهر في الوضع المفتوح وحده. -->
    <div class="slot"><button class="btn" type="button" id="login-signup" data-safe hidden>أنشئ حساباً</button></div>
</header>
…
<p class="help" id="login-help">تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل.</p>
```

- **Hidden button keeps its slot.** `[hidden] { display: none !important }` is already global, and the slot keeps `min-width`, so nothing moves when the button is hidden.
- **`renderLogin()`.** It runs before choices load when start-up fails, so it guards against missing choices:

  ```js
  const mode = state.choices ? state.choices.registration.mode : null;
  $('login-signup').hidden = mode !== 'open';
  const contact = state.choices && state.choices.support_contact;
  if (mode === 'open' && contact) {
      const address = UI.bdi(contact);
      address.dir = 'ltr';
      $('login-help').replaceChildren('نسيت كلمة المرور؟ اكتب إلى ', address);
  } else {
      $('login-help').textContent = 'تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل.';
  }
  ```

- **Wiring:** `$('login-signup').addEventListener('click', () => startSignup('login'));`. It listens to click only, so touch and gaze behave the same.
- **While an alert is open,** `UI.showAlert` disables the entry like every other bar button. The CSS that keeps top slots at least 24 px from «حسناً» already covers it; this was measured (§8.4).
- **Measured.**
  - Adding the entry leaves the sign-in layout exactly as on main: same heights, same audit results, with and without an alert.
  - Main's sign-in help line already overflows by 3 px at Text Size 23 and 53, in both the 320 and 375 px frames.
  - The shorter open-mode line above («نسيت كلمة المرور؟ اكتب إلى ‹contact›») still overflows, but only at 320 px.
  - So the sign-in redesign has to make room for the help line. §10.3 adds the test that will catch it.

### 8.2 The nine steps (`portal.js`, `index.html`)

**Starting.**

```js
/* التسجيل بلا رابط (EYEWORK_REGISTRATION=open)، من «أنشئ حساباً». البيانات في الذاكرة وحدها. */
function blankSignup(code, from) {
    return { code, from, checked: false, agreed: false, name: '', year: null, month: null, day: null,
             profession: null, email: '', alert: null };
}

function startSignup(from) {
    if (state.busy) {
        return;
    }
    state.signup = blankSignup(null, from);
    go('#/signup');
}
```

`captureSignup()` uses `blankSignup(code, 'login')`.

**The check before the first step** (in `renderSignup`):

```js
const s = state.signup;
const result = s.code
    ? await api('POST', '/api/auth/signup-code', { json: { code: s.code } })
    : await api('GET', '/api/auth/registration');
if (nav !== state.nav || state.signup !== s) {
    return;
}
if (result.status !== 204) {
    const final = result.status === 422 || (result.data && ['REGISTER_CODE', 'REGISTER_CLOSED',
        'REGISTER_LINK', 'REGISTER_FULL', 'REGISTER_PAUSED'].includes(result.data.code));
    if (final) {
        // لا فائدة من المحاولة اليوم: يُترك التسجيل، ويعود الوسم إلى حيث بدأ.
        state.signup = null;
        history.replaceState(null, '', s.from === 'welcome' ? '#/welcome' : '#/login');
    }
    const origin = s.from === 'welcome' ? renderWelcome() : renderLogin();
    let message = result.status === 422 ? SIGNUP_LINK_INVALID : detail(result);
    if (final && s.code && state.choices.registration.mode === 'open') {
        message += ' ويمكنك إنشاء حسابٍ بلا رابط من «أنشئ حساباً».';
    }
    UI.showAlert(origin, final ? message : `${message} «حسناً» تعيد المحاولة.`);
    return;
}
s.checked = true;
```

- The existing «حسناً» handler retries an unchecked sign-up on `login`. Add the same branch for `welcome` if that screen exists.
- `renderWelcome()` is the design track's. Without a welcome screen, `from` is always `'login'`; drop the `welcome` branches then rather than leaving dead references.

**Reload in the middle** (`state.signup` lost while the hash is still `#/signup…`):

- In `open` mode the sign-up starts over at the notice: `state.signup = blankSignup(null, 'login'); state.signup.alert = 'أُعيد تحميل الصفحة، فبدأ التسجيل من أوله.'; go('#/signup', { replace: true });`
- In `code` mode the existing «افتح رابط التسجيل من جديد.» stays.
- Nothing is lost either way, since nothing was sent before the last step.

**Back from the notice.** `signupParent('signup-notice')` returns `'#/welcome'` when `state.signup.from === 'welcome'`, otherwise `'#/login'`.

**Entry from outside this page: `#/signup/new`.** The React AuthForm's «ابدأ التسجيل» and any link opened from a home-screen shortcut need a way to start a sign-up without a link. They use this route.

- `renderSignup('new')` is handled before the `!state.signup` check, the same way in every mode: `state.signup = blankSignup(null, 'login'); go('#/signup', { replace: true });`, with no alert.
- The check before the first step then does the rest:
  - in `open` mode, `GET /api/auth/registration` returns 204 and the notice opens;
  - in `code` or `closed` mode, it returns 403 `REGISTER_LINK` or `REGISTER_CLOSED`, and the sign-in screen shows the server's own text. The client writes no copy of its own for this.
- `new` matches the existing route pattern (`[a-z]+`) and is not a step name, so step order is unaffected.

**Creating the account.** `onSignupCreate` builds the body without `code` unless there is one:

```js
const json = { name: s.name, birth_date: birthDate(), email: s.email, password,
               profession: s.profession, accept_terms: true };
if (s.code) {
    json.code = s.code;
}
```

`REGISTER_FULL`, `REGISTER_PAUSED` and `RATE` at this step stay on the password screen as an alert; that is the existing fallback for errors without a field. A TAKEN answer goes back to the email step, as today.

**Copy changes:**

- Profession help, static, the same in every mode: «تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ ممّن يدير التطبيق.»
- Email step: a new line under the field, static, true in every mode:
  `<p class="help" id="signup-email-help">من يحاول التسجيل بهذا البريد يعرف أن له حساباً هنا. إن كان ذلك يضرّك فاختر بريداً لا يعرفه غيرك.</p>`
- Review help (`#signup-review-help`), set by `renderSignupReview()`:
  - With a contact: «لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به. إن نُسيت كلمة المرور فاكتب إلى ‹contact› من هذا البريد.» The contact goes in a `bdi dir=ltr`.
  - Without one, today's text.
- Notice: §9.

### 8.3 Welcome screen (only if the design track adds one)

- `#welcome-signup` («أنشئ حساباً») and `#welcome-login` («ادخل»). Both are `data-safe`, at least 72×72 px, at least 24 px apart and at least 16 px from the edges, and listen to click only.
- After a press of `#welcome-signup`, the nearest enabled control on the notice must not be `#signup-agree`. A test enforces this.
- After «رجوع» on the notice, nothing that commits sits under or nearest to the pressed spot on the welcome screen.
- No welcome control may sit in the bottom-end slot. That is where «أوافق وأتابع» appears on the notice.

### 8.4 Measured geometry

Measured with the repo's `LANDING` and `NEAREST` scripts on the variant in §13.

| Frame | After «أنشئ حساباً» (notice) | After «رجوع» on the notice (sign-in) |
|---|---|---|
| 375×635 | nothing under the spot; nearest is «رجوع», 143–231 px away | nothing under the spot; nearest is the username field (100–156 px) or the entry (143 px) |
| 390×664 | nearest «رجوع», 158–246 px | nearest the username field |
| 390×763 | nearest «رجوع», 158–246 px | nearest the username field |
| 320×635 | nearest «رجوع», 128–196 px | nearest the username field or the entry (128 px) |
| 1280×800 | nearest «رجوع», 182–270 px | nearest the username field |

- «أوافق وأتابع» is never the nearest control, and nothing that commits is either under the spot or nearest to it.
- A gaze resting at top-left can go back and forth between «أنشئ حساباً» and «رجوع». That is the same non-committing pair the contract already accepts for «حسابي» and «رجوع».

### 8.5 21st.dev and the React client

The owner asked for 21st.dev for interfaces and components. For this track, that means the following.

- **Pattern.** The entry follows the 21st.dev sign-in block: a primary sign-in form plus a secondary «create account» action. `a519ddb` ported that AuthForm into `eyework/client/`.
- **Porting, not importing.** The CSP is `self` only, so components are copied into the repo and rebuilt with the existing tokens. Nothing loads from 21st.dev, a CDN, Tailwind's runtime or Google Fonts.
- **The gaze contract overrides component defaults.** The usual 21st.dev «Don't have an account? Sign up» inline text link would fail it: the target is too small and it often sits next to the commit button. It must become the full 72×72 button in the top-end slot described above, with the same id (`login-signup`). The rules in §8.3 apply to any 21st.dev hero or welcome block.
- **The React AuthForm (`a519ddb`).** It already starts the step-by-step sign-up rather than a six-field form: the «حساب جديد» tab, then «ابدأ التسجيل». When it is served, it needs four things:
  1. `onStartSignup` goes to `/#/signup/new`, not `/#/signup`. Under this spec, a bare `#/signup` with no sign-up in memory is the "page reloaded" path and shows that alert.
  2. It reads `registration.mode` from `/api/choices`. It shows «حساب جديد» only in `open` mode. In `code` mode, the panel says «التسجيل هنا برابطٍ ممّن يدير التطبيق.» and has no start button. In `closed` mode the tab is hidden.
  3. The consent rule in §8.3 applies to its «ابدأ التسجيل». After the press, the notice's «أوافق وأتابع» must not be the nearest control to the pressed spot. In the current layout that button is full width in the content area, so this must be measured once the client is served.
  4. The two clients name the entry differently: «أنشئ حساباً» on the static sign-in screen, as the owner's brief says, and «حساب جديد» as the React tab. The design track should pick one name when it moves the screens.

---

## 9. Consent notice and `TERMS_VERSION`

**The notice** (`signup-notice`, `index.html`). This is main's `2026-10-09` wording with two edits: the operator replaces the link-giver, and one sentence is added at the end.

```html
<p class="line">يُحفظ في هذا التطبيق: الاسم، وتاريخ الميلاد، والمهنة، وكلمة المرور مجزّأة، وبصمة البريد لا البريد، فلا يصله شيء ولا يُستردّ الحساب به.</p>
<p class="line">في بوابة التسويق تُرسَل صورة المنتج ونصّه، دون الاسم والميلاد، إلى Anthropic خارج المملكة للصياغة، وتحذفها خلال 30 يوماً إلا ما تُبقيه سياستها أو القانون.</p>
<p class="line">تحذف حسابك وبياناته متى شئت، أو يحذفه بطلبك مَن يدير التطبيق؛ والنسخ الاحتياطية الأقدم تبقى حتى تُحذف. ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.</p>
```

- **Mode-neutral.** The text is the same in all three modes and is true in each, so one version covers all of them.
- **Removed clause.** «إن أُوقف أو نسيت كلمة مرورك» is dropped to make room. «يحذفه بطلبك مَن يدير التطبيق» still covers both cases.
- **Fit.** Measured with the repo's `AUDIT`, the notice fits with no scroll and nothing clipped:
  - at 320×635, 375×635 and 390×664;
  - at the default text size and at Text Size 17, 23 and 53 (the content cap is 19 px).
  - For comparison, the same edits on the older four-line wording (`fa84cd1`) overflow at 320×635 at every text size. On main's wording, putting the sentence on the first line instead of the last overflows at 320×635 at 23 and 53. The placement above is the one that fits.
- **Digest.** The normalised text the test hashes (via `tests/unit/test_terms.py::_notice_text`) gives `30af143db9054102da493deb9ce927549e0372ed856f5672519bf31843d37ff2`.

**`TERMS_VERSION`** becomes the release date of this change.

- It must be later than every key already in `DIGESTS` on main: `2026-10-08` and `2026-10-09`.
- Add `"<that date>": "30af143d…"` to `DIGESTS` and keep the old entries.
- The shape check allows one version per day. If no account has ever accepted `2026-10-09` (it is on main, but may not be deployed), this text may take that date with the new digest instead. Precedent: `fa84cd1` replaced the digest of an unreleased version. That choice is decision 7.

---

## 10. Tests

What each test proves is in *italics*.

### 10.1 Database: `tests/db/test_open_registration.py` (new)

1. `test_an_open_registration_creates_an_active_open_account_and_one_ledger_row`: *the account is active, `self_registered`, `open_registered`, carries the terms version, and the ledger has exactly one `(OPEN, OK)` row.*
2. `test_an_open_registration_never_takes_over_an_account_or_a_pending_invitation`: *both come back TAKEN; display name, profession, password and `self_registered` are untouched; one `(OPEN, TAKEN)` row each.*
3. `test_an_open_registration_checks_name_birth_consent_and_profession` (parametrised over no name, a bad name shape, no consent, before 1900, tomorrow in Riyadh, an unknown profession): *each raises its named constraint (or a FK violation), exactly as the code path does.*
4. `test_a_refused_open_registration_leaves_no_ledger_row`: *an exception rolls back the ledger write, so refusals cannot pause registration.*
5. `test_the_open_daily_cap_counts_open_accounts_of_the_last_day`: *149 `(OPEN, OK)` rows plus TAKEN rows plus rows older than 24 h → the 150th succeeds and the 151st raises `registration_open_daily_cap`; a code registration still succeeds.*
6. `test_the_total_daily_cap_counts_both_ways`: *100 `(OPEN, OK)` + 99 `(CODE, OK)` → the 200th by code succeeds; the next by code and the next without a link both raise `registration_daily_cap`.*
7. `test_deleting_accounts_makes_no_room_under_either_cap`: *`ew_delete_me` and an owner `DELETE` both leave the ledger, and the cap stays full.*
8. `test_sixty_taken_answers_pause_open_registration_but_not_links`: *59 rows from today plus old rows plus one live TAKEN → a free email raises `registration_open_paused`; `ew_open_registration_blocker()` says so; a code registration succeeds.*
9. `test_the_availability_check_names_the_blocker_or_nothing`: *NULL on an empty day, the constraint name when full; callable by the web role without a session.*
10. `test_a_taken_answer_through_a_link_counts_on_the_link_only`: *`taken_count` goes up and the ledger gets no row (the CHECK forbids `(CODE, TAKEN)` anyway).*
11. `test_a_code_registration_writes_one_ledger_row`: *every OK, by either route, is counted in one place.*
12. `test_the_web_role_cannot_touch_the_ledger_or_the_internal_helpers` (parametrised: SELECT, INSERT, DELETE, TRUNCATE on the ledger; `ew_registration_blocker`, `ew_new_open_account`, `SELECT open_registered FROM users`): *each is refused with `permission denied`.*
13. `test_the_ledger_holds_no_identity`: *the columns are exactly `occurred_at, outcome, via`, and `(CODE, TAKEN)` is refused by name.*
14. `test_two_open_registrations_cannot_both_take_the_last_place`: *with 149 rows, the second transaction waits on the advisory lock (uses `test_state_machine.blocked_on_a_lock`) and then raises the cap.*
15. `test_the_generation_limit_is_ten_for_a_new_open_account_and_forty_otherwise`: *10 for a new open account; 40 for code, invited and older accounts; NULL with no session or for an inactive user; the values equal `campaigns.NEW_ACCOUNT_DAILY_GENERATIONS` and `DAILY_GENERATIONS`.*
16. `test_the_new_account_week_is_measured_by_the_database`: *a `created_at` of 7 days minus 1 minute is new; 7 days plus 1 minute is not.*
17. `test_a_new_open_account_writes_ten_times_a_day_then_forty_after_its_first_week`: *ten billable attempts an hour ago → `generation_new_account_cap`; after aging `created_at` by 8 days, `ew_begin_generation` succeeds and marks `new_account = false`.*
18. `test_unbilled_failures_do_not_count_toward_the_new_account_limits`: *`UPSTREAM_BUSY` attempts do not use up the 10 or the 400, the same rule as the existing caps.*
19. `test_new_open_accounts_share_four_hundred_a_day_counting_deleted_ones`: *400 `new_account` attempts by an account later deleted → 400 tombstones with `new_account`; another new account is refused with `generation_new_accounts_cap`; an established account still starts a generation.*
20. `test_a_new_open_account_opens_three_campaigns_and_others_twenty`: *the 4th draft raises `new_account_campaign_cap`; an established account opens its 4th.*
21. `test_open_registered_implies_self_registered`: *the owner cannot write an open account that is not self-registered.*

**Changes to existing database tests:**

- `test_registration.py`:
  - `test_the_daily_cap_counts_the_codes_used_in_the_last_day` → `test_the_daily_cap_counts_the_ledger_of_the_last_day`, seeding `(CODE, OK)` rows instead of used codes. *The cap's source moved.*
  - The deletion test is unchanged and must still pass.
  - The module docstring adds the third route.
- `test_roles_and_grants.py`:
  - `ALL_TABLES` and the DELETE/TRUNCATE parameters add `registration_ledger`.
  - `APP_FUNCTIONS` adds `ew_register_open`, `ew_open_registration_blocker` and `ew_my_generation_limit`.
  - New INSERT/UPDATE refusal parameters for `registration_ledger`.
  - *The catalogue shows no wider grant than these three.*
- `test_rls.py`: `RLS_TABLES` adds `public.registration_ledger`. *RLS is enabled and forced.*
- `test_generation_caps.py`: `test_the_trace_of_a_deleted_attempt_has_no_identity…` now expects the columns `["new_account", "outcome", "started_at"]`. *The tombstone gains a flag, not an identity.*
- `test_purge.py`: new `test_registration_ledger_rows_go_after_their_day`. *A row from 25 h ago is deleted, one from 1 h ago is kept, and `purge()["registration_ledger"]` reports it.*
- `test_migrations.py`:
  - `SNAPSHOT_MUST_COVER` adds `ALTER TABLE ONLY public.registration_ledger FORCE ROW LEVEL SECURITY;`
  - New `test_0007_backfills_the_ledger_from_codes_used_in_the_last_day`: *migrate down to 0006, then insert codes used 1 h ago (with an account), 2 h ago (account deleted), 25 h ago, and one unused; migrate up to 0007 → exactly two `(CODE, OK)` rows, at those times.*
  - New `test_0007_down_refuses_while_open_accounts_exist`: *refuses with «1 حساباً», the ledger still says 0007, and down works after the delete.*
  - New `test_0007_down_waits_for_an_open_account_being_created_and_still_refuses`: *same pattern as the 0005 test.*
  - The existing up/down/up tests cover 0007 automatically.

### 10.2 API: `tests/api/test_open_registration_api.py` (new)

The API `browser` factory gains an `address` argument, passed to `TestClient(client=(address, 50000))`; Starlette 1.6 supports it.

1. `test_registering_without_a_link_signs_in_with_the_new_account_limits`: *204, cookie set; `/api/me` returns `generations_left: 10, generation_limit: 10`, the name and the profession, and no email or birth date; the database shows `open_registered`.*
2. `test_a_link_still_works_in_open_mode_and_its_account_is_not_new`: *the code is consumed; `open_registered` is false; the limit is 40.*
3. `test_an_unusable_link_is_refused_even_in_open_mode`: *410 `REGISTER_CODE`, zero users. A bad link never quietly turns into an open registration.*
4. `test_code_mode_refuses_registration_without_a_link_before_anything_else`: *403 `REGISTER_LINK` even with an invalid name; no user and no ledger row.*
5. `test_closed_mode_refuses_every_route` (register with and without a code, signup-code, `GET /api/auth/registration`): *403 `REGISTER_CLOSED`.*
6. `test_the_choices_name_the_mode_and_the_contact` (open, code, closed): *`registration.mode`, `registration_open`, `support_contact`.*
7. `test_a_taken_email_is_refused_without_touching_the_account_and_counted`: *409 `REGISTER_TAKEN` with field TAKEN; the account is unchanged; one `(OPEN, TAKEN)` row.*
8. `test_three_taken_answers_close_the_open_path_for_that_network`: *from 203.0.113.7: three 409s, then a free email gets 429 `RATE` with Retry-After, and no fourth ledger row or new user; 198.51.100.9 still gets 204; a link from 203.0.113.7 still works.*
9. `test_open_registrations_are_limited_per_network_and_field_errors_do_not_count`: *five 422s, then five 204s, then 429.*
10. `test_the_daily_per_network_limit_holds_after_the_hourly_one_resets`: *with `eyework.rate_limit.monotonic` patched forward by 61 minutes: five more 204s, then the 11th in the day gets 429.*
11. `test_ipv6_addresses_in_one_64_share_a_budget`: *`2001:db8:1:2::10` and `2001:db8:1:2:ffff::1` share one budget; `2001:db8:1:3::1` does not; `::ffff:203.0.113.7` counts as `203.0.113.7`.*
12. `test_a_full_day_answers_the_same_for_taken_and_free_emails`: *with 150 `(OPEN, OK)` rows, both get identical 503 `REGISTER_FULL` bodies and Retry-After; the check route says the same.*
13. `test_a_paused_day_answers_the_same_for_taken_and_free_emails_and_links_still_work`: *503 `REGISTER_PAUSED` for both; a code registration gets 204.*
14. `test_the_availability_check_is_limited_per_network`: *the 31st request in an hour gets 429.*
15. `test_the_availability_check_changes_nothing_and_needs_no_write_headers`: *a GET without `X-Eyework` gets 204, and the ledger is unchanged.*
16. `test_each_invalid_field_names_itself_without_a_link`: *the existing field parameters, without a code: 422 with the field name and zero users.*
17. `test_registering_without_a_link_needs_the_write_headers`: *403 `ORIGIN`, zero users.*
18. `test_a_new_open_marketing_account_writes_ten_times_a_day`: *ten billable attempts seeded an hour ago, then `/copy` gets 429 `AI_NEW_DAILY` with Retry-After 3600; after `created_at` is aged 8 days, it gets 200.*
19. `test_a_new_open_account_opens_three_campaigns`: *the 4th `POST /api/campaigns` gets 409 `NEW_OPEN_CAP`.*

**Changes to `test_registration_api.py`:**

- `closed_server` builds `Settings(..., registration="closed")`.
- `/api/me` expects `generation_limit: 40`.
- `test_the_choices_list_the_professions` also asserts `registration.mode == "open"`.
- `_body` sends `code` only when given.

### 10.3 Browser: `tests/ui/test_open_registration.py` (new)

The sign-up walk in `test_portals.test_signing_up_from_the_link_to_the_portal` moves into a shared `walk_signup(flow, page)` helper; the link test keeps using it. A fixture `registration_settings(**changes)` swaps `server["app"].state.settings` with `dataclasses.replace` and restores it afterwards; routes read the settings on every request.

1. `test_signing_up_from_the_sign_in_screen_to_the_portal` (all 5 frames):
   - *The sign-in screen with its entry, and every step, pass the audit: size, gap, edges, at most 10 targets, no scroll, nothing clipped.*
   - *On handheld frames, the landing and nearest-control rules hold after every press.*
   - *`_gaze_safe`: no timers, no hover listeners.*
   - *Exactly one `GET /api/auth/registration` before the notice and one `POST /api/auth/register` at the end, whose body has no `code` key.*
   - *The database row is `open_registered`.*
2. `test_the_press_that_opens_the_notice_never_has_the_consent_button_nearest` (handheld frames): *for the entry press, no `flow.nearest` entry names `signup-agree`, and none commits.*
3. `test_back_from_the_notice_returns_to_the_sign_in_screen_with_nothing_committing_nearest`.
4. `test_the_entry_is_absent_in_code_and_closed_modes`: *`#login-signup` is not visible; typing `#/signup` shows sign-in with «افتح رابط التسجيل من جديد.»; no GET to the check route.*
5. `test_a_full_or_paused_day_is_said_before_the_first_step` (`REGISTER_FULL`, `REGISTER_PAUSED` via `page.route`): *a sign-in alert carries the server's text; the notice never appears; the hash is `#/login`; «حسناً» sends nothing.*
6. `test_a_failed_check_keeps_the_sign_up_and_tries_again` (offline, 429): *the alert ends with «حسناً» تعيد المحاولة; «حسناً» leads to the notice.*
7. `test_reloading_in_the_middle_starts_over_at_the_notice`: *after a reload at `#/signup/email`, the notice shows «أُعيد تحميل الصفحة، فبدأ التسجيل من أوله.»; no POST.*
8. `test_a_taken_email_returns_to_the_email_step_and_a_new_one_succeeds`.
9. `test_the_sign_in_screen_keeps_the_contract_with_an_alert_open`: *after a failed sign-in, the audit passes with «حسناً» and the disabled entry both visible; after «حسناً», nothing that commits is nearest.*
10. `test_the_contact_is_shown_where_recovery_is_explained`: *with a contact, `#login-help` and `#signup-review-help` hold it in `bdi[dir=ltr]`; with none (code mode), the link texts.*
11. `test_a_used_link_in_open_mode_offers_signing_up_without_it`: *the alert ends with «من «أنشئ حساباً».», and the entry is visible.*
12. `test_a_second_press_while_the_check_is_in_flight_sends_nothing_more`: *with the route held by `page.route`, a double press sends exactly one GET.*
13. `test_the_new_sign_up_route_starts_without_a_link_and_without_an_alert`: *in `open` mode, `goto('/#/signup/new')` leads to the notice with no alert and one GET to the check route. In `code` mode it leads to sign-in with «التسجيل هنا برابطٍ ممّن يدير التطبيق. اطلبه منه.».*

**Changes to existing browser tests:**

- `test_text_size.py` adds, at TIGHTEST × sizes [17, 23, 53]:
  - the sign-in screen with its entry, and the same with an alert;
  - the walk without a link (notice, email with its new line, review with the contact).
  - *This closes a real gap: the sign-in screen is not audited at larger Text Sizes today. My measurement of main's sign-in screen puts the help line 3 px over at 23 and 53 at 320 and 375 px, before any change in this spec. The design track's sign-in redesign must fix that or this test fails.*
  - *Adding the entry to the top slot does not change the sign-in layout: measured identical to main.*
- `test_touch.py`: *the walk without a link by tap alone.*
- `test_portals.py`: *the link walk is unchanged in `open` mode and makes no `GET /api/auth/registration`.*

### 10.4 Unit and architecture

- `tests/unit/test_config_registration.py` (new): *unset means open and requires a contact; open with a contact; code and closed without one; an unknown mode fails; an invalid contact fails; the contact is normalised (NFKC, lowercase).*
- `tests/unit/test_config_sdk_env.py`: `base_env` sets `EYEWORK_SUPPORT_CONTACT`. *Without it, the new default would stop the app from starting.*
- `tests/unit/test_rate_limit.py` (new): *`blocked()` records nothing and returns the wait; `record()` counts; the sweep still drops stale keys.*
- `tests/unit/test_client_network.py` (new): *IPv4 maps to itself, IPv6 to its /64, IPv4-mapped to IPv4, and a non-address string to itself.*
- `tests/unit/test_terms.py`:
  - `DIGESTS` adds the new version.
  - *New assertions: the notice names «مَن يدير التطبيق», contains no «أعطاك الرابط», and contains «ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا».*
- Architecture: no change. *The existing rules must still pass: no timers, no storage, click only, no wall clock, no SQL formatting, nothing unfinished.*

---

## 11. Rollout and rollback

1. Ship the code with the migration. Run `python -m eyework.migrations.run up` with the owner role.
2. **Existing deployments.** Before restarting, choose one:
   - set `EYEWORK_SUPPORT_CONTACT`, which opens registration; or
   - set `EYEWORK_REGISTRATION=code`, which keeps today's behaviour.

   A restart with neither fails with a `ConfigError` that names the variable.
3. `purge` now also clears the ledger. The daily schedule that already runs it stays as it is.
4. **Rollback.**
   - Set `EYEWORK_REGISTRATION=code` first. That is enough to stop open registration with no migration.
   - To go below 0007, delete the open accounts as 0007 down's HINT says, then run `down --to 0006`. Down refuses while any open account exists.

---

## 12. Decisions that are the owner's

1. **The enumeration trade-off.** In open mode, anyone can learn whether an email has an account in a disability app (§4.2), and a single targeted question cannot be stopped. Accept it with the mitigations in §4.3 (this spec), or choose B (verify the email through a provider), C (login names the app generates) or D (stay in `code` mode).
2. **The new default applies to existing deployments.** Should `open` be the default even for an existing deployment? This spec makes such a deployment refuse to start until its operator chooses: a contact, or `code`.
3. **Who answers `EYEWORK_SUPPORT_CONTACT`, and the recovery process.** The process is to reply to the account's own address before `reissue-activation --owner-verified` or `delete-user` (§4.4, §4.6). The operator's mailbox provider sees what users choose to write.
4. **The numbers.**
   - Registrations per day: 200 in total, at most 150 without a link.
   - The pause: 60 "email taken" answers a day.
   - Per network: 5 an hour, 10 a day, 3 "email taken" answers a day.
   - New accounts: 7 days long, 10 generations a day each, 400 a day for all of them together, 3 open campaigns each.
5. **Accounts from operator links.** Should they also get the new-account limits? Today they don't: the operator vouched for them.
6. **Existing users, including invited ones.** Once registration is open, anyone can ask whether their email has an account. Should they be told in the app before switching? That would need a one-time notice screen and a flag on `users`, which is not in 0007. The alternative is to keep `code` until they have been told.
7. **The `TERMS_VERSION` date.** If no account has ever accepted `2026-10-09`, should this notice take that date (replacing its digest), or ship as its own later version?
8. **A global storage ceiling for campaign images.** Not in this spec. §5.4 gives the bound without one.

---

## 13. Evidence (scratch, not part of the repo)

All under `design/registration_check/`:

- `migrations/0007_open_registration.up.sql` and `.down.sql`: the exact SQL in §6.
- `scripts/build_down.py`: generates the down file from main's 0005 so its restored functions match word for word.
- `scripts/cycle.sh`: 0001–0006 from main, then 0007 up, down and up, with `pg_dump` comparisons.
- `scripts/check_0007.py`: the 20 functional checks as `eyework_app`; result 20/20.
- `scripts/fit.py`: copy variants of the static `index.html` (`fa84cd1`, sign-in markup and styles identical to main), measured with the repo's `AUDIT` at 320×635, 375×635 and 390×664 and Text Size default, 17, 23 and 53.
- `scripts/nearest.py`: entry geometry with the repo's `LANDING` and `NEAREST` at all five frames.
- `scripts/digest.py`: the consent digest computed with the repo's own `_notice_text`.
- `variants/`: the measured HTML. `H3_trim_enum_last` is the notice in §9; `E_screens` is the sign-in, email, review and profession screens.
- `fit_results.txt` and `nearest_results.txt`: the raw output of the last runs of `fit.py` and `nearest.py`.
