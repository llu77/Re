"""
خدمة المخزون
============
كل وصولٍ إلى جداول المخزون (`inv_*`) يمرّ من هنا، بعباراتٍ ثابتة في أعلى الملف
وبدور `eyework_app` وهوية صاحب الجلسة. القاعدة تفرض الضمانات (العزل، والمهنة،
وثبات ما سُجّل، والترقيم، والأرصدة، والسقوف)؛ وهذه الوحدة تترجم أخطاءها إلى
نتائج يفهمها الويب وتبني ما تعرضه الشاشات: الفاتورة بأسطرها ومجاميعها وما
ينقصها، وبطاقة الصنف، وجلسة الجرد بتقدّمها، والمصروفات بفتراتها.

**كل كتابةٍ على صفٍّ قائم مشروطةٌ بما رآه صاحبها** (`expected_row_version`)؛
الأسطر تُقفل رأس مستندها أوّلاً فتُرفض الضغطة المكرّرة والتبويب القديم بـ409.

**مراجعة سيمبول** تُسجَّل هنا أداةً في `reviewer.FEATURES` (قائمة الفحوص في
`inventory_prompt`، ودوالّ البدء والتسجيل والبصمة في 0010)، والمحمّل يبني
الموضوع بأقلّ ما يلزم: لا اسم ولا مورّد ولا رقم ولا تاريخ. وشاشات «اسأل
سيمبول» لهذه البوابة تُسجَّل في `assistant.SCREENS`.

«اليوم» بتوقيت الرياض من القاعدة (`ew_riyadh_today`)؛ بايثون لا يقرأ الساعة.
"""

from __future__ import annotations

import dataclasses
import datetime
import difflib
from typing import Any, Callable, Iterable, Mapping
from uuid import UUID

from psycopg import errors as pg_errors

from eyework import assistant, reviewer
from eyework.assistant_prompt import ScreenContext
from eyework.db import Database
from eyework.inventory_flags import LEVELS, flag_key, render
from eyework.inventory_prompt import CANDIDATE_RATIO, CANDIDATES_MAX, CATALOGUE, PAYLOAD_KEYS, purchase_payload, return_payload
from eyework.inventory_rules import (
    COUNT_SCOPE_NAMES,
    MAX_PAGE,
    PAGE_SIZES,
    UNIT_NAMES,
    count_label,
    credit_note_due,
    document_label,
    halalas_words,
    item_code,
    normalise_digits,
    normalise_text,
    quantity_words,
    reorder_suggestion,
    suggested_order,
)
from eyework.professions import Profession
from eyework.reviewer import ReviewFeature, Snapshot
from eyework.service_errors import Conflict, Invalid, NotFound

__all__ = [
    "FEATURE",
    "NOT_FOUND",
    "Conflict",
    "Invalid",
    "NotFound",
    "add_count_item",
    "add_line",
    "cancel_count",
    "create_category",
    "create_item",
    "create_purchase",
    "create_rep",
    "create_return",
    "create_supplier",
    "discard_purchase",
    "discard_return",
    "expenses",
    "expense_months",
    "get_count",
    "get_item",
    "get_purchase",
    "get_return",
    "get_settings",
    "get_supplier",
    "item_movements",
    "list_categories",
    "list_counts",
    "list_items",
    "list_purchases",
    "list_returns",
    "list_suppliers",
    "list_vouchers",
    "open_count",
    "patch_category",
    "patch_count",
    "patch_item",
    "patch_line",
    "patch_purchase",
    "patch_rep",
    "patch_return",
    "patch_supplier",
    "post_count",
    "post_purchase",
    "post_return",
    "purchase_flags",
    "put_credit_note",
    "put_return_line",
    "put_settings",
    "refresh_count",
    "remove_line",
    "return_flags",
    "reverse_purchase",
    "search_items",
    "set_count_line",
    "stock_voucher",
    "summary",
    "vat_tool",
]

NOT_FOUND = "لم يُعثر على المستند."
#: ما يعدّه السقف «آخر المشتريات» في بطاقة الصنف.
RECENT_PURCHASES = 5
SIMILAR_MAX = 3
SIMILAR_RATIO = 0.8
#: أطول فترةٍ للمصروفات، كما في المواصفة §5.3.
EXPENSES_MAX_DAYS = 366

# ── العبارات: الإعدادات والمورّدون والتصنيفات ───────────────────────────
_TODAY = "SELECT ew_riyadh_today() AS today"
_PROFESSION = "SELECT ew_my_profession() AS profession"
_DISPLAY_NAME = "SELECT ew_my_display_name() AS name"
_SETTINGS = """
SELECT s.cost_includes_vat, s.store_name, s.store_location, s.row_version,
       EXISTS (SELECT 1 FROM inv_movements m WHERE m.user_id = s.user_id) AS cost_basis_locked
  FROM inv_settings s
"""
_INSERT_SETTINGS = """
INSERT INTO inv_settings (user_id, cost_includes_vat, store_name, store_location)
VALUES (ew_current_user(), %s, coalesce(%s, 'المخزن الرئيسي'), %s)
"""
_UPDATE_SETTINGS = """
UPDATE inv_settings SET cost_includes_vat = %s, store_name = coalesce(%s, store_name), store_location = %s
 WHERE row_version = %s
"""
_SETTINGS_VERSION = "SELECT row_version FROM inv_settings FOR UPDATE"

_SUPPLIER_COLUMNS = "s.id, s.name, s.vat_number, s.cr_number, s.phone, s.note, s.is_active, s.row_version"
_SUPPLIERS = """
SELECT s.id, s.name, s.vat_number, s.cr_number, s.phone, s.note, s.is_active, s.row_version, count(*) OVER () AS total
  FROM inv_suppliers s
 WHERE s.is_active = %s
   AND (%s::text IS NULL OR s.name_key LIKE '%%' || ew_inv_name_key(%s) || '%%' OR s.vat_number LIKE %s || '%%')
 ORDER BY s.name_key, s.id
 LIMIT %s OFFSET %s
"""
_SUPPLIER = "SELECT s.id, s.name, s.vat_number, s.cr_number, s.phone, s.note, s.is_active, s.row_version FROM inv_suppliers s WHERE s.id = %s"
_SUPPLIER_SAME_VAT = "SELECT s.id, s.name, s.vat_number, s.cr_number, s.phone, s.note, s.is_active, s.row_version FROM inv_suppliers s WHERE s.vat_number = %s AND s.id <> %s ORDER BY s.name_key"
_INSERT_SUPPLIER = """
INSERT INTO inv_suppliers (user_id, name, vat_number, cr_number, phone, note)
VALUES (ew_current_user(), %s, %s, %s, %s, %s) RETURNING id
"""
_UPDATE_SUPPLIER = """
UPDATE inv_suppliers
   SET name = coalesce(%s, name), vat_number = CASE WHEN %s THEN %s ELSE vat_number END,
       cr_number = CASE WHEN %s THEN %s ELSE cr_number END, phone = CASE WHEN %s THEN %s ELSE phone END,
       note = CASE WHEN %s THEN %s ELSE note END, is_active = coalesce(%s, is_active)
 WHERE id = %s AND row_version = %s
"""
_SUPPLIER_LOCK = "SELECT row_version FROM inv_suppliers WHERE id = %s FOR UPDATE"
_REPS = """
SELECT r.id, r.supplier_id, r.name, r.mobile, r.is_default, r.is_active, r.row_version
  FROM inv_supplier_reps r WHERE r.supplier_id = %s ORDER BY r.is_default DESC, r.name_key, r.id
"""
_REP = """
SELECT r.id, r.supplier_id, r.name, r.mobile, r.is_default, r.is_active, r.row_version
  FROM inv_supplier_reps r WHERE r.id = %s AND r.supplier_id = %s
"""
_INSERT_REP = """
INSERT INTO inv_supplier_reps (user_id, supplier_id, name, mobile, is_default)
VALUES (ew_current_user(), %s, %s, %s, %s) RETURNING id
"""
_UPDATE_REP = """
UPDATE inv_supplier_reps
   SET name = coalesce(%s, name), mobile = CASE WHEN %s THEN %s ELSE mobile END,
       is_default = coalesce(%s, is_default), is_active = coalesce(%s, is_active)
 WHERE id = %s AND supplier_id = %s AND row_version = %s
"""
_REP_LOCK = "SELECT row_version FROM inv_supplier_reps WHERE id = %s AND supplier_id = %s FOR UPDATE"

_CATEGORIES = """
SELECT c.id, c.name, c.is_active, c.row_version, (SELECT count(*) FROM inv_items i WHERE i.category_id = c.id AND i.is_active) AS items
  FROM inv_categories c WHERE c.is_active OR %s ORDER BY c.name_key, c.id
"""
_CATEGORY = "SELECT c.id, c.name, c.is_active, c.row_version FROM inv_categories c WHERE c.id = %s"
_INSERT_CATEGORY = "INSERT INTO inv_categories (user_id, name) VALUES (ew_current_user(), %s) RETURNING id"
_UPDATE_CATEGORY = """
UPDATE inv_categories SET name = coalesce(%s, name), is_active = coalesce(%s, is_active)
 WHERE id = %s AND row_version = %s
"""
_CATEGORY_LOCK = "SELECT row_version FROM inv_categories WHERE id = %s FOR UPDATE"

# ── العبارات: الأصناف ───────────────────────────────────────────────────
_ITEM_COLUMNS = """
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile
"""
_ITEM_FROM = """
  FROM inv_items i
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
"""
_ITEMS = """
SELECT 
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile
, count(*) OVER () AS total

  FROM inv_items i
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id

 WHERE CASE %s WHEN 'archived' THEN NOT i.is_active
               WHEN 'low' THEN i.is_active AND i.reorder_level_milli IS NOT NULL AND i.on_hand_milli <= i.reorder_level_milli
               WHEN 'service' THEN i.is_active AND i.kind = 'SERVICE'
               WHEN 'uncounted' THEN i.is_active AND i.kind = 'STOCK'
                                     AND (i.last_counted_on IS NULL OR i.last_counted_on < ew_riyadh_today() - 90)
               ELSE i.is_active END
   AND (%s::uuid IS NULL OR i.category_id = %s)
   AND (%s::text IS NULL OR i.name_key LIKE '%%' || ew_inv_name_key(%s) || '%%'
        OR upper(i.supplier_code) LIKE upper(%s) || '%%' OR i.barcode LIKE %s || '%%' OR i.number::text = %s)
 ORDER BY i.name_key, i.id
 LIMIT %s OFFSET %s
"""
_ITEM = """SELECT 
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile
 
  FROM inv_items i
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
 WHERE i.id = %s"""
