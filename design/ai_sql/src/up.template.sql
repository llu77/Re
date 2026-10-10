-- ════════════════════════════════════════════════════════════════════════
-- NEXT_ai_layer — دفتر استدعاءات النموذج، وتنبيهات المراجِع، وقرارات صاحبها
-- ════════════════════════════════════════════════════════════════════════
-- ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو النموذج، فيُفرض هنا:
--
--   • كل استدعاءٍ للنموذج خارج الحملة صفٌّ في ai_requests يُفتح قبل الاستدعاء
--     بسقوفه: واحدٌ جارٍ لكل مستخدمٍ وأداة، وحدّ عشر دقائق ويومٍ لكل أداة (أضيق
--     للحساب المفتوح الجديد)، وحدّ يومٍ للأداة في التطبيق كلّه، والسقف العام
--     (ألفان في اليوم، منها أربعمئة للحسابات الجديدة) يجمع الحملات وهذه معاً في
--     دالّةٍ واحدة: ew_ai_spend. لا محتوى في الدفتر: لا سؤال ولا جواب ولا نصّ.
--   • تنبيه المراجِع مقترحٌ لا قرار: يُكتب لمحتوىً بعينه (بصمته)، ولا يُكتب إن
--     تغيّر المحتوى أثناء المراجعة. والاعتماد لا يمرّ وعلى بصمته الحالية تنبيهٌ
--     آخر قرارٍ فيه غير «تابع رغم ذلك» (ew_ai_gate)، ثم يُغلق التنبيه فلا يُقرَّر
--     فيه بعدها.
--   • قرارات صاحب التنبيه سجلٌّ يُضاف إليه ولا يُعدَّل.
--   • لا اسم في شيءٍ من هذا: الاسم يضيفه الخادم إلى نصّ التنبيه عند العرض.
--   • العزل بالصفّ على eyework.user_id، مفروضٌ على المالك أيضاً (FORCE). دور الويب
--     يقرأ صفوفه ولا يكتب جدولاً مباشرة: كل كتابةٍ دالّة.
-- ════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF to_regprocedure('ew_new_open_account(uuid)') IS NULL
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = 'attempt_tombstones'
                         AND column_name = 'new_account') THEN
        RAISE EXCEPTION 'طبقة الذكاء الاصطناعي تحتاج ترحيل التسجيل المفتوح قبلها.';
    END IF;
END
$$;

-- ── النصّ الذي كتبه النموذج ويُعرض ──────────────────────────────────────
-- سطرٌ واحد بطولٍ محدود، بلا محارف تحكّمٍ أو اتجاهٍ خفية، وبلا وسومٍ ولا روابط
-- ولا بريد. نظيرها ai_text.check في الخادم، وهو الأشدّ (اختبارٌ يقارنهما).
CREATE FUNCTION ew_ai_text_ok(t text, p_min integer, p_max integer) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT t IS NOT NULL AND char_length(t) BETWEEN p_min AND p_max AND t = btrim(t)
       AND t !~ '[[:cntrl:]]'
       AND t !~ '[‎‏‪-‮⁦-⁩]'
       AND t !~ '[<>#]'
       AND t !~* '(https?://|www\.)'
       AND t !~ '[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+'
$$;

