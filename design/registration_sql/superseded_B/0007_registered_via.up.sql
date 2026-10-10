-- ════════════════════════════════════════════════════════════════════════
-- 0007_open_registration — التسجيل بلا رابط
-- ════════════════════════════════════════════════════════════════════════
-- يُنشئ المستخدم حسابه بلا رمزٍ من المشغّل حين يكون التسجيل مفتوحاً
-- (`EYEWORK_REGISTRATION=open`، يقرّره التطبيق). وكل ضمانةٍ في 0005 باقية.
--
-- **ثمن السؤال عن البريد معلَن.** التطبيق لا يرسل بريداً فلا يتحقّق من صاحبه،
-- وجواب «هذا البريد مسجَّل» لا بدّ منه: من يعرف بريد أحدٍ يعرف بطلبٍ واحد إن
-- كان له حسابٌ هنا. ما تفعله القاعدة أن تجعل السؤال بالجملة بطيئاً ومرئياً: كل
-- جواب «مأخوذ» في التسجيل المفتوح أثرٌ بلا هوية، وبعد خمسين في يومٍ يتوقّف
-- التسجيل المفتوح كلّه حتى يمضي اليوم — لكل بريد، فلا يصير التوقّف نفسه جواباً.
-- وروابط المشغّل تبقى تعمل.
--
-- **السقف اليومي لا يُفرغه الحذف.** كان يعدّ رموز التسجيل المستعملة، والتسجيل
-- المفتوح بلا رمز. فكل حسابٍ ينشئه صاحبه، بالرابط أو بدونه، يترك في سجلٍّ بلا
-- هوية وقته وبابه فقط — لا حساباً ولا بريداً ولا عنواناً — يعدّه السقف ويبقى بعد
-- حذف الحساب، ويحذفه `purge` بعد يومه. مئتان في اليوم للبابين، منها مئةٌ وخمسون
-- للمفتوح على الأكثر: طوفانٌ من التسجيل المفتوح لا يُغلق روابط المشغّل.
--
-- **الحساب الجديد لا ينفق ما ينفقه القديم.** حسابٌ فُتح بلا رابط، في أيامه الثلاثة
-- الأولى: عشر محاولات كتابةٍ في اليوم لا أربعون، وللحسابات الجديدة كلها أربعمئة من
-- ألفي التطبيق. فحساباتٌ تُنشأ بالجملة لا تستنفد اليوم على أصحاب الحسابات القائمة.
-- والمحاولة تحمل صفتها من لحظة بدئها، وأثرها بعد الحذف يحملها كذلك.
--
-- **لا منحَ أوسع من الحاجة.** دور الويب لا يقرأ السجلّ ولا يكتبه، ويصله عبر ثلاث
-- دوالّ: التسجيل المفتوح، وحاله اليوم (مفتوح أو اكتمل أو متوقّف)، وسقف صاحب الجلسة.
-- والتسجيل المفتوح دالّةٌ وحدها لا رمزٌ فارغ في دالّة الرابط: سحب EXECUTE منها
-- يُغلقه في القاعدة نفسها.
-- ════════════════════════════════════════════════════════════════════════

-- ── باب الحساب ─────────────────────────────────────────────────────────
-- كل حسابٍ أنشأه صاحبه قبل هذا الترحيل كان برابط؛ وحساب الدعوة بلا باب.
ALTER TABLE users ADD COLUMN registered_via text
    CONSTRAINT registered_via_known CHECK (registered_via IN ('CODE', 'OPEN'));
UPDATE users SET registered_via = 'CODE' WHERE self_registered;
ALTER TABLE users ADD CONSTRAINT registered_via_iff_self
    CHECK ((registered_via IS NOT NULL) = self_registered);

