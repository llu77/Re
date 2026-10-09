"""
المخزون والمشتريات — في القاعدة (0010)
=====================================
ما يجب أن يصمد ولو أخطأت الواجهة أو الخادم أو المساعد، بدور الويب نفسه الذي يحمله الخادم:

  • المستند المسجَّل لا يتغيّر ولا يُحذف إلا مع حسابه: التصحيح بمرتجعٍ أو بقيدٍ عكسي.
  • الترقيم لكل حساب بلا فجوات، في معاملة التسجيل نفسها، وما تراجع لا يستهلك رقماً.
  • ما يُسجَّل هو ما رآه صاحبه (رقم الصفّ)، بعد إقراره بكل تنبيه قواعدٍ قائم، وبعد قراره في كل
    تنبيهٍ من سيمبول على المحتوى نفسه (ew_ai_gate من طبقة الذكاء 0009).
  • لا رصيد تحت الصفر، ولا مرتجعٌ أكثر ممّا بقي، ولا سببٌ ناقص؛ والمبالغ بالهللة وضريبة 15%
    بتقريب ZATCA على مستوى الفئة، والمتوسط المتحرّك كمثال IFRS for SMEs رقم 44.
  • مراجعة سيمبول استدعاءٌ في الدفتر الواحد (ai_requests) بسقوف ai_features، ولا دفتر هنا.
  • العزل بالصفّ مفروضٌ على المالك أيضاً، والمنح بالأعمدة، ولا DELETE لدور الويب.

منقولةٌ من فحوص المسودة (96) بعد إعادة التأسيس على طبقة الذكاء (102 فحصاً).
"""

from __future__ import annotations

import datetime
import pathlib
import threading
import uuid
from dataclasses import dataclass
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework.tests.conftest import as_user, create_campaign, make_user
from eyework.tests.db.test_ai_layer import owner_scalar, query, scalar
from eyework.tests.db.test_state_machine import blocked_on_a_lock

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "migrations"
INV_TABLES = ("inv_settings", "inv_suppliers", "inv_supplier_reps", "inv_categories", "inv_items", "inv_purchases",
              "inv_purchase_lines", "inv_returns", "inv_return_lines", "inv_count_sessions", "inv_vouchers", "inv_count_lines",
              "inv_movements", "inv_ledger", "inv_review_flags")
FLAG = ('[{"check": "PRICE_IMPLAUSIBLE", "severity": "MEDIUM", "field": "unit_price", "line": 1, '
        '"reason": "سعر الكرتونة يبدو أعلى من المعتاد لماءٍ معبّأ.", "suggestion": "قارنه بآخر شراءٍ لهذا الصنف.", "evidence": []}]')
USAGE = '{"input": 1000, "output": 200, "model": "claude-opus-5-5", "prompt_version": "inv-2026-10-09.1", "api_request_id": "req_1"}'


# ── أدوات ───────────────────────────────────────────────────────────────
def refused(connection, user: UUID | None, statement: str, params: tuple = (), *, constraint: str | None = None, cls=None) -> bool:
    """رُفضت العبارة بالقيد المسمّى (أو بصنف الخطأ، أو بأيّ خطأ)."""
    try:
        query(connection, user, statement, params)
    except psycopg.Error as exc:
        if constraint is not None:
            return exc.diag.constraint_name == constraint
        if cls is not None:
            return isinstance(exc, cls)
        return True
    return False


def owner_refused(owner, statement: str, params: tuple = (), constraint: str | None = None) -> bool:
    try:
        with owner.transaction(), owner.cursor() as cursor:
            cursor.execute(statement, params)
    except psycopg.Error as exc:
        return constraint is None or exc.diag.constraint_name == constraint
    return False


def owner_run(owner, statement: str, params: tuple = ()) -> None:
    with owner.cursor() as cursor:
        cursor.execute(statement, params)


def item(app, user, name, unit="CARTON", price=4550, kind="STOCK", cat="S", reorder=None) -> UUID:
    return scalar(app, user, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas, vat_category, reorder_level_milli)"
                             " VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s) RETURNING id", (name, kind, unit, price, cat, reorder))


def draft(app, user, supplier=None, no=None, day=None, printed=None, pvat=None, incl=False) -> UUID:
    return scalar(app, user, "INSERT INTO inv_purchases (user_id, supplier_id, supplier_invoice_no, invoice_date, prices_include_vat,"
                             " printed_total_halalas, printed_vat_halalas) VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s) RETURNING id",
                  (supplier, no, day, incl, printed, pvat))


def line(app, user, purchase, itm, qty, price, cat="S", disc=0) -> int:
    return scalar(app, user, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas,"
                             " discount_halalas, vat_category) VALUES (%s, ew_current_user(), %s, %s, %s, %s, %s) RETURNING line_no",
                  (purchase, itm, qty, price, disc, cat))


def rv(app, user, table, doc) -> int:
    return scalar(app, user, f"SELECT row_version FROM {table} WHERE id = %s", (doc,))


def flags(app, user, purchase) -> list[str]:
    return scalar(app, user, "SELECT ew_inv_flag_keys(%s, NULL)", (purchase,))


def post(app, user, purchase, ack=None) -> int:
    if ack is None:
        ack = flags(app, user, purchase)
    return scalar(app, user, "SELECT ew_inv_post_purchase(%s, %s, %s)", (purchase, rv(app, user, "inv_purchases", purchase), ack))


def voucher(app, user, kind, itm, qty, cost=None, reason=None, note=None, day=None, before=None, token=None):
    return query(app, user, "SELECT * FROM ew_inv_stock_voucher(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (token or uuid.uuid4(), kind, itm, qty, cost, reason, note, day, before))[0]


def ret(app, user, purchase, reason=None, note=None) -> UUID:
    return scalar(app, user, "INSERT INTO inv_returns (user_id, purchase_id, reason, note) VALUES (ew_current_user(), %s, %s, %s) RETURNING id",
                  (purchase, reason, note))


def rline(app, user, return_id, line_no, qty) -> None:
    query(app, user, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), %s, %s)",
          (return_id, line_no, qty))


def post_return(app, user, return_id) -> int:
    keys = scalar(app, user, "SELECT ew_inv_flag_keys(NULL, %s)", (return_id,))
    return scalar(app, user, "SELECT ew_inv_post_return(%s, %s, %s)", (return_id, rv(app, user, "inv_returns", return_id), keys))


def category(app, user, name) -> UUID:
    return scalar(app, user, "INSERT INTO inv_categories (user_id, name) VALUES (ew_current_user(), %s) RETURNING id", (name,))


def rep(app, user, supplier, name, mobile=None, default=False) -> UUID:
    return scalar(app, user, "INSERT INTO inv_supplier_reps (user_id, supplier_id, name, mobile, is_default)"
                             " VALUES (ew_current_user(), %s, %s, %s, %s) RETURNING id", (supplier, name, mobile, default))


def count_open(app, user, scope="ALL", cat=None, items=None, blind=True, token=None):
    return query(app, user, "SELECT * FROM ew_inv_count_open(%s, %s, %s, %s, %s, NULL)",
                 (token or uuid.uuid4(), scope, cat, items, blind))[0]


def count_line(app, user, session, itm, counted, reason=None, note=None, cost=None) -> None:
    query(app, user, "UPDATE inv_count_lines SET counted_milli = %s, reason = %s, note = %s, unit_cost_halalas = %s"
                     " WHERE session_id = %s AND item_id = %s", (counted, reason, note, cost, session, itm))


def count_post(app, user, session, day):
    return query(app, user, "SELECT * FROM ew_inv_count_post(%s, %s, %s)",
                 (session, rv(app, user, "inv_count_sessions", session), day))[0]


