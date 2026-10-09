-- ════════════════════════════════════════════════════════════════════════
-- 0010_inventory — تراجع
-- ════════════════════════════════════════════════════════════════════════

-- المستند المسجَّل سجلُّ عملٍ لصاحبه، لا يُحذف إلا مع حسابه. فلا تراجع وفي القاعدة
-- مستندٌ مسجَّل أو سندٌ أو حركة. والقفل أولاً: تسجيلٌ لم يُثبَّت بعد لا يراه العدّ.
LOCK TABLE inv_purchases, inv_returns, inv_vouchers, inv_movements, inv_ledger, inv_count_sessions IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT (SELECT count(*) FROM inv_purchases WHERE status <> 'DRAFT')
         + (SELECT count(*) FROM inv_returns WHERE status <> 'DRAFT')
         + (SELECT count(*) FROM inv_vouchers)
         + (SELECT count(*) FROM inv_movements)
         + (SELECT count(*) FROM inv_ledger)
         + (SELECT count(*) FROM inv_count_sessions WHERE status <> 'OPEN') INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'في القاعدة % سجلّاً مسجَّلاً في المخزون (فواتير أو مرتجعات أو سندات أو حركات أو قيود أو جلسات جرد)', n
            USING HINT = 'لا تُحذف إلا مع حساباتها: احذف الحسابات المعنية (delete-user) ثم أعد التراجع.';
    END IF;
END
$$;

REVOKE EXECUTE ON FUNCTION ew_riyadh_today() FROM eyework_app;

DELETE FROM ai_flags WHERE subject_kind IN ('PURCHASE', 'RETURN');

-- تعتمد على نوعَي الصنف والسند، فتسقط قبل جدوليهما.
DROP FUNCTION IF EXISTS ew_inv_count_voucher(uuid, inv_items, bigint, bigint, text, text, date, uuid, uuid);
DROP TABLE IF EXISTS inv_review_flags;
DROP TABLE IF EXISTS inv_ledger;
DROP TABLE IF EXISTS inv_movements;
DROP TABLE IF EXISTS inv_count_lines;
DROP TABLE IF EXISTS inv_return_lines;
DROP TABLE IF EXISTS inv_returns;
DROP TABLE IF EXISTS inv_purchase_lines;
DROP TABLE IF EXISTS inv_purchases;
DROP TABLE IF EXISTS inv_vouchers;
DROP TABLE IF EXISTS inv_count_sessions;
DROP TABLE IF EXISTS inv_items;
DROP TABLE IF EXISTS inv_categories;
DROP TABLE IF EXISTS inv_supplier_reps;
DROP TABLE IF EXISTS inv_suppliers;
DROP TABLE IF EXISTS inv_counters;
DROP TABLE IF EXISTS inv_settings;

DROP FUNCTION IF EXISTS ew_inv_count_cancel(uuid, integer);
DROP FUNCTION IF EXISTS ew_inv_count_post(uuid, integer, date);
DROP FUNCTION IF EXISTS ew_inv_count_refresh(uuid);
DROP FUNCTION IF EXISTS ew_inv_count_add_item(uuid, uuid);
DROP FUNCTION IF EXISTS ew_inv_count_open(uuid, text, uuid, uuid[], boolean, text);
DROP FUNCTION IF EXISTS ew_inv_review_record(uuid, jsonb, jsonb);
DROP FUNCTION IF EXISTS ew_inv_review_begin(uuid, uuid);
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
DROP FUNCTION IF EXISTS ew_inv_keep_posted_lines();
DROP FUNCTION IF EXISTS ew_inv_keep_record();
DROP FUNCTION IF EXISTS ew_inv_movement_insert();
DROP FUNCTION IF EXISTS ew_inv_count_line_guard();
DROP FUNCTION IF EXISTS ew_inv_count_session_guard();
DROP FUNCTION IF EXISTS ew_inv_return_line_guard();
DROP FUNCTION IF EXISTS ew_inv_return_guard();
DROP FUNCTION IF EXISTS ew_inv_return_insert_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_line_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_guard();
DROP FUNCTION IF EXISTS ew_inv_purchase_insert_guard();
DROP FUNCTION IF EXISTS ew_inv_item_guard();
DROP FUNCTION IF EXISTS ew_inv_supplier_rep_guard();
DROP FUNCTION IF EXISTS ew_inv_category_guard();
DROP FUNCTION IF EXISTS ew_inv_supplier_guard();
DROP FUNCTION IF EXISTS ew_inv_rep_ok(uuid, uuid, uuid);
DROP FUNCTION IF EXISTS ew_inv_settings_guard();
DROP FUNCTION IF EXISTS ew_inv_require_storekeeper(uuid);
DROP FUNCTION IF EXISTS ew_inv_phone_ok(text);
DROP FUNCTION IF EXISTS ew_inv_doc_no_ok(text);
DROP FUNCTION IF EXISTS ew_inv_doc_key(text);
DROP FUNCTION IF EXISTS ew_inv_name_key(text);
DROP FUNCTION IF EXISTS ew_inv_vat_bp(text);
DROP FUNCTION IF EXISTS ew_inv_qty_ok(text, bigint);
DROP FUNCTION IF EXISTS ew_inv_text_ok(text, integer);
