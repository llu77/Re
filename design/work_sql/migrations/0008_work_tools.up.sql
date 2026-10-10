-- ════════════════════════════════════════════════════════════════════════
-- 0008_work_tools — المساعد في كل بوابة، وسجلّ المخزون، وسجلّ البلاغات
-- ════════════════════════════════════════════════════════════════════════
-- ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم، فيُفرض هنا:
--
--   • كل استدعاءٍ للنموذج خارج الحملة صفٌّ في ai_calls يُفتح قبل الاستدعاء بسقوفه:
--     واحدٌ جارٍ لكل مستخدم، وحدّ عشر دقائق ويومٍ لكل أداة (أضيق للحساب المفتوح
--     الجديد)، وحدّ يومٍ لكل أداةٍ في التطبيق كلّه، والسقف العام نفسه (ألفان في
--     اليوم، منها أربعمئة للحسابات الجديدة) يجمع الحملات وهذه معاً.
--   • لا نتيجة ناجحة بلا أثرها: جوابٌ أو أسطر سندٍ أو ردود، في المعاملة نفسها.
--   • الأداة لأصحاب مهنتها: سجلّ المخزون وقراءة السند لأمين المخزون، وسجلّ البلاغات
--     والردود للدعم الفني. والمساعد لكل مهنة.
--   • الرصيد يكتبه المحفّز وحده من الحركات، ولا ينزل تحت الصفر، والحركة لا تُعدَّل
--     ولا تُحذف: تُلغى مرةً واحدة، في يومها، وهي آخر حركةٍ لصنفها.
--   • صورة السند تُحذف عند تسجيل الاستلام أو إلغائه، في المعاملة نفسها، ولا تُخزَّن
--     ببياناتٍ وصفية.
--   • رسالة العميل تُحذف حين يُغلق بلاغها، وبعد سبعة أيام في كل حال (purge).
--   • الجواب الجاهز المشترك لا يقرؤه دور الويب ولا يكتبه إلا عبر دوالّ: لا هوية فيه
--     ولا سؤالٌ مكتوب، ويُسحب بضغطة «غير مفيدة» واحدة.
--   • العزل بالصفّ على eyework.user_id، مفروضٌ على المالك أيضاً (FORCE)، والمنح
--     بالأعمدة، ولا DELETE لدور الويب.
-- ════════════════════════════════════════════════════════════════════════

-- ── الأدوات التي تستدعي النموذج وسقوفها ─────────────────────────────────
-- جدولٌ لا ثوابت في الدوالّ: اختبارٌ يقارنه بـeyework/ai_limits.py.
CREATE TABLE ai_features (
    code             text PRIMARY KEY CONSTRAINT ai_feature_code CHECK (code IN ('ASSISTANT', 'RECEIPT', 'REPLY')),
    -- NULL: لكل مهنة.
    profession       text REFERENCES professions (code) ON DELETE RESTRICT,
    per_user_day     integer NOT NULL CHECK (per_user_day BETWEEN 1 AND 200),
    per_new_user_day integer NOT NULL CHECK (per_new_user_day BETWEEN 0 AND 200),
    per_user_10min   integer NOT NULL CHECK (per_user_10min BETWEEN 1 AND 50),
    app_day          integer NOT NULL CHECK (app_day BETWEEN 1 AND 2000),
    CONSTRAINT ai_feature_new_within_user CHECK (per_new_user_day <= per_user_day)
);
INSERT INTO ai_features (code, profession, per_user_day, per_new_user_day, per_user_10min, app_day) VALUES
    ('ASSISTANT', NULL,          30, 10, 10, 1000),
    ('RECEIPT',   'STOREKEEPER', 10,  3,  4,  300),
    ('REPLY',     'SUPPORT',     20,  5,  6,  500);

