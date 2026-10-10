-- ════════════════════════════════════════════════════════════════════════
-- 0001_identity — الهوية والجلسات
-- ════════════════════════════════════════════════════════════════════════
-- قائمة مستخدمي هذا التطبيق معلومةٌ صحّية: من فيها يعمل بعينيه. ولذلك:
--   • لا بريد ولا اسم ولا هاتف ولا تشخيص في أي جدول. اسم الدخول نفسه لا
--     يُخزَّن، بل HMAC له بمفتاحٍ خارج القاعدة — نسخةٌ مسرّبة من القاعدة
--     لا تكشف من يستخدمها.
--   • دور الويب `eyework_app` لا يقرأ جداول الهوية أصلاً: لا منح ولا سياسة.
--     يصلها عبر دوالّ SECURITY DEFINER محدّدة، كلٌّ تفعل شيئاً واحداً.
--   • أدوار المنصّة السريرية — وكل دورٍ آخر — لا تتصل بهذه القاعدة:
--     CONNECT مسحوبةٌ من PUBLIC.
--
-- الدور `eyework_app` لا يُنشأ هنا. ترحيلٌ يُنشئ دوراً بكلمة مرورٍ مكتوبة فيه
-- يترك في الإنتاج دوراً بكلمة مرورٍ منشورة متى نسي المشغّل إنشاءه أولاً.
-- يُنشئه المشغّل (أو `eyework/scripts/dev_db.sh` في التطوير) قبل الترحيل.
-- ════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eyework_app') THEN
        RAISE EXCEPTION 'الدور eyework_app غير موجود. أنشئه قبل الترحيل (LOGIN NOSUPERUSER NOBYPASSRLS).';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eyework_app'
               AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)) THEN
        RAISE EXCEPTION 'الدور eyework_app يحمل صلاحياتٍ تتجاوز العزل. أزلها قبل الترحيل.';
    END IF;
    -- المالك نفسه لا يتجاوز العزل: superuser يتخطّى RLS حتى مع FORCE، فتصير
    -- كل سياسةٍ هنا زينة.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
        RAISE EXCEPTION 'شغّل الترحيل بدور المالك eyework_owner لا بدورٍ يتجاوز العزل.';
    END IF;
    -- ما مُنح لـeyework_app قبل الترحيل يُسحب أولاً، فلا يبقى إلا ما يمنحه الترحيل.
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC, eyework_app', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO eyework_app', current_database());
END
$$;

-- الافتراض: لا صلاحية لأحد. كل منحٍ بعدها صريحٌ ومقصود.
REVOKE ALL ON SCHEMA public FROM PUBLIC, eyework_app;
GRANT USAGE ON SCHEMA public TO eyework_app;

-- هوية الطلب كما ضبطها التطبيق داخل معاملته. فارغةٌ ⇒ NULL ⇒ لا يطابق صفّاً.
CREATE FUNCTION ew_current_user() RETURNS uuid
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT nullif(current_setting('eyework.user_id', true), '')::uuid
$$;

-- ── الجداول ─────────────────────────────────────────────────────────────
CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- HMAC-SHA256 لاسم الدخول بعد توحيده. المفتاح في EYEWORK_LOGIN_KEY.
    login_hmac     bytea NOT NULL UNIQUE CHECK (octet_length(login_hmac) = 32),
    -- فارغة حتى التفعيل: الحساب يُنشأ بدعوة، ويضع صاحبه كلمته بنفسه.
    password_hash  text CHECK (password_hash ~ '^scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}$'),
    is_active      boolean NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    activated_at   timestamptz,
    CONSTRAINT activated_iff_password CHECK ((activated_at IS NULL) = (password_hash IS NULL))
);

CREATE TABLE activation_tokens (
    token_hash  bytea PRIMARY KEY CHECK (octet_length(token_hash) = 32),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    CONSTRAINT activation_window
        CHECK (expires_at > created_at AND expires_at <= created_at + interval '72 hours')
);
-- رمزٌ مفتوحٌ واحد لكل حساب: إعادة الدعوة تُغلق القديم قبل أن تفتح جديداً.
CREATE UNIQUE INDEX activation_one_open ON activation_tokens (user_id) WHERE used_at IS NULL;