-- ── الأدوات التي تستدعي النموذج وسقوفها ─────────────────────────────────
-- جدولٌ لا ثوابت في الدوالّ؛ نظيره eyework/ai_limits.py FEATURES (اختبارٌ يقارنهما).
-- الحملة (generation_attempts) خارجه بسقوفها في ew_begin_generation، ويجمعهما
-- السقف العام.
CREATE TABLE ai_features (
    code             text PRIMARY KEY CONSTRAINT ai_feature_code CHECK (code ~ '^[A-Z][A-Z_]{2,39}$'),
    -- NULL: لكل مهنة (المساعد). وإلا فلأصحاب مهنتها وحدهم.
    profession       text REFERENCES professions (code) ON DELETE RESTRICT,
    per_user_10min   integer NOT NULL CHECK (per_user_10min BETWEEN 1 AND 50),
    per_user_day     integer NOT NULL CHECK (per_user_day BETWEEN 1 AND 500),
    per_new_user_day integer NOT NULL CHECK (per_new_user_day BETWEEN 0 AND 500),
    app_day          integer NOT NULL CHECK (app_day BETWEEN 1 AND 2000),
    -- عقد الاستدعاء بالثواني: بعده لا يُعدّ جارياً، ولا تُكتب نتيجته الناجحة.
    lease_seconds    integer NOT NULL CHECK (lease_seconds BETWEEN 30 AND 300),
    CONSTRAINT ai_feature_new_within_user CHECK (per_new_user_day <= per_user_day)
);
INSERT INTO ai_features (code, profession, per_user_10min, per_user_day, per_new_user_day, app_day, lease_seconds) VALUES
    ('ASSISTANT',                NULL,          10, 60, 15, 1000,  60),
    ('STOCK_REVIEW',             'STOREKEEPER',  6, 30, 10,  600,  60),
    ('SUPPORT_DRAFT',            'SUPPORT',     10, 60, 10,  800, 150),
    ('SUPPORT_REPLY_REVIEW',     'SUPPORT',     10, 60, 10,  600,  60),
    ('SUPPORT_ARTICLE_PROPOSAL', 'SUPPORT',      3, 10,  3,  150, 150),
    ('SUPPORT_ARTICLE_REVIEW',   'SUPPORT',      5, 20,  5,  200,  60);

