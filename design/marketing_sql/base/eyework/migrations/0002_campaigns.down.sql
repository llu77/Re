-- ════════════════════════════════════════════════════════════════════════
-- 0002_campaigns — تراجع
-- ════════════════════════════════════════════════════════════════════════
-- يُعيد المخطّط إلى ما بعد 0001 بالضبط. السياسات والمحفّزات تسقط مع
-- جداولها، والدوالّ تُسقط صراحةً.
-- ════════════════════════════════════════════════════════════════════════

ALTER TABLE IF EXISTS generation_attempts DROP CONSTRAINT IF EXISTS attempt_base_belongs;
ALTER TABLE IF EXISTS campaigns DROP CONSTRAINT IF EXISTS approved_version_belongs;
ALTER TABLE IF EXISTS campaigns DROP CONSTRAINT IF EXISTS current_version_belongs;

DROP TABLE IF EXISTS campaign_images;
DROP TABLE IF EXISTS copy_versions;
DROP TABLE IF EXISTS generation_attempts;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS campaign_transition;

DROP FUNCTION IF EXISTS ew_finish_generation(uuid, text, integer, integer);
DROP FUNCTION IF EXISTS ew_begin_generation(uuid, text, integer, uuid);
DROP FUNCTION IF EXISTS ew_attempt_settle_once();
DROP FUNCTION IF EXISTS ew_forbid_update();
DROP FUNCTION IF EXISTS ew_version_becomes_current();
DROP FUNCTION IF EXISTS ew_version_insert_guard();
DROP FUNCTION IF EXISTS ew_image_guard();
DROP FUNCTION IF EXISTS ew_purge_image_on_cancel();
DROP FUNCTION IF EXISTS ew_campaign_guard();
DROP FUNCTION IF EXISTS ew_campaign_insert_guard();
DROP FUNCTION IF EXISTS ew_jpeg_has_no_metadata(bytea);
DROP FUNCTION IF EXISTS ew_is_billable(text);
DROP FUNCTION IF EXISTS ew_budget_allowed(integer);