CREATE TABLE sessions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    CONSTRAINT session_window
        CHECK (expires_at > created_at AND expires_at <= created_at + interval '30 days')
);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;

-- ── العزل: مغلقٌ لدور الويب ─────────────────────────────────────────────
-- FORCE لأن المالك يتجاوز RLS بدونها. وسياسة المالك وحدها موجودة؛ دور الويب
-- بلا سياسة وبلا منح، فيُرفض قبل أن يصل إلى أي صفّ.
ALTER TABLE users             ENABLE ROW LEVEL SECURITY;
ALTER TABLE users             FORCE  ROW LEVEL SECURITY;
ALTER TABLE activation_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE activation_tokens FORCE  ROW LEVEL SECURITY;
ALTER TABLE sessions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions          FORCE  ROW LEVEL SECURITY;

CREATE POLICY users_owner_access       ON users             FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY activation_owner_access  ON activation_tokens FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY sessions_owner_access    ON sessions          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ── واجهة الهوية الوحيدة لدور الويب ─────────────────────────────────────
-- كل دالّة: SECURITY DEFINER، و`search_path` مثبَّت (دونه يستطيع من يملك
-- إنشاء كائنٍ في مسارٍ أسبق أن يُشغّل شيفرته بصلاحيات المالك)، وEXECUTE
-- مسحوبةٌ من PUBLIC وممنوحةٌ لدور الويب وحده.

-- الحساب المفعَّل الفعّال وحده. يُرجع التجزئة ليتحقّق منها التطبيق بزمنٍ ثابت.
CREATE FUNCTION ew_login_lookup(p_login bytea)
RETURNS TABLE (user_id uuid, password_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT id, password_hash FROM users
     WHERE login_hmac = p_login AND is_active AND activated_at IS NOT NULL
$$;

CREATE FUNCTION ew_open_session(p_user uuid, p_token bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user AND is_active AND activated_at IS NOT NULL) THEN
        RAISE EXCEPTION 'session' USING ERRCODE = 'check_violation', CONSTRAINT = 'session_needs_active_user';
    END IF;
    INSERT INTO sessions (user_id, token_hash, expires_at)
    VALUES (p_user, p_token, now() + interval '30 days');
END
$$;

-- جلسةٌ صالحة لمستخدمٍ فعّال، أو لا شيء. عمرها مطلق (ثلاثون يوماً) بلا تمديد.
CREATE FUNCTION ew_resolve_session(p_token bytea) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT s.user_id FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token_hash = p_token AND s.revoked_at IS NULL AND s.expires_at > now()
       AND u.is_active
$$;

CREATE FUNCTION ew_revoke_session(p_token bytea) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    UPDATE sessions SET revoked_at = now() WHERE token_hash = p_token AND revoked_at IS NULL
$$;

-- رمزٌ صالح لاسم الدخول نفسه يُستعمل مرةً واحدة: يضع كلمة المرور (أو
-- يستبدلها — هذا هو مسار الاسترداد الوحيد)، ويُبطل كل جلسةٍ قائمة. ورابطٌ
-- عُبث باسمه لا يُفعِّل: لا يحفظ المتصفّح كلمة المرور تحت اسمٍ غير اسم الحساب.
-- NULL لكل فشل، برسالةٍ واحدة في التطبيق.
CREATE FUNCTION ew_activate(p_token bytea, p_login bytea, p_password_hash text) RETURNS uuid
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

REVOKE ALL ON FUNCTION ew_login_lookup(bytea), ew_open_session(uuid, bytea),
                       ew_resolve_session(bytea), ew_revoke_session(bytea),
                       ew_activate(bytea, bytea, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_login_lookup(bytea), ew_open_session(uuid, bytea),
                          ew_resolve_session(bytea), ew_revoke_session(bytea),
                          ew_activate(bytea, bytea, text) TO eyework_app;
-- ew_current_user تستدعيها سياسات العزل بصلاحية من يستعلم، فتُمنح لدور الويب وحده.
REVOKE ALL ON FUNCTION ew_current_user() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_current_user() TO eyework_app;
