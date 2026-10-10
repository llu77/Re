-- ════════════════════════════════════════════════════════════════════════
-- NEXT_marketing — مساحة عمل التسويق: خطة الحملة، وقنواتها، ومحتواها، ونتائجها،
--                  ومراجعة سيمبول
-- ════════════════════════════════════════════════════════════════════════
-- ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو النموذج، فيُفرض هنا:
--
--   • كل صفٍّ لصاحبه: RLS مفروضة على المالك أيضاً (FORCE). دور الويب يقرأ صفوفه
--     ولا يكتب أيّ جدولٍ مباشرة: كل كتابةٍ دالّةٌ تقرأ صاحب الجلسة من
--     ew_current_user()، لا من معامِل، ولحساب التسويق وحده.
--   • كل كتابةٍ مشروطةٌ بما رآه صاحبها (row_version): ضغطةٌ مكرّرة بالنظر لا تُطبَّق مرتين.
--   • الخطة المعتمدة ثابتة، والمحتوى المعتمد ثابت: يُعاد إلى التخطيط أو إلى المسودة
--     ليُعدَّل، ثم يُعتمد من جديد. لا محتوى يُعتمد ولا يُنشر وخطّته غير معتمدة.
--   • لا اعتماد ولا حفظ نتائج إلا بإقرارٍ بكل تنبيهٍ قائم لحظتها، والإقرار يُحفظ معه.
--     التنبيه لا يمنع؛ الإقرار به هو القرار، وهو للموظف.
--   • المستحيل يُرفض: مخصّصات القنوات فوق الميزانية، ونتائج لفترةٍ لم تأتِ أو خارج
--     الحملة أو متداخلة، ونصٌّ بمحارف تحكّمٍ أو اتجاهٍ خفية.
--   • النموذج لا يكتب إلا تنبيهاتٍ على نصٍّ لم يتغيّر منذ أُرسل، وكل اقتباسٍ فيها من
--     النصّ نفسه. سقوف كلفته هنا، والسقف العام يجمع كل دفاتر الذكاء الاصطناعي
--     عبر ew_ai_spend.
-- ════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF to_regprocedure('ew_new_open_account(uuid)') IS NULL
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = 'attempt_tombstones'
                         AND column_name = 'new_account') THEN
        RAISE EXCEPTION 'مساحة التسويق تحتاج ترحيل التسجيل المفتوح (NEXT_open_registration) قبلها.';
    END IF;
END
$$;

-- ── المجالات ────────────────────────────────────────────────────────────
-- نصٌّ بلا محارف تحكّم (عدا فاصل السطر في متعدّد الأسطر) ولا محارف اتجاهٍ خفية ولا
-- مسافاتٍ في طرفيه، وبصورة NFC: ما يُرى هو ما يُخزَّن ويُنسخ.
CREATE FUNCTION ew_mkt_text_ok(t text, p_multiline boolean) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT t = btrim(t, E' \n')
       AND t !~ '[\x01-\x09\x0B-\x1F\x7F-\x9F]'
       AND (p_multiline OR strpos(t, E'\n') = 0)
       AND t !~ '[‎‏‪-‮⁦-⁩]'
       AND t IS NFC NORMALIZED
$$;

-- القنوات نظير eyework/marketing_rules.CHANNELS؛ اختبارٌ يقارنهما.
CREATE FUNCTION ew_mkt_channel_known(c text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT c IN ('INSTAGRAM', 'X', 'SNAPCHAT', 'TIKTOK', 'WHATSAPP', 'YOUTUBE', 'GOOGLE_ADS', 'OTHER')
$$;

-- المؤشّر يقيس الهدف: نظير marketing_rules.KPIS_BY_GOAL.
CREATE FUNCTION ew_mkt_kpi_fits(p_goal text, p_kpi text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT CASE p_goal
        WHEN 'AWARENESS' THEN p_kpi = 'IMPRESSIONS'
        WHEN 'TRAFFIC'   THEN p_kpi = 'CLICKS'
        WHEN 'LEADS'     THEN p_kpi IN ('LEADS', 'COST_PER_LEAD')
        WHEN 'SALES'     THEN p_kpi IN ('ORDERS', 'REVENUE', 'COST_PER_ORDER')
        ELSE false
    END
$$;

-- مجموعتا مفاتيح التنبيهات متساويتان، بلا اعتبارٍ للترتيب ولا للتكرار.
CREATE FUNCTION ew_mkt_same_keys(a text[], b text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT ARRAY(SELECT DISTINCT x FROM unnest(coalesce(a, '{}')) x ORDER BY x)
         = ARRAY(SELECT DISTINCT x FROM unnest(coalesce(b, '{}')) x ORDER BY x)
$$;

-- ── آلات الحالات ────────────────────────────────────────────────────────
-- جداول لا ثوابت: المحفّز يقرؤها، واختبارٌ يقارنها بـeyework/marketing_rules.py.
CREATE TABLE mkt_campaign_transition (
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (from_status, to_status)
);
INSERT INTO mkt_campaign_transition (from_status, to_status) VALUES
    ('PLANNING', 'APPROVED'),
    ('APPROVED', 'PLANNING'),
    ('PLANNING', 'CANCELLED'),
    ('APPROVED', 'CANCELLED');

CREATE TABLE mkt_item_transition (
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (from_status, to_status)
);
INSERT INTO mkt_item_transition (from_status, to_status) VALUES
    ('DRAFT',    'APPROVED'),
    ('APPROVED', 'DRAFT'),
    ('APPROVED', 'PUBLISHED'),
    ('DRAFT',    'CANCELLED'),
    ('APPROVED', 'CANCELLED');

-- ── الجداول ─────────────────────────────────────────────────────────────
CREATE TABLE mkt_campaigns (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status              text NOT NULL DEFAULT 'PLANNING'
                        CONSTRAINT mkt_campaign_status CHECK (status IN ('PLANNING', 'APPROVED', 'CANCELLED')),
    row_version         integer NOT NULL DEFAULT 1,
    name                text NOT NULL
                        CONSTRAINT mkt_campaign_name CHECK (char_length(name) BETWEEN 2 AND 60 AND ew_mkt_text_ok(name, false)),
    -- ما يُروَّج له والرسالة الأساسية.
    brief               text
                        CONSTRAINT mkt_campaign_brief CHECK (brief IS NULL OR (char_length(brief) BETWEEN 1 AND 500
                                                                                AND ew_mkt_text_ok(brief, true))),
    goal                text
                        CONSTRAINT mkt_campaign_goal CHECK (goal IS NULL OR goal IN ('AWARENESS', 'TRAFFIC', 'LEADS', 'SALES')),
    kpi_metric          text,
    -- عددٌ للعدّادات، وهللاتٌ لـREVENUE وCOST_PER_LEAD وCOST_PER_ORDER.
    kpi_target          bigint,
    audience            text
                        CONSTRAINT mkt_campaign_audience CHECK (audience IS NULL OR (char_length(audience) BETWEEN 1 AND 200
                                                                                      AND ew_mkt_text_ok(audience, false))),
    -- الميزانية الإجمالية بالهللة. صفرٌ لحملةٍ بلا إنفاق.
    budget_halalas      bigint NOT NULL DEFAULT 0
                        CONSTRAINT mkt_budget_range CHECK (budget_halalas BETWEEN 0 AND 10000000000),
    starts_on           date,
    ends_on             date,
    approved_at         timestamptz,
    cancelled_at        timestamptz,
    -- مفاتيح التنبيهات التي أقرّ بها صاحبها لحظة الاعتماد.
    approved_with_flags text[] NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    CONSTRAINT mkt_kpi_complete CHECK ((kpi_metric IS NULL) = (kpi_target IS NULL)),
    CONSTRAINT mkt_kpi_target_range CHECK (kpi_target IS NULL OR kpi_target BETWEEN 1 AND 1000000000000),
    CONSTRAINT mkt_kpi_fits_goal CHECK (kpi_metric IS NULL OR ew_mkt_kpi_fits(goal, kpi_metric)),
    CONSTRAINT mkt_dates_order CHECK (starts_on IS NULL OR ends_on IS NULL OR ends_on >= starts_on),
    CONSTRAINT mkt_dates_span CHECK (starts_on IS NULL OR ends_on IS NULL OR ends_on - starts_on <= 365),
    CONSTRAINT mkt_dates_floor CHECK (starts_on IS NULL OR starts_on >= DATE '2020-01-01'),
    CONSTRAINT mkt_approved_complete
        CHECK (status <> 'APPROVED' OR (goal IS NOT NULL AND starts_on IS NOT NULL AND ends_on IS NOT NULL)),
    CONSTRAINT mkt_approved_iff_time CHECK ((status = 'APPROVED') = (approved_at IS NOT NULL)),
    CONSTRAINT mkt_cancelled_iff_time CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))
);
CREATE INDEX mkt_campaigns_user_status ON mkt_campaigns (user_id, status, starts_on);

CREATE TABLE mkt_campaign_channels (
    campaign_id       uuid NOT NULL,
    user_id           uuid NOT NULL,
    channel           text NOT NULL CONSTRAINT mkt_channel_known CHECK (ew_mkt_channel_known(channel)),
    allocated_halalas bigint NOT NULL DEFAULT 0
                      CONSTRAINT mkt_allocation_range CHECK (allocated_halalas BETWEEN 0 AND 10000000000),
    PRIMARY KEY (campaign_id, channel),
    FOREIGN KEY (campaign_id, user_id) REFERENCES mkt_campaigns (id, user_id) ON DELETE CASCADE
);

CREATE TABLE mkt_items (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id           uuid NOT NULL,
    user_id               uuid NOT NULL,
    channel               text NOT NULL,
    status                text NOT NULL DEFAULT 'DRAFT'
                          CONSTRAINT mkt_item_status CHECK (status IN ('DRAFT', 'APPROVED', 'PUBLISHED', 'CANCELLED')),
    row_version           integer NOT NULL DEFAULT 1,
    publish_on            date NOT NULL CONSTRAINT mkt_item_date_floor CHECK (publish_on >= DATE '2020-01-01'),
    -- بتوقيت الرياض، بالدقيقة. فارغٌ: في أيّ وقتٍ من اليوم.
    publish_at            time(0) without time zone
                          CONSTRAINT mkt_item_time_minute CHECK (publish_at IS NULL OR extract(second FROM publish_at) = 0),
    body                  text NOT NULL
                          CONSTRAINT mkt_item_body CHECK (char_length(body) BETWEEN 1 AND 2000 AND ew_mkt_text_ok(body, true)),
    -- يكتبه المحفّز: sha256 للقناة والنصّ، وهما ما يُرسَل للمراجعة.
    body_digest           bytea NOT NULL DEFAULT '\x' CONSTRAINT mkt_item_digest CHECK (octet_length(body_digest) = 32),
    -- تنبيهات قواعد النصّ كما حسبها الخادم من النصّ نفسه (copy_rules وطول إكس).
    copy_warnings         text[] NOT NULL DEFAULT '{}'
                          CONSTRAINT mkt_item_copy_warnings CHECK (
                              copy_warnings <@ ARRAY['PRICE', 'HEALTH_CLAIM', 'SUPERLATIVE', 'TOO_LONG_FOR_X']::text[]
                              AND cardinality(copy_warnings) <= 4),
    planned_spend_halalas bigint
                          CONSTRAINT mkt_item_spend_range CHECK (planned_spend_halalas IS NULL
                                                                 OR planned_spend_halalas BETWEEN 0 AND 10000000000),
    -- إعلان المنتج (أداة الصورة) الذي جاء منه النصّ، إن جاء منه.
    source_campaign_id    uuid,
    -- النصّ الذي اكتملت مراجعة سيمبول له. يساوي body_digest أو لا شيء.
    ai_reviewed_digest    bytea,
    approved_at           timestamptz,
    published_at          timestamptz,
    cancelled_at          timestamptz,
    approved_with_flags   text[] NOT NULL DEFAULT '{}',
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    FOREIGN KEY (campaign_id, user_id) REFERENCES mkt_campaigns (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id, channel) REFERENCES mkt_campaign_channels (campaign_id, channel) ON DELETE CASCADE,
    FOREIGN KEY (source_campaign_id, user_id) REFERENCES campaigns (id, user_id) ON DELETE SET NULL (source_campaign_id),
    CONSTRAINT mkt_item_approved_iff_time CHECK ((status IN ('APPROVED', 'PUBLISHED')) = (approved_at IS NOT NULL)),
    CONSTRAINT mkt_item_published_iff_time CHECK ((status = 'PUBLISHED') = (published_at IS NOT NULL)),
    CONSTRAINT mkt_item_cancelled_iff_time CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))
);
CREATE INDEX mkt_items_user_day ON mkt_items (user_id, publish_on);
CREATE INDEX mkt_items_campaign ON mkt_items (campaign_id, channel);
CREATE INDEX mkt_items_source ON mkt_items (source_campaign_id) WHERE source_campaign_id IS NOT NULL;