-- ── الدفتر ──────────────────────────────────────────────────────────────
-- كل استدعاءٍ محاولةٌ تُحسب، نجحت أم فشلت. ما يخصّ المحتوى بصمته وحدها.
CREATE TABLE ai_requests (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    feature            text NOT NULL REFERENCES ai_features (code) ON DELETE RESTRICT,
    -- ما يُراجَع أو يُكتب له: نوعه ومعرّفه وبصمة محتواه. بلا مفتاحٍ خارجي عمداً: الدفتر
    -- يبقى ما بقي يومُه في السقوف وإن حُذف ما يخصّه.
    subject_kind       text CONSTRAINT ai_request_subject_kind CHECK (subject_kind ~ '^[A-Z][A-Z_]{2,39}$'),
    subject_id         uuid,
    content_digest     bytea CONSTRAINT ai_request_digest CHECK (octet_length(content_digest) = 32),
    started_at         timestamptz NOT NULL DEFAULT now(),
    finished_at        timestamptz,
    outcome            text CONSTRAINT ai_request_outcome CHECK (outcome IN (
                           'OK', 'DONT_KNOW', 'OUT_OF_SCOPE', 'CANNOT_ANSWER', 'NOT_SUPPORT',
                           'REFUSED', 'OUTPUT_INVALID', 'DISCARDED', 'ABANDONED',
                           'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR')),
    -- عدد التنبيهات التي كُتبت من مراجعةٍ نجحت. رقمٌ لا نصّ: لقياس المراجِع بلا محتوى.
    flags_count        smallint CONSTRAINT ai_request_flags_count CHECK (flags_count BETWEEN 0 AND 3),
    input_tokens       integer CHECK (input_tokens >= 0),
    output_tokens      integer CHECK (output_tokens >= 0),
    cache_read_tokens  integer CHECK (cache_read_tokens >= 0),
    cache_write_tokens integer CHECK (cache_write_tokens >= 0),
    -- النموذج الذي خدم فعلاً — قد يكون البديل من جهة الخادم.
    served_model       text CHECK (served_model IS NULL OR served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    prompt_version     text CHECK (prompt_version IS NULL OR prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    api_request_id     text CHECK (api_request_id IS NULL OR api_request_id ~ '^[A-Za-z0-9_-]{1,128}$'),
    -- من حسابٍ مفتوحٍ جديد لحظة البدء: حصّة الجدد لا يُفرغها حذف.
    new_account        boolean NOT NULL DEFAULT false,
    UNIQUE (id, user_id),
    CONSTRAINT ai_request_finished_iff_outcome CHECK ((finished_at IS NULL) = (outcome IS NULL)),
    CONSTRAINT ai_request_subject_pair CHECK ((subject_kind IS NULL) = (subject_id IS NULL)),
    CONSTRAINT ai_request_digest_needs_subject CHECK (content_digest IS NULL OR subject_id IS NOT NULL),
    CONSTRAINT ai_request_flags_only_ok CHECK (flags_count IS NULL OR outcome = 'OK')
);
CREATE INDEX ai_requests_user_time    ON ai_requests (user_id, started_at DESC);
CREATE INDEX ai_requests_feature_time ON ai_requests (feature, started_at DESC);
CREATE INDEX ai_requests_time         ON ai_requests (started_at DESC);
CREATE INDEX ai_requests_subject      ON ai_requests (subject_id, content_digest) WHERE subject_id IS NOT NULL;

-- استدعاءٌ أُغلق لا يُعاد فتحه ولا تُعدَّل نتيجته (دالّة 0002 نفسها).
CREATE TRIGGER trg_ai_request_settle BEFORE UPDATE ON ai_requests
    FOR EACH ROW EXECUTE FUNCTION ew_attempt_settle_once();

-- حذف الحساب لا يُفرغ السقف العام: أثرٌ بلا هوية، كمحاولات الحملة.
CREATE FUNCTION ew_ai_request_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;
CREATE TRIGGER trg_ai_request_tombstone BEFORE DELETE ON ai_requests
    FOR EACH ROW EXECUTE FUNCTION ew_ai_request_tombstone();

-- ── التنبيهات ───────────────────────────────────────────────────────────
-- ما قاله المراجِع عن محتوىً بعينه. السبب والاقتراح من النموذج بعد فحصهما في الخادم،
-- بلا اسمٍ ولا نداء؛ والشواهد يبنيها الخادم من الأرقام التي أرسلها، لا النموذج.
CREATE TABLE ai_flags (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    request_id      uuid,
    feature         text NOT NULL REFERENCES ai_features (code) ON DELETE RESTRICT,
    subject_kind    text NOT NULL CONSTRAINT ai_flag_subject_kind CHECK (subject_kind ~ '^[A-Z][A-Z_]{2,39}$'),
    subject_id      uuid NOT NULL,
    content_digest  bytea NOT NULL CONSTRAINT ai_flag_digest CHECK (octet_length(content_digest) = 32),
    position        smallint NOT NULL CONSTRAINT ai_flag_position CHECK (position BETWEEN 1 AND 3),
    check_code      text NOT NULL CONSTRAINT ai_flag_check CHECK (check_code ~ '^[A-Z][A-Z_]{2,39}$'),
    severity        text NOT NULL CONSTRAINT ai_flag_severity CHECK (severity IN ('HIGH', 'MEDIUM')),
    field           text NOT NULL CONSTRAINT ai_flag_field CHECK (field ~ '^[a-z][a-z_]{1,39}$'),
    line_no         smallint CONSTRAINT ai_flag_line CHECK (line_no BETWEEN 1 AND 999),
    reason          text,
    suggestion      text,
    evidence        jsonb NOT NULL DEFAULT '[]' CONSTRAINT ai_flag_evidence CHECK (
                        jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) <= 3
                        AND octet_length(evidence::text) <= 600),
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- يكتبه ew_ai_gate حين يُعتمد المحتوى: بعده لا قرار في التنبيه.
    closed_at       timestamptz,
    -- حين يمحو صاحب الموضوع نصوصه (رسائل العملاء مثلاً) تُمحى نصوص التنبيه معها،
    -- ويبقى رمزه وقراراته.
    erased_at       timestamptz,
    UNIQUE (id, user_id),
    -- الدفتر يُحذف بعد ثلاثين يوماً، والتنبيه المعتمد يبقى مع موضوعه.
    FOREIGN KEY (request_id, user_id) REFERENCES ai_requests (id, user_id) ON DELETE SET NULL (request_id),
    CONSTRAINT ai_flag_texts CHECK (
        (erased_at IS NULL AND ew_ai_text_ok(reason, 12, 160)
         AND (suggestion IS NULL OR ew_ai_text_ok(suggestion, 8, 140)))
     OR (erased_at IS NOT NULL AND reason IS NULL AND suggestion IS NULL AND evidence = '[]'::jsonb))
);
-- تنبيهٌ واحد لكل فحصٍ وسطرٍ في المحتوى نفسه، وإن تكرّرت المراجعة.
CREATE UNIQUE INDEX ai_flags_one_per_check
    ON ai_flags (subject_kind, subject_id, content_digest, check_code, (coalesce(line_no, 0)));
CREATE INDEX ai_flags_subject  ON ai_flags (user_id, subject_kind, subject_id, content_digest);
CREATE INDEX ai_flags_open_age ON ai_flags (created_at) WHERE closed_at IS NULL;

-- ما يتغيّر في التنبيه بعد كتابته: إغلاقه مرةً، ومحو نصوصه مرةً، وفكّه عن دفترٍ حُذف.
CREATE FUNCTION ew_ai_flag_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF (NEW.id, NEW.user_id, NEW.feature, NEW.subject_kind, NEW.subject_id, NEW.content_digest, NEW.position,
        NEW.check_code, NEW.severity, NEW.field, NEW.line_no, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.user_id, OLD.feature, OLD.subject_kind, OLD.subject_id, OLD.content_digest, OLD.position,
        OLD.check_code, OLD.severity, OLD.field, OLD.line_no, OLD.created_at)
       OR (NEW.request_id IS DISTINCT FROM OLD.request_id AND NEW.request_id IS NOT NULL)
       OR (OLD.closed_at IS NOT NULL AND NEW.closed_at IS DISTINCT FROM OLD.closed_at)
       OR (OLD.erased_at IS NOT NULL AND NEW.erased_at IS DISTINCT FROM OLD.erased_at)
       OR (NEW.erased_at IS NULL
           AND (NEW.reason, NEW.suggestion, NEW.evidence) IS DISTINCT FROM (OLD.reason, OLD.suggestion, OLD.evidence)) THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_flag_immutable';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_ai_flag_guard BEFORE UPDATE ON ai_flags
    FOR EACH ROW EXECUTE FUNCTION ew_ai_flag_guard();

-- ── القرارات ────────────────────────────────────────────────────────────
-- «عدّل» و«تابع رغم ذلك» كما ضغطهما صاحب التنبيه، و«تراجع» عن الثانية قبل الاعتماد.
-- يُضاف ولا يُعدَّل؛ والقرار القائم آخر صفّ.
CREATE TABLE ai_flag_decisions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    flag_id     uuid NOT NULL,
    user_id     uuid NOT NULL,
    choice      text NOT NULL CONSTRAINT ai_decision_choice CHECK (choice IN ('EDIT', 'PROCEED', 'UNDO')),
    decided_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (flag_id, user_id) REFERENCES ai_flags (id, user_id) ON DELETE CASCADE
);
CREATE INDEX ai_decisions_flag ON ai_flag_decisions (flag_id, id DESC);
CREATE TRIGGER trg_ai_decision_append_only BEFORE UPDATE ON ai_flag_decisions
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();

