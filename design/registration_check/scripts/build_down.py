"""Builds 0007 down: guard, then the four 0005 functions verbatim, then drops."""
import re, sys
src = open(sys.argv[1], encoding='utf-8').read()
out = sys.argv[2]

def grab(name):
    m = re.search(r'(CREATE (?:OR REPLACE )?FUNCTION ' + re.escape(name) + r'\(.*?\n\$\$;\n)', src, re.S)
    body = m.group(1)
    return re.sub(r'^CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', body)

head = '''-- ════════════════════════════════════════════════════════════════════════
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
'''
tail = '''
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
'''
parts = [grab(n) for n in ('ew_attempt_tombstone', 'ew_register', 'ew_campaign_insert_guard', 'ew_begin_generation')]
open(out, 'w', encoding='utf-8').write(head + '\n'.join(parts) + tail)
print('written', out)
