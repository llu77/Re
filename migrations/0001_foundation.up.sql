-- ════════════════════════════════════════════════════════════════════════
-- 0001_foundation — بوابة اعتماد الممارس
-- ════════════════════════════════════════════════════════════════════════
-- الضمانة المركزية: لا يصل محتوى سريري إلى المريض دون اعتماد صريح من ممارس
-- مرخّص. تُفرض هنا، في طبقة البيانات، عبر نقطة عبور واحدة — لا في الواجهة.
--
-- ما يمنعه هذا الملف بنيوياً، لا باتفاق:
--   • دور المريض بلا أي صلاحية على جداول المحتوى. المسار الالتفافي مستحيل
--     لا ممنوع.
--   • الانتقالات آلة حالات في جدول، يفرضها محفّز يرمي استثناءً.
--   • الرفض بلا سبب، والاعتماد بلا مراجِع، والصورة بلا جانب — كلها قيود CHECK.
--   • سجل التدقيق append-only بمحفّز، لأن المالك يتجاوز الصلاحيات لا المحفّزات.
-- ════════════════════════════════════════════════════════════════════════

-- ── الأدوار ─────────────────────────────────────────────────────────────
-- على مستوى العنقود، ولذلك تُنشأ بحراسة. كلمات المرور للتطوير فقط؛ في
-- الإنتاج تُدار خارج الترحيل.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_practitioner') THEN
        CREATE ROLE app_practitioner LOGIN PASSWORD 'dev_practitioner';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_patient') THEN
        CREATE ROLE app_patient LOGIN PASSWORD 'dev_patient';
    END IF;
END
$$;

-- اسم القاعدة لا يقبل CURRENT_CATALOG في GRANT؛ يلزم معرّف حرفي.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_practitioner, app_patient',
                   current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO app_practitioner, app_patient;

-- الافتراض: لا صلاحية لأحد. كل منح لاحق صريح ومقصود.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO PUBLIC;

-- ── المستأجرون والمستخدمون ──────────────────────────────────────────────
CREATE TABLE tenants (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    role           text NOT NULL CHECK (role IN ('PRACTITIONER','ADMIN','PATIENT','CAREGIVER')),
    email          text NOT NULL,
    password_hash  text NOT NULL,
    license_number text,
    is_active      boolean NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email),
    -- ممارس بلا رقم ترخيص لا يعتمد شيئاً
    CONSTRAINT practitioner_is_licensed
        CHECK (role <> 'PRACTITIONER' OR nullif(btrim(license_number), '') IS NOT NULL)
);

-- بوابتان بمصادقة مستقلة: جلسة بوابة لا تصلح للأخرى.
CREATE TABLE sessions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gate        text NOT NULL CHECK (gate IN ('PRACTITIONER','PATIENT')),
    token_hash  text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    CONSTRAINT session_outlives_creation CHECK (expires_at > created_at)
);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE patients (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    file_number  bigint NOT NULL,
    user_id      uuid REFERENCES users(id) ON DELETE SET NULL,
    display_name text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, file_number)
);

-- ── آلة الحالات ─────────────────────────────────────────────────────────
-- جدول لا ثوابت في الكود: المحفّز يقرؤه، واختبار يقارنه بـcore/types.py.
CREATE TABLE proposal_transition (
    from_status text NOT NULL,
    to_status   text NOT NULL,
    PRIMARY KEY (from_status, to_status)
);

INSERT INTO proposal_transition (from_status, to_status) VALUES
    ('DRAFT',   'PENDING'),
    ('PENDING', 'APPROVED'),
    ('PENDING', 'EDITED_APPROVED'),
    ('PENDING', 'REJECTED'),
    ('PENDING', 'EXPIRED');

