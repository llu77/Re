-- ════════════════════════════════════════════════════════════════════════
-- 0006_passkeys — مفاتيح المرور
-- ════════════════════════════════════════════════════════════════════════
-- دخولٌ بلا كتابة: يضغط المستخدم زرّاً واحداً، ويؤكّد النظام بـFace ID أو
-- Touch ID أو رمز الجهاز. كلمة المرور تبقى بديلاً لمن لا مفتاح له.
--
-- **ما يُخزَّن.** المفتاح العام وحده، ومعرّفه، وعدّاد توقيعه، وطرق اتصاله.
-- لا شهادة جهاز (`attestation: none`)، ولا اسم، ولا شيء يدلّ على صاحبه غير
-- رقم حسابه. والمفتاح الخاص لا يصل الخادم أبداً.
--
-- **التحدّي.** كل طقسٍ يبدأ بتحدٍّ عشوائي يحفظ الخادم تجزئته، ويُستهلك مرةً
-- واحدة، وينتهي بعد خمس دقائق في القاعدة لا في المتصفّح. تحدّي الدخول بلا
-- صاحب (لا اسم في طلبه)، وتحدّي الإضافة لصاحب الجلسة التي طلبته وحده.
--
-- **العزل.** كجداول الهوية في 0001: دور الويب لا يقرأ الجدولين ولا يكتبهما؛
-- يصلهما عبر دوالّ SECURITY DEFINER، كلٌّ تفعل شيئاً واحداً، وما يخصّ صاحب
-- الجلسة يُقرأ من `ew_current_user()` لا من معامِل.
--
-- **الاسترداد يمحوها.** رابط التفعيل الجديد يُبطل الجلسات منذ 0001؛ وهنا يحذف
-- مفاتيح المرور أيضاً: مفتاحٌ أضافه من سرق الجلسة يبقى باباً له بعد الاسترداد.
-- ════════════════════════════════════════════════════════════════════════

CREATE TABLE passkeys (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- معرّف المفتاح كما يرسله الجهاز، ومنه يُعرف الحساب عند الدخول.
    credential_id  bytea NOT NULL UNIQUE
        CONSTRAINT passkey_credential_id_shape CHECK (octet_length(credential_id) BETWEEN 1 AND 1023),
    -- مفتاح COSE العام كما سلّمه الجهاز عند الإضافة.
    public_key     bytea NOT NULL
        CONSTRAINT passkey_public_key_shape CHECK (octet_length(public_key) BETWEEN 1 AND 2048),
    -- عدّاد التوقيع: لا يرجع إلى الوراء إلا في نسخةٍ منسوخة من المفتاح.
    sign_count     bigint NOT NULL DEFAULT 0
        CONSTRAINT passkey_sign_count_range CHECK (sign_count BETWEEN 0 AND 4294967295),
    transports     text[] NOT NULL DEFAULT '{}'
        CONSTRAINT passkey_transports_known CHECK (
            transports <@ ARRAY['usb', 'nfc', 'ble', 'smart-card', 'internal', 'cable', 'hybrid']::text[]
            AND cardinality(transports) <= 7
        ),
    created_at     timestamptz NOT NULL DEFAULT now(),
    last_used_at   timestamptz
);
CREATE INDEX passkeys_user_idx ON passkeys (user_id);

CREATE TABLE passkey_challenges (
    -- SHA-256 للتحدّي: الخام يغادر في الخيارات ويعود في ردّ الجهاز.
    challenge_hash bytea PRIMARY KEY CHECK (octet_length(challenge_hash) = 32),
    purpose        text NOT NULL CONSTRAINT passkey_challenge_purpose CHECK (purpose IN ('LOGIN', 'ADD')),
    user_id        uuid REFERENCES users(id) ON DELETE CASCADE,
    created_at     timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    used_at        timestamptz,
    -- تحدّي الإضافة لصاحب جلسة، وتحدّي الدخول لا صاحب له.
    CONSTRAINT passkey_challenge_owner CHECK ((purpose = 'ADD') = (user_id IS NOT NULL)),
    -- نظير `passkeys.CHALLENGE_SECONDS`: مهلةٌ أطول لا يكتبها حتى المالك.
    CONSTRAINT passkey_challenge_window
        CHECK (expires_at > created_at AND expires_at <= created_at + interval '5 minutes')
);
CREATE INDEX passkey_challenges_expiry_idx ON passkey_challenges (expires_at);