_ITEM_SEARCH = """
SELECT 
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile


  FROM inv_items i
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id

 WHERE i.is_active
   AND (i.name_key LIKE '%%' || ew_inv_name_key(%s) || '%%' OR upper(i.supplier_code) LIKE upper(%s) || '%%'
        OR i.barcode = %s OR i.number::text = %s)
 ORDER BY (i.name_key = ew_inv_name_key(%s)) DESC, (i.barcode = %s) DESC, i.name_key, i.id
 LIMIT %s
"""
_ITEM_EXACT = "SELECT 1 FROM inv_items i WHERE i.is_active AND i.name_key = ew_inv_name_key(%s)"
_ITEM_NAMES = "SELECT i.id, i.name, i.name_key, i.unit FROM inv_items i WHERE i.is_active AND i.kind = 'STOCK' AND i.id <> %s"
_ACTIVE_ITEM_NAMES = "SELECT i.id, i.name, i.name_key, i.unit FROM inv_items i WHERE i.is_active"
_STOCK_VALUE = "SELECT coalesce(sum(i.stock_value_halalas), 0)::bigint AS value FROM inv_items i"
_INSERT_ITEM = """
INSERT INTO inv_items (user_id, name, supplier_code, barcode, kind, unit, category_id, vat_category, vat_exemption_reason,
                       price_halalas, selling_price_halalas, selling_price_includes_vat, reorder_level_milli,
                       target_level_milli, preferred_supplier_id, note)
VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
"""
_UPDATE_ITEM = """
UPDATE inv_items
   SET name = coalesce(%s, name),
       supplier_code = CASE WHEN %s THEN %s ELSE supplier_code END,
       barcode = CASE WHEN %s THEN %s ELSE barcode END,
       kind = coalesce(%s, kind), unit = coalesce(%s, unit),
       category_id = CASE WHEN %s THEN %s ELSE category_id END,
       vat_category = coalesce(%s, vat_category),
       vat_exemption_reason = CASE WHEN %s THEN %s ELSE vat_exemption_reason END,
       price_halalas = coalesce(%s, price_halalas),
       selling_price_halalas = CASE WHEN %s THEN %s ELSE selling_price_halalas END,
       selling_price_includes_vat = coalesce(%s, selling_price_includes_vat),
       reorder_level_milli = CASE WHEN %s THEN %s ELSE reorder_level_milli END,
       target_level_milli = CASE WHEN %s THEN %s ELSE target_level_milli END,
       preferred_supplier_id = CASE WHEN %s THEN %s ELSE preferred_supplier_id END,
       note = CASE WHEN %s THEN %s ELSE note END,
       is_active = coalesce(%s, is_active)
 WHERE id = %s AND row_version = %s
"""
_ITEM_LOCK = "SELECT row_version FROM inv_items WHERE id = %s FOR UPDATE"
_ITEM_RECENT_LINES = """
SELECT p.number, p.invoice_date, p.supplier_name, l.quantity_milli, l.unit, l.net_halalas
  FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
 WHERE l.item_id = %s AND p.status = 'POSTED'
 ORDER BY p.posted_at DESC, l.line_no DESC
 LIMIT %s
"""
_ITEM_MOVEMENTS = """
SELECT m.kind, m.occurred_on, m.quantity_milli, m.value_halalas, m.on_hand_after_milli, m.value_after_halalas,
       p.number AS purchase_number, p.reversal_number, r.number AS return_number, v.number AS voucher_number,
       v.kind AS voucher_kind, v.reason AS voucher_reason, cs.number AS count_number,
       count(*) OVER () AS total
  FROM inv_movements m
  LEFT JOIN inv_purchases p ON p.id = m.purchase_id
  LEFT JOIN inv_returns r ON r.id = m.return_id
  LEFT JOIN inv_vouchers v ON v.id = m.voucher_id
  LEFT JOIN inv_count_sessions cs ON cs.id = v.session_id
 WHERE m.item_id = %s
 ORDER BY m.seq DESC
 LIMIT %s OFFSET %s
"""
_ITEM_ISSUED_90 = """
SELECT coalesce(sum(m.quantity_milli), 0)::bigint AS issued, count(*) AS movements
  FROM inv_movements m WHERE m.item_id = %s AND m.kind IN ('ISSUE_OUT', 'RETURN_OUT') AND m.occurred_on >= ew_riyadh_today() - 90
"""
_ITEM_COUNT_HISTORY = """
SELECT cs.number, v.occurred_on, v.on_hand_before_milli, v.quantity_milli, v.reason
  FROM inv_vouchers v LEFT JOIN inv_count_sessions cs ON cs.id = v.session_id
 WHERE v.item_id = %s AND v.kind = 'COUNT'
 ORDER BY v.created_at DESC LIMIT 6
"""


