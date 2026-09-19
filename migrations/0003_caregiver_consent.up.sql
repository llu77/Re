-- ════════════════════════════════════════════════════════════════════════
-- 0003_caregiver_consent — وصول المرافق بموافقة موثَّقة
-- ════════════════════════════════════════════════════════════════════════
-- كثير من مرضى إعادة التأهيل لا يستخدمون البوابة وحدهم: زوج أو ابنة أو
-- مرافق مهني يفتح الخطة ويسجّل الأداء. النظام اليوم يرفضهم رفضاً صامتاً —
-- دور `CAREGIVER` موجود ويجتاز بوابة المريض، لكن `patient_id` يُشتق من
-- `patients.user_id` وحده، فيبقى فارغاً ويُردّ كل طلب بـ403.
--
-- ثلاث ضمانات يفرضها هذا الملف في طبقة البيانات:
--   • لا وصول لمرافق بلا صفّ موافقة: نصّ الموافقة، ومن أعطاها، والممارس
--     الذي وثّقها، ووقتها. الوصول **هو** الصفّ، فلا يوجد وصول بلا توثيق.
--   • السحب فوريّ ونهائيّ: صفّ مسحوب لا يُعاد تفعيله، وجلسات المرافق
--     المفتوحة تُبطَل في اللحظة نفسها.
--   • كل منح وكل سحب في سجل التدقيق، منسوباً إلى الممارس الذي نفّذه.
--
-- حدٌّ مقصود: مرافق واحد لا يخدم أكثر من مريض في آن. الفهرس الجزئي يمنع
-- الصفّ الثاني، فيفشل المنح أمام الممارس بدل أن يصير «أيّ المريضين؟» سؤالاً
-- يُجاب عليه بالتخمين عند تسجيل الدخول.
-- ════════════════════════════════════════════════════════════════════════

