-- ════════════════════════════════════════════════════════════════════════
-- 0011_support_desk — مكتب الدعم الفني: التذاكر، والمسودات، وقاعدة المعرفة، والقرارات
-- ════════════════════════════════════════════════════════════════════════
-- ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو النموذج، فيُفرض هنا:
--
--   • المكتب لحساب الدعم الفني وحده، وكل صفٍّ لصاحبه: RLS مفروضة على المالك
--     أيضاً (FORCE)، ودور الويب يقرأ صفوفه ولا يكتب أيّ جدولٍ مباشرة. كل كتابةٍ
--     دالّةٌ تقرأ صاحب الجلسة من ew_current_user() وتسجّل القرار في سجلٍّ لا يُعدَّل.
--   • لا شيء يصل العميل إلا بضغطة الموظف: الردّ يُجهَّز، ثم يُنسخ أو يُشارك، ثم
--     يؤكّد الموظف أنه أرسله. المسودة وحدها لا تغيّر حالة التذكرة.
--   • المسودة التي «تجيب» (ANSWER) لا تُحفظ بلا اقتباسٍ حرفيٍّ من النسخة المنشورة
--     لمقالةٍ في قاعدة معرفة صاحبها.
--   • الأولوية المقترحة يحسبها المحفّز من الأثر والإلحاح، لا يكتبها النموذج.
--   • رسالة العميل والملاحظة الداخلية لا تُخزَّنان ببريدٍ أو سلسلة أرقامٍ طويلة
--     (هاتف، هوية، بطاقة، آيبان)؛ ولا ردٌّ ولا مقالةٌ برقم هويةٍ أو بطاقةٍ أو آيبان.
--   • كل استدعاءٍ لسيمبول (المسودة، ومراجعة الردّ، واقتراح المقالة ومراجعتها) صفٌّ في
--     الدفتر الواحد (0009: ai_requests) بسقوف ميزته في ai_features. وتنبيهاته في ai_flags
--     بقرار صاحبها، وبوّابتها ew_ai_gate عند إطلاق الردّ ونشر المقالة. وتنبيهات القواعد هنا
--     في support_flags بإقرارها.
-- ════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF to_regprocedure('ew_ai_request_open(text, text, uuid, bytea)') IS NULL
       OR (SELECT count(*) FROM ai_features WHERE profession = 'SUPPORT') <> 4 THEN
        RAISE EXCEPTION 'مكتب الدعم يحتاج طبقة الذكاء 0009_ai_layer قبله.';
    END IF;
END
$$;

-- ── المجالات ────────────────────────────────────────────────────────────
-- نصٌّ بلا محارف تحكّمٍ ولا محارف اتجاهٍ خفية ولا مسافاتٍ في طرفيه؛ والسطر الواحد بلا فاصل.
CREATE FUNCTION ew_support_text_ok(t text, p_multiline boolean) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT t = btrim(t, E' \n')
       AND t !~ '[\x01-\x09\x0B-\x1F\x7F]'
       AND (p_multiline OR strpos(t, E'\n') = 0)
       AND t !~ '[‎‏‪-‮⁦-⁩]'
$$;