-- ════════════════════════════════════════════════════════════════════════
-- السقوف والدفتر (دوالّ داخلية: تستدعيها دوالّ المالك وحدها)
-- ════════════════════════════════════════════════════════════════════════

-- ما ربما فُوتر في آخر يوم من كل استدعاءات النموذج، ومن آثار ما حُذف. p_new_only: ما
-- بدأه حسابٌ مفتوحٌ جديد وحده. **الدالّة الوحيدة التي تجمع الدفاتر**: ترحيلٌ يضيف دفتراً
-- آخر يعيد كتابتها (اختبارٌ يعدّ كل جدولٍ فيه new_account وoutcome).
CREATE FUNCTION ew_ai_spend(p_new_only boolean) RETURNS bigint
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT (SELECT count(*) FROM generation_attempts
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM ai_requests
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM attempt_tombstones
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
$$;

-- يفتح استدعاءً لصاحب الجلسة بعد كل السقوف، أو يرفض باسم قيده. تستدعيها دوالّ كل أداةٍ
-- بعد فحص حال موضوعها وحساب بصمته. قفل صفّ المستخدم يجعل العدّ والإدراج ذرّيين لكل
-- مستخدم، والقفل العام يجمع المستخدمين، كما في ew_begin_generation.
CREATE FUNCTION ew_ai_request_open(p_feature text, p_subject_kind text, p_subject_id uuid, p_digest bytea)
RETURNS uuid
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    f     ai_features%ROWTYPE;
    fresh boolean;
    req   uuid;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO f FROM ai_features WHERE code = p_feature;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'feature' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_feature_unknown';
    END IF;
    IF f.profession IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = f.profession) THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'ai_feature_profession';
    END IF;
    -- محتوىً روجع بنجاح لا يُراجَع ثانيةً: تنبيهاته في ai_flags.
    IF p_digest IS NOT NULL AND EXISTS (
           SELECT 1 FROM ai_requests
            WHERE user_id = uid AND feature = p_feature AND subject_id = p_subject_id
              AND content_digest = p_digest AND outcome = 'OK') THEN
        RAISE EXCEPTION 'current' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_review_current';
    END IF;
    IF EXISTS (SELECT 1 FROM ai_requests
                WHERE user_id = uid AND feature = p_feature AND finished_at IS NULL
                  AND started_at > now() - make_interval(secs => f.lease_seconds)) THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_in_progress';
    END IF;
    IF (SELECT count(*) FROM ai_requests
         WHERE user_id = uid AND feature = p_feature
           AND started_at > now() - interval '10 minutes') >= f.per_user_10min THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_rate';
    END IF;
    fresh := ew_new_open_account(uid);
    IF (SELECT count(*) FROM ai_requests
         WHERE user_id = uid AND feature = p_feature AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN f.per_new_user_day ELSE f.per_user_day END) THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation',
            CONSTRAINT = (CASE WHEN fresh THEN 'ai_new_account_daily_cap' ELSE 'ai_daily_cap' END);
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM ai_requests
         WHERE feature = p_feature AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= f.app_day THEN
        RAISE EXCEPTION 'app' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_feature_app_cap';
    END IF;
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    INSERT INTO ai_requests (user_id, feature, subject_kind, subject_id, content_digest, new_account)
    VALUES (uid, p_feature, p_subject_kind, p_subject_id, p_digest, fresh)
    RETURNING id INTO req;
    RETURN req;