CREATE TABLE caregiver_links (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenants(id)  ON DELETE RESTRICT,
    patient_id        uuid NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    caregiver_user_id uuid NOT NULL REFERENCES users(id)    ON DELETE RESTRICT,

    -- صلة المرافق بالمريض كما وثّقها الممارس. نصّ حرّ عمداً: التصنيف المغلق
    -- يدفع إلى اختيار خانة خاطئة، والصلة تُقرأ ولا تُحسب.
    relationship      text NOT NULL,

    -- ── الموافقة ───────────────────────────────────────────────────────
    -- النصّ كما عُرض ووُقِّع، لا إشارة إليه: نسخة السياسة قد تتغيّر غداً
    -- وتبقى هذه الموافقة هي ما وافق عليه صاحبها فعلاً.
    consent_text      text NOT NULL,
    consent_given_by  text NOT NULL CHECK (consent_given_by IN ('PATIENT', 'GUARDIAN')),
    granted_by        uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    granted_at        timestamptz NOT NULL DEFAULT now(),

    revoked_at        timestamptz,
    revoked_by        uuid REFERENCES users(id) ON DELETE RESTRICT,

    CONSTRAINT relationship_is_not_blank
        CHECK (nullif(btrim(relationship), '') IS NOT NULL),
    CONSTRAINT consent_is_not_blank
        CHECK (nullif(btrim(consent_text), '') IS NOT NULL),
    CONSTRAINT revocation_is_complete
        CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
    CONSTRAINT revoked_after_granted
        CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

-- مرافق واحد ⇒ مريض واحد فاعل. يجعل اشتقاق سياق المريض في المصادقة قاطعاً.
CREATE UNIQUE INDEX one_active_patient_per_caregiver
    ON caregiver_links (caregiver_user_id) WHERE revoked_at IS NULL;

CREATE INDEX caregiver_links_patient_idx
    ON caregiver_links (patient_id) WHERE revoked_at IS NULL;

-- ── سلامة الصفّ ─────────────────────────────────────────────────────────
-- المفاتيح الخارجية لا تقول شيئاً عن الدور ولا عن المستأجر، وفحصها يتجاوز
-- عزل الصفوف أصلاً. بلا هذا المحفّز يصير معرّف مستخدمٍ مخمَّن وصولاً.
CREATE FUNCTION check_caregiver_link() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    caregiver_role   text;
    caregiver_tenant uuid;
    patient_tenant   uuid;
BEGIN
    SELECT role, tenant_id INTO caregiver_role, caregiver_tenant
    FROM users WHERE id = NEW.caregiver_user_id;

    IF caregiver_role IS DISTINCT FROM 'CAREGIVER' THEN
        RAISE EXCEPTION 'حساب المرافق يجب أن يكون بدور CAREGIVER لا %', caregiver_role
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT tenant_id INTO patient_tenant FROM patients WHERE id = NEW.patient_id;

    IF patient_tenant IS DISTINCT FROM NEW.tenant_id
       OR caregiver_tenant IS DISTINCT FROM NEW.tenant_id THEN
        RAISE EXCEPTION 'المرافق والمريض والصفّ يجب أن يكونوا في مستأجر واحد'
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER trg_caregiver_link_is_sound
    BEFORE INSERT ON caregiver_links
    FOR EACH ROW EXECUTE FUNCTION check_caregiver_link();

-- الموافقة سجل واقعة: لا تُعاد كتابتها ولا تُحذف. المتغيّر الوحيد هو السحب،
-- ومرة واحدة. تصحيح موافقة خاطئة يكون بسحبها ومنح موافقة جديدة.
CREATE FUNCTION forbid_caregiver_link_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'صفّ موافقة المرافق غير قابل للحذف'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.patient_id        IS DISTINCT FROM OLD.patient_id
       OR NEW.caregiver_user_id IS DISTINCT FROM OLD.caregiver_user_id
       OR NEW.tenant_id      IS DISTINCT FROM OLD.tenant_id
       OR NEW.relationship   IS DISTINCT FROM OLD.relationship
       OR NEW.consent_text   IS DISTINCT FROM OLD.consent_text
       OR NEW.consent_given_by IS DISTINCT FROM OLD.consent_given_by
       OR NEW.granted_by     IS DISTINCT FROM OLD.granted_by
       OR NEW.granted_at     IS DISTINCT FROM OLD.granted_at THEN
        RAISE EXCEPTION 'لا يُعدَّل من صفّ الموافقة إلا سحبه'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'الموافقة مسحوبة بالفعل ولا تُعاد' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER trg_caregiver_link_immutable
    BEFORE UPDATE OR DELETE ON caregiver_links
    FOR EACH ROW EXECUTE FUNCTION forbid_caregiver_link_rewrite();

-- السحب يُغلق الجلسات المفتوحة فوراً.
--
-- اشتقاق `patient_id` في المصادقة يقرأ هذا الجدول في كل طلب، فالوصول ينقطع
-- في الطلب التالي على أي حال. إبطال الجلسة هنا يجعل الانقطاع في طبقة
-- الجلسة أيضاً لا في طبقة الاشتقاق وحدها. SECURITY DEFINER لأن الممارس لا
-- يملك `sessions`.
CREATE FUNCTION close_caregiver_sessions() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    UPDATE sessions SET revoked_at = now()
    WHERE user_id = NEW.caregiver_user_id AND revoked_at IS NULL;
    RETURN NULL;
END
$$;

CREATE TRIGGER trg_caregiver_revocation_closes_sessions
    AFTER UPDATE OF revoked_at ON caregiver_links
    FOR EACH ROW WHEN (OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL)
    EXECUTE FUNCTION close_caregiver_sessions();

-- كل منح وكل سحب في السجل غير القابل للتزوير.
CREATE FUNCTION audit_caregiver_link_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    acting uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               to_status, reason, detail)
        VALUES (coalesce(acting, NEW.granted_by), NEW.tenant_id, 'caregiver_link', NEW.id,
                'GRANT', 'ACTIVE', NEW.relationship,
                jsonb_build_object('patient_id', NEW.patient_id,
                                   'caregiver_user_id', NEW.caregiver_user_id,
                                   'consent_given_by', NEW.consent_given_by));
    ELSIF OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL THEN
        INSERT INTO audit_log (actor_id, tenant_id, entity, entity_id, action,
                               from_status, to_status, detail)
        VALUES (coalesce(acting, NEW.revoked_by), NEW.tenant_id, 'caregiver_link', NEW.id,
                'REVOKE', 'ACTIVE', 'REVOKED',
                jsonb_build_object('patient_id', NEW.patient_id,
                                   'caregiver_user_id', NEW.caregiver_user_id));
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER trg_caregiver_link_audit
    AFTER INSERT OR UPDATE ON caregiver_links
    FOR EACH ROW EXECUTE FUNCTION audit_caregiver_link_change();

-- ── الصلاحيات ───────────────────────────────────────────────────────────
-- الممارس يمنح ويسحب ويقرأ. المريض ودور المرافق لا يلمسان الجدول: سياق
-- المريض يُشتق أثناء المصادقة بدور المالك، تماماً كما يُشتق من `patients`.
GRANT SELECT, INSERT, UPDATE ON caregiver_links TO app_practitioner;
REVOKE ALL ON caregiver_links FROM app_patient;

-- ── عزل الصفوف ──────────────────────────────────────────────────────────
ALTER TABLE caregiver_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_links FORCE  ROW LEVEL SECURITY;

CREATE POLICY caregiver_links_tenant_scope ON caregiver_links
    FOR ALL TO app_practitioner
    USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY caregiver_links_owner_access ON caregiver_links
    FOR ALL TO CURRENT_USER USING (true) WITH CHECK (true);
