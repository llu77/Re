-- ════════════════════════════════════════════════════════════════════════
-- 0003_persona — تراجع
-- ════════════════════════════════════════════════════════════════════════

REVOKE INSERT (assistant_note) ON copy_versions FROM eyework_app;
ALTER TABLE copy_versions DROP COLUMN IF EXISTS assistant_note;

DROP FUNCTION IF EXISTS ew_my_display_name();
ALTER TABLE users DROP COLUMN IF EXISTS display_name;
