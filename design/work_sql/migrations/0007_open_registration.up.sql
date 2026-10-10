-- ════════════════════════════════════════════════════════════════════════
-- 0007_open_registration — التسجيل المفتوح بلا رابط
-- ════════════════════════════════════════════════════════════════════════
-- يُنشئ الزائر حسابه بلا رمزٍ من المشغّل حين يكون EYEWORK_REGISTRATION=open.
-- الوضع يقرّره الخادم: ew_register_open دالّةٌ مستقلّة لا يستدعيها في وضعي
-- code وclosed، وew_register برمزه باقٍ على شرطه: لا حساب به بلا رمزٍ صالح.
--
-- ما تضمنه القاعدة في الطريقين: لا يُستولى على بريدٍ قائم (ولا على دعوةٍ لم
-- تُفعَّل)، والاسم والتاريخ والموافقة والمهنة تُفحص كما في 0005، وسقوفٌ يومية
-- للحسابات الجديدة لا يُفرغها حذف.
--
-- **دفتر التسجيل.** صفٌّ لكل تسجيلٍ نجح، ولكل جواب «البريد مأخوذ» بلا رمز:
-- وقته وطريقه ونتيجته فقط — لا حساب ولا بريد ولا عنوان. منه تُعدّ السقوف، فلا
-- يُفرغها حذف الحساب، ويحذفه purge بعد يومه.
--
-- **الحساب المفتوح الجديد** (open_registered، في أيامه السبعة الأولى): عشرة
-- طلبات كتابةٍ في اليوم بدل أربعين، وأربعمئة في اليوم للحسابات الجديدة كلّها
-- من ألفي التطبيق، وثلاث حملاتٍ مفتوحة بدل عشرين. فحساباتٌ تُنشأ بالجملة لا
-- تستنفد ما لأصحاب الحسابات القائمة، ولا تملأ القرص بالصور.
-- ════════════════════════════════════════════════════════════════════════

-- ── دفتر التسجيل ────────────────────────────────────────────────────────
CREATE TABLE registration_ledger (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    via         text NOT NULL CONSTRAINT registration_ledger_via CHECK (via IN ('CODE', 'OPEN')),
    outcome     text NOT NULL CONSTRAINT registration_ledger_outcome CHECK (outcome IN ('OK', 'TAKEN')),
    -- «مأخوذ» برمزٍ يُعدّ على الرمز نفسه (0005)، فلا صفّ له هنا.
    CONSTRAINT registration_ledger_taken_is_open CHECK (outcome = 'OK' OR via = 'OPEN')
);
CREATE INDEX registration_ledger_time ON registration_ledger (occurred_at);
ALTER TABLE registration_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE registration_ledger FORCE  ROW LEVEL SECURITY;
CREATE POLICY registration_ledger_owner_access ON registration_ledger FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- ما كان سقف 0005 يعدّه في آخر يوم: الرموز المستعملة، ومنها ما حُذف حسابه.
INSERT INTO registration_ledger (occurred_at, via, outcome)
SELECT used_at, 'CODE', 'OK' FROM signup_codes WHERE used_at > now() - interval '24 hours';

-- ── الحساب المفتوح ──────────────────────────────────────────────────────
-- أنشأه صاحبه بلا رابط: لا مشغّل يعرفه، فله حدودٌ أضيق في أسبوعه الأول.
ALTER TABLE users ADD COLUMN open_registered boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD CONSTRAINT open_registered_is_self_registered
    CHECK (NOT open_registered OR self_registered);

-- المحاولة تحمل أنها من حسابٍ جديد، وأثرها بعد الحذف كذلك: حصّة الحسابات
-- الجديدة لا يُفرغها حذفُ حسابٍ بعد استهلاك.
ALTER TABLE generation_attempts ADD COLUMN new_account boolean NOT NULL DEFAULT false;
ALTER TABLE attempt_tombstones  ADD COLUMN new_account boolean NOT NULL DEFAULT false;

-- حسابٌ مفتوحٌ عمره دون سبعة أيام. تستدعيها دوالّ المالك وحدها.
CREATE FUNCTION ew_new_open_account(p_user uuid) RETURNS boolean
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT coalesce((SELECT open_registered AND created_at > now() - interval '7 days'
                       FROM users WHERE id = p_user), false)
$$;

-- ما يمنع تسجيلاً بهذا الطريق الآن، باسم قيده، أو NULL. من الدفتر وحده.
CREATE FUNCTION ew_registration_blocker(p_via text) RETURNS text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT CASE
        WHEN count(*) FILTER (WHERE outcome = 'OK') >= 200 THEN 'registration_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'OK') >= 150
            THEN 'registration_open_daily_cap'
        WHEN p_via = 'OPEN' AND count(*) FILTER (WHERE via = 'OPEN' AND outcome = 'TAKEN') >= 60
            THEN 'registration_open_paused'
    END
      FROM registration_ledger
     WHERE occurred_at > now() - interval '24 hours'