-- ── المقترحات ───────────────────────────────────────────────────────────
CREATE TABLE proposals (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    patient_id       uuid NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    kind             text NOT NULL CHECK (kind IN
                         ('PLAN','PLAN_UPDATE','ILLUSTRATION_SET','READINESS','DOCUMENTATION')),
    status           text NOT NULL DEFAULT 'DRAFT' CHECK (status IN
                         ('DRAFT','PENDING','APPROVED','EDITED_APPROVED','REJECTED','EXPIRED')),
    payload          jsonb NOT NULL,
    provenance       jsonb NOT NULL DEFAULT '{}'::jsonb,
    affected_side    text CHECK (affected_side IN ('LEFT','RIGHT','BILATERAL')),
    priority         smallint NOT NULL DEFAULT 5 CHECK (priority BETWEEN 0 AND 9),
    is_red_flag      boolean NOT NULL DEFAULT false,
    version          integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    queued_at        timestamptz,
    expires_at       timestamptz NOT NULL,
    reviewer_id      uuid REFERENCES users(id) ON DELETE RESTRICT,
    decision_at      timestamptz,
    rejection_reason text,

    -- زمن المراجعة: من دخول الطابور إلى القرار. الطرح immutable فيصلح مولَّداً.
    review_seconds   double precision
                     GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (decision_at - queued_at))) STORED,

    -- الرفض يتطلب سبباً نصياً إلزامياً
    CONSTRAINT rejection_needs_reason CHECK (
        status <> 'REJECTED' OR nullif(btrim(rejection_reason), '') IS NOT NULL),

    -- كل قرار منسوب إلى مراجِع مسمّى وبوقت
    CONSTRAINT decision_needs_reviewer CHECK (
        status NOT IN ('APPROVED','EDITED_APPROVED','REJECTED')
        OR (reviewer_id IS NOT NULL AND decision_at IS NOT NULL)),

    -- القاعدة 4: الجانب المصاب غير قابل للقيمة الفارغة في أي محتوى مصوَّر
    CONSTRAINT illustration_needs_side CHECK (
        kind <> 'ILLUSTRATION_SET' OR affected_side IS NOT NULL),

    -- ما دخل الطابور له وقت دخول
    CONSTRAINT queued_before_decision CHECK (
        decision_at IS NULL OR (queued_at IS NOT NULL AND decision_at >= queued_at))
);

CREATE INDEX proposals_queue_idx
    ON proposals (tenant_id, is_red_flag DESC, priority, queued_at)
    WHERE status = 'PENDING';
CREATE INDEX proposals_patient_idx ON proposals (patient_id, kind);

-- التعديل قبل الاعتماد يُحفظ كنسخة جديدة ولا يطمس الأصل.
CREATE TABLE proposal_versions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id   uuid NOT NULL REFERENCES proposals(id) ON DELETE RESTRICT,
    version       integer NOT NULL CHECK (version >= 1),
    payload       jsonb NOT NULL,
    affected_side text CHECK (affected_side IN ('LEFT','RIGHT','BILATERAL')),
    edited_by     uuid REFERENCES users(id) ON DELETE SET NULL,
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, version)
);

-- ── سجل التدقيق ─────────────────────────────────────────────────────────
CREATE TABLE audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_id    uuid,
    tenant_id   uuid,
    entity      text NOT NULL,
    entity_id   uuid NOT NULL,
    action      text NOT NULL,
    from_status text,
    to_status   text,
    reason      text,
    detail      jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX audit_log_entity_idx ON audit_log (entity, entity_id, occurred_at);

-- ── المحفّزات ───────────────────────────────────────────────────────────

-- انتهاء الصلاحية: 48 ساعة. لا يصلح عموداً مولَّداً ولا قيد CHECK لأن
-- `timestamptz + interval` مُصنَّفة STABLE لا IMMUTABLE.
CREATE FUNCTION set_proposal_expiry() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.expires_at := NEW.created_at + interval '48 hours';
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_proposal_expiry
    BEFORE INSERT ON proposals
    FOR EACH ROW EXECUTE FUNCTION set_proposal_expiry();