# ── أدوات ───────────────────────────────────────────────────────────────
class _Pager:
    """صفحةٌ وحجمها كما يقبلهما المسار، وما يُرجع: items وpage وpages وtotal."""

    def __init__(self, page: int, size: int) -> None:
        if size not in PAGE_SIZES or not 1 <= page <= MAX_PAGE:
            raise Invalid("PAGE", field="page")
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    def wrap(self, rows: list[dict], items: list) -> dict:
        total = rows[0]["total"] if rows else 0
        return {"items": items, "page": self.page, "pages": max(1, -(-total // self.size)), "total": total}


def _rows(cursor, statement: str, params: tuple) -> list[dict]:
    cursor.execute(statement, params)
    return [dict(row) for row in cursor.fetchall()]


def _one(cursor, statement: str, params: tuple) -> dict:
    cursor.execute(statement, params)
    row = cursor.fetchone()
    if row is None:
        raise NotFound("NOT_FOUND", NOT_FOUND)
    return dict(row)


def _lock_version(cursor, statement: str, params: tuple, expected: int) -> None:
    """يقفل الصفّ ويقارن رقمه بما رآه صاحبه: 404 إن غاب و409 إن تغيّر."""
    row = _one(cursor, statement, params)
    if row["row_version"] != expected:
        raise Conflict("STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")


def _today(cursor) -> datetime.date:
    cursor.execute(_TODAY)
    return cursor.fetchone()["today"]


def _display_name(cursor) -> str | None:
    cursor.execute(_DISPLAY_NAME)
    return cursor.fetchone()["name"]


def _text(value: str | None) -> str | None:
    return None if value is None else normalise_text(value)


def _digits(value: str | None) -> str | None:
    return None if value is None else normalise_digits(normalise_text(value))


def _date(value: str | None, field: str) -> datetime.date | None:
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(normalise_digits(value))
    except ValueError as error:
        raise Invalid("INV_DATE", field=field) from error


def _iso(value: object) -> str | None:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return None


# ── الإعدادات ──────────────────────────────────────────────────────────
def _settings_view(row: Mapping) -> dict:
    return {"cost_includes_vat": row["cost_includes_vat"], "cost_basis_locked": row["cost_basis_locked"],
            "store_name": row["store_name"], "store_location": row["store_location"], "row_version": row["row_version"]}


def get_settings(db: Database, user_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_SETTINGS)
        row = cursor.fetchone()
    if row is None:
        raise NotFound("INV_SETUP", "أجب أولاً عن سؤال ضريبة المشتريات في إعدادات المخزون.")
    return _settings_view(row)


def put_settings(db: Database, user_id: UUID, cost_includes_vat: bool, store_name: str | None,
                 store_location: str | None, expected_row_version: int | None) -> dict:
    """ينشئ الإعدادات أوّل مرة (بلا رقم صفّ)، أو يحدّثها بما رآه صاحبها."""
    with db.session(user_id) as cursor:
        cursor.execute(_SETTINGS_VERSION)
        row = cursor.fetchone()
        if row is None:
            cursor.execute(_INSERT_SETTINGS, (cost_includes_vat, _text(store_name), _text(store_location)))
        else:
            if expected_row_version is None or row["row_version"] != expected_row_version:
                raise Conflict("STALE", "تغيّرت الإعدادات منذ عرضها. راجعها مرة أخرى.")
            cursor.execute(_UPDATE_SETTINGS, (cost_includes_vat, _text(store_name), _text(store_location),
                                              expected_row_version))
        cursor.execute(_SETTINGS)
        return _settings_view(cursor.fetchone())


# ── المورّدون ومندوبوهم ────────────────────────────────────────────────
def _supplier_view(row: Mapping, reps: list[dict] | None = None) -> dict:
    view = {"id": str(row["id"]), "name": row["name"], "vat_number": row["vat_number"], "cr_number": row["cr_number"],
            "phone": row["phone"], "note": row["note"], "is_active": row["is_active"], "row_version": row["row_version"]}
    if reps is not None:
        view["reps"] = reps
    return view


def _rep_view(row: Mapping) -> dict:
    return {"id": str(row["id"]), "supplier_id": str(row["supplier_id"]), "name": row["name"], "mobile": row["mobile"],
            "is_default": row["is_default"], "is_active": row["is_active"], "row_version": row["row_version"]}


def list_suppliers(db: Database, user_id: UUID, q: str | None, page: int, size: int, archived: bool) -> dict:
    pager = _Pager(page, size)
    query = _text(q) or None
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _SUPPLIERS, (not archived, query, query, _digits(query), pager.size, pager.offset))
    return pager.wrap(rows, [_supplier_view(row) for row in rows])


def get_supplier(db: Database, user_id: UUID, supplier_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        row = _one(cursor, _SUPPLIER, (supplier_id,))
        reps = [_rep_view(rep) for rep in _rows(cursor, _REPS, (supplier_id,))]
    return _supplier_view(row, reps)


def create_supplier(db: Database, user_id: UUID, name: str, vat_number: str | None, cr_number: str | None,
                    phone: str | None, note: str | None) -> dict:
    """مورّدٌ جديد، ومعه من يحمل الرقم الضريبي نفسه (معلومةٌ لا منع)."""
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_SUPPLIER, (normalise_text(name), _digits(vat_number), _digits(cr_number), _digits(phone), _text(note)))
        supplier_id = cursor.fetchone()["id"]
        row = _one(cursor, _SUPPLIER, (supplier_id,))
        same = _rows(cursor, _SUPPLIER_SAME_VAT, (row["vat_number"], supplier_id)) if row["vat_number"] else []
    view = _supplier_view(row, [])
    view["same_vat_number"] = [_supplier_view(other) for other in same]
    return view


def patch_supplier(db: Database, user_id: UUID, supplier_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    """`fields` ما جاء في الطلب وحده: الغائب لا يتغيّر، والحاضر فارغاً يُمحى."""
    with db.session(user_id) as cursor:
        _lock_version(cursor, _SUPPLIER_LOCK, (supplier_id,), expected_row_version)
        cursor.execute(_UPDATE_SUPPLIER, (
            _text(fields.get("name")),
            "vat_number" in fields, _digits(fields.get("vat_number")),
            "cr_number" in fields, _digits(fields.get("cr_number")),
            "phone" in fields, _digits(fields.get("phone")),
            "note" in fields, _text(fields.get("note")),
            fields.get("is_active"), supplier_id, expected_row_version))
        row = _one(cursor, _SUPPLIER, (supplier_id,))
        reps = [_rep_view(rep) for rep in _rows(cursor, _REPS, (supplier_id,))]
    return _supplier_view(row, reps)


def create_rep(db: Database, user_id: UUID, supplier_id: UUID, name: str, mobile: str | None, is_default: bool) -> dict:
    with db.session(user_id) as cursor:
        _one(cursor, _SUPPLIER, (supplier_id,))
        cursor.execute(_INSERT_REP, (supplier_id, normalise_text(name), _digits(mobile), is_default))
        rep_id = cursor.fetchone()["id"]
        return _rep_view(_one(cursor, _REP, (rep_id, supplier_id)))


def patch_rep(db: Database, user_id: UUID, supplier_id: UUID, rep_id: UUID, expected_row_version: int,
              fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _lock_version(cursor, _REP_LOCK, (rep_id, supplier_id), expected_row_version)
        cursor.execute(_UPDATE_REP, (_text(fields.get("name")), "mobile" in fields, _digits(fields.get("mobile")),
                                     fields.get("is_default"), fields.get("is_active"), rep_id, supplier_id,
                                     expected_row_version))
        return _rep_view(_one(cursor, _REP, (rep_id, supplier_id)))


# ── التصنيفات ──────────────────────────────────────────────────────────
def _category_view(row: Mapping) -> dict:
    view = {"id": str(row["id"]), "name": row["name"], "is_active": row["is_active"], "row_version": row["row_version"]}
    if "items" in row:
        view["items"] = row["items"]
    return view


def list_categories(db: Database, user_id: UUID, archived: bool) -> list[dict]:
    with db.session(user_id) as cursor:
        return [_category_view(row) for row in _rows(cursor, _CATEGORIES, (archived,))]


def create_category(db: Database, user_id: UUID, name: str) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_CATEGORY, (normalise_text(name),))
        return _category_view(_one(cursor, _CATEGORY, (cursor.fetchone()["id"],)))


def patch_category(db: Database, user_id: UUID, category_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _lock_version(cursor, _CATEGORY_LOCK, (category_id,), expected_row_version)
        cursor.execute(_UPDATE_CATEGORY, (_text(fields.get("name")), fields.get("is_active"), category_id, expected_row_version))
        return _category_view(_one(cursor, _CATEGORY, (category_id,)))


# ── الأصناف ────────────────────────────────────────────────────────────
def _item_option(row: Mapping, *, prices_include_vat: bool = False) -> dict:
    """ما يحتاجه منتقي الصنف وسطر الفاتورة: الرمز والاسم والوحدة والسعر بأساس المسودة."""
    price = row["price_halalas"]
    entry = round(price * 1.15) if prices_include_vat and row["vat_category"] == "S" else price
    return {
        "id": str(row["id"]), "number": row["number"], "code": item_code(row["number"]), "name": row["name"],
        "unit": row["unit"], "unit_name": UNIT_NAMES[row["unit"]], "kind": row["kind"], "vat_category": row["vat_category"],
        "barcode": row["barcode"], "supplier_code": row["supplier_code"],
        "price_halalas": price, "price_entry_halalas": entry, "on_hand_milli": row["on_hand_milli"],
        "last_price_halalas": row["last_price_halalas"],
    }


def _item_row(row: Mapping) -> dict:
    on_hand = row["on_hand_milli"]
    avg = round(row["stock_value_halalas"] * 1000 / on_hand) if on_hand else None
    view = _item_option(row)
    view.update({
        "avg_cost_halalas": avg, "stock_value_halalas": row["stock_value_halalas"],
        "reorder_level_milli": row["reorder_level_milli"], "target_level_milli": row["target_level_milli"],
        "below_reorder": row["reorder_level_milli"] is not None and on_hand <= row["reorder_level_milli"],
        "suggested_order_milli": suggested_order(on_hand, row["reorder_level_milli"], row["target_level_milli"]),
        "category": None if row["category_id"] is None else {"id": str(row["category_id"]), "name": row["category_name"]},
        "preferred_supplier": None if row["preferred_supplier_id"] is None else {
            "id": str(row["preferred_supplier_id"]), "name": row["preferred_supplier_name"],
            "rep_name": row["preferred_rep_name"], "rep_mobile": row["preferred_rep_mobile"]},
        "selling_price_halalas": row["selling_price_halalas"], "selling_price_includes_vat": row["selling_price_includes_vat"],
        "vat_exemption_reason": row["vat_exemption_reason"], "note": row["note"],
        "last_counted_on": _iso(row["last_counted_on"]), "last_movement_at": _iso(row["last_movement_at"]),
        "is_active": row["is_active"], "row_version": row["row_version"],
    })
    return view


def list_items(db: Database, user_id: UUID, q: str | None, filter_name: str, category_id: UUID | None,
               page: int, size: int) -> dict:
    pager = _Pager(page, size)
    if filter_name not in ("all", "low", "service", "archived", "uncounted"):
        raise Invalid("FILTER", field="filter")
    query = _text(q) or None
    digits = _digits(query)
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _ITEMS, (filter_name, category_id, category_id, query, query, query, digits, digits,
                                      pager.size, pager.offset))
        cursor.execute(_STOCK_VALUE)
        value = cursor.fetchone()["value"]
    view = pager.wrap(rows, [_item_row(row) for row in rows])
    view["stock_value_halalas"] = value
    return view


def search_items(db: Database, user_id: UUID, q: str, purchase_id: UUID | None, limit: int = 8) -> dict:
    """المنتقي: ثمانية خياراتٍ على الأكثر، و`create` باسم ما كُتب إن لم يطابق صنفاً بالضبط."""
    query = normalise_text(q)
    if not query:
        return {"items": [], "create": None}
    digits = normalise_digits(query)
    with db.session(user_id) as cursor:
        incl = False
        if purchase_id is not None:
            cursor.execute("SELECT prices_include_vat FROM inv_purchases WHERE id = %s", (purchase_id,))
            found = cursor.fetchone()
            incl = bool(found and found["prices_include_vat"])
        rows = _rows(cursor, _ITEM_SEARCH, (query, query, digits, digits, query, digits, limit))
        cursor.execute(_ITEM_EXACT, (query,))
        exact = cursor.fetchone() is not None
    return {"items": [_item_option(row, prices_include_vat=incl) for row in rows],
            "create": None if exact else {"name": query}}


def _name_similarity(a: str, b: str) -> float:
    """تشابه مفتاحي اسمين: على النصّ كما هو، أو على كلماته مرتّبة (الترتيب المختلف لا يُبعد)."""
    direct = difflib.SequenceMatcher(None, a, b).ratio()
    sorted_a = " ".join(sorted(a.split()))
    sorted_b = " ".join(sorted(b.split()))
    return max(direct, difflib.SequenceMatcher(None, sorted_a, sorted_b).ratio())


def _similar(cursor, name: str, exclude: UUID | None, *, ratio: float, limit: int, stock_only: bool) -> list[dict]:
    """أقرب الأصناف اسماً بنسبة تشابه `difflib` على مفتاح الاسم؛ للمعلومة وللمرشَّحين."""
    cursor.execute("SELECT ew_inv_name_key(%s) AS key", (name,))
    key = cursor.fetchone()["key"]
    if stock_only:
        cursor.execute(_ITEM_NAMES, (exclude,))
    else:
        cursor.execute(_ACTIVE_ITEM_NAMES)
    scored = []
    for row in cursor.fetchall():
        if row["id"] == exclude:
            continue
        score = _name_similarity(key, row["name_key"])
        if score >= ratio:
            scored.append((score, dict(row)))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["name_key"]))
    return [row for _, row in scored[:limit]]


def get_item(db: Database, user_id: UUID, item_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        row = _one(cursor, _ITEM, (item_id,))
        recent = _rows(cursor, _ITEM_RECENT_LINES, (item_id, RECENT_PURCHASES))
        cursor.execute(_ITEM_ISSUED_90, (item_id,))
        issued = cursor.fetchone()
        counts = _rows(cursor, _ITEM_COUNT_HISTORY, (item_id,))
    view = _item_row(row)
    view["recent_purchases"] = [{
        "document": document_label("PURCHASE", line["number"]), "invoice_date": _iso(line["invoice_date"]),
        "supplier_name": line["supplier_name"], "quantity_milli": line["quantity_milli"],
        "unit_price_halalas": round(line["net_halalas"] * 1000 / line["quantity_milli"]) if line["quantity_milli"] else None,
    } for line in recent]
    view["reorder_suggestion_milli"] = reorder_suggestion(issued["issued"], issued["movements"], row["unit"])
    view["counts"] = [{
        "session": None if count["number"] is None else count_label(count["number"]),
        "occurred_on": _iso(count["occurred_on"]), "book_milli": count["on_hand_before_milli"],
        "counted_milli": count["quantity_milli"], "reason": count["reason"],
    } for count in counts]
    return view


def item_movements(db: Database, user_id: UUID, item_id: UUID, page: int, size: int) -> dict:
    """بطاقة الصنف: التاريخ والمستند والنوع والوارد والمنصرف والرصيد بعد والقيمة بعد."""
    pager = _Pager(page, size)
    with db.session(user_id) as cursor:
        _one(cursor, "SELECT id FROM inv_items WHERE id = %s", (item_id,))
        rows = _rows(cursor, _ITEM_MOVEMENTS, (item_id, pager.size, pager.offset))
    items = []
    for row in rows:
        if row["purchase_number"] is not None and row["kind"] == "REVERSAL_OUT":
            document = document_label("REVERSAL", row["reversal_number"])
        elif row["purchase_number"] is not None:
            document = document_label("PURCHASE", row["purchase_number"])
        elif row["return_number"] is not None:
            document = document_label("RETURN", row["return_number"])
        elif row["count_number"] is not None:
            document = count_label(row["count_number"])
        else:
            document = document_label("VOUCHER", row["voucher_number"])
        inbound = row["kind"].endswith("_IN")
        unit_cost = round(row["value_halalas"] * 1000 / row["quantity_milli"]) if row["quantity_milli"] else None
        items.append({
            "kind": row["kind"], "occurred_on": _iso(row["occurred_on"]), "document": document,
            "in_milli": row["quantity_milli"] if inbound else 0, "out_milli": 0 if inbound else row["quantity_milli"],
            "unit_cost_halalas": unit_cost, "value_halalas": row["value_halalas"],
            "on_hand_after_milli": row["on_hand_after_milli"], "value_after_halalas": row["value_after_halalas"],
            "reason": row["voucher_reason"],
        })
    return pager.wrap(rows, items)


_ITEM_FIELDS = ("supplier_code", "barcode", "kind", "unit", "category_id", "vat_category", "vat_exemption_reason",
                "price_halalas", "selling_price_halalas", "selling_price_includes_vat", "reorder_level_milli",
                "target_level_milli", "preferred_supplier_id", "note")


def create_item(db: Database, user_id: UUID, fields: Mapping) -> dict:
    """صنفٌ جديد برقمه من العدّاد، ومعه أقرب الأصناف اسماً (معلومةٌ لا منع)."""
    name = normalise_text(fields["name"])
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_ITEM, (
            name, _digits(fields.get("supplier_code")), _digits(fields.get("barcode")), fields["kind"], fields["unit"],
            fields.get("category_id"), fields.get("vat_category", "S"), _text(fields.get("vat_exemption_reason")),
            fields["price_halalas"], fields.get("selling_price_halalas"), fields.get("selling_price_includes_vat", True),
            fields.get("reorder_level_milli"), fields.get("target_level_milli"), fields.get("preferred_supplier_id"),
            _text(fields.get("note"))))
        item_id = cursor.fetchone()["id"]
        row = _one(cursor, _ITEM, (item_id,))
        similar = _similar(cursor, name, item_id, ratio=SIMILAR_RATIO, limit=SIMILAR_MAX, stock_only=False)
        options = [_item_option(_one(cursor, _ITEM, (other["id"],))) for other in similar]
    view = _item_row(row)
    view["similar"] = options
    return view


def patch_item(db: Database, user_id: UUID, item_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _lock_version(cursor, _ITEM_LOCK, (item_id,), expected_row_version)
        cursor.execute(_UPDATE_ITEM, (
            _text(fields.get("name")),
            "supplier_code" in fields, _digits(fields.get("supplier_code")),
            "barcode" in fields, _digits(fields.get("barcode")),
            fields.get("kind"), fields.get("unit"),
            "category_id" in fields, fields.get("category_id"),
            fields.get("vat_category"),
            "vat_exemption_reason" in fields, _text(fields.get("vat_exemption_reason")),
            fields.get("price_halalas"),
            "selling_price_halalas" in fields, fields.get("selling_price_halalas"),
            fields.get("selling_price_includes_vat"),
            "reorder_level_milli" in fields, fields.get("reorder_level_milli"),
            "target_level_milli" in fields, fields.get("target_level_milli"),
            "preferred_supplier_id" in fields, fields.get("preferred_supplier_id"),
            "note" in fields, _text(fields.get("note")),
            fields.get("is_active"), item_id, expected_row_version))
        return _item_row(_one(cursor, _ITEM, (item_id,)))


# ── العبارات: فاتورة الشراء ────────────────────────────────────────────
_PURCHASE = """
SELECT p.id, p.status, p.row_version, p.number, p.supplier_id, p.supplier_invoice_no, p.invoice_date,
       p.prices_include_vat, p.printed_total_halalas, p.printed_vat_halalas, p.note, p.rep_id, p.delivery_note_no,
       p.received_on, p.posted_at, p.supplier_name, p.supplier_vat_number, p.rep_name, p.rep_mobile,
       p.subtotal_halalas, p.vat_halalas, p.total_halalas, p.reversal_number, p.reversed_at, p.reversal_reason,
       p.reversal_note, p.created_at, p.updated_at,
       s.name AS current_supplier_name, s.vat_number AS current_supplier_vat, s.is_active AS supplier_active,
       r.name AS current_rep_name, r.mobile AS current_rep_mobile
  FROM inv_purchases p
  LEFT JOIN inv_suppliers s ON s.id = p.supplier_id
  LEFT JOIN inv_supplier_reps r ON r.id = p.rep_id
 WHERE p.id = %s
"""
_PURCHASE_LINES = """
SELECT l.line_no, l.quantity_milli, l.unit_price_halalas, l.discount_halalas, l.vat_category AS line_vat_category,
       l.received_quantity_milli, l.net_halalas AS posted_net, l.line_vat_halalas AS posted_vat, l.amount_halalas AS posted_amount,
       l.item_name AS posted_item_name, l.unit AS posted_unit,
       
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile

  FROM inv_purchase_lines l
  JOIN inv_items i ON i.id = l.item_id
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
 WHERE l.purchase_id = %s
 ORDER BY l.line_no
"""
_PURCHASE_CALC = "SELECT line_no, vat_rate_bp, amount_halalas, net_halalas, vat_halalas FROM ew_inv_purchase_calc(%s)"
_PURCHASE_RETURNS = "SELECT id, number, status FROM inv_returns WHERE purchase_id = %s ORDER BY created_at"
_PURCHASE_RETURNED = """
SELECT l.line_no, (l.quantity_milli - coalesce((SELECT sum(rl.quantity_milli) FROM inv_return_lines rl
                                                JOIN inv_returns rr ON rr.id = rl.return_id
                                               WHERE rl.purchase_id = l.purchase_id AND rl.line_no = l.line_no
                                                 AND rr.status = 'POSTED'), 0))::bigint AS remaining_milli
  FROM inv_purchase_lines l WHERE l.purchase_id = %s
"""
_PURCHASES = """
SELECT p.id, p.status, p.row_version, p.number, p.supplier_invoice_no, p.invoice_date, p.total_halalas, p.updated_at,
       p.posted_at, p.reversal_number, coalesce(p.supplier_name, s.name) AS supplier_name,
       (SELECT count(*) FROM inv_purchase_lines l WHERE l.purchase_id = p.id) AS lines,
       count(*) OVER () AS total
  FROM inv_purchases p LEFT JOIN inv_suppliers s ON s.id = p.supplier_id
 WHERE (%s::text IS NULL OR p.status = %s)
   AND (%s::text IS NULL OR p.number::text = %s OR p.supplier_invoice_key = ew_inv_doc_key(%s)
        OR coalesce(p.supplier_name, s.name) LIKE '%%' || %s || '%%')
 ORDER BY p.updated_at DESC, p.id
 LIMIT %s OFFSET %s
"""
_INSERT_PURCHASE = """
INSERT INTO inv_purchases (user_id, supplier_id, supplier_invoice_no, invoice_date, prices_include_vat,
                           printed_total_halalas, printed_vat_halalas, note, rep_id, delivery_note_no, received_on)
VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
"""
_UPDATE_PURCHASE = """
UPDATE inv_purchases
   SET supplier_id = CASE WHEN %s THEN %s ELSE supplier_id END,
       supplier_invoice_no = CASE WHEN %s THEN %s ELSE supplier_invoice_no END,
       invoice_date = CASE WHEN %s THEN %s ELSE invoice_date END,
       prices_include_vat = coalesce(%s, prices_include_vat),
       printed_total_halalas = CASE WHEN %s THEN %s ELSE printed_total_halalas END,
       printed_vat_halalas = CASE WHEN %s THEN %s ELSE printed_vat_halalas END,
       note = CASE WHEN %s THEN %s ELSE note END,
       rep_id = CASE WHEN %s THEN %s ELSE rep_id END,
       delivery_note_no = CASE WHEN %s THEN %s ELSE delivery_note_no END,
       received_on = CASE WHEN %s THEN %s ELSE received_on END
 WHERE id = %s AND row_version = %s
"""
_PURCHASE_LOCK = "SELECT row_version, status FROM inv_purchases WHERE id = %s FOR UPDATE"
_INSERT_LINE = """
INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, discount_halalas,
                                vat_category, received_quantity_milli)
VALUES (%s, ew_current_user(), %s, %s, %s, %s, %s, %s) RETURNING line_no
"""
_UPDATE_LINE = """
UPDATE inv_purchase_lines
   SET item_id = coalesce(%s, item_id), quantity_milli = coalesce(%s, quantity_milli),
       unit_price_halalas = coalesce(%s, unit_price_halalas), discount_halalas = coalesce(%s, discount_halalas),
       vat_category = coalesce(%s, vat_category),
       received_quantity_milli = CASE WHEN %s THEN %s ELSE received_quantity_milli END
 WHERE purchase_id = %s AND line_no = %s
"""
_LINE_VAT_DEFAULT = "SELECT vat_category FROM inv_items WHERE id = %s"
_REMOVE_LINE = "SELECT ew_inv_remove_purchase_line(%s, %s, %s)"
_DISCARD = "SELECT ew_inv_discard_draft(%s, %s, %s)"
_PURCHASE_FLAGS = "SELECT code, line_no, detail FROM ew_inv_purchase_flags(%s)"
_RETURN_FLAGS = "SELECT code, line_no, detail FROM ew_inv_return_flags(%s)"
_FLAG_KEYS = "SELECT ew_inv_flag_keys(%s, %s) AS keys"
_ACKNOWLEDGED = """
SELECT f.code, f.line_no, f.detail FROM inv_review_flags f
 WHERE (f.purchase_id = %s OR f.return_id = %s) AND f.acknowledged_at IS NOT NULL ORDER BY f.code, f.line_no
"""
_PURCHASE_DIGEST = "SELECT ew_inv_purchase_digest(%s) AS digest"
_RETURN_DIGEST = "SELECT ew_inv_return_digest(%s) AS digest"
_POST_PURCHASE = "SELECT ew_inv_post_purchase(%s, %s, %s) AS number"
_REVERSE = "SELECT ew_inv_reverse_purchase(%s, %s, %s, %s) AS number"
_ITEM_HISTORY = """
SELECT h.item_id, count(*) AS n,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY h.unit_net) AS median_price,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY h.quantity_milli) AS median_quantity
  FROM (SELECT pl.item_id, pl.net_halalas * 1000.0 / pl.quantity_milli AS unit_net, pl.quantity_milli,
               row_number() OVER (PARTITION BY pl.item_id ORDER BY pp.posted_at DESC, pp.number DESC) AS k
          FROM inv_purchase_lines pl JOIN inv_purchases pp ON pp.id = pl.purchase_id
         WHERE pp.status = 'POSTED' AND pp.id <> %s AND pl.item_id = ANY (%s)) h
 WHERE h.k <= 10
 GROUP BY h.item_id
"""

# ── العبارات: المرتجع ──────────────────────────────────────────────────
_RETURN = """
SELECT r.id, r.status, r.row_version, r.purchase_id, r.return_date, r.reason, r.note, r.rep_id, r.number, r.posted_at,
       r.rep_name, r.rep_mobile, r.net_halalas, r.vat_halalas, r.total_halalas, r.credit_note_no, r.credit_note_date,
       r.created_at, r.updated_at, p.number AS purchase_number, p.status AS purchase_status, p.invoice_date,
       p.supplier_invoice_no, p.supplier_name, p.supplier_id, p.total_halalas AS purchase_total,
       x.name AS current_rep_name, x.mobile AS current_rep_mobile
  FROM inv_returns r
  JOIN inv_purchases p ON p.id = r.purchase_id
  LEFT JOIN inv_supplier_reps x ON x.id = r.rep_id
 WHERE r.id = %s
"""
_RETURN_LINES = """
SELECT l.line_no, l.quantity_milli AS bought_milli, l.unit_price_halalas, l.net_halalas AS line_net,
       (l.quantity_milli - coalesce((SELECT sum(y.quantity_milli) FROM inv_return_lines y JOIN inv_returns yr ON yr.id = y.return_id
                                      WHERE y.purchase_id = l.purchase_id AND y.line_no = l.line_no AND yr.status = 'POSTED'
                                        AND yr.id <> %s), 0))::bigint AS remaining_milli,
       x.quantity_milli, x.net_halalas, x.vat_halalas,
       
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile

  FROM inv_purchase_lines l
  JOIN inv_items i ON i.id = l.item_id
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
  LEFT JOIN inv_return_lines x ON x.return_id = %s AND x.line_no = l.line_no
 WHERE l.purchase_id = %s
 ORDER BY l.line_no
"""
_RETURNS = """
SELECT r.id, r.status, r.row_version, r.number, r.return_date, r.reason, r.total_halalas, r.credit_note_no,
       r.updated_at, p.number AS purchase_number, p.supplier_name, s.name AS current_supplier_name,
       count(*) OVER () AS total
  FROM inv_returns r JOIN inv_purchases p ON p.id = r.purchase_id LEFT JOIN inv_suppliers s ON s.id = p.supplier_id
 WHERE (%s::text IS NULL OR r.status = %s)
   AND (NOT %s OR (r.status = 'POSTED' AND r.credit_note_no IS NULL))
 ORDER BY r.updated_at DESC, r.id
 LIMIT %s OFFSET %s
"""
_INSERT_RETURN = "INSERT INTO inv_returns (user_id, purchase_id, rep_id) VALUES (ew_current_user(), %s, %s) RETURNING id"
_UPDATE_RETURN = """
UPDATE inv_returns
   SET return_date = coalesce(%s, return_date), reason = CASE WHEN %s THEN %s ELSE reason END,
       note = CASE WHEN %s THEN %s ELSE note END, rep_id = CASE WHEN %s THEN %s ELSE rep_id END
 WHERE id = %s AND row_version = %s
"""
_RETURN_LOCK = "SELECT row_version, status FROM inv_returns WHERE id = %s FOR UPDATE"
_UPSERT_RETURN_LINE = """
INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), %s, %s)
ON CONFLICT (return_id, line_no) DO UPDATE SET quantity_milli = EXCLUDED.quantity_milli
"""
_REMOVE_RETURN_LINE = "SELECT ew_inv_remove_return_line(%s, %s, %s)"
_RETURN_LINE_EXISTS = "SELECT 1 FROM inv_return_lines WHERE return_id = %s AND line_no = %s"
_POST_RETURN = "SELECT ew_inv_post_return(%s, %s, %s) AS number"
_CREDIT_NOTE = "UPDATE inv_returns SET credit_note_no = %s, credit_note_date = %s WHERE id = %s AND row_version = %s"

# ── العبارات: السندات ──────────────────────────────────────────────────
_VOUCHER = "SELECT voucher_id, voucher_number, replayed FROM ew_inv_stock_voucher(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
_VOUCHERS = """
SELECT v.id AS voucher_id, v.number AS voucher_number, v.kind AS voucher_kind, v.quantity_milli, v.on_hand_before_milli,
       v.unit_cost_halalas, v.reason AS voucher_reason, v.note AS voucher_note, v.occurred_on, v.created_at,
       cs.number AS count_number, 
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile
, count(*) OVER () AS total
  FROM inv_vouchers v
  JOIN inv_items i ON i.id = v.item_id
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
  LEFT JOIN inv_count_sessions cs ON cs.id = v.session_id
 WHERE %s::uuid IS NULL OR v.id = %s
 ORDER BY v.created_at DESC
 LIMIT %s OFFSET %s
"""


# ── فاتورة الشراء ──────────────────────────────────────────────────────
def _flag_views(rows: Iterable[Mapping], lines_by_no: Mapping[int, Mapping], display_name: str | None) -> list[dict]:
    """تنبيهات القواعد بنصوصها، الأعلى أوّلاً ثم بترتيب الرمز والسطر."""
    views = []
    for row in rows:
        line = lines_by_no.get(row["line_no"]) if row["line_no"] is not None else None
        views.append({
            "key": flag_key(row["code"], row["line_no"]), "source": "RULE", "code": row["code"],
            "line_no": row["line_no"], "level": LEVELS.get(row["code"], "normal"),
            "text": render(row["code"], row["line_no"], row["detail"], display_name, line=line),
        })
    views.sort(key=lambda flag: (flag["level"] != "high", flag["code"], flag["line_no"] or 0))
    return views


def _purchase_view(cursor, purchase_id: UUID) -> dict:
    p = _one(cursor, _PURCHASE, (purchase_id,))
    rows = _rows(cursor, _PURCHASE_LINES, (purchase_id,))
    calc = {row["line_no"]: row for row in _rows(cursor, _PURCHASE_CALC, (purchase_id,))} if rows else {}
    remaining = {row["line_no"]: row["remaining_milli"] for row in _rows(cursor, _PURCHASE_RETURNED, (purchase_id,))}
    lines = []
    totals = {"net": 0, "vat": 0, "gross": 0}
    for row in rows:
        figures = calc.get(row["line_no"], {})
        net = row["posted_net"] if row["posted_net"] is not None else figures.get("net_halalas", 0)
        vat = row["posted_vat"] if row["posted_vat"] is not None else figures.get("vat_halalas", 0)
        amount = row["posted_amount"] if row["posted_amount"] is not None else figures.get("amount_halalas", 0)
        totals["net"] += net
        totals["vat"] += vat
        option = _item_option(row, prices_include_vat=p["prices_include_vat"])
        if row["posted_item_name"] is not None:
            option["name"] = row["posted_item_name"]
            option["unit"] = row["posted_unit"]
            option["unit_name"] = UNIT_NAMES[row["posted_unit"]]
        lines.append({
            "line_no": row["line_no"], "item": option, "quantity_milli": row["quantity_milli"],
            "received_quantity_milli": row["received_quantity_milli"], "unit_price_halalas": row["unit_price_halalas"],
            "discount_halalas": row["discount_halalas"], "vat_category": row["line_vat_category"],
            "amount_halalas": amount, "net_halalas": net, "vat_halalas": vat,
            "remaining_milli": remaining.get(row["line_no"], row["quantity_milli"]),
        })
    totals["gross"] = totals["net"] + totals["vat"]
    missing = []
    if p["status"] == "DRAFT":
        if p["supplier_id"] is None:
            missing.append("supplier")
        if p["supplier_invoice_no"] is None:
            missing.append("supplier_invoice_no")
        if p["invoice_date"] is None:
            missing.append("invoice_date")
        if p["printed_total_halalas"] is None:
            missing.append("printed_total")
        if not lines:
            missing.append("lines")
    returns = _rows(cursor, _PURCHASE_RETURNS, (purchase_id,))
    supplier = None
    if p["supplier_id"] is not None:
        supplier = {"id": str(p["supplier_id"]), "name": p["supplier_name"] or p["current_supplier_name"],
                    "vat_number": p["supplier_vat_number"] if p["status"] != "DRAFT" else p["current_supplier_vat"],
                    "is_active": p["supplier_active"]}
    rep = None
    if p["rep_id"] is not None:
        rep = {"id": str(p["rep_id"]), "name": p["rep_name"] or p["current_rep_name"],
               "mobile": p["rep_mobile"] if p["status"] != "DRAFT" else p["current_rep_mobile"]}
    acknowledged = _rows(cursor, _ACKNOWLEDGED, (purchase_id, None)) if p["status"] != "DRAFT" else []
    return {
        "id": str(p["id"]), "status": p["status"], "row_version": p["row_version"], "number": p["number"],
        "label": None if p["number"] is None else document_label("PURCHASE", p["number"]),
        "supplier": supplier, "rep": rep, "supplier_invoice_no": p["supplier_invoice_no"],
        "invoice_date": _iso(p["invoice_date"]), "received_on": _iso(p["received_on"]),
        "delivery_note_no": p["delivery_note_no"], "prices_include_vat": p["prices_include_vat"],
        "printed_total_halalas": p["printed_total_halalas"], "printed_vat_halalas": p["printed_vat_halalas"],
        "note": p["note"], "lines": lines, "totals": totals, "missing": missing, "posted_at": _iso(p["posted_at"]),
        "acknowledged": _flag_views(acknowledged, {line["line_no"]: line for line in lines}, _display_name(cursor)),
        "returns": [{"id": str(r["id"]), "number": r["number"], "status": r["status"],
                     "label": None if r["number"] is None else document_label("RETURN", r["number"])} for r in returns],
        "returnable": p["status"] == "POSTED" and any(line["remaining_milli"] > 0 for line in lines),
        "reversal": None if p["reversal_number"] is None else {
            "number": p["reversal_number"], "label": document_label("REVERSAL", p["reversal_number"]),
            "at": _iso(p["reversed_at"]), "reason": p["reversal_reason"], "note": p["reversal_note"]},
        "updated_at": _iso(p["updated_at"]),
    }


def list_purchases(db: Database, user_id: UUID, status: str | None, q: str | None, page: int, size: int) -> dict:
    pager = _Pager(page, size)
    if status is not None and status.upper() not in ("DRAFT", "POSTED", "REVERSED"):
        raise Invalid("STATUS", field="status")
    state = None if status is None else status.upper()
    query = _text(q) or None
    digits = _digits(query)
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _PURCHASES, (state, state, query, digits, query, query, pager.size, pager.offset))
    return pager.wrap(rows, [{
        "id": str(row["id"]), "status": row["status"], "row_version": row["row_version"], "number": row["number"],
        "label": None if row["number"] is None else document_label("PURCHASE", row["number"]),
        "supplier_name": row["supplier_name"], "supplier_invoice_no": row["supplier_invoice_no"],
        "invoice_date": _iso(row["invoice_date"]), "total_halalas": row["total_halalas"], "lines": row["lines"],
        "updated_at": _iso(row["updated_at"]), "posted_at": _iso(row["posted_at"]),
        "reversal_number": row["reversal_number"],
    } for row in rows])


def get_purchase(db: Database, user_id: UUID, purchase_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        return _purchase_view(cursor, purchase_id)


def create_purchase(db: Database, user_id: UUID, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_PURCHASE, (
            fields.get("supplier_id"), _digits(fields.get("supplier_invoice_no")),
            _date(fields.get("invoice_date"), "invoice_date"), fields.get("prices_include_vat", False),
            fields.get("printed_total_halalas"), fields.get("printed_vat_halalas"), _text(fields.get("note")),
            fields.get("rep_id"), _digits(fields.get("delivery_note_no")), _date(fields.get("received_on"), "received_on")))
        return _purchase_view(cursor, cursor.fetchone()["id"])


def _draft_lock(cursor, statement: str, document_id: UUID, expected_row_version: int) -> None:
    row = _one(cursor, statement, (document_id,))
    if row["status"] != "DRAFT":
        raise Conflict("INV_POSTED", "سُجّل هذا المستند، ولا يتغيّر بعد تسجيله.")
    if row["row_version"] != expected_row_version:
        raise Conflict("STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")


def patch_purchase(db: Database, user_id: UUID, purchase_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _draft_lock(cursor, _PURCHASE_LOCK, purchase_id, expected_row_version)
        cursor.execute(_UPDATE_PURCHASE, (
            "supplier_id" in fields, fields.get("supplier_id"),
            "supplier_invoice_no" in fields, _digits(fields.get("supplier_invoice_no")),
            "invoice_date" in fields, _date(fields.get("invoice_date"), "invoice_date"),
            fields.get("prices_include_vat"),
            "printed_total_halalas" in fields, fields.get("printed_total_halalas"),
            "printed_vat_halalas" in fields, fields.get("printed_vat_halalas"),
            "note" in fields, _text(fields.get("note")),
            "rep_id" in fields, fields.get("rep_id"),
            "delivery_note_no" in fields, _digits(fields.get("delivery_note_no")),
            "received_on" in fields, _date(fields.get("received_on"), "received_on"),
            purchase_id, expected_row_version))
        return _purchase_view(cursor, purchase_id)


def add_line(db: Database, user_id: UUID, purchase_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _draft_lock(cursor, _PURCHASE_LOCK, purchase_id, expected_row_version)
        category = fields.get("vat_category")
        if category is None:
            cursor.execute(_LINE_VAT_DEFAULT, (fields["item_id"],))
            row = cursor.fetchone()
            if row is None:
                raise NotFound("NOT_FOUND", "لم يُعثر على الصنف.")
            category = row["vat_category"]
        cursor.execute(_INSERT_LINE, (purchase_id, fields["item_id"], fields["quantity_milli"], fields["unit_price_halalas"],
                                      fields.get("discount_halalas", 0), category, fields.get("received_quantity_milli")))
        return _purchase_view(cursor, purchase_id)


def patch_line(db: Database, user_id: UUID, purchase_id: UUID, line_no: int, expected_row_version: int,
               fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _draft_lock(cursor, _PURCHASE_LOCK, purchase_id, expected_row_version)
        cursor.execute(_UPDATE_LINE, (fields.get("item_id"), fields.get("quantity_milli"), fields.get("unit_price_halalas"),
                                      fields.get("discount_halalas"), fields.get("vat_category"),
                                      "received_quantity_milli" in fields, fields.get("received_quantity_milli"),
                                      purchase_id, line_no))
        if cursor.rowcount == 0:
            raise NotFound("NOT_FOUND", "لم يُعثر على السطر.")
        return _purchase_view(cursor, purchase_id)


def remove_line(db: Database, user_id: UUID, purchase_id: UUID, line_no: int, expected_row_version: int) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_REMOVE_LINE, (purchase_id, line_no, expected_row_version))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        return _purchase_view(cursor, purchase_id)


def discard_purchase(db: Database, user_id: UUID, purchase_id: UUID, expected_row_version: int) -> None:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_DISCARD, (purchase_id, None, expected_row_version))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error


def _rule_flags(cursor, statement: str, document_id: UUID, lines: list[dict]) -> list[dict]:
    rows = _rows(cursor, statement, (document_id,))
    return _flag_views(rows, {line["line_no"]: line for line in lines}, _display_name(cursor))


def purchase_flags(db: Database, user_id: UUID, purchase_id: UUID) -> dict:
    """تنبيهات القواعد الآن وملاحظات سيمبول المحفوظة على المحتوى الحالي، بلا استدعاء."""
    with db.session(user_id) as cursor:
        view = _purchase_view(cursor, purchase_id)
        if view["status"] != "DRAFT":
            return {"row_version": view["row_version"], "flags": view["acknowledged"], "ai": [], "digest": None}
        flags = _rule_flags(cursor, _PURCHASE_FLAGS, purchase_id, view["lines"])
        cursor.execute(_PURCHASE_DIGEST, (purchase_id,))
        digest = bytes(cursor.fetchone()["digest"])
    ai_flags = reviewer.flags_for(db, user_id, "PURCHASE", purchase_id, digest)
    return {"row_version": view["row_version"], "flags": flags, "ai": ai_flags, "digest": digest.hex()}


def _post(db: Database, user_id: UUID, statement: str, kind: str, document_id: UUID, expected_row_version: int,
          acknowledged: list[str], flags_statement: str, digest_statement: str, view: Callable) -> dict:
    """تسجيلٌ بإقرارٍ بكل تنبيهٍ قائم (`inv_flags_unacknowledged` ⇒ 409 بالتنبيهات) وبوّابة سيمبول."""
    try:
        with db.session(user_id) as cursor:
            cursor.execute(statement, (document_id, expected_row_version, acknowledged))
            return view(cursor, document_id)
    except pg_errors.NoDataFound as error:
        raise NotFound("NOT_FOUND", NOT_FOUND) from error
    except pg_errors.CheckViolation as error:
        constraint = getattr(error.diag, "constraint_name", None)
        if constraint == "inv_flags_unacknowledged":
            with db.session(user_id) as cursor:
                current = view(cursor, document_id)
                flags = _rule_flags(cursor, flags_statement, document_id, current["lines"])
            raise Conflict("FLAGS_CHANGED", "تغيّرت التنبيهات منذ عرضها. راجعها ثم سجّل.",
                           {"flags": flags, "row_version": current["row_version"]}) from error
        if constraint == "ai_flags_undecided":
            with db.session(user_id) as cursor:
                cursor.execute(digest_statement, (document_id,))
                digest = bytes(cursor.fetchone()["digest"])
            raise reviewer.flags_undecided(db, user_id, kind, document_id, digest) from error
        raise


def post_purchase(db: Database, user_id: UUID, purchase_id: UUID, expected_row_version: int,
                  acknowledged: list[str]) -> dict:
    return _post(db, user_id, _POST_PURCHASE, "PURCHASE", purchase_id, expected_row_version, acknowledged,
                 _PURCHASE_FLAGS, _PURCHASE_DIGEST, _purchase_view)


def reverse_purchase(db: Database, user_id: UUID, purchase_id: UUID, expected_row_version: int, reason: str,
                     note: str | None) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_REVERSE, (purchase_id, expected_row_version, reason, _text(note)))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        return _purchase_view(cursor, purchase_id)


# ── المرتجع ────────────────────────────────────────────────────────────
def _return_view(cursor, return_id: UUID) -> dict:
    r = _one(cursor, _RETURN, (return_id,))
    rows = _rows(cursor, _RETURN_LINES, (return_id, return_id, r["purchase_id"]))
    lines = []
    totals = {"net": 0, "vat": 0, "gross": 0}
    for row in rows:
        lines.append({
            "line_no": row["line_no"], "item": _item_option(row), "bought_milli": row["bought_milli"],
            "remaining_milli": row["remaining_milli"], "quantity_milli": row["quantity_milli"] or 0,
            "unit_price_halalas": row["unit_price_halalas"], "net_halalas": row["net_halalas"], "vat_halalas": row["vat_halalas"],
        })
        totals["net"] += row["net_halalas"] or 0
        totals["vat"] += row["vat_halalas"] or 0
    totals["gross"] = totals["net"] + totals["vat"]
    due = credit_note_due(r["return_date"]) if r["return_date"] is not None else None
    rep = None
    if r["rep_id"] is not None:
        rep = {"id": str(r["rep_id"]), "name": r["rep_name"] or r["current_rep_name"],
               "mobile": r["rep_mobile"] if r["status"] != "DRAFT" else r["current_rep_mobile"]}
    acknowledged = _rows(cursor, _ACKNOWLEDGED, (None, return_id)) if r["status"] != "DRAFT" else []
    return {
        "id": str(r["id"]), "status": r["status"], "row_version": r["row_version"], "number": r["number"],
        "label": None if r["number"] is None else document_label("RETURN", r["number"]),
        "purchase": {"id": str(r["purchase_id"]), "number": r["purchase_number"], "status": r["purchase_status"],
                     "label": document_label("PURCHASE", r["purchase_number"]), "invoice_date": _iso(r["invoice_date"]),
                     "supplier_invoice_no": r["supplier_invoice_no"], "supplier_name": r["supplier_name"],
                     "supplier_id": str(r["supplier_id"]), "total_halalas": r["purchase_total"]},
        "rep": rep, "return_date": _iso(r["return_date"]), "reason": r["reason"], "note": r["note"], "lines": lines,
        "totals": totals if r["status"] == "POSTED" else None, "posted_at": _iso(r["posted_at"]),
        "credit_note": None if r["credit_note_no"] is None else {"number": r["credit_note_no"], "date": _iso(r["credit_note_date"])},
        "credit_note_due": _iso(due),
        "acknowledged": _flag_views(acknowledged, {line["line_no"]: line for line in lines}, _display_name(cursor)),
        "updated_at": _iso(r["updated_at"]),
    }


def list_returns(db: Database, user_id: UUID, status: str | None, awaiting_credit_note: bool, page: int, size: int) -> dict:
    pager = _Pager(page, size)
    if status is not None and status.upper() not in ("DRAFT", "POSTED"):
        raise Invalid("STATUS", field="status")
    state = None if status is None else status.upper()
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _RETURNS, (state, state, awaiting_credit_note, pager.size, pager.offset))
        today = _today(cursor)
    items = []
    for row in rows:
        due = credit_note_due(row["return_date"]) if row["return_date"] else None
        items.append({
            "id": str(row["id"]), "status": row["status"], "row_version": row["row_version"], "number": row["number"],
            "label": None if row["number"] is None else document_label("RETURN", row["number"]),
            "purchase_label": document_label("PURCHASE", row["purchase_number"]),
            "supplier_name": row["supplier_name"] or row["current_supplier_name"], "return_date": _iso(row["return_date"]),
            "reason": row["reason"], "total_halalas": row["total_halalas"], "credit_note_no": row["credit_note_no"],
            "credit_note_due": _iso(due),
            "credit_note_overdue": row["status"] == "POSTED" and row["credit_note_no"] is None and due is not None and today > due,
            "updated_at": _iso(row["updated_at"]),
        })
    return pager.wrap(rows, items)


def get_return(db: Database, user_id: UUID, return_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        return _return_view(cursor, return_id)


def create_return(db: Database, user_id: UUID, purchase_id: UUID, rep_id: UUID | None) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_RETURN, (purchase_id, rep_id))
        return _return_view(cursor, cursor.fetchone()["id"])


def patch_return(db: Database, user_id: UUID, return_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        _draft_lock(cursor, _RETURN_LOCK, return_id, expected_row_version)
        cursor.execute(_UPDATE_RETURN, (_date(fields.get("return_date"), "return_date"),
                                        "reason" in fields, fields.get("reason"), "note" in fields, _text(fields.get("note")),
                                        "rep_id" in fields, fields.get("rep_id"), return_id, expected_row_version))
        return _return_view(cursor, return_id)


def put_return_line(db: Database, user_id: UUID, return_id: UUID, line_no: int, expected_row_version: int,
                    quantity_milli: int) -> dict:
    """يضيف السطر أو يعدّله، والصفر يزيله (عبر دالّة الحذف)."""
    with db.session(user_id) as cursor:
        if quantity_milli == 0:
            cursor.execute(_RETURN_LINE_EXISTS, (return_id, line_no))
            if cursor.fetchone() is not None:
                try:
                    cursor.execute(_REMOVE_RETURN_LINE, (return_id, line_no, expected_row_version))
                except pg_errors.NoDataFound as error:
                    raise NotFound("NOT_FOUND", NOT_FOUND) from error
            else:
                _draft_lock(cursor, _RETURN_LOCK, return_id, expected_row_version)
        else:
            _draft_lock(cursor, _RETURN_LOCK, return_id, expected_row_version)
            cursor.execute(_UPSERT_RETURN_LINE, (return_id, line_no, quantity_milli))
        return _return_view(cursor, return_id)


def return_flags(db: Database, user_id: UUID, return_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        view = _return_view(cursor, return_id)
        if view["status"] != "DRAFT":
            return {"row_version": view["row_version"], "flags": view["acknowledged"], "ai": [], "digest": None}
        flags = _rule_flags(cursor, _RETURN_FLAGS, return_id, view["lines"])
        cursor.execute(_RETURN_DIGEST, (return_id,))
        digest = bytes(cursor.fetchone()["digest"])
    ai_flags = reviewer.flags_for(db, user_id, "RETURN", return_id, digest)
    return {"row_version": view["row_version"], "flags": flags, "ai": ai_flags, "digest": digest.hex()}


def post_return(db: Database, user_id: UUID, return_id: UUID, expected_row_version: int, acknowledged: list[str]) -> dict:
    return _post(db, user_id, _POST_RETURN, "RETURN", return_id, expected_row_version, acknowledged,
                 _RETURN_FLAGS, _RETURN_DIGEST, _return_view)


def put_credit_note(db: Database, user_id: UUID, return_id: UUID, expected_row_version: int, number: str, date: str) -> dict:
    with db.session(user_id) as cursor:
        _lock_version(cursor, "SELECT row_version FROM inv_returns WHERE id = %s FOR UPDATE", (return_id,), expected_row_version)
        cursor.execute(_CREDIT_NOTE, (_digits(number), _date(date, "date"), return_id, expected_row_version))
        return _return_view(cursor, return_id)


def discard_return(db: Database, user_id: UUID, return_id: UUID, expected_row_version: int) -> None:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_DISCARD, (None, return_id, expected_row_version))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error


# ── السندات ────────────────────────────────────────────────────────────
def _voucher_view(row: Mapping, *, replayed: bool = False) -> dict:
    return {
        "id": str(row["voucher_id"]), "number": row["voucher_number"], "label": document_label("VOUCHER", row["voucher_number"]),
        "kind": row["voucher_kind"], "item": _item_option(row), "quantity_milli": row["quantity_milli"],
        "on_hand_before_milli": row["on_hand_before_milli"], "unit_cost_halalas": row["unit_cost_halalas"],
        "reason": row["voucher_reason"], "note": row["voucher_note"], "occurred_on": _iso(row["occurred_on"]),
        "count_label": None if row["count_number"] is None else count_label(row["count_number"]),
        "created_at": _iso(row["created_at"]), "replayed": replayed,
    }


def stock_voucher(db: Database, user_id: UUID, kind: str, fields: Mapping) -> dict:
    """سندٌ بضغطةٍ واحدة: رصيدٌ افتتاحي أو صرفٌ أو جردٌ فردي؛ الضغطة المكرّرة تعيد السند نفسه."""
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_VOUCHER, (fields["client_token"], kind, fields["item_id"], fields.get("quantity_milli"),
                                      fields.get("unit_cost_halalas"), fields.get("reason"), _text(fields.get("note")),
                                      _date(fields["occurred_on"], "occurred_on"), fields.get("expected_on_hand_milli")))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", "لم يُعثر على الصنف.") from error
        result = cursor.fetchone()
        row = _one(cursor, _VOUCHERS, (result["voucher_id"], result["voucher_id"], 1, 0))
    return _voucher_view(row, replayed=result["replayed"])


def list_vouchers(db: Database, user_id: UUID, page: int, size: int) -> dict:
    pager = _Pager(page, size)
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _VOUCHERS, (None, None, pager.size, pager.offset))
    return pager.wrap(rows, [_voucher_view(row) for row in rows])


