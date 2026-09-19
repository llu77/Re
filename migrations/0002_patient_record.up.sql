-- ════════════════════════════════════════════════════════════════════════
-- 0002_patient_record — أداء المريض وبلاغات العلامات الحمراء
-- ════════════════════════════════════════════════════════════════════════
-- تدقيق المرحلة 0: لا كيان جلسة في النظام إطلاقاً، ولا حساب التزام، ولا
-- أي قدرة على تصعيد علامة حمراء إلى إنسان. ما كان يُحفظ باسم «أداء» كان
-- مخرج مولّد أرقام عشوائية.
--
-- ثلاث ضمانات يفرضها هذا الملف في طبقة البيانات:
--   • حدود اليوم تعريف واحد: عمود `local_day` يملؤه محفّز من `occurred_at`
--     بتوقيت الرياض. لا مستدعٍ يحسبه بنفسه، فلا تختلف إجابة «هل أدّى جلسة
--     اليوم؟» باختلاف المسار.
--   • المزامنة المتأخرة بلا تكرار ولا فقد: `client_uuid` فريد لكل مريض،
--     فإعادة الإرسال بعد انقطاع لا تُضاعف السجل.
--   • كل فعل منسوب إلى من نفّذه: `recorded_by` غير قابل للقيمة الفارغة،
--     فوضع المرافق يبقى قابلاً للتمييز عن المريض نفسه.
-- ════════════════════════════════════════════════════════════════════════

-- ── حدود اليوم ──────────────────────────────────────────────────────────
-- نظير `core.clock.local_day` في SQL. لا يصلح عموداً مولَّداً لأن
-- `timestamptz AT TIME ZONE zone` مُصنَّفة STABLE لا IMMUTABLE.
-- `test_local_day_matches_python` يقارن التنفيذين فيمنع انحرافهما.
CREATE FUNCTION local_day(moment timestamptz) RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT (moment AT TIME ZONE 'Asia/Riyadh')::date
$$;

-- ── جلسات المريض ────────────────────────────────────────────────────────
CREATE TABLE patient_sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    patient_id    uuid NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,

    -- النسخة المعتمدة التي أُدّيت. بلا اعتماد لا توجد جلسة تُسجَّل أصلاً.
    plan_id       uuid NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
    step_index    smallint CHECK (step_index >= 0),

    outcome       text NOT NULL CHECK (outcome IN ('DONE', 'PARTIAL', 'UNABLE')),
    reason        text,
    difficulty    smallint CHECK (difficulty BETWEEN 0 AND 10),
    pain          smallint CHECK (pain BETWEEN 0 AND 10),

    -- متى أدّاها المريض. يأتي من الجهاز للعمل دون اتصال.
    occurred_at   timestamptz NOT NULL,
    -- متى استلمها الخادم. مصدر الثقة للترتيب.
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    -- اليوم التقويمي المحلي لـ`occurred_at`. يملؤه المحفّز.
    local_day     date NOT NULL,

    -- من نفّذ التسجيل: المريض أو مرافقه.
    recorded_by   uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    -- معرّف الجهاز للتسجيلة. يمنع تكرار المزامنة بعد انقطاع.
    client_uuid   uuid NOT NULL,

    UNIQUE (patient_id, client_uuid),

    -- تسجيل في المستقبل ليس مزامنة متأخرة بل ساعة جهاز خاطئة. نسمح بانحراف
    -- بسيط ونرفض ما عداه.
    CONSTRAINT occurred_is_not_in_the_future
        CHECK (occurred_at <= recorded_at + interval '5 minutes'),
    -- المزامنة المتأخرة مقبولة، والقِدَم المفرط ليس مزامنة.
    CONSTRAINT occurred_is_not_ancient
        CHECK (occurred_at >= recorded_at - interval '30 days')
);

CREATE INDEX patient_sessions_adherence_idx
    ON patient_sessions (patient_id, local_day);
CREATE INDEX patient_sessions_plan_idx ON patient_sessions (plan_id);

CREATE FUNCTION set_session_local_day() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.local_day := local_day(NEW.occurred_at);
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_session_local_day
    BEFORE INSERT OR UPDATE OF occurred_at ON patient_sessions
    FOR EACH ROW EXECUTE FUNCTION set_session_local_day();