-- الانتقالات: ما ليس في الجدول يرمي خطأ. الحالات النهائية لا تُعدَّل إطلاقاً.
CREATE FUNCTION enforce_proposal_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        IF NOT EXISTS (SELECT 1 FROM proposal_transition WHERE from_status = OLD.status) THEN
            RAISE EXCEPTION 'حالة نهائية غير قابلة للتعديل: %', OLD.status
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM proposal_transition
        WHERE from_status = OLD.status AND to_status = NEW.status
    ) THEN
        RAISE EXCEPTION 'انتقال غير مسموح: % ← %', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER trg_proposal_transition
    BEFORE UPDATE ON proposals
    FOR EACH ROW EXECUTE FUNCTION enforce_proposal_transition();

-- سجل التدقيق: append-only. المحفّز هو الحارس الفعلي لأن المالك يتجاوز
-- الصلاحيات ولا يتجاوز المحفّزات.
CREATE FUNCTION forbid_audit_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'سجل التدقيق append-only: % ممنوع', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER trg_audit_append_only
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;

-- كل انتقال يُسجَّل: من · ماذا · متى · لماذا.
CREATE FUNCTION audit_proposal_change() RETURNS trigger
LANGUAGE plpgsql AS $$
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

CREATE TRIGGER trg_proposal_audit
    AFTER INSERT OR UPDATE ON proposals
    FOR EACH ROW EXECUTE FUNCTION audit_proposal_change();

-- ── نقطة العبور الوحيدة ─────────────────────────────────────────────────
-- تقرأ الحالة وترفض ما ليس APPROVED أو EDITED_APPROVED، وتسقط المنتهي.
-- تعمل بصلاحيات مالكها، فدور المريض يصل إليها دون أي صلاحية على الجدول.
CREATE VIEW patient_deliverable_v WITH (security_barrier) AS
SELECT
    p.id AS proposal_id,
    p.patient_id,
    p.kind,
    p.payload,
    p.affected_side,
    p.decision_at AS approved_at
FROM proposals p
WHERE p.status IN ('APPROVED', 'EDITED_APPROVED')
  AND p.expires_at > now()
  AND p.patient_id = nullif(current_setting('app.patient_id', true), '')::uuid;

-- المريض: العرض فقط. لا شيء غيره.
REVOKE ALL ON proposals, proposal_versions, proposal_transition,
              patients, users, sessions, tenants, audit_log
    FROM app_patient;
GRANT SELECT ON patient_deliverable_v TO app_patient;

-- الممارس: عمل على المقترحات تحت عزل الصفوف.
GRANT SELECT, INSERT, UPDATE ON proposals TO app_practitioner;
GRANT SELECT, INSERT ON proposal_versions TO app_practitioner;
GRANT SELECT ON patients, users, proposal_transition TO app_practitioner;
GRANT SELECT, INSERT ON audit_log TO app_practitioner;

-- ── عزل الصفوف ──────────────────────────────────────────────────────────
-- FORCE ليخضع المالك أيضاً — وإلا كان العزل اتفاقاً لا ضمانة.
ALTER TABLE proposals         ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals         FORCE  ROW LEVEL SECURITY;
ALTER TABLE patients          ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients          FORCE  ROW LEVEL SECURITY;
ALTER TABLE proposal_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_versions FORCE  ROW LEVEL SECURITY;

CREATE POLICY proposals_tenant_isolation ON proposals
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY patients_tenant_isolation ON patients
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY versions_tenant_isolation ON proposal_versions
    FOR ALL TO app_practitioner
    USING (EXISTS (
        SELECT 1 FROM proposals p
        WHERE p.id = proposal_versions.proposal_id
          AND p.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid));

-- مالك المخطط يحتاج مروراً خاصاً به بعد FORCE، وإلا تعطّلت الترحيلات وقراءة
-- العرض. مقيّد بالدور المالك وحده.
CREATE POLICY proposals_owner_access ON proposals
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY patients_owner_access ON patients
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY versions_owner_access ON proposal_versions
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
