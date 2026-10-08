-- ════════════════════════════════════════════════════════════════════════
-- 0005_registration — التسجيل والمهن
-- ════════════════════════════════════════════════════════════════════════
-- يُنشئ المستخدم حسابه بنفسه: اسمه، وتاريخ ميلاده، وبريده (اسم الدخول)،
-- وكلمة مروره، ومهنته — برابط تسجيلٍ يصدره المشغّل. ولكل مهنةٍ بوابتها؛ والمهنة
-- تُفرض هنا لا في الواجهة وحدها.
--
-- **لماذا رابط تسجيل لا تسجيلٌ مفتوح.** قائمة المستخدمين معلومةٌ صحّية (من فيها
-- يعمل بعينيه). تسجيلٌ مفتوح يجيب «هذا البريد مسجّل» يجعل كل من شاء يسأل: هل
-- يستعمل فلانٌ هذا التطبيق؟ وحساباتٌ بلا حدّ تستهلك سقف النموذج العام لليوم.
-- الرمز يُحصر السؤال فيمن يحمله، ويُقفل بعد ثلاث إجابات «مأخوذ».
--
-- **ما يُخزَّن.** البريد لا يُخزَّن: HMAC له كاسم الدخول تماماً، فلا تحقّق به
-- ولا استرداد. الاسم وتاريخ الميلاد يُخزَّنان كما طلب صاحب التطبيق؛ وهما معاً
-- يعرّفان صاحبهما من نسخةٍ مسرّبة دون المفتاح — تنازلٌ عن ضمانة 0001 معلنٌ في
-- README، ولا يقرؤهما دور الويب إلا اسم صاحب الجلسة.
-- ════════════════════════════════════════════════════════════════════════

-- المهن جدولٌ لا قائمة نصوص في القيود: المفتاح الخارجي يمنع مهنةً لا وجود لها،
-- وإضافة مهنةٍ ترحيلٌ يُراجَع.
CREATE TABLE professions (
    code    text PRIMARY KEY CONSTRAINT profession_code_shape CHECK (code ~ '^[A-Z_]{3,20}$'),
    name_ar text NOT NULL CONSTRAINT profession_name_shape CHECK (char_length(name_ar) BETWEEN 2 AND 40)
);
INSERT INTO professions (code, name_ar) VALUES
    ('MARKETING',   'التسويق'),
    ('STOREKEEPER', 'أمين المخزون'),
    ('SUPPORT',     'الدعم الفني');

-- الحسابات القائمة كلها حسابات تسويق: لم يكن في التطبيق غيره. والافتراض يُسحب
-- بعد الملء، فكل حسابٍ جديد يسمّي مهنته.
ALTER TABLE users ADD COLUMN profession text NOT NULL DEFAULT 'MARKETING'
    REFERENCES professions (code) ON DELETE RESTRICT;
ALTER TABLE users ALTER COLUMN profession DROP DEFAULT;

-- فارغٌ لحسابات الدعوة؛ والتسجيل يفرضه.
ALTER TABLE users ADD COLUMN birth_date date
    CONSTRAINT birth_date_range CHECK (birth_date IS NULL OR birth_date >= DATE '1900-01-01');

-- أنشأه صاحبه أم المشغّل: الاسترداد والسقف اليومي يختلفان بينهما.
ALTER TABLE users ADD COLUMN self_registered boolean NOT NULL DEFAULT false;
CREATE INDEX users_self_registered_recent ON users (created_at) WHERE self_registered;