END
$$;

-- يُغلق استدعاءً مفتوحاً لصاحب الجلسة بنتيجته وأرقامه. p_usage: كائنٌ مفاتيحه من
-- input وoutput وcache_read وcache_write وmodel وprompt_version وapi_request_id.
-- النتيجة الناجحة لا تُكتب بعد عقد الاستدعاء.
CREATE FUNCTION ew_ai_request_settle(p_request uuid, p_outcome text, p_flags smallint, p_usage jsonb)
RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    r ai_requests%ROWTYPE;
BEGIN
    IF p_usage IS NOT NULL AND (jsonb_typeof(p_usage) <> 'object' OR EXISTS (
           SELECT 1 FROM jsonb_object_keys(p_usage) k
            WHERE k NOT IN ('input', 'output', 'cache_read', 'cache_write', 'model', 'prompt_version',
                            'api_request_id'))) THEN
        RAISE EXCEPTION 'usage' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_usage_shape';
    END IF;
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = ew_current_user() FOR UPDATE;
    IF NOT FOUND OR r.finished_at IS NOT NULL
       OR (p_outcome IN ('OK', 'DONT_KNOW', 'OUT_OF_SCOPE', 'CANNOT_ANSWER', 'NOT_SUPPORT')
           AND r.started_at <= now() - make_interval(secs => (SELECT lease_seconds FROM ai_features
                                                              WHERE code = r.feature))) THEN
        RAISE EXCEPTION 'request' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_not_open';
    END IF;
    UPDATE ai_requests
       SET finished_at = now(), outcome = p_outcome, flags_count = p_flags,
           input_tokens = (p_usage ->> 'input')::integer,
           output_tokens = (p_usage ->> 'output')::integer,
           cache_read_tokens = (p_usage ->> 'cache_read')::integer,
           cache_write_tokens = (p_usage ->> 'cache_write')::integer,
           served_model = p_usage ->> 'model',
           prompt_version = p_usage ->> 'prompt_version',
           api_request_id = p_usage ->> 'api_request_id'
     WHERE id = p_request;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- المراجِع: كتابة التنبيهات، والبوابة عند الاعتماد
-- ════════════════════════════════════════════════════════════════════════

