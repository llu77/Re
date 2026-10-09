-- ════════════════════════════════════════════════════════════════════════
-- 0001_identity — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُعيد القاعدة إلى ما كانت عليه بالضبط. الأدوار لا تُحذف: هي على مستوى
-- العنقود، ويُنشئها المشغّل لا الترحيل.
-- ════════════════════════════════════════════════════════════════════════

DROP FUNCTION IF EXISTS ew_activate(bytea, bytea, text);
DROP FUNCTION IF EXISTS ew_revoke_session(bytea);
DROP FUNCTION IF EXISTS ew_resolve_session(bytea);
DROP FUNCTION IF EXISTS ew_open_session(uuid, bytea);
DROP FUNCTION IF EXISTS ew_login_lookup(bytea);

DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS activation_tokens;
DROP TABLE IF EXISTS users;

DROP FUNCTION IF EXISTS ew_current_user();

REVOKE USAGE ON SCHEMA public FROM eyework_app;
GRANT USAGE ON SCHEMA public TO PUBLIC;

DO $$
BEGIN
    EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM eyework_app', current_database());
    EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO PUBLIC', current_database());
END
$$;