-- ما وافق عليه صاحب الحساب عند التسجيل، ومتى. حساب التسجيل لا يوجد بدونه.
ALTER TABLE users ADD COLUMN terms_version text
    CONSTRAINT terms_version_shape CHECK (terms_version IS NULL OR terms_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$');
ALTER TABLE users ADD COLUMN terms_accepted_at timestamptz;
ALTER TABLE users ADD CONSTRAINT terms_complete
    CHECK ((terms_version IS NULL) = (terms_accepted_at IS NULL));
ALTER TABLE users ADD CONSTRAINT self_registered_accepted_terms
    CHECK (NOT self_registered OR terms_version IS NOT NULL);

-- ── رموز التسجيل ────────────────────────────────────────────────────────
-- يصدرها المشغّل دفعاتٍ (`admin issue-signup-codes`)، ولا تُربط ببريد. الرمز
-- الخام في جزء الرابط بعد `#`، والقاعدة تحفظ تجزئته وحدها.
CREATE TABLE signup_codes (
    code_hash   bytea PRIMARY KEY CHECK (octet_length(code_hash) = 32),
    -- اسم الدفعة كما يكتبه المشغّل («riyadh-oct»): ليعرف من أين جاء حسابٌ يُساء استعماله.
    label       text CONSTRAINT signup_label_shape CHECK (label IS NULL OR label ~ '^[A-Za-z0-9 _.-]{1,40}$'),
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    user_id     uuid REFERENCES users (id) ON DELETE SET NULL,
    -- إجابات «البريد مأخوذ» بهذا الرمز. الثالثة تُقفله: لا يصير الرمز أداة سؤالٍ عن الناس.
    taken_count integer NOT NULL DEFAULT 0 CONSTRAINT signup_taken_count CHECK (taken_count BETWEEN 0 AND 3),
    CONSTRAINT signup_window CHECK (expires_at > created_at AND expires_at <= created_at + interval '30 days'),
    CONSTRAINT signup_used_by CHECK (user_id IS NULL OR used_at IS NOT NULL)
);

ALTER TABLE professions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE professions  FORCE  ROW LEVEL SECURITY;
ALTER TABLE signup_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE signup_codes FORCE  ROW LEVEL SECURITY;
CREATE POLICY professions_owner_access  ON professions  FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY signup_codes_owner_access ON signup_codes FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ── التسجيل ─────────────────────────────────────────────────────────────
-- «اليوم» بتوقيت الرياض لا بتوقيت الخادم: مولود اليوم في الرياض بعد منتصف
-- الليل لا يُرفض لأن الساعة في UTC لم تبلغ يومه بعد.
CREATE FUNCTION ew_riyadh_today() RETURNS date
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date
$$;

-- رمزٌ صالحٌ للاستعمال؟ تسأله الواجهة قبل الخطوة الأولى، فلا يملأ أحدٌ تسع
-- شاشاتٍ برمزٍ منتهٍ. لا يكشف شيئاً عن الحسابات.
CREATE FUNCTION ew_signup_code_usable(p_code bytea) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM signup_codes
                    WHERE code_hash = p_code AND used_at IS NULL AND expires_at > now() AND taken_count < 3)
$$;

-- النتيجة: (الحساب، 'OK') أو (NULL، 'CODE') لرمزٍ غير صالح، أو (NULL، 'TAKEN')
-- لبريدٍ مأخوذ — وهذه تُعدّ على الرمز. لا تُحدِّث صفّاً قائماً أبداً: بريد دعوةٍ
-- لم تُفعَّل بعد لا «يُستولى» عليه بالتسجيل.
CREATE FUNCTION ew_register(
    p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid;
    code signup_codes%ROWTYPE;
BEGIN
    SELECT * INTO code FROM signup_codes WHERE code_hash = p_code FOR UPDATE;
    IF NOT FOUND OR code.used_at IS NOT NULL OR code.expires_at <= now() OR code.taken_count >= 3 THEN
        RETURN QUERY SELECT NULL::uuid, 'CODE'::text;
        RETURN;
    END IF;
    IF p_name IS NULL THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_name';
    END IF;
    IF p_birth IS NULL OR p_birth > ew_riyadh_today() THEN
        RAISE EXCEPTION 'birth' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_birth_date';
    END IF;
    IF p_terms_version IS NULL THEN
        RAISE EXCEPTION 'terms' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_needs_consent';
    END IF;
    -- قفلٌ واحد للجميع: بلا هذا يرى تسجيلان متزامنان العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    IF (SELECT count(*) FROM users
         WHERE self_registered AND created_at > now() - interval '24 hours') >= 200 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'registration_daily_cap';
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- مهنة صاحب الجلسة وحده: البوابة تُفتح بها.
CREATE FUNCTION ew_my_profession() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT profession FROM users WHERE id = ew_current_user() AND is_active
$$;

-- صاحب الحساب يحذفه بنفسه، وكل ما يتبعه: الجلسات، والرموز، والحملات، والنسخ،
-- والصور. لا يحتاج المشغّل ولا بريداً.
CREATE FUNCTION ew_delete_me() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    DELETE FROM users WHERE id = uid AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
END
$$;

-- ew_riyadh_today تستدعيها ew_register بصلاحية مالكها؛ دور الويب لا يحتاجها.
REVOKE ALL ON FUNCTION ew_riyadh_today(), ew_signup_code_usable(bytea),
                       ew_register(bytea, bytea, text, text, date, text, text),
                       ew_my_profession(), ew_delete_me() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_signup_code_usable(bytea),
                          ew_register(bytea, bytea, text, text, date, text, text),
                          ew_my_profession(), ew_delete_me() TO eyework_app;

-- ── الحملة لحساب التسويق وحده: عند الإنشاء، وعند كل كتابةٍ تكلّف ─────────
CREATE OR REPLACE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.user_id AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- الكلفة تُفرض حيث تقع: حسابٌ نُقل إلى مهنةٍ أخرى لا يكتب لحملةٍ قديمة.
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    SELECT * INTO c FROM campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_kind NOT IN ('INITIAL','EDIT')
       OR (p_kind = 'INITIAL' AND (c.status <> 'DRAFT' OR p_expected_version IS NOT NULL))
       OR (p_kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED' OR c.current_version_id IS DISTINCT FROM p_expected_version)) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_wrong_state';
    END IF;
    SELECT sha256 INTO image FROM campaign_images WHERE campaign_id = p_campaign;
    IF image IS NULL THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_needs_image';
    END IF;
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE user_id = uid AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_in_progress';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_rate';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 40 THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;
