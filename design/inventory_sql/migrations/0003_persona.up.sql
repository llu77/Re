-- ════════════════════════════════════════════════════════════════════════
-- 0003_persona — «سيمبول» واسم المستخدم
-- ════════════════════════════════════════════════════════════════════════
-- اسمٌ يناديه به المساعد في الواجهة، اختياريّ، يضعه المشغّل عند الدعوة أو
-- بعدها. يبقى في هذه القاعدة: لا يصل مزوّد النموذج أبداً، ودور الويب لا
-- يقرأ جدول المستخدمين، فيصله اسم صاحب الجلسة وحده عبر دالّة.
--
-- وكلمة المساعد للمستخدم مع كل نسخة: ما أبرزه وما تركه لأنه لم يتأكّد منه.
-- تُعرض بجانب النصّ ولا تُنشر معه.
-- ════════════════════════════════════════════════════════════════════════

-- حروفٌ عربية ولاتينية ومسافاتٌ مفردة، بلا تشكيلٍ ولا تطويل ولا أرقام: اسمٌ
-- يُنادى به، لا معرّفٌ ولا وسيلة اتصال.
ALTER TABLE users ADD COLUMN display_name text
    CONSTRAINT display_name_shape CHECK (
        display_name IS NULL OR (
            char_length(display_name) BETWEEN 1 AND 30
            AND display_name ~ '^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$'
        )
    );

CREATE FUNCTION ew_my_display_name() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT display_name FROM users WHERE id = ew_current_user() AND is_active
$$;
REVOKE ALL ON FUNCTION ew_my_display_name() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_my_display_name() TO eyework_app;

ALTER TABLE copy_versions ADD COLUMN assistant_note text
    CONSTRAINT assistant_note_shape CHECK (
        assistant_note IS NULL OR (
            char_length(assistant_note) BETWEEN 1 AND 120
            AND strpos(assistant_note, chr(10)) = 0 AND strpos(assistant_note, chr(13)) = 0
        )
    );
GRANT INSERT (assistant_note) ON copy_versions TO eyework_app;