# ── العبارات: جلسة الجرد ───────────────────────────────────────────────
_COUNT = """
SELECT cs.id, cs.number, cs.status, cs.scope, cs.category_id, c.name AS category_name, cs.blind, cs.note, cs.snapshot_at,
       cs.last_purchase_number, cs.last_voucher_number, cs.items_total, cs.items_counted, cs.items_matched,
       cs.posted_at, cs.cancelled_at, cs.row_version, cs.created_at, cs.updated_at,
       (SELECT count(*) FROM inv_count_lines l WHERE l.session_id = cs.id AND l.counted_milli IS NOT NULL) AS counted_so_far,
       (SELECT count(*) FROM inv_count_lines l JOIN inv_items i ON i.id = l.item_id
         WHERE l.session_id = cs.id AND l.counted_milli IS NOT NULL AND i.on_hand_milli <> l.book_milli) AS changed_lines
  FROM inv_count_sessions cs LEFT JOIN inv_categories c ON c.id = cs.category_id
 WHERE cs.id = %s
"""
_COUNTS = """
SELECT cs.id, cs.number, cs.status, cs.scope, cs.blind, cs.items_total, cs.items_counted, cs.items_matched,
       cs.snapshot_at, cs.posted_at, cs.cancelled_at, cs.row_version,
       (SELECT count(*) FROM inv_count_lines l WHERE l.session_id = cs.id AND l.counted_milli IS NOT NULL) AS counted_so_far,
       count(*) OVER () AS total
  FROM inv_count_sessions cs
 ORDER BY cs.created_at DESC
 LIMIT %s OFFSET %s
"""
_COUNT_LINES = """
SELECT l.line_no, l.book_milli, l.counted_milli, l.unit_cost_halalas, l.reason AS line_reason, l.note AS line_note,
       l.added_during_count, l.counted_at, l.voucher_id, i.on_hand_milli <> l.book_milli AS changed, 
i.id, i.number, i.name, i.supplier_code, i.barcode, i.kind, i.unit, i.vat_category, i.vat_exemption_reason,
i.price_halalas, i.selling_price_halalas, i.selling_price_includes_vat, i.reorder_level_milli, i.target_level_milli,
i.note, i.on_hand_milli, i.stock_value_halalas, i.last_movement_at, i.last_counted_on, i.is_active, i.row_version,
i.category_id, c.name AS category_name, i.preferred_supplier_id, ps.name AS preferred_supplier_name,
(SELECT l.net_halalas * 1000 / l.quantity_milli FROM inv_purchase_lines l JOIN inv_purchases p ON p.id = l.purchase_id
  WHERE l.item_id = i.id AND p.status = 'POSTED' ORDER BY p.posted_at DESC, l.line_no DESC LIMIT 1) AS last_price_halalas,
(SELECT r.name FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_name,
(SELECT r.mobile FROM inv_supplier_reps r WHERE r.supplier_id = i.preferred_supplier_id AND r.is_default AND r.is_active LIMIT 1) AS preferred_rep_mobile

  FROM inv_count_lines l
  JOIN inv_items i ON i.id = l.item_id
  LEFT JOIN inv_categories c ON c.id = i.category_id
  LEFT JOIN inv_suppliers ps ON ps.id = i.preferred_supplier_id
 WHERE l.session_id = %s
 ORDER BY l.line_no
"""
_OPEN_COUNT = "SELECT session_id, session_number, replayed FROM ew_inv_count_open(%s, %s, %s, %s, %s, %s)"
_COUNT_LOCK = "SELECT row_version, status FROM inv_count_sessions WHERE id = %s FOR UPDATE"
_UPDATE_COUNT = "UPDATE inv_count_sessions SET blind = coalesce(%s, blind), note = CASE WHEN %s THEN %s ELSE note END WHERE id = %s AND row_version = %s"
_UPDATE_COUNT_LINE = """
UPDATE inv_count_lines
   SET counted_milli = %s, unit_cost_halalas = %s, reason = %s, note = CASE WHEN %s THEN %s ELSE note END
 WHERE session_id = %s AND item_id = %s
"""
_ADD_COUNT_ITEM = "SELECT ew_inv_count_add_item(%s, %s) AS line_no"
_REFRESH_COUNT = "SELECT ew_inv_count_refresh(%s) AS refreshed"
_POST_COUNT = "SELECT session_number, items_counted, items_matched FROM ew_inv_count_post(%s, %s, %s)"
_CANCEL_COUNT = "SELECT ew_inv_count_cancel(%s, %s)"