CREATE TABLE mkt_results (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id        uuid NOT NULL,
    user_id            uuid NOT NULL,
    channel            text NOT NULL,
    row_version        integer NOT NULL DEFAULT 1,
    period_start       date NOT NULL,
    period_end         date NOT NULL,
    spend_halalas      bigint CONSTRAINT mkt_results_spend CHECK (spend_halalas BETWEEN 0 AND 10000000000),
    impressions        bigint CONSTRAINT mkt_results_impressions CHECK (impressions BETWEEN 0 AND 100000000000),
    clicks             bigint CONSTRAINT mkt_results_clicks CHECK (clicks BETWEEN 0 AND 100000000000),
    leads              bigint CONSTRAINT mkt_results_leads CHECK (leads BETWEEN 0 AND 1000000000),
    orders             bigint CONSTRAINT mkt_results_orders CHECK (orders BETWEEN 0 AND 1000000000),
    revenue_halalas    bigint CONSTRAINT mkt_results_revenue CHECK (revenue_halalas BETWEEN 0 AND 100000000000),
    acknowledged_flags text[] NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (campaign_id, user_id) REFERENCES mkt_campaigns (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id, channel) REFERENCES mkt_campaign_channels (campaign_id, channel),
    CONSTRAINT mkt_results_period CHECK (period_end >= period_start AND period_start >= DATE '2020-01-01'),
    CONSTRAINT mkt_results_some CHECK (num_nonnulls(spend_halalas, impressions, clicks, leads, orders, revenue_halalas) >= 1)
);
CREATE INDEX mkt_results_channel_period ON mkt_results (campaign_id, channel, period_start);