-- ما يكتبه الموظف أو يلصقه من كلام العميل: بلا بريدٍ ولا رابطٍ (بمخطّطه، أو اسم موقعٍ يتبعه مسار) ولا
-- تسعة أرقامٍ فأكثر، بينها حتى ثلاثةٌ من المسافات (كلّها عدا السطر) والشَّرطات والأقواس، أو بنقاطٍ بين
-- مجموعاتٍ من رقمين فأكثر. يحذفها الخادم قبل الحفظ، وهذا الحاجز الثاني: نظير support_rules.contact_free
-- حرفاً بحرف (اختبارٌ يقارنهما).
CREATE FUNCTION ew_support_contact_free(t text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT t !~ '[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+'
       AND t !~* '(?<![a-z0-9])(https?://|www\.)[^[:space:]]'
       AND t !~* '(?<![a-z0-9@.-])([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}[/?#]'
       AND t !~ '([0-9٠-٩۰-۹０-９][ \u00a0\u1680\u2000-\u200b\u202f\u205f\u3000()\u2010-\u2015\u2212\uff0d-]{0,3}){8}[0-9٠-٩۰-۹０-９]'
       AND NOT EXISTS (
           SELECT 1 FROM regexp_matches(t, '(?<![0-9٠-٩۰-۹０-９.])[0-9٠-٩۰-۹０-９]{2,}(?:\.[0-9٠-٩۰-۹０-９]{2,})+(?![0-9٠-٩۰-۹０-９.])', 'g') AS m(x)
            WHERE length(regexp_replace(m.x[1], '[^0-9٠-٩۰-۹０-９]', '', 'g')) >= 9)
$$;

-- ما يُرسَل أو يُنشر (الردّ والمقالة): قد يحمل هاتف جهة العمل أو بريدها، ولا يحمل
-- رقم هويةٍ أو إقامة (عشرة أرقام تبدأ بـ1 أو 2)، ولا بطاقةً أو آيبان (13 رقماً فأكثر).
CREATE FUNCTION ew_support_kb_clean(t text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT t !~ '(^|[^0-9٠-٩])[12١٢][0-9٠-٩]{9}([^0-9٠-٩]|$)'
       AND t !~ '([0-9٠-٩][ -]?){12}[0-9٠-٩]'
       AND t !~* 'SA[0-9]{2} ?[0-9]{4}'
$$;

-- صورةٌ موحّدة للنصّ يُقارَن بها الاقتباس: NFKC، وحروفٌ صغيرة، بلا تشكيلٍ ولا تطويل،
-- والمسافات واحدة. نظيرها grounding.kb_norm في الخادم (اختبارٌ يقارنهما).
CREATE FUNCTION ew_kb_norm(t text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT btrim(regexp_replace(
               regexp_replace(lower(normalize(t, NFKC)), '[ً-ٰٟـ]', '', 'g'),
               '[[:space:]]+', ' ', 'g'))
$$;

-- مصفوفة الأثر والإلحاح، نظير support_rules.PRIORITY_MATRIX. المقترح يحسبه المحفّز منها.
CREATE FUNCTION ew_support_priority_for(p_impact text, p_urgency text, p_security boolean) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT CASE
        WHEN p_impact = 'WIDESPREAD' AND p_urgency = 'STOPPED' THEN 'URGENT'
        WHEN p_security OR p_urgency = 'STOPPED'
             OR (p_impact = 'WIDESPREAD' AND p_urgency = 'DEGRADED') THEN 'HIGH'
        WHEN p_urgency = 'DEGRADED' OR p_impact = 'WIDESPREAD' THEN 'NORMAL'
        ELSE 'LOW'
    END
$$;

CREATE FUNCTION ew_support_priority_rank(p text) RETURNS integer
LANGUAGE sql IMMUTABLE SET search_path = public, pg_temp AS $$
    SELECT CASE p WHEN 'URGENT' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'NORMAL' THEN 2 WHEN 'LOW' THEN 1 END
$$;

-- ── الإعداد لكل حساب ────────────────────────────────────────────────────
CREATE TABLE support_settings (
    user_id             uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    -- توقيع الردّ كما يكتبه الموظف («فريق الدعم الفني»). فارغٌ: لا توقيع.
    signature           text CONSTRAINT support_signature_shape CHECK (signature IS NULL OR (
                            char_length(signature) BETWEEN 2 AND 60 AND ew_support_text_ok(signature, false)
                            AND ew_support_contact_free(signature))),
    -- نسخة إشعار المكتب التي قرأها ووافق عليها. لا استدعاء للنموذج بدونها.
    notice_version      text CONSTRAINT support_notice_version_shape
                            CHECK (notice_version IS NULL OR notice_version ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
    notice_accepted_at  timestamptz,
    next_ticket_number  integer NOT NULL DEFAULT 1 CHECK (next_ticket_number >= 1),
    next_article_number integer NOT NULL DEFAULT 1 CHECK (next_article_number >= 1),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT support_notice_complete CHECK ((notice_version IS NULL) = (notice_accepted_at IS NULL))
);

-- أهداف زمن الخدمة لكل أولوية، بالدقائق التقويمية، من قيمٍ جاهزة.
CREATE TABLE support_sla_targets (
    user_id             uuid NOT NULL REFERENCES support_settings (user_id) ON DELETE CASCADE,
    priority            text NOT NULL CONSTRAINT support_sla_priority
                            CHECK (priority IN ('URGENT', 'HIGH', 'NORMAL', 'LOW')),
    first_reply_minutes integer NOT NULL CONSTRAINT support_sla_first
                            CHECK (first_reply_minutes IN (30, 60, 120, 240, 480, 1440)),
    resolve_minutes     integer NOT NULL CONSTRAINT support_sla_resolve
                            CHECK (resolve_minutes IN (240, 480, 1440, 2880, 4320, 7200)),
    PRIMARY KEY (user_id, priority),
    CONSTRAINT support_sla_order CHECK (first_reply_minutes < resolve_minutes)
);

-- ── آلة حالات التذكرة ───────────────────────────────────────────────────
-- نظير eyework/support_rules.py TRANSITIONS؛ اختبارٌ يقارنهما.
CREATE TABLE support_ticket_transition (
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (from_status, to_status)
);
INSERT INTO support_ticket_transition (from_status, to_status) VALUES
    ('NEW',       'OPEN'),     ('NEW',       'PENDING'),  ('NEW',       'ESCALATED'),
    ('NEW',       'RESOLVED'), ('NEW',       'CLOSED'),
    ('OPEN',      'PENDING'),  ('OPEN',      'ESCALATED'), ('OPEN',     'RESOLVED'),
    ('OPEN',      'CLOSED'),
    ('PENDING',   'OPEN'),     ('PENDING',   'ESCALATED'), ('PENDING',  'RESOLVED'),
    ('PENDING',   'CLOSED'),
    ('ESCALATED', 'OPEN'),     ('ESCALATED', 'CLOSED'),
    ('RESOLVED',  'OPEN'),     ('RESOLVED',  'PENDING'),  ('RESOLVED',  'CLOSED');

-- ── التذاكر ─────────────────────────────────────────────────────────────
CREATE TABLE support_tickets (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- رقم التذكرة لدى صاحبها (#12). يكتبه المحفّز.
    number             integer NOT NULL DEFAULT 0,
    status             text NOT NULL DEFAULT 'NEW' CONSTRAINT support_ticket_status
                           CHECK (status IN ('NEW', 'OPEN', 'PENDING', 'ESCALATED', 'RESOLVED', 'CLOSED')),
    priority           text NOT NULL DEFAULT 'NORMAL' CONSTRAINT support_ticket_priority
                           CHECK (priority IN ('URGENT', 'HIGH', 'NORMAL', 'LOW')),
    category           text CONSTRAINT support_ticket_category CHECK (category IS NULL OR category IN
                           ('ACCOUNT', 'SOFTWARE', 'HARDWARE', 'PRINTING', 'NETWORK', 'EMAIL', 'INSTALL',
                            'HOW_TO', 'OTHER')),
    -- من أين جاءت الرسالة. الردّ يُرسل من القناة نفسها، خارج التطبيق.
    channel            text NOT NULL CONSTRAINT support_ticket_channel
                           CHECK (channel IN ('MESSAGING', 'EMAIL', 'PHONE', 'IN_PERSON', 'WEB_FORM', 'OTHER')),
    -- ما يعرف به الموظف العميل في الطابور وفي التحية. لا يصل النموذج أبداً.
    customer_label     text CONSTRAINT support_customer_label_shape CHECK (customer_label IS NULL OR (
                           char_length(customer_label) BETWEEN 1 AND 30
                           AND customer_label ~ '^[ء-غف-يa-zA-Z0-9٠-٩]+( [ء-غف-يa-zA-Z0-9٠-٩]+)*$'
                           AND ew_support_contact_free(customer_label))),
    subject            text CONSTRAINT support_subject_shape CHECK (subject IS NULL OR (
                           char_length(subject) BETWEEN 3 AND 80 AND ew_support_text_ok(subject, false)
                           AND ew_support_contact_free(subject))),
    follow_up_of       uuid,
    escalation_target  text CONSTRAINT support_escalation_target CHECK (escalation_target IS NULL OR
                           escalation_target IN ('TIER2', 'SUPERVISOR', 'VENDOR', 'FIELD_TECH', 'OTHER_TEAM')),
    resolution         text CONSTRAINT support_resolution CHECK (resolution IS NULL OR resolution IN
                           ('REPLIED', 'BY_PHONE', 'IN_PERSON', 'DUPLICATE', 'NOT_SUPPORT', 'NO_RESPONSE')),
    close_reason       text CONSTRAINT support_close_reason CHECK (close_reason IS NULL OR close_reason IN
                           ('AFTER_RESOLVED', 'IDLE', 'PROFESSION_CHANGED')),
    row_version        integer NOT NULL DEFAULT 1,
    client_token       uuid NOT NULL,
    -- زمن الخدمة: موعد أول ردّ، وزمن انتظار العميل (يتوقّف في PENDING وما بعد الحلّ).
    first_reply_due_at timestamptz NOT NULL DEFAULT now(),
    first_replied_at   timestamptz,
    resolve_minutes    integer NOT NULL DEFAULT 0,
    wait_seconds       integer NOT NULL DEFAULT 0 CHECK (wait_seconds >= 0),
    clock_since        timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    last_activity_at   timestamptz NOT NULL DEFAULT now(),
    resolved_at        timestamptz,
    closed_at          timestamptz,
    texts_purged_at    timestamptz,
    UNIQUE (user_id, number),
    UNIQUE (user_id, client_token),
    UNIQUE (id, user_id),
    FOREIGN KEY (follow_up_of, user_id) REFERENCES support_tickets (id, user_id) ON DELETE SET NULL (follow_up_of),
    CONSTRAINT support_ticket_number CHECK (number >= 1),
    CONSTRAINT support_clock_runs CHECK ((status IN ('NEW', 'OPEN', 'ESCALATED')) = (clock_since IS NOT NULL)),
    CONSTRAINT support_escalated_has_target CHECK ((status = 'ESCALATED') = (escalation_target IS NOT NULL)),
    CONSTRAINT support_resolved_complete
        CHECK (status <> 'RESOLVED' OR (resolved_at IS NOT NULL AND resolution IS NOT NULL)),
    CONSTRAINT support_unresolved_clear
        CHECK (status IN ('RESOLVED', 'CLOSED') OR (resolved_at IS NULL AND resolution IS NULL)),
    CONSTRAINT support_closed_iff_time
        CHECK ((status = 'CLOSED') = (closed_at IS NOT NULL) AND (status = 'CLOSED') = (close_reason IS NOT NULL)),
    CONSTRAINT support_purge_after_close CHECK (texts_purged_at IS NULL OR status = 'CLOSED')
);
CREATE INDEX support_tickets_queue    ON support_tickets (user_id, status, first_reply_due_at);
CREATE INDEX support_tickets_recent   ON support_tickets (user_id, updated_at DESC);
CREATE INDEX support_tickets_resolved ON support_tickets (resolved_at) WHERE status = 'RESOLVED';
CREATE INDEX support_tickets_idle     ON support_tickets (last_activity_at) WHERE status <> 'CLOSED';
CREATE INDEX support_tickets_closed   ON support_tickets (closed_at) WHERE status = 'CLOSED';

-- ── المحادثة ────────────────────────────────────────────────────────────
-- CUSTOMER: ما ألصقه الموظف من رسالة العميل بعد الحذف. NOTE: ملاحظةٌ داخلية لا تصل العميل.
-- AGENT: ردٌّ أكّد الموظف إرساله، يكتبه ew_support_confirm_reply وحده.
CREATE TABLE support_messages (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id    uuid NOT NULL,
    user_id      uuid NOT NULL,
    author       text NOT NULL CONSTRAINT support_message_author CHECK (author IN ('CUSTOMER', 'AGENT', 'NOTE')),
    body         text NOT NULL CONSTRAINT support_message_body
                     CHECK (char_length(body) BETWEEN 1 AND 4000 AND ew_support_text_ok(body, true)),
    reply_id     uuid UNIQUE,
    -- كم موضعاً حذفه الخادم (بريد، رقم، رابط) قبل الحفظ.
    masked_count smallint NOT NULL DEFAULT 0 CHECK (masked_count BETWEEN 0 AND 500),
    client_token uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    UNIQUE (ticket_id, id),
    UNIQUE (user_id, client_token),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT support_message_agent_reply CHECK ((author = 'AGENT') = (reply_id IS NOT NULL)),
    CONSTRAINT support_message_agent_token CHECK ((author = 'AGENT') = (client_token IS NULL)),
    CONSTRAINT support_message_contact_free CHECK (author = 'AGENT' OR ew_support_contact_free(body))
);
CREATE INDEX support_messages_ticket ON support_messages (ticket_id, created_at);
CREATE INDEX support_messages_user_time ON support_messages (user_id, created_at DESC) WHERE author <> 'AGENT';

-- ── قاعدة المعرفة ───────────────────────────────────────────────────────
-- DRAFT: كتبه الموظف ولم يعتمده.
-- PUBLISHED: اعتمده الموظف؛ النسخة المنشورة وحدها يراها المساعد. ARCHIVED وDISCARDED: خارجها.
CREATE TABLE kb_articles (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    number              integer NOT NULL DEFAULT 0,
    state               text NOT NULL DEFAULT 'DRAFT' CONSTRAINT kb_article_state
                            CHECK (state IN ('DRAFT', 'PUBLISHED', 'ARCHIVED', 'DISCARDED')),
    published_version   smallint,
    latest_version      smallint NOT NULL DEFAULT 0,
    -- «علّمها أو أصلحها»: مقالةٌ منشورة يشكّ الموظف في صحّتها.
    needs_review        boolean NOT NULL DEFAULT false,
    needs_review_reason text CONSTRAINT kb_review_reason CHECK (needs_review_reason IS NULL OR
                            needs_review_reason IN ('DRAFT_WRONG_INFO', 'DRAFT_OUTDATED', 'EMPLOYEE')),
    -- كم ردّاً أُرسل وهو يقتبس منها. يكتبه ew_support_confirm_reply.
    reuse_count         integer NOT NULL DEFAULT 0 CHECK (reuse_count >= 0),
    source_ticket_id    uuid,
    client_token        uuid,
    row_version         integer NOT NULL DEFAULT 1,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    published_at        timestamptz,
    archived_at         timestamptz,
    discarded_at        timestamptz,
    UNIQUE (user_id, number),
    UNIQUE (id, user_id),
    UNIQUE (user_id, client_token),
    FOREIGN KEY (source_ticket_id, user_id) REFERENCES support_tickets (id, user_id)
        ON DELETE SET NULL (source_ticket_id),
    CONSTRAINT kb_article_number CHECK (number >= 1),
    CONSTRAINT kb_published_has_version CHECK ((state = 'PUBLISHED') = (published_version IS NOT NULL)),
    CONSTRAINT kb_version_bound CHECK (published_version IS NULL OR published_version <= latest_version),
    CONSTRAINT kb_review_iff_reason CHECK (needs_review = (needs_review_reason IS NOT NULL)),
    CONSTRAINT kb_review_only_published CHECK (NOT needs_review OR state = 'PUBLISHED'),
    CONSTRAINT kb_archived_time CHECK ((state = 'ARCHIVED') = (archived_at IS NOT NULL)),
    CONSTRAINT kb_discarded_time CHECK ((state = 'DISCARDED') = (discarded_at IS NOT NULL)),
    CONSTRAINT kb_ever_published CHECK ((state IN ('PUBLISHED', 'ARCHIVED')) = (published_at IS NOT NULL))
);
CREATE INDEX kb_articles_user_state ON kb_articles (user_id, state, updated_at DESC);

-- نسخ المقالة لا تُعدَّل بعد كتابتها. بنية KCS: المشكلة بكلام العميل، والبيئة، والحلّ، والسبب.
CREATE TABLE kb_versions (
    article_id  uuid NOT NULL,
    version     smallint NOT NULL DEFAULT 0 CONSTRAINT kb_version_cap CHECK (version BETWEEN 1 AND 30),
    user_id     uuid NOT NULL,
    title       text NOT NULL CHECK (char_length(title) BETWEEN 4 AND 80 AND ew_support_text_ok(title, false)),
    issue       text NOT NULL CHECK (char_length(issue) BETWEEN 10 AND 400 AND ew_support_text_ok(issue, true)),
    environment text CHECK (environment IS NULL OR
                            (char_length(environment) BETWEEN 3 AND 300 AND ew_support_text_ok(environment, true))),
    resolution  text NOT NULL CHECK (char_length(resolution) BETWEEN 20 AND 4000
                                     AND ew_support_text_ok(resolution, true)),
    cause       text CHECK (cause IS NULL OR (char_length(cause) BETWEEN 3 AND 400 AND ew_support_text_ok(cause, true))),
    created_at  timestamptz NOT NULL DEFAULT now(),
    search      tsvector GENERATED ALWAYS AS (
                    setweight(to_tsvector('arabic'::regconfig, title), 'A')
                    || setweight(to_tsvector('arabic'::regconfig, issue), 'B')
                    || setweight(to_tsvector('arabic'::regconfig, resolution), 'C')) STORED,
    PRIMARY KEY (article_id, version),
    FOREIGN KEY (article_id, user_id) REFERENCES kb_articles (id, user_id) ON DELETE CASCADE,
    CONSTRAINT kb_version_clean CHECK (ew_support_kb_clean(
        title || ' ' || issue || ' ' || coalesce(environment, '') || ' ' || resolution || ' ' || coalesce(cause, '')))
);
CREATE INDEX kb_versions_search ON kb_versions USING gin (search);

-- ── المسودات ────────────────────────────────────────────────────────────
CREATE TABLE support_drafts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           uuid NOT NULL,
    user_id             uuid NOT NULL,
    call_id             uuid UNIQUE REFERENCES ai_requests (id) ON DELETE SET NULL,
    based_on_message_id uuid NOT NULL,
    seq                 smallint NOT NULL DEFAULT 0,
    -- DRAFT: مسودةٌ تصلح للإرسال. CANNOT_ANSWER: قاعدة المعرفة لا تجيب، وقد تحمل ردّاً
    -- يطلب معلوماتٍ أو يُفيد بالمتابعة. NOT_SUPPORT: الرسالة ليست طلب دعم.
    result              text NOT NULL CONSTRAINT support_draft_result
                            CHECK (result IN ('DRAFT', 'CANNOT_ANSWER', 'NOT_SUPPORT')),
    reply_kind          text CONSTRAINT support_draft_kind
                            CHECK (reply_kind IS NULL OR reply_kind IN ('ANSWER', 'ASK_INFO', 'UPDATE')),
    body                text CONSTRAINT support_draft_body CHECK (body IS NULL OR (
                            char_length(body) BETWEEN 20 AND 1200 AND ew_support_text_ok(body, true)
                            AND ew_support_kb_clean(body))),
    subject             text CONSTRAINT support_draft_subject CHECK (subject IS NULL OR (
                            char_length(subject) BETWEEN 3 AND 80 AND ew_support_text_ok(subject, false)
                            AND ew_support_contact_free(subject))),
    note_to_employee    text CONSTRAINT support_draft_note CHECK (note_to_employee IS NULL OR (
                            char_length(note_to_employee) BETWEEN 1 AND 160
                            AND ew_support_text_ok(note_to_employee, false))),
    suggested_category  text NOT NULL CONSTRAINT support_draft_category CHECK (suggested_category IN
                            ('ACCOUNT', 'SOFTWARE', 'HARDWARE', 'PRINTING', 'NETWORK', 'EMAIL', 'INSTALL',
                             'HOW_TO', 'OTHER')),
    impact              text NOT NULL CONSTRAINT support_draft_impact CHECK (impact IN ('WIDESPREAD', 'SINGLE')),
    urgency             text NOT NULL CONSTRAINT support_draft_urgency
                            CHECK (urgency IN ('STOPPED', 'DEGRADED', 'REQUEST')),
    security_concern    boolean NOT NULL,
    -- يكتبه المحفّز من ew_support_priority_for، لا النموذج.
    suggested_priority  text NOT NULL DEFAULT 'NORMAL' CONSTRAINT support_draft_priority
                            CHECK (suggested_priority IN ('URGENT', 'HIGH', 'NORMAL', 'LOW')),
    escalate_suggestion text CONSTRAINT support_draft_escalate CHECK (escalate_suggestion IS NULL OR
                            escalate_suggestion IN ('TIER2', 'SUPERVISOR', 'VENDOR', 'FIELD_TECH', 'OTHER_TEAM')),
    language            text NOT NULL CONSTRAINT support_draft_language CHECK (language IN ('AR', 'EN')),
    -- طلب الموظف لإعادة الكتابة: خياراتٌ جاهزة وكلمةٌ قصيرة منه.
    presets             text[] NOT NULL DEFAULT '{}' CONSTRAINT support_draft_presets CHECK (
                            presets <@ ARRAY['SHORTER', 'SIMPLER', 'MORE_FORMAL', 'WARMER', 'ASK_INFO']::text[]
                            AND cardinality(presets) <= 2
                            AND NOT (presets @> ARRAY['MORE_FORMAL', 'WARMER']::text[])),
    hint                text CONSTRAINT support_draft_hint CHECK (hint IS NULL OR (
                            char_length(hint) BETWEEN 1 AND 200 AND ew_support_text_ok(hint, false)
                            AND ew_support_contact_free(hint))),
    redraft_of          uuid,
    rejected_at         timestamptz,
    reject_reason       text CONSTRAINT support_draft_reject_reason CHECK (reject_reason IS NULL OR reject_reason IN
                            ('WRONG_INFO', 'NOT_IN_KB', 'MISUNDERSTOOD', 'TONE', 'TOO_LONG', 'INCOMPLETE',
                             'OUTDATED_ARTICLE', 'OTHER')),
    reject_note         text CONSTRAINT support_draft_reject_note CHECK (reject_note IS NULL OR (
                            char_length(reject_note) BETWEEN 1 AND 200 AND ew_support_text_ok(reject_note, false)
                            AND ew_support_contact_free(reject_note))),
    served_model        text NOT NULL CHECK (served_model ~ '^claude-[a-z0-9.-]{1,57}$'),
    prompt_version      text NOT NULL CHECK (prompt_version ~ '^[a-z0-9.-]{1,32}$'),
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, seq),
    UNIQUE (id, user_id),
    UNIQUE (ticket_id, id),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (ticket_id, based_on_message_id) REFERENCES support_messages (ticket_id, id) ON DELETE CASCADE,
    FOREIGN KEY (ticket_id, redraft_of) REFERENCES support_drafts (ticket_id, id) ON DELETE CASCADE,
    CONSTRAINT support_draft_shape CHECK (
        (result = 'DRAFT' AND reply_kind IS NOT NULL AND body IS NOT NULL)
     OR (result = 'CANNOT_ANSWER' AND (reply_kind IS NULL) = (body IS NULL)
         AND reply_kind IS DISTINCT FROM 'ANSWER' AND note_to_employee IS NOT NULL)
     OR (result = 'NOT_SUPPORT' AND reply_kind IS NULL AND body IS NULL AND note_to_employee IS NOT NULL)),
    CONSTRAINT support_draft_rejection CHECK ((rejected_at IS NULL) = (reject_reason IS NULL)
                                              AND (reject_note IS NULL OR reject_reason IS NOT NULL))
);
CREATE INDEX support_drafts_user_rejected ON support_drafts (user_id, rejected_at DESC) WHERE rejected_at IS NOT NULL;

-- ما اقتبسته المسودة من قاعدة المعرفة، حرفاً بحرف، من نسخةٍ منشورة.
CREATE TABLE support_draft_citations (
    draft_id        uuid NOT NULL,
    user_id         uuid NOT NULL,
    position        smallint NOT NULL CHECK (position BETWEEN 1 AND 3),
    article_id      uuid NOT NULL,
    article_version smallint NOT NULL,
    quote           text NOT NULL CHECK (char_length(quote) BETWEEN 8 AND 300 AND ew_support_text_ok(quote, true)),
    PRIMARY KEY (draft_id, position),
    FOREIGN KEY (draft_id, user_id) REFERENCES support_drafts (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id, user_id) REFERENCES kb_articles (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id, article_version) REFERENCES kb_versions (article_id, version) ON DELETE CASCADE
);
CREATE INDEX support_citations_article ON support_draft_citations (article_id);

-- ── الردود ──────────────────────────────────────────────────────────────
-- core: نصّ الردّ بلا تحيةٍ ولا توقيع (منه تُراجع المطابقة، وهو وحده يصل النموذج).
-- body: ما يُنسخ للعميل كما هو: التحية باسمه إن وُجد، ثم core، ثم التوقيع.
CREATE TABLE support_replies (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id    uuid NOT NULL,
    user_id      uuid NOT NULL,
    draft_id     uuid,
    kind         text NOT NULL CONSTRAINT support_reply_kind CHECK (kind IN ('ANSWER', 'ASK_INFO', 'UPDATE')),
    -- AS_IS: المسودة كما هي. EDITED: مسودةٌ عدّلها الموظف. MANUAL: كتبه بنفسه.
    -- TEMPLATE: أسئلةٌ جاهزة اختارها لطلب المعلومات.
    origin       text NOT NULL CONSTRAINT support_reply_origin CHECK (origin IN ('AS_IS', 'EDITED', 'MANUAL', 'TEMPLATE')),
    core         text NOT NULL CONSTRAINT support_reply_core
                     CHECK (char_length(core) BETWEEN 20 AND 1200 AND ew_support_text_ok(core, true)),
    body         text NOT NULL CONSTRAINT support_reply_body CHECK (char_length(body) BETWEEN 20 AND 1500
                     AND ew_support_text_ok(body, true) AND ew_support_kb_clean(body)),
    body_sha256  bytea NOT NULL DEFAULT '\x' CHECK (octet_length(body_sha256) = 32),
    state        text NOT NULL DEFAULT 'READY' CONSTRAINT support_reply_state
                     CHECK (state IN ('READY', 'RELEASED', 'SENT', 'WITHDRAWN')),
    release_via  text CONSTRAINT support_reply_via CHECK (release_via IS NULL OR release_via IN ('COPY', 'SHARE', 'SCRIPT')),
    -- مقالاتٌ منشورة أدرج الموظف خطواتها في الردّ («أضف من قاعدة المعرفة»): سندٌ تراه المراجعة ويعود إلى المحرّر.
    kb_article_ids uuid[] NOT NULL DEFAULT '{}' CONSTRAINT support_reply_kb_ids_count CHECK (cardinality(kb_article_ids) <= 3),
    client_token uuid NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    released_at  timestamptz,
    sent_at      timestamptz,
    withdrawn_at timestamptz,
    UNIQUE (user_id, client_token),
    UNIQUE (id, user_id),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (ticket_id, draft_id) REFERENCES support_drafts (ticket_id, id) ON DELETE CASCADE,
    CONSTRAINT support_reply_contains_core CHECK (strpos(body, core) > 0),
    CONSTRAINT support_reply_origin_draft CHECK ((origin IN ('AS_IS', 'EDITED')) = (draft_id IS NOT NULL)),
    CONSTRAINT support_reply_state_times CHECK (
        (state = 'READY'     AND released_at IS NULL AND release_via IS NULL AND sent_at IS NULL AND withdrawn_at IS NULL)
     OR (state = 'RELEASED'  AND released_at IS NOT NULL AND release_via IS NOT NULL AND sent_at IS NULL
                             AND withdrawn_at IS NULL)
     OR (state = 'SENT'      AND released_at IS NOT NULL AND release_via IS NOT NULL AND sent_at IS NOT NULL
                             AND withdrawn_at IS NULL)
     OR (state = 'WITHDRAWN' AND withdrawn_at IS NOT NULL AND sent_at IS NULL))
);
-- ردٌّ حيٌّ واحد لكل تذكرة: لا يُنسخ ردّان ولا يُنسى أحدهما.
CREATE UNIQUE INDEX support_one_live_reply ON support_replies (ticket_id) WHERE state IN ('READY', 'RELEASED');
CREATE INDEX support_replies_released ON support_replies (user_id, released_at) WHERE state = 'RELEASED';

ALTER TABLE support_messages ADD CONSTRAINT support_message_reply_fk
    FOREIGN KEY (reply_id) REFERENCES support_replies (id) ON DELETE CASCADE;

-- ── تنبيهات القواعد ─────────────────────────────────────────────────────
-- فحصٌ ثابت في الخادم أو القاعدة على الردّ أو التذكرة. نصّ التنبيه بالعربية وباسم المستخدم
-- يُكتب في الخادم من الرمز، لا يُخزَّن. (تنبيهات سيمبول في ai_flags.)
CREATE TABLE support_flags (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    ticket_id          uuid NOT NULL,
    reply_id           uuid,
    code               text NOT NULL CONSTRAINT support_flag_code CHECK (code IN (
                           'PROMISE', 'ASKS_SECRET', 'NO_QUESTION', 'LINK_NOT_IN_KB', 'LANGUAGE_MISMATCH',
                           'RESOLVE_UNANSWERED', 'PRIORITY_BELOW_SUGGESTION')),
    -- اقتباسٌ حرفيّ من الردّ. يُمحى مع نصوص التذكرة.
    evidence           text CONSTRAINT support_flag_evidence CHECK (evidence IS NULL OR (
                           char_length(evidence) BETWEEN 2 AND 200 AND ew_support_text_ok(evidence, true))),
    state              text NOT NULL DEFAULT 'OPEN' CONSTRAINT support_flag_state
                           CHECK (state IN ('OPEN', 'HEEDED', 'DISMISSED')),
    dismiss_reason     text CONSTRAINT support_flag_dismiss CHECK (dismiss_reason IS NULL OR dismiss_reason IN
                           ('FALSE_ALARM', 'EMPLOYER_APPROVED', 'KB_OUTDATED', 'CONFIRMED', 'OTHER')),
    created_at         timestamptz NOT NULL DEFAULT now(),
    resolved_at        timestamptz,
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (reply_id, user_id) REFERENCES support_replies (id, user_id) ON DELETE CASCADE,
    CONSTRAINT support_flag_resolution CHECK ((state = 'OPEN') = (resolved_at IS NULL)
                                              AND (state = 'DISMISSED') = (dismiss_reason IS NOT NULL))
);
CREATE INDEX support_flags_reply   ON support_flags (reply_id) WHERE reply_id IS NOT NULL;
CREATE INDEX support_flags_ticket  ON support_flags (ticket_id);

-- ── التصعيد ─────────────────────────────────────────────────────────────
CREATE TABLE support_escalations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id   uuid NOT NULL,
    user_id     uuid NOT NULL,
    -- وظيفيّ (فريقٌ أعلى خبرة، مورّد، فنيٌّ ميداني، فريقٌ آخر) أو هرميّ (المشرف).
    target      text NOT NULL CONSTRAINT support_escalation_to
                    CHECK (target IN ('TIER2', 'SUPERVISOR', 'VENDOR', 'FIELD_TECH', 'OTHER_TEAM')),
    note        text NOT NULL CONSTRAINT support_escalation_note CHECK (char_length(note) BETWEEN 10 AND 1000
                    AND ew_support_text_ok(note, true) AND ew_support_contact_free(note)),
    created_at  timestamptz NOT NULL DEFAULT now(),
    returned_at timestamptz,
    return_note text CONSTRAINT support_escalation_return CHECK (return_note IS NULL OR (
                    char_length(return_note) BETWEEN 3 AND 500 AND ew_support_text_ok(return_note, true)
                    AND ew_support_contact_free(return_note))),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT support_escalation_return_time CHECK (return_note IS NULL OR returned_at IS NOT NULL)
);
CREATE UNIQUE INDEX support_one_open_escalation ON support_escalations (ticket_id) WHERE returned_at IS NULL;

-- ── سجلّ القرارات ───────────────────────────────────────────────────────
-- رموزٌ وأوقاتٌ فقط، لا نصّ حرّ: يبقى بعد محو نصوص التذكرة، ويُحذف معها بعد سنة.
CREATE TABLE support_events (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    ticket_id   uuid,
    article_id  uuid,
    event       text NOT NULL CONSTRAINT support_event_kind CHECK (event IN (
                    'TICKET_CREATED', 'FOLLOW_UP_CREATED', 'CUSTOMER_MESSAGE_ADDED', 'NOTE_ADDED',
                    'STATUS_CHANGED', 'CLASSIFIED', 'SUBJECT_SET',
                    'DRAFT_REQUESTED', 'DRAFT_PROPOSED', 'DRAFT_FAILED', 'DRAFT_REJECTED',
                    'REPLY_PREPARED', 'REVIEW_DONE', 'REVIEW_FAILED',
                    'FLAG_RAISED', 'FLAG_HEEDED', 'FLAG_DISMISSED',
                    'REPLY_RELEASED', 'REPLY_SENT', 'REPLY_WITHDRAWN',
                    'ESCALATED', 'ESCALATION_RETURNED', 'RESOLVED', 'REOPENED', 'TEXTS_PURGED',
                    'ARTICLE_CREATED', 'ARTICLE_VERSION_ADDED',
                    'ARTICLE_PUBLISHED', 'ARTICLE_ARCHIVED', 'ARTICLE_DISCARDED',
                    'ARTICLE_MARKED_REVIEW', 'ARTICLE_REVIEW_CLEARED')),
    actor       text NOT NULL DEFAULT 'EMPLOYEE' CONSTRAINT support_event_actor
                    CHECK (actor IN ('EMPLOYEE', 'ASSISTANT', 'SYSTEM')),
    from_status text,
    to_status   text,
    detail      text CONSTRAINT support_event_detail CHECK (detail IS NULL OR detail ~ '^[A-Z0-9_]{2,40}$'),
    draft_id    uuid,
    reply_id    uuid,
    flag_id     uuid,
    at          timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (ticket_id, user_id) REFERENCES support_tickets (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (article_id, user_id) REFERENCES kb_articles (id, user_id) ON DELETE CASCADE,
    CONSTRAINT support_event_target CHECK (ticket_id IS NOT NULL OR article_id IS NOT NULL)
);
CREATE INDEX support_events_ticket    ON support_events (ticket_id, id) WHERE ticket_id IS NOT NULL;
CREATE INDEX support_events_article   ON support_events (article_id, id) WHERE article_id IS NOT NULL;
CREATE INDEX support_events_user_time ON support_events (user_id, at DESC);

-- ════════════════════════════════════════════════════════════════════════
-- المحفّزات: الحاجز الثاني خلف الدوالّ، ولا يتجاوزها المالك نفسه
-- ════════════════════════════════════════════════════════════════════════

-- ما كُتب لا يُعاد كتابته (دالّة 0002 نفسها).
CREATE TRIGGER trg_support_messages_append_only BEFORE UPDATE ON support_messages
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();
CREATE TRIGGER trg_support_citations_append_only BEFORE UPDATE ON support_draft_citations
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();
CREATE TRIGGER trg_kb_versions_append_only BEFORE UPDATE ON kb_versions
    FOR EACH ROW EXECUTE FUNCTION ew_forbid_update();
-- السجلّ ملحقٌ فقط، إلا أن يُمحى أحد مرجعيه والآخر باقٍ (ew_support_events_keep): حدثٌ يخصّ تذكرةً ومقالةً
-- معاً يبقى ما بقيت إحداهما — مقالةٌ مهمَلة تُحذف بعد ثلاثين يوماً وسجلّ تذكرتها باقٍ سنة، والتذكرة تُحذف بعد
-- سنة والمقالة باقية.
CREATE FUNCTION ew_support_event_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF NOT ((NEW.ticket_id IS NULL AND OLD.ticket_id IS NOT NULL AND NEW.article_id IS NOT NULL
             AND to_jsonb(NEW) - 'ticket_id' = to_jsonb(OLD) - 'ticket_id')
         OR (NEW.article_id IS NULL AND OLD.article_id IS NOT NULL AND NEW.ticket_id IS NOT NULL
             AND to_jsonb(NEW) - 'article_id' = to_jsonb(OLD) - 'article_id')) THEN
        RAISE EXCEPTION 'append-only: %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_events_append_only BEFORE UPDATE ON support_events
    FOR EACH ROW EXECUTE FUNCTION ew_support_event_update_guard();

CREATE FUNCTION ew_support_events_keep() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_TABLE_NAME = 'kb_articles' THEN
        UPDATE support_events SET article_id = NULL WHERE article_id = OLD.id AND ticket_id IS NOT NULL;
    ELSE
        UPDATE support_events SET ticket_id = NULL WHERE ticket_id = OLD.id AND article_id IS NOT NULL;
    END IF;
    RETURN OLD;
END
$$;

-- الإعداد يُنشأ بأهداف زمن الخدمة الافتراضية لهذا التطبيق (قابلةٌ للتغيير، لا معيارٌ مفروض).
CREATE FUNCTION ew_support_settings_defaults() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    INSERT INTO support_sla_targets (user_id, priority, first_reply_minutes, resolve_minutes) VALUES
        (NEW.user_id, 'URGENT',   60,  480),
        (NEW.user_id, 'HIGH',    240, 1440),
        (NEW.user_id, 'NORMAL',  480, 4320),
        (NEW.user_id, 'LOW',    1440, 7200);
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_support_settings_defaults AFTER INSERT ON support_settings
    FOR EACH ROW EXECUTE FUNCTION ew_support_settings_defaults();

-- تذكرةٌ جديدة: لحساب دعمٍ فنيٍّ فعّال، برقمها التالي، وموعد أول ردٍّ من أولويتها، وفي حدود الحساب.
CREATE FUNCTION ew_support_ticket_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    n      integer;
    target support_sla_targets%ROWTYPE;
    fresh  boolean;
BEGIN
    -- FOR SHARE يقف أمام تغيير المهنة (admin set-profession يقفل الصفّ للتعديل).
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'SUPPORT' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (NEW.user_id) ON CONFLICT (user_id) DO NOTHING;
    SELECT next_ticket_number INTO n FROM support_settings WHERE user_id = NEW.user_id FOR UPDATE;
    fresh := ew_new_open_account(NEW.user_id);
    IF (SELECT count(*) FROM support_tickets WHERE user_id = NEW.user_id AND status <> 'CLOSED')
       >= (CASE WHEN fresh THEN 30 ELSE 300 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_open_ticket_cap';
    END IF;
    IF (SELECT count(*) FROM support_tickets
         WHERE user_id = NEW.user_id AND created_at > now() - interval '24 hours')
       >= (CASE WHEN fresh THEN 30 ELSE 200 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_daily_ticket_cap';
    END IF;
    SELECT * INTO target FROM support_sla_targets WHERE user_id = NEW.user_id AND priority = NEW.priority;
    UPDATE support_settings SET next_ticket_number = n + 1, updated_at = now() WHERE user_id = NEW.user_id;
    NEW.number := n;
    NEW.status := 'NEW';
    NEW.row_version := 1;
    NEW.escalation_target := NULL;
    NEW.resolution := NULL;
    NEW.close_reason := NULL;
    NEW.created_at := now();
    NEW.updated_at := now();
    NEW.last_activity_at := now();
    NEW.first_reply_due_at := now() + make_interval(mins => target.first_reply_minutes);
    NEW.first_replied_at := NULL;
    NEW.resolve_minutes := target.resolve_minutes;
    NEW.wait_seconds := 0;
    NEW.clock_since := now();
    NEW.resolved_at := NULL;
    NEW.closed_at := NULL;
    NEW.texts_purged_at := NULL;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_ticket_insert BEFORE INSERT ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION ew_support_ticket_insert_guard();

-- التعديل: الأعمدة المُدارة ثابتة، والحالة بجدول الانتقالات، وساعة الانتظار والمواعيد
-- يكتبها المحفّز. والتذكرة المغلقة لا يتغيّر فيها إلا محو نصوصها.
CREATE FUNCTION ew_support_ticket_update_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target support_sla_targets%ROWTYPE;
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.number <> OLD.number
       OR NEW.created_at <> OLD.created_at OR NEW.client_token <> OLD.client_token
       OR NEW.row_version <> OLD.row_version OR NEW.channel <> OLD.channel
       OR (NEW.follow_up_of IS DISTINCT FROM OLD.follow_up_of AND NEW.follow_up_of IS NOT NULL) THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_managed_columns';
    END IF;
    IF OLD.status = 'CLOSED' THEN
        IF NEW.status <> 'CLOSED' OR NEW.priority <> OLD.priority
           OR NEW.category IS DISTINCT FROM OLD.category
           OR NEW.escalation_target IS DISTINCT FROM OLD.escalation_target
           OR NEW.resolution IS DISTINCT FROM OLD.resolution
           OR NEW.close_reason IS DISTINCT FROM OLD.close_reason
           OR NEW.first_replied_at IS DISTINCT FROM OLD.first_replied_at
           OR (NEW.subject IS NOT NULL AND NEW.subject IS DISTINCT FROM OLD.subject)
           OR (NEW.customer_label IS NOT NULL AND NEW.customer_label IS DISTINCT FROM OLD.customer_label)
           OR (OLD.texts_purged_at IS NOT NULL AND NEW.texts_purged_at IS DISTINCT FROM OLD.texts_purged_at) THEN
            RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
        END IF;
        NEW.row_version := OLD.row_version + 1;
        NEW.updated_at := now();
        NEW.last_activity_at := OLD.last_activity_at;
        NEW.closed_at := OLD.closed_at;
        NEW.resolved_at := OLD.resolved_at;
        NEW.clock_since := OLD.clock_since;
        NEW.wait_seconds := OLD.wait_seconds;
        NEW.first_reply_due_at := OLD.first_reply_due_at;
        NEW.resolve_minutes := OLD.resolve_minutes;
        RETURN NEW;
    END IF;
    IF NEW.status <> OLD.status AND NOT EXISTS (
           SELECT 1 FROM support_ticket_transition WHERE from_status = OLD.status AND to_status = NEW.status) THEN
        RAISE EXCEPTION 'transition' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF NEW.texts_purged_at IS DISTINCT FROM OLD.texts_purged_at THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_managed_columns';
    END IF;

    -- ساعة انتظار العميل: تجري في NEW وOPEN وESCALATED، وتقف في غيرها.
    NEW.clock_since := OLD.clock_since;
    NEW.wait_seconds := OLD.wait_seconds;
    IF NEW.status <> OLD.status THEN
        IF OLD.clock_since IS NOT NULL AND NEW.status NOT IN ('NEW', 'OPEN', 'ESCALATED') THEN
            NEW.wait_seconds := OLD.wait_seconds + floor(extract(epoch FROM now() - OLD.clock_since))::integer;
            NEW.clock_since := NULL;
        ELSIF OLD.clock_since IS NULL AND NEW.status IN ('NEW', 'OPEN', 'ESCALATED') THEN
            NEW.clock_since := now();
        END IF;
    END IF;
    NEW.resolved_at := CASE
        WHEN NEW.status = 'RESOLVED' AND OLD.status <> 'RESOLVED' THEN now()
        WHEN NEW.status IN ('RESOLVED', 'CLOSED') THEN OLD.resolved_at
        ELSE NULL END;
    IF NEW.status NOT IN ('RESOLVED', 'CLOSED') THEN
        NEW.resolution := NULL;
    ELSIF NEW.status = 'CLOSED' THEN
        NEW.resolution := OLD.resolution;
    END IF;
    NEW.closed_at := CASE WHEN NEW.status = 'CLOSED' THEN now() ELSE NULL END;
    IF NEW.status <> 'CLOSED' THEN
        NEW.close_reason := NULL;
    END IF;
    IF NEW.status <> 'ESCALATED' THEN
        NEW.escalation_target := NULL;
    END IF;
    -- أول ردٍّ يُكتب مرةً واحدة.
    IF OLD.first_replied_at IS NOT NULL THEN
        NEW.first_replied_at := OLD.first_replied_at;
    END IF;
    -- تغيير الأولوية يعيد حساب المواعيد من وقت الإنشاء، والردّ الأول إن لم يقع بعد.
    IF NEW.priority <> OLD.priority THEN
        SELECT * INTO target FROM support_sla_targets WHERE user_id = NEW.user_id AND priority = NEW.priority;
        NEW.first_reply_due_at := CASE WHEN NEW.first_replied_at IS NULL
                                       THEN OLD.created_at + make_interval(mins => target.first_reply_minutes)
                                       ELSE OLD.first_reply_due_at END;
        NEW.resolve_minutes := target.resolve_minutes;
    ELSE
        NEW.first_reply_due_at := OLD.first_reply_due_at;
        NEW.resolve_minutes := OLD.resolve_minutes;
    END IF;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    NEW.last_activity_at := CASE WHEN ew_current_user() IS NULL THEN OLD.last_activity_at ELSE now() END;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_ticket_update BEFORE UPDATE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION ew_support_ticket_update_guard();

-- كل تغيّرٍ في الحالة سطرٌ في السجلّ، أيّاً كان من غيّرها. بلا جلسةٍ: النظام.
CREATE FUNCTION ew_support_ticket_status_event() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    INSERT INTO support_events (user_id, ticket_id, event, actor, from_status, to_status, detail)
    VALUES (NEW.user_id, NEW.id, 'STATUS_CHANGED',
            CASE WHEN ew_current_user() IS NULL THEN 'SYSTEM' ELSE 'EMPLOYEE' END,
            OLD.status, NEW.status, coalesce(NEW.close_reason, NEW.resolution));
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_support_ticket_status_event AFTER UPDATE OF status ON support_tickets
    FOR EACH ROW WHEN (NEW.status IS DISTINCT FROM OLD.status) EXECUTE FUNCTION ew_support_ticket_status_event();

-- رسالةٌ في تذكرةٍ لم تُغلق، وفي حدود التذكرة واليوم.
CREATE FUNCTION ew_support_message_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    t support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = NEW.ticket_id AND user_id = NEW.user_id;
    IF NOT FOUND OR t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    -- ستون رسالةً يلصقها الموظف أو يكتبها؛ والردّ المرسل (AGENT) يُسجَّل دائماً: أُرسل من قناته قبل أن يُؤكَّد.
    IF NEW.author <> 'AGENT' AND (SELECT count(*) FROM support_messages WHERE ticket_id = NEW.ticket_id) >= 60 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_message_cap';
    END IF;
    IF NEW.author <> 'AGENT' AND (SELECT count(*) FROM support_messages
                                   WHERE user_id = NEW.user_id AND author <> 'AGENT'
                                     AND created_at > now() - interval '24 hours')
                                 >= (CASE WHEN ew_new_open_account(NEW.user_id) THEN 60 ELSE 400 END) THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_daily_message_cap';
    END IF;
    IF NEW.author = 'AGENT' AND NOT EXISTS (SELECT 1 FROM support_replies
                                             WHERE id = NEW.reply_id AND ticket_id = NEW.ticket_id
                                               AND state = 'SENT' AND body = NEW.body) THEN
        RAISE EXCEPTION 'agent' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_agent_message_needs_sent_reply';
    END IF;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_message_insert BEFORE INSERT ON support_messages
    FOR EACH ROW EXECUTE FUNCTION ew_support_message_insert_guard();

-- مسودةٌ لا توجد إلا على استدعاءٍ مفتوح لها، عمره دون خمس دقائق، ولآخر رسالةٍ من العميل.
CREATE FUNCTION ew_support_draft_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    c      ai_requests%ROWTYPE;
    latest uuid;
BEGIN
    SELECT * INTO c FROM ai_requests WHERE id = NEW.call_id FOR UPDATE;
    IF NOT FOUND OR c.feature <> 'SUPPORT_DRAFT' OR c.finished_at IS NOT NULL OR c.user_id <> NEW.user_id
       OR c.subject_kind <> 'SUPPORT_TICKET' OR c.subject_id IS DISTINCT FROM NEW.ticket_id
       OR c.started_at <= now() - make_interval(secs => (SELECT lease_seconds FROM ai_features
                                                          WHERE code = 'SUPPORT_DRAFT')) THEN
        RAISE EXCEPTION 'call' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_needs_open_call';
    END IF;
    SELECT id INTO latest FROM support_messages
     WHERE ticket_id = NEW.ticket_id AND author = 'CUSTOMER' ORDER BY created_at DESC, id DESC LIMIT 1;
    IF latest IS DISTINCT FROM NEW.based_on_message_id THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_stale';
    END IF;
    NEW.seq := (SELECT coalesce(max(seq), 0) + 1 FROM support_drafts WHERE ticket_id = NEW.ticket_id);
    NEW.suggested_priority := ew_support_priority_for(NEW.impact, NEW.urgency, NEW.security_concern);
    NEW.rejected_at := NULL;
    NEW.reject_reason := NULL;
    NEW.reject_note := NULL;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_draft_insert BEFORE INSERT ON support_drafts
    FOR EACH ROW EXECUTE FUNCTION ew_support_draft_insert_guard();

-- المسودة لا تتغيّر بعد كتابتها إلا رفضها، مرةً واحدة.
CREATE FUNCTION ew_support_draft_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    -- ON DELETE SET NULL على call_id وحده (محو سجلّ الاستدعاء بعد أيامه): لا يتغيّر معه عمودٌ آخر.
    IF OLD.call_id IS NOT NULL AND NEW.call_id IS NULL AND to_jsonb(NEW) - 'call_id' = to_jsonb(OLD) - 'call_id' THEN
        RETURN NEW;
    END IF;
    IF OLD.rejected_at IS NOT NULL OR NEW.rejected_at IS NULL OR NEW.call_id IS DISTINCT FROM OLD.call_id
       OR (NEW.id, NEW.ticket_id, NEW.user_id, NEW.based_on_message_id, NEW.seq, NEW.result, NEW.reply_kind,
           NEW.body, NEW.subject, NEW.note_to_employee, NEW.suggested_category, NEW.impact, NEW.urgency,
           NEW.security_concern, NEW.suggested_priority, NEW.escalate_suggestion, NEW.language, NEW.presets,
           NEW.hint, NEW.redraft_of, NEW.served_model, NEW.prompt_version, NEW.created_at)
          IS DISTINCT FROM
          (OLD.id, OLD.ticket_id, OLD.user_id, OLD.based_on_message_id, OLD.seq, OLD.result, OLD.reply_kind,
           OLD.body, OLD.subject, OLD.note_to_employee, OLD.suggested_category, OLD.impact, OLD.urgency,
           OLD.security_concern, OLD.suggested_priority, OLD.escalate_suggestion, OLD.language, OLD.presets,
           OLD.hint, OLD.redraft_of, OLD.served_model, OLD.prompt_version, OLD.created_at) THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_immutable';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_draft_update BEFORE UPDATE ON support_drafts
    FOR EACH ROW EXECUTE FUNCTION ew_support_draft_update_guard();

-- الاقتباس من النسخة المنشورة الآن لمقالةٍ لصاحب المسودة، وحرفيٌّ فيها بعد التوحيد،
-- ولمسودةٍ كُتبت في المعاملة نفسها.
CREATE FUNCTION ew_support_citation_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v support_drafts%ROWTYPE;
    a kb_articles%ROWTYPE;
    k kb_versions%ROWTYPE;
BEGIN
    SELECT * INTO v FROM support_drafts WHERE id = NEW.draft_id AND user_id = NEW.user_id;
    IF NOT FOUND OR v.created_at <> now() THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_needs_new_draft';
    END IF;
    SELECT * INTO a FROM kb_articles WHERE id = NEW.article_id AND user_id = NEW.user_id;
    IF NOT FOUND OR a.state <> 'PUBLISHED' OR a.published_version <> NEW.article_version THEN
        RAISE EXCEPTION 'kb' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_not_published';
    END IF;
    SELECT * INTO k FROM kb_versions WHERE article_id = NEW.article_id AND version = NEW.article_version;
    -- اقتباسٌ يصير بعد التوحيد أقلّ من ثمانية أحرف (تطويلٌ أو تشكيلٌ أو مسافات) لا يُسند شيئاً: كل نصٍّ يحويه.
    IF length(ew_kb_norm(NEW.quote)) < 8
       OR strpos(ew_kb_norm(k.title || ' ' || k.issue || ' ' || coalesce(k.environment, '') || ' '
                            || k.resolution || ' ' || coalesce(k.cause, '')),
                 ew_kb_norm(NEW.quote)) = 0 THEN
        RAISE EXCEPTION 'quote' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_not_verbatim';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_citation BEFORE INSERT ON support_draft_citations
    FOR EACH ROW EXECUTE FUNCTION ew_support_citation_guard();

-- عند الالتزام: مسودةٌ «تجيب» لها اقتباسٌ واحدٌ على الأقل. مؤجّلٌ لأن الاقتباسات تُكتب بعدها.
CREATE FUNCTION ew_support_draft_grounded() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.reply_kind = 'ANSWER'
       AND EXISTS (SELECT 1 FROM support_drafts WHERE id = NEW.id)
       AND NOT EXISTS (SELECT 1 FROM support_draft_citations WHERE draft_id = NEW.id) THEN
        RAISE EXCEPTION 'grounded' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_answer_needs_citation';
    END IF;
    RETURN NULL;
END
$$;
CREATE CONSTRAINT TRIGGER trg_support_draft_grounded AFTER INSERT ON support_drafts
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ew_support_draft_grounded();

-- الردّ: يُجهَّز لتذكرةٍ لم تُغلق، وأصله يُستنتج من مطابقته للمسودة لا من قول العميل.
CREATE FUNCTION ew_support_reply_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    t support_tickets%ROWTYPE;
    d support_drafts%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = NEW.ticket_id AND user_id = NEW.user_id;
    IF NOT FOUND OR t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    IF NEW.kind = 'ANSWER' AND t.status = 'ESCALATED' THEN
        RAISE EXCEPTION 'escalated' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_escalation_open';
    END IF;
    IF NEW.draft_id IS NOT NULL THEN
        SELECT * INTO d FROM support_drafts WHERE id = NEW.draft_id AND ticket_id = NEW.ticket_id;
        IF NOT FOUND OR d.rejected_at IS NOT NULL OR d.body IS NULL
           OR d.seq <> (SELECT max(seq) FROM support_drafts WHERE ticket_id = NEW.ticket_id) THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_draft_not_current';
        END IF;
        NEW.origin := CASE WHEN NEW.core = d.body AND NEW.kind = d.reply_kind THEN 'AS_IS' ELSE 'EDITED' END;
    ELSIF NEW.origin NOT IN ('MANUAL', 'TEMPLATE') THEN
        RAISE EXCEPTION 'origin' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_origin_draft';
    END IF;
    NEW.body_sha256 := sha256(convert_to(NEW.body, 'UTF8'));
    NEW.state := 'READY';
    NEW.release_via := NULL;
    NEW.released_at := NULL;
    NEW.sent_at := NULL;
    NEW.withdrawn_at := NULL;
    NEW.created_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_reply_insert BEFORE INSERT ON support_replies
    FOR EACH ROW EXECUTE FUNCTION ew_support_reply_insert_guard();

-- نصّ الردّ ثابت. تتغيّر حالته فقط، وفي اتجاهٍ واحد.
CREATE FUNCTION ew_support_reply_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF (NEW.id, NEW.ticket_id, NEW.user_id, NEW.draft_id, NEW.kind, NEW.origin, NEW.core, NEW.body,
        NEW.body_sha256, NEW.client_token, NEW.created_at, NEW.kb_article_ids)
       IS DISTINCT FROM
       (OLD.id, OLD.ticket_id, OLD.user_id, OLD.draft_id, OLD.kind, OLD.origin, OLD.core, OLD.body,
        OLD.body_sha256, OLD.client_token, OLD.created_at, OLD.kb_article_ids) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_immutable';
    END IF;
    IF NEW.state = OLD.state AND (NEW.release_via, NEW.released_at, NEW.sent_at, NEW.withdrawn_at)
                                 IS DISTINCT FROM (OLD.release_via, OLD.released_at, OLD.sent_at, OLD.withdrawn_at) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_immutable';
    END IF;
    IF NEW.state <> OLD.state AND NOT (
           (OLD.state = 'READY' AND NEW.state IN ('RELEASED', 'WITHDRAWN'))
        OR (OLD.state = 'RELEASED' AND NEW.state IN ('SENT', 'WITHDRAWN'))) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_reply_update BEFORE UPDATE ON support_replies
    FOR EACH ROW EXECUTE FUNCTION ew_support_reply_update_guard();

-- التنبيه: اقتباسه من النصّ الذي يُنبّه عليه، وتغيّره الوحيد إغلاقه أو محو اقتباسه.
CREATE FUNCTION ew_support_flag_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    source_text text;
BEGIN
    IF NEW.reply_id IS NOT NULL THEN
        SELECT body INTO source_text FROM support_replies
         WHERE id = NEW.reply_id AND ticket_id = NEW.ticket_id AND user_id = NEW.user_id AND state = 'READY';
        IF NOT FOUND THEN
            RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_target_state';
        END IF;
    END IF;
    IF NEW.evidence IS NOT NULL AND (source_text IS NULL
                                     OR strpos(ew_kb_norm(source_text), ew_kb_norm(NEW.evidence)) = 0) THEN
        RAISE EXCEPTION 'evidence' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_evidence_verbatim';
    END IF;
    NEW.created_at := now();
    IF NEW.state = 'OPEN' THEN
        NEW.resolved_at := NULL;
    ELSE
        NEW.resolved_at := now();
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_flag_insert BEFORE INSERT ON support_flags
    FOR EACH ROW EXECUTE FUNCTION ew_support_flag_insert_guard();

CREATE FUNCTION ew_support_flag_update_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF (NEW.id, NEW.user_id, NEW.ticket_id, NEW.reply_id, NEW.code, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.user_id, OLD.ticket_id, OLD.reply_id, OLD.code, OLD.created_at)
       OR (NEW.evidence IS DISTINCT FROM OLD.evidence AND NEW.evidence IS NOT NULL)
       OR (NEW.state <> OLD.state AND OLD.state <> 'OPEN') THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_immutable';
    END IF;
    IF NEW.state <> OLD.state THEN
        NEW.resolved_at := now();
    ELSE
        NEW.resolved_at := OLD.resolved_at;
        NEW.dismiss_reason := OLD.dismiss_reason;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_support_flag_update BEFORE UPDATE ON support_flags
    FOR EACH ROW EXECUTE FUNCTION ew_support_flag_update_guard();

-- المقالة: لحساب دعمٍ فنيٍّ فعّال، برقمها التالي، وفي حدّ ثلاثمئة مقالة.
CREATE FUNCTION ew_kb_article_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    n integer;
BEGIN
    PERFORM 1 FROM users WHERE id = NEW.user_id AND is_active AND profession = 'SUPPORT' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    IF NEW.state <> 'DRAFT' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_starts_unpublished';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (NEW.user_id) ON CONFLICT (user_id) DO NOTHING;
    SELECT next_article_number INTO n FROM support_settings WHERE user_id = NEW.user_id FOR UPDATE;
    IF (SELECT count(*) FROM kb_articles WHERE user_id = NEW.user_id AND state <> 'DISCARDED') >= 300 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_cap';
    END IF;
    UPDATE support_settings SET next_article_number = n + 1, updated_at = now() WHERE user_id = NEW.user_id;
    NEW.number := n;
    NEW.published_version := NULL;
    NEW.latest_version := 0;
    NEW.needs_review := false;
    NEW.needs_review_reason := NULL;
    NEW.reuse_count := 0;
    NEW.row_version := 1;
    NEW.created_at := now();
    NEW.updated_at := now();
    NEW.published_at := NULL;
    NEW.archived_at := NULL;
    NEW.discarded_at := NULL;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_kb_article_insert BEFORE INSERT ON kb_articles
    FOR EACH ROW EXECUTE FUNCTION ew_kb_article_insert_guard();

-- الحالة في اتجاهاتها وحدها، والنسخة المنشورة هي الأحدث لحظة الاعتماد.
CREATE FUNCTION ew_kb_article_update_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.user_id <> OLD.user_id OR NEW.number <> OLD.number
       OR NEW.created_at <> OLD.created_at OR NEW.row_version <> OLD.row_version
       OR NEW.client_token IS DISTINCT FROM OLD.client_token
       OR (NEW.source_ticket_id IS DISTINCT FROM OLD.source_ticket_id AND NEW.source_ticket_id IS NOT NULL)
       OR NEW.latest_version < OLD.latest_version OR NEW.reuse_count < OLD.reuse_count THEN
        RAISE EXCEPTION 'managed' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_managed_columns';
    END IF;
    IF OLD.state = 'DISCARDED' AND (NEW.state <> 'DISCARDED' OR NEW.latest_version <> OLD.latest_version) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    IF NEW.state <> OLD.state AND NOT (
           (OLD.state = 'DRAFT' AND NEW.state IN ('PUBLISHED', 'DISCARDED'))
        OR (OLD.state = 'PUBLISHED' AND NEW.state = 'ARCHIVED')
        OR (OLD.state = 'ARCHIVED' AND NEW.state = 'PUBLISHED')) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    IF NEW.published_version IS DISTINCT FROM OLD.published_version AND NEW.published_version IS NOT NULL
       AND NEW.published_version <> NEW.latest_version THEN
        RAISE EXCEPTION 'version' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_publish_latest_only';
    END IF;
    NEW.published_at := CASE
        WHEN NEW.state = 'PUBLISHED' AND NEW.published_version IS DISTINCT FROM OLD.published_version THEN now()
        WHEN NEW.state IN ('PUBLISHED', 'ARCHIVED') THEN OLD.published_at
        ELSE NULL END;
    NEW.archived_at := CASE WHEN NEW.state = 'ARCHIVED' THEN coalesce(OLD.archived_at, now()) ELSE NULL END;
    NEW.discarded_at := CASE WHEN NEW.state = 'DISCARDED' THEN coalesce(OLD.discarded_at, now()) ELSE NULL END;
    NEW.row_version := OLD.row_version + 1;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_kb_article_update BEFORE UPDATE ON kb_articles
    FOR EACH ROW EXECUTE FUNCTION ew_kb_article_update_guard();

-- النسخة: رقمها التالي، وفي حدّ ثلاثين. يكتبها الموظف وحده.
CREATE FUNCTION ew_kb_version_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    a kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = NEW.article_id AND user_id = NEW.user_id FOR UPDATE;
    IF NOT FOUND OR a.state = 'DISCARDED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    NEW.version := a.latest_version + 1;
    NEW.created_at := now();
    UPDATE kb_articles SET latest_version = NEW.version WHERE id = NEW.article_id;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_kb_version_insert BEFORE INSERT ON kb_versions
    FOR EACH ROW EXECUTE FUNCTION ew_kb_version_insert_guard();

-- ════════════════════════════════════════════════════════════════════════
-- الدوالّ الداخلية
-- ════════════════════════════════════════════════════════════════════════

-- صاحب الجلسة إن كان حساب دعمٍ فنيٍّ فعّالاً، بقفلٍ على صفّه. يُنشئ إعداده إن غاب.
CREATE FUNCTION ew_support_me(p_for_update boolean) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
BEGIN
    IF p_for_update THEN
        PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT' FOR UPDATE;
    ELSE
        PERFORM 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT' FOR SHARE;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    INSERT INTO support_settings (user_id) VALUES (uid) ON CONFLICT (user_id) DO NOTHING;
    RETURN uid;
END
$$;

-- لا يُخزَّن كلام عميلٍ ولا يُستدعى النموذج قبل أن يقرأ صاحب الحساب إشعار المكتب ويوافق عليه.
CREATE FUNCTION ew_support_require_notice(p_uid uuid) RETURNS void
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM support_settings WHERE user_id = p_uid AND notice_version IS NOT NULL) THEN
        RAISE EXCEPTION 'notice' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_notice_required';
    END IF;
END
$$;

-- تذكرةٌ لصاحب الجلسة بقفلٍ عليها، بالنسخة التي رآها.
CREATE FUNCTION ew_support_ticket_for(p_uid uuid, p_ticket uuid, p_expected_row_version integer)
RETURNS support_tickets
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    t support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO t FROM support_tickets WHERE id = p_ticket AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF p_expected_row_version IS NOT NULL AND t.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF t.status = 'CLOSED' THEN
        RAISE EXCEPTION 'closed' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_closed';
    END IF;
    RETURN t;
END
$$;

CREATE FUNCTION ew_support_log(
    p_uid uuid, p_ticket uuid, p_article uuid, p_event text, p_detail text,
    p_draft uuid, p_reply uuid, p_flag uuid, p_actor text
) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    INSERT INTO support_events (user_id, ticket_id, article_id, event, detail, draft_id, reply_id, flag_id, actor)
    VALUES (p_uid, p_ticket, p_article, p_event, p_detail, p_draft, p_reply, p_flag, coalesce(p_actor, 'EMPLOYEE'))
$$;

-- بصمة ما يُراجَع من نسخة مقالة: كل حقلٍ يصل سيمبول، بفاصلٍ لا يُكتب في النصّ.
CREATE FUNCTION ew_kb_version_digest(p_article uuid, p_version smallint) RETURNS bytea
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT sha256(convert_to(concat_ws(chr(31), title, issue, coalesce(environment, ''), resolution,
                                       coalesce(cause, '')), 'UTF8'))
      FROM kb_versions WHERE article_id = p_article AND version = p_version
$$;

-- استدعاءٌ مفتوح لصاحب الجلسة من ميزةٍ بعينها، بقفل.
CREATE FUNCTION ew_support_request_for(p_uid uuid, p_request uuid, p_feature text) RETURNS ai_requests
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    r ai_requests%ROWTYPE;
BEGIN
    SELECT * INTO r FROM ai_requests WHERE id = p_request AND user_id = p_uid FOR UPDATE;
    IF NOT FOUND OR r.finished_at IS NOT NULL OR (p_feature IS NOT NULL AND r.feature <> p_feature) THEN
        RAISE EXCEPTION 'request' USING ERRCODE = 'check_violation', CONSTRAINT = 'ai_request_not_open';
    END IF;
    RETURN r;
END
$$;

-- ════════════════════════════════════════════════════════════════════════
-- واجهة دور الويب: كل دالّةٍ تفعل شيئاً واحداً لصاحب الجلسة
-- ════════════════════════════════════════════════════════════════════════

-- ── الإعداد ─────────────────────────────────────────────────────────────
CREATE FUNCTION ew_support_accept_notice(p_version text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
BEGIN
    UPDATE support_settings
       SET notice_version = p_version, notice_accepted_at = now(), updated_at = now()
     WHERE user_id = uid AND notice_version IS DISTINCT FROM p_version;
END
$$;

-- p_targets: {"URGENT": [60, 480], ...} لما يتغيّر وحده. والتوقيع NULL يمحوه.
CREATE FUNCTION ew_support_save_settings(p_signature text, p_targets jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    p   text;
BEGIN
    UPDATE support_settings SET signature = p_signature, updated_at = now() WHERE user_id = uid;
    IF p_targets IS NOT NULL THEN
        IF jsonb_typeof(p_targets) <> 'object' THEN
            RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_first';
        END IF;
        FOR p IN SELECT jsonb_object_keys(p_targets) LOOP
            IF jsonb_typeof(p_targets -> p) <> 'array' OR jsonb_array_length(p_targets -> p) <> 2 THEN
                RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_first';
            END IF;
            UPDATE support_sla_targets
               SET first_reply_minutes = (p_targets -> p ->> 0)::integer,
                   resolve_minutes = (p_targets -> p ->> 1)::integer
             WHERE user_id = uid AND priority = p;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'targets' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_sla_priority';
            END IF;
        END LOOP;
    END IF;
END
$$;

-- ── التذاكر ─────────────────────────────────────────────────────────────
-- تذكرةٌ من رسالةٍ ألصقها الموظف. الضغطة المكرّرة (client_token نفسه) تُرجع التذكرة نفسها.
CREATE FUNCTION ew_support_create_ticket(
    p_client_token uuid, p_channel text, p_priority text, p_category text, p_customer_label text,
    p_subject text, p_body text, p_masked smallint
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    tid uuid;
BEGIN
    -- ضغطتان بالرمز نفسه معاً: الثانية تنتظر الأولى ثم تجد ما كتبته فتُرجعه.
    PERFORM pg_advisory_xact_lock(hashtextextended('ew_support_token:' || uid::text, 0));
    SELECT id INTO tid FROM support_tickets WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN tid;
    END IF;
    PERFORM ew_support_require_notice(uid);
    INSERT INTO support_tickets (user_id, client_token, channel, priority, category, customer_label, subject)
    VALUES (uid, p_client_token, p_channel, coalesce(p_priority, 'NORMAL'), p_category, p_customer_label, p_subject)
    RETURNING id INTO tid;
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (tid, uid, 'CUSTOMER', p_body, p_masked, p_client_token);
    PERFORM ew_support_log(uid, tid, NULL, 'TICKET_CREATED', p_channel, NULL, NULL, NULL, NULL);
    RETURN tid;
END
$$;

-- رسالةٌ جديدة من العميل تعيد التذكرة إلى الموظف؛ والملاحظة الداخلية لا تغيّر حالتها.
CREATE FUNCTION ew_support_add_message(
    p_ticket uuid, p_expected_row_version integer, p_author text, p_body text, p_masked smallint,
    p_client_token uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
    mid uuid;
BEGIN
    -- ضغطتان بالرمز نفسه معاً: الثانية تنتظر الأولى ثم تجد ما كتبته فتُرجعه.
    PERFORM pg_advisory_xact_lock(hashtextextended('ew_support_token:' || uid::text, 0));
    SELECT id INTO mid FROM support_messages WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN mid;
    END IF;
    IF p_author NOT IN ('CUSTOMER', 'NOTE') THEN
        RAISE EXCEPTION 'author' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_message_author';
    END IF;
    PERFORM ew_support_require_notice(uid);
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (p_ticket, uid, p_author, p_body, p_masked, p_client_token)
    RETURNING id INTO mid;
    IF p_author = 'CUSTOMER' THEN
        UPDATE support_tickets
           SET status = CASE WHEN t.status IN ('PENDING', 'RESOLVED') THEN 'OPEN' ELSE t.status END
         WHERE id = p_ticket;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'CUSTOMER_MESSAGE_ADDED', NULL, NULL, NULL, NULL, NULL);
    ELSE
        UPDATE support_tickets SET status = t.status WHERE id = p_ticket;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'NOTE_ADDED', NULL, NULL, NULL, NULL, NULL);
    END IF;
    RETURN mid;
END
$$;

-- التصنيف والأولوية والموضوع قرار الموظف. p_from_draft: قَبِل اقتراح هذه المسودة كما هو.
-- أولويةٌ أدنى من المقترحة تُسجَّل تنبيهاً ثابتاً، ولا تُمنع.
CREATE FUNCTION ew_support_set_ticket(
    p_ticket uuid, p_expected_row_version integer, p_category text, p_priority text, p_subject text,
    p_from_draft uuid
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid       uuid := ew_support_me(false);
    t         support_tickets%ROWTYPE;
    d         support_drafts%ROWTYPE;
    suggested text;
    flag      uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF p_from_draft IS NOT NULL THEN
        SELECT * INTO d FROM support_drafts WHERE id = p_from_draft AND ticket_id = p_ticket AND user_id = uid;
        IF NOT FOUND OR p_category IS DISTINCT FROM d.suggested_category
           OR p_priority IS DISTINCT FROM d.suggested_priority THEN
            RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_suggestion_mismatch';
        END IF;
    END IF;
    UPDATE support_tickets
       SET category = p_category, priority = p_priority, subject = p_subject
     WHERE id = p_ticket;
    IF p_category IS DISTINCT FROM t.category OR p_priority <> t.priority THEN
        PERFORM ew_support_log(uid, p_ticket, NULL, 'CLASSIFIED',
                               CASE WHEN p_from_draft IS NULL THEN 'MANUAL' ELSE 'ACCEPTED_SUGGESTION' END,
                               p_from_draft, NULL, NULL, NULL);
    END IF;
    IF p_subject IS DISTINCT FROM t.subject THEN
        PERFORM ew_support_log(uid, p_ticket, NULL, 'SUBJECT_SET', NULL, NULL, NULL, NULL, NULL);
    END IF;
    SELECT suggested_priority INTO suggested FROM support_drafts
     WHERE ticket_id = p_ticket ORDER BY seq DESC LIMIT 1;
    IF suggested IS NOT NULL AND p_priority <> t.priority
       AND ew_support_priority_rank(p_priority) < ew_support_priority_rank(suggested) THEN
        INSERT INTO support_flags (user_id, ticket_id, code)
        VALUES (uid, p_ticket, 'PRIORITY_BELOW_SUGGESTION')
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_RAISED', 'PRIORITY_BELOW_SUGGESTION', NULL, NULL, flag,
                               'SYSTEM');
    END IF;
END
$$;

-- ── المسودات ────────────────────────────────────────────────────────────
-- يفتح استدعاء مسودةٍ لآخر رسالةٍ من العميل، بعد الإشعار والسقوف وحدّ التذكرة.
CREATE FUNCTION ew_support_begin_draft(p_ticket uuid, p_expected_row_version integer)
RETURNS TABLE (request_id uuid, based_on_message_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid    uuid := ew_support_me(true);
    t      support_tickets%ROWTYPE;
    latest uuid;
    req    uuid;
BEGIN
    PERFORM ew_support_require_notice(uid);
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    SELECT id INTO latest FROM support_messages
     WHERE ticket_id = p_ticket AND author = 'CUSTOMER' ORDER BY created_at DESC, id DESC LIMIT 1;
    IF latest IS NULL THEN
        RAISE EXCEPTION 'message' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_needs_message';
    END IF;
    -- ما فشل قبل أن يصل النموذج (سيمبول متوقّف أو مشغول، أو خطأٌ في الطريق) لا يُحسب: لا يُكلّف ولا يُنتج شيئاً.
    IF (SELECT count(*) FROM ai_requests
         WHERE user_id = uid AND feature = 'SUPPORT_DRAFT' AND subject_id = p_ticket AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 8 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_draft_cap';
    END IF;
    req := ew_ai_request_open('SUPPORT_DRAFT', 'SUPPORT_TICKET', p_ticket, NULL);
    PERFORM ew_support_log(uid, p_ticket, NULL, 'DRAFT_REQUESTED', NULL, NULL, NULL, NULL, NULL);
    RETURN QUERY SELECT req, latest;
END
$$;

-- يكتب المسودة واقتباساتها ويُغلق الاستدعاء، في معاملةٍ واحدة: لا نتيجةٌ ناجحة بلا مسودتها.
-- p_based_on: آخر رسالةٍ من العميل كما أعادها البدء (المحفّز يرفضها إن جاءت بعدها أخرى).
-- p_citations: [{"article_id": "...", "version": 3, "quote": "..."}] بعد فحصها في الخادم.
-- p_usage: أرقام الاستدعاء كما في ew_ai_request_settle؛ والنموذج ونسخة المطالبة تُحفظ مع المسودة.
CREATE FUNCTION ew_support_record_draft(
    p_request uuid, p_based_on uuid, p_result text, p_reply_kind text, p_body text, p_subject text, p_note text,
    p_category text, p_impact text, p_urgency text, p_security boolean, p_escalate text, p_language text,
    p_presets text[], p_hint text, p_redraft_of uuid, p_citations jsonb, p_usage jsonb
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    r   ai_requests%ROWTYPE;
    did uuid;
    i   integer := 0;
    q   jsonb;
BEGIN
    r := ew_support_request_for(uid, p_request, 'SUPPORT_DRAFT');
    INSERT INTO support_drafts (ticket_id, user_id, call_id, based_on_message_id, result, reply_kind, body, subject,
                                note_to_employee, suggested_category, impact, urgency, security_concern,
                                escalate_suggestion, language, presets, hint, redraft_of, served_model,
                                prompt_version)
    VALUES (r.subject_id, uid, p_request, p_based_on, p_result, p_reply_kind, p_body, p_subject, p_note,
            p_category, p_impact, p_urgency, p_security, p_escalate, p_language, coalesce(p_presets, '{}'),
            p_hint, p_redraft_of, p_usage ->> 'model', p_usage ->> 'prompt_version')
    RETURNING id INTO did;
    IF p_citations IS NOT NULL THEN
        IF jsonb_typeof(p_citations) <> 'array' OR jsonb_array_length(p_citations) > 3 THEN
            RAISE EXCEPTION 'citations' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_citation_count';
        END IF;
        FOR q IN SELECT value FROM jsonb_array_elements(p_citations) LOOP
            i := i + 1;
            INSERT INTO support_draft_citations (draft_id, user_id, position, article_id, article_version, quote)
            VALUES (did, uid, i, (q ->> 'article_id')::uuid, (q ->> 'version')::smallint, q ->> 'quote');
        END LOOP;
    END IF;
    PERFORM ew_ai_request_settle(p_request, CASE p_result WHEN 'DRAFT' THEN 'OK' ELSE p_result END, NULL, p_usage);
    PERFORM ew_support_log(uid, r.subject_id, NULL, 'DRAFT_PROPOSED', p_result, did, NULL, NULL, 'ASSISTANT');
    RETURN did;
END
$$;

-- يُغلق استدعاءً لم يُنتج أثراً (رفضٌ أو خطأٌ أو جوابٌ مرفوض)، ويسجّله على تذكرته.
CREATE FUNCTION ew_support_finish_call(p_request uuid, p_outcome text, p_usage jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid    uuid := ew_support_me(false);
    r      ai_requests%ROWTYPE;
    ticket uuid;
BEGIN
    r := ew_support_request_for(uid, p_request, NULL);
    -- DISCARDED: جاءت رسالةٌ أو مسودةٌ أحدث أثناء الاستدعاء فلم يُكتب شيء؛ يُغلق الطلب ولا يبقى مفتوحاً يحجز التالي.
    IF p_outcome = 'DISCARDED' THEN
        PERFORM ew_ai_request_settle(p_request, p_outcome, NULL, p_usage);
    ELSE
        PERFORM ew_ai_request_fail(p_request, p_outcome, p_usage);
    END IF;
    IF r.feature = 'SUPPORT_DRAFT' THEN
        PERFORM ew_support_log(uid, r.subject_id, NULL, 'DRAFT_FAILED', p_outcome, NULL, NULL, NULL, 'ASSISTANT');
    ELSIF r.feature = 'SUPPORT_REPLY_REVIEW' THEN
        SELECT ticket_id INTO ticket FROM support_replies WHERE id = r.subject_id AND user_id = uid;
        IF ticket IS NOT NULL THEN
            PERFORM ew_support_log(uid, ticket, NULL, 'REVIEW_FAILED', p_outcome, NULL, r.subject_id, NULL,
                                   'ASSISTANT');
        END IF;
    END IF;
END
$$;

-- رفض المسودة بسببه. WRONG_INFO أو OUTDATED_ARTICLE على مسودةٍ تقتبس: تُعلَّم مقالاتها
-- «تحتاج مراجعة» (علّمها أو أصلحها)، فلا تتكرّر المعلومة نفسها في مسودةٍ أخرى دون أن يراها الموظف.
CREATE FUNCTION ew_support_reject_draft(p_draft uuid, p_reason text, p_note text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    d   support_drafts%ROWTYPE;
    t   support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO d FROM support_drafts WHERE id = p_draft AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, d.ticket_id, NULL);
    IF d.rejected_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_immutable';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE draft_id = p_draft AND state IN ('READY', 'RELEASED', 'SENT')) THEN
        RAISE EXCEPTION 'used' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_draft_in_use';
    END IF;
    UPDATE support_drafts SET rejected_at = now(), reject_reason = p_reason, reject_note = p_note WHERE id = p_draft;
    IF p_reason IN ('WRONG_INFO', 'OUTDATED_ARTICLE') THEN
        UPDATE kb_articles a
           SET needs_review = true,
               needs_review_reason = CASE p_reason WHEN 'WRONG_INFO' THEN 'DRAFT_WRONG_INFO' ELSE 'DRAFT_OUTDATED' END
          FROM support_draft_citations c
         WHERE c.draft_id = p_draft AND a.id = c.article_id AND a.state = 'PUBLISHED' AND NOT a.needs_review;
    END IF;
    PERFORM ew_support_log(uid, d.ticket_id, NULL, 'DRAFT_REJECTED', p_reason, p_draft, NULL, NULL, NULL);
END
$$;

-- ── الردود ──────────────────────────────────────────────────────────────
-- يُجهّز الردّ بنصّه النهائي ويكتب تنبيهات الفحص الثابت التي حسبها الخادم:
-- p_rule_flags: [{"code": "PROMISE", "evidence": "..."}]. الأصل والمراجعة يستنتجهما المحفّز.
CREATE FUNCTION ew_support_prepare_reply(
    p_ticket uuid, p_expected_row_version integer, p_client_token uuid, p_draft uuid, p_kind text,
    p_template boolean, p_core text, p_body text, p_rule_flags jsonb, p_kb_article_ids uuid[] DEFAULT '{}'
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    t    support_tickets%ROWTYPE;
    rid  uuid;
    f    jsonb;
    flag uuid;
BEGIN
    -- ضغطتان بالرمز نفسه معاً: الثانية تنتظر الأولى ثم تجد ما كتبته فتُرجعه.
    PERFORM pg_advisory_xact_lock(hashtextextended('ew_support_token:' || uid::text, 0));
    SELECT id INTO rid FROM support_replies WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN rid;
    END IF;
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF EXISTS (SELECT 1 FROM unnest(coalesce(p_kb_article_ids, '{}')) k
                WHERE NOT EXISTS (SELECT 1 FROM kb_articles a WHERE a.id = k AND a.user_id = uid AND a.state = 'PUBLISHED')) THEN
        RAISE EXCEPTION 'kb' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_kb_ids';
    END IF;
    INSERT INTO support_replies (ticket_id, user_id, draft_id, kind, origin, core, body, client_token, kb_article_ids)
    VALUES (p_ticket, uid, p_draft, p_kind,
            CASE WHEN p_draft IS NOT NULL THEN 'EDITED' WHEN p_template THEN 'TEMPLATE' ELSE 'MANUAL' END,
            p_core, p_body, p_client_token, coalesce(p_kb_article_ids, '{}'))
    RETURNING id INTO rid;
    UPDATE support_tickets SET status = t.status WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'REPLY_PREPARED',
                           (SELECT origin FROM support_replies WHERE id = rid), p_draft, rid, NULL, NULL);
    IF p_rule_flags IS NOT NULL THEN
        IF jsonb_typeof(p_rule_flags) <> 'array' OR jsonb_array_length(p_rule_flags) > 8 THEN
            RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
        END IF;
        FOR f IN SELECT value FROM jsonb_array_elements(p_rule_flags) LOOP
            IF f ->> 'code' NOT IN ('PROMISE', 'ASKS_SECRET', 'NO_QUESTION', 'LINK_NOT_IN_KB', 'LANGUAGE_MISMATCH') THEN
                RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_code';
            END IF;
            INSERT INTO support_flags (user_id, ticket_id, reply_id, code, evidence)
            VALUES (uid, p_ticket, rid, f ->> 'code', f ->> 'evidence')
            RETURNING id INTO flag;
            PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_RAISED', f ->> 'code', NULL, rid, flag, 'SYSTEM');
        END LOOP;
    END IF;
    RETURN rid;
END
$$;

-- يبدأ مراجعة سيمبول لردٍّ عدّله الموظف أو كتبه (المسودة كما هي والأسئلة الجاهزة لا تُراجَع).
-- البصمة بصمة النصّ الذي يُنسخ؛ والردّ لا يتغيّر بعد تجهيزه.
CREATE FUNCTION ew_support_review_begin(p_reply uuid) RETURNS TABLE (request_id uuid, content_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(true);
    r   support_replies%ROWTYPE;
    t   support_tickets%ROWTYPE;
BEGIN
    PERFORM ew_support_require_notice(uid);
    SELECT * INTO r FROM support_replies
     WHERE id = p_reply AND user_id = uid AND state = 'READY' AND origin IN ('EDITED', 'MANUAL') FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    RETURN QUERY SELECT ew_ai_request_open('SUPPORT_REPLY_REVIEW', 'SUPPORT_REPLY', p_reply, r.body_sha256),
                        r.body_sha256;
END
$$;

-- يكتب ما قاله سيمبول عن الردّ (ew_ai_flags_put)، أو يُسقطه DISCARDED إن لم يعد الردّ جاهزاً.
CREATE FUNCTION ew_support_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_support_me(false);
    r       ai_requests%ROWTYPE;
    reply   support_replies%ROWTYPE;
    outcome text;
BEGIN
    r := ew_support_request_for(uid, p_request, 'SUPPORT_REPLY_REVIEW');
    SELECT * INTO reply FROM support_replies
     WHERE id = r.subject_id AND user_id = uid AND state = 'READY' FOR UPDATE;
    outcome := ew_ai_flags_put(p_request, reply.body_sha256, p_flags, p_usage);
    IF outcome = 'OK' THEN
        PERFORM ew_support_log(uid, reply.ticket_id, NULL, 'REVIEW_DONE', NULL, NULL, reply.id, NULL, 'ASSISTANT');
    END IF;
    RETURN outcome;
END
$$;

-- الموظف يقرّر في تنبيه القاعدة: أخذ به (HEEDED) أو تجاوزه بسببٍ (DISMISSED).
CREATE FUNCTION ew_support_ack_flag(p_flag uuid, p_action text, p_reason text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    f   support_flags%ROWTYPE;
BEGIN
    SELECT * INTO f FROM support_flags WHERE id = p_flag AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'no_data_found';
    END IF;
    IF f.state <> 'OPEN' OR p_action NOT IN ('HEEDED', 'DISMISSED')
       OR (p_action = 'DISMISSED') <> (p_reason IS NOT NULL) THEN
        RAISE EXCEPTION 'flag' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flag_immutable';
    END IF;
    UPDATE support_flags SET state = p_action, dismiss_reason = p_reason WHERE id = p_flag;
    PERFORM ew_support_log(uid, f.ticket_id, NULL,
                           CASE p_action WHEN 'HEEDED' THEN 'FLAG_HEEDED' ELSE 'FLAG_DISMISSED' END,
                           coalesce(p_reason, f.code), NULL, f.reply_id, p_flag, NULL);
END
$$;

-- النسخ أو المشاركة: النصّ الذي يُنسخ هو المحفوظ بعينه (البصمة)، ولا تنبيه قاعدةٍ مفتوحٌ عليه،
-- ولا تنبيهٌ من سيمبول بلا قرار «تابع» (ew_ai_gate). لا ينتظر مراجعةً جارية: سيمبول لا يمنع.
CREATE FUNCTION ew_support_release_reply(p_reply uuid, p_via text, p_body_sha256 bytea)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    r   support_replies%ROWTYPE;
    t   support_tickets%ROWTYPE;
BEGIN
    SELECT * INTO r FROM support_replies WHERE id = p_reply AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    IF r.state <> 'READY' THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    IF p_body_sha256 IS NULL OR r.body_sha256 IS DISTINCT FROM p_body_sha256 THEN
        RAISE EXCEPTION 'hash' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_hash_mismatch';
    END IF;
    IF EXISTS (SELECT 1 FROM support_flags WHERE reply_id = p_reply AND state = 'OPEN') THEN
        RAISE EXCEPTION 'flags' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_flags_open';
    END IF;
    PERFORM ew_ai_gate('SUPPORT_REPLY', p_reply, r.body_sha256);
    UPDATE support_replies SET state = 'RELEASED', release_via = p_via, released_at = now() WHERE id = p_reply;
    UPDATE support_tickets SET status = t.status WHERE id = r.ticket_id;
    PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_RELEASED', p_via, r.draft_id, p_reply, NULL, NULL);
END
$$;

-- الموظف يؤكّد أنه أرسل الردّ من القناة (أو أنه لم يُرسله). الإرسال يكتب الردّ في المحادثة
-- ويغيّر حالة التذكرة بنوعه، ويعدّ إعادة استعمال المقالات المقتبسة.
CREATE FUNCTION ew_support_confirm_reply(p_reply uuid, p_sent boolean) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    r    support_replies%ROWTYPE;
    t    support_tickets%ROWTYPE;
    next text;
BEGIN
    SELECT * INTO r FROM support_replies WHERE id = p_reply AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'no_data_found';
    END IF;
    t := ew_support_ticket_for(uid, r.ticket_id, NULL);
    IF r.state NOT IN ('READY', 'RELEASED') OR (p_sent AND r.state <> 'RELEASED') THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_reply_transition';
    END IF;
    IF NOT p_sent THEN
        UPDATE support_replies SET state = 'WITHDRAWN', withdrawn_at = now() WHERE id = p_reply;
        UPDATE support_tickets SET status = t.status WHERE id = r.ticket_id;
        PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_WITHDRAWN', NULL, r.draft_id, p_reply, NULL, NULL);
        RETURN;
    END IF;
    UPDATE support_replies SET state = 'SENT', sent_at = now() WHERE id = p_reply;
    INSERT INTO support_messages (ticket_id, user_id, author, body, reply_id)
    VALUES (r.ticket_id, uid, 'AGENT', r.body, p_reply);
    next := CASE
        WHEN r.kind = 'ANSWER' THEN 'RESOLVED'
        WHEN t.status = 'ESCALATED' THEN 'ESCALATED'
        WHEN r.kind = 'ASK_INFO' THEN 'PENDING'
        ELSE 'OPEN' END;
    UPDATE support_tickets
       SET status = next,
           resolution = CASE WHEN next = 'RESOLVED' THEN coalesce(t.resolution, 'REPLIED') ELSE NULL END,
           first_replied_at = coalesce(t.first_replied_at, now())
     WHERE id = r.ticket_id;
    UPDATE kb_articles a SET reuse_count = a.reuse_count + 1
      FROM (SELECT DISTINCT article_id FROM support_draft_citations WHERE draft_id = r.draft_id) c
     WHERE a.id = c.article_id AND a.user_id = uid;
    PERFORM ew_support_log(uid, r.ticket_id, NULL, 'REPLY_SENT', r.kind, r.draft_id, p_reply, NULL, NULL);
    IF next = 'RESOLVED' AND t.status <> 'RESOLVED' THEN
        PERFORM ew_support_log(uid, r.ticket_id, NULL, 'RESOLVED', 'REPLIED', NULL, p_reply, NULL, NULL);
    END IF;
END
$$;

-- ── التصعيد والحلّ وإعادة الفتح ─────────────────────────────────────────
CREATE FUNCTION ew_support_escalate(p_ticket uuid, p_expected_row_version integer, p_target text, p_note text)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
    eid uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status NOT IN ('NEW', 'OPEN', 'PENDING') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    -- ردٌّ جاهزٌ أو منسوخٌ لم يُؤكَّد: لو صُعّدت التذكرة لما أمكن تأكيده ولا إعادة التصعيد.
    IF EXISTS (SELECT 1 FROM support_replies WHERE ticket_id = p_ticket AND state IN ('READY', 'RELEASED')) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_live_reply_exists';
    END IF;
    INSERT INTO support_escalations (ticket_id, user_id, target, note) VALUES (p_ticket, uid, p_target, p_note)
    RETURNING id INTO eid;
    UPDATE support_tickets SET status = 'ESCALATED', escalation_target = p_target WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'ESCALATED', p_target, NULL, NULL, NULL, NULL);
    RETURN eid;
END
$$;

CREATE FUNCTION ew_support_return_escalation(p_ticket uuid, p_expected_row_version integer, p_note text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status <> 'ESCALATED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE ticket_id = p_ticket AND state IN ('READY', 'RELEASED')) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_live_reply_exists';
    END IF;
    UPDATE support_escalations SET returned_at = now(), return_note = p_note
     WHERE ticket_id = p_ticket AND returned_at IS NULL;
    UPDATE support_tickets SET status = 'OPEN' WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'ESCALATION_RETURNED', t.escalation_target, NULL, NULL, NULL, NULL);
END
$$;

-- حلٌّ بلا ردٍّ مكتوب. وآخر رسالةٍ من العميل بلا ردٍّ بعدها تُرفض أولاً، ثم تُقبل إن أكّدها
-- الموظف (p_confirmed)، ويبقى تأكيده تنبيهاً مُتجاوَزاً في السجلّ.
CREATE FUNCTION ew_support_resolve(
    p_ticket uuid, p_expected_row_version integer, p_resolution text, p_confirmed boolean
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid  uuid := ew_support_me(false);
    t    support_tickets%ROWTYPE;
    last text;
    flag uuid;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status NOT IN ('NEW', 'OPEN', 'PENDING')
       OR p_resolution NOT IN ('BY_PHONE', 'IN_PERSON', 'DUPLICATE', 'NOT_SUPPORT', 'NO_RESPONSE')
       OR (p_resolution = 'NO_RESPONSE' AND t.status <> 'PENDING') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF EXISTS (SELECT 1 FROM support_replies WHERE ticket_id = p_ticket AND state IN ('READY', 'RELEASED')) THEN
        RAISE EXCEPTION 'reply' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_live_reply_exists';
    END IF;
    SELECT author INTO last FROM support_messages
     WHERE ticket_id = p_ticket AND author IN ('CUSTOMER', 'AGENT') ORDER BY created_at DESC, id DESC LIMIT 1;
    IF last = 'CUSTOMER' AND p_resolution IN ('NO_RESPONSE') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    IF last = 'CUSTOMER' AND p_resolution NOT IN ('BY_PHONE', 'IN_PERSON', 'DUPLICATE', 'NOT_SUPPORT')
       OR (last = 'CUSTOMER' AND p_resolution IN ('DUPLICATE', 'NOT_SUPPORT') AND NOT coalesce(p_confirmed, false)) THEN
        RAISE EXCEPTION 'unanswered' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_resolve_unanswered';
    END IF;
    IF last = 'CUSTOMER' AND p_resolution IN ('DUPLICATE', 'NOT_SUPPORT') THEN
        INSERT INTO support_flags (user_id, ticket_id, code, state, dismiss_reason)
        VALUES (uid, p_ticket, 'RESOLVE_UNANSWERED', 'DISMISSED', 'CONFIRMED')
        RETURNING id INTO flag;
        PERFORM ew_support_log(uid, p_ticket, NULL, 'FLAG_DISMISSED', 'CONFIRMED', NULL, NULL, flag, NULL);
    END IF;
    UPDATE support_tickets
       SET status = 'RESOLVED', resolution = p_resolution,
           first_replied_at = CASE WHEN p_resolution IN ('BY_PHONE', 'IN_PERSON')
                                   THEN coalesce(t.first_replied_at, now()) ELSE t.first_replied_at END
     WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'RESOLVED', p_resolution, NULL, NULL, NULL, NULL);
END
$$;

CREATE FUNCTION ew_support_reopen(p_ticket uuid, p_expected_row_version integer) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    t   support_tickets%ROWTYPE;
BEGIN
    t := ew_support_ticket_for(uid, p_ticket, p_expected_row_version);
    IF t.status <> 'RESOLVED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_ticket_transition';
    END IF;
    UPDATE support_tickets SET status = 'OPEN' WHERE id = p_ticket;
    PERFORM ew_support_log(uid, p_ticket, NULL, 'REOPENED', NULL, NULL, NULL, NULL, NULL);
END
$$;

-- ردٌّ من العميل على تذكرةٍ مغلقة يفتح تذكرة متابعةٍ تشير إليها، ولا يعيد فتحها.
CREATE FUNCTION ew_support_follow_up(p_closed uuid, p_client_token uuid, p_body text, p_masked smallint)
RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    old support_tickets%ROWTYPE;
    tid uuid;
BEGIN
    -- ضغطتان بالرمز نفسه معاً: الثانية تنتظر الأولى ثم تجد ما كتبته فتُرجعه.
    PERFORM pg_advisory_xact_lock(hashtextextended('ew_support_token:' || uid::text, 0));
    SELECT id INTO tid FROM support_tickets WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN tid;
    END IF;
    SELECT * INTO old FROM support_tickets WHERE id = p_closed AND user_id = uid;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket' USING ERRCODE = 'no_data_found';
    END IF;
    IF old.status <> 'CLOSED' THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'support_follow_up_needs_closed';
    END IF;
    PERFORM ew_support_require_notice(uid);
    INSERT INTO support_tickets (user_id, client_token, channel, priority, category, customer_label, subject,
                                 follow_up_of)
    VALUES (uid, p_client_token, old.channel, old.priority, old.category, old.customer_label, old.subject, p_closed)
    RETURNING id INTO tid;
    INSERT INTO support_messages (ticket_id, user_id, author, body, masked_count, client_token)
    VALUES (tid, uid, 'CUSTOMER', p_body, p_masked, p_client_token);
    PERFORM ew_support_log(uid, tid, NULL, 'FOLLOW_UP_CREATED', NULL, NULL, NULL, NULL, NULL);
    RETURN tid;
END
$$;

-- الإغلاق الآلي لصاحب الجلسة: المحلولة بعد أربعة أيام، وما خمل تسعين يوماً. يستدعيه
-- الطابور عند عرضه، ويستدعي نظيرَه purge للجميع يومياً.
CREATE FUNCTION ew_support_close_due() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    n   integer;
    m   integer;
BEGIN
    -- خارج الجلسة كي لا يُحسب الإغلاق الآلي نشاطاً للموظف ولا يُنسب إليه.
    PERFORM set_config('eyework.user_id', '', true);
    UPDATE support_tickets SET status = 'CLOSED', close_reason = 'AFTER_RESOLVED'
     WHERE user_id = uid AND status = 'RESOLVED' AND resolved_at < now() - interval '4 days';
    GET DIAGNOSTICS n = ROW_COUNT;
    UPDATE support_tickets SET status = 'CLOSED', close_reason = 'IDLE'
     WHERE user_id = uid AND status <> 'CLOSED' AND last_activity_at < now() - interval '90 days';
    GET DIAGNOSTICS m = ROW_COUNT;
    -- ردٌّ جُهّز أو نُسخ ولم يؤكَّد على تذكرةٍ أُغلقت لا يبقى حيّاً.
    UPDATE support_replies r SET state = 'WITHDRAWN', withdrawn_at = now()
      FROM support_tickets t
     WHERE t.id = r.ticket_id AND t.user_id = uid AND t.status = 'CLOSED' AND r.state IN ('READY', 'RELEASED');
    PERFORM set_config('eyework.user_id', uid::text, true);
    RETURN n + m;
END
$$;

-- ── قاعدة المعرفة ───────────────────────────────────────────────────────
CREATE FUNCTION ew_kb_create(
    p_client_token uuid, p_title text, p_issue text, p_environment text, p_resolution text, p_cause text,
    p_source_ticket uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    aid uuid;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('ew_support_token:' || uid::text, 0));
    SELECT id INTO aid FROM kb_articles WHERE user_id = uid AND client_token = p_client_token;
    IF FOUND THEN
        RETURN aid;
    END IF;
    IF (SELECT count(*) FROM kb_versions WHERE user_id = uid AND created_at > now() - interval '24 hours') >= 100 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_daily_version_cap';
    END IF;
    INSERT INTO kb_articles (user_id, state, client_token, source_ticket_id)
    VALUES (uid, 'DRAFT', p_client_token, p_source_ticket)
    RETURNING id INTO aid;
    INSERT INTO kb_versions (article_id, user_id, title, issue, environment, resolution, cause)
    VALUES (aid, uid, p_title, p_issue, p_environment, p_resolution, p_cause);
    PERFORM ew_support_log(uid, p_source_ticket, aid, 'ARTICLE_CREATED', NULL, NULL, NULL, NULL, NULL);
    RETURN aid;
END
$$;

CREATE FUNCTION ew_kb_add_version(
    p_article uuid, p_expected_row_version integer, p_title text, p_issue text, p_environment text,
    p_resolution text, p_cause text
) RETURNS smallint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
    v   smallint;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF (SELECT count(*) FROM kb_versions WHERE user_id = uid AND created_at > now() - interval '24 hours') >= 100 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_daily_version_cap';
    END IF;
    INSERT INTO kb_versions (article_id, user_id, title, issue, environment, resolution, cause)
    VALUES (p_article, uid, p_title, p_issue, p_environment, p_resolution, p_cause)
    RETURNING version INTO v;
    UPDATE kb_articles SET updated_at = now() WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article, 'ARTICLE_VERSION_ADDED', NULL, NULL, NULL, NULL, NULL);
    RETURN v;
END
$$;

-- الاعتماد قرار الموظف وحده: النسخة التي رآها، وهي الأحدث، ولا تنبيه مفتوحٌ عليها.
CREATE FUNCTION ew_kb_publish(p_article uuid, p_expected_row_version integer, p_version smallint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version OR a.latest_version <> p_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    PERFORM ew_ai_gate('KB_ARTICLE', p_article, ew_kb_version_digest(p_article, p_version));
    UPDATE kb_articles
       SET state = 'PUBLISHED', published_version = p_version, needs_review = false, needs_review_reason = NULL
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article, 'ARTICLE_PUBLISHED', 'V' || p_version, NULL, NULL, NULL, NULL);
END
$$;

-- الأرشفة تُخرج المقالة من قاعدة المساعد، والتجاهل يُسقط ما لم يُنشر قط.
CREATE FUNCTION ew_kb_set_state(p_article uuid, p_expected_row_version integer, p_state text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_state NOT IN ('ARCHIVED', 'DISCARDED') THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_article_transition';
    END IF;
    UPDATE kb_articles
       SET state = p_state, published_version = NULL, needs_review = false, needs_review_reason = NULL
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article,
                           CASE p_state WHEN 'ARCHIVED' THEN 'ARTICLE_ARCHIVED' ELSE 'ARTICLE_DISCARDED' END,
                           NULL, NULL, NULL, NULL, NULL);
END
$$;

-- «علّمها» أو «أُصلحت»: مقالةٌ منشورة تحتاج مراجعة، أو رُفع عنها ذلك.
CREATE FUNCTION ew_kb_mark_review(p_article uuid, p_expected_row_version integer, p_needs boolean) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    a   kb_articles%ROWTYPE;
BEGIN
    SELECT * INTO a FROM kb_articles WHERE id = p_article AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    IF a.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    UPDATE kb_articles
       SET needs_review = p_needs, needs_review_reason = CASE WHEN p_needs THEN 'EMPLOYEE' END
     WHERE id = p_article;
    PERFORM ew_support_log(uid, NULL, p_article,
                           CASE WHEN p_needs THEN 'ARTICLE_MARKED_REVIEW' ELSE 'ARTICLE_REVIEW_CLEARED' END,
                           NULL, NULL, NULL, NULL, NULL);
END
$$;

-- البحث في المنشور من مقالات صاحب الجلسة: أيّ كلمةٍ من الاستعلام بعد التجذيع العربي.
CREATE FUNCTION ew_kb_search(p_query text, p_limit integer)
RETURNS TABLE (article_id uuid, number integer, version smallint, title text, issue text, environment text,
               resolution text, cause text, rank real)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_current_user();
    q   tsquery;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND is_active AND profession = 'SUPPORT') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege', CONSTRAINT = 'support_needs_support';
    END IF;
    IF p_query IS NULL OR char_length(p_query) NOT BETWEEN 2 AND 200 OR p_limit NOT BETWEEN 1 AND 10 THEN
        RAISE EXCEPTION 'query' USING ERRCODE = 'check_violation', CONSTRAINT = 'kb_search_query';
    END IF;
    SELECT to_tsquery('simple', string_agg(quote_literal(lexeme), ' | '))
      INTO q FROM unnest(tsvector_to_array(to_tsvector('arabic'::regconfig, p_query))) AS lexeme;
    IF q IS NULL THEN
        RETURN;
    END IF;
    RETURN QUERY
    SELECT a.id, a.number, v.version, v.title, v.issue, v.environment, v.resolution, v.cause,
           ts_rank_cd(v.search, q) AS r
      FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id AND v.version = a.published_version
     WHERE a.user_id = uid AND a.state = 'PUBLISHED' AND v.search @@ q
     ORDER BY r DESC, a.reuse_count DESC, a.number
     LIMIT p_limit;
END
$$;

-- مراجعة سيمبول لآخر نسخةٍ من مقالةٍ لم تُنشر بعد (p_version NULL: آخر نسخة). البصمة من حقول
-- النسخة؛ ونسخةٌ جديدة بصمةٌ جديدة، فما قيل عن السابقة لا يُعرض على اللاحقة.
CREATE FUNCTION ew_kb_review_begin(p_article uuid, p_version smallint)
RETURNS TABLE (request_id uuid, content_digest bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(true);
    v   smallint;
    d   bytea;
BEGIN
    PERFORM ew_support_require_notice(uid);
    SELECT latest_version INTO v FROM kb_articles
     WHERE id = p_article AND user_id = uid AND latest_version = coalesce(p_version, latest_version)
       AND state NOT IN ('ARCHIVED', 'DISCARDED') AND published_version IS DISTINCT FROM latest_version
       FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'article' USING ERRCODE = 'no_data_found';
    END IF;
    d := ew_kb_version_digest(p_article, v);
    RETURN QUERY SELECT ew_ai_request_open('SUPPORT_ARTICLE_REVIEW', 'KB_ARTICLE', p_article, d), d;
END
$$;

-- بصمة آخر نسخةٍ من مقالةٍ لصاحب الجلسة: قرار «عدّل» أو «تابع» يقارنها بما رُوجع.
CREATE FUNCTION ew_kb_current_digest(p_article uuid) RETURNS bytea
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT ew_kb_version_digest(a.id, a.latest_version) FROM kb_articles a
     WHERE a.id = p_article AND a.user_id = ew_current_user() AND a.latest_version >= 1
$$;

CREATE FUNCTION ew_kb_review_record(p_request uuid, p_flags jsonb, p_usage jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid uuid := ew_support_me(false);
    r   ai_requests%ROWTYPE;
    a   kb_articles%ROWTYPE;
    d   bytea;
BEGIN
    r := ew_support_request_for(uid, p_request, 'SUPPORT_ARTICLE_REVIEW');
    SELECT * INTO a FROM kb_articles
     WHERE id = r.subject_id AND user_id = uid AND state NOT IN ('ARCHIVED', 'DISCARDED')
       AND published_version IS DISTINCT FROM latest_version
       FOR UPDATE;
    IF FOUND THEN
        d := ew_kb_version_digest(a.id, a.latest_version);
    END IF;
    RETURN ew_ai_flags_put(p_request, d, p_flags, p_usage);
END
$$;


-- ما قاله سيمبول عن ردٍّ أو مقالةٍ يُحذف معهما (حذف الحساب، ومحو نصوص التذكرة، والإسقاط).
CREATE TRIGGER trg_support_replies_forget_ai AFTER DELETE ON support_replies
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('SUPPORT_REPLY');
CREATE TRIGGER trg_kb_articles_events_keep BEFORE DELETE ON kb_articles
    FOR EACH ROW EXECUTE FUNCTION ew_support_events_keep();
CREATE TRIGGER trg_support_tickets_events_keep BEFORE DELETE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION ew_support_events_keep();
CREATE TRIGGER trg_kb_articles_forget_ai AFTER DELETE ON kb_articles
    FOR EACH ROW EXECUTE FUNCTION ew_ai_forget_subject('KB_ARTICLE');

-- ════════════════════════════════════════════════════════════════════════
-- العزل والمنح
-- ════════════════════════════════════════════════════════════════════════
ALTER TABLE support_settings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_settings          FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_sla_targets       ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_sla_targets       FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_ticket_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_ticket_transition FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_tickets           ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets           FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_messages          ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_messages          FORCE  ROW LEVEL SECURITY;
ALTER TABLE kb_articles               ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_articles               FORCE  ROW LEVEL SECURITY;
ALTER TABLE kb_versions               ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_versions               FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_drafts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_drafts            FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_draft_citations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_draft_citations   FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_replies           ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_replies           FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_flags             ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_flags             FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_escalations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_escalations       FORCE  ROW LEVEL SECURITY;
ALTER TABLE support_events            ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_events            FORCE  ROW LEVEL SECURITY;

-- المالك: كل شيء (الدوالّ والمحفّزات وأداة المشغّل).
CREATE POLICY support_settings_owner_access    ON support_settings          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_sla_owner_access         ON support_sla_targets       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_transition_owner_access  ON support_ticket_transition FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_tickets_owner_access     ON support_tickets           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_messages_owner_access    ON support_messages          FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY kb_articles_owner_access         ON kb_articles               FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY kb_versions_owner_access         ON kb_versions               FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_drafts_owner_access      ON support_drafts            FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_citations_owner_access   ON support_draft_citations   FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_replies_owner_access     ON support_replies           FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_flags_owner_access       ON support_flags             FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_escalations_owner_access ON support_escalations       FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY support_events_owner_access      ON support_events            FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);

-- دور الويب: قراءة صفوف صاحب الجلسة وحدها. لا INSERT ولا UPDATE ولا DELETE على أيّ جدول.
-- support_ticket_transition بلا سياسة لدور الويب: تُقرأ عبر الدوالّ.
CREATE POLICY support_settings_own    ON support_settings        FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_sla_own         ON support_sla_targets     FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_tickets_own     ON support_tickets         FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_messages_own    ON support_messages        FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY kb_articles_own         ON kb_articles             FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY kb_versions_own         ON kb_versions             FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_drafts_own      ON support_drafts          FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_citations_own   ON support_draft_citations FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_replies_own     ON support_replies         FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_flags_own       ON support_flags           FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_escalations_own ON support_escalations     FOR SELECT TO eyework_app USING (user_id = ew_current_user());
CREATE POLICY support_events_own      ON support_events          FOR SELECT TO eyework_app USING (user_id = ew_current_user());

GRANT SELECT ON support_settings, support_sla_targets, support_tickets, support_messages,
                kb_articles, kb_versions, support_drafts, support_draft_citations, support_replies, support_flags,
                support_escalations, support_events TO eyework_app;

-- دوالّ القيود تُستدعى بصلاحية من يكتب ومن يقرأ الأعمدة المولّدة، فتُمنح لدور الويب وحده.
REVOKE ALL ON FUNCTION ew_support_text_ok(text, boolean), ew_support_contact_free(text), ew_support_kb_clean(text),
                       ew_kb_norm(text), ew_support_priority_for(text, text, boolean), ew_support_priority_rank(text)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ew_support_text_ok(text, boolean), ew_support_contact_free(text),
                          ew_support_kb_clean(text), ew_kb_norm(text), ew_support_priority_for(text, text, boolean),
                          ew_support_priority_rank(text) TO eyework_app;

-- دوالّ المحفّزات والداخلية لا يستدعيها دور الويب.
REVOKE ALL ON FUNCTION ew_support_settings_defaults(), ew_support_ticket_insert_guard(),
                       ew_support_ticket_update_guard(), ew_support_ticket_status_event(),
                       ew_support_message_insert_guard(), ew_support_draft_insert_guard(),
                       ew_support_draft_update_guard(), ew_support_citation_guard(), ew_support_draft_grounded(),
                       ew_support_reply_insert_guard(), ew_support_reply_update_guard(),
                       ew_support_flag_insert_guard(), ew_support_flag_update_guard(), ew_kb_article_insert_guard(),
                       ew_kb_article_update_guard(), ew_kb_version_insert_guard(),
                       ew_support_me(boolean), ew_support_require_notice(uuid), ew_support_ticket_for(uuid, uuid, integer),
                       ew_support_log(uuid, uuid, uuid, text, text, uuid, uuid, uuid, text),
                       ew_kb_version_digest(uuid, smallint), ew_support_request_for(uuid, uuid, text),
                       ew_support_event_update_guard(), ew_support_events_keep()
    FROM PUBLIC;

-- واجهة دور الويب.
REVOKE ALL ON FUNCTION
    ew_support_accept_notice(text), ew_support_save_settings(text, jsonb),
    ew_support_create_ticket(uuid, text, text, text, text, text, text, smallint),
    ew_support_add_message(uuid, integer, text, text, smallint, uuid),
    ew_support_set_ticket(uuid, integer, text, text, text, uuid),
    ew_support_begin_draft(uuid, integer),
    ew_support_record_draft(uuid, uuid, text, text, text, text, text, text, text, text, boolean, text, text, text[],
                            text, uuid, jsonb, jsonb),
    ew_support_finish_call(uuid, text, jsonb),
    ew_support_reject_draft(uuid, text, text),
    ew_support_prepare_reply(uuid, integer, uuid, uuid, text, boolean, text, text, jsonb, uuid[]),
    ew_support_review_begin(uuid),
    ew_support_review_record(uuid, jsonb, jsonb),
    ew_support_ack_flag(uuid, text, text),
    ew_support_release_reply(uuid, text, bytea),
    ew_support_confirm_reply(uuid, boolean),
    ew_support_escalate(uuid, integer, text, text),
    ew_support_return_escalation(uuid, integer, text),
    ew_support_resolve(uuid, integer, text, boolean),
    ew_support_reopen(uuid, integer),
    ew_support_follow_up(uuid, uuid, text, smallint),
    ew_support_close_due(),
    ew_kb_create(uuid, text, text, text, text, text, uuid),
    ew_kb_add_version(uuid, integer, text, text, text, text, text),
    ew_kb_publish(uuid, integer, smallint),
    ew_kb_set_state(uuid, integer, text),
    ew_kb_mark_review(uuid, integer, boolean),
    ew_kb_search(text, integer),
    ew_kb_review_begin(uuid, smallint),
    ew_kb_current_digest(uuid),
    ew_kb_review_record(uuid, jsonb, jsonb)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    ew_support_accept_notice(text), ew_support_save_settings(text, jsonb),
    ew_support_create_ticket(uuid, text, text, text, text, text, text, smallint),
    ew_support_add_message(uuid, integer, text, text, smallint, uuid),
    ew_support_set_ticket(uuid, integer, text, text, text, uuid),
    ew_support_begin_draft(uuid, integer),
    ew_support_record_draft(uuid, uuid, text, text, text, text, text, text, text, text, boolean, text, text, text[],
                            text, uuid, jsonb, jsonb),
    ew_support_finish_call(uuid, text, jsonb),
    ew_support_reject_draft(uuid, text, text),
    ew_support_prepare_reply(uuid, integer, uuid, uuid, text, boolean, text, text, jsonb, uuid[]),
    ew_support_review_begin(uuid),
    ew_support_review_record(uuid, jsonb, jsonb),
    ew_support_ack_flag(uuid, text, text),
    ew_support_release_reply(uuid, text, bytea),
    ew_support_confirm_reply(uuid, boolean),
    ew_support_escalate(uuid, integer, text, text),
    ew_support_return_escalation(uuid, integer, text),
    ew_support_resolve(uuid, integer, text, boolean),
    ew_support_reopen(uuid, integer),
    ew_support_follow_up(uuid, uuid, text, smallint),
    ew_support_close_due(),
    ew_kb_create(uuid, text, text, text, text, text, uuid),
    ew_kb_add_version(uuid, integer, text, text, text, text, text),
    ew_kb_publish(uuid, integer, smallint),
    ew_kb_set_state(uuid, integer, text),
    ew_kb_mark_review(uuid, integer, boolean),
    ew_kb_search(text, integer),
    ew_kb_review_begin(uuid, smallint),
    ew_kb_current_digest(uuid),
    ew_kb_review_record(uuid, jsonb, jsonb)
TO eyework_app;