-- ── سجلّ التسجيل: وقتٌ وباب، بلا هوية ──────────────────────────────────
CREATE TABLE registration_ledger (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    -- CODE وOPEN: حسابٌ أُنشئ بالرابط أو بدونه. TAKEN: جواب «البريد مأخوذ» في التسجيل المفتوح.
    kind        text NOT NULL CONSTRAINT registration_ledger_kind CHECK (kind IN ('CODE', 'OPEN', 'TAKEN'))
);
CREATE INDEX registration_ledger_time ON registration_ledger (occurred_at);
ALTER TABLE registration_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE registration_ledger FORCE  ROW LEVEL SECURITY;
CREATE POLICY registration_ledger_owner_access ON registration_ledger FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
-- السقف لا ينقطع عند الترحيل: رموز اليوم المستعملة هي ما كان يعدّه.
INSERT INTO registration_ledger (occurred_at, kind)
SELECT used_at, 'CODE' FROM signup_codes WHERE used_at > now() - interval '24 hours';

-- ── صفة «جديد» على المحاولة وأثرها ─────────────────────────────────────
ALTER TABLE generation_attempts ADD COLUMN newcomer boolean NOT NULL DEFAULT false;
CREATE INDEX attempts_newcomer_time ON generation_attempts (started_at) WHERE newcomer;
ALTER TABLE attempt_tombstones ADD COLUMN newcomer boolean NOT NULL DEFAULT false;

-- كما في 0005، والأثر يحمل صفة المحاولة: حذف حسابٍ جديد لا يُفرغ حصّة الجدد.
CREATE OR REPLACE FUNCTION ew_attempt_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, newcomer)
        VALUES (OLD.started_at, OLD.outcome, OLD.newcomer);
    END IF;
    RETURN OLD;
END
$$;

-- ── الحساب الجديد ───────────────────────────────────────────────────────
-- فُتح بلا رابطٍ قبل أقلّ من ثلاثة أيام.
CREATE FUNCTION ew_is_newcomer(p_user uuid) RETURNS boolean
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT EXISTS (SELECT 1 FROM users
                    WHERE id = p_user AND registered_via = 'OPEN'
                      AND created_at > now() - interval '72 hours')
$$;

-- محاولات الكتابة المحسوبة في اليوم لكل حساب.
CREATE FUNCTION ew_generation_cap(p_user uuid) RETURNS integer
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT CASE WHEN ew_is_newcomer(p_user) THEN 10 ELSE 40 END
$$;

-- سقف صاحب الجلسة وحده، ليُعرض ما بقي له اليوم. بلا جلسةٍ فعّالة: NULL.
CREATE FUNCTION ew_my_generation_cap() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_generation_cap(id) FROM users WHERE id = ew_current_user() AND is_active
$$;

-- ── التسجيل ─────────────────────────────────────────────────────────────
-- ما يمنع تسجيلاً من هذا الباب الآن، باسم قيده، أو NULL.
CREATE FUNCTION ew_registration_refusal(p_via text) RETURNS text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT CASE
        WHEN count(*) FILTER (WHERE kind IN ('CODE', 'OPEN')) >= 200 THEN 'registration_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE kind = 'OPEN') >= 150 THEN 'registration_open_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE kind = 'TAKEN') >= 50 THEN 'registration_open_paused'
    END
      FROM registration_ledger WHERE occurred_at > now() - interval '24 hours'
$$;

-- قلب التسجيل للبابين: الحساب، أو NULL لبريدٍ هو اسم دخولٍ لحسابٍ قائم. لا يُحدِّث
-- صفّاً قائماً أبداً. وكل فحصٍ قبل السؤال عن البريد: ما يُرفض لا يقول عنه شيئاً.
CREATE FUNCTION ew_register_account(
    p_via text, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text
) RETURNS uuid
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid;
    refusal text;
BEGIN
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
    refusal := ew_registration_refusal(p_via);
    IF refusal IS NOT NULL THEN
        RAISE EXCEPTION 'registration' USING ERRCODE = 'check_violation', CONSTRAINT = refusal;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, registered_via, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession,
            true, p_via, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        IF p_via = 'OPEN' THEN
            INSERT INTO registration_ledger (kind) VALUES ('TAKEN');
        END IF;
        RETURN NULL;
    END IF;
    INSERT INTO registration_ledger (kind) VALUES (p_via);
    RETURN uid;