-- قفلٌ لكل موضوع: كتابة التنبيهات والبوابة لا تتداخلان.
CREATE FUNCTION ew_ai_lock_subject(p_subject_id uuid) RETURNS void
LANGUAGE sql SET search_path = public, pg_temp AS $$
    SELECT pg_advisory_xact_lock(hashtextextended('eyework.ai_subject:' || p_subject_id::text, 0))
$$;

-- يكتب ما قاله المراجِع ويُغلق الاستدعاء. تستدعيها دالّة كل أداة بعد أن تقفل موضوعها
-- وتحسب بصمته الآن (p_current_digest، أو NULL إن خرج الموضوع من المراجعة). إن تغيّر
-- المحتوى منذ البدء لا يُكتب شيء، ويُغلق الاستدعاء DISCARDED: تنبيهٌ عن محتوىً آخر لا
-- يُعرض. p_flags: مصفوفةٌ من ثلاثة على الأكثر، كلٌّ بمفاتيحه السبعة.
CREATE FUNCTION ew_ai_flags_put(p_request uuid, p_current_digest bytea, p_flags jsonb, p_usage jsonb)
RETURNS text
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_current_user();
    r    ai_requests%ROWTYPE;
    f    jsonb;
    pos  smallint := 0;
    kept smallint := 0;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = uid;
    IF NOT FOUND OR r.subject_id IS NULL THEN
        RAISE EXCEPTION 'request' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_not_open';
    END IF;
    PERFORM ew_ai_lock_subject(r.subject_id);
    IF p_current_digest IS DISTINCT FROM r.content_digest THEN
        PERFORM ew_ai_request_settle(p_request, 'DISCARDED', NULL, p_usage);
        RETURN 'DISCARDED';
    END IF;
    IF jsonb_typeof(p_flags) IS DISTINCT FROM 'array' OR jsonb_array_length(p_flags) > 3 THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_flags_shape';
    END IF;
    FOR f IN SELECT value FROM jsonb_array_elements(p_flags) LOOP
        pos := pos + 1;
        IF jsonb_typeof(f) <> 'object'
           OR NOT f ?& ARRAY['check', 'severity', 'field', 'line', 'reason', 'suggestion', 'evidence']
           OR (SELECT count(*) FROM jsonb_object_keys(f)) <> 7 THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_flags_shape';
        END IF;
        INSERT INTO ai_flags (user_id, request_id, feature, subject_kind, subject_id, content_digest, position,
                              check_code, severity, field, line_no, reason, suggestion, evidence)
        VALUES (uid, r.id, r.feature, r.subject_kind, r.subject_id, r.content_digest, pos,
                f ->> 'check', f ->> 'severity', f ->> 'field', (f ->> 'line')::smallint, f ->> 'reason',
                f ->> 'suggestion', f -> 'evidence')
        ON CONFLICT DO NOTHING;
        IF FOUND THEN
            kept := kept + 1;
        END IF;
    END LOOP;
    PERFORM ew_ai_request_settle(p_request, 'OK', kept, p_usage);
    RETURN 'OK';
END
$$;

-- البوابة: تستدعيها دالّة الاعتماد في كل أداة، في معاملتها، بعد أن تقفل موضوعها.
-- ترفض ما بقي على البصمة الحالية تنبيهٌ آخر قرارٍ فيه غير PROCEED، وإلا تُغلق تنبيهاتها
-- (فلا يُقرَّر فيها بعد الاعتماد) وتُرجع عددها. لا تنتظر مراجعةً جارية: المساعد لا يمنع.
CREATE FUNCTION ew_ai_gate(p_subject_kind text, p_subject_id uuid, p_digest bytea) RETURNS integer
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    n   integer;
BEGIN
    PERFORM ew_ai_lock_subject(p_subject_id);
    PERFORM 1 FROM ai_flags
     WHERE user_id = uid AND subject_kind = p_subject_kind AND subject_id = p_subject_id
       AND content_digest = p_digest AND closed_at IS NULL
     ORDER BY id FOR UPDATE;
    IF EXISTS (SELECT 1 FROM ai_flags g
                WHERE g.user_id = uid AND g.subject_kind = p_subject_kind AND g.subject_id = p_subject_id
                  AND g.content_digest = p_digest AND g.closed_at IS NULL
                  AND coalesce((SELECT d.choice FROM ai_flag_decisions d
                                 WHERE d.flag_id = g.id ORDER BY d.id DESC LIMIT 1), '') <> 'PROCEED') THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_flags_undecided';
    END IF;
    UPDATE ai_flags SET closed_at = now()
     WHERE user_id = uid AND subject_kind = p_subject_kind AND subject_id = p_subject_id
       AND content_digest = p_digest AND closed_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END
