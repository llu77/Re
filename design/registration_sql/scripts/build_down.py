"""Builds NEXT_open_registration.down.sql from main's 0005_registration.up.sql.

Usage: python3 build_down.py <main 0005_registration.up.sql> <output down.sql>

The guard, then ew_register recreated with 0005's exact text and grants (the up
migration dropped it because its signature changed), then the three functions the
up migration replaced, restored word for word, then the drops.
"""
import re
import sys

src = open(sys.argv[1], encoding="utf-8").read()
out = sys.argv[2]


def grab(name: str, *, replace: bool) -> str:
    match = re.search(r"(CREATE (?:OR REPLACE )?FUNCTION " + re.escape(name) + r"\(.*?\n\$\$;\n)", src, re.S)
    if not match:
        raise SystemExit(f"{name} not found in 0005")
    body = match.group(1)
    if replace:
        body = re.sub(r"^CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", body)
    return body


HEAD = """-- ════════════════════════════════════════════════════════════════════════
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
"""

REGISTER_GRANTS = """REVOKE ALL ON FUNCTION ew_register(bytea, bytea, text, text, date, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_register(bytea, bytea, text, text, date, text, text) TO eyework_app;

-- والثلاث التي استُبدلت، كما كانت في 0005، حرفاً بحرف.
"""

TAIL = """
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
"""

register = grab("ew_register", replace=False)
assert register.startswith("CREATE FUNCTION ew_register("), "0005 must create ew_register"
replaced = [grab(name, replace=True) for name in ("ew_attempt_tombstone", "ew_campaign_insert_guard",
                                                   "ew_begin_generation")]
with open(out, "w", encoding="utf-8") as handle:
    handle.write(HEAD + register + REGISTER_GRANTS + "\n".join(replaced) + TAIL)
print("written", out)