$$;

-- تسألها الواجهة قبل الخطوة الأولى من التسجيل المفتوح، فلا يكتب أحدٌ تسع شاشاتٍ
-- بالنظر ليسمع في آخرها أن اليوم اكتمل. حالُ التطبيق كلّه، لا شيء عن أحد.
CREATE FUNCTION ew_open_registration_blocker() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_registration_blocker('OPEN')
$$;

-- ── التسجيل برمز: كما في 0005، والسقف من الدفتر ─────────────────────────
CREATE OR REPLACE FUNCTION ew_register(
    p_code bytea, p_login bytea, p_password_hash text, p_name text, p_birth date,
    p_profession text, p_terms_version text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid;
    code    signup_codes%ROWTYPE;
    blocker text;
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
    -- قفلٌ واحد للطريقين: تسجيلان متزامنان لا يريان العدّ نفسه فيمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('CODE');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
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
    INSERT INTO registration_ledger (via, outcome) VALUES ('CODE', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- ── التسجيل المفتوح ─────────────────────────────────────────────────────
-- النتيجة: (الحساب، 'OK') أو (NULL، 'TAKEN') لبريدٍ مأخوذ — وهذه تُكتب في الدفتر،
-- وستّون منها في يومٍ توقف التسجيل المفتوح كلّه: لا يصير أداة سؤالٍ عن الناس.
-- السقوف تُفحص قبل الإدراج، فالجواب عند امتلائها واحدٌ لكل بريد.
CREATE FUNCTION ew_register_open(
    p_login bytea, p_password_hash text, p_name text, p_birth date, p_profession text,
    p_terms_version text
) RETURNS TABLE (new_user uuid, outcome text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid;
    blocker text;
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
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.registration_daily_cap', 0));
    blocker := ew_registration_blocker('OPEN');
    IF blocker IS NOT NULL THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = blocker;
    END IF;
    INSERT INTO users (login_hmac, password_hash, activated_at, display_name, birth_date, profession,
                       self_registered, open_registered, terms_version, terms_accepted_at)
    VALUES (p_login, p_password_hash, now(), p_name, p_birth, p_profession, true, true, p_terms_version, now())
    ON CONFLICT (login_hmac) DO NOTHING
    RETURNING id INTO uid;
    IF uid IS NULL THEN
        INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'TAKEN');
        RETURN QUERY SELECT NULL::uuid, 'TAKEN'::text;
        RETURN;
    END IF;
    INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'OK');
    RETURN QUERY SELECT uid, 'OK'::text;
END
$$;

-- حدّ طلبات الكتابة اليومي لصاحب الجلسة وحده: 10 لحسابٍ مفتوحٍ جديد، و40 لغيره.
CREATE FUNCTION ew_my_generation_limit() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT CASE WHEN ew_new_open_account(id) THEN 10 ELSE 40 END
      FROM users WHERE id = ew_current_user() AND is_active
$$;

-- ── أثر المحاولة المحذوفة يحمل أنها من حسابٍ جديد ───────────────────────
CREATE OR REPLACE FUNCTION ew_attempt_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;

-- ── ثلاث حملاتٍ مفتوحة للحساب المفتوح الجديد ────────────────────────────
CREATE OR REPLACE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل):
    -- إمّا تنتظره الحملة فتُرفض بالمهنة الجديدة، وإمّا ينتظرها فيلغيها.
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    IF ew_new_open_account(NEW.user_id)
       AND (SELECT count(*) FROM campaigns
             WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 3 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'new_account_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

-- ── حدود الكتابة للحساب المفتوح الجديد ──────────────────────────────────
CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
    fresh   boolean;
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
    -- الحساب المفتوح الجديد: عشرة في اليوم. وقفل صفّ المستخدم أعلاه يجعل العدّ والإدراج ذرّيين.
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
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
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256, new_account)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image, fresh)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

-- ── المنح ───────────────────────────────────────────────────────────────
-- الدفتر بلا منح ولا سياسةٍ لدور الويب. ew_new_open_account وew_registration_blocker
-- تستدعيهما دوالّ المالك بصلاحيته؛ دور الويب لا يحتاجهما.
REVOKE ALL ON FUNCTION ew_new_open_account(uuid), ew_registration_blocker(text),
                       ew_open_registration_blocker(),
                       ew_register_open(bytea, text, text, date, text, text),
                       ew_my_generation_limit() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_open_registration_blocker(),
                          ew_register_open(bytea, text, text, date, text, text),
                          ew_my_generation_limit() TO eyework_app;