def ai_flags(app, user, subject) -> list[tuple]:
    return query(app, user, "SELECT id, check_code, closed_at FROM ai_flags WHERE subject_id = %s ORDER BY created_at", (subject,))


def begin(app, user, purchase) -> tuple[UUID, bytes]:
    return query(app, user, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (purchase,))[0]


def record(app, user, request, flag=FLAG, usage=USAGE) -> str:
    return scalar(app, user, "SELECT ew_inv_review_record(%s, %s::jsonb, %s::jsonb)", (request, flag, usage))


@dataclass
class Scene:
    keeper: UUID
    other: UUID
    marketer: UUID
    sup: UUID
    sup_novat: UUID
    water: UUID
    rice: UUID
    ship: UUID
    today: datetime.date


@pytest.fixture
def scene(owner, app) -> Scene:
    """أمينا مخزونٍ بإعداديهما، ومسوّق، ومورّدان، وثلاثة أصناف (صنفان يُخزَّنان وخدمة)."""
    keeper = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    other = make_user(owner, login=b"other-keeper", profession="STOREKEEPER")
    marketer = make_user(owner, login=b"marketer")
    query(app, keeper, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)")
    query(app, other, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), true)")
    sup = scalar(app, keeper, "INSERT INTO inv_suppliers (user_id, name, vat_number) VALUES (ew_current_user(), 'مؤسسة النور', '300000000000003') RETURNING id")
    sup_novat = scalar(app, keeper, "INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'بقالة الحي') RETURNING id")
    return Scene(
        keeper=keeper, other=other, marketer=marketer, sup=sup, sup_novat=sup_novat,
        water=item(app, keeper, "كرتونة ماء ٣٣٠ مل", reorder=20000),
        rice=item(app, keeper, "أرز بسمتي", unit="KG", price=900),
        ship=item(app, keeper, "شحن", unit="SERVICE", kind="SERVICE", price=5000),
        today=owner_scalar(owner, "SELECT ew_riyadh_today()"),
    )


def base_invoice(app, s: Scene) -> UUID:
    """فاتورةٌ بسطرين: عشرة كراتين بـ100.00 وشحنٌ بـ10.00، والمطبوع 1,160.00 (يخالف المحسوب بعشرة ريالات)."""
    p = draft(app, s.keeper, s.sup, "INV-1001", s.today, 116000)
    line(app, s.keeper, p, s.water, 10000, 10000)
    line(app, s.keeper, p, s.ship, 1000, 1000)
    return p


# ── الإعداد والمهنة والعزل ──────────────────────────────────────────────
def test_only_a_storekeeper_keeps_inventory_and_every_row_stays_private(owner, app, scene):
    s = scene
    assert refused(app, s.marketer, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)",
                   constraint="inv_needs_storekeeper")
    assert refused(app, s.keeper, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (%s, false)", (s.marketer,))
    assert scalar(app, s.other, "SELECT count(*) FROM inv_items") == 0
    assert scalar(app, s.other, "SELECT count(*) FROM inv_suppliers") == 0
    assert refused(app, s.keeper, "UPDATE inv_items SET on_hand_milli = 5000 WHERE id = %s", (s.water,), cls=errors.InsufficientPrivilege)
    assert all(refused(app, s.keeper, f"DELETE FROM {t}", cls=errors.InsufficientPrivilege) for t in INV_TABLES)
    assert refused(app, s.keeper, "SELECT * FROM inv_counters", cls=errors.InsufficientPrivilege)
    assert refused(app, s.keeper, "SELECT ew_inv_next_no(ew_current_user(), 'PURCHASE')", cls=errors.InsufficientPrivilege)
    assert refused(app, s.keeper, "SELECT ew_inv_check_ack(NULL, NULL, '{}')", cls=errors.InsufficientPrivilege)


def test_suppliers_and_items_follow_the_master_data_rules(app, scene):
    s = scene
    assert refused(app, s.keeper, "INSERT INTO inv_suppliers (user_id, name, vat_number) VALUES (ew_current_user(), 'س', '310000000000004')",
                   constraint="inv_supplier_vat_shape")
    assert refused(app, s.keeper, "INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'مؤسسه النور')", constraint="inv_suppliers_name")
    assert refused(app, s.keeper, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (ew_current_user(), 'كرتونه ماء 330 مل', 'STOCK', 'CARTON', 100)",
                   constraint="inv_items_name")
    assert refused(app, s.keeper, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (ew_current_user(), 'تركيب', 'SERVICE', 'PIECE', 100)",
                   constraint="inv_item_unit_matches_kind")


# ── الأسطر والحساب ─────────────────────────────────────────────────────
def test_lines_are_numbered_by_the_database_and_computed_as_zatca_rounds(app, scene):
    s = scene
    p = draft(app, s.keeper, s.sup, "INV-1001", s.today, 116000)
    assert line(app, s.keeper, p, s.water, 10000, 10000) == 1 and line(app, s.keeper, p, s.ship, 1000, 1000) == 2
    assert refused(app, s.keeper, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category)"
                                  " VALUES (%s, ew_current_user(), %s, 1500, 100, 'S')", (p, s.water), constraint="inv_quantity_unit")
    assert refused(app, s.keeper, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, discount_halalas, vat_category)"
                                  " VALUES (%s, ew_current_user(), %s, 1000, 100, 101, 'S')", (p, s.water), constraint="inv_line_discount_exceeds")
    assert query(app, s.keeper, "SELECT line_no, amount_halalas, net_halalas, vat_halalas FROM ew_inv_purchase_calc(%s)", (p,)) == [
        (1, 100000, 100000, 15000), (2, 1000, 1000, 150)]
    # أكبر الكسور: أربعون سطراً بعشر هللاتٍ لا تُنتج ضريبةً سالبة، ومجموعها ضريبة الفئة.
    small = draft(app, s.keeper)
    for _ in range(40):
        line(app, s.keeper, small, s.water, 1000, 10)
    rows = [r[0] for r in query(app, s.keeper, "SELECT vat_halalas FROM ew_inv_purchase_calc(%s)", (small,))]
    assert sum(rows) == 60 and min(rows) >= 1
    assert refused(app, s.keeper, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category)"
                                  " VALUES (%s, ew_current_user(), %s, 1000, 10, 'S')", (small, s.water), constraint="inv_line_cap")
    incl = draft(app, s.keeper, incl=True)
    line(app, s.keeper, incl, s.water, 1000, 125500)
    # شاملةٌ 1,255.00: الضريبة 163.70 (15/115، مثال دليل ZATCA رقم 6).
    assert query(app, s.keeper, "SELECT amount_halalas, net_halalas, vat_halalas FROM ew_inv_purchase_calc(%s)", (incl,)) == [(125500, 109130, 16370)]
    assert scalar(app, s.keeper, "SELECT vat_halalas FROM ew_inv_purchase_calc(%s) LIMIT 1", (small,)) in (1, 2)


