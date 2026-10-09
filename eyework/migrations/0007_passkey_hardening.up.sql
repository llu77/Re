-- ════════════════════════════════════════════════════════════════════════
-- 0007_passkey_hardening — مفتاح المرور يُنشأ بعد الدخول بكلمة المرور وحده
-- ════════════════════════════════════════════════════════════════════════
-- **لا إضافة من «حسابي».** في 0006 كان يكفي ملفّ الجلسة لإضافة مفتاح: من وجد
-- جهازاً مفتوحاً على حسابٍ أضاف مفتاحاً على جهازه هو، وبقي له باباً بعد الخروج.
-- الآن يُنشئ المتصفّح المفتاح وحده بعد الدخول بكلمة المرور مباشرةً (الإنشاء
-- المشروط، `mediation: 'conditional'`)، والقاعدة لا تقبل الإضافة إلا لجلسةٍ:
--   • هي جلسة الطلب نفسه (تجزئة رمزه معامِلٌ، والحساب من `ew_current_user()`)،
--   • قائمةٌ لم تُبطَل ولم تنتهِ،
--   • فُتحت بكلمة المرور قبل خمس دقائق على الأكثر (`sessions.password_at`).
-- يُفحص ذلك عند التحدّي، ثم ثانيةً في معاملة الحفظ نفسها بعد قفل الحساب.
--
-- **الاسترداد بالترتيب.** `ew_activate` يحذف تحدّيات الحساب، ثم مفاتيحه، ثم يضع
-- كلمة المرور، ثم يُبطل الجلسات. دخولٌ بمفتاحٍ في منتصفه يقفل صفّ المفتاح، فينتظره
-- الحذف، ثم يرى إبطالُ الجلسات (عبارةٌ لاحقة بلقطةٍ جديدة) جلستَه فيُبطلها. وإضافةٌ
-- في منتصفها تقفل صفّ تحدّيها، فينتظرها الحذف الأول، ثم يُحذف مفتاحها مع غيره.
--
-- **تحدّيات الدخول لها سقف.** طلبها بلا جلسة، وكل طلبٍ صفّ: كل تحدٍّ جديد يحذف
-- ما انتهى قبله (عشرةً على الأكثر، بلا انتظار قفل)، وتحدّيات الدخول السارية لا
-- تتجاوز عشرة آلاف (`passkey_login_ceiling`). وفهرسٌ على صاحب التحدّي: حذف
-- الحساب والاسترداد لا يمرّان على الجدول كلّه.
-- ════════════════════════════════════════════════════════════════════════

-- ── وقت الدخول بكلمة المرور ─────────────────────────────────────────────
-- NULL لجلسةٍ فُتحت بغيرها: مفتاح مرور، أو رابط تفعيل، أو تسجيل.
ALTER TABLE sessions ADD COLUMN password_at timestamptz;
ALTER TABLE sessions ADD CONSTRAINT session_password_at
    CHECK (password_at IS NULL OR (password_at >= created_at AND password_at < expires_at));

-- كـew_open_session في 0001، ومعها وقت الدخول بكلمة المرور.
CREATE FUNCTION ew_open_password_session(p_user uuid, p_token bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user AND is_active AND activated_at IS NOT NULL) THEN
        RAISE EXCEPTION 'session' USING ERRCODE = 'check_violation', CONSTRAINT = 'session_needs_active_user';
    END IF;
    INSERT INTO sessions (user_id, token_hash, expires_at, password_at)
    VALUES (p_user, p_token, now() + interval '30 days', now());
END
$$;

-- ── التحدّيات ───────────────────────────────────────────────────────────
CREATE INDEX passkey_challenges_user_idx ON passkey_challenges (user_id) WHERE user_id IS NOT NULL;

DROP FUNCTION ew_passkey_challenge(bytea, text);