-- الخطة المرتبطة يجب أن تخص هذا المريض وأن تكون معتمدة.
-- المفتاح الخارجي وحده لا يكفي: فحصه يتجاوز عزل الصفوف، فمعرّف خطة مريض
-- آخر كان يُقبل لو خُمِّن. والتسجيل على خطة لم تُعتمد يعني أداءً على محتوى
-- لم يصل المريض أصلاً.
CREATE FUNCTION check_session_plan() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    plan_patient uuid;
    plan_status  text;
BEGIN
    SELECT patient_id, status INTO plan_patient, plan_status
    FROM proposals WHERE id = NEW.plan_id;

    IF plan_patient IS DISTINCT FROM NEW.patient_id THEN
        RAISE EXCEPTION 'الخطة لا تخص هذا المريض'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF plan_status NOT IN ('APPROVED', 'EDITED_APPROVED') THEN
        RAISE EXCEPTION 'لا تُسجَّل جلسة على خطة غير معتمدة (%)', plan_status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_session_plan_belongs_to_patient
    BEFORE INSERT ON patient_sessions
    FOR EACH ROW EXECUTE FUNCTION check_session_plan();

-- الجلسة سجل واقعة. لا تُعدَّل ولا تُحذف — تصحيحها بتسجيل جديد.
CREATE FUNCTION forbid_session_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'سجل الجلسة غير قابل للتعديل: % ممنوع', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER trg_session_immutable
    BEFORE UPDATE OR DELETE ON patient_sessions
    FOR EACH ROW EXECUTE FUNCTION forbid_session_mutation();

-- ── بلاغات العلامات الحمراء ─────────────────────────────────────────────
-- ليست مقترحاً: لا شيء فيها يُعتمد ويُسلَّم. هي نداء يصل إنساناً، ويُقاس
-- زمن وصوله إليه.
CREATE TABLE red_flag_reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    patient_id      uuid NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,

    body            text NOT NULL,
    reported_by     uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reported_at     timestamptz NOT NULL DEFAULT now(),

    acknowledged_by uuid REFERENCES users(id) ON DELETE RESTRICT,
    acknowledged_at timestamptz,
    resolution_note text,

    -- زمن التصعيد: من البلاغ إلى استلام الممارس. مؤشر تقييم مخزَّن.
    escalation_seconds double precision
        GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (acknowledged_at - reported_at))) STORED,

    CONSTRAINT body_is_not_blank CHECK (nullif(btrim(body), '') IS NOT NULL),
    CONSTRAINT acknowledgement_is_complete CHECK (
        (acknowledged_by IS NULL) = (acknowledged_at IS NULL)),
    CONSTRAINT acknowledged_after_reported CHECK (
        acknowledged_at IS NULL OR acknowledged_at >= reported_at)
);

CREATE INDEX red_flags_open_idx
    ON red_flag_reports (tenant_id, reported_at)
    WHERE acknowledged_at IS NULL;

-- البلاغ لا يُحذف ولا يُعاد كتابته؛ يُستلَم فقط.
CREATE FUNCTION forbid_red_flag_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'بلاغ العلامة الحمراء غير قابل للحذف'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.body IS DISTINCT FROM OLD.body
       OR NEW.patient_id IS DISTINCT FROM OLD.patient_id
       OR NEW.reported_at IS DISTINCT FROM OLD.reported_at
       OR NEW.reported_by IS DISTINCT FROM OLD.reported_by THEN
        RAISE EXCEPTION 'لا يُعدَّل من البلاغ إلا الاستلام والمعالجة'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.acknowledged_at IS NOT NULL
       AND NEW.acknowledged_at IS DISTINCT FROM OLD.acknowledged_at THEN
        RAISE EXCEPTION 'البلاغ مُستلَم بالفعل' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_red_flag_immutable
    BEFORE UPDATE OR DELETE ON red_flag_reports
    FOR EACH ROW EXECUTE FUNCTION forbid_red_flag_rewrite();