# ── العبارات: المصروفات والملخّص ───────────────────────────────────────
_LEDGER_TOTALS = """
SELECT kind, coalesce(sum(net_halalas), 0)::bigint AS net, coalesce(sum(vat_halalas), 0)::bigint AS vat,
       coalesce(sum(gross_halalas), 0)::bigint AS gross
  FROM inv_ledger WHERE entry_date BETWEEN %s AND %s GROUP BY kind
"""
_LEDGER_ENTRIES = """
SELECT e.kind, e.entry_date, e.net_halalas, e.vat_halalas, e.gross_halalas, e.purchase_id, e.return_id,
       p.number AS purchase_number, p.reversal_number, p.supplier_name, p.supplier_invoice_no, r.number AS return_number,
       count(*) OVER () AS total
  FROM inv_ledger e JOIN inv_purchases p ON p.id = e.purchase_id LEFT JOIN inv_returns r ON r.id = e.return_id
 WHERE e.entry_date BETWEEN %s AND %s
 ORDER BY e.entry_date DESC, e.seq DESC
 LIMIT %s OFFSET %s
"""
_LEDGER_MONTHS = """
SELECT extract(month FROM entry_date)::int AS month, kind, coalesce(sum(net_halalas), 0)::bigint AS net,
       coalesce(sum(vat_halalas), 0)::bigint AS vat, coalesce(sum(gross_halalas), 0)::bigint AS gross
  FROM inv_ledger WHERE extract(year FROM entry_date) = %s GROUP BY 1, 2
"""
_ATTENTION = """
SELECT (SELECT count(*) FROM inv_purchases WHERE status = 'DRAFT') + (SELECT count(*) FROM inv_returns WHERE status = 'DRAFT') AS drafts,
       (SELECT count(*) FROM inv_items WHERE is_active AND reorder_level_milli IS NOT NULL AND on_hand_milli <= reorder_level_milli) AS low_stock,
       (SELECT count(*) FROM inv_returns WHERE status = 'POSTED' AND credit_note_no IS NULL) AS awaiting_credit_note,
       (SELECT count(*) FROM inv_returns r WHERE r.status = 'POSTED' AND r.credit_note_no IS NULL
          AND ew_riyadh_today() > (date_trunc('month', r.return_date) + interval '1 month 14 days')::date) AS credit_note_overdue,
       (SELECT count(*) FROM inv_items WHERE is_active AND kind = 'STOCK'
          AND (last_counted_on IS NULL OR last_counted_on < ew_riyadh_today() - 90)) AS uncounted,
       (SELECT cs.id FROM inv_count_sessions cs WHERE cs.status = 'OPEN') AS open_count_id,
       (SELECT cs.number FROM inv_count_sessions cs WHERE cs.status = 'OPEN') AS open_count_number,
       (SELECT count(*) FROM inv_items WHERE is_active) AS items,
       (SELECT count(*) FROM inv_suppliers WHERE is_active) AS suppliers,
       (SELECT count(*) FROM inv_movements) AS movements
"""