# ── التنبيهات والإقرار والتسجيل ────────────────────────────────────────
def test_posting_needs_every_flag_acknowledged_and_the_row_version_the_user_saw(owner, app, scene):
    s = scene
    p1 = base_invoice(app, s)
    keys = flags(app, s.keeper, p1)
    assert "TOTAL_MISMATCH" in keys
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, '{}')", (p1, rv(app, s.keeper, "inv_purchases", p1)), constraint="inv_flags_unacknowledged")
    assert owner_scalar(owner, "SELECT count(*) FROM inv_counters WHERE kind <> 'ITEM'") == 0
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, %s)", (p1, rv(app, s.keeper, "inv_purchases", p1) - 1, keys), constraint="inv_stale_row_version")
    assert post(app, s.keeper, p1) == 1
    assert query(app, s.keeper, "SELECT status, subtotal_halalas, vat_halalas, total_halalas, supplier_name FROM inv_purchases WHERE id = %s", (p1,))[0] \
        == ("POSTED", 101000, 15150, 116150, "مؤسسة النور")
    assert query(app, s.keeper, "SELECT count(*), sum(quantity_milli), sum(value_halalas) FROM inv_movements WHERE purchase_id = %s", (p1,))[0] == (1, 10000, 100000)
    assert query(app, s.keeper, "SELECT kind, entry_date, net_halalas, vat_halalas, gross_halalas FROM inv_ledger WHERE purchase_id = %s", (p1,))[0] \
        == ("PURCHASE", s.today, 101000, 15150, 116150)
    assert scalar(app, s.keeper, "SELECT count(*) FROM inv_review_flags WHERE purchase_id = %s AND acknowledged_at IS NOT NULL", (p1,)) == len(keys)
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, '{}')", (p1, rv(app, s.keeper, "inv_purchases", p1)), constraint="inv_document_not_draft")
    assert refused(app, s.keeper, "UPDATE inv_purchases SET note = 'x' WHERE id = %s", (p1,), constraint="inv_document_is_final")
    assert refused(app, s.keeper, "UPDATE inv_purchase_lines SET quantity_milli = 9000 WHERE purchase_id = %s AND line_no = 1", (p1,), constraint="inv_document_not_draft")
    assert owner_refused(owner, "DELETE FROM inv_purchases WHERE id = %s", (p1,), "inv_record_is_permanent")
    assert owner_refused(owner, "DELETE FROM inv_movements WHERE purchase_id = %s", (p1,), "inv_record_is_permanent")
    assert owner_refused(owner, "DELETE FROM inv_ledger WHERE purchase_id = %s", (p1,), "inv_record_is_permanent")
    assert owner_refused(owner, "UPDATE inv_movements SET quantity_milli = 1 WHERE purchase_id = %s", (p1,))
    # الحساب الآخر لا يضيف سطراً إليها ولا يسجّلها: لا توجد له.
    o_item = item(app, s.other, "قفازات", unit="BOX", price=1200)
    assert refused(app, s.other, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category)"
                                 " VALUES (%s, ew_current_user(), %s, 1000, 100, 'S')", (p1, o_item), constraint="inv_purchase_lines_purchase_id_user_id_fkey")
    assert refused(app, s.other, "SELECT ew_inv_post_purchase(%s, 1, '{}')", (p1,), cls=errors.NoDataFound)
    assert refused(app, s.keeper, "UPDATE inv_items SET unit = 'PIECE' WHERE id = %s", (s.water,), constraint="inv_item_unit_locked")
    assert refused(app, s.keeper, "UPDATE inv_items SET is_active = false WHERE id = %s", (s.water,), constraint="inv_item_has_stock")


def test_duplicates_history_and_dates_raise_the_rule_flags(app, scene):
    s = scene
    post(app, s.keeper, base_invoice(app, s))
    p2 = draft(app, s.keeper, s.sup, "inv 1001", s.today, 116150)
    line(app, s.keeper, p2, s.water, 10000, 10000)
    line(app, s.keeper, p2, s.ship, 1000, 1000)
    assert "DUPLICATE_SUPPLIER_INVOICE" in flags(app, s.keeper, p2)
    query(app, s.keeper, "SELECT ew_inv_discard_draft(%s, NULL, %s)", (p2, rv(app, s.keeper, "inv_purchases", p2)))
    assert scalar(app, s.keeper, "SELECT count(*) FROM inv_purchases WHERE id = %s", (p2,)) == 0
    for i in range(3):
        pp = draft(app, s.keeper, s.sup, f"H-{i}", s.today, 115000)
        line(app, s.keeper, pp, s.water, 10000, 10000)
        post(app, s.keeper, pp)
    p3 = draft(app, s.keeper, s.sup_novat, "B-77", s.today - datetime.timedelta(days=120), 0)
    ln = line(app, s.keeper, p3, s.water, 100000, 100000, cat="Z")
    k3 = flags(app, s.keeper, p3)
    assert f"PRICE_FAR_FROM_HISTORY:{ln}" in k3 and scalar(
        app, s.keeper, "SELECT (detail->>'extra_zero')::boolean FROM ew_inv_purchase_flags(%s) WHERE code = 'PRICE_FAR_FROM_HISTORY'", (p3,))
    assert f"QUANTITY_FAR_FROM_HISTORY:{ln}" in k3 and scalar(
        app, s.keeper, "SELECT (detail->>'extra_zero')::boolean FROM ew_inv_purchase_flags(%s) WHERE code = 'QUANTITY_FAR_FROM_HISTORY'", (p3,))
    assert f"CATEGORY_CHANGED:{ln}" in k3 and "OLD_INVOICE_DATE" in k3
    query(app, s.keeper, "UPDATE inv_purchase_lines SET vat_category = 'S', unit_price_halalas = 10000, quantity_milli = 10000 WHERE purchase_id = %s", (p3,))
    assert "VAT_WITHOUT_SUPPLIER_VAT_NUMBER" in flags(app, s.keeper, p3)
    assert rv(app, s.keeper, "inv_purchases", p3) > 1
    pf = draft(app, s.keeper, s.sup, "F-1", s.today + datetime.timedelta(days=1), 11500)
    line(app, s.keeper, pf, s.water, 1000, 10000)
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, %s)", (pf, rv(app, s.keeper, "inv_purchases", pf), flags(app, s.keeper, pf)),
                   constraint="inv_purchase_future_date")


def test_twenty_open_drafts_is_the_cap(app, scene):
    s = scene
    for _ in range(20):
        draft(app, s.other)
    assert refused(app, s.other, "INSERT INTO inv_purchases (user_id) VALUES (ew_current_user())", constraint="inv_open_draft_cap")


