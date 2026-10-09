-- ════════════════════════════════════════════════════════════════════════
-- NEXT_inventory — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- المستند المسجَّل سجلُّ عملٍ لصاحبه، لا يُحذف إلا مع حسابه. فلا تراجع وفي القاعدة
-- مستندٌ مسجَّل أو سندٌ أو حركة. والقفل أولاً: تسجيلٌ لم يُثبَّت بعد لا يراه العدّ.
LOCK TABLE inv_purchases, inv_returns, inv_vouchers, inv_movements, inv_ledger IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT (SELECT count(*) FROM inv_purchases WHERE status <> 'DRAFT')
         + (SELECT count(*) FROM inv_returns WHERE status <> 'DRAFT')
         + (SELECT count(*) FROM inv_vouchers)
         + (SELECT count(*) FROM inv_movements)
         + (SELECT count(*) FROM inv_ledger) INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'في القاعدة % سجلّاً مسجَّلاً في المخزون (فواتير أو مرتجعات أو سندات أو حركات أو قيود)', n
            USING HINT = 'لا تُحذف إلا مع حساباتها: احذف الحسابات المعنية (delete-user) ثم أعد التراجع.';
    END IF;
END
$$;

-- محاولات المراجعة في يومها تبقى في السقف العام أثراً بلا هوية، كما عند حذف الحساب.
INSERT INTO attempt_tombstones (started_at, outcome, new_account)
SELECT started_at, outcome, new_account FROM inv_review_calls
 WHERE started_at > now() - interval '24 hours' AND ew_is_billable(outcome);

-- الدالّة كما كانت في 0007، حرفاً بحرف.
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

REVOKE EXECUTE ON FUNCTION ew_riyadh_today() FROM eyework_app;

DROP TABLE IF EXISTS inv_review_flags;
DROP TABLE IF EXISTS inv_review_calls;
DROP TABLE IF EXISTS inv_ledger;
DROP TABLE IF EXISTS inv_movements;
DROP TABLE IF EXISTS inv_return_lines;
DROP TABLE IF EXISTS inv_returns;
DROP TABLE IF EXISTS inv_purchase_lines;
DROP TABLE IF EXISTS inv_purchases;
DROP TABLE IF EXISTS inv_vouchers;
DROP TABLE IF EXISTS inv_items;
DROP TABLE IF EXISTS inv_suppliers;
DROP TABLE IF EXISTS inv_counters;
DROP TABLE IF EXISTS inv_settings;

DROP FUNCTION IF EXISTS ew_inv_my_review_limit();
DROP FUNCTION IF EXISTS ew_inv_review_record(uuid, integer, integer, text, text, text, text[], smallint[], text[], jsonb[]);
DROP FUNCTION IF EXISTS ew_inv_review_finish(uuid, text, integer, integer, text, text, text);
DROP FUNCTION IF EXISTS ew_inv_review_begin(uuid, uuid);
DROP FUNCTION IF EXISTS ew_inv_ai_spend(boolean);
DROP FUNCTION IF EXISTS ew_inv_discard_draft(uuid, uuid, integer);
DROP FUNCTION IF EXISTS ew_inv_remove_return_line(uuid, smallint, integer);
DROP FUNCTION IF EXISTS ew_inv_remove_purchase_line(uuid, smallint, integer);
DROP FUNCTION IF EXISTS ew_inv_stock_voucher(uuid, text, uuid, bigint, bigint, text, text, date, bigint);
DROP FUNCTION IF EXISTS ew_inv_reverse_purchase(uuid, integer, text, text);
DROP FUNCTION IF EXISTS ew_inv_post_return(uuid, integer, text[]);
DROP FUNCTION IF EXISTS ew_inv_post_purchase(uuid, integer, text[]);
DROP FUNCTION IF EXISTS ew_inv_check_ack(uuid, uuid, text[]);
DROP FUNCTION IF EXISTS ew_inv_lock_items(uuid[]);
DROP FUNCTION IF EXISTS ew_inv_next_no(uuid, text);
DROP FUNCTION IF EXISTS ew_inv_flag_keys(uuid, uuid);
DROP FUNCTION IF EXISTS ew_inv_return_flags(uuid);
DROP FUNCTION IF EXISTS ew_inv_purchase_flags(uuid);
DROP FUNCTION IF EXISTS ew_inv_return_digest(uuid);
DROP FUNCTION IF EXISTS ew_inv_purchase_digest(uuid);
DROP FUNCTION IF EXISTS ew_inv_purchase_calc(uuid);
DROP FUNCTION IF EXISTS ew_inv_review_tombstone();
DROP FUNCTION IF EXISTS ew_inv_keep_posted_lines();
DROP FUNCTION IF EXISTS ew_inv_keep_record();
DROP FUNCTION IF EXISTS ew_inv_movement_insert();
DROP FUNCTION IF EXISTS ew_inv_return_line_guard();
DROP FUNCTION IF EXISTS ew_inv_return_guard();
DROP FUNCTION IF EXISTS ew_inv_return_insert_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_line_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_insert_guard();
DROP FUNCTION IF EXISTS ew_inv_item_guard();
DROP FUNCTION IF EXISTS ew_inv_supplier_guard();
DROP FUNCTION IF EXISTS ew_inv_settings_guard();
DROP FUNCTION IF EXISTS ew_inv_require_storekeeper(uuid);
DROP FUNCTION IF EXISTS ew_inv_doc_no_ok(text);
DROP FUNCTION IF EXISTS ew_inv_doc_key(text);
DROP FUNCTION IF EXISTS ew_inv_name_key(text);
DROP FUNCTION IF EXISTS ew_inv_vat_bp(text);
DROP FUNCTION IF EXISTS ew_inv_qty_ok(text, bigint);
DROP FUNCTION IF EXISTS ew_inv_text_ok(text, integer);