-- ── دفتر مراجعة سيمبول ──────────────────────────────────────────────────
-- كل استدعاءٍ للنموذج يُحسب، نجح أم فشل. بلا مفتاحٍ خارجي إلى المنشور عمداً: الاستدعاء
-- المُغلق لا يتغيّر (ew_attempt_settle_once)، ويبقى بعد حذف منشوره لتعدّه السقوف.
CREATE TABLE mkt_review_calls (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_id        uuid NOT NULL,
    -- ما أُرسل بالضبط (القناة والنصّ)، بصمةً لا نصّاً.
    body_digest    bytea NOT NULL CONSTRAINT mkt_review_digest CHECK (octet_length(body_digest) = 32),
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    outcome        text CONSTRAINT mkt_review_outcome CHECK (outcome IN (
                       'OK', 'REFUSED', 'OUTPUT_INVALID', 'DISCARDED',
                       'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE', 'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR')),
    input_tokens   integer CHECK (input_tokens >= 0),
    output_tokens  integer CHECK (output_tokens >= 0),
    served_model   text CHECK (served_model IS NULL OR served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    prompt_version text CHECK (prompt_version IS NULL OR prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    api_request_id text CHECK (api_request_id IS NULL OR char_length(api_request_id) <= 128),
    new_account    boolean NOT NULL DEFAULT false,
    CONSTRAINT mkt_review_finished_iff_outcome CHECK ((finished_at IS NULL) = (outcome IS NULL))
);
CREATE INDEX mkt_review_calls_user_time ON mkt_review_calls (user_id, started_at DESC);
CREATE INDEX mkt_review_calls_time      ON mkt_review_calls (started_at DESC);

CREATE TRIGGER trg_mkt_review_settle BEFORE UPDATE ON mkt_review_calls
    FOR EACH ROW EXECUTE FUNCTION ew_attempt_settle_once();

-- حذف الحساب لا يُفرغ السقف العام: أثرٌ بلا هوية كمحاولات الحملة.
CREATE FUNCTION ew_mkt_review_tombstone() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.started_at > now() - interval '24 hours' AND ew_is_billable(OLD.outcome) THEN
        INSERT INTO attempt_tombstones (started_at, outcome, new_account)
        VALUES (OLD.started_at, OLD.outcome, OLD.new_account);
    END IF;
    RETURN OLD;
END
$$;
CREATE TRIGGER trg_mkt_review_tombstone BEFORE DELETE ON mkt_review_calls
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_review_tombstone();

-- تنبيهات سيمبول لنصٍّ بعينه. تُمحى حين يتغيّر النصّ، ولا تُعدَّل.
CREATE TABLE mkt_ai_flags (
    item_id     uuid NOT NULL,
    user_id     uuid NOT NULL,
    body_digest bytea NOT NULL CHECK (octet_length(body_digest) = 32),
    ordinal     smallint NOT NULL CONSTRAINT mkt_ai_flag_ordinal CHECK (ordinal BETWEEN 1 AND 5),
    kind        text NOT NULL CONSTRAINT mkt_ai_flag_kind CHECK (kind IN (
                    'COMPARATIVE', 'ABSOLUTE', 'HEALTH', 'CERTIFICATION', 'PRICE_OFFER',
                    'ORIGIN_NATURE', 'RESULT', 'ENDORSEMENT')),
    quote       text NOT NULL
                CONSTRAINT mkt_ai_flag_quote CHECK (char_length(quote) BETWEEN 2 AND 120 AND ew_mkt_text_ok(quote, false)),
    reason      text NOT NULL
                CONSTRAINT mkt_ai_flag_reason CHECK (char_length(reason) BETWEEN 1 AND 160 AND ew_mkt_text_ok(reason, false)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, body_digest, ordinal),
    FOREIGN KEY (item_id, user_id) REFERENCES mkt_items (id, user_id) ON DELETE CASCADE
);
CREATE TRIGGER trg_mkt_ai_flags_append_only BEFORE UPDATE ON mkt_ai_flags
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();

-- ── المحفّزات ───────────────────────────────────────────────────────────
-- حملةٌ تبدأ في التخطيط، لحساب التسويق وحده، وخمسون غير ملغاةٍ لكل حساب على الأكثر.
CREATE FUNCTION ew_mkt_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'PLANNING' OR NEW.row_version <> 1 OR NEW.approved_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL OR cardinality(NEW.approved_with_flags) <> 0 THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_starts_planning';
    END IF;
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'mkt_needs_marketing';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.mkt.campaigns.' || NEW.user_id::text, 0));
    IF (SELECT count(*) FROM mkt_campaigns WHERE user_id = NEW.user_id AND status <> 'CANCELLED') >= 50 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_cap';
    END IF;
    IF NEW.starts_on > ew_riyadh_today() + 730 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_range';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_campaign_insert BEFORE INSERT ON mkt_campaigns
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_campaign_insert_guard();

CREATE FUNCTION ew_mkt_campaign_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    allocated bigint;
BEGIN
    IF OLD.status = 'CANCELLED' THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.created_at <> OLD.created_at
       OR NEW.row_version <> OLD.row_version THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_managed_columns';
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM mkt_campaign_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_transition';
    END IF;
    -- الخطة تتغيّر في التخطيط وحده: ما اعتُمد هو ما رآه صاحبه.
    IF ROW(NEW.name, NEW.brief, NEW.goal, NEW.kpi_metric, NEW.kpi_target, NEW.audience, NEW.budget_halalas,
           NEW.starts_on, NEW.ends_on)
       IS DISTINCT FROM ROW(OLD.name, OLD.brief, OLD.goal, OLD.kpi_metric, OLD.kpi_target, OLD.audience,
                            OLD.budget_halalas, OLD.starts_on, OLD.ends_on) THEN
        IF NOT (OLD.status = 'PLANNING' AND NEW.status = 'PLANNING') THEN
            RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
        END IF;
        IF NEW.starts_on IS DISTINCT FROM OLD.starts_on AND NEW.starts_on > ew_riyadh_today() + 730 THEN
            RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_range';
        END IF;
    END IF;
    IF NEW.budget_halalas < OLD.budget_halalas THEN
        SELECT coalesce(sum(allocated_halalas), 0) INTO allocated FROM mkt_campaign_channels WHERE campaign_id = NEW.id;
        IF allocated > NEW.budget_halalas THEN
            RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
        END IF;
    END IF;
    -- النتائج المُدخلة تبقى داخل الحملة: لا تُقصّ المواعيد من تحتها.
    IF ROW(NEW.starts_on, NEW.ends_on) IS DISTINCT FROM ROW(OLD.starts_on, OLD.ends_on) AND EXISTS (
           SELECT 1 FROM mkt_results r WHERE r.campaign_id = NEW.id
              AND (NEW.starts_on IS NULL OR NEW.ends_on IS NULL
                   OR r.period_start < NEW.starts_on OR r.period_end > NEW.ends_on)) THEN
        RAISE EXCEPTION 'dates' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_dates_exclude_results';
    END IF;
    IF NEW.status = 'APPROVED' AND OLD.status <> 'APPROVED'
       AND NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = NEW.id) THEN
        RAISE EXCEPTION 'incomplete' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_incomplete';
    END IF;

    -- أعمدةٌ يكتبها المحفّز وحده.
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.approved_at := CASE WHEN NEW.status = 'APPROVED'
                            THEN CASE WHEN OLD.status = 'APPROVED' THEN OLD.approved_at ELSE now() END END;
    NEW.approved_with_flags := CASE
        WHEN NEW.status = 'APPROVED' AND OLD.status = 'APPROVED' THEN OLD.approved_with_flags
        WHEN NEW.status = 'APPROVED' THEN NEW.approved_with_flags
        ELSE '{}'::text[] END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() END;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_campaign_guard BEFORE UPDATE ON mkt_campaigns
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_campaign_guard();

-- القنوات تتغيّر والخطة في التخطيط وحده. قناةٌ عليها محتوىً حيّ أو نتائج لا تُزال؛
-- ومحتواها الملغى يُزال معها. وحين تُحذف الحملة نفسها (حذف الحساب أو الكنس) تتبعها.
CREATE FUNCTION ew_mkt_channel_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    st text;
BEGIN
    SELECT status INTO st FROM mkt_campaigns WHERE id = coalesce(NEW.campaign_id, OLD.campaign_id) FOR UPDATE;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF st <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.campaign_id <> OLD.campaign_id OR NEW.user_id <> OLD.user_id
                             OR NEW.channel <> OLD.channel) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_managed';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM mkt_items WHERE campaign_id = OLD.campaign_id AND channel = OLD.channel
                                              AND status <> 'CANCELLED') THEN
            RAISE EXCEPTION 'in use' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_in_use';
        END IF;
        IF EXISTS (SELECT 1 FROM mkt_results WHERE campaign_id = OLD.campaign_id AND channel = OLD.channel) THEN
            RAISE EXCEPTION 'results' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_has_results';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_channel_guard BEFORE INSERT OR UPDATE OR DELETE ON mkt_campaign_channels
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_channel_guard();

-- مجموع المخصّصات لا يتجاوز الميزانية. مؤجَّلٌ إلى نهاية المعاملة: نقل مبلغٍ من قناةٍ
-- إلى أخرى يمرّ بحالٍ وسطى. الدالّة ew_mkt_set_channels تفحصه قبلها برسالةٍ أوضح.
CREATE FUNCTION ew_mkt_allocations_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF (SELECT coalesce(sum(allocated_halalas), 0) FROM mkt_campaign_channels WHERE campaign_id = NEW.campaign_id)
       > (SELECT budget_halalas FROM mkt_campaigns WHERE id = NEW.campaign_id) THEN
        RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
    END IF;
    RETURN NULL;
END
$$;
CREATE CONSTRAINT TRIGGER trg_mkt_allocations AFTER INSERT OR UPDATE ON mkt_campaign_channels
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ew_mkt_allocations_check();