# ── المتوسط المتحرّك والسندات ───────────────────────────────────────────
def test_the_moving_average_follows_ifrs_for_smes_example_44_and_vouchers_are_idempotent(app, scene):
    s = scene
    cable = item(app, s.keeper, "كابل ألياف", unit="PIECE", price=1000)
    opening = voucher(app, s.keeper, "OPENING", cable, 1000000, cost=1000, day=s.today)
    voucher(app, s.keeper, "ISSUE", cable, 200000, reason="SALE", day=s.today)
    for no, qty, price, printed in (("C-25F", 400000, 1500, 600000), ("C-2M", 200000, 2000, 400000)):
        p = draft(app, s.keeper, s.sup, no, s.today, printed)
        line(app, s.keeper, p, cable, qty, price, cat="Z")
        post(app, s.keeper, p)
    assert query(app, s.keeper, "SELECT on_hand_milli, stock_value_halalas FROM inv_items WHERE id = %s", (cable,))[0] == (1400000, 1800000)
    voucher(app, s.keeper, "ISSUE", cable, 900000, reason="SALE", day=s.today)
    assert scalar(app, s.keeper, "SELECT value_halalas FROM inv_movements WHERE item_id = %s AND kind = 'ISSUE_OUT' ORDER BY seq DESC LIMIT 1", (cable,)) == 1157143
    assert query(app, s.keeper, "SELECT on_hand_milli, stock_value_halalas FROM inv_items WHERE id = %s", (cable,))[0] == (500000, 642857)
    token = scalar(app, s.keeper, "SELECT client_token FROM inv_vouchers WHERE id = %s", (opening[0],))
    assert query(app, s.keeper, "SELECT voucher_number, replayed FROM ew_inv_stock_voucher(%s, 'OPENING', %s, 1000000, 1000, NULL, NULL, %s, NULL)",
                 (token, cable, s.today))[0] == (opening[1], True)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'OPENING', %s, 1000, 1000, NULL, NULL, %s, NULL)",
                   (uuid.uuid4(), cable, s.today), constraint="inv_opening_not_first")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 600000, NULL, 'USE', NULL, %s, NULL)",
                   (uuid.uuid4(), cable, s.today), constraint="inv_negative_stock")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'COUNT', %s, 480000, NULL, NULL, NULL, %s, 400000)",
                   (uuid.uuid4(), cable, s.today), constraint="inv_count_stale")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'COUNT', %s, 480000, NULL, NULL, NULL, %s, 500000)",
                   (uuid.uuid4(), cable, s.today), constraint="inv_count_needs_reason")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'COUNT', %s, 480000, NULL, 'FOUND', NULL, %s, 500000)",
                   (uuid.uuid4(), cable, s.today), constraint="inv_count_reason_direction")
    voucher(app, s.keeper, "COUNT", cable, 480000, reason="DAMAGE", day=s.today, before=500000)
    assert scalar(app, s.keeper, "SELECT last_counted_on FROM inv_items WHERE id = %s", (cable,)) == s.today
    assert query(app, s.keeper, "SELECT kind, quantity_milli FROM inv_movements WHERE item_id = %s ORDER BY seq DESC LIMIT 1", (cable,))[0] == ("COUNT_OUT", 20000)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 1000, NULL, 'USE', NULL, %s, NULL)",
                   (uuid.uuid4(), cable, s.today - datetime.timedelta(days=31)), constraint="inv_voucher_date")
    assert refused(app, s.keeper, "UPDATE inv_settings SET cost_includes_vat = true", constraint="inv_cost_basis_locked")


# ── المرتجع ────────────────────────────────────────────────────────────
def test_returns_take_the_remaining_share_and_the_credit_note_is_recorded_once(app, scene):
    s = scene
    pr = draft(app, s.keeper, s.sup, "R-1", s.today, 34500)
    line(app, s.keeper, pr, s.water, 3000, 10000, cat="Z")   # ثلاثة كراتين بـ100.00، صافي 300.00 بلا ضريبة
    line(app, s.keeper, pr, s.ship, 1000, 4500)               # شحن 45.00 وضريبته
    post(app, s.keeper, pr)
    r1 = ret(app, s.keeper, pr)
    rline(app, s.keeper, r1, 1, 1000)
    assert refused(app, s.keeper, "SELECT ew_inv_post_return(%s, %s, '{}')", (r1, rv(app, s.keeper, "inv_returns", r1)), constraint="inv_return_needs_reason")
    query(app, s.keeper, "UPDATE inv_returns SET reason = 'OTHER' WHERE id = %s", (r1,))
    assert refused(app, s.keeper, "SELECT ew_inv_post_return(%s, %s, '{}')", (r1, rv(app, s.keeper, "inv_returns", r1)), constraint="inv_return_needs_note")
    query(app, s.keeper, "UPDATE inv_returns SET reason = 'DAMAGED' WHERE id = %s", (r1,))
    assert post_return(app, s.keeper, r1) == 1
    r2 = ret(app, s.keeper, pr, "DAMAGED")
    rline(app, s.keeper, r2, 1, 1000)
    post_return(app, s.keeper, r2)
    r3 = ret(app, s.keeper, pr, "EXCESS")
    assert refused(app, s.keeper, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), 1, 2000)", (r3,),
                   constraint="inv_return_exceeds_remaining")
    rline(app, s.keeper, r3, 1, 1000)
    rline(app, s.keeper, r3, 2, 1000)
    post_return(app, s.keeper, r3)
    nets = [x[0] for x in query(app, s.keeper, "SELECT rl.net_halalas FROM inv_return_lines rl JOIN inv_returns r ON r.id = rl.return_id"
                                               " WHERE r.purchase_id = %s AND rl.line_no = 1 ORDER BY r.number", (pr,))]
    assert sum(nets) == 30000
    assert scalar(app, s.keeper, "SELECT count(*) FROM inv_movements WHERE return_id = %s", (r3,)) == 1
    assert query(app, s.keeper, "SELECT kind, net_halalas, vat_halalas FROM inv_ledger WHERE return_id = %s", (r3,))[0] == ("RETURN", -14500, -675)
    r4 = ret(app, s.keeper, pr, "EXCESS")
    assert refused(app, s.keeper, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), 1, 1000)", (r4,),
                   constraint="inv_return_exceeds_remaining")
    assert scalar(app, s.keeper, "UPDATE inv_returns SET credit_note_no = 'CN-55', credit_note_date = %s WHERE id = %s RETURNING credit_note_at IS NOT NULL", (s.today, r1))
    assert refused(app, s.keeper, "UPDATE inv_returns SET credit_note_no = 'CN-56', credit_note_date = %s WHERE id = %s", (s.today, r1), constraint="inv_document_is_final")
    assert refused(app, s.keeper, "UPDATE inv_returns SET credit_note_no = 'CN-9', credit_note_date = %s WHERE id = %s",
                   (s.today + datetime.timedelta(days=1), r2), constraint="inv_credit_note_date")
    assert refused(app, s.keeper, "UPDATE inv_returns SET reason = 'EXCESS' WHERE id = %s", (r2,), constraint="inv_document_is_final")
    assert refused(app, s.keeper, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pr, rv(app, s.keeper, "inv_purchases", pr)),
                   constraint="inv_reversal_has_returns")


def test_a_return_of_goods_already_issued_is_refused_and_consumes_no_number(owner, app, scene):
    s = scene
    pz = draft(app, s.keeper, s.sup, "Z-9", s.today, 50000)
    line(app, s.keeper, pz, s.rice, 5500, 9000, cat="Z")
    post(app, s.keeper, pz)
    voucher(app, s.keeper, "ISSUE", s.rice, 5500, reason="USE", day=s.today)
    rz = ret(app, s.keeper, pz, "DAMAGED")
    rline(app, s.keeper, rz, 1, 1500)
    assert refused(app, s.keeper, "SELECT ew_inv_post_return(%s, %s, '{}')", (rz, rv(app, s.keeper, "inv_returns", rz)), constraint="inv_negative_stock")
    assert owner_scalar(owner, "SELECT count(*) FROM inv_counters WHERE user_id = %s AND kind = 'RETURN'", (s.keeper,)) == 0


# ── القيد العكسي ───────────────────────────────────────────────────────
def test_a_reversal_takes_the_stock_out_writes_the_negative_entry_and_is_final(app, scene):
    s = scene
    pv = draft(app, s.keeper, s.sup, "DUP-1", s.today, 23000)
    line(app, s.keeper, pv, s.water, 2000, 10000)
    post(app, s.keeper, pv)
    before = scalar(app, s.keeper, "SELECT on_hand_milli FROM inv_items WHERE id = %s", (s.water,))
    assert refused(app, s.keeper, "SELECT ew_inv_reverse_purchase(%s, %s, 'OTHER', NULL)", (pv, rv(app, s.keeper, "inv_purchases", pv)), constraint="inv_reversal_needs_note")
    assert scalar(app, s.keeper, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pv, rv(app, s.keeper, "inv_purchases", pv))) == 1
    assert scalar(app, s.keeper, "SELECT on_hand_milli FROM inv_items WHERE id = %s", (s.water,)) == before - 2000
    assert query(app, s.keeper, "SELECT net_halalas, vat_halalas FROM inv_ledger WHERE purchase_id = %s AND kind = 'REVERSAL'", (pv,))[0] == (-20000, -3000)
    assert refused(app, s.keeper, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pv, rv(app, s.keeper, "inv_purchases", pv)), constraint="inv_reversal_needs_posted")
    assert refused(app, s.keeper, "INSERT INTO inv_returns (user_id, purchase_id, reason) VALUES (ew_current_user(), %s, 'EXCESS')", (pv,),
                   constraint="inv_return_needs_posted_purchase")
    pd = draft(app, s.keeper, s.sup, "DUP-1", s.today, 23000)
    line(app, s.keeper, pd, s.water, 2000, 10000)
    assert "DUPLICATE_SUPPLIER_INVOICE" not in flags(app, s.keeper, pd)