# ── جلسة الجرد ─────────────────────────────────────────────────────────
def _count_line_view(row: Mapping, blind: bool, status: str) -> dict:
    counted = row["counted_milli"]
    reveal = status != "OPEN" or not blind or counted is not None
    difference = None if counted is None else counted - row["book_milli"]
    return {
        "line_no": row["line_no"], "item": _item_option(row),
        "book_milli": row["book_milli"] if reveal else None,
        "counted_milli": counted, "difference_milli": difference if reveal else None,
        "unit_cost_halalas": row["unit_cost_halalas"], "reason": row["line_reason"], "note": row["line_note"],
        "added_during_count": row["added_during_count"], "counted_at": _iso(row["counted_at"]),
        "changed": bool(row["changed"]) and counted is not None and status == "OPEN",
        "needs_cost": counted is not None and counted > 0 and row["on_hand_milli"] == 0 and row["unit_cost_halalas"] is None,
        "posted": row["voucher_id"] is not None,
    }


def _count_view(cursor, session_id: UUID) -> dict:
    cs = _one(cursor, _COUNT, (session_id,))
    rows = _rows(cursor, _COUNT_LINES, (session_id,))
    lines = [_count_line_view(row, cs["blind"], cs["status"]) for row in rows]
    return {
        "id": str(cs["id"]), "number": cs["number"], "label": count_label(cs["number"]), "status": cs["status"],
        "scope": cs["scope"], "scope_name": COUNT_SCOPE_NAMES[cs["scope"]],
        "category": None if cs["category_id"] is None else {"id": str(cs["category_id"]), "name": cs["category_name"]},
        "blind": cs["blind"], "note": cs["note"], "snapshot_at": _iso(cs["snapshot_at"]),
        "last_purchase_label": None if cs["last_purchase_number"] is None else document_label("PURCHASE", cs["last_purchase_number"]),
        "last_voucher_label": None if cs["last_voucher_number"] is None else document_label("VOUCHER", cs["last_voucher_number"]),
        "items_total": cs["items_total"], "counted_so_far": cs["counted_so_far"], "changed_lines": cs["changed_lines"],
        "items_counted": cs["items_counted"], "items_matched": cs["items_matched"],
        "posted_at": _iso(cs["posted_at"]), "cancelled_at": _iso(cs["cancelled_at"]), "row_version": cs["row_version"],
        "lines": lines, "updated_at": _iso(cs["updated_at"]),
    }


