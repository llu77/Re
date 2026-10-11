-- ════════════════════════════════════════════════════════════════════════
-- 0012_full_name — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- قيد 0003 لا يقبل اسماً أطول من ثلاثين حرفاً، ولا يُقصّ اسم أحدٍ بصمت: فلا تراجع وفي القاعدة واحدٌ منها. والقفل
-- أولاً: تسجيلٌ لم يُثبَّت بعد لا يراه العدّ، فينتظره التراجع ثم يعدّه.
LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE
    n integer;
BEGIN
    SELECT count(*) INTO n FROM users WHERE char_length(display_name) > 30;
    IF n > 0 THEN
        RAISE EXCEPTION 'في القاعدة % حساباً باسمٍ أطول من ثلاثين حرفاً لا يصفه قيد 0003', n
            USING HINT = 'يُقصَّر الاسم أو يُحذف الحساب بدور المالك قبل التراجع';
    END IF;
END
$$;

ALTER TABLE users DROP CONSTRAINT display_name_shape;
ALTER TABLE users ADD CONSTRAINT display_name_shape CHECK (
    display_name IS NULL OR (
        char_length(display_name) BETWEEN 1 AND 30
        AND display_name ~ '^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$'
    )
);