-- منشورٌ يبدأ مسودة، في حملةٍ غير ملغاة، وثلاثمئة لكل حملة على الأكثر.
CREATE FUNCTION ew_mkt_item_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    st text;
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.approved_at IS NOT NULL OR NEW.published_at IS NOT NULL
       OR NEW.cancelled_at IS NOT NULL OR cardinality(NEW.approved_with_flags) <> 0
       OR NEW.ai_reviewed_digest IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_starts_draft';
    END IF;
    SELECT status INTO st FROM mkt_campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    IF st IS NULL OR st = 'CANCELLED' THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_is_final';
    END IF;
    IF (SELECT count(*) FROM mkt_items WHERE campaign_id = NEW.campaign_id) >= 300 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_cap';
    END IF;
    IF NEW.publish_on > ew_riyadh_today() + 730 THEN
        RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_date_range';
    END IF;
    NEW.body_digest := sha256(convert_to(NEW.channel || E'\n' || NEW.body, 'UTF8'));
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_item_insert BEFORE INSERT ON mkt_items
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_item_insert_guard();

CREATE FUNCTION ew_mkt_item_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    st text;
    content_changed boolean;
BEGIN
    -- إعلان المنتج حُذف (الكنس أو حذف الحساب): يُفرَغ مرجعه وحده، ولا شيء غيره.
    IF NEW.source_campaign_id IS NULL AND OLD.source_campaign_id IS NOT NULL THEN
        IF ROW(NEW.id, NEW.campaign_id, NEW.user_id, NEW.channel, NEW.status, NEW.row_version, NEW.publish_on,
               NEW.publish_at, NEW.body, NEW.body_digest, NEW.copy_warnings, NEW.planned_spend_halalas,
               NEW.ai_reviewed_digest, NEW.approved_at, NEW.published_at, NEW.cancelled_at, NEW.approved_with_flags,
               NEW.created_at, NEW.updated_at)
           IS DISTINCT FROM ROW(OLD.id, OLD.campaign_id, OLD.user_id, OLD.channel, OLD.status, OLD.row_version,
               OLD.publish_on, OLD.publish_at, OLD.body, OLD.body_digest, OLD.copy_warnings, OLD.planned_spend_halalas,
               OLD.ai_reviewed_digest, OLD.approved_at, OLD.published_at, OLD.cancelled_at, OLD.approved_with_flags,
               OLD.created_at, OLD.updated_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('PUBLISHED', 'CANCELLED') THEN
        RAISE EXCEPTION 'final' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_final';
    END IF;
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.campaign_id <> OLD.campaign_id
       OR NEW.created_at <> OLD.created_at OR NEW.row_version <> OLD.row_version
       OR NEW.source_campaign_id IS DISTINCT FROM OLD.source_campaign_id
       OR NEW.body_digest <> OLD.body_digest THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
    END IF;
    content_changed := ROW(NEW.channel, NEW.publish_on, NEW.publish_at, NEW.body, NEW.planned_spend_halalas,
                           NEW.copy_warnings)
                       IS DISTINCT FROM ROW(OLD.channel, OLD.publish_on, OLD.publish_at, OLD.body,
                                            OLD.planned_spend_halalas, OLD.copy_warnings);

    -- اكتمال المراجعة وحده: لا يغيّر المحتوى ولا رقم الصفّ، ولا يكون إلا للنصّ الحالي.
    IF NOT content_changed AND NEW.status = OLD.status
       AND NEW.ai_reviewed_digest IS DISTINCT FROM OLD.ai_reviewed_digest THEN
        IF NEW.ai_reviewed_digest IS DISTINCT FROM OLD.body_digest OR OLD.status <> 'DRAFT'
           OR ROW(NEW.approved_at, NEW.published_at, NEW.cancelled_at, NEW.approved_with_flags, NEW.updated_at)
              IS DISTINCT FROM ROW(OLD.approved_at, OLD.published_at, OLD.cancelled_at, OLD.approved_with_flags,
                                   OLD.updated_at) THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_managed_columns';
        END IF;
        RETURN NEW;
    END IF;

    IF content_changed AND NOT (OLD.status = 'DRAFT' AND NEW.status = 'DRAFT') THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM mkt_item_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_transition';
    END IF;
    -- لا محتوى يُعتمد ولا يُنشر وخطّته في التخطيط. FOR SHARE يقف أمام إعادة الخطة إلى التخطيط.
    IF NEW.status IN ('APPROVED', 'PUBLISHED') AND NEW.status <> OLD.status THEN
        SELECT status INTO st FROM mkt_campaigns WHERE id = NEW.campaign_id FOR SHARE;
        IF st IS DISTINCT FROM 'APPROVED' THEN
            RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_not_approved';
        END IF;
    END IF;
    IF NEW.status = 'PUBLISHED' AND OLD.status <> 'PUBLISHED' THEN
        IF NEW.published_at IS NULL OR NEW.published_at > now() OR NEW.published_at < now() - interval '30 days' THEN
            RAISE EXCEPTION 'published' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_published_at_range';
        END IF;
    ELSE
        NEW.published_at := OLD.published_at;
    END IF;
    IF content_changed THEN
        IF NEW.publish_on IS DISTINCT FROM OLD.publish_on AND NEW.publish_on > ew_riyadh_today() + 730 THEN
            RAISE EXCEPTION 'date' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_date_range';
        END IF;
        NEW.body_digest := sha256(convert_to(NEW.channel || E'\n' || NEW.body, 'UTF8'));
        IF NEW.body_digest <> OLD.body_digest THEN
            DELETE FROM mkt_ai_flags WHERE item_id = NEW.id;
            NEW.ai_reviewed_digest := NULL;
        ELSE
            NEW.ai_reviewed_digest := OLD.ai_reviewed_digest;
        END IF;
    ELSE
        NEW.ai_reviewed_digest := OLD.ai_reviewed_digest;
    END IF;

    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.approved_at := CASE WHEN NEW.status IN ('APPROVED', 'PUBLISHED')
                            THEN coalesce(OLD.approved_at, now()) END;
    NEW.approved_with_flags := CASE
        WHEN NEW.status IN ('APPROVED', 'PUBLISHED') AND OLD.status IN ('APPROVED', 'PUBLISHED')
            THEN OLD.approved_with_flags
        WHEN NEW.status = 'APPROVED' THEN NEW.approved_with_flags
        ELSE '{}'::text[] END;
    NEW.cancelled_at := CASE WHEN NEW.status = 'CANCELLED' THEN now() END;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_item_guard BEFORE UPDATE ON mkt_items
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_item_guard();

-- النتائج لحملةٍ معتمدة، لفترةٍ داخلها لم تتجاوز اليوم، بلا تداخلٍ لقناةٍ واحدة،
-- وألفٌ لكل حملةٍ على الأكثر. قفل صفّ الحملة يجعل الفحص والكتابة ذرّيين.
CREATE FUNCTION ew_mkt_results_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    c mkt_campaigns%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.campaign_id <> OLD.campaign_id
                             OR NEW.channel <> OLD.channel OR NEW.created_at <> OLD.created_at
                             OR NEW.row_version <> OLD.row_version) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_managed';
    END IF;
    SELECT * INTO c FROM mkt_campaigns WHERE id = NEW.campaign_id FOR UPDATE;
    IF c.status IS DISTINCT FROM 'APPROVED' THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_need_approved_plan';
    END IF;
    IF NEW.period_start < c.starts_on OR NEW.period_end > c.ends_on THEN
        RAISE EXCEPTION 'outside' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_outside_campaign';
    END IF;
    IF NEW.period_end > ew_riyadh_today() THEN
        RAISE EXCEPTION 'future' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_in_future';
    END IF;
    IF EXISTS (SELECT 1 FROM mkt_results r
                WHERE r.campaign_id = NEW.campaign_id AND r.channel = NEW.channel AND r.id <> NEW.id
                  AND r.period_start <= NEW.period_end AND r.period_end >= NEW.period_start) THEN
        RAISE EXCEPTION 'overlap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_overlap';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.row_version <> 1 THEN
            RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_managed';
        END IF;
        IF (SELECT count(*) FROM mkt_results WHERE campaign_id = NEW.campaign_id) >= 1000 THEN
            RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_cap';
        END IF;
        NEW.created_at := now();
    ELSE
        NEW.row_version := OLD.row_version + 1;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_mkt_results_guard BEFORE INSERT OR UPDATE ON mkt_results
    FOR EACH ROW EXECUTE FUNCTION ew_mkt_results_guard();