def list_counts(db: Database, user_id: UUID, page: int, size: int) -> dict:
    pager = _Pager(page, size)
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _COUNTS, (pager.size, pager.offset))
    return pager.wrap(rows, [{
        "id": str(row["id"]), "number": row["number"], "label": count_label(row["number"]), "status": row["status"],
        "scope": row["scope"], "scope_name": COUNT_SCOPE_NAMES[row["scope"]], "blind": row["blind"],
        "items_total": row["items_total"], "counted_so_far": row["counted_so_far"], "items_counted": row["items_counted"],
        "items_matched": row["items_matched"], "snapshot_at": _iso(row["snapshot_at"]), "posted_at": _iso(row["posted_at"]),
        "cancelled_at": _iso(row["cancelled_at"]), "row_version": row["row_version"],
    } for row in rows])


def get_count(db: Database, user_id: UUID, session_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        return _count_view(cursor, session_id)


def open_count(db: Database, user_id: UUID, client_token: UUID, scope: str, category_id: UUID | None,
               item_ids: list[UUID] | None, blind: bool, note: str | None) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_OPEN_COUNT, (client_token, scope, category_id, item_ids or None, blind, _text(note)))
        result = cursor.fetchone()
        view = _count_view(cursor, result["session_id"])
    view["replayed"] = result["replayed"]
    return view


def patch_count(db: Database, user_id: UUID, session_id: UUID, expected_row_version: int, fields: Mapping) -> dict:
    with db.session(user_id) as cursor:
        row = _one(cursor, _COUNT_LOCK, (session_id,))
        if row["status"] != "OPEN":
            raise Conflict("INV_COUNT_CLOSED", "انتهت هذه الجلسة، ولا تتغيّر.")
        if row["row_version"] != expected_row_version:
            raise Conflict("STALE", "تغيّرت الجلسة منذ عرضها. راجعها مرة أخرى.")
        cursor.execute(_UPDATE_COUNT, (fields.get("blind"), "note" in fields, _text(fields.get("note")), session_id,
                                       expected_row_version))
        return _count_view(cursor, session_id)


def set_count_line(db: Database, user_id: UUID, session_id: UUID, item_id: UUID, expected_row_version: int,
                   counted_milli: int | None, unit_cost_halalas: int | None, reason: str | None, note: str | None,
                   note_given: bool) -> dict:
    """المعدود (فارغٌ: لم يُعدّ بعد) وسبب فرقه وتكلفة وحدته؛ الجلسة مفتوحة وبرقم صفّها."""
    with db.session(user_id) as cursor:
        row = _one(cursor, _COUNT_LOCK, (session_id,))
        if row["status"] != "OPEN":
            raise Conflict("INV_COUNT_CLOSED", "انتهت هذه الجلسة، ولا تتغيّر.")
        if row["row_version"] != expected_row_version:
            raise Conflict("STALE", "تغيّرت الجلسة منذ عرضها. راجعها مرة أخرى.")
        cursor.execute(_UPDATE_COUNT_LINE, (counted_milli, unit_cost_halalas, reason, note_given, _text(note), session_id, item_id))
        if cursor.rowcount == 0:
            raise NotFound("NOT_FOUND", "لم يُعثر على السطر.")
        return _count_view(cursor, session_id)


def add_count_item(db: Database, user_id: UUID, session_id: UUID, item_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_ADD_COUNT_ITEM, (session_id, item_id))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        return _count_view(cursor, session_id)


def refresh_count(db: Database, user_id: UUID, session_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_REFRESH_COUNT, (session_id,))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        refreshed = cursor.fetchone()["refreshed"]
        view = _count_view(cursor, session_id)
    view["refreshed"] = refreshed
    return view


def post_count(db: Database, user_id: UUID, session_id: UUID, expected_row_version: int, occurred_on: str) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_POST_COUNT, (session_id, expected_row_version, _date(occurred_on, "occurred_on")))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        return _count_view(cursor, session_id)


def cancel_count(db: Database, user_id: UUID, session_id: UUID, expected_row_version: int) -> dict:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_CANCEL_COUNT, (session_id, expected_row_version))
        except pg_errors.NoDataFound as error:
            raise NotFound("NOT_FOUND", NOT_FOUND) from error
        return _count_view(cursor, session_id)


# ── المصروفات والملخّص ─────────────────────────────────────────────────
def _totals(rows: Iterable[Mapping]) -> dict:
    by_kind = {row["kind"]: {"net": row["net"], "vat": row["vat"], "gross": row["gross"]} for row in rows}
    zero = {"net": 0, "vat": 0, "gross": 0}
    purchases = by_kind.get("PURCHASE", zero)
    returns = by_kind.get("RETURN", zero)
    reversals = by_kind.get("REVERSAL", zero)
    net = {key: purchases[key] + returns[key] + reversals[key] for key in zero}
    return {"purchases": purchases, "returns": {k: -v for k, v in returns.items()},
            "reversals": {k: -v for k, v in reversals.items()}, "net": net}


def expenses(db: Database, user_id: UUID, from_day: str, to_day: str, page: int, size: int) -> dict:
    start = _date(from_day, "from")
    end = _date(to_day, "to")
    if start > end or (end - start).days >= EXPENSES_MAX_DAYS:
        raise Invalid("INV_PERIOD", field="to")
    pager = _Pager(page, size)
    with db.session(user_id) as cursor:
        totals = _totals(_rows(cursor, _LEDGER_TOTALS, (start, end)))
        rows = _rows(cursor, _LEDGER_ENTRIES, (start, end, pager.size, pager.offset))
    entries = []
    for row in rows:
        if row["kind"] == "PURCHASE":
            document = document_label("PURCHASE", row["purchase_number"])
        elif row["kind"] == "RETURN":
            document = document_label("RETURN", row["return_number"])
        else:
            document = document_label("REVERSAL", row["reversal_number"])
        entries.append({"date": _iso(row["entry_date"]), "kind": row["kind"], "document": document,
                        "purchase_id": str(row["purchase_id"]), "return_id": None if row["return_id"] is None else str(row["return_id"]),
                        "supplier_name": row["supplier_name"], "supplier_invoice_no": row["supplier_invoice_no"],
                        "net": row["net_halalas"], "vat": row["vat_halalas"], "gross": row["gross_halalas"]})
    return {"from": start.isoformat(), "to": end.isoformat(), "totals": totals, "entries": pager.wrap(rows, entries)}


def expense_months(db: Database, user_id: UUID, year: int) -> dict:
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _LEDGER_MONTHS, (year,))
    months = []
    for month in range(1, 13):
        months.append({"month": month, **_totals([row for row in rows if row["month"] == month])})
    return {"year": year, "months": months}


def summary(db: Database, user_id: UUID) -> dict:
    """الرئيسية: اليوم وشهره، ومجاميع الشهر، وقيمة المخزون، وما يحتاج انتباهاً، والإعداد."""
    with db.session(user_id) as cursor:
        today = _today(cursor)
        first = today.replace(day=1)
        totals = _totals(_rows(cursor, _LEDGER_TOTALS, (first, today)))
        cursor.execute(_STOCK_VALUE)
        value = cursor.fetchone()["value"]
        cursor.execute(_ATTENTION)
        attention = dict(cursor.fetchone())
        cursor.execute(_SETTINGS)
        settings = cursor.fetchone()
    return {
        "today": today.isoformat(), "month": today.strftime("%Y-%m"), "month_totals": totals, "stock_value": value,
        "settings": None if settings is None else _settings_view(settings),
        "attention": {
            "drafts": attention["drafts"], "low_stock": attention["low_stock"],
            "awaiting_credit_note": attention["awaiting_credit_note"], "credit_note_overdue": attention["credit_note_overdue"],
            "uncounted": attention["uncounted"],
            "open_count": None if attention["open_count_id"] is None else {
                "id": str(attention["open_count_id"]), "label": count_label(attention["open_count_number"])},
        },
        "counts": {"items": attention["items"], "suppliers": attention["suppliers"], "movements": attention["movements"]},
    }


def vat_tool(amount_halalas: int, basis: str, category: str) -> dict:
    from eyework.inventory_rules import vat_split

    net, vat, gross = vat_split(amount_halalas, basis, category)
    return {"net_halalas": net, "vat_halalas": vat, "gross_halalas": gross}


# ── مراجعة سيمبول: الأداة في السجلّ ───────────────────────────────────
_REVIEW_PURCHASE_LINES = """
SELECT l.line_no, l.quantity_milli, l.vat_category, i.id AS item_id, i.name AS item_name, i.unit, i.kind, c.net_halalas
  FROM inv_purchase_lines l JOIN inv_items i ON i.id = l.item_id
  JOIN ew_inv_purchase_calc(%s) c ON c.line_no = l.line_no
 WHERE l.purchase_id = %s ORDER BY l.line_no
"""
_REVIEW_PURCHASE = "SELECT status, row_version FROM inv_purchases WHERE id = %s"
_REVIEW_RETURN = """
SELECT r.status, r.row_version, r.reason, r.return_date, p.invoice_date, r.purchase_id
  FROM inv_returns r JOIN inv_purchases p ON p.id = r.purchase_id WHERE r.id = %s
"""
_REVIEW_RETURN_LINES = """
SELECT x.line_no, x.quantity_milli, l.quantity_milli AS bought_milli, i.name AS item_name, i.unit, i.kind
  FROM inv_return_lines x JOIN inv_purchase_lines l ON l.purchase_id = x.purchase_id AND l.line_no = x.line_no
  JOIN inv_items i ON i.id = l.item_id
 WHERE x.return_id = %s ORDER BY x.line_no
"""