# ── الترقيم بلا فجوات والتزامن ──────────────────────────────────────────
def test_two_tabs_posting_one_draft_and_two_drafts_at_once_keep_the_numbers_gapless(app, app_url, scene):
    s = scene
    pc = draft(app, s.keeper, s.sup, "CC-1", s.today, 11500)
    line(app, s.keeper, pc, s.water, 1000, 10000)
    keys, version = flags(app, s.keeper, pc), rv(app, s.keeper, "inv_purchases", pc)
    outcome: dict[str, object] = {}
    with psycopg.connect(app_url, autocommit=False) as c1, psycopg.connect(app_url, autocommit=False) as c2:
        for c in (c1, c2):
            c.execute("SELECT set_config('eyework.user_id', %s, true)", (str(s.keeper),))
        c1.execute("SELECT ew_inv_post_purchase(%s, %s, %s)", (pc, version, keys))

        def second() -> None:
            try:
                outcome["r"] = c2.execute("SELECT ew_inv_post_purchase(%s, %s, %s)", (pc, version, keys)).fetchone()[0]
            except psycopg.Error as exc:
                outcome["e"] = exc.diag.constraint_name
                c2.rollback()

        racer = threading.Thread(target=second)
        racer.start()
        waited = blocked_on_a_lock(app, c2.info.backend_pid, racer)
        c1.commit()
        racer.join()
    assert waited and outcome.get("e") == "inv_document_not_draft"

    drafts = []
    for no in ("PAR-1", "PAR-2"):
        p = draft(app, s.keeper, s.sup, no, s.today, 11500)
        line(app, s.keeper, p, s.water, 1000, 10000)
        drafts.append(p)
    results: dict[str, object] = {}

    def poster(name: str, purchase: UUID) -> None:
        with psycopg.connect(app_url, autocommit=True) as c:
            as_user(c, s.keeper)
            try:
                results[name] = post(c, s.keeper, purchase)
            except psycopg.Error as exc:
                results[name] = exc.diag.constraint_name

    racers = [threading.Thread(target=poster, args=(n, p)) for n, p in zip("ab", drafts)]
    for r in racers:
        r.start()
    for r in racers:
        r.join()
    numbers = [x[0] for x in query(app, s.keeper, "SELECT number FROM inv_purchases WHERE number IS NOT NULL ORDER BY number")]
    assert sorted(results.values()) == numbers[-2:] and numbers == list(range(1, len(numbers) + 1))


# ── مراجعة سيمبول على الدفتر الواحد (0009) ──────────────────────────────
def reviewable(app, s: Scene, no: str = "AI-1") -> UUID:
    p = draft(app, s.keeper, s.sup, no, s.today, 11500)
    line(app, s.keeper, p, s.water, 1000, 10000)
    return p


def test_a_stock_review_opens_in_the_shared_ledger_and_its_flag_gates_the_posting(app, scene):
    s = scene
    pr1 = reviewable(app, s)
    assert refused(app, s.marketer, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_needs_storekeeper")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (draft(app, s.keeper),), constraint="inv_purchase_no_lines")
    call, digest = begin(app, s.keeper, pr1)
    assert query(app, s.keeper, "SELECT feature, subject_kind, subject_id, content_digest FROM ai_requests WHERE id = %s", (call,))[0] \
        == ("STOCK_REVIEW", "PURCHASE", pr1, digest)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="ai_request_in_progress")
    assert record(app, s.keeper, call) == "OK"
    assert [f[1] for f in ai_flags(app, s.keeper, pr1)] == ["PRICE_IMPLAUSIBLE"]
    assert query(app, s.keeper, "SELECT outcome, flags_count FROM ai_requests WHERE id = %s", (call,))[0] == ("OK", 1)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="ai_review_current")
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, %s)", (pr1, rv(app, s.keeper, "inv_purchases", pr1), flags(app, s.keeper, pr1)),
                   constraint="ai_flags_undecided")
    flag_id = ai_flags(app, s.keeper, pr1)[0][0]
    query(app, s.keeper, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (flag_id,))
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, %s)", (pr1, rv(app, s.keeper, "inv_purchases", pr1), flags(app, s.keeper, pr1)),
                   constraint="ai_flags_undecided")
    # بعد تعديلٍ تتغيّر البصمة فيُراجَع من جديد، والتنبيه القديم على محتوىً آخر لا يمنع.
    query(app, s.keeper, "UPDATE inv_purchase_lines SET unit_price_halalas = 9000 WHERE purchase_id = %s", (pr1,))
    call2, digest2 = begin(app, s.keeper, pr1)
    assert digest2 != digest
    query(app, s.keeper, "UPDATE inv_purchase_lines SET unit_price_halalas = 9500 WHERE purchase_id = %s", (pr1,))
    assert record(app, s.keeper, call2) == "DISCARDED"
    assert len(ai_flags(app, s.keeper, pr1)) == 1
    assert scalar(app, s.keeper, "SELECT outcome FROM ai_requests WHERE id = %s", (call2,)) == "DISCARDED"
    call3, _ = begin(app, s.keeper, pr1)
    assert refused(app, s.keeper, "SELECT ew_inv_review_record(%s, '[{\"check\": \"X\"}]'::jsonb, NULL)", (call3,), constraint="ai_flags_shape")
    query(app, s.keeper, "SELECT ew_ai_request_fail(%s, 'UPSTREAM_BUSY', NULL)", (call3,))
    assert post(app, s.keeper, pr1) == 1


def test_proceed_opens_the_gate_and_posting_closes_the_flag(app, scene):
    s = scene
    pr0 = reviewable(app, s, "AI-2")
    call, _ = begin(app, s.keeper, pr0)
    assert record(app, s.keeper, call) == "OK"
    flag_id = ai_flags(app, s.keeper, pr0)[0][0]
    query(app, s.keeper, "SELECT * FROM ew_ai_decide(%s, 'PROCEED')", (flag_id,))
    assert post(app, s.keeper, pr0) == 1
    assert ai_flags(app, s.keeper, pr0)[0][2] is not None
    assert refused(app, s.keeper, "SELECT * FROM ew_ai_decide(%s, 'EDIT')", (flag_id,), constraint="ai_flag_closed")


def test_discarding_a_draft_forgets_what_symbol_said_about_it(owner, app, scene):
    s = scene
    p = reviewable(app, s, "AI-4")
    call, _ = begin(app, s.keeper, p)
    assert record(app, s.keeper, call) == "OK"
    query(app, s.keeper, "SELECT ew_inv_discard_draft(%s, NULL, %s)", (p, rv(app, s.keeper, "inv_purchases", p)))
    assert owner_scalar(owner, "SELECT count(*) FROM ai_flags WHERE subject_id = %s", (p,)) == 0


def seed(owner, user: UUID, count: int, age: str, outcome: str = "OK") -> None:
    owner_run(owner, "INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome)"
                     " SELECT %s, 'STOCK_REVIEW', now() - %s::interval, now(), %s FROM generate_series(1, %s)", (user, age, outcome, count))