-- تحدّي دخولٍ بلا صاحب ولو كانت في الطلب جلسة. يحذف أولاً ما انتهى (عشرةً على
-- الأكثر، ويتخطّى ما يقفله غيره)، ثم يرفض إن بلغت تحدّيات الدخول السارية السقف.
-- السقف تقريبي: طلباتٌ متزامنة قد تتجاوزه بعددها، لا أكثر.
CREATE FUNCTION ew_passkey_login_challenge(p_challenge bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM passkey_challenges WHERE challenge_hash IN (
        SELECT challenge_hash FROM passkey_challenges WHERE expires_at <= now()
         ORDER BY expires_at LIMIT 10 FOR UPDATE SKIP LOCKED);
    IF (SELECT count(*) FROM (SELECT 1 FROM passkey_challenges
                               WHERE purpose = 'LOGIN' AND expires_at > now() LIMIT 10000) AS live) >= 10000 THEN
        RAISE EXCEPTION 'ceiling' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_login_ceiling';
    END IF;
    INSERT INTO passkey_challenges (challenge_hash, purpose, expires_at)
    VALUES (p_challenge, 'LOGIN', now() + interval '5 minutes');
END
$$;

-- تحدّي إضافةٍ لصاحب جلسة الطلب، إن دخلها بكلمة المرور قبل خمس دقائق على الأكثر،
-- باسم الدخول نفسه الذي يُعرض في المفتاح، وما دام دون سقف المفاتيح — يُرفض قبل
-- أن يُسأل الجهاز لا بعده.
CREATE FUNCTION ew_passkey_add_challenge(p_challenge bytea, p_session bytea, p_login bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active AND activated_at IS NOT NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token_hash = p_session AND s.user_id = uid AND u.login_hmac = p_login
       AND s.revoked_at IS NULL AND s.expires_at > now() AND s.password_at > now() - interval '5 minutes';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'session' USING ERRCODE = 'insufficient_privilege',
                                        CONSTRAINT = 'passkey_needs_password_sign_in';
    END IF;
    IF (SELECT count(*) FROM passkeys WHERE user_id = uid) >= 10 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'passkey_cap';
    END IF;
    DELETE FROM passkey_challenges WHERE challenge_hash IN (
        SELECT challenge_hash FROM passkey_challenges WHERE expires_at <= now()
         ORDER BY expires_at LIMIT 10 FOR UPDATE SKIP LOCKED);
    INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, expires_at)
    VALUES (p_challenge, 'ADD', uid, now() + interval '5 minutes');
END
$$;

-- ── الحفظ ───────────────────────────────────────────────────────────────
DROP FUNCTION ew_passkey_add(bytea, bytea, bigint, text[]);

-- يحفظ مفتاحاً تحقّق منه التطبيق لصاحب الجلسة، لا لحسابٍ يسمّيه الطلب. وفي
-- المعاملة نفسها، بعد قفل الحساب: جلسة الطلب ما زالت قائمةً وفُتحت بكلمة المرور
-- قبل خمس دقائق على الأكثر، وتبقى كذلك حتى الحفظ (FOR SHARE: إبطالها ينتظره).
-- false لمعرّفٍ محفوظٌ من قبل — لهذا الحساب أو لغيره، بلا فرقٍ يُرى.
CREATE FUNCTION ew_passkey_add(p_session bytea, p_credential bytea, p_public_key bytea, p_sign_count bigint,
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
    PERFORM 1 FROM sessions
     WHERE token_hash = p_session AND user_id = uid
       AND revoked_at IS NULL AND expires_at > now() AND password_at > now() - interval '5 minutes'
       FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'session' USING ERRCODE = 'insufficient_privilege',
                                        CONSTRAINT = 'passkey_needs_password_sign_in';
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

REVOKE ALL ON FUNCTION ew_open_password_session(uuid, bytea), ew_passkey_login_challenge(bytea),
                       ew_passkey_add_challenge(bytea, bytea, bytea),
                       ew_passkey_add(bytea, bytea, bytea, bigint, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_open_password_session(uuid, bytea), ew_passkey_login_challenge(bytea),
                          ew_passkey_add_challenge(bytea, bytea, bytea),
                          ew_passkey_add(bytea, bytea, bytea, bigint, text[]) TO eyework_app;

-- ── الاسترداد ───────────────────────────────────────────────────────────
-- كما في 0006، والحذف قبل الإبطال: التحدّيات، ثم المفاتيح، ثم كلمة المرور، ثم
-- الجلسات. وهو ترتيب الأقفال في الإضافة (التحدّي ثم الحساب) والدخول (المفتاح ثم
-- الجلسة)، فلا تتعانق معاملتان.
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
    DELETE FROM passkey_challenges WHERE user_id = uid;
    DELETE FROM passkeys WHERE user_id = uid;
    UPDATE users SET password_hash = p_password_hash, activated_at = coalesce(activated_at, now())
     WHERE id = uid;
    UPDATE sessions SET revoked_at = now() WHERE user_id = uid AND revoked_at IS NULL;
    RETURN uid;
END
$$;
