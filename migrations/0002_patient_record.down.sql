-- ════════════════════════════════════════════════════════════════════════
-- 0002_patient_record — تراجع
-- ════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_red_flag_audit     ON red_flag_reports;
DROP TRIGGER IF EXISTS trg_red_flag_immutable ON red_flag_reports;
DROP TRIGGER IF EXISTS trg_session_immutable  ON patient_sessions;
DROP TRIGGER IF EXISTS trg_session_plan_belongs_to_patient ON patient_sessions;
DROP TRIGGER IF EXISTS trg_session_local_day  ON patient_sessions;

DROP FUNCTION IF EXISTS audit_red_flag_change();
DROP FUNCTION IF EXISTS forbid_red_flag_rewrite();
DROP FUNCTION IF EXISTS forbid_session_mutation();
DROP FUNCTION IF EXISTS check_session_plan();
DROP FUNCTION IF EXISTS set_session_local_day();

DROP TABLE IF EXISTS red_flag_reports;
DROP TABLE IF EXISTS patient_sessions;

DROP FUNCTION IF EXISTS local_day(timestamptz);

-- استعادة دالة تدقيق المقترحات كما عرّفها الترحيل 0001، وصلاحية الكتابة معها.
CREATE OR REPLACE FUNCTION audit_proposal_change() RETURNS trigger
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

GRANT INSERT ON audit_log TO app_practitioner;