def test_the_review_caps_come_from_the_ai_features_row_and_the_shared_spend(owner, app, scene):
    s = scene
    pr2 = reviewable(app, s, "AI-3")
    seed(owner, s.keeper, 6, "1 minute")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr2,), constraint="ai_rate")
    owner_run(owner, "ALTER TABLE ai_requests DISABLE TRIGGER trg_ai_request_settle")
    owner_run(owner, "UPDATE ai_requests SET started_at = now() - interval '1 hour' WHERE user_id = %s", (s.keeper,))
    seed(owner, s.keeper, 24, "2 hours")
    seed(owner, s.keeper, 3, "2 hours", outcome="UPSTREAM_BUSY")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr2,), constraint="ai_daily_cap")
    assert scalar(app, s.keeper, "SELECT used_today FROM ew_ai_my_usage() WHERE feature = 'STOCK_REVIEW'") == 30
    owner_run(owner, "UPDATE ai_requests SET started_at = now() - interval '25 hours' WHERE user_id = %s", (s.keeper,))
    owner_run(owner, "ALTER TABLE ai_requests ENABLE TRIGGER trg_ai_request_settle")
    seed(owner, s.other, 600, "3 hours")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr2,), constraint="ai_feature_app_cap")
    owner_run(owner, "DELETE FROM ai_requests WHERE user_id = %s", (s.other,))
    assert owner_scalar(owner, "SELECT count(*) FROM attempt_tombstones") == 600
    assert owner_scalar(owner, "SELECT ew_ai_spend(false)") >= 600
    owner_run(owner, "DELETE FROM attempt_tombstones")
    owner_run(owner, "INSERT INTO attempt_tombstones (started_at, outcome) SELECT now() - interval '1 hour', 'OK' FROM generate_series(1, 2000)")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr2,), constraint="generation_global_cap")
    owner_run(owner, "DELETE FROM attempt_tombstones")
    # حملةٌ تُرفض لأن مراجعات المخزون استنفدت السقف العام: ew_begin_generation يعدّ الدفتر الواحد.
    campaign = create_campaign(app, s.marketer)
    seed(owner, s.other, 2000, "3 hours")
    assert refused(app, s.marketer, "SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (campaign,), constraint="generation_global_cap")


# ── حذف الحساب والتراجع ────────────────────────────────────────────────
def test_deleting_the_account_removes_every_inventory_record_with_it(owner, app, scene):
    s = scene
    p = base_invoice(app, s)
    post(app, s.keeper, p)
    call, _ = begin(app, s.keeper, reviewable(app, s, "AI-5"))
    record(app, s.keeper, call)
    assert owner_scalar(owner, "SELECT count(*) FROM inv_ledger WHERE user_id = %s", (s.keeper,)) == 1
    query(app, s.keeper, "SELECT ew_delete_me()")
    left = owner_scalar(owner, "SELECT (SELECT count(*) FROM inv_items WHERE user_id = %s) + (SELECT count(*) FROM inv_purchases WHERE user_id = %s)"
                               " + (SELECT count(*) FROM inv_ledger WHERE user_id = %s) + (SELECT count(*) FROM inv_movements WHERE user_id = %s)"
                               " + (SELECT count(*) FROM ai_requests WHERE user_id = %s) + (SELECT count(*) FROM ai_flags WHERE user_id = %s)", (s.keeper,) * 6)
    assert left == 0
    # صنفٌ أو مورّد لا يُحذف مباشرةً ولو من المالك (الحذف مع الحساب وحده).
    item(app, s.other, "قفازات", unit="BOX", price=1200)
    assert owner_refused(owner, "DELETE FROM inv_items WHERE user_id = %s", (s.other,), "inv_record_is_permanent")


def test_the_down_migration_refuses_while_posted_records_exist(owner, app, scene):
    s = scene
    post(app, s.keeper, base_invoice(app, s))
    down = (MIGRATIONS / "0010_inventory.down.sql").read_text(encoding="utf-8")
    with pytest.raises(psycopg.Error, match="سجلّاً مسجَّلاً"):
        with owner.transaction(), owner.cursor() as cursor:
            cursor.execute(down)
    assert owner_scalar(owner, "SELECT count(*) FROM pg_tables WHERE tablename = 'inv_ledger'") == 1


# ── ما أضافه بحث المهن: الأصناف والمندوبون والتسليم وجلسات الجرد ────────
def test_items_take_their_numbers_from_the_account_counter_and_their_identifiers_are_checked(owner, app, scene):
    s = scene
    assert query(app, s.keeper, "SELECT number FROM inv_items ORDER BY number") == [(1,), (2,), (3,)]
    sugar = item(app, s.keeper, "سكّر")
    assert scalar(app, s.keeper, "SELECT number FROM inv_items WHERE id = %s", (sugar,)) == 4
    assert scalar(app, s.other, "SELECT number FROM inv_items WHERE id = %s", (item(app, s.other, "سكّر"),)) == 1
    assert refused(app, s.keeper, "UPDATE inv_items SET number = 9 WHERE id = %s", (sugar,), cls=errors.InsufficientPrivilege)
    assert owner_refused(owner, "UPDATE inv_items SET number = 9 WHERE id = %s", (sugar,), constraint="inv_managed_columns")
    # الباركود بشكل GTIN وفريدٌ في الحساب، ورمز المورّد اختياري بشكله.
    query(app, s.keeper, "UPDATE inv_items SET barcode = '6281001234567', supplier_code = 'SUG-1' WHERE id = %s", (sugar,))
    assert refused(app, s.keeper, "UPDATE inv_items SET barcode = '12345' WHERE id = %s", (s.water,), constraint="inv_item_barcode_shape")
    assert refused(app, s.keeper, "UPDATE inv_items SET barcode = '6281001234567' WHERE id = %s", (s.water,), constraint="inv_items_barcode")
    assert refused(app, s.keeper, "UPDATE inv_items SET supplier_code = '-x' WHERE id = %s", (s.water,), constraint="inv_item_code_shape")
    assert refused(app, s.keeper, "UPDATE inv_items SET barcode = '62810012' WHERE id = %s", (s.ship,), constraint="inv_item_service_has_no_stock")
    # التصنيف والمورّد المفضّل غير مؤرشفين، وسبب الإعفاء لغير الفئة S، والمستهدف فوق حدّ الطلب.
    drinks = category(app, s.keeper, "مشروبات")
    query(app, s.keeper, "UPDATE inv_items SET category_id = %s, preferred_supplier_id = %s WHERE id = %s", (drinks, s.sup, s.water))
    assert refused(app, s.keeper, "INSERT INTO inv_categories (user_id, name) VALUES (ew_current_user(), 'مشروبات')", constraint="inv_categories_name")
    query(app, s.keeper, "UPDATE inv_categories SET is_active = false WHERE id = %s", (drinks,))
    assert refused(app, s.keeper, "UPDATE inv_items SET category_id = %s WHERE id = %s", (drinks, sugar), constraint="inv_category_archived")
    assert refused(app, s.other, "UPDATE inv_items SET category_id = %s WHERE name = 'سكّر'", (drinks,), constraint="inv_category_archived")
    query(app, s.keeper, "UPDATE inv_suppliers SET is_active = false WHERE id = %s", (s.sup_novat,))
    assert refused(app, s.keeper, "UPDATE inv_items SET preferred_supplier_id = %s WHERE id = %s", (s.sup_novat, sugar), constraint="inv_supplier_archived")
    assert refused(app, s.keeper, "UPDATE inv_items SET vat_exemption_reason = 'دواء' WHERE id = %s", (sugar,), constraint="inv_item_exemption_needs_category")
    query(app, s.keeper, "UPDATE inv_items SET vat_category = 'Z', vat_exemption_reason = 'دواء مؤهّل' WHERE id = %s", (sugar,))
    assert refused(app, s.keeper, "UPDATE inv_items SET target_level_milli = 10000 WHERE id = %s", (s.water,), constraint="inv_item_target_shape")
    query(app, s.keeper, "UPDATE inv_items SET target_level_milli = 60000, selling_price_halalas = 1500 WHERE id = %s", (s.water,))
    assert query(app, s.keeper, "SELECT target_level_milli, selling_price_includes_vat, last_counted_on FROM inv_items WHERE id = %s",
                 (s.water,))[0] == (60000, True, None)
    assert query(app, s.keeper, "SELECT store_name, store_location FROM inv_settings")[0] == ("المخزن الرئيسي", None)
    query(app, s.keeper, "UPDATE inv_settings SET store_name = 'مستودع الدمام', store_location = 'حي الفيصلية'")
    assert refused(app, s.keeper, "UPDATE inv_settings SET store_name = ''", constraint="inv_store_name_shape")


def test_representatives_belong_to_their_supplier_and_are_snapshotted_on_posting(app, scene):
    s = scene
    assert refused(app, s.keeper, "UPDATE inv_suppliers SET cr_number = '12' WHERE id = %s", (s.sup,), constraint="inv_supplier_cr_shape")
    assert refused(app, s.keeper, "UPDATE inv_suppliers SET phone = '555' WHERE id = %s", (s.sup,), constraint="inv_supplier_phone_shape")
    query(app, s.keeper, "UPDATE inv_suppliers SET cr_number = '1010123456', phone = '0112345678' WHERE id = %s", (s.sup,))
    ahmad = rep(app, s.keeper, s.sup, "أحمد", "0501234567", default=True)
    assert refused(app, s.keeper, "INSERT INTO inv_supplier_reps (user_id, supplier_id, name, mobile) VALUES (ew_current_user(), %s, 'خالد', '12')",
                   (s.sup,), constraint="inv_rep_mobile_shape")
    assert refused(app, s.keeper, "INSERT INTO inv_supplier_reps (user_id, supplier_id, name) VALUES (ew_current_user(), %s, 'أحمد')",
                   (s.sup,), constraint="inv_supplier_reps_name")
    assert refused(app, s.other, "INSERT INTO inv_supplier_reps (user_id, supplier_id, name) VALUES (ew_current_user(), %s, 'أحمد')",
                   (s.sup,), constraint="inv_supplier_archived")
    khalid = rep(app, s.keeper, s.sup, "خالد", default=True)
    assert query(app, s.keeper, "SELECT name FROM inv_supplier_reps WHERE is_default ORDER BY name") == [("خالد",)]
    corner = rep(app, s.keeper, s.sup_novat, "سعد", "0559876543")
    # على الفاتورة: مندوبٌ من مورّدها فقط، ويُنزع حين يتغيّر المورّد، ويُحفظ اسمه وجواله عند التسجيل.
    assert refused(app, s.keeper, "INSERT INTO inv_purchases (user_id, supplier_id, rep_id) VALUES (ew_current_user(), %s, %s)",
                   (s.sup, corner), constraint="inv_rep_not_of_supplier")
    p = draft(app, s.keeper, s.sup, "REP-1", s.today, 115000)
    query(app, s.keeper, "UPDATE inv_purchases SET rep_id = %s, delivery_note_no = 'DN-7', received_on = %s WHERE id = %s", (ahmad, s.today, p))
    assert refused(app, s.keeper, "UPDATE inv_purchases SET rep_id = %s WHERE id = %s", (corner, p), constraint="inv_rep_not_of_supplier")
    query(app, s.keeper, "UPDATE inv_purchases SET supplier_id = %s WHERE id = %s", (s.sup_novat, p))
    assert scalar(app, s.keeper, "SELECT rep_id FROM inv_purchases WHERE id = %s", (p,)) is None
    query(app, s.keeper, "UPDATE inv_purchases SET supplier_id = %s, rep_id = %s WHERE id = %s", (s.sup, khalid, p))
    line(app, s.keeper, p, s.water, 10000, 10000)
    post(app, s.keeper, p)
    query(app, s.keeper, "UPDATE inv_supplier_reps SET name = 'خالد العمري', mobile = '0500000000' WHERE id = %s", (khalid,))
    assert query(app, s.keeper, "SELECT rep_name, rep_mobile, delivery_note_no FROM inv_purchases WHERE id = %s", (p,))[0] == ("خالد", None, "DN-7")
    assert refused(app, s.keeper, "UPDATE inv_purchases SET rep_id = %s WHERE id = %s", (ahmad, p), constraint="inv_document_is_final")
    # وعلى المرتجع من مندوبي مورّد الفاتورة، بسبب نقص التسليم، ويُحفظ كذلك.
    assert refused(app, s.keeper, "INSERT INTO inv_returns (user_id, purchase_id, rep_id) VALUES (ew_current_user(), %s, %s)",
                   (p, corner), constraint="inv_rep_not_of_supplier")
    r = ret(app, s.keeper, p, reason="SHORT_DELIVERY")
    query(app, s.keeper, "UPDATE inv_returns SET rep_id = %s WHERE id = %s", (ahmad, r))
    rline(app, s.keeper, r, 1, 2000)
    post_return(app, s.keeper, r)
    assert query(app, s.keeper, "SELECT rep_name, rep_mobile FROM inv_returns WHERE id = %s", (r,))[0] == ("أحمد", "0501234567")


def test_a_short_delivery_raises_its_flag_and_is_part_of_what_the_reviewer_sees(app, scene):
    s = scene
    p = draft(app, s.keeper, s.sup, "SD-1", s.today, 115000)
    line(app, s.keeper, p, s.water, 10000, 10000)
    before = scalar(app, s.keeper, "SELECT ew_inv_purchase_digest(%s)", (p,))
    assert refused(app, s.keeper, "UPDATE inv_purchase_lines SET received_quantity_milli = 11000 WHERE purchase_id = %s", (p,),
                   constraint="inv_line_received_range")
    assert refused(app, s.keeper, "UPDATE inv_purchase_lines SET received_quantity_milli = 500 WHERE purchase_id = %s", (p,),
                   constraint="inv_quantity_unit")
    version = rv(app, s.keeper, "inv_purchases", p)
    query(app, s.keeper, "UPDATE inv_purchase_lines SET received_quantity_milli = 8000 WHERE purchase_id = %s", (p,))
    assert rv(app, s.keeper, "inv_purchases", p) == version + 1
    assert "SHORT_DELIVERY:1" in flags(app, s.keeper, p)
    assert scalar(app, s.keeper, "SELECT ew_inv_purchase_digest(%s)", (p,)) != before
    assert scalar(app, s.keeper, "SELECT detail FROM ew_inv_purchase_flags(%s) WHERE code = 'SHORT_DELIVERY'", (p,)) == {"invoiced": 10000, "received": 8000}
    query(app, s.keeper, "UPDATE inv_purchase_lines SET received_quantity_milli = 10000 WHERE purchase_id = %s", (p,))
    assert "SHORT_DELIVERY:1" not in flags(app, s.keeper, p)
    query(app, s.keeper, "UPDATE inv_purchases SET received_on = %s WHERE id = %s", (s.today + datetime.timedelta(days=1), p))
    assert refused(app, s.keeper, "SELECT ew_inv_post_purchase(%s, %s, %s)", (p, rv(app, s.keeper, "inv_purchases", p), flags(app, s.keeper, p)),
                   constraint="inv_purchase_future_date")


def test_a_count_session_snapshots_the_books_counts_blind_and_posts_one_voucher_per_counted_line(owner, app, scene):
    s = scene
    voucher(app, s.keeper, "OPENING", s.water, 50000, cost=4550, day=s.today)
    voucher(app, s.keeper, "OPENING", s.rice, 20500, cost=900, day=s.today)
    tea = item(app, s.keeper, "شاي")
    token = uuid.uuid4()
    session, number, replayed = count_open(app, s.keeper, token=token)
    assert (number, replayed) == (1, False)
    assert count_open(app, s.keeper, token=token) == (session, 1, True)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_open(%s, 'ALL', NULL, NULL, true, NULL)", (uuid.uuid4(),),
                   constraint="inv_count_session_open")
    assert refused(app, s.other, "SELECT * FROM ew_inv_count_open(%s, 'ALL', NULL, NULL, true, NULL)", (uuid.uuid4(),),
                   constraint="inv_count_no_items")
    assert query(app, s.keeper, "SELECT scope, blind, items_total, last_purchase_number, last_voucher_number, status"
                                " FROM inv_count_sessions WHERE id = %s", (session,))[0] == ("ALL", True, 3, None, 2, "OPEN")
    assert query(app, s.keeper, "SELECT item_id, book_milli, counted_milli FROM inv_count_lines WHERE session_id = %s ORDER BY line_no",
                 (session,)) == [(s.rice, 20500, None), (tea, 0, None), (s.water, 50000, None)]
    assert scalar(app, s.other, "SELECT count(*) FROM inv_count_lines") == 0
    # المعدود بشكل الوحدة، والفرق بسببٍ في اتجاهه، ولا سبب بلا فرق.
    assert refused(app, s.keeper, "UPDATE inv_count_lines SET counted_milli = 500 WHERE session_id = %s AND item_id = %s", (session, s.water),
                   constraint="inv_quantity_unit")
    assert refused(app, s.keeper, "UPDATE inv_count_lines SET counted_milli = 48000 WHERE session_id = %s AND item_id = %s", (session, s.water),
                   constraint="inv_count_line_reason_needed")
    assert refused(app, s.keeper, "UPDATE inv_count_lines SET counted_milli = 48000, reason = 'FOUND' WHERE session_id = %s AND item_id = %s",
                   (session, s.water), constraint="inv_count_line_reason_needed")
    count_line(app, s.keeper, session, s.water, 48000, reason="DAMAGE")
    count_line(app, s.keeper, session, s.rice, 20500)
    count_line(app, s.keeper, session, tea, 3000, reason="FOUND")
    assert scalar(app, s.keeper, "SELECT count(*) FROM inv_count_lines WHERE session_id = %s AND counted_at IS NOT NULL", (session,)) == 3
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_post(%s, %s, %s)", (session, rv(app, s.keeper, "inv_count_sessions", session), s.today),
                   constraint="inv_count_needs_cost")
    count_line(app, s.keeper, session, tea, 3000, reason="FOUND", cost=2000)
    # رصيدٌ تحرّك بعد اللقطة: يوقف الترحيل حتى يُحدَّث ويُعاد عدّه.
    voucher(app, s.keeper, "ISSUE", s.rice, 500, reason="SALE", day=s.today)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_post(%s, %s, %s)", (session, rv(app, s.keeper, "inv_count_sessions", session), s.today),
                   constraint="inv_count_stale")
    assert scalar(app, s.keeper, "SELECT ew_inv_count_refresh(%s)", (session,)) == 1
    assert query(app, s.keeper, "SELECT book_milli, counted_milli, reason FROM inv_count_lines WHERE session_id = %s AND item_id = %s",
                 (session, s.rice))[0] == (20000, None, None)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_post(%s, %s, %s)", (session, rv(app, s.keeper, "inv_count_sessions", session),
                   s.today + datetime.timedelta(days=1)), constraint="inv_voucher_date")
    assert count_post(app, s.keeper, session, s.today) == (1, 2, 0)
    assert query(app, s.keeper, "SELECT status, items_counted, items_matched FROM inv_count_sessions WHERE id = %s", (session,))[0] == ("POSTED", 2, 0)
    assert query(app, s.keeper, "SELECT i.on_hand_milli, i.stock_value_halalas, i.last_counted_on FROM inv_items i WHERE i.id IN (%s, %s) ORDER BY i.number",
                 (s.water, tea)) == [(48000, 218400, s.today), (3000, 6000, s.today)]
    assert query(app, s.keeper, "SELECT v.kind, v.quantity_milli, v.on_hand_before_milli, v.reason, v.session_id = %s"
                                " FROM inv_count_lines l JOIN inv_vouchers v ON v.id = l.voucher_id WHERE l.session_id = %s ORDER BY l.line_no",
                 (session, session)) == [("COUNT", 3000, 0, "FOUND", True), ("COUNT", 48000, 50000, "DAMAGE", True)]
    assert scalar(app, s.keeper, "SELECT last_counted_on FROM inv_items WHERE id = %s", (s.rice,)) is None
    assert refused(app, s.keeper, "UPDATE inv_count_lines SET counted_milli = 1000 WHERE session_id = %s AND item_id = %s", (session, s.rice),
                   constraint="inv_count_not_open")
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_post(%s, 99, %s)", (session, s.today), constraint="inv_count_not_open")
    assert owner_refused(owner, "DELETE FROM inv_count_sessions WHERE id = %s", (session,), constraint="inv_record_is_permanent")
    # جلسةٌ على أصنافٍ مختارة، يُضاف إليها صنفٌ لم يكن في الكشف، ثم تُلغى وتحتفظ برقمها.
    session2 = count_open(app, s.keeper, scope="SELECTED", items=[s.water])[0]
    assert refused(app, s.keeper, "SELECT ew_inv_count_add_item(%s, %s)", (session2, s.ship), constraint="inv_movement_needs_stock_item")
    assert refused(app, s.keeper, "SELECT ew_inv_count_add_item(%s, %s)", (session2, s.water), constraint="inv_count_line_exists")
    assert scalar(app, s.keeper, "SELECT ew_inv_count_add_item(%s, %s)", (session2, tea)) == 2
    assert query(app, s.keeper, "SELECT number, items_total FROM inv_count_sessions WHERE id = %s", (session2,))[0] == (2, 2)
    assert scalar(app, s.keeper, "SELECT added_during_count FROM inv_count_lines WHERE session_id = %s AND item_id = %s", (session2, tea)) is True
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_post(%s, %s, %s)", (session2, rv(app, s.keeper, "inv_count_sessions", session2), s.today),
                   constraint="inv_count_nothing_counted")
    query(app, s.keeper, "SELECT ew_inv_count_cancel(%s, %s)", (session2, rv(app, s.keeper, "inv_count_sessions", session2)))
    assert query(app, s.keeper, "SELECT status, cancelled_at IS NOT NULL FROM inv_count_sessions WHERE id = %s", (session2,))[0] == ("CANCELLED", True)
    assert refused(app, s.keeper, "SELECT * FROM ew_inv_count_open(%s, 'CATEGORY', NULL, NULL, true, NULL)", (uuid.uuid4(),),
                   constraint="inv_count_scope")
    query(app, s.keeper, "UPDATE inv_items SET reorder_level_milli = 50000 WHERE id = %s", (s.water,))
    assert count_open(app, s.keeper, scope="LOW")[1] == 3
    assert scalar(app, s.keeper, "SELECT items_total FROM inv_count_sessions WHERE number = 3") == 1