-- ── التنبيهات: محسوبةٌ هنا من بيانات صاحبها وحده ───────────────────────────
-- كل تنبيهٍ بمفتاحٍ ثابت (الرمز، أو الرمز ونقطتين ومعرّفه) يُقرّ به الموظف كما رآه،
-- وتفاصيل يكتب منها الخادم الجملة العربية باسم صاحبها.

-- تنبيهات المنشور: قواعد النصّ، والموعد، والميزانية، وما كتبه سيمبول للنصّ الحالي.
CREATE FUNCTION ew_mkt_item_flags(p_item uuid)
RETURNS TABLE (flag_key text, code text, detail jsonb)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    i       mkt_items%ROWTYPE;
    c       mkt_campaigns%ROWTYPE;
    alloc   bigint;
    planned bigint;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    SELECT * INTO c FROM mkt_campaigns WHERE id = i.campaign_id;

    RETURN QUERY SELECT w, w, '{}'::jsonb FROM unnest(i.copy_warnings) AS w ORDER BY w;

    IF c.starts_on IS NOT NULL AND (i.publish_on < c.starts_on OR i.publish_on > c.ends_on) THEN
        RETURN QUERY SELECT 'ITEM_OUTSIDE_CAMPAIGN'::text, 'ITEM_OUTSIDE_CAMPAIGN'::text,
                            jsonb_build_object('publish_on', i.publish_on, 'starts_on', c.starts_on,
                                               'ends_on', c.ends_on);
    END IF;
    IF i.status = 'DRAFT' AND i.publish_on < ew_riyadh_today() THEN
        RETURN QUERY SELECT 'ITEM_DATE_PASSED'::text, 'ITEM_DATE_PASSED'::text,
                            jsonb_build_object('publish_on', i.publish_on);
    END IF;
    IF i.publish_at IS NOT NULL AND i.status IN ('DRAFT', 'APPROVED') THEN
        RETURN QUERY
            SELECT 'SLOT_CLASH:' || o.id::text, 'SLOT_CLASH'::text,
                   jsonb_build_object('other_item', o.id, 'campaign_name', oc.name, 'channel', o.channel,
                                      'publish_on', o.publish_on, 'publish_at', to_char(o.publish_at, 'HH24:MI'))
              FROM mkt_items o JOIN mkt_campaigns oc ON oc.id = o.campaign_id
             WHERE o.user_id = uid AND o.id <> i.id AND o.channel = i.channel AND o.publish_on = i.publish_on
               AND o.status <> 'CANCELLED' AND o.publish_at IS NOT NULL
               AND abs(extract(epoch FROM (o.publish_at - i.publish_at))) < 3600
             ORDER BY o.publish_at, o.id
             LIMIT 3;
    END IF;
    IF coalesce(i.planned_spend_halalas, 0) > 0 AND i.status IN ('DRAFT', 'APPROVED') THEN
        SELECT allocated_halalas INTO alloc FROM mkt_campaign_channels
         WHERE campaign_id = i.campaign_id AND channel = i.channel;
        SELECT coalesce(sum(planned_spend_halalas), 0) INTO planned FROM mkt_items
         WHERE campaign_id = i.campaign_id AND channel = i.channel AND status <> 'CANCELLED';
        IF planned > alloc THEN
            RETURN QUERY SELECT 'CHANNEL_PLANNED_OVER_ALLOCATION:' || i.channel,
                                'CHANNEL_PLANNED_OVER_ALLOCATION'::text,
                                jsonb_build_object('channel', i.channel, 'planned', planned, 'allocated', alloc);
        END IF;
    END IF;
    RETURN QUERY
        SELECT 'CLAIM_NEEDS_PROOF:' || f.ordinal::text, 'CLAIM_NEEDS_PROOF'::text,
               jsonb_build_object('kind', f.kind, 'quote', f.quote, 'reason', f.reason)
          FROM mkt_ai_flags f
         WHERE f.item_id = i.id AND f.body_digest = i.body_digest
         ORDER BY f.ordinal;
END
$$;

-- تنبيهات الخطة عند اعتمادها: المؤشّر، والميزانية، والمواعيد.
CREATE FUNCTION ew_mkt_campaign_flags(p_campaign uuid)
RETURNS TABLE (flag_key text, code text, detail jsonb)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_current_user();
    c     mkt_campaigns%ROWTYPE;
    spent bigint;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.kpi_metric IS NULL THEN
        RETURN QUERY SELECT 'NO_KPI'::text, 'NO_KPI'::text, jsonb_build_object('goal', c.goal);
    END IF;
    RETURN QUERY
        SELECT 'CHANNEL_PLANNED_OVER_ALLOCATION:' || ch.channel, 'CHANNEL_PLANNED_OVER_ALLOCATION'::text,
               jsonb_build_object('channel', ch.channel, 'planned', p.planned, 'allocated', ch.allocated_halalas)
          FROM mkt_campaign_channels ch
          CROSS JOIN LATERAL (SELECT coalesce(sum(planned_spend_halalas), 0) AS planned FROM mkt_items
                               WHERE campaign_id = ch.campaign_id AND channel = ch.channel
                                 AND status <> 'CANCELLED') p
         WHERE ch.campaign_id = c.id AND p.planned > ch.allocated_halalas
         ORDER BY ch.channel;
    RETURN QUERY
        SELECT 'CHANNEL_SPEND_OVER_ALLOCATION:' || ch.channel, 'CHANNEL_SPEND_OVER_ALLOCATION'::text,
               jsonb_build_object('channel', ch.channel, 'spent', s.spent, 'allocated', ch.allocated_halalas)
          FROM mkt_campaign_channels ch
          CROSS JOIN LATERAL (SELECT coalesce(sum(spend_halalas), 0) AS spent FROM mkt_results
                               WHERE campaign_id = ch.campaign_id AND channel = ch.channel) s
         WHERE ch.campaign_id = c.id AND s.spent > ch.allocated_halalas
         ORDER BY ch.channel;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent FROM mkt_results WHERE campaign_id = c.id;
    IF spent > c.budget_halalas THEN
        RETURN QUERY SELECT 'TOTAL_SPEND_OVER_BUDGET'::text, 'TOTAL_SPEND_OVER_BUDGET'::text,
                            jsonb_build_object('spent', spent, 'budget', c.budget_halalas);
    END IF;
    IF c.starts_on IS NOT NULL THEN
        RETURN QUERY
            SELECT 'ITEM_OUTSIDE_CAMPAIGN:' || i.id::text, 'ITEM_OUTSIDE_CAMPAIGN'::text,
                   jsonb_build_object('item', i.id, 'channel', i.channel, 'publish_on', i.publish_on,
                                      'starts_on', c.starts_on, 'ends_on', c.ends_on)
              FROM mkt_items i
             WHERE i.campaign_id = c.id AND i.status IN ('DRAFT', 'APPROVED')
               AND (i.publish_on < c.starts_on OR i.publish_on > c.ends_on)
             ORDER BY i.publish_on, i.id
             LIMIT 20;
    END IF;
END
$$;

-- تنبيهات إدخال نتائج قبل حفظه: الإنفاق أمام المخصّص والميزانية. لا تنبيه لإدخالٍ بلا إنفاق.
CREATE FUNCTION ew_mkt_results_flags(p_campaign uuid, p_channel text, p_result uuid, p_spend bigint)
RETURNS TABLE (flag_key text, code text, detail jsonb)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid        uuid := ew_current_user();
    c          mkt_campaigns%ROWTYPE;
    alloc      bigint;
    spent_ch   bigint;
    spent_all  bigint;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF coalesce(p_spend, 0) = 0 THEN
        RETURN;
    END IF;
    SELECT allocated_halalas INTO alloc FROM mkt_campaign_channels WHERE campaign_id = c.id AND channel = p_channel;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent_ch FROM mkt_results
     WHERE campaign_id = c.id AND channel = p_channel AND id IS DISTINCT FROM p_result;
    SELECT coalesce(sum(spend_halalas), 0) INTO spent_all FROM mkt_results
     WHERE campaign_id = c.id AND id IS DISTINCT FROM p_result;
    spent_ch := spent_ch + p_spend;
    spent_all := spent_all + p_spend;
    IF spent_ch > alloc THEN
        RETURN QUERY SELECT 'CHANNEL_SPEND_OVER_ALLOCATION:' || p_channel, 'CHANNEL_SPEND_OVER_ALLOCATION'::text,
                            jsonb_build_object('channel', p_channel, 'spent', spent_ch, 'allocated', alloc,
                                               'entry', p_spend);
    END IF;
    IF spent_all > c.budget_halalas THEN
        RETURN QUERY SELECT 'TOTAL_SPEND_OVER_BUDGET'::text, 'TOTAL_SPEND_OVER_BUDGET'::text,
                            jsonb_build_object('spent', spent_all, 'budget', c.budget_halalas, 'entry', p_spend);
    END IF;
