-- ════════════════════════════════════════════════════════════════════════
-- NEXT_marketing (تراجع)
-- ════════════════════════════════════════════════════════════════════════
-- التراجع يمحو عمل مستخدمي التسويق كلّه، فيرفض ما دامت في القاعدة حملةٌ واحدة: من أراد
-- ذلك يحذفها عمداً أولاً. واستدعاءات المراجعة تُحذف قبل الجداول فتترك آثارها بلا هوية
-- (ew_mkt_review_tombstone)، فلا يُفرغ التراجعُ السقفَ العام.
-- ════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM mkt_campaigns) THEN
        RAISE EXCEPTION 'في القاعدة حملاتٌ من مساحة التسويق، والتراجع يمحوها. احذفها عمداً أولاً إن كان هذا المقصود.';
    END IF;
END
$$;

DELETE FROM mkt_review_calls;

-- ew_begin_generation كما كتبها NEXT_open_registration، حرفاً بحرف.
CREATE OR REPLACE FUNCTION ew_begin_generation(
    p_campaign uuid, p_kind text, p_expected_row_version integer, p_expected_version uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    uid     uuid := ew_current_user();
    c       campaigns%ROWTYPE;
    image   bytea;
    attempt uuid;
    fresh   boolean;
BEGIN
    PERFORM 1 FROM users WHERE id = uid AND is_active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- الكلفة تُفرض حيث تقع: حسابٌ نُقل إلى مهنةٍ أخرى لا يكتب لحملةٍ قديمة.
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = uid AND profession = 'MARKETING') THEN
        RAISE EXCEPTION 'profession' USING ERRCODE = 'insufficient_privilege',
                                           CONSTRAINT = 'campaign_needs_marketing';
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
    -- الحساب المفتوح الجديد: عشرة في اليوم. وقفل صفّ المستخدم أعلاه يجعل العدّ والإدراج ذرّيين.
    fresh := ew_new_open_account(uid);
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE user_id = uid AND ew_is_billable(outcome)
                     AND started_at > now() - interval '24 hours') >= 10 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_account_cap';
    END IF;
    -- السقف العام يجمع كل المستخدمين، وقفل صفّ المستخدم لا يجمعهم: بلا قفلٍ
    -- واحدٍ للجميع يرى طلبان متزامنان لمستخدمَين العدَّ نفسه ويمرّان معاً.
    PERFORM pg_advisory_xact_lock(hashtextextended('eyework.generation_global_cap', 0));
    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN
        RAISE EXCEPTION 'global' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_global_cap';
    END IF;
    -- حصّة الحسابات الجديدة كلّها من السقف العام، تحت القفل نفسه. أثر المحاولة
    -- المحذوفة يُعدّ فيها أيضاً.
    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN
        RAISE EXCEPTION 'new' USING ERRCODE = 'check_violation', CONSTRAINT = 'generation_new_accounts_cap';
    END IF;
    IF (SELECT count(*) FROM copy_versions WHERE campaign_id = p_campaign) >= 10 THEN
        RAISE EXCEPTION 'versions' USING ERRCODE = 'check_violation', CONSTRAINT = 'version_cap';
    END IF;

    INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256, new_account)
    VALUES (p_campaign, uid, p_kind, p_expected_version, image, fresh)
    RETURNING id INTO attempt;
    RETURN attempt;
END
$$;


DROP FUNCTION ew_mkt_review_begin(uuid);
DROP FUNCTION ew_mkt_review_record(uuid, text[], text[], text[], integer, integer, text, text, text);
DROP FUNCTION ew_mkt_review_finish(uuid, text, integer, integer, text, text);
DROP FUNCTION ew_ai_spend(boolean);
DROP FUNCTION ew_mkt_results_save(uuid, text, uuid, integer, date, date, bigint, bigint, bigint, bigint, bigint, bigint, text[]);
DROP FUNCTION ew_mkt_item_transition(uuid, integer, text, text[], timestamptz);
DROP FUNCTION ew_mkt_item_save(uuid, integer, text, date, time, text, text[], bigint);
DROP FUNCTION ew_mkt_item_create(uuid, text, date, time, text, text[], bigint, uuid);
DROP FUNCTION ew_mkt_campaign_transition(uuid, integer, text, text[]);
DROP FUNCTION ew_mkt_set_channels(uuid, integer, text[], bigint[]);
DROP FUNCTION ew_mkt_campaign_save(uuid, integer, text, text, text, text, bigint, text, bigint, date, date);
DROP FUNCTION ew_mkt_campaign_create(text);
DROP FUNCTION ew_mkt_lock_campaign(uuid, uuid, integer);
DROP FUNCTION ew_mkt_require();
DROP FUNCTION ew_mkt_results_flags(uuid, text, uuid, bigint);
DROP FUNCTION ew_mkt_campaign_flags(uuid);
DROP FUNCTION ew_mkt_item_flags(uuid);

DROP TABLE mkt_ai_flags;
DROP TABLE mkt_review_calls;
DROP TABLE mkt_results;
DROP TABLE mkt_items;
DROP TABLE mkt_campaign_channels;
DROP TABLE mkt_campaigns;
DROP TABLE mkt_item_transition;
DROP TABLE mkt_campaign_transition;

DROP FUNCTION ew_mkt_review_tombstone();
DROP FUNCTION ew_mkt_results_guard();
DROP FUNCTION ew_mkt_item_guard();
DROP FUNCTION ew_mkt_item_insert_guard();
DROP FUNCTION ew_mkt_allocations_check();
DROP FUNCTION ew_mkt_channel_guard();
DROP FUNCTION ew_mkt_campaign_guard();
DROP FUNCTION ew_mkt_campaign_insert_guard();
DROP FUNCTION ew_mkt_same_keys(text[], text[]);
DROP FUNCTION ew_mkt_kpi_fits(text, text);
DROP FUNCTION ew_mkt_channel_known(text);
DROP FUNCTION ew_mkt_text_ok(text, boolean);