END
$$;

-- برابط المشغّل كما في 0005: الرمز يُفحص أولاً، و«مأخوذ» يُعدّ عليه ويُقفله في الثالثة.
CREATE OR REPLACE FUNCTION ew_register(
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
    uid := ew_register_account('CODE', p_login, p_password_hash, p_name, p_birth, p_profession,
                               p_terms_version);
    IF uid IS NULL THEN
        UPDATE signup_codes SET taken_count = taken_count + 1 WHERE code_hash = p_code;
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    UPDATE signup_codes SET used_at = now(), user_id = uid WHERE code_hash = p_code;
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- بلا رابط: (الحساب، 'OK') أو (NULL، 'TAKEN')، وما سواهما خطأٌ باسم قيده.
CREATE FUNCTION ew_register_open(
    p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text,
    p_terms_version text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid;
BEGIN
    uid := ew_register_account('OPEN', p_login, p_password_hash, p_name, p_birth, p_profession,
                               p_terms_version);
    RETURN QUERY SELECT uid, CASE WHEN uid IS NULL THEN 'TAKEN' ELSE 'OK' END;
END
$$;

-- حال التسجيل المفتوح الآن: OK أو FULL أو PAUSED، أو CLOSED إن سحب المشغّل EXECUTE
-- من ew_register_open (`admin open-registration off`). عدٌّ للجميع لا يقول شيئاً عن
-- أحد، تسأله الواجهة قبل الخطوة الأولى فلا يملأ أحدٌ تسع شاشاتٍ ليُردّ في آخرها.
CREATE FUNCTION ew_open_registration_state() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT CASE
        WHEN NOT has_function_privilege(session_user, 'ew_register_open(bytea, text, text, date, text, text)',
                                        'EXECUTE') THEN 'CLOSED'
        ELSE CASE ew_registration_refusal('OPEN')
            WHEN 'registration_open_paused' THEN 'PAUSED'
            WHEN 'registration_daily_cap' THEN 'FULL'
            WHEN 'registration_open_daily_cap' THEN 'FULL'
            ELSE 'OK'
        END
    END
$$;

-- ── سقوف كلفة النموذج: الحساب الجديد ────────────────────────────────────
-- كما في 0005، ومعها: سقف الحساب من ew_generation_cap، وحصّة الجدد من السقف العام،
-- وصفة المحاولة تُكتب عند بدئها.
CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
    is_new  boolean;
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
    is_new := ew_is_newcomer(uid);
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
           AND started_at > now() - interval '24 hours') >= ew_generation_cap(uid) THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- للحسابات الجديدة كلها أربعمئة من الألفين، تحت القفل نفسه.
    IF is_new AND (SELECT count(*) FROM generation_attempts
                    WHERE newcomer AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
                + (SELECT count(*) FROM attempt_tombstones
                    WHERE newcomer AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN
        RAISE EXCEPTION 'newcomers' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_newcomer_pool';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256, newcomer)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image, is_new)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

-- ── المنح ───────────────────────────────────────────────────────────────
-- الداخلية تُستدعى بصلاحية مالكها من دوالّ SECURITY DEFINER؛ ودور الويب ينال ثلاثاً.
REVOKE ALL ON FUNCTION ew_is_newcomer(uuid), ew_generation_cap(uuid), ew_my_generation_cap(),
                       ew_registration_refusal(text),
                       ew_register_account(text, bytea, text, text, date, text, text),
                       ew_register_open(bytea, text, text, date, text, text),
                       ew_open_registration_state() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_register_open(bytea, text, text, date, text, text),
                          ew_open_registration_state(), ew_my_generation_cap() TO eyework_app;