END
$$;

-- ── واجهة الكتابة لدور الويب ────────────────────────────────────────────
-- كل دالّة: SECURITY DEFINER، و`search_path` مثبَّت، والمستخدم من الجلسة.

-- صاحب الجلسة فعّال ومهنته التسويق. FOR SHARE يقف أمام تغيير المهنة.
CREATE FUNCTION ew_mkt_require() RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'MARKETING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'mkt_needs_marketing';
    END IF;
    RETURN uid;
END
$$;

-- حملةٌ لصاحب الجلسة، مقفلةٌ للكتابة، بما رآه صاحبها.
CREATE FUNCTION ew_mkt_lock_campaign(p_uid uuid, p_campaign uuid, p_expected_row_version integer)
RETURNS mkt_campaigns
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    c mkt_campaigns%ROWTYPE;
BEGIN
    SELECT * INTO c FROM mkt_campaigns WHERE id = p_campaign AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_expected_row_version IS NOT NULL AND c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    RETURN c;
END
$$;

CREATE FUNCTION ew_mkt_campaign_create(p_name text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_mkt_require();
    cid uuid;
BEGIN
    INSERT INTO mkt_campaigns (user_id, name) VALUES (uid, p_name) RETURNING id INTO cid;
    RETURN cid;
END
$$;

-- الخطة كاملةً بقيمها الجديدة: الخادم يدمج ما أُرسل بما في الصفّ.
CREATE FUNCTION ew_mkt_campaign_save(
    p_campaign uuid, p_expected_row_version integer, p_name text, p_brief text, p_goal text,
    p_kpi_metric text, p_kpi_target bigint, p_audience text, p_budget_halalas bigint,
    p_starts_on date, p_ends_on date
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_mkt_require();
    c   mkt_campaigns%ROWTYPE;
    rv  integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF c.status <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    UPDATE mkt_campaigns
       SET name = p_name, brief = p_brief, goal = p_goal, kpi_metric = p_kpi_metric, kpi_target = p_kpi_target,
           audience = p_audience, budget_halalas = p_budget_halalas, starts_on = p_starts_on, ends_on = p_ends_on
     WHERE id = p_campaign
    RETURNING row_version INTO rv;
    RETURN rv;
END
$$;

-- قنوات الخطة ومخصّصاتها، كلّها معاً. من واحدةٍ إلى ثمانٍ بلا تكرار.
CREATE FUNCTION ew_mkt_set_channels(
    p_campaign uuid, p_expected_row_version integer, p_channels text[], p_allocations bigint[]
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_mkt_require();
    c   mkt_campaigns%ROWTYPE;
    rv  integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF c.status <> 'PLANNING' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_is_fixed';
    END IF;
    IF p_channels IS NULL OR p_allocations IS NULL
       OR cardinality(p_channels) <> cardinality(p_allocations)
       OR cardinality(p_channels) NOT BETWEEN 1 AND 8
       OR (SELECT count(DISTINCT x) FROM unnest(p_channels) x) <> cardinality(p_channels)
       OR array_position(p_channels, NULL) IS NOT NULL OR array_position(p_allocations, NULL) IS NOT NULL THEN
        RAISE EXCEPTION 'shape' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channels_shape';
    END IF;
    IF (SELECT sum(a) FROM unnest(p_allocations) a) > c.budget_halalas THEN
        RAISE EXCEPTION 'budget' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_allocations_over_budget';
    END IF;
    DELETE FROM mkt_campaign_channels WHERE campaign_id = p_campaign AND NOT (channel = ANY (p_channels));
    INSERT INTO mkt_campaign_channels (campaign_id, user_id, channel, allocated_halalas)
    SELECT p_campaign, uid, t.ch, t.al FROM unnest(p_channels, p_allocations) AS t(ch, al)
    ON CONFLICT (campaign_id, channel) DO UPDATE SET allocated_halalas = EXCLUDED.allocated_halalas
     WHERE mkt_campaign_channels.allocated_halalas IS DISTINCT FROM EXCLUDED.allocated_halalas;
    UPDATE mkt_campaigns SET updated_at = now() WHERE id = p_campaign RETURNING row_version INTO rv;
    RETURN rv;
END
$$;

-- اعتماد الخطة، أو إعادتها إلى التخطيط، أو إلغاؤها. الاعتماد بإقرارٍ بكل تنبيهٍ قائم.
CREATE FUNCTION ew_mkt_campaign_transition(
    p_campaign uuid, p_expected_row_version integer, p_to text, p_acknowledged text[]
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    c    mkt_campaigns%ROWTYPE;
    keys text[];
    rv   integer;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, p_expected_row_version);
    IF p_to = 'APPROVED' AND c.status = 'PLANNING' THEN
        IF c.goal IS NULL OR c.starts_on IS NULL OR c.ends_on IS NULL
           OR NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = c.id) THEN
            RAISE EXCEPTION 'incomplete' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_plan_incomplete';
        END IF;
        keys := ARRAY(SELECT f.flag_key FROM ew_mkt_campaign_flags(c.id) f);
        IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
        END IF;
        UPDATE mkt_campaigns SET status = 'APPROVED', approved_with_flags = keys
         WHERE id = c.id RETURNING row_version INTO rv;
    ELSIF p_to = 'PLANNING' AND c.status = 'APPROVED' THEN
        UPDATE mkt_campaigns SET status = 'PLANNING' WHERE id = c.id RETURNING row_version INTO rv;
    ELSIF p_to = 'CANCELLED' AND c.status IN ('PLANNING', 'APPROVED') THEN
        UPDATE mkt_items SET status = 'CANCELLED' WHERE campaign_id = c.id AND status IN ('DRAFT', 'APPROVED');
        UPDATE mkt_campaigns SET status = 'CANCELLED' WHERE id = c.id RETURNING row_version INTO rv;
    ELSE
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_campaign_transition';
    END IF;
    RETURN rv;
END
$$;

-- منشورٌ جديد مسودةً. من إعلان منتجٍ جاهز: النصّ هو عنوانه ووصفه المعتمدان حرفاً بحرف.
CREATE FUNCTION ew_mkt_item_create(
    p_campaign uuid, p_channel text, p_publish_on date, p_publish_at time, p_body text,
    p_copy_warnings text[], p_planned_spend_halalas bigint, p_source_campaign uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_mkt_require();
    title text;
    descr text;
    iid   uuid;
BEGIN
    PERFORM 1 FROM mkt_campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = p_campaign AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    IF p_source_campaign IS NOT NULL THEN
        SELECT v.title, v.description INTO title, descr
          FROM campaigns a JOIN copy_versions v ON v.id = a.approved_version_id
         WHERE a.id = p_source_campaign AND a.user_id = uid AND a.status = 'READY';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'source' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_source_not_ready';
        END IF;
        IF p_body IS DISTINCT FROM title || E'\n' || descr THEN
            RAISE EXCEPTION 'source' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_source_body';
        END IF;
    END IF;
    INSERT INTO mkt_items (campaign_id, user_id, channel, publish_on, publish_at, body, copy_warnings,
                           planned_spend_halalas, source_campaign_id)
    VALUES (p_campaign, uid, p_channel, p_publish_on, p_publish_at, p_body, coalesce(p_copy_warnings, '{}'),
            p_planned_spend_halalas, p_source_campaign)
    RETURNING id INTO iid;
    RETURN iid;
END
$$;

-- المنشور كاملاً بقيمه الجديدة، والمسودة وحدها تُعدَّل.
CREATE FUNCTION ew_mkt_item_save(
    p_item uuid, p_expected_row_version integer, p_channel text, p_publish_on date, p_publish_at time,
    p_body text, p_copy_warnings text[], p_planned_spend_halalas bigint
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_mkt_require();
    i   mkt_items%ROWTYPE;
    rv  integer;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    -- الحملة أولاً ثم المنشور، بالترتيب نفسه في كل دالّة: لا قفل متقاطع.
    PERFORM 1 FROM mkt_campaigns WHERE id = i.campaign_id FOR SHARE;
    SELECT * INTO i FROM mkt_items WHERE id = p_item FOR UPDATE;
    IF i.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    IF i.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = i.campaign_id AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    UPDATE mkt_items
       SET channel = p_channel, publish_on = p_publish_on, publish_at = p_publish_at, body = p_body,
           copy_warnings = coalesce(p_copy_warnings, '{}'), planned_spend_halalas = p_planned_spend_halalas
     WHERE id = p_item
    RETURNING row_version INTO rv;
    RETURN rv;
END
$$;

-- اعتماد المنشور بإقرارٍ بكل تنبيهٍ قائم، أو إعادته مسودة، أو تسجيل نشره، أو إلغاؤه.
CREATE FUNCTION ew_mkt_item_transition(
    p_item uuid, p_expected_row_version integer, p_to text, p_acknowledged text[], p_published_at timestamptz
) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    i    mkt_items%ROWTYPE;
    keys text[];
    rv   integer;
BEGIN
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    PERFORM 1 FROM mkt_campaigns WHERE id = i.campaign_id FOR SHARE;
    SELECT * INTO i FROM mkt_items WHERE id = p_item FOR UPDATE;
    IF i.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
    END IF;
    IF p_to = 'APPROVED' AND i.status = 'DRAFT' THEN
        keys := ARRAY(SELECT f.flag_key FROM ew_mkt_item_flags(p_item) f);
        IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
        END IF;
        UPDATE mkt_items SET status = 'APPROVED', approved_with_flags = keys
         WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'DRAFT' AND i.status = 'APPROVED' THEN
        UPDATE mkt_items SET status = 'DRAFT' WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'PUBLISHED' AND i.status = 'APPROVED' THEN
        UPDATE mkt_items SET status = 'PUBLISHED', published_at = coalesce(p_published_at, now())
         WHERE id = p_item RETURNING row_version INTO rv;
    ELSIF p_to = 'CANCELLED' AND i.status IN ('DRAFT', 'APPROVED') THEN
        UPDATE mkt_items SET status = 'CANCELLED' WHERE id = p_item RETURNING row_version INTO rv;
    ELSE
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_transition';
    END IF;
    RETURN rv;
END
$$;

-- إدخال نتائج قناةٍ لفترة، أو تصحيحه، بإقرارٍ بتنبيهات الإنفاق القائمة لحظتها.
CREATE FUNCTION ew_mkt_results_save(
    p_campaign uuid, p_channel text, p_result uuid, p_expected_row_version integer,
    p_period_start date, p_period_end date, p_spend_halalas bigint, p_impressions bigint, p_clicks bigint,
    p_leads bigint, p_orders bigint, p_revenue_halalas bigint, p_acknowledged text[]
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    c    mkt_campaigns%ROWTYPE;
    r    mkt_results%ROWTYPE;
    keys text[];
    rid  uuid;
BEGIN
    c := ew_mkt_lock_campaign(uid, p_campaign, NULL);
    IF c.status <> 'APPROVED' THEN
        RAISE EXCEPTION 'plan' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_results_need_approved_plan';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mkt_campaign_channels WHERE campaign_id = c.id AND channel = p_channel) THEN
        RAISE EXCEPTION 'channel' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_channel_not_in_plan';
    END IF;
    IF p_result IS NOT NULL THEN
        SELECT * INTO r FROM mkt_results WHERE id = p_result AND campaign_id = c.id AND user_id = uid FOR UPDATE;
        IF NOT FOUND OR r.channel <> p_channel THEN
            RAISE EXCEPTION 'result' USING ERRCODE = 'no_data_found';
        END IF;
        IF r.row_version <> p_expected_row_version THEN
            RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_stale';
        END IF;
    END IF;
    keys := ARRAY(SELECT f.flag_key FROM ew_mkt_results_flags(c.id, p_channel, p_result, p_spend_halalas) f);
    IF NOT ew_mkt_same_keys(keys, p_acknowledged) THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_flags_changed';
    END IF;
    IF p_result IS NULL THEN
        INSERT INTO mkt_results (campaign_id, user_id, channel, period_start, period_end, spend_halalas, impressions,
                                 clicks, leads, orders, revenue_halalas, acknowledged_flags)
        VALUES (c.id, uid, p_channel, p_period_start, p_period_end, p_spend_halalas, p_impressions, p_clicks,
                p_leads, p_orders, p_revenue_halalas, keys)
        RETURNING id INTO rid;
    ELSE
        UPDATE mkt_results
           SET period_start = p_period_start, period_end = p_period_end, spend_halalas = p_spend_halalas,
               impressions = p_impressions, clicks = p_clicks, leads = p_leads, orders = p_orders,
               revenue_halalas = p_revenue_halalas, acknowledged_flags = keys
         WHERE id = p_result
        RETURNING id INTO rid;
    END IF;
    RETURN rid;
END
$$;

-- ── سقوف مراجعة سيمبول ──────────────────────────────────────────────────
-- ما ربما فُوتر في آخر يوم من كل استدعاءات النموذج، ومن آثار ما حُذف. p_new_only: ما بدأه
-- حسابٌ مفتوحٌ جديد وحده. الدالّة الوحيدة التي تجمع دفاتر الذكاء الاصطناعي: كل ترحيلٍ
-- يضيف دفتراً يعيد كتابتها بجمعه (اختبارٌ يعدّ كل جدولٍ فيه started_at وoutcome وnew_account).
CREATE OR REPLACE FUNCTION ew_ai_spend(p_new_only boolean) RETURNS bigint
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    SELECT (SELECT count(*) FROM generation_attempts
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM mkt_review_calls
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
         + (SELECT count(*) FROM attempt_tombstones
             WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
               AND (new_account OR NOT p_new_only))
$$;

-- يفتح استدعاءً لمراجعة نصّ مسودةٍ بعد كل السقوف، أو يُرجع NULL إن رُوجع هذا النصّ نفسه.
CREATE FUNCTION ew_mkt_review_begin(p_item uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid   uuid := ew_mkt_require();
    i     mkt_items%ROWTYPE;
    fresh boolean;
    call  uuid;
BEGIN
    -- قفلٌ لكل مستخدم: الفحص والإدراج ذرّيان، وطلبان متزامنان لا يمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.mkt.review.' || uid::text, 0));
    SELECT * INTO i FROM mkt_items WHERE id = p_item AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'item' USING ERRCODE = 'no_data_found';
    END IF;
    IF i.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'fixed' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_item_is_fixed';
    END IF;
    IF i.ai_reviewed_digest = i.body_digest THEN
        RETURN NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM mkt_review_calls
                WHERE user_id = uid AND finished_at IS NULL AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_in_progress';
    END IF;
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_rate';
    END IF;
    fresh := ew_new_open_account(uid);
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE user_id = uid AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN 10 ELSE 30 END) THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation',
            CONSTRAINT = CASE WHEN fresh THEN 'mkt_review_new_account_cap' ELSE 'mkt_review_daily_cap' END;
    END IF;
    -- القفل العام نفسه الذي يأخذه ew_begin_generation: السقف واحدٌ للأدوات كلها.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM mkt_review_calls
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 600 THEN
        RAISE EXCEPTION 'app' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_app_cap';
    END IF;
    IF ew_ai_spend(false) >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    INSERT INTO mkt_review_calls (user_id, item_id, body_digest, new_account)
    VALUES (uid, i.id, i.body_digest, fresh)
    RETURNING id INTO call;
    RETURN call;
END
$$;

-- يكتب تنبيهات سيمبول للنصّ الذي أُرسل، إن لم يتغيّر منذئذٍ، ويُغلق الاستدعاء OK؛ وإلا
-- يُغلقه DISCARDED ويُرجع false. كل اقتباسٍ من النصّ نفسه.
CREATE FUNCTION ew_mkt_review_record(
    p_call uuid, p_kinds text[], p_quotes text[], p_reasons text[], p_input_tokens integer,
    p_output_tokens integer, p_served_model text, p_prompt_version text, p_request_id text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_mkt_require();
    call mkt_review_calls%ROWTYPE;
    i    mkt_items%ROWTYPE;
BEGIN
    SELECT * INTO call FROM mkt_review_calls WHERE id = p_call AND user_id = uid AND finished_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_kinds IS NULL OR p_quotes IS NULL OR p_reasons IS NULL
       OR cardinality(p_kinds) <> cardinality(p_quotes) OR cardinality(p_kinds) <> cardinality(p_reasons)
       OR cardinality(p_kinds) > 5 THEN
        RAISE EXCEPTION 'shape' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_shape';
    END IF;
    SELECT * INTO i FROM mkt_items WHERE id = call.item_id AND user_id = uid FOR UPDATE;
    IF NOT FOUND OR i.status <> 'DRAFT' OR i.body_digest <> call.body_digest THEN
        UPDATE mkt_review_calls
           SET finished_at = now(), outcome = 'DISCARDED', input_tokens = p_input_tokens,
               output_tokens = p_output_tokens, served_model = p_served_model, prompt_version = p_prompt_version,
               api_request_id = p_request_id
         WHERE id = p_call;
        RETURN false;
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_quotes) q WHERE q IS NULL OR strpos(i.body, q) = 0) THEN
        RAISE EXCEPTION 'quote' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_quote';
    END IF;
    DELETE FROM mkt_ai_flags WHERE item_id = i.id;
    INSERT INTO mkt_ai_flags (item_id, user_id, body_digest, ordinal, kind, quote, reason)
    SELECT i.id, uid, i.body_digest, t.n, t.k, t.q, t.r
      FROM unnest(p_kinds, p_quotes, p_reasons) WITH ORDINALITY AS t(k, q, r, n);
    UPDATE mkt_items SET ai_reviewed_digest = body_digest WHERE id = i.id;
    UPDATE mkt_review_calls
       SET finished_at = now(), outcome = 'OK', input_tokens = p_input_tokens, output_tokens = p_output_tokens,
           served_model = p_served_model, prompt_version = p_prompt_version, api_request_id = p_request_id
     WHERE id = p_call;
    RETURN true;
END
$$;

-- يُغلق استدعاءً لم يُكتب منه شيء، بنتيجته.
CREATE FUNCTION ew_mkt_review_finish(
    p_call uuid, p_outcome text, p_input_tokens integer, p_output_tokens integer,
    p_served_model text, p_request_id text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    IF p_outcome IS NULL OR p_outcome NOT IN ('REFUSED', 'OUTPUT_INVALID', 'UPSTREAM_BUSY', 'UPSTREAM_UNREACHABLE',
                                              'UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR') THEN
        RAISE EXCEPTION 'outcome' USING ERRCODE = 'check_violation', CONSTRAINT = 'mkt_review_outcome';
    END IF;
    UPDATE mkt_review_calls
       SET finished_at = now(), outcome = p_outcome, input_tokens = p_input_tokens, output_tokens = p_output_tokens,
           served_model = p_served_model, api_request_id = p_request_id
     WHERE id = p_call AND user_id = uid AND finished_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'no_data_found';
    END IF;
END
$$;

-- ── حملة المنتج: السقف العام يعدّ المراجعات أيضاً ────────────────────────
-- نصّ NEXT_open_registration نفسه، والسطران المعلَّمان «★» وحدهما يتغيّران: السقف العام
-- وحصّة الحسابات الجديدة من ew_ai_spend.
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
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF ew_ai_spend(false) >= 2000 THEN  -- ★
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF fresh AND ew_ai_spend(true) >= 400 THEN  -- ★
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

-- ── العزل بالصفّ: ENABLE + FORCE ─────────────────────────────────────────
ALTER TABLE mkt_campaigns         ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_campaigns         FORCE  ROW LEVEL SECURITY;
ALTER TABLE mkt_campaign_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_campaign_channels FORCE  ROW LEVEL SECURITY;
ALTER TABLE mkt_items             ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_items             FORCE  ROW LEVEL SECURITY;
ALTER TABLE mkt_results           ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_results           FORCE  ROW LEVEL SECURITY;
ALTER TABLE mkt_review_calls      ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_review_calls      FORCE  ROW LEVEL SECURITY;
ALTER TABLE mkt_ai_flags          ENABLE ROW LEVEL SECURITY;
ALTER TABLE mkt_ai_flags          FORCE  ROW LEVEL SECURITY;

-- دور الويب يقرأ صفوف صاحب الجلسة وحده، ولا سياسة كتابةٍ له: يكتب عبر الدوالّ.
CREATE POLICY mkt_campaigns_own ON mkt_campaigns         FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY mkt_channels_own  ON mkt_campaign_channels FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY mkt_items_own     ON mkt_items             FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY mkt_results_own   ON mkt_results           FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY mkt_reviews_own   ON mkt_review_calls      FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY mkt_ai_flags_own  ON mkt_ai_flags          FOR SELECT TO eyework_app USING (user_id = ew_current_user());

CREATE POLICY mkt_campaigns_owner_access ON mkt_campaigns         FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY mkt_channels_owner_access  ON mkt_campaign_channels FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY mkt_items_owner_access     ON mkt_items             FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY mkt_results_owner_access   ON mkt_results           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY mkt_reviews_owner_access   ON mkt_review_calls      FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY mkt_ai_flags_owner_access  ON mkt_ai_flags          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- ── المنح: قراءةٌ للجداول، وتنفيذٌ للدوالّ العامة وحدها ───────────────────
GRANT SELECT ON mkt_campaign_transition, mkt_item_transition TO eyework_app;
GRANT SELECT ON mkt_campaigns, mkt_campaign_channels, mkt_items, mkt_results, mkt_review_calls, mkt_ai_flags
    TO eyework_app;

REVOKE ALL ON FUNCTION
    ew_mkt_text_ok(text, boolean), ew_mkt_channel_known(text), ew_mkt_kpi_fits(text, text),
    ew_mkt_same_keys(text[], text[]),
    ew_mkt_review_tombstone(), ew_mkt_campaign_insert_guard(), ew_mkt_campaign_guard(), ew_mkt_channel_guard(),
    ew_mkt_allocations_check(), ew_mkt_item_insert_guard(), ew_mkt_item_guard(), ew_mkt_results_guard(),
    ew_mkt_item_flags(uuid), ew_mkt_campaign_flags(uuid), ew_mkt_results_flags(uuid, text, uuid, bigint),
    ew_mkt_require(), ew_mkt_lock_campaign(uuid, uuid, integer),
    ew_mkt_campaign_create(text),
    ew_mkt_campaign_save(uuid, integer, text, text, text, text, bigint, text, bigint, date, date),
    ew_mkt_set_channels(uuid, integer, text[], bigint[]),
    ew_mkt_campaign_transition(uuid, integer, text, text[]),
    ew_mkt_item_create(uuid, text, date, time, text, text[], bigint, uuid),
    ew_mkt_item_save(uuid, integer, text, date, time, text, text[], bigint),
    ew_mkt_item_transition(uuid, integer, text, text[], timestamptz),
    ew_mkt_results_save(uuid, text, uuid, integer, date, date, bigint, bigint, bigint, bigint, bigint, bigint, text[]),
    ew_ai_spend(boolean),
    ew_mkt_review_begin(uuid),
    ew_mkt_review_record(uuid, text[], text[], text[], integer, integer, text, text, text),
    ew_mkt_review_finish(uuid, text, integer, integer, text, text)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
    ew_mkt_item_flags(uuid), ew_mkt_campaign_flags(uuid), ew_mkt_results_flags(uuid, text, uuid, bigint),
    ew_mkt_campaign_create(text),
    ew_mkt_campaign_save(uuid, integer, text, text, text, text, bigint, text, bigint, date, date),
    ew_mkt_set_channels(uuid, integer, text[], bigint[]),
    ew_mkt_campaign_transition(uuid, integer, text, text[]),
    ew_mkt_item_create(uuid, text, date, time, text, text[], bigint, uuid),
    ew_mkt_item_save(uuid, integer, text, date, time, text, text[], bigint),
    ew_mkt_item_transition(uuid, integer, text, text[], timestamptz),
    ew_mkt_results_save(uuid, text, uuid, integer, date, date, bigint, bigint, bigint, bigint, bigint, bigint, text[]),
    ew_mkt_review_begin(uuid),
    ew_mkt_review_record(uuid, text[], text[], text[], integer, integer, text, text, text),
    ew_mkt_review_finish(uuid, text, integer, integer, text, text)
TO eyework_app;
