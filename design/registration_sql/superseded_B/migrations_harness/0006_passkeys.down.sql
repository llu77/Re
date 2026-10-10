-- ════════════════════════════════════════════════════════════════════════
-- 0006_passkeys — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- الدالّة كما كانت في 0001، حرفاً بحرف.
CREATE OR REPLACE FUNCTION ew_activate(p_token bytea, p_login bytea, p_password_hash text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid;
BEGIN
    UPDATE activation_tokens t SET used_at = now()
      FROM users u
     WHERE t.token_hash = p_token AND t.used_at IS NULL AND t.expires_at > now()
       AND u.id = t.user_id AND u.is_active AND u.login_hmac = p_login
    RETURNING t.user_id INTO uid;
    IF uid IS NULL THEN
        RETURN NULL;
    END IF;
    UPDATE users SET password_hash = p_password_hash, activated_at = coalesce(activated_at, now())
     WHERE id = uid;
    UPDATE sessions SET revoked_at = now() WHERE user_id = uid AND revoked_at IS NULL;
    RETURN uid;
END
$$;

DROP FUNCTION IF EXISTS ew_passkey_add(bytea, bytea, bigint, text[]);
DROP FUNCTION IF EXISTS ew_my_passkeys();
DROP FUNCTION IF EXISTS ew_passkey_signed_in(bytea, bigint);
DROP FUNCTION IF EXISTS ew_passkey_lookup(bytea);
DROP FUNCTION IF EXISTS ew_passkey_take_challenge(bytea, text);
DROP FUNCTION IF EXISTS ew_passkey_challenge(bytea, text);

DROP TABLE IF EXISTS passkey_challenges;
DROP TABLE IF EXISTS passkeys;
