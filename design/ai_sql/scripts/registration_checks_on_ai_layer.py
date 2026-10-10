"""Functional checks of NEXT_open_registration on the scratch database, as the real web role.

Sections 1-15 are the previous run's checks with the new signatures; 16-22 are new (size mode,
the dropped 7-argument ew_register, consent to a newer notice, and the down refusal).
"""

from __future__ import annotations

import datetime
import hashlib
import sys
import threading

import psycopg
from psycopg import errors

WT = "reg_v2_main"
sys.path.insert(0, WT)
from eyework.tests.conftest import UNUSABLE_HASH, as_user, create_campaign, make_user  # noqa: E402

DB = "ai_spec_check"
OWNER = f"postgresql://eyework_owner:eyework_dev_owner@localhost:5432/{DB}"
APP = f"postgresql://eyework_app:eyework_dev_app@localhost:5432/{DB}"
TERMS = "2026-10-09"
BIRTH = datetime.date(1994, 3, 21)

owner = psycopg.connect(OWNER, autocommit=True)
app = psycopg.connect(APP, autocommit=True)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def clean() -> None:
    owner.execute("TRUNCATE users, attempt_tombstones, registration_ledger RESTART IDENTITY CASCADE")


def h(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def reg_open(login: str, *, name="سارة", birth=BIRTH, profession="MARKETING", terms=TERMS, size="COMPACT",
             conn=None):
    conn = conn or app
    as_user(conn, None)
    return conn.execute("SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s, %s)",
                        (h(login), UNUSABLE_HASH, name, birth, profession, terms, size)).fetchone()


def issue_code(code: str) -> bytes:
    owner.execute("INSERT INTO signup_codes (code_hash, expires_at) VALUES (%s, now() + interval '1 day')",
                  (h(code),))
    return h(code)


def reg_code(code: bytes, login: str, *, size="GAZE"):
    as_user(app, None)
    return app.execute("SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s, %s)",
                       (code, h(login), UNUSABLE_HASH, "ليلى", BIRTH, "SUPPORT", TERMS, size)).fetchone()


def constraint_of(fn) -> str | None:
    try:
        fn()
    except (errors.CheckViolation, errors.InsufficientPrivilege) as exc:
        return exc.diag.constraint_name
    return None


def ledger() -> list[tuple]:
    return owner.execute("SELECT via, outcome, count(*) FROM registration_ledger"
                         " GROUP BY 1, 2 ORDER BY 1, 2").fetchall()


def seed_ledger(n: int, via: str, outcome: str, age: str = "1 hour") -> None:
    owner.execute("INSERT INTO registration_ledger (occurred_at, via, outcome)"
                  " SELECT now() - %s::interval, %s, %s FROM generate_series(1, %s)", (age, via, outcome, n))


# 1. An open registration makes an active, open, self-registered account and one ledger row.
clean()
uid, outcome = reg_open("new@example.sa")
row = owner.execute("SELECT is_active, activated_at IS NOT NULL, self_registered, open_registered, terms_version"
                    " FROM users WHERE id = %s", (uid,)).fetchone()
check("open register OK", outcome == "OK" and row == (True, True, True, True, TERMS), str(row))
check("ledger OPEN/OK", ledger() == [("OPEN", "OK", 1)], str(ledger()))

# 2. Taken: an existing login and a pending invitation are never touched; each answer is a ledger row.
make_user(owner, login=b"invited", password_hash=None)
invited_hmac = b"invited".ljust(32, b"\0")
as_user(app, None)
taken = reg_open("new@example.sa", name="ليلى", profession="SUPPORT")
pending = app.execute("SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s, %s)",
                      (invited_hmac, UNUSABLE_HASH, "ليلى", BIRTH, "SUPPORT", TERMS, "GAZE")).fetchone()
rows = owner.execute("SELECT display_name, profession, password_hash IS NULL, self_registered FROM users"
                     " ORDER BY created_at").fetchall()
check("taken never touches", taken == (None, "TAKEN") and pending == (None, "TAKEN")
      and rows == [("سارة", "MARKETING", False, True), (None, "MARKETING", True, False)], str(rows))
check("ledger TAKEN rows", ledger() == [("OPEN", "OK", 1), ("OPEN", "TAKEN", 2)], str(ledger()))

# 3. Field checks are 0005's; a refused attempt leaves no ledger row.
clean()
names = [constraint_of(lambda: reg_open("a@x.sa", name=None)),
         constraint_of(lambda: reg_open("a@x.sa", name="سارة2")),
         constraint_of(lambda: reg_open("a@x.sa", terms=None)),
         constraint_of(lambda: reg_open("a@x.sa", birth=datetime.date(1899, 12, 31)))]
tomorrow = owner.execute("SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date + 1").fetchone()[0]
names.append(constraint_of(lambda: reg_open("a@x.sa", birth=tomorrow)))
try:
    reg_open("a@x.sa", profession="ASTRONAUT")
    fk = False
except errors.ForeignKeyViolation:
    fk = True
check("field checks", names == ["registration_needs_name", "display_name_shape", "registration_needs_consent",
                                "birth_date_range", "registration_birth_date"] and fk, str(names))
check("no ledger row on refusal", ledger() == [], str(ledger()))

# 4. The open cap: 150 open accounts a day; TAKEN rows and older rows do not count.
clean()
seed_ledger(149, "OPEN", "OK")
seed_ledger(40, "OPEN", "TAKEN")
seed_ledger(30, "OPEN", "OK", age="25 hours")
first = reg_open("the-150th@example.sa")[1]
blocked = constraint_of(lambda: reg_open("the-151st@example.sa"))
code_ok = reg_code(issue_code("c1"), "coded@example.sa")[1]
check("open daily cap", first == "OK" and blocked == "registration_open_daily_cap" and code_ok == "OK",
      f"{first} {blocked} {code_ok}")

# 5. The total cap counts both ways: 200 a day.
clean()
seed_ledger(100, "OPEN", "OK")
seed_ledger(99, "CODE", "OK")
a = reg_code(issue_code("c2"), "the-200th@example.sa")[1]
b = constraint_of(lambda: reg_code(issue_code("c3"), "the-201st@example.sa"))
c = constraint_of(lambda: reg_open("open-201st@example.sa"))
check("total daily cap", a == "OK" and b == "registration_daily_cap" and c == "registration_daily_cap", f"{a} {b} {c}")

# 6. Deleting accounts makes no room under either cap.
clean()
seed_ledger(149, "OPEN", "OK")
uid, _ = reg_open("del@example.sa")
as_user(app, uid)
app.execute("SELECT ew_delete_me()")
owner.execute("DELETE FROM users WHERE open_registered")
check("deletion makes no room", constraint_of(lambda: reg_open("next@example.sa")) == "registration_open_daily_cap")

# 7. Sixty TAKEN answers in a day pause open registration for everyone; code links still work.
clean()
seed_ledger(59, "OPEN", "TAKEN")
seed_ledger(10, "OPEN", "TAKEN", age="25 hours")
reg_open("someone@example.sa")
sixtieth = reg_open("someone@example.sa")[1]
paused = constraint_of(lambda: reg_open("free@example.sa"))
as_user(app, None)
blocker = app.execute("SELECT ew_open_registration_blocker()").fetchone()[0]
code_ok = reg_code(issue_code("c4"), "coded@example.sa")[1]
check("taken breaker", sixtieth == "TAKEN" and paused == "registration_open_paused"
      and blocker == "registration_open_paused" and code_ok == "OK", f"{sixtieth} {paused} {blocker} {code_ok}")

# 8. The availability check names the blocker or returns NULL, and tells nothing about anyone.
clean()
as_user(app, None)
none_yet = app.execute("SELECT ew_open_registration_blocker()").fetchone()[0]
seed_ledger(200, "CODE", "OK")
full = app.execute("SELECT ew_open_registration_blocker()").fetchone()[0]
check("availability", none_yet is None and full == "registration_daily_cap", f"{none_yet} {full}")

# 9. A code TAKEN still counts on the code, and writes nothing to the ledger.
clean()
reg_code(issue_code("c5"), "x@example.sa")
probe = issue_code("c6")
reg_code(probe, "x@example.sa")
count = owner.execute("SELECT taken_count FROM signup_codes WHERE code_hash = %s", (probe,)).fetchone()[0]
check("code TAKEN on the code", count == 1 and ledger() == [("CODE", "OK", 1)], f"{count} {ledger()}")

# 10. The web role can neither read nor write the ledger, nor call the internal helpers.
denied = []
for statement in ("SELECT * FROM registration_ledger", "INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'OK')",
                  "DELETE FROM registration_ledger", "TRUNCATE registration_ledger",
                  "SELECT ew_registration_blocker('OPEN')", "SELECT ew_new_open_account(gen_random_uuid())",
                  "SELECT open_registered FROM users"):
    try:
        app.execute(statement)
        denied.append(False)
    except errors.InsufficientPrivilege:
        denied.append(True)
check("web role denied", all(denied), str(denied))
try:
    owner.execute("INSERT INTO registration_ledger (via, outcome) VALUES ('CODE', 'TAKEN')")
    shape = False
except errors.CheckViolation as exc:
    shape = exc.diag.constraint_name == "registration_ledger_taken_is_open"
columns = [r[0] for r in owner.execute("SELECT column_name FROM information_schema.columns"
                                       " WHERE table_name = 'registration_ledger' ORDER BY column_name").fetchall()]
check("ledger has no identity", shape and columns == ["occurred_at", "outcome", "via"], str(columns))

# 11. Two open registrations at once cannot both take the last place under the cap.
clean()
seed_ledger(149, "OPEN", "OK")
other = psycopg.connect(APP)  # not autocommit: holds the advisory lock until commit
as_user(other, None)
other.execute("SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s, %s)",
              (h("racer-1@example.sa"), UNUSABLE_HASH, "سارة", BIRTH, "MARKETING", TERMS, "COMPACT"))
outcome_box = {}


def second() -> None:
    racer = psycopg.connect(APP, autocommit=True)
    outcome_box["c"] = constraint_of(lambda: reg_open("racer-2@example.sa", conn=racer))
    racer.close()


thread = threading.Thread(target=second)
thread.start()
thread.join(timeout=1.5)
waited = thread.is_alive()
other.commit()
thread.join(timeout=10)
other.close()
check("concurrent cap is serialized", waited and outcome_box.get("c") == "registration_open_daily_cap",
      f"waited={waited} {outcome_box}")

# 12. AI limits for a new open account: 10 a day, its limit visible to itself, 40 after a week.
clean()
uid, _ = reg_open("fresh@example.sa")
coded, _ = reg_code(issue_code("c7"), "coded@example.sa")
owner.execute("UPDATE users SET profession = 'MARKETING' WHERE id = %s", (coded,))
as_user(app, uid)
limit_fresh = app.execute("SELECT ew_my_generation_limit()").fetchone()[0]
as_user(app, coded)
limit_coded = app.execute("SELECT ew_my_generation_limit()").fetchone()[0]
as_user(app, None)
limit_none = app.execute("SELECT ew_my_generation_limit()").fetchone()[0]
check("generation limit", (limit_fresh, limit_coded, limit_none) == (10, 40, None),
      str((limit_fresh, limit_coded, limit_none)))

campaign = create_campaign(app, uid)
owner.execute(
    "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at, outcome,"
    " new_account) SELECT %s, %s, 'INITIAL', sha256('seeded'::bytea), now() - interval '1 hour' - g * interval '1 minute',"
    " now() - interval '1 hour' - g * interval '1 minute' + interval '20 seconds', 'UPSTREAM_TIMEOUT', true"
    " FROM generate_series(1, 10) g", (campaign, uid))
as_user(app, uid)
version = app.execute("SELECT row_version FROM campaigns WHERE id = %s", (campaign,)).fetchone()[0]
new_cap = constraint_of(lambda: app.execute("SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, version)))
owner.execute("UPDATE users SET created_at = now() - interval '8 days' WHERE id = %s", (uid,))
as_user(app, uid)
week_later = app.execute("SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, version)).fetchone()[0]
flag = owner.execute("SELECT new_account FROM generation_attempts WHERE id = %s", (week_later,)).fetchone()[0]
limit_after = app.execute("SELECT ew_my_generation_limit()").fetchone()[0]
check("new-account daily cap", new_cap == "generation_new_account_cap" and week_later is not None
      and flag is False and limit_after == 40, f"{new_cap} {flag} {limit_after}")

# 13. The pool of 400 a day for all new accounts, counting the traces of deleted ones; others unaffected.
clean()
uid, _ = reg_open("fresh@example.sa")
gone, _ = reg_open("gone@example.sa")
old = make_user(owner, login=b"established")
gone_campaign = create_campaign(app, gone)
owner.execute(
    "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at, outcome,"
    " new_account) SELECT %s, %s, 'INITIAL', sha256('seeded'::bytea), now() - interval '1 hour' - g * interval '1 second',"
    " now() - interval '1 hour' - g * interval '1 second' + interval '1 second', 'OUTPUT_INVALID', true"
    " FROM generate_series(1, 400) g", (gone_campaign, gone))
owner.execute("DELETE FROM users WHERE id = %s", (gone,))
traces = owner.execute("SELECT count(*) FROM attempt_tombstones WHERE new_account").fetchone()[0]
campaign = create_campaign(app, uid)
as_user(app, uid)
pool = constraint_of(lambda: app.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (campaign,)))
established = create_campaign(app, old)
as_user(app, old)
fine = app.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (established,)).fetchone()[0]
check("new-accounts pool", traces == 400 and pool == "generation_new_accounts_cap" and fine is not None,
      f"traces={traces} {pool}")

# 14. Three open campaigns for a new open account; the established limit (20) is unchanged for others.
clean()
uid, _ = reg_open("fresh@example.sa")
for _ in range(3):
    create_campaign(app, uid, with_image=False)
fourth = constraint_of(lambda: create_campaign(app, uid, with_image=False))
old = make_user(owner, login=b"established")
for _ in range(4):
    create_campaign(app, old, with_image=False)
check("new-account campaign cap", fourth == "new_account_campaign_cap", str(fourth))

# 15. An open account cannot claim to be anything else: the constraint pins open to self-registered.
try:
    owner.execute("INSERT INTO users (login_hmac, profession, open_registered) VALUES (%s, 'MARKETING', true)",
                  (h("bad"),))
    pinned = False
except errors.CheckViolation as exc:
    pinned = exc.diag.constraint_name == "open_registered_is_self_registered"
check("open implies self-registered", pinned)

# 16. Both routes store the chosen size; registration without one is refused by name, with no ledger row.
clean()
opened, _ = reg_open("touch@example.sa", size="COMPACT")
coded, _ = reg_code(issue_code("c8"), "gaze@example.sa", size="GAZE")
sizes = owner.execute("SELECT ui_size FROM users WHERE id IN (%s, %s) ORDER BY id = %s DESC",
                      (opened, coded, opened)).fetchall()
before = ledger()
missing_open = constraint_of(lambda: reg_open("nosize@example.sa", size=None))
missing_code = constraint_of(lambda: reg_code(issue_code("c9"), "nosize2@example.sa", size=None))
unknown = constraint_of(lambda: reg_open("bigger@example.sa", size="LARGE"))
check("size stored and required",
      sizes == [("COMPACT",), ("GAZE",)] and missing_open == "registration_needs_ui_size"
      and missing_code == "registration_needs_ui_size" and unknown == "ui_size_known" and ledger() == before,
      f"{sizes} {missing_open} {missing_code} {unknown} {ledger()}")

# 17. The 7-argument ew_register is gone: no route creates an account without a size.
as_user(app, None)
try:
    app.execute("SELECT * FROM ew_register(%s, %s, %s, %s, %s, %s, %s)",
                (h("c10"), h("old@example.sa"), UNUSABLE_HASH, "ليلى", BIRTH, "SUPPORT", TERMS))
    gone = False
except errors.UndefinedFunction:
    gone = True
check("old ew_register signature gone", gone)

# 18. Existing and invited accounts have no size until their owner chooses; ew_my_ui_size is the session's own.
clean()
existing = make_user(owner, login=b"existing")
invited = make_user(owner, login=b"invited", password_hash=None)
fresh, _ = reg_open("fresh@example.sa", size="GAZE")
as_user(app, existing)
mine_existing = app.execute("SELECT ew_my_ui_size()").fetchone()[0]
as_user(app, fresh)
mine_fresh = app.execute("SELECT ew_my_ui_size()").fetchone()[0]
as_user(app, None)
mine_none = app.execute("SELECT ew_my_ui_size()").fetchone()[0]
invited_size = owner.execute("SELECT ui_size FROM users WHERE id = %s", (invited,)).fetchone()[0]
check("unchosen is NULL, own value only", (mine_existing, mine_fresh, mine_none, invited_size)
      == (None, "GAZE", None, None), str((mine_existing, mine_fresh, mine_none, invited_size)))

# 19. ew_set_my_ui_size changes the session's own row and nothing else; bad values are refused by name.
as_user(app, existing)
app.execute("SELECT ew_set_my_ui_size('COMPACT')")
after = dict(owner.execute("SELECT id, ui_size FROM users").fetchall())
bad_null = constraint_of(lambda: app.execute("SELECT ew_set_my_ui_size(NULL)"))
bad_value = constraint_of(lambda: app.execute("SELECT ew_set_my_ui_size('HUGE')"))
inactive = make_user(owner, login=b"inactive", active=False)
check("set own size only", after[existing] == "COMPACT" and after[fresh] == "GAZE" and after[invited] is None
      and bad_null == "ui_size_known" and bad_value == "ui_size_known",
      f"{after} {bad_null} {bad_value}")


def raises_privilege(statement: str) -> bool:
    try:
        app.execute(statement)
    except errors.InsufficientPrivilege:
        return True
    return False


as_user(app, None)
check("no session raises insufficient_privilege", raises_privilege("SELECT ew_set_my_ui_size('GAZE')"))
as_user(app, inactive)
check("inactive raises insufficient_privilege", raises_privilege("SELECT ew_set_my_ui_size('GAZE')"))

# 20. The web role has no direct access to the column.
as_user(app, existing)
check("web role cannot read or write ui_size directly",
      raises_privilege("SELECT ui_size FROM users")
      and raises_privilege("UPDATE users SET ui_size = 'GAZE'"))

# 21. Consent to a newer notice: own row only, never backwards, NULL refused; invited accounts can accept.
clean()
newcomer, _ = reg_open("newcomer@example.sa")
invited = make_user(owner, login=b"invited")
bystander = make_user(owner, login=b"bystander")
as_user(app, newcomer)
own_version = app.execute("SELECT ew_my_terms_version()").fetchone()[0]
as_user(app, invited)
invited_before = app.execute("SELECT ew_my_terms_version()").fetchone()[0]
app.execute("SELECT ew_accept_terms('2026-10-20')")
app.execute("SELECT ew_accept_terms('2026-10-20')")  # the same version again is harmless
backwards = constraint_of(lambda: app.execute("SELECT ew_accept_terms('2026-10-01')"))
missing = constraint_of(lambda: app.execute("SELECT ew_accept_terms(NULL)"))
rows = dict((r[0], r[1:]) for r in owner.execute(
    "SELECT id, terms_version, terms_accepted_at IS NOT NULL FROM users").fetchall())
as_user(app, None)
check("accept a newer notice",
      own_version == TERMS and invited_before is None and rows[invited] == ("2026-10-20", True)
      and rows[bystander] == (None, False) and backwards == "terms_version_backwards"
      and missing == "registration_needs_consent"
      and raises_privilege("SELECT ew_accept_terms('2026-10-20')"),
      f"{own_version} {invited_before} {rows} {backwards} {missing}")

# 22. Down refuses while an open account exists; after deleting it, down and up again both work.
import os
import subprocess

clean()
reg_open("blocker@example.sa")
env = {**os.environ, "EYEWORK_OWNER_DATABASE_URL": OWNER, "PYTHONPATH": WT}
refused = subprocess.run(["python3", "-m", "eyework.migrations.run", "down", "--to", "0006"],
                         cwd=WT, env=env, capture_output=True, text=True)
still = owner.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
owner.execute("DELETE FROM users WHERE open_registered")
down = subprocess.run(["python3", "-m", "eyework.migrations.run", "down", "--to", "0006"],
                      cwd=WT, env=env, capture_output=True, text=True)
up = subprocess.run(["python3", "-m", "eyework.migrations.run", "up"], cwd=WT, env=env,
                    capture_output=True, text=True)
check("down refuses with open accounts",
      refused.returncode != 0 and "1 حساباً مسجَّلاً بلا رابط" in refused.stderr
      and "DELETE FROM users WHERE open_registered" in refused.stderr and still == "0007"
      and down.returncode == 0 and up.returncode == 0,
      f"rc={refused.returncode} still={still} down={down.returncode} up={up.returncode} {refused.stderr[-300:]}")

clean()
width = max(len(name) for name, _, _ in results)
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
