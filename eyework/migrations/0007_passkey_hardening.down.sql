-- ════════════════════════════════════════════════════════════════════════
-- 0007_passkey_hardening — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يعود مخطّط 0006 كما كان حرفاً بحرف. ما في الجداول يبقى: المفاتيح والتحدّيات
-- بالشكل نفسه، ووقت الدخول بكلمة المرور يسقط مع عموده.

-- الدالّة كما كانت في 0006، حرفاً بحرف.
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
    DELETE FROM passkeys WHERE user_id = uid;
    RETURN uid;
END
$$;

DROP FUNCTION IF EXISTS ew_passkey_add(bytea, bytea, bytea, bigint, text[]);
DROP FUNCTION IF EXISTS ew_passkey_add_challenge(bytea, bytea, bytea);
DROP FUNCTION IF EXISTS ew_passkey_login_challenge(bytea);
DROP FUNCTION IF EXISTS ew_open_password_session(uuid, bytea);

-- الدالّتان كما كانتا في 0006، حرفاً بحرف.
CREATE FUNCTION ew_passkey_challenge(p_challenge bytea, p_purpose text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid;
BEGIN
    IF p_purpose = 'ADD' THEN
        uid := ew_current_user();
        PERFORM 1 FROM users WHERE id = uid AND is_active AND activated_at IS NOT NULL;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF (SELECT count(*) FROM passkeys WHERE user_id = uid) >= 10 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_cap';
        END IF;
    END IF;
    INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, expires_at)
    VALUES (p_challenge, p_purpose, uid, now() + interval '5 minutes');
END
$$;

CREATE FUNCTION ew_passkey_add(p_credential bytea, p_public_key bytea, p_sign_count bigint,
                               p_transports text[]) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    added uuid;
BEGIN
    -- قفلٌ على صفّ الحساب: إضافتان متزامنتان لا تتجاوزان السقف معاً.
    PERFORM 1 FROM users WHERE id = uid AND is_active AND activated_at IS NOT NULL FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (SELECT count(*) FROM passkeys WHERE user_id = uid) >= 10 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_cap';
    END IF;
    INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, transports)
    VALUES (uid, p_credential, p_public_key, p_sign_count, p_transports)
    ON CONFLICT (credential_id) DO NOTHING
    RETURNING id INTO added;
    RETURN added IS NOT NULL;
END
$$;

REVOKE ALL ON FUNCTION ew_passkey_challenge(bytea, text), ew_passkey_add(bytea, bytea, bigint, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_passkey_challenge(bytea, text), ew_passkey_add(bytea, bytea, bigint, text[])
    TO eyework_app;

DROP INDEX IF EXISTS passkey_challenges_user_idx;

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS session_password_at;
ALTER TABLE sessions DROP COLUMN IF EXISTS password_at;