def _load_purchase(cursor, purchase_id: UUID, expected_row_version: int | None) -> Snapshot:
    head = _one(cursor, _REVIEW_PURCHASE, (purchase_id,))
    if head["status"] != "DRAFT":
        raise NotFound("NOT_FOUND", NOT_FOUND)
    if expected_row_version is not None and head["row_version"] != expected_row_version:
        raise Conflict("STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")
    rows = _rows(cursor, _REVIEW_PURCHASE_LINES, (purchase_id, purchase_id))
    if not rows:
        raise Invalid("INV_NO_LINES", field="lines")
    cursor.execute(_ITEM_HISTORY, (purchase_id, [row["item_id"] for row in rows]))
    history = {row["item_id"]: row for row in cursor.fetchall()}
    lines = []
    for row in rows:
        stats = history.get(row["item_id"])
        candidates = []
        if stats is None and row["kind"] == "STOCK":
            similar = _similar(cursor, row["item_name"], row["item_id"], ratio=CANDIDATE_RATIO, limit=CANDIDATES_MAX, stock_only=True)
            candidates = [(index, other["name"], other["unit"]) for index, other in enumerate(similar, 1)]
        lines.append({
            "line_no": row["line_no"], "item_name": row["item_name"], "unit": row["unit"], "kind": row["kind"],
            "quantity_milli": row["quantity_milli"],
            "unit_net_halalas": round(row["net_halalas"] * 1000 / row["quantity_milli"]) if row["quantity_milli"] else 0,
            "vat_category": row["vat_category"], "history_count": 0 if stats is None else stats["n"],
            "median_price_halalas": None if stats is None else round(stats["median_price"]),
            "median_quantity_milli": None if stats is None else round(stats["median_quantity"]),
            "candidates": candidates,
        })
    cursor.execute(_PURCHASE_DIGEST, (purchase_id,))
    return Snapshot(purchase_payload(lines), bytes(cursor.fetchone()["digest"]))


def _load_return(cursor, return_id: UUID, expected_row_version: int | None) -> Snapshot:
    head = _one(cursor, _REVIEW_RETURN, (return_id,))
    if head["status"] != "DRAFT":
        raise NotFound("NOT_FOUND", NOT_FOUND)
    if expected_row_version is not None and head["row_version"] != expected_row_version:
        raise Conflict("STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")
    if head["reason"] is None:
        raise Invalid("INV_RETURN_REASON", field="reason")
    rows = _rows(cursor, _REVIEW_RETURN_LINES, (return_id,))
    if not rows:
        raise Invalid("INV_NO_LINES", field="lines")
    days = (head["return_date"] - head["invoice_date"]).days
    lines = [{"line_no": row["line_no"], "item_name": row["item_name"], "unit": row["unit"], "kind": row["kind"],
              "quantity_milli": row["quantity_milli"], "bought_milli": row["bought_milli"], "days_since_purchase": days}
             for row in rows]
    cursor.execute(_RETURN_DIGEST, (return_id,))
    return Snapshot(return_payload(head["reason"], lines), bytes(cursor.fetchone()["digest"]))


def _load(cursor, user_id: UUID, kind: str, subject_id: UUID, expected_row_version: int | None) -> Snapshot:
    """محمّل الموضوع (المواصفة §7.3): الفحص الحتمي، ثم أقلّ ما يلزم، والبصمة من القاعدة."""
    if kind == "PURCHASE":
        return _load_purchase(cursor, subject_id, expected_row_version)
    if kind == "RETURN":
        return _load_return(cursor, subject_id, expected_row_version)
    raise NotFound("NOT_FOUND", NOT_FOUND)


def _fixture(cursor, user_id: UUID) -> UUID:
    """مسودةٌ نموذجية بدور المالك: صنفٌ جديد له مرشَّحٌ قريب الاسم، لاختبار ما يحمّله المحمّل."""
    cursor.execute("INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (%s, false) ON CONFLICT DO NOTHING", (user_id,))
    cursor.execute("INSERT INTO inv_suppliers (user_id, name) VALUES (%s, 'مورّد النموذج') RETURNING id", (user_id,))
    supplier = cursor.fetchone()[0]
    cursor.execute("INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (%s, 'كرتونة ماء ٣٣٠ مل', 'STOCK', 'CARTON', 1800)",
                   (user_id,))
    cursor.execute("INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (%s, 'مياه 330 كرتون', 'STOCK', 'CARTON', 1800)"
                   " RETURNING id", (user_id,))
    item = cursor.fetchone()[0]
    cursor.execute("INSERT INTO inv_purchases (user_id, supplier_id, supplier_invoice_no, invoice_date, printed_total_halalas)"
                   " VALUES (%s, %s, 'F-1', ew_riyadh_today(), 20700) RETURNING id", (user_id, supplier))
    purchase = cursor.fetchone()[0]
    cursor.execute("INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category)"
                   " VALUES (%s, %s, %s, 10000, 1800, 'S')", (purchase, user_id, item))
    return purchase


FEATURE = ReviewFeature(
    code="STOCK_REVIEW", kinds=frozenset({"PURCHASE", "RETURN"}), profession=Profession.STOREKEEPER, catalogue=CATALOGUE,
    begin_sql="SELECT request_id, content_digest AS digest FROM ew_inv_review_begin(%s, NULL)",
    record_sql="SELECT ew_inv_review_record(%s, %s, %s) AS outcome",
    digest_sql="SELECT ew_inv_purchase_digest(%s) AS digest",
    load=_load, payload_keys=PAYLOAD_KEYS, fixture=_fixture,
)
#: المرتجع يبدأ بدالّة البدء نفسها بمعاملها الثاني، وبصمته من دالّته: `reviewer` يختار بحسب النوع.
RETURN_FEATURE = dataclasses.replace(
    FEATURE,
    begin_sql="SELECT request_id, content_digest AS digest FROM ew_inv_review_begin(NULL, %s)",
    digest_sql="SELECT ew_inv_return_digest(%s) AS digest",
)
reviewer.FEATURES["STOCK_REVIEW"] = FEATURE
reviewer.KIND_FEATURES[("STOCK_REVIEW", "RETURN")] = RETURN_FEATURE


# ── شاشات «اسأل سيمبول» في بوابة المخزون ──────────────────────────────
_SCREEN_ITEM = """
SELECT i.name, i.unit, i.kind, i.vat_category, i.price_halalas, i.on_hand_milli, i.stock_value_halalas, i.reorder_level_milli,
       i.target_level_milli, i.last_counted_on, c.name AS category_name
  FROM inv_items i LEFT JOIN inv_categories c ON c.id = i.category_id WHERE i.id = %s
"""
_SCREEN_PURCHASE = """
SELECT p.status, p.number, p.invoice_date, p.prices_include_vat, p.printed_total_halalas,
       (SELECT count(*) FROM inv_purchase_lines l WHERE l.purchase_id = p.id) AS lines
  FROM inv_purchases p WHERE p.id = %s
"""
_SCREEN_COUNT = """
SELECT cs.status, cs.number, cs.scope, cs.blind, cs.items_total,
       (SELECT count(*) FROM inv_count_lines l WHERE l.session_id = cs.id AND l.counted_milli IS NOT NULL) AS counted
  FROM inv_count_sessions cs WHERE cs.id = %s
"""
_HOME_STATUS = {"DRAFT": "مسودة", "POSTED": "مسجّلة", "REVERSED": "معكوسة", "OPEN": "مفتوحة", "CANCELLED": "ملغاة"}


def _inventory_home(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_ATTENTION)
    a = cursor.fetchone()
    cursor.execute(_STOCK_VALUE)
    value = cursor.fetchone()["value"]
    lines = [f"الأصناف النشطة: {a['items']}، والموردون: {a['suppliers']}، وقيمة المخزون {halalas_words(value)}",
             f"مسوداتٌ لم تُسجَّل: {a['drafts']}، وأصنافٌ تحت حدّ الطلب: {a['low_stock']}، "
             f"ومرتجعاتٌ تنتظر إشعار المورّد الدائن: {a['awaiting_credit_note']} (متأخّر: {a['credit_note_overdue']})",
             f"أصنافٌ لم تُجرد منذ تسعين يوماً: {a['uncounted']}"]
    if a["open_count_number"] is not None:
        lines.append(f"جلسة جردٍ مفتوحة: {count_label(a['open_count_number'])}")
    return assistant.fit(lines)


def _screen_item(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_SCREEN_ITEM, (screen_id,))
    row = cursor.fetchone()
    if row is None:
        raise NotFound
    lines = [f"الصنف: {row['name']} ({UNIT_NAMES[row['unit']]}، {'يُخزَّن' if row['kind'] == 'STOCK' else 'خدمة'})",
             f"سعر الشراء المحدَّد: {halalas_words(row['price_halalas'])} قبل الضريبة، فئة الضريبة {row['vat_category']}"]
    if row["kind"] == "STOCK":
        lines.append(f"الرصيد: {quantity_words(row['on_hand_milli'], row['unit'])}، والقيمة {halalas_words(row['stock_value_halalas'])}")
        if row["reorder_level_milli"] is not None:
            lines.append(f"حدّ الطلب: {quantity_words(row['reorder_level_milli'], row['unit'])}")
        lines.append("آخر جرد: " + (_iso(row["last_counted_on"]) or "لم يُجرد بعد"))
    if row["category_name"]:
        lines.append(f"التصنيف: {row['category_name']}")
    return assistant.fit(lines)


def _screen_purchase(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_SCREEN_PURCHASE, (screen_id,))
    row = cursor.fetchone()
    if row is None:
        raise NotFound
    lines = [f"الحالة: {_HOME_STATUS.get(row['status'], row['status'])}", f"عدد الأسطر: {row['lines']}",
             "الأسعار شاملة الضريبة" if row["prices_include_vat"] else "الأسعار قبل الضريبة"]
    if row["number"] is not None:
        lines.insert(0, f"فاتورة الشراء {document_label('PURCHASE', row['number'])}")
    if row["printed_total_halalas"] is not None:
        lines.append(f"الإجمالي المطبوع: {halalas_words(row['printed_total_halalas'])}")
    return assistant.fit(lines)


def _screen_count(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_SCREEN_COUNT, (screen_id,))
    row = cursor.fetchone()
    if row is None:
        raise NotFound
    return assistant.fit([f"جلسة الجرد {count_label(row['number'])}: {_HOME_STATUS.get(row['status'], row['status'])}",
                          f"النطاق: {COUNT_SCOPE_NAMES[row['scope']]}، {'عدٌّ مغلق' if row['blind'] else 'الرصيد ظاهر'}",
                          f"عُدّ {row['counted']} من {row['items_total']} صنفاً"])


_HOME = assistant.SCREENS["HOME"]


def _home(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_PROFESSION)
    if cursor.fetchone()["profession"] == Profession.STOREKEEPER.value:
        return _inventory_home(cursor, user_id, screen_id)
    return _HOME.load(cursor, user_id, screen_id)


assistant.register(dataclasses.replace(
    _HOME, load=_home,
    extra_labels={**_HOME.extra_labels, Profession.STOREKEEPER: (
        "فاتورة شراء جديدة", "مرتجع من فاتورة", "منتج جديد", "المخزون", "الجرد", "المصاريف", "المجاميع")},
))
assistant.register(ScreenContext(
    kind="INVENTORY_ITEM", profession=Profession.STOREKEEPER, title="بطاقة المنتج",
    labels=("صرف", "جرد", "تعديل", "أرشفة"),
    ready_questions=("متى أرفع حدّ الطلب لهذا المنتج؟", "كيف أصحّح رصيداً خاطئاً؟"),
    needs_id=True, load=_screen_item,
))
assistant.register(ScreenContext(
    kind="INVENTORY_PURCHASE", profession=Profession.STOREKEEPER, title="فاتورة الشراء",
    labels=("أضف سطراً", "راجِع وسجّل", "احذف المسودة", "مرتجع من هذه الفاتورة", "قيد عكسي"),
    ready_questions=("ماذا أتحقّق منه قبل تسجيل الفاتورة؟", "متى أستعمل القيد العكسي بدل المرتجع؟"),
    needs_id=True, load=_screen_purchase,
))
assistant.register(ScreenContext(
    kind="INVENTORY_COUNT", profession=Profession.STOREKEEPER, title="جلسة الجرد",
    labels=("المعدود فعلاً", "صفر", "أضف منتجاً لم يكن في الكشف", "حدّث الأرصدة", "رحّل الجرد", "ألغِ الجلسة"),
    ready_questions=("ماذا أفعل حين يختلف المعدود عن الرصيد؟", "لماذا لا أرى الرصيد وأنا أعدّ؟"),
    needs_id=True, load=_screen_count,
))
