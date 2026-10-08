-- ════════════════════════════════════════════════════════════════════════
-- 0005_registration — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- الدالّتان كما كانتا في 0002، حرفاً بحرف.
CREATE OR REPLACE FUNCTION ew_campaign_insert_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF NEW.status <> 'DRAFT' OR NEW.row_version <> 1 OR NEW.current_version_id IS NOT NULL
       OR NEW.approved_version_id IS NOT NULL OR NEW.budget_sar IS NOT NULL OR NEW.days IS NOT NULL
       OR NEW.approved_at IS NOT NULL OR NEW.ready_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'draft' USING ERRCODE = 'check_violation', CONSTRAINT = 'campaign_starts_as_draft';
    END IF;
    -- قفلٌ على المستخدم يمنع حملتين متزامنتين من تجاوز السقف معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.user_id::text, 0));
    IF (SELECT count(*) FROM campaigns
         WHERE user_id = NEW.user_id AND status IN ('DRAFT','COPY_PROPOSED','COPY_APPROVED')) >= 20 THEN
        RAISE EXCEPTION 'cap' USING ERRCODE = 'check_violation', CONSTRAINT = 'open_campaign_cap';
    END IF;
    NEW.created_at := now();
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO c FROM campaigns WHERE id = p_campaign AND user_id = uid FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'campaign' USING ERRCODE = 'no_data_found';
    END IF;
    IF c.row_version <> p_expected_row_version THEN
        RAISE EXCEPTION 'stale' USING ERRCODE = 'check_violation', CONSTRAINT = 'stale_row_version';
    END IF;
    IF p_kind NOT IN ('INITIAL','EDIT')
       OR (p_kind = 'INITIAL' AND (c.status <> 'DRAFT' OR p_expected_version IS NOT NULL))
       OR (p_kind = 'EDIT' AND (c.status <> 'COPY_PROPOSED' OR c.current_version_id IS DISTINCT FROM p_expected_version)) THEN
        RAISE EXCEPTION 'state' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_wrong_state';
    END IF;
    SELECT sha256 INTO image FROM campaign_images WHERE campaign_id = p_campaign;
    IF image IS NULL THEN
        RAISE EXCEPTION 'image' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_needs_image';
    END IF;
    IF EXISTS (SELECT 1 FROM generation_attempts
                WHERE user_id = uid AND finished_at IS NULL
                  AND started_at > now() - interval '5 minutes') THEN
        RAISE EXCEPTION 'busy' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_in_progress';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND started_at > now() - interval '10 minutes') >= 6 THEN
        RAISE EXCEPTION 'rate' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_rate';
    END IF;
    IF (SELECT count(*) FROM generation_attempts
         WHERE user_id = uid AND ew_is_billable(outcome)
           AND started_at > now() - interval '24 hours') >= 40 THEN
        RAISE EXCEPTION 'daily' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_daily_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;

DROP FUNCTION IF EXISTS ew_delete_me();
DROP FUNCTION IF EXISTS ew_my_profession();
DROP FUNCTION IF EXISTS ew_register(bytea, bytea, text, text, date, text, text);
DROP FUNCTION IF EXISTS ew_signup_code_usable(bytea);
DROP FUNCTION IF EXISTS ew_riyadh_today();

DROP TABLE IF EXISTS signup_codes;
DROP TRIGGER IF EXISTS trg_attempt_tombstone ON generation_attempts;
DROP FUNCTION IF EXISTS ew_attempt_tombstone();
DROP TABLE IF EXISTS attempt_tombstones;

ALTER TABLE users DROP CONSTRAINT IF EXISTS self_registered_accepted_terms;
ALTER TABLE users DROP CONSTRAINT IF EXISTS terms_complete;
ALTER TABLE users DROP COLUMN IF EXISTS terms_accepted_at;
ALTER TABLE users DROP COLUMN IF EXISTS terms_version;
ALTER TABLE users DROP COLUMN IF EXISTS self_registered;
ALTER TABLE users DROP COLUMN IF EXISTS birth_date;
ALTER TABLE users DROP COLUMN IF EXISTS profession;

DROP TABLE IF EXISTS professions;