-- كل بلاغ وكل استلام في سجل التدقيق.
--
-- SECURITY DEFINER: المحفّز يكتب بصلاحيات مالكه لا بصلاحيات المستدعي. بدونها
-- يفشل بلاغ المريض كلياً، لأن دور المريض ممنوع من `audit_log` عمداً — وهو
-- المنع الذي يجعل السجل غير قابل للتزوير. `search_path` مثبَّت لأن
-- SECURITY DEFINER بلا تثبيته باب لاختطاف الأسماء.
CREATE FUNCTION audit_red_flag_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    acting uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action, to_status)
        VALUES (coalesce(acting, NEW.reported_by), NEW.tenant_id, 'red_flag', NEW.id,
                'REPORT', 'OPEN');
    ELSIF OLD.acknowledged_at IS NULL AND NEW.acknowledged_at IS NOT NULL THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               from_status, to_status, reason)
        VALUES (coalesce(acting, NEW.acknowledged_by), NEW.tenant_id, 'red_flag', NEW.id,
                'ACKNOWLEDGE', 'OPEN', 'ACKNOWLEDGED', NEW.resolution_note);
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER trg_red_flag_audit
    AFTER INSERT OR UPDATE ON red_flag_reports
    FOR EACH ROW EXECUTE FUNCTION audit_red_flag_change();

-- ── تشديد سجل التدقيق ───────────────────────────────────────────────────
-- بعد أن صارت المحفّزات تكتب بصلاحيات مالكها، لم يعد أي دور تطبيق يحتاج
-- الكتابة المباشرة. سحبها يجعل السجل **غير قابل للتزوير** أيضاً، لا
-- append-only فحسب: لا مسار يكتب فيه صفاً إلا واقعة حقيقية.
CREATE OR REPLACE FUNCTION audit_proposal_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    acting uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               from_status, to_status, reason, detail)
        VALUES (coalesce(acting, NEW.created_by), NEW.tenant_id, 'proposal', NEW.id,
                'CREATE', NULL, NEW.status, NULL,
                jsonb_build_object('kind', NEW.kind, 'version', NEW.version));
    ELSIF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               from_status, to_status, reason, detail)
        VALUES (coalesce(acting, NEW.reviewer_id), NEW.tenant_id, 'proposal', NEW.id,
                'TRANSITION', OLD.status, NEW.status, NEW.rejection_reason,
                jsonb_build_object('kind', NEW.kind, 'version', NEW.version));
    END IF;
    RETURN NULL;
END
$$;

REVOKE INSERT ON audit_log FROM app_practitioner;

-- ── الصلاحيات ───────────────────────────────────────────────────────────
-- المريض يكتب جلساته وبلاغاته، ولا يقرأ شيئاً من جداول المحتوى.
GRANT INSERT ON patient_sessions  TO app_patient;
GRANT INSERT ON red_flag_reports  TO app_patient;
GRANT SELECT ON patient_sessions  TO app_patient;
GRANT SELECT ON red_flag_reports  TO app_patient;

GRANT SELECT, UPDATE ON red_flag_reports TO app_practitioner;
GRANT SELECT ON patient_sessions TO app_practitioner;

-- ── عزل الصفوف ──────────────────────────────────────────────────────────
ALTER TABLE patient_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_sessions  FORCE  ROW LEVEL SECURITY;
ALTER TABLE red_flag_reports  ENABLE ROW LEVEL SECURITY;
ALTER TABLE red_flag_reports  FORCE  ROW LEVEL SECURITY;

-- المريض: صفوفه هو، لا غير. الإعداد غائب ⇒ لا صفوف (فشل مغلق).
CREATE POLICY sessions_patient_scope ON patient_sessions
    FOR ALL TO app_patient
    USING      (patient_id = nullif(current_setting('app.patient_id', true), '')::uuid)
    WITH CHECK (patient_id = nullif(current_setting('app.patient_id', true), '')::uuid);

CREATE POLICY red_flags_patient_scope ON red_flag_reports
    FOR ALL TO app_patient
    USING      (patient_id = nullif(current_setting('app.patient_id', true), '')::uuid)
    WITH CHECK (patient_id = nullif(current_setting('app.patient_id', true), '')::uuid);

-- الممارس: مستأجره هو.
CREATE POLICY sessions_tenant_scope ON patient_sessions
    FOR ALL TO app_practitioner
    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY red_flags_tenant_scope ON red_flag_reports
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY sessions_owner_access ON patient_sessions
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY red_flags_owner_access ON red_flag_reports
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