-- ── العزل: مغلقٌ لدور الويب كجداول الهوية ───────────────────────────────
ALTER TABLE passkeys           ENABLE ROW LEVEL SECURITY;
ALTER TABLE passkeys           FORCE  ROW LEVEL SECURITY;
ALTER TABLE passkey_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE passkey_challenges FORCE  ROW LEVEL SECURITY;
CREATE POLICY passkeys_owner_access           ON passkeys           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY passkey_challenges_owner_access ON passkey_challenges FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ── واجهة مفاتيح المرور لدور الويب ──────────────────────────────────────

-- تحدٍّ جديد. للإضافة: لصاحب جلسةٍ فعّال، وما دام دون سقف المفاتيح — يُرفض
-- قبل أن يمرّ صاحبه بـFace ID لا بعده. وللدخول: بلا صاحب ولو كانت في الطلب جلسة.
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

-- يستهلك تحدّياً صالحاً لغرضه مرةً واحدة: true إن استُهلك الآن. تحدّي الإضافة
-- لا يستهلكه إلا صاحبه؛ والاستهلاك يبقى ولو فشل التحقّق بعده.
CREATE FUNCTION ew_passkey_take_challenge(p_challenge bytea, p_purpose text) RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    WITH taken AS (
        UPDATE passkey_challenges SET used_at = now()
         WHERE challenge_hash = p_challenge AND purpose = p_purpose
           AND used_at IS NULL AND expires_at > now()
           AND user_id IS NOT DISTINCT FROM (CASE WHEN p_purpose = 'ADD' THEN ew_current_user() END)
        RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM taken)
$$;

-- مفتاح حسابٍ مفعَّلٍ فعّال وحده، بمعرّفه. يتحقّق التطبيق من التوقيع به.
CREATE FUNCTION ew_passkey_lookup(p_credential bytea)
RETURNS TABLE (user_id uuid, public_key bytea, sign_count bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT p.user_id, p.public_key, p.sign_count
      FROM passkeys p JOIN users u ON u.id = p.user_id
     WHERE p.credential_id = p_credential AND u.is_active AND u.activated_at IS NOT NULL
$$;

-- دخولٌ تحقّق منه التطبيق: يحفظ العدّاد الجديد ووقت الاستعمال، ويُرجع الحساب.
-- العدّاد يتقدّم، أو يبقى صفراً في مفتاحٍ لا يعدّ، ولا يرجع: NULL لدخولٍ آخر
-- سبق بالعدّاد نفسه بين القراءة والكتابة.
CREATE FUNCTION ew_passkey_signed_in(p_credential bytea, p_sign_count bigint) RETURNS uuid
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    UPDATE passkeys p SET sign_count = p_sign_count, last_used_at = now()
      FROM users u
     WHERE p.credential_id = p_credential AND u.id = p.user_id
       AND u.is_active AND u.activated_at IS NOT NULL
       AND (p_sign_count > p.sign_count OR (p_sign_count = 0 AND p.sign_count = 0))
    RETURNING p.user_id
$$;

-- مفاتيح صاحب الجلسة وحده: ليمنع الجهازُ إضافة المفتاح نفسه مرتين.
CREATE FUNCTION ew_my_passkeys() RETURNS TABLE (credential_id bytea, transports text[])
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT p.credential_id, p.transports FROM passkeys p
     WHERE p.user_id = ew_current_user()
     ORDER BY p.created_at, p.id
$$;

-- يحفظ مفتاحاً تحقّق منه التطبيق لصاحب الجلسة، لا لحسابٍ يسمّيه الطلب.
-- false لمعرّفٍ محفوظٌ من قبل — لهذا الحساب أو لغيره، بلا فرقٍ يُرى.
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

REVOKE ALL ON FUNCTION ew_passkey_challenge(bytea, text), ew_passkey_take_challenge(bytea, text),
                       ew_passkey_lookup(bytea), ew_passkey_signed_in(bytea, bigint),
                       ew_my_passkeys(), ew_passkey_add(bytea, bytea, bigint, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_passkey_challenge(bytea, text), ew_passkey_take_challenge(bytea, text),
                          ew_passkey_lookup(bytea), ew_passkey_signed_in(bytea, bigint),
                          ew_my_passkeys(), ew_passkey_add(bytea, bytea, bigint, text[]) TO eyework_app;

-- ── الاسترداد يحذف مفاتيح المرور ────────────────────────────────────────
-- كما في 0001 حرفاً بحرف، ومعه سطر حذف المفاتيح.
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
