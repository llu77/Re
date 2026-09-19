-- ════════════════════════════════════════════════════════════════════════
-- 0003_caregiver_consent — تراجع
-- ════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_caregiver_link_audit ON caregiver_links;
DROP TRIGGER IF EXISTS trg_caregiver_revocation_closes_sessions ON caregiver_links;
DROP TRIGGER IF EXISTS trg_caregiver_link_immutable ON caregiver_links;
DROP TRIGGER IF EXISTS trg_caregiver_link_is_sound ON caregiver_links;

DROP FUNCTION IF EXISTS audit_caregiver_link_change();
DROP FUNCTION IF EXISTS close_caregiver_sessions();
DROP FUNCTION IF EXISTS forbid_caregiver_link_rewrite();
DROP FUNCTION IF EXISTS check_caregiver_link();

DROP TABLE IF EXISTS caregiver_links;