-- كل استدعاءٍ محاولةٌ تُحسب، نجحت أم فشلت.
CREATE TABLE ai_calls (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    feature        text NOT NULL REFERENCES ai_features (code) ON DELETE RESTRICT,
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    outcome        text CONSTRAINT ai_call_outcome CHECK (outcome IN (
                       'OK', 'UNUSABLE', 'OUT_OF_SCOPE', 'REFUSED', 'OUTPUT_INVALID', 'DISCARDED',
                       'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR')),
    input_tokens   integer CHECK (input_tokens >= 0),
    output_tokens  integer CHECK (output_tokens >= 0),
    -- النموذج الذي خدم فعلاً — قد يكون البديل من جهة الخادم.
    served_model   text CHECK (served_model IS NULL OR served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    prompt_version text CHECK (prompt_version IS NULL OR prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    api_request_id text CHECK (api_request_id IS NULL OR char_length(api_request_id) <= 128),
    -- من حسابٍ مفتوحٍ جديد لحظة البدء (0007): حصّة الجدد لا يُفرغها حذف.
    new_account    boolean NOT NULL DEFAULT false,
    CONSTRAINT ai_call_finished_iff_outcome CHECK ((finished_at IS NULL) = (outcome IS NULL)),
    UNIQUE (id, user_id)
);
CREATE INDEX ai_calls_user_time    ON ai_calls (user_id, started_at DESC);
CREATE INDEX ai_calls_feature_time ON ai_calls (feature, started_at DESC);
CREATE INDEX ai_calls_time         ON ai_calls (started_at DESC);

-- استدعاءٌ أُغلق لا يُعاد فتحه ولا تُعدَّل نتيجته (دالّة 0002 نفسها).
CREATE TRIGGER trg_ai_call_settle BEFORE UPDATE ON ai_calls
    FOR EACH ROW EXECUTE FUNCTION ew_attempt_settle_once();

-- حذف الحساب لا يُفرغ السقف العام: أثرٌ بلا هوية كمحاولات الحملة (0005).
CREATE FUNCTION ew_ai_call_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;
CREATE TRIGGER trg_ai_call_tombstone BEFORE DELETE ON ai_calls
    FOR EACH ROW EXECUTE FUNCTION ew_ai_call_tombstone();

-- ما قرأه صاحب الحساب من إشعار كل أداةٍ تُرسل شيئاً، وأيّ نسخةٍ منه.
CREATE TABLE feature_notices (
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    feature        text NOT NULL REFERENCES ai_features (code) ON DELETE RESTRICT,
    notice_version text NOT NULL CONSTRAINT feature_notice_version_shape
                       CHECK (notice_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
    accepted_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, feature)
);

-- ── السقف العام: الحملات وهذه معاً ──────────────────────────────────────
-- ما ربما فُوتر في آخر يوم، من كل الأدوات، ومن آثار ما حُذف. p_new_only: ما بدأه
-- حسابٌ مفتوحٌ جديد وحده. تستدعيها دوالّ المالك وحدها.
CREATE FUNCTION ew_ai_spend(p_new_only boolean) RETURNS bigint
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT (SELECT count(*) FROM generation_attempts
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM ai_calls
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM attempt_tombstones
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
$$;

-- يُسجّل قراءة الإشعار بنسختها لصاحب الجلسة. التطبيق يقرّر أيّ نسخةٍ هي الحالية.
CREATE FUNCTION ew_accept_notice(p_feature text, p_version text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    INSERT INTO feature_notices (user_id, feature, notice_version)
    VALUES (ew_current_user(), p_feature, p_version)
    ON CONFLICT (user_id, feature) DO UPDATE
       SET notice_version = EXCLUDED.notice_version, accepted_at = now()
     WHERE feature_notices.notice_version IS DISTINCT FROM EXCLUDED.notice_version
$$;

-- يفتح استدعاءً لصاحب الجلسة بعد كل السقوف، أو يرفض باسم قيده. داخليّة: تستدعيها
-- دوالّ كل أداةٍ بعد فحص حالها.
CREATE FUNCTION ew_ai_call_open(p_feature text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    f     ai_features%ROWTYPE;
    fresh boolean;
    call  uuid;
BEGIN
    -- قفل صفّ المستخدم يجعل العدّ والإدراج ذرّيين لكل مستخدم، كما في ew_begin_generation.
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO f FROM ai_features WHERE code = p_feature;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'feature' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_feature_unknown';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM feature_notices WHERE user_id = uid AND feature = p_feature) THEN
        RAISE EXCEPTION 'notice' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_notice_required';
    END IF;
    IF f.profession IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = f.profession) THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'ai_feature_profession';
    END IF;
    IF EXISTS (SELECT 1 FROM ai_calls
                WHERE user_id = uid AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_call_in_progress';
    END IF;
    IF (SELECT count(*) FROM ai_calls
         WHERE user_id = uid AND feature = p_feature
           AND started_at > now() - interval '10 minutes') >= f.per_user_10min THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_call_rate';
    END IF;
    fresh := ew_new_open_account(uid);
    IF (SELECT count(*) FROM ai_calls
         WHERE user_id = uid AND feature = p_feature AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours')
       >= CASE WHEN fresh THEN f.per_new_user_day ELSE f.per_user_day END THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation',
            CONSTRAINT = CASE WHEN fresh THEN 'ai_new_account_daily_cap' ELSE 'ai_daily_cap' END;
    END IF;
    -- القفل العام نفسه الذي يأخذه ew_begin_generation: السقف واحدٌ للأدوات كلها.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM ai_calls
         WHERE feature = p_feature AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= f.app_day THEN
        RAISE EXCEPTION 'feature' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_feature_app_cap';
    END IF;
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    INSERT INTO ai_calls (user_id, feature, new_account) VALUES (uid, p_feature, fresh)
    RETURNING id INTO call;
    RETURN call;
END
$$;

-- يُغلق استدعاءً مفتوحاً لصاحب الجلسة. داخليّة.
CREATE FUNCTION ew_ai_call_settle(
    p_call uuid, p_outcome text, p_input integer, p_output integer,
    p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE ai_calls
       SET finished_at = now(), outcome = p_outcome, input_tokens = p_input, output_tokens = p_output,
           served_model = p_model, prompt_version = p_prompt_version, api_request_id = p_request_id
     WHERE id = p_call AND user_id = ew_current_user() AND finished_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'no_data_found';
    END IF;
END
$$;

-- يُغلق استدعاءً لم يُنتج شيئاً (رفضٌ أو خطأٌ أو نصٌّ مرفوض)، ويُعلِم ما ينتظره أنه
-- فشل. النتائج التي لها أثرٌ تُغلق بدوالّ أداتها، في معاملة أثرها.
CREATE FUNCTION ew_finish_ai_call(
    p_call uuid, p_outcome text, p_input integer, p_output integer,
    p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_outcome IN ('OK', 'UNUSABLE', 'OUT_OF_SCOPE') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    PERFORM ew_ai_call_settle(p_call, p_outcome, p_input, p_output, p_model, p_prompt_version, p_request_id);
    UPDATE assistant_exchanges SET status = 'FAILED', finished_at = now()
     WHERE ai_call_id = p_call AND user_id = ew_current_user() AND status = 'PENDING';
    UPDATE reply_requests SET status = 'FAILED', call_id = NULL
     WHERE call_id = p_call AND user_id = ew_current_user() AND status = 'PENDING';
    UPDATE reply_requests SET call_id = NULL, pending_option = NULL
     WHERE call_id = p_call AND user_id = ew_current_user() AND status = 'READY';
END
$$;

-- ما بقي لصاحب الجلسة اليوم من كل أداةٍ تخصّ مهنته، ونسخة الإشعار الذي قرأه.
CREATE FUNCTION ew_my_ai_limits()
RETURNS TABLE (feature text, per_day integer, used_today bigint, notice_version text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT f.code,
           CASE WHEN ew_new_open_account(u.id) THEN f.per_new_user_day ELSE f.per_user_day END,
           (SELECT count(*) FROM ai_calls c
             WHERE c.user_id = u.id AND c.feature = f.code AND ew_is_billable(c.outcome)
               AND c.started_at > now() - interval '24 hours'),
           (SELECT n.notice_version FROM feature_notices n WHERE n.user_id = u.id AND n.feature = f.code)
      FROM users u CROSS JOIN ai_features f
     WHERE u.id = ew_current_user() AND u.is_active
       AND (f.profession IS NULL OR f.profession = u.profession)
     ORDER BY f.code
$$;

-- ── السقف العام في الحملة يعدّ الأدوات الأخرى أيضاً ─────────────────────
-- 0007 كما هو، والسطران المعلَّمان «0008» فقط.
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
    -- 0008: السقف العام يعدّ استدعاءات الأدوات الأخرى (ai_calls) مع المحاولات وآثارها.
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    -- 0008: وكذلك استدعاءات الأدوات الأخرى من حساباتٍ جديدة.
    IF fresh AND ew_ai_spend(true) >= 400 THEN
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

-- ════════════════════════════════════════════════════════════════════════
-- المساعد
-- ════════════════════════════════════════════════════════════════════════
-- نظير eyework/assistant_prompt.py PRESETS؛ اختبارٌ يقارنهما.
CREATE FUNCTION ew_assistant_preset_ok(p_scope text, p_preset text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT (p_scope = 'TASK'   AND p_preset IN ('EXPLAIN_STEPS', 'NEEDED_SKILLS', 'HOW_TO_START', 'PRACTICE', 'FREE'))
        OR (p_scope = 'SKILL'  AND p_preset IN ('SKILL_MEANING', 'SKILL_TASKS', 'SKILL_PRACTICE', 'PRACTICE', 'FREE'))
        OR (p_scope = 'PORTAL' AND p_preset IN ('TOP_TASKS', 'TOP_SKILLS', 'PRACTICE', 'FREE'))
$$;

-- سؤالٌ جاهز عن محتوى البوابة وحده: جوابه لا يخصّ سائله، فيُعاد لغيره.
CREATE FUNCTION ew_assistant_cacheable(p_preset text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT p_preset NOT IN ('PRACTICE', 'FREE')
$$;

-- الجواب الجاهز: لكل (محتوى البوابة، نسخة التعليمات، البند، السؤال) جوابٌ حيّ واحد.
-- لا مستخدم فيه ولا سؤالٌ مكتوب. دور الويب لا يصله إلا عبر الدوالّ أدناه.
CREATE TABLE assistant_ready_answers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profession     text NOT NULL REFERENCES professions (code) ON DELETE CASCADE,
    context_sha    bytea NOT NULL CHECK (octet_length(context_sha) = 32),
    prompt_version text NOT NULL CHECK (prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    scope          text NOT NULL,
    item_key       text,
    preset         text NOT NULL,
    answer         jsonb NOT NULL CONSTRAINT ready_answer_shape
                       CHECK (jsonb_typeof(answer) = 'object' AND octet_length(answer::text) <= 4096),
    served_model   text NOT NULL CHECK (served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    created_at     timestamptz NOT NULL DEFAULT now(),
    retired_at     timestamptz,
    CONSTRAINT ready_answer_preset CHECK (ew_assistant_preset_ok(scope, preset) AND ew_assistant_cacheable(preset)),
    CONSTRAINT ready_answer_item CHECK ((scope = 'PORTAL') = (item_key IS NULL)
                                        AND (item_key IS NULL OR item_key ~ '^[TS][0-9]{1,2}$'))
);
CREATE UNIQUE INDEX assistant_ready_one_live
    ON assistant_ready_answers (profession, context_sha, prompt_version, scope, (coalesce(item_key, '')), preset)
    WHERE retired_at IS NULL;

CREATE TABLE assistant_exchanges (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- مهنة السائل لحظة السؤال: البند يُفهم في بوابتها.
    profession      text NOT NULL REFERENCES professions (code) ON DELETE RESTRICT,
    scope           text NOT NULL,
    item_key        text,
    preset          text NOT NULL,
    -- السؤال المكتوب بعد حذف وسائل الاتصال منه، كما أُرسل. الجاهز لا يُخزَّن نصّه.
    question        text CONSTRAINT exchange_question_shape CHECK (
                        question IS NULL OR (char_length(question) BETWEEN 3 AND 200
                                             AND question !~ '[\x01-\x1f\x7f]')),
    context_sha     bytea NOT NULL CHECK (octet_length(context_sha) = 32),
    prompt_version  text NOT NULL CHECK (prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    status          text NOT NULL DEFAULT 'PENDING'
                        CONSTRAINT exchange_status CHECK (status IN ('PENDING', 'DONE', 'OUT_OF_SCOPE', 'FAILED')),
    answer          jsonb CONSTRAINT exchange_answer_shape
                        CHECK (answer IS NULL OR (jsonb_typeof(answer) = 'object'
                                                  AND octet_length(answer::text) <= 4096)),
    ai_call_id      uuid,
    ready_answer_id uuid REFERENCES assistant_ready_answers (id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    not_helpful_at  timestamptz,
    FOREIGN KEY (ai_call_id, user_id) REFERENCES ai_calls (id, user_id) ON DELETE SET NULL (ai_call_id),
    CONSTRAINT exchange_preset CHECK (ew_assistant_preset_ok(scope, preset)),
    CONSTRAINT exchange_item CHECK ((scope = 'PORTAL') = (item_key IS NULL)
                                    AND (item_key IS NULL OR item_key ~ '^[TS][0-9]{1,2}$')),
    CONSTRAINT exchange_question_iff_free CHECK ((preset = 'FREE') = (question IS NOT NULL)),
    CONSTRAINT exchange_finished CHECK ((status = 'PENDING') = (finished_at IS NULL)),
    CONSTRAINT exchange_answer_iff_done CHECK ((status = 'DONE') = (answer IS NOT NULL)),
    CONSTRAINT exchange_not_helpful_done CHECK (not_helpful_at IS NULL OR status = 'DONE')
);
CREATE UNIQUE INDEX assistant_exchanges_call ON assistant_exchanges (ai_call_id) WHERE ai_call_id IS NOT NULL;
CREATE INDEX assistant_exchanges_user_time ON assistant_exchanges (user_id, created_at DESC);

-- يبدأ سؤالاً: جوابٌ جاهز إن وُجد (بلا استدعاء ولا سقف)، وإلا استدعاءٌ بسقوفه.
-- p_notice_version: نسخة الإشعار التي عرضتها الواجهة الآن، أو NULL إن قُرئ من قبل.
CREATE FUNCTION ew_assistant_begin(
    p_scope text, p_item_key text, p_preset text, p_question text,
    p_context_sha bytea, p_prompt_version text, p_notice_version text
) RETURNS TABLE (exchange_id uuid, ai_call_id uuid, answer jsonb)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    prof  text;
    ready assistant_ready_answers%ROWTYPE;
    call  uuid;
    ex    uuid;
BEGIN
    SELECT profession INTO prof FROM users WHERE id = uid AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_notice_version IS NOT NULL THEN
        PERFORM ew_accept_notice('ASSISTANT', p_notice_version);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM feature_notices WHERE user_id = uid AND feature = 'ASSISTANT') THEN
        RAISE EXCEPTION 'notice' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_notice_required';
    END IF;
    IF ew_assistant_cacheable(p_preset) THEN
        SELECT * INTO ready FROM assistant_ready_answers r
         WHERE r.profession = prof AND r.context_sha = p_context_sha AND r.prompt_version = p_prompt_version
           AND r.scope = p_scope AND r.item_key IS NOT DISTINCT FROM p_item_key AND r.preset = p_preset
           AND r.retired_at IS NULL;
        IF FOUND THEN
            INSERT INTO assistant_exchanges (user_id, profession, scope, item_key, preset, context_sha,
                                             prompt_version, status, answer, ready_answer_id, finished_at)
            VALUES (uid, prof, p_scope, p_item_key, p_preset, p_context_sha, p_prompt_version,
                    'DONE', ready.answer, ready.id, now())
            RETURNING id INTO ex;
            RETURN QUERY SELECT ex, NULL::uuid, ready.answer;
            RETURN;
        END IF;
    END IF;
    call := ew_ai_call_open('ASSISTANT');
    INSERT INTO assistant_exchanges (user_id, profession, scope, item_key, preset, question, context_sha,
                                     prompt_version, ai_call_id)
    VALUES (uid, prof, p_scope, p_item_key, p_preset, p_question, p_context_sha, p_prompt_version, call)
    RETURNING id INTO ex;
    RETURN QUERY SELECT ex, call, NULL::jsonb;
END
$$;

-- يكتب نتيجة السؤال ويُغلق استدعاءه في معاملةٍ واحدة. الجواب الناجح لسؤالٍ جاهز
-- يصير جواباً جاهزاً لغيره (إن لم يسبقه غيره).
CREATE FUNCTION ew_assistant_record(
    p_exchange uuid, p_outcome text, p_answer jsonb, p_input integer, p_output integer,
    p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    e     assistant_exchanges%ROWTYPE;
    a     ai_calls%ROWTYPE;
    ready uuid;
BEGIN
    SELECT * INTO e FROM assistant_exchanges WHERE id = p_exchange AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR e.status <> 'PENDING' OR e.ai_call_id IS NULL THEN
        RAISE EXCEPTION 'exchange' USING ERRCODE = 'check_violation', CONSTRAINT = 'exchange_not_pending';
    END IF;
    SELECT * INTO a FROM ai_calls WHERE id = e.ai_call_id FOR UPDATE;
    IF a.finished_at IS NOT NULL OR a.started_at <= now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'lease' USING ERRCODE = 'check_violation', CONSTRAINT = 'exchange_not_pending';
    END IF;
    IF p_outcome NOT IN ('OK', 'OUT_OF_SCOPE') OR (p_outcome = 'OK') <> (p_answer IS NOT NULL) THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    IF p_outcome = 'OK' AND ew_assistant_cacheable(e.preset) THEN
        INSERT INTO assistant_ready_answers (profession, context_sha, prompt_version, scope, item_key, preset,
                                             answer, served_model)
        VALUES (e.profession, e.context_sha, e.prompt_version, e.scope, e.item_key, e.preset, p_answer, p_model)
        ON CONFLICT (profession, context_sha, prompt_version, scope, (coalesce(item_key, '')), preset)
            WHERE retired_at IS NULL DO NOTHING
        RETURNING id INTO ready;
    END IF;
    UPDATE assistant_exchanges
       SET status = CASE p_outcome WHEN 'OK' THEN 'DONE' ELSE 'OUT_OF_SCOPE' END,
           answer = p_answer, ready_answer_id = ready, finished_at = now()
     WHERE id = p_exchange;
    PERFORM ew_ai_call_settle(e.ai_call_id, p_outcome, p_input, p_output, p_model, p_prompt_version, p_request_id);
END
$$;

-- «غير مفيدة»: تُسجَّل للسائل، ويُسحب الجواب الجاهز الذي جاء منه أو صار منه.
CREATE FUNCTION ew_assistant_not_helpful(p_exchange uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    e assistant_exchanges%ROWTYPE;
BEGIN
    SELECT * INTO e FROM assistant_exchanges WHERE id = p_exchange AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'exchange' USING ERRCODE = 'no_data_found';
    END IF;
    IF e.status <> 'DONE' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'exchange_not_helpful_done';
    END IF;
    IF e.not_helpful_at IS NOT NULL THEN
        RETURN;
    END IF;
    UPDATE assistant_exchanges SET not_helpful_at = now() WHERE id = p_exchange;
    IF e.ready_answer_id IS NOT NULL THEN
        UPDATE assistant_ready_answers SET retired_at = now()
         WHERE id = e.ready_answer_id AND retired_at IS NULL;
    END IF;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- سجلّ المخزون
-- ════════════════════════════════════════════════════════════════════════
-- نظير eyework/stock.py name_key: يجمع «أ إ آ ٱ» إلى «ا»، و«ى» إلى «ي»، و«ة» إلى
-- «ه»، ويحذف التطويل والتشكيل، ويوحّد المسافات. اختبارٌ يقارن الاثنين.
CREATE FUNCTION ew_stock_name_key(p_name text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT btrim(regexp_replace(
               regexp_replace(translate(lower(normalize(p_name, NFKC)), 'أإآٱىةـ', 'اااايه'),
                              '[ً-ْٰ]', '', 'g'),
               '\s+', ' ', 'g'))
$$;

CREATE TABLE stock_items (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name             text NOT NULL CONSTRAINT stock_item_name_shape CHECK (
                         char_length(name) BETWEEN 1 AND 40 AND name = btrim(name)
                         AND name !~ '[\x01-\x1f\x7f‎‏‪-‮⁦-⁩]'),
    -- يكتبه المحفّز من الاسم.
    name_key         text NOT NULL DEFAULT '',
    unit             text NOT NULL CONSTRAINT stock_item_unit
                         CHECK (unit IN ('PIECE', 'BOX', 'CARTON', 'PACK', 'PALLET', 'KG', 'LITRE', 'METRE')),
    -- يكتبه محفّز الحركات وحده.
    balance          integer NOT NULL DEFAULT 0 CONSTRAINT stock_item_balance CHECK (balance BETWEEN 0 AND 10000000),
    row_version      integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    last_movement_at timestamptz,
    UNIQUE (user_id, name_key),
    UNIQUE (id, user_id)
);
CREATE INDEX stock_items_recent ON stock_items (user_id, last_movement_at DESC NULLS LAST, name_key);

-- سند استلامٍ يقرؤه المساعد من صورته، ويؤكّد صاحبه أسطره سطراً سطراً.
CREATE TABLE stock_receipts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'DRAFT'
                        CONSTRAINT stock_receipt_status CHECK (status IN ('DRAFT', 'READ', 'CONFIRMED', 'CANCELLED')),
    row_version     integer NOT NULL DEFAULT 1,
    read_call_id    uuid,
    read_attempts   smallint NOT NULL DEFAULT 0 CONSTRAINT stock_receipt_read_cap CHECK (read_attempts BETWEEN 0 AND 3),
    unusable_reason text CONSTRAINT stock_receipt_reason CHECK (unusable_reason IS NULL OR unusable_reason IN
                        ('NOT_A_DELIVERY_NOTE', 'UNREADABLE', 'TOO_MANY_LINES', 'NO_QUANTITIES')),
    -- أسطرٌ قرأها المساعد ورفضها الفحص: تُذكر للمستخدم ليضيفها بيده.
    dropped_lines   smallint NOT NULL DEFAULT 0 CHECK (dropped_lines BETWEEN 0 AND 20),
    document_ref    text CONSTRAINT stock_receipt_ref_shape CHECK (document_ref IS NULL OR
                        document_ref ~ '^[A-Za-z0-9٠-٩/._-]([A-Za-z0-9٠-٩/._ -]{0,28}[A-Za-z0-9٠-٩/._-])?$'),
    party           text CONSTRAINT stock_receipt_party_shape CHECK (party IS NULL OR (
                        char_length(party) BETWEEN 1 AND 40 AND party = btrim(party)
                        AND party !~ '[\x01-\x1f\x7f‎‏‪-‮⁦-⁩]')),
    occurred_on     date,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    confirmed_at    timestamptz,
    cancelled_at    timestamptz,
    UNIQUE (id, user_id),
    FOREIGN KEY (read_call_id, user_id) REFERENCES ai_calls (id, user_id) ON DELETE SET NULL (read_call_id),
    CONSTRAINT stock_receipt_confirmed_time CHECK ((status = 'CONFIRMED') = (confirmed_at IS NOT NULL)),
    CONSTRAINT stock_receipt_cancelled_time CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))
);
CREATE INDEX stock_receipts_user_recent ON stock_receipts (user_id, updated_at DESC);

CREATE TABLE stock_movements (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid NOT NULL,
    item_id           uuid NOT NULL,
    kind              text NOT NULL CONSTRAINT stock_movement_kind CHECK (kind IN ('RECEIVE', 'ISSUE', 'COUNT')),
    -- المستلم أو المصروف أو المعدود.
    quantity          integer NOT NULL CONSTRAINT stock_movement_quantity CHECK (quantity BETWEEN 0 AND 100000),
    -- ما في السند، والتالف غير المقبول: للاستلام وحده.
    expected_quantity integer CONSTRAINT stock_movement_expected
                          CHECK (expected_quantity IS NULL OR expected_quantity BETWEEN 0 AND 100000),
    damaged_quantity  integer NOT NULL DEFAULT 0 CONSTRAINT stock_movement_damaged
                          CHECK (damaged_quantity BETWEEN 0 AND 100000),
    party             text CONSTRAINT stock_movement_party_shape CHECK (party IS NULL OR (
                          char_length(party) BETWEEN 1 AND 40 AND party = btrim(party)
                          AND party !~ '[\x01-\x1f\x7f‎‏‪-‮⁦-⁩]')),
    document_ref      text CONSTRAINT stock_movement_ref_shape CHECK (document_ref IS NULL OR
                          document_ref ~ '^[A-Za-z0-9٠-٩/._-]([A-Za-z0-9٠-٩/._ -]{0,28}[A-Za-z0-9٠-٩/._-])?$'),
    occurred_on       date NOT NULL,
    receipt_id        uuid,
    -- يولّده العميل عند فتح شاشة المراجعة: الضغطة المكرّرة لا تُسجّل حركتين.
    client_token      uuid NOT NULL,
    -- يكتبها المحفّز.
    delta             integer NOT NULL DEFAULT 0,
    balance_after     integer NOT NULL DEFAULT 0,
    created_at        timestamptz NOT NULL DEFAULT now(),
    voided_at         timestamptz,
    UNIQUE (user_id, client_token),
    FOREIGN KEY (item_id, user_id) REFERENCES stock_items (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (receipt_id, user_id) REFERENCES stock_receipts (id, user_id) ON DELETE SET NULL (receipt_id),
    -- الاستلام بلا كمية أثرٌ لنقصٍ كامل في السند، فيحتاج كمية السند.
    CONSTRAINT stock_movement_positive
        CHECK (kind = 'COUNT' OR quantity > 0 OR (kind = 'RECEIVE' AND expected_quantity > 0)),
    CONSTRAINT stock_movement_receive_fields
        CHECK (kind = 'RECEIVE' OR (expected_quantity IS NULL AND damaged_quantity = 0 AND receipt_id IS NULL))
);
CREATE INDEX stock_movements_item_time ON stock_movements (item_id, created_at DESC, id DESC);
CREATE INDEX stock_movements_user_time ON stock_movements (user_id, created_at DESC);

CREATE TABLE stock_receipt_images (
    receipt_id  uuid PRIMARY KEY,
    user_id     uuid NOT NULL,
    jpeg        bytea NOT NULL,
    width       smallint NOT NULL CHECK (width  BETWEEN 320 AND 1568),
    height      smallint NOT NULL CHECK (height BETWEEN 320 AND 1568),
    sha256      bytea NOT NULL CHECK (octet_length(sha256) = 32),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (receipt_id, user_id) REFERENCES stock_receipts (id, user_id) ON DELETE CASCADE,
    CONSTRAINT receipt_image_size        CHECK (octet_length(jpeg) BETWEEN 1 AND 3145728),
    CONSTRAINT receipt_image_is_jpeg     CHECK (substring(jpeg FROM 1 FOR 3) = '\xffd8ff'::bytea),
    CONSTRAINT receipt_image_no_metadata CHECK (ew_jpeg_has_no_metadata(jpeg)),
    CONSTRAINT receipt_image_no_exif     CHECK (position('\x457869660000'::bytea IN jpeg) = 0),
    CONSTRAINT receipt_image_no_xmp      CHECK (position('\x687474703a2f2f6e732e61646f62652e636f6d2f7861702f'::bytea
                                                         IN jpeg) = 0)
);
ALTER TABLE stock_receipt_images ALTER COLUMN jpeg SET STORAGE EXTERNAL;

CREATE TABLE stock_receipt_lines (
    receipt_id        uuid NOT NULL,
    user_id           uuid NOT NULL,
    line_no           smallint NOT NULL CHECK (line_no BETWEEN 1 AND 20),
    -- ما قرأه المساعد، لا يتغيّر.
    read_name         text NOT NULL,
    read_quantity     integer NOT NULL CHECK (read_quantity BETWEEN 0 AND 100000),
    read_unit         text NOT NULL,
    unclear           boolean NOT NULL,
    -- ما يقرّه المستخدم: الاسم، والمستلم فعلاً، وما في السند، والتالف، والوحدة، والصنف.
    name              text NOT NULL,
    quantity          integer NOT NULL CHECK (quantity BETWEEN 0 AND 100000),
    document_quantity integer NOT NULL CHECK (document_quantity BETWEEN 0 AND 100000),
    damaged_quantity  integer NOT NULL DEFAULT 0 CHECK (damaged_quantity BETWEEN 0 AND 100000),
    unit              text NOT NULL,
    item_id           uuid,
    decision          text NOT NULL DEFAULT 'PENDING'
                          CONSTRAINT receipt_line_decision CHECK (decision IN ('PENDING', 'ACCEPTED', 'REJECTED')),
    edited            boolean NOT NULL DEFAULT false,
    PRIMARY KEY (receipt_id, line_no),
    FOREIGN KEY (receipt_id, user_id) REFERENCES stock_receipts (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id, user_id) REFERENCES stock_items (id, user_id) ON DELETE SET NULL (item_id),
    CONSTRAINT receipt_line_names CHECK (
        char_length(read_name) BETWEEN 1 AND 40 AND char_length(name) BETWEEN 1 AND 40
        AND name = btrim(name) AND name !~ '[\x01-\x1f\x7f‎‏‪-‮⁦-⁩]'),
    CONSTRAINT receipt_line_units CHECK (
        read_unit IN ('PIECE', 'BOX', 'CARTON', 'PACK', 'PALLET', 'KG', 'LITRE', 'METRE', 'UNKNOWN')
        AND unit IN ('PIECE', 'BOX', 'CARTON', 'PACK', 'PALLET', 'KG', 'LITRE', 'METRE', 'UNKNOWN')),
    CONSTRAINT receipt_line_accept_known_unit CHECK (decision <> 'ACCEPTED' OR unit <> 'UNKNOWN'),
    CONSTRAINT receipt_line_accept_something CHECK (decision <> 'ACCEPTED' OR quantity > 0 OR document_quantity > 0)
);

-- ── محفّزات المخزون ─────────────────────────────────────────────────────
-- الصنف لأمين المخزون، وخمسمئة صنفٍ لكل حساب، ويبدأ برصيدٍ صفر.
CREATE FUNCTION ew_stock_item_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'STOREKEEPER' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'stock_needs_storekeeper';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.stock_items:' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM stock_items WHERE user_id = NEW.user_id) >= 500 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_item_cap';
    END IF;
    NEW.name_key := ew_stock_name_key(NEW.name);
    IF NEW.name_key = '' THEN
        RAISE EXCEPTION 'name' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_item_name_shape';
    END IF;
    NEW.balance := 0;
    NEW.row_version := 1;
    NEW.last_movement_at := NULL;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_item_insert BEFORE INSERT ON stock_items
    FOR EACH ROW EXECUTE FUNCTION ew_stock_item_insert_guard();

-- الصنف لا يتغيّر إلا برصيده (من الحركات)، ورقم صفّه يزيد مع كل تغيير.
CREATE FUNCTION ew_stock_item_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version OR NEW.name <> OLD.name OR NEW.unit <> OLD.unit
       OR NEW.name_key <> OLD.name_key THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_item_managed_columns';
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_item_update BEFORE UPDATE ON stock_items
    FOR EACH ROW EXECUTE FUNCTION ew_stock_item_update_guard();

-- الحركة تكتب أثرها في الرصيد في المعاملة نفسها، تحت قفل صفّ الصنف.
CREATE FUNCTION ew_stock_movement_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    item  stock_items%ROWTYPE;
    today date := ew_riyadh_today();
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'STOREKEEPER' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'stock_needs_storekeeper';
    END IF;
    SELECT * INTO item FROM stock_items WHERE id = NEW.item_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'foreign_key_violation', CONSTRAINT = 'stock_movements_item_id_user_id_fkey';
    END IF;
    IF NEW.occurred_on > today OR NEW.occurred_on < today - 30 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_movement_date';
    END IF;
    NEW.delta := CASE NEW.kind
        WHEN 'RECEIVE' THEN NEW.quantity
        WHEN 'ISSUE'   THEN -NEW.quantity
        ELSE NEW.quantity - item.balance END;
    IF item.balance + NEW.delta < 0 THEN
        RAISE EXCEPTION 'balance' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_negative_balance';
    END IF;
    NEW.balance_after := item.balance + NEW.delta;
    NEW.created_at := now();
    NEW.voided_at := NULL;
    UPDATE stock_items SET balance = NEW.balance_after, last_movement_at = now() WHERE id = item.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_movement_insert BEFORE INSERT ON stock_movements
    FOR EACH ROW EXECUTE FUNCTION ew_stock_movement_insert();

-- لا تعديل: إلغاءٌ واحد، في الأربع والعشرين ساعة الأولى، لآخر حركةٍ قائمة لصنفها.
CREATE FUNCTION ew_stock_movement_void() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    item stock_items%ROWTYPE;
BEGIN
    IF ROW(NEW.id, NEW.user_id, NEW.item_id, NEW.kind, NEW.quantity, NEW.expected_quantity,
           NEW.damaged_quantity, NEW.party, NEW.document_ref, NEW.occurred_on, NEW.client_token,
           NEW.delta, NEW.balance_after, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.user_id, OLD.item_id, OLD.kind, OLD.quantity, OLD.expected_quantity,
           OLD.damaged_quantity, OLD.party, OLD.document_ref, OLD.occurred_on, OLD.client_token,
           OLD.delta, OLD.balance_after, OLD.created_at) THEN
        RAISE EXCEPTION 'append-only' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_movement_append_only';
    END IF;
    -- receipt_id يصير NULL حين يُحذف سنده (purge)، ولا شيء غيره يتغيّر بلا إلغاء.
    IF NEW.voided_at IS NOT DISTINCT FROM OLD.voided_at THEN
        RETURN NEW;
    END IF;
    IF OLD.voided_at IS NOT NULL OR NEW.voided_at IS NULL THEN
        RAISE EXCEPTION 'void' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_void_once';
    END IF;
    IF OLD.created_at <= now() - interval '24 hours' THEN
        RAISE EXCEPTION 'window' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_void_window';
    END IF;
    SELECT * INTO item FROM stock_items WHERE id = OLD.item_id FOR UPDATE;
    IF EXISTS (SELECT 1 FROM stock_movements m
                WHERE m.item_id = OLD.item_id AND m.voided_at IS NULL AND m.id <> OLD.id
                  AND (m.created_at, m.id) > (OLD.created_at, OLD.id)) THEN
        RAISE EXCEPTION 'latest' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_void_not_latest';
    END IF;
    IF item.balance - OLD.delta < 0 THEN
        RAISE EXCEPTION 'balance' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_negative_balance';
    END IF;
    NEW.voided_at := now();
    UPDATE stock_items SET balance = item.balance - OLD.delta, last_movement_at = now() WHERE id = item.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_movement_void BEFORE UPDATE ON stock_movements
    FOR EACH ROW EXECUTE FUNCTION ew_stock_movement_void();

-- السند لأمين المخزون، وخمسةٌ مفتوحة لكل حساب، ويبدأ مسودة.
CREATE FUNCTION ew_stock_receipt_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'STOREKEEPER' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'stock_needs_storekeeper';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.stock_receipts:' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM stock_receipts
         WHERE user_id = NEW.user_id AND status IN ('DRAFT', 'READ')) >= 5 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_open_cap';
    END IF;
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.read_call_id IS NOT NULL OR NEW.read_attempts <> 0
       OR NEW.confirmed_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_starts_as_draft';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_receipt_insert BEFORE INSERT ON stock_receipts
    FOR EACH ROW EXECUTE FUNCTION ew_stock_receipt_insert_guard();

-- الحالات: DRAFT → READ → CONFIRMED، وDRAFT/READ → CANCELLED. ما بعد التسجيل أو
-- الإلغاء ثابت. التفاصيل (رقم السند والجهة والتاريخ) تتغيّر قبلهما فقط.
CREATE FUNCTION ew_stock_receipt_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.status IN ('CONFIRMED', 'CANCELLED') THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_managed_columns';
    END IF;
    IF NEW.status <> OLD.status AND (OLD.status, NEW.status) NOT IN
       (('DRAFT', 'READ'), ('READ', 'CONFIRMED'), ('DRAFT', 'CANCELLED'), ('READ', 'CANCELLED')) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_transition';
    END IF;
    IF NEW.read_call_id IS DISTINCT FROM OLD.read_call_id AND OLD.status <> 'DRAFT' AND NEW.read_call_id IS NOT NULL THEN
        RAISE EXCEPTION 'read' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_transition';
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.confirmed_at := CASE WHEN NEW.status = 'CONFIRMED' THEN now() END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() END;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_receipt_update BEFORE UPDATE ON stock_receipts
    FOR EACH ROW EXECUTE FUNCTION ew_stock_receipt_update_guard();

-- صورة السند تُحذف حين يُسجَّل الاستلام أو يُلغى. بصلاحية المالك: دور الويب لا يحذف.
CREATE FUNCTION ew_stock_receipt_purge_image() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM stock_receipt_images WHERE receipt_id = NEW.id;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_stock_receipt_purge_image AFTER UPDATE OF status ON stock_receipts
    FOR EACH ROW WHEN (NEW.status IN ('CONFIRMED', 'CANCELLED'))
    EXECUTE FUNCTION ew_stock_receipt_purge_image();

-- الصورة تُوضع أو تُستبدل والسند مسودة، ولا تتغيّر تحت قراءةٍ جارية.
CREATE FUNCTION ew_stock_receipt_image_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    r stock_receipts%ROWTYPE;
BEGIN
    SELECT * INTO r FROM stock_receipts WHERE id = NEW.receipt_id FOR UPDATE;
    IF r.status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_image_only_in_draft';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.receipt_id <> OLD.receipt_id OR NEW.user_id <> OLD.user_id) THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_image_only_in_draft';
    END IF;
    IF EXISTS (SELECT 1 FROM ai_calls
                WHERE id = r.read_call_id AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'locked' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_image_locked_during_read';
    END IF;
    IF TG_OP = 'INSERT' THEN
        NEW.created_at := now();
    ELSE
        NEW.created_at := OLD.created_at;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_receipt_image_guard BEFORE INSERT OR UPDATE ON stock_receipt_images
    FOR EACH ROW EXECUTE FUNCTION ew_stock_receipt_image_guard();

-- السطر يتغيّر والسند مقروءٌ لم يُسجَّل، وما قرأه المساعد لا يتغيّر. الصنف المختار
-- يفرض وحدته.
CREATE FUNCTION ew_stock_receipt_line_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    status    text;
    item_unit text;
BEGIN
    SELECT r.status INTO status FROM stock_receipts r WHERE r.id = OLD.receipt_id FOR SHARE;
    IF status IS DISTINCT FROM 'READ' THEN
        RAISE EXCEPTION 'line' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_line_only_while_read';
    END IF;
    IF ROW(NEW.receipt_id, NEW.user_id, NEW.line_no, NEW.read_name, NEW.read_quantity, NEW.read_unit, NEW.unclear)
       IS DISTINCT FROM
       ROW(OLD.receipt_id, OLD.user_id, OLD.line_no, OLD.read_name, OLD.read_quantity, OLD.read_unit, OLD.unclear) THEN
        RAISE EXCEPTION 'read' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_line_read_is_fixed';
    END IF;
    IF NEW.item_id IS NOT NULL THEN
        SELECT unit INTO item_unit FROM stock_items WHERE id = NEW.item_id AND user_id = NEW.user_id;
        NEW.unit := item_unit;
    END IF;
    NEW.edited := OLD.edited OR ROW(NEW.name, NEW.quantity, NEW.document_quantity, NEW.damaged_quantity,
                                    NEW.unit, NEW.item_id)
                                IS DISTINCT FROM
                                ROW(OLD.name, OLD.quantity, OLD.document_quantity, OLD.damaged_quantity,
                                    OLD.unit, OLD.item_id);
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_stock_receipt_line_guard BEFORE UPDATE ON stock_receipt_lines
    FOR EACH ROW EXECUTE FUNCTION ew_stock_receipt_line_guard();

-- كل قرارٍ على سطرٍ يغيّر رقم صفّ السند: «سجّل الاستلام» يُرسل ما رآه صاحبه.
CREATE FUNCTION ew_stock_receipt_line_touch() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE stock_receipts SET updated_at = now() WHERE id = NEW.receipt_id;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_stock_receipt_line_touch AFTER UPDATE ON stock_receipt_lines
    FOR EACH ROW EXECUTE FUNCTION ew_stock_receipt_line_touch();

-- ── قراءة السند وتسجيله ─────────────────────────────────────────────────
CREATE FUNCTION ew_receipt_begin_read(p_receipt uuid, p_expected_row_version integer, p_notice_version text)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_current_user();
    r    stock_receipts%ROWTYPE;
    call uuid;
BEGIN
    IF p_notice_version IS NOT NULL THEN
        PERFORM ew_accept_notice('RECEIPT', p_notice_version);
    END IF;
    SELECT * INTO r FROM stock_receipts WHERE id = p_receipt AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'receipt' USING ERRCODE = 'no_data_found';
    END IF;
    IF r.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF r.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_transition';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM stock_receipt_images WHERE receipt_id = p_receipt) THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_needs_image';
    END IF;
    IF r.read_attempts >= 3 THEN
        RAISE EXCEPTION 'reads' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_read_cap';
    END IF;
    call := ew_ai_call_open('RECEIPT');
    UPDATE stock_receipts
       SET read_call_id = call, read_attempts = r.read_attempts + 1, unusable_reason = NULL
     WHERE id = p_receipt;
    RETURN call;
END
$$;

-- يكتب نتيجة القراءة ويُغلق استدعاءها. p_lines: [{line_no, name, quantity, unit, unclear}]
-- بعد فحصها في التطبيق؛ والمطابقة بصنفٍ قائم هنا، بالاسم الموحَّد وحده.
CREATE FUNCTION ew_receipt_record_read(
    p_receipt uuid, p_outcome text, p_reason text, p_document_ref text, p_lines jsonb, p_dropped integer,
    p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    r   stock_receipts%ROWTYPE;
    a   ai_calls%ROWTYPE;
    n   integer;
BEGIN
    SELECT * INTO r FROM stock_receipts WHERE id = p_receipt AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR r.status <> 'DRAFT' OR r.read_call_id IS NULL THEN
        RAISE EXCEPTION 'receipt' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_read_not_pending';
    END IF;
    SELECT * INTO a FROM ai_calls WHERE id = r.read_call_id FOR UPDATE;
    IF a.finished_at IS NOT NULL OR a.started_at <= now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'lease' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_read_not_pending';
    END IF;
    IF p_outcome = 'OK' THEN
        INSERT INTO stock_receipt_lines (receipt_id, user_id, line_no, read_name, read_quantity, read_unit, unclear,
                                         name, quantity, document_quantity, unit, item_id)
        SELECT p_receipt, uid, l.line_no, l.name, l.quantity, l.unit, l.unclear,
               l.name, l.quantity, l.quantity, coalesce(i.unit, l.unit), i.id
          FROM jsonb_to_recordset(p_lines) AS l(line_no smallint, name text, quantity integer, unit text, unclear boolean)
          LEFT JOIN stock_items i ON i.user_id = uid AND i.name_key = ew_stock_name_key(l.name);
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n NOT BETWEEN 1 AND 20 THEN
            RAISE EXCEPTION 'lines' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_read_lines';
        END IF;
        UPDATE stock_receipts
           SET status = 'READ', document_ref = coalesce(r.document_ref, nullif(p_document_ref, '')),
               dropped_lines = p_dropped
         WHERE id = p_receipt;
    ELSIF p_outcome = 'UNUSABLE' THEN
        UPDATE stock_receipts SET unusable_reason = p_reason WHERE id = p_receipt;
    ELSE
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    PERFORM ew_ai_call_settle(r.read_call_id, p_outcome, p_input, p_output, p_model, p_prompt_version, p_request_id);
END
$$;

-- يُسجّل الأسطر المقبولة حركات استلام في معاملةٍ واحدة، ويُغلق السند (فتُحذف صورته).
-- يُرجع عدد الحركات.
CREATE FUNCTION ew_receipt_confirm(p_receipt uuid, p_expected_row_version integer) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_current_user();
    r    stock_receipts%ROWTYPE;
    l    stock_receipt_lines%ROWTYPE;
    item uuid;
    n    integer := 0;
BEGIN
    SELECT * INTO r FROM stock_receipts WHERE id = p_receipt AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'receipt' USING ERRCODE = 'no_data_found';
    END IF;
    IF r.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF r.status <> 'READ' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'stock_receipt_transition';
    END IF;
    IF EXISTS (SELECT 1 FROM stock_receipt_lines WHERE receipt_id = p_receipt AND decision = 'PENDING') THEN
        RAISE EXCEPTION 'pending' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_lines_pending';
    END IF;
    FOR l IN SELECT * FROM stock_receipt_lines
              WHERE receipt_id = p_receipt AND decision = 'ACCEPTED' ORDER BY line_no LOOP
        item := l.item_id;
        IF item IS NULL THEN
            INSERT INTO stock_items (user_id, name, unit) VALUES (uid, l.name, l.unit)
            ON CONFLICT (user_id, name_key) DO NOTHING
            RETURNING id INTO item;
            IF item IS NULL THEN
                SELECT id INTO item FROM stock_items WHERE user_id = uid AND name_key = ew_stock_name_key(l.name);
            END IF;
        END IF;
        INSERT INTO stock_movements (user_id, item_id, kind, quantity, expected_quantity, damaged_quantity,
                                     party, document_ref, occurred_on, receipt_id, client_token)
        VALUES (uid, item, 'RECEIVE', l.quantity, l.document_quantity, l.damaged_quantity,
                r.party, r.document_ref, coalesce(r.occurred_on, ew_riyadh_today()), r.id,
                md5(r.id::text || ':' || l.line_no::text)::uuid);
        n := n + 1;
    END LOOP;
    IF n = 0 THEN
        RAISE EXCEPTION 'empty' USING ERRCODE = 'check_violation', CONSTRAINT = 'receipt_nothing_accepted';
    END IF;
    UPDATE stock_receipts SET status = 'CONFIRMED' WHERE id = p_receipt;
    RETURN n;
END
$$;

CREATE FUNCTION ew_receipt_cancel(p_receipt uuid, p_expected_row_version integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    r stock_receipts%ROWTYPE;
BEGIN
    SELECT * INTO r FROM stock_receipts WHERE id = p_receipt AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'receipt' USING ERRCODE = 'no_data_found';
    END IF;
    IF r.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    UPDATE stock_receipts SET status = 'CANCELLED' WHERE id = p_receipt;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- سجلّ البلاغات والردود المقترحة
-- ════════════════════════════════════════════════════════════════════════
CREATE TABLE support_tickets (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status        text NOT NULL DEFAULT 'OPEN'
                      CONSTRAINT support_ticket_status CHECK (status IN ('OPEN', 'RESOLVED', 'REFERRED')),
    category      text NOT NULL CONSTRAINT support_ticket_category CHECK (category IN
                      ('HARDWARE', 'SOFTWARE', 'NETWORK', 'PRINTING', 'EMAIL', 'ACCOUNT', 'PHONE', 'OTHER')),
    channel       text NOT NULL CONSTRAINT support_ticket_channel CHECK (channel IN ('IN_PERSON', 'PHONE', 'MESSAGE')),
    -- يجمعه محفّز الإجراءات.
    minutes_total integer NOT NULL DEFAULT 0 CHECK (minutes_total BETWEEN 0 AND 100000),
    row_version   integer NOT NULL DEFAULT 1,
    client_token  uuid NOT NULL,
    opened_on     date NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    closed_at     timestamptz,
    UNIQUE (user_id, client_token),
    UNIQUE (id, user_id),
    CONSTRAINT support_ticket_closed_time CHECK ((status = 'OPEN') = (closed_at IS NULL))
);
CREATE INDEX support_tickets_user_recent ON support_tickets (user_id, status, updated_at DESC);

CREATE TABLE support_ticket_actions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id    uuid NOT NULL,
    user_id      uuid NOT NULL,
    action       text NOT NULL CONSTRAINT support_action_kind CHECK (action IN
                     ('GUIDED_USER', 'RESTARTED', 'REINSTALLED', 'UPDATED', 'CONFIGURED', 'RESET_ACCESS',
                      'REPLACED_PART', 'REFERRED', 'OTHER')),
    minutes      smallint NOT NULL CONSTRAINT support_action_minutes CHECK (minutes IN (5, 10, 15, 20, 30, 45, 60, 90, 120)),
    client_token uuid NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_token),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE
);
CREATE INDEX support_ticket_actions_ticket ON support_ticket_actions (ticket_id, created_at DESC);

-- رسالة العميل بعد حذف وسائل الاتصال منها، وملاحظة الموظف، وما يريد أن يقوله الردّ.
CREATE TABLE reply_requests (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL,
    ticket_id          uuid NOT NULL,
    row_version        integer NOT NULL DEFAULT 1,
    message            text NOT NULL CONSTRAINT reply_message_shape CHECK (char_length(message) BETWEEN 10 AND 1000),
    agent_note         text CONSTRAINT reply_note_shape CHECK (agent_note IS NULL OR char_length(agent_note) BETWEEN 3 AND 300),
    intent             text NOT NULL CONSTRAINT reply_intent CHECK (intent IN ('ASK_INFO', 'ACKNOWLEDGE', 'REFERRED', 'EXPLAIN_STEPS')),
    language           text NOT NULL CONSTRAINT reply_language CHECK (language IN ('AR', 'EN')),
    status             text NOT NULL DEFAULT 'PENDING'
                           CONSTRAINT reply_status CHECK (status IN ('PENDING', 'READY', 'CANNOT_HELP', 'FAILED')),
    cannot_help_reason text CONSTRAINT reply_reason CHECK (cannot_help_reason IS NULL OR cannot_help_reason IN
                           ('NOT_A_SUPPORT_MESSAGE', 'NEEDS_AGENT_NOTE', 'UNSAFE_REQUEST')),
    -- الاستدعاء الجاري: الأول أو تعديل خيارٍ (pending_option).
    call_id            uuid,
    pending_option     smallint CHECK (pending_option IS NULL OR pending_option BETWEEN 1 AND 3),
    approved_option    smallint CHECK (approved_option IS NULL OR approved_option BETWEEN 1 AND 3),
    approved_revision  smallint CHECK (approved_revision IS NULL OR approved_revision BETWEEN 0 AND 3),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (call_id, user_id) REFERENCES ai_calls (id, user_id) ON DELETE SET NULL (call_id),
    CONSTRAINT reply_steps_need_note CHECK (intent <> 'EXPLAIN_STEPS' OR agent_note IS NOT NULL),
    CONSTRAINT reply_reason_iff_cannot CHECK ((status = 'CANNOT_HELP') = (cannot_help_reason IS NOT NULL)),
    CONSTRAINT reply_approval_pair CHECK ((approved_option IS NULL) = (approved_revision IS NULL)),
    CONSTRAINT reply_pending_has_call CHECK (pending_option IS NULL OR call_id IS NOT NULL)
);
CREATE INDEX reply_requests_ticket ON reply_requests (ticket_id, created_at DESC);

CREATE FUNCTION ew_reply_parts_ok(p_parts text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT cardinality(p_parts) BETWEEN 1 AND 2
       AND NOT EXISTS (SELECT 1 FROM unnest(p_parts) AS p WHERE p IS NULL OR char_length(p) NOT BETWEEN 20 AND 260)
$$;

CREATE TABLE reply_options (
    request_id     uuid NOT NULL,
    user_id        uuid NOT NULL,
    option_no      smallint NOT NULL CHECK (option_no BETWEEN 1 AND 3),
    revision       smallint NOT NULL CHECK (revision BETWEEN 0 AND 3),
    style          text NOT NULL CONSTRAINT reply_option_style CHECK (style IN ('BRIEF', 'DETAILED', 'ASK_INFO')),
    parts          text[] NOT NULL CONSTRAINT reply_option_parts CHECK (ew_reply_parts_ok(parts)),
    warnings       text[] NOT NULL DEFAULT '{}' CONSTRAINT reply_option_warnings
                       CHECK (warnings <@ ARRAY['PROMISE_TIME', 'MONEY', 'GUARANTEE', 'PLACEHOLDER']::text[]),
    revise_presets text[] NOT NULL DEFAULT '{}' CONSTRAINT reply_option_presets
                       CHECK (revise_presets <@ ARRAY['SHORTER', 'SIMPLER', 'MORE_FORMAL', 'WARMER']::text[]
                              AND cardinality(revise_presets) <= 2
                              AND NOT (revise_presets @> ARRAY['MORE_FORMAL', 'WARMER']::text[])),
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (request_id, option_no, revision),
    FOREIGN KEY (request_id, user_id) REFERENCES reply_requests (id, user_id) ON DELETE CASCADE,
    CONSTRAINT reply_revision_has_presets CHECK ((revision = 0) = (cardinality(revise_presets) = 0))
);

-- ── محفّزات البلاغات ────────────────────────────────────────────────────
CREATE FUNCTION ew_support_ticket_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND profession = 'SUPPORT' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.support_tickets:' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM support_tickets WHERE user_id = NEW.user_id AND status = 'OPEN') >= 200 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_open_ticket_cap';
    END IF;
    NEW.status := 'OPEN';
    NEW.minutes_total := 0;
    NEW.row_version := 1;
    NEW.opened_on := ew_riyadh_today();
    NEW.closed_at := NULL;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_ticket_insert BEFORE INSERT ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION ew_support_ticket_insert_guard();

CREATE FUNCTION ew_support_ticket_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version OR NEW.client_token <> OLD.client_token
       OR NEW.opened_on <> OLD.opened_on THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_managed_columns';
    END IF;
    -- يُعاد فتح البلاغ في الثلاثين يوماً التالية لإغلاقه فقط.
    IF OLD.status <> 'OPEN' AND NEW.status = 'OPEN' AND OLD.closed_at <= now() - interval '30 days' THEN
        RAISE EXCEPTION 'reopen' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reopen_window';
    END IF;
    IF OLD.status <> 'OPEN' AND NEW.status <> 'OPEN' AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF OLD.status <> 'OPEN' AND NEW.status = OLD.status
       AND ROW(NEW.category, NEW.channel, NEW.minutes_total) IS DISTINCT FROM ROW(OLD.category, OLD.channel, OLD.minutes_total) THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.closed_at := CASE WHEN NEW.status = 'OPEN' THEN NULL
                          WHEN OLD.status = 'OPEN' THEN now()
                          ELSE OLD.closed_at END;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_ticket_update BEFORE UPDATE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION ew_support_ticket_update_guard();

-- إغلاق البلاغ يحذف رسائل عملائه وردودها في المعاملة نفسها.
CREATE FUNCTION ew_support_ticket_purge_replies() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM reply_requests WHERE ticket_id = NEW.id;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_support_ticket_purge_replies AFTER UPDATE OF status ON support_tickets
    FOR EACH ROW WHEN (OLD.status = 'OPEN' AND NEW.status <> 'OPEN')
    EXECUTE FUNCTION ew_support_ticket_purge_replies();

CREATE FUNCTION ew_support_action_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    t support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = NEW.ticket_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'foreign_key_violation',
                                       CONSTRAINT = 'support_ticket_actions_ticket_id_user_id_fkey';
    END IF;
    IF t.status <> 'OPEN' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    IF (SELECT count(*) FROM support_ticket_actions WHERE ticket_id = NEW.ticket_id) >= 50 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_action_cap';
    END IF;
    NEW.created_at := now();
    UPDATE support_tickets SET minutes_total = least(100000, t.minutes_total + NEW.minutes) WHERE id = t.id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_action_insert BEFORE INSERT ON support_ticket_actions
    FOR EACH ROW EXECUTE FUNCTION ew_support_action_insert();

-- ── الردود المقترحة ─────────────────────────────────────────────────────
CREATE FUNCTION ew_reply_begin(
    p_ticket uuid, p_expected_row_version integer, p_message text, p_agent_note text,
    p_intent text, p_language text, p_notice_version text
) RETURNS TABLE (request_id uuid, call_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_current_user();
    t    support_tickets%ROWTYPE;
    call uuid;
    req  uuid;
BEGIN
    IF p_notice_version IS NOT NULL THEN
        PERFORM ew_accept_notice('REPLY', p_notice_version);
    END IF;
    SELECT * INTO t FROM support_tickets WHERE id = p_ticket AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF t.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF t.status <> 'OPEN' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    IF (SELECT count(*) FROM reply_requests
         WHERE ticket_id = p_ticket AND created_at > now() - interval '24 hours') >= 5 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_ticket_daily_cap';
    END IF;
    call := ew_ai_call_open('REPLY');
    INSERT INTO reply_requests (user_id, ticket_id, message, agent_note, intent, language, call_id)
    VALUES (uid, p_ticket, p_message, p_agent_note, p_intent, p_language, call)
    RETURNING id INTO req;
    RETURN QUERY SELECT req, call;
END
$$;

-- p_options: [{option_no, style, parts: [..], warnings: [..]}] بعد فحصها في التطبيق.
CREATE FUNCTION ew_reply_record(
    p_request uuid, p_outcome text, p_reason text, p_options jsonb,
    p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    q   reply_requests%ROWTYPE;
    a   ai_calls%ROWTYPE;
    n   integer;
BEGIN
    SELECT * INTO q FROM reply_requests WHERE id = p_request AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR q.status <> 'PENDING' OR q.call_id IS NULL THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_pending';
    END IF;
    SELECT * INTO a FROM ai_calls WHERE id = q.call_id FOR UPDATE;
    IF a.finished_at IS NOT NULL OR a.started_at <= now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'lease' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_pending';
    END IF;
    IF p_outcome = 'OK' THEN
        INSERT INTO reply_options (request_id, user_id, option_no, revision, style, parts, warnings)
        SELECT p_request, uid, o.option_no, 0, o.style,
               ARRAY(SELECT jsonb_array_elements_text(o.parts)),
               ARRAY(SELECT jsonb_array_elements_text(o.warnings))
          FROM jsonb_to_recordset(p_options) AS o(option_no smallint, style text, parts jsonb, warnings jsonb);
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n NOT BETWEEN 1 AND 3 THEN
            RAISE EXCEPTION 'options' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_options_count';
        END IF;
        UPDATE reply_requests SET status = 'READY', call_id = NULL, row_version = q.row_version + 1, updated_at = now()
         WHERE id = p_request;
    ELSIF p_outcome = 'UNUSABLE' THEN
        UPDATE reply_requests
           SET status = 'CANNOT_HELP', cannot_help_reason = p_reason, call_id = NULL,
               row_version = q.row_version + 1, updated_at = now()
         WHERE id = p_request;
    ELSE
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    PERFORM ew_ai_call_settle(q.call_id, p_outcome, p_input, p_output, p_model, p_prompt_version, p_request_id);
END
$$;

-- تعديل خيارٍ واحد بخياراتٍ جاهزة، قبل الاعتماد. ثلاثة تعديلاتٍ لكل خيار.
CREATE FUNCTION ew_reply_begin_revision(
    p_request uuid, p_expected_row_version integer, p_option smallint, p_notice_version text
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_current_user();
    q    reply_requests%ROWTYPE;
    rev  smallint;
    call uuid;
BEGIN
    IF p_notice_version IS NOT NULL THEN
        PERFORM ew_accept_notice('REPLY', p_notice_version);
    END IF;
    SELECT * INTO q FROM reply_requests WHERE id = p_request AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    IF q.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF q.status <> 'READY' OR q.call_id IS NOT NULL OR q.approved_option IS NOT NULL THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_revisable';
    END IF;
    SELECT max(revision) INTO rev FROM reply_options WHERE request_id = p_request AND option_no = p_option;
    IF rev IS NULL THEN
        RAISE EXCEPTION 'option' USING ERRCODE = 'no_data_found';
    END IF;
    IF rev >= 3 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_revision_cap';
    END IF;
    call := ew_ai_call_open('REPLY');
    UPDATE reply_requests SET call_id = call, pending_option = p_option, row_version = q.row_version + 1,
                              updated_at = now()
     WHERE id = p_request;
    RETURN call;
END
$$;

CREATE FUNCTION ew_reply_record_revision(
    p_request uuid, p_outcome text, p_style text, p_parts text[], p_warnings text[], p_presets text[],
    p_input integer, p_output integer, p_model text, p_prompt_version text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    q   reply_requests%ROWTYPE;
    a   ai_calls%ROWTYPE;
    rev smallint;
BEGIN
    SELECT * INTO q FROM reply_requests WHERE id = p_request AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR q.status <> 'READY' OR q.call_id IS NULL OR q.pending_option IS NULL THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_pending';
    END IF;
    SELECT * INTO a FROM ai_calls WHERE id = q.call_id FOR UPDATE;
    IF a.finished_at IS NOT NULL OR a.started_at <= now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'lease' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_pending';
    END IF;
    IF p_outcome <> 'OK' THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    SELECT max(revision) INTO rev FROM reply_options WHERE request_id = p_request AND option_no = q.pending_option;
    INSERT INTO reply_options (request_id, user_id, option_no, revision, style, parts, warnings, revise_presets)
    VALUES (p_request, uid, q.pending_option, rev + 1, p_style, p_parts, p_warnings, p_presets);
    UPDATE reply_requests SET call_id = NULL, pending_option = NULL, row_version = q.row_version + 1,
                              updated_at = now()
     WHERE id = p_request;
    PERFORM ew_ai_call_settle(q.call_id, p_outcome, p_input, p_output, p_model, p_prompt_version, p_request_id);
END
$$;

-- يعتمد النسخة التي رآها صاحبها من الخيار، لا ما يختاره العميل غيرها.
CREATE FUNCTION ew_reply_approve(p_request uuid, p_expected_row_version integer, p_option smallint, p_revision smallint)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    q  reply_requests%ROWTYPE;
BEGIN
    SELECT * INTO q FROM reply_requests WHERE id = p_request AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    IF q.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF q.status <> 'READY' OR q.call_id IS NOT NULL THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'reply_not_revisable';
    END IF;
    IF p_revision IS DISTINCT FROM (SELECT max(revision) FROM reply_options
                                     WHERE request_id = p_request AND option_no = p_option) THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    UPDATE reply_requests SET approved_option = p_option, approved_revision = p_revision,
                              row_version = q.row_version + 1, updated_at = now()
     WHERE id = p_request;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- العزل والمنح
-- ════════════════════════════════════════════════════════════════════════
ALTER TABLE ai_features             ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_features             FORCE  ROW LEVEL SECURITY;
ALTER TABLE ai_calls                ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_calls                FORCE  ROW LEVEL SECURITY;
ALTER TABLE feature_notices         ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_notices         FORCE  ROW LEVEL SECURITY;
ALTER TABLE assistant_ready_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_ready_answers FORCE  ROW LEVEL SECURITY;
ALTER TABLE assistant_exchanges     ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_exchanges     FORCE  ROW LEVEL SECURITY;
ALTER TABLE stock_items             ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_items             FORCE  ROW LEVEL SECURITY;
ALTER TABLE stock_receipts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_receipts          FORCE  ROW LEVEL SECURITY;
ALTER TABLE stock_movements         ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_movements         FORCE  ROW LEVEL SECURITY;
ALTER TABLE stock_receipt_images    ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_receipt_images    FORCE  ROW LEVEL SECURITY;
ALTER TABLE stock_receipt_lines     ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_receipt_lines     FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_tickets         ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets         FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_ticket_actions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_ticket_actions  FORCE  ROW LEVEL SECURITY;
ALTER TABLE reply_requests          ENABLE ROW LEVEL SECURITY;
ALTER TABLE reply_requests          FORCE  ROW LEVEL SECURITY;
ALTER TABLE reply_options           ENABLE ROW LEVEL SECURITY;
ALTER TABLE reply_options           FORCE  ROW LEVEL SECURITY;

-- المالك: كل شيء (دوالّ SECURITY DEFINER والمحفّزات وأداة المشغّل).
CREATE POLICY ai_features_owner_access             ON ai_features             FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY ai_calls_owner_access                ON ai_calls                FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY feature_notices_owner_access         ON feature_notices         FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY assistant_ready_answers_owner_access ON assistant_ready_answers FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY assistant_exchanges_owner_access     ON assistant_exchanges     FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY stock_items_owner_access             ON stock_items             FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY stock_receipts_owner_access          ON stock_receipts          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY stock_movements_owner_access         ON stock_movements         FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY stock_receipt_images_owner_access    ON stock_receipt_images    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY stock_receipt_lines_owner_access     ON stock_receipt_lines     FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_tickets_owner_access         ON support_tickets         FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_ticket_actions_owner_access  ON support_ticket_actions  FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY reply_requests_owner_access          ON reply_requests          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY reply_options_owner_access           ON reply_options           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- دور الويب: صفوف صاحب الجلسة وحدها. ai_features وassistant_ready_answers بلا
-- سياسةٍ ولا منح: تُقرأ عبر الدوالّ وحدها.
CREATE POLICY ai_calls_own               ON ai_calls               FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY feature_notices_own        ON feature_notices        FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY assistant_exchanges_own    ON assistant_exchanges    FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY stock_items_own            ON stock_items            FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY stock_receipts_own         ON stock_receipts         FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY stock_movements_own        ON stock_movements        FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY stock_receipt_images_own   ON stock_receipt_images   FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY stock_receipt_lines_own    ON stock_receipt_lines    FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY support_tickets_own        ON support_tickets        FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY support_ticket_actions_own ON support_ticket_actions FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY reply_requests_own         ON reply_requests         FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());
CREATE POLICY reply_options_own          ON reply_options          FOR ALL TO eyework_app
    USING (user_id = ew_current_user()) WITH CHECK (user_id = ew_current_user());

-- بالأعمدة، بلا DELETE ولا TRUNCATE. ما لا يُمنح هنا يُكتب عبر الدوالّ وحدها.
GRANT SELECT ON ai_calls, feature_notices, assistant_exchanges, reply_requests, reply_options TO eyework_app;

GRANT SELECT ON stock_items TO eyework_app;
GRANT INSERT (user_id, name, unit) ON stock_items TO eyework_app;
GRANT SELECT ON stock_movements TO eyework_app;
GRANT INSERT (user_id, item_id, kind, quantity, expected_quantity, damaged_quantity, party, document_ref,
              occurred_on, client_token) ON stock_movements TO eyework_app;
GRANT UPDATE (voided_at) ON stock_movements TO eyework_app;
GRANT SELECT ON stock_receipts TO eyework_app;
GRANT INSERT (user_id) ON stock_receipts TO eyework_app;
GRANT UPDATE (document_ref, party, occurred_on) ON stock_receipts TO eyework_app;
GRANT SELECT ON stock_receipt_images TO eyework_app;
GRANT INSERT (receipt_id, user_id, jpeg, width, height, sha256) ON stock_receipt_images TO eyework_app;
GRANT UPDATE (jpeg, width, height, sha256) ON stock_receipt_images TO eyework_app;
GRANT SELECT ON stock_receipt_lines TO eyework_app;
GRANT UPDATE (name, quantity, document_quantity, damaged_quantity, unit, item_id, decision)
    ON stock_receipt_lines TO eyework_app;

GRANT SELECT ON support_tickets TO eyework_app;
GRANT INSERT (user_id, category, channel, client_token) ON support_tickets TO eyework_app;
GRANT UPDATE (status, category, channel) ON support_tickets TO eyework_app;
GRANT SELECT ON support_ticket_actions TO eyework_app;
GRANT INSERT (ticket_id, user_id, action, minutes, client_token) ON support_ticket_actions TO eyework_app;

-- الدوالّ: الداخلية ودوالّ المحفّزات لا يستدعيها دور الويب.
REVOKE ALL ON FUNCTION
    ew_ai_call_tombstone(), ew_ai_spend(boolean), ew_accept_notice(text, text), ew_ai_call_open(text),
    ew_ai_call_settle(uuid, text, integer, integer, text, text, text),
    ew_finish_ai_call(uuid, text, integer, integer, text, text, text), ew_my_ai_limits(),
    ew_assistant_preset_ok(text, text), ew_assistant_cacheable(text),
    ew_assistant_begin(text, text, text, text, bytea, text, text),
    ew_assistant_record(uuid, text, jsonb, integer, integer, text, text, text),
    ew_assistant_not_helpful(uuid),
    ew_stock_name_key(text), ew_stock_item_insert_guard(), ew_stock_item_update_guard(),
    ew_stock_movement_insert(), ew_stock_movement_void(), ew_stock_receipt_insert_guard(),
    ew_stock_receipt_update_guard(), ew_stock_receipt_purge_image(), ew_stock_receipt_image_guard(),
    ew_stock_receipt_line_guard(), ew_stock_receipt_line_touch(),
    ew_receipt_begin_read(uuid, integer, text),
    ew_receipt_record_read(uuid, text, text, text, jsonb, integer, integer, integer, text, text, text),
    ew_receipt_confirm(uuid, integer), ew_receipt_cancel(uuid, integer),
    ew_support_ticket_insert_guard(), ew_support_ticket_update_guard(), ew_support_ticket_purge_replies(),
    ew_support_action_insert(), ew_reply_parts_ok(text[]),
    ew_reply_begin(uuid, integer, text, text, text, text, text),
    ew_reply_record(uuid, text, text, jsonb, integer, integer, text, text, text),
    ew_reply_begin_revision(uuid, integer, smallint, text),
    ew_reply_record_revision(uuid, text, text, text[], text[], text[], integer, integer, text, text, text),
    ew_reply_approve(uuid, integer, smallint, smallint)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
    ew_finish_ai_call(uuid, text, integer, integer, text, text, text), ew_my_ai_limits(),
    ew_assistant_begin(text, text, text, text, bytea, text, text),
    ew_assistant_record(uuid, text, jsonb, integer, integer, text, text, text),
    ew_assistant_not_helpful(uuid),
    ew_receipt_begin_read(uuid, integer, text),
    ew_receipt_record_read(uuid, text, text, text, jsonb, integer, integer, integer, text, text, text),
    ew_receipt_confirm(uuid, integer), ew_receipt_cancel(uuid, integer),
    ew_reply_begin(uuid, integer, text, text, text, text, text),
    ew_reply_record(uuid, text, text, jsonb, integer, integer, text, text, text),
    ew_reply_begin_revision(uuid, integer, smallint, text),
    ew_reply_record_revision(uuid, text, text, text[], text[], text[], integer, integer, text, text, text),
    ew_reply_approve(uuid, integer, smallint, smallint),
    -- دوالّ قيودٍ في جداولٍ يكتبها دور الويب مباشرة: تُستدعى بصلاحية الكاتب.
    ew_reply_parts_ok(text[])
TO eyework_app;