$$;

-- يُحذف ما قيل عن موضوعٍ حُذف. محفّز AFTER DELETE على جدول كل موضوع، ونوعه معامِله:
--   CREATE TRIGGER … AFTER DELETE ON inv_purchases FOR EACH ROW
--       EXECUTE FUNCTION ew_ai_forget_subject('PURCHASE');
CREATE FUNCTION ew_ai_forget_subject() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    DELETE FROM ai_flags WHERE subject_kind = TG_ARGV[0] AND subject_id = OLD.id;
    RETURN OLD;
END
$$;

-- تُمحى نصوص التنبيهات حين تمحو الأداة نصوص موضوعها؛ ويبقى الرمز والقرارات.
CREATE FUNCTION ew_ai_erase_subject(p_subject_kind text, p_subject_id uuid) RETURNS integer
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    n integer;
BEGIN
    UPDATE ai_flags SET reason = NULL, suggestion = NULL, evidence = '[]'::jsonb, erased_at = now()
     WHERE subject_kind = p_subject_kind AND subject_id = p_subject_id AND erased_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- ما يستدعيه دور الويب
-- ════════════════════════════════════════════════════════════════════════

-- قرار صاحب التنبيه. EDIT وPROCEED في أيّ وقتٍ قبل الاعتماد، وUNDO عن PROCEED وحدها.
-- تكرار القرار القائم لا يُضيف صفّاً. عشرون قراراً على الأكثر للتنبيه الواحد.
CREATE FUNCTION ew_ai_decide(p_flag uuid, p_choice text)
RETURNS TABLE (choice text, decided_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid    uuid := ew_current_user();
    g      ai_flags%ROWTYPE;
    latest ai_flag_decisions%ROWTYPE;
BEGIN
    IF p_choice IS NULL OR p_choice NOT IN ('EDIT', 'PROCEED', 'UNDO') THEN
        RAISE EXCEPTION 'choice' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_decision_choice';
    END IF;
    SELECT * INTO g FROM ai_flags WHERE id = p_flag AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'no_data_found';
    END IF;
    IF g.closed_at IS NOT NULL OR g.erased_at IS NOT NULL THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_flag_closed';
    END IF;
    SELECT * INTO latest FROM ai_flag_decisions d WHERE d.flag_id = g.id ORDER BY d.id DESC LIMIT 1;
    IF p_choice = 'UNDO' AND latest.choice IS DISTINCT FROM 'PROCEED' THEN
        RAISE EXCEPTION 'undo' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_decision_undo';
    END IF;
    IF latest.choice IS NOT DISTINCT FROM p_choice THEN
        RETURN QUERY SELECT latest.choice, latest.decided_at;
        RETURN;
    END IF;
    IF (SELECT count(*) FROM ai_flag_decisions d WHERE d.flag_id = g.id) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_decision_cap';
    END IF;
    RETURN QUERY
        INSERT INTO ai_flag_decisions AS d (flag_id, user_id, choice) VALUES (g.id, uid, p_choice)
        RETURNING d.choice, d.decided_at;
END
$$;

-- يُغلق استدعاءً لم يُنتج شيئاً: رفضٌ، أو خطأٌ من المزوّد، أو جوابٌ رفضه الخادم.
CREATE FUNCTION ew_ai_request_fail(p_request uuid, p_outcome text, p_usage jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_outcome IS NULL OR p_outcome NOT IN ('REFUSED', 'OUTPUT_INVALID', 'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE',
                                              'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    PERFORM ew_ai_request_settle(p_request, p_outcome, NULL, p_usage);
END
$$;

-- ما لصاحب الجلسة من كل أداةٍ تخصّ مهنته اليوم، وما استعمل منه.
CREATE FUNCTION ew_ai_my_usage() RETURNS TABLE (feature text, per_day integer, used_today bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT f.code,
           CASE WHEN ew_new_open_account(u.id) THEN f.per_new_user_day ELSE f.per_user_day END,
           (SELECT count(*) FROM ai_requests r
             WHERE r.user_id = u.id AND r.feature = f.code AND ew_is_billable(r.outcome)
               AND r.started_at > now() - interval '24 hours')
      FROM users u JOIN ai_features f ON f.profession IS NULL OR f.profession = u.profession
     WHERE u.id = ew_current_user() AND u.is_active
     ORDER BY f.code
$$;

-- ── «اسأل سيمبول» ───────────────────────────────────────────────────────
-- السؤال والجواب لا يُخزَّنان: الدفتر يعرف أن سؤالاً سُئل، ومتى، وبكم، فقط.
CREATE FUNCTION ew_assistant_begin() RETURNS uuid
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_ai_request_open('ASSISTANT', NULL, NULL, NULL)
$$;

CREATE FUNCTION ew_assistant_finish(p_request uuid, p_outcome text, p_usage jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_outcome IS NULL OR p_outcome NOT IN ('OK', 'DONT_KNOW', 'OUT_OF_SCOPE') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_outcome_needs_record';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM ai_requests
                    WHERE id = p_request AND user_id = ew_current_user() AND feature = 'ASSISTANT') THEN
        RAISE EXCEPTION 'request' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_not_open';
    END IF;
    PERFORM ew_ai_request_settle(p_request, p_outcome, NULL, p_usage);
END
$$;

-- ── السقف العام في الحملة يعدّ الأدوات الأخرى أيضاً ─────────────────────
-- جسم الترحيل السابق كما هو، والشرطان المعلَّمان «ai_layer» فقط.
--@@BEGIN_GENERATION@@

-- ════════════════════════════════════════════════════════════════════════
-- العزل والمنح
-- ════════════════════════════════════════════════════════════════════════
ALTER TABLE ai_features       ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_features       FORCE  ROW LEVEL SECURITY;
ALTER TABLE ai_requests       ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_requests       FORCE  ROW LEVEL SECURITY;
ALTER TABLE ai_flags          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_flags          FORCE  ROW LEVEL SECURITY;
ALTER TABLE ai_flag_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_flag_decisions FORCE  ROW LEVEL SECURITY;

-- دور الويب يقرأ صفوفه وحدها، ولا يكتب: لا سياسة INSERT أو UPDATE أو DELETE له.
CREATE POLICY ai_requests_own  ON ai_requests       FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY ai_flags_own     ON ai_flags          FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY ai_decisions_own ON ai_flag_decisions FOR SELECT TO eyework_app USING (user_id = ew_current_user());

CREATE POLICY ai_features_owner_access  ON ai_features       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY ai_requests_owner_access  ON ai_requests       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY ai_flags_owner_access     ON ai_flags          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY ai_decisions_owner_access ON ai_flag_decisions FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

GRANT SELECT ON ai_requests, ai_flags, ai_flag_decisions TO eyework_app;

REVOKE ALL ON FUNCTION ew_ai_text_ok(text, integer, integer), ew_ai_request_tombstone(), ew_ai_flag_guard(),
                       ew_ai_spend(boolean), ew_ai_request_open(text, text, uuid, bytea),
                       ew_ai_request_settle(uuid, text, smallint, jsonb), ew_ai_lock_subject(uuid),
                       ew_ai_flags_put(uuid, bytea, jsonb, jsonb), ew_ai_gate(text, uuid, bytea),
                       ew_ai_forget_subject(), ew_ai_erase_subject(text, uuid),
                       ew_ai_decide(uuid, text), ew_ai_request_fail(uuid, text, jsonb), ew_ai_my_usage(),
                       ew_assistant_begin(), ew_assistant_finish(uuid, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_ai_decide(uuid, text), ew_ai_request_fail(uuid, text, jsonb), ew_ai_my_usage(),
                          ew_assistant_begin(), ew_assistant_finish(uuid, text, jsonb) TO eyework_app;
