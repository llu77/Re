-- ════════════════════════════════════════════════════════════════════════
-- 0004_image_activity — تراجع
-- ════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS trg_image_touch ON campaign_images;
DROP FUNCTION IF EXISTS ew_image_touch();
ALTER TABLE campaign_images DROP COLUMN IF EXISTS updated_at;
