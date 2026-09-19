-- ════════════════════════════════════════════════════════════════════════
-- 0001_foundation — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُعيد المخطط إلى ما كان عليه بالضبط. مُختبَر في الاتجاهين بمقارنة لقطة
-- `pg_dump --schema-only` قبل وبعد (معيار القبول 10).
--
-- الأدوار لا تُحذف هنا: هي على مستوى العنقود وقد تملك كائنات في قواعد أخرى.
-- تُسحب صلاحياتها على هذه القاعدة فقط.
-- ════════════════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS patient_deliverable_v;

DROP TRIGGER IF EXISTS trg_proposal_audit      ON proposals;
DROP TRIGGER IF EXISTS trg_proposal_transition ON proposals;
DROP TRIGGER IF EXISTS trg_proposal_expiry     ON proposals;
DROP TRIGGER IF EXISTS trg_audit_append_only   ON audit_log;

DROP FUNCTION IF EXISTS audit_proposal_change();
DROP FUNCTION IF EXISTS forbid_audit_mutation();
DROP FUNCTION IF EXISTS enforce_proposal_transition();
DROP FUNCTION IF EXISTS set_proposal_expiry();

-- السياسات تسقط مع جداولها، لكن نصرّح بها ليبقى التراجع مقروءاً.
DROP POLICY IF EXISTS versions_owner_access       ON proposal_versions;
DROP POLICY IF EXISTS versions_tenant_isolation   ON proposal_versions;
DROP POLICY IF EXISTS patients_owner_access       ON patients;
DROP POLICY IF EXISTS patients_tenant_isolation   ON patients;
DROP POLICY IF EXISTS proposals_owner_access      ON proposals;
DROP POLICY IF EXISTS proposals_tenant_isolation  ON proposals;

DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS proposal_versions;
DROP TABLE IF EXISTS proposals;
DROP TABLE IF EXISTS proposal_transition;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tenants;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_practitioner') THEN
        EXECUTE format('REVOKE ALL ON SCHEMA public FROM app_practitioner');
        EXECUTE format('REVOKE ALL ON DATABASE %I FROM app_practitioner', current_database());
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_patient') THEN
        EXECUTE format('REVOKE ALL ON SCHEMA public FROM app_patient');
        EXECUTE format('REVOKE ALL ON DATABASE %I FROM app_patient', current_database());
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO PUBLIC;
