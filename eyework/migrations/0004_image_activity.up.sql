-- ════════════════════════════════════════════════════════════════════════
-- 0004_image_activity — متى تغيّرت الصورة
-- ════════════════════════════════════════════════════════════════════════
-- استبدال صورة المسودة لا يغيّر الحملة نفسها (row_version لا يزيد عمداً)،
-- فكان `purge` يرى مسودةً عُمل عليها اليوم خاملةً منذ إنشائها ويحذفها. الصورة
-- تحمل الآن وقت آخر تغيير، ويحسب `purge` الخمول من آخر نشاطٍ أيّاً كان.
-- ════════════════════════════════════════════════════════════════════════

ALTER TABLE campaign_images ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
UPDATE campaign_images SET updated_at = created_at;

CREATE FUNCTION ew_image_touch() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION ew_image_touch() FROM PUBLIC;
CREATE TRIGGER trg_image_touch BEFORE UPDATE ON campaign_images
    FOR EACH ROW EXECUTE FUNCTION ew_image_touch();
