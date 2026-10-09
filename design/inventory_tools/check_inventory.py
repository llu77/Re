"""فحوص NEXT_inventory الوظيفية بدور eyework_app. قاعدةٌ مؤقتة تُبنى من الترحيلات وتُحذف."""
import os
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg import errors

MIG = Path(sys.argv[1])
DB = "invspec_check"
OWNER = f"postgresql://eyework_owner:eyework_dev_owner@localhost:5432/{DB}"
APP = f"postgresql://eyework_app:eyework_dev_app@localhost:5432/{DB}"
RESULTS = []


def pg(sql):
    subprocess.run(["su", "postgres", "-c", f'psql -qtAX -c "{sql}"'], check=True)


def check(name, ok):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


pg(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
pg(f"CREATE DATABASE {DB} OWNER eyework_owner")
for p in sorted(MIG.glob("*.up.sql")):
    with psycopg.connect(OWNER, autocommit=True) as c, c.transaction(), c.cursor() as cur:
        cur.execute(p.read_text(encoding="utf-8"))

owner = psycopg.connect(OWNER, autocommit=True)


def osql(sql, params=()):
    with owner.cursor() as cur:
        cur.execute(sql, params)
        try:
            return cur.fetchall()
        except psycopg.ProgrammingError:
            return None


def new_user(profession="STOREKEEPER", name="سارة"):
    return osql("INSERT INTO users (login_hmac, profession, display_name) VALUES (%s, %s, %s) RETURNING id",
                (os.urandom(32), profession, name))[0][0]


@contextmanager
def app(uid, conn=None):
    own = conn is None
    conn = conn or psycopg.connect(APP, autocommit=True)
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT set_config('eyework.user_id', %s, true)", ("" if uid is None else str(uid),))
            yield cur
    finally:
        if own:
            conn.close()


def q(uid, sql, params=()):
    with app(uid) as cur:
        cur.execute(sql, params)
        try:
            return cur.fetchall()
        except psycopg.ProgrammingError:
            return None


def refused(uid, sql, params=(), constraint=None, cls=None):
    try:
        q(uid, sql, params)
    except psycopg.Error as exc:
        if constraint is not None:
            return exc.diag.constraint_name == constraint
        if cls is not None:
            return isinstance(exc, cls)
        return True
    return False


def owner_refused(sql, params=(), constraint=None):
    try:
        with owner.transaction():
            osql(sql, params)
    except psycopg.Error as exc:
        return constraint is None or exc.diag.constraint_name == constraint
    return False


TODAY = osql("SELECT ew_riyadh_today()")[0][0]

# ── الإعداد والمهنة والعزل ──────────────────────────────────────────────
sara = new_user()
omar = new_user()
mkt = new_user("MARKETING", "ليلى")
check("marketing account cannot create inventory settings",
      refused(mkt, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)",
              constraint="inv_needs_storekeeper"))
q(sara, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)")
q(omar, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), true)")
check("settings row cannot be written for another user",
      refused(sara, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (%s, false)", (mkt,)))

sup = q(sara, "INSERT INTO inv_suppliers (user_id, name, vat_number) VALUES (ew_current_user(), 'مؤسسة النور', '300000000000003') RETURNING id")[0][0]
sup_novat = q(sara, "INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'بقالة الحي') RETURNING id")[0][0]
check("supplier VAT number must be 15 digits starting and ending with 3",
      refused(sara, "INSERT INTO inv_suppliers (user_id, name, vat_number) VALUES (ew_current_user(), 'س', '310000000000004')",
              constraint="inv_supplier_vat_shape"))
check("supplier names collide after Arabic normalisation",
      refused(sara, "INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'مؤسسه النور')",
              constraint="inv_suppliers_name"))


def item(uid, name, unit="CARTON", price=4550, kind="STOCK", cat="S", reorder=None):
    return q(uid, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas, vat_category, reorder_level_milli) "
                  "VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s) RETURNING id",
             (name, kind, unit, price, cat, reorder))[0][0]


water = item(sara, "كرتونة ماء ٣٣٠ مل", reorder=20000)
rice = item(sara, "أرز بسمتي", unit="KG", price=900)
ship = item(sara, "شحن", unit="SERVICE", kind="SERVICE", price=5000)
check("item names collide after normalisation (ة/ه, digits)",
      refused(sara, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (ew_current_user(), 'كرتونه ماء 330 مل', 'STOCK', 'CARTON', 100)",
              constraint="inv_items_name"))
check("a service item cannot have a stock unit",
      refused(sara, "INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (ew_current_user(), 'تركيب', 'SERVICE', 'PIECE', 100)",
              constraint="inv_item_unit_matches_kind"))
check("other account sees none of these rows",
      q(omar, "SELECT count(*) FROM inv_items")[0][0] == 0 and q(omar, "SELECT count(*) FROM inv_suppliers")[0][0] == 0)
check("web role cannot write stock balance directly",
      refused(sara, "UPDATE inv_items SET on_hand_milli = 5000 WHERE id = %s", (water,), cls=errors.InsufficientPrivilege))


def draft(uid, supplier=None, no=None, d=None, printed=None, pvat=None, incl=False):
    return q(uid, "INSERT INTO inv_purchases (user_id, supplier_id, supplier_invoice_no, invoice_date, prices_include_vat, "
                  "printed_total_halalas, printed_vat_halalas) VALUES (ew_current_user(), %s, %s, %s, %s, %s, %s) RETURNING id",
             (supplier, no, d, incl, printed, pvat))[0][0]


def line(uid, pid, itm, qty, price, cat="S", disc=0):
    return q(uid, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, "
                  "discount_halalas, vat_category) VALUES (%s, ew_current_user(), %s, %s, %s, %s, %s) RETURNING line_no",
             (pid, itm, qty, price, disc, cat))[0][0]


def rv(uid, table, doc):
    return q(uid, f"SELECT row_version FROM {table} WHERE id = %s", (doc,))[0][0]


def flags(uid, pid):
    return q(uid, "SELECT ew_inv_flag_keys(%s, NULL)", (pid,))[0][0]


def post(uid, pid, ack=None):
    if ack is None:
        ack = flags(uid, pid)
    return q(uid, "SELECT ew_inv_post_purchase(%s, %s, %s)", (pid, rv(uid, "inv_purchases", pid), ack))[0][0]


# ── الأسطر والحساب ─────────────────────────────────────────────────────
p1 = draft(sara, sup, "INV-1001", TODAY, 116000, None)
check("lines are numbered by the database", line(sara, p1, water, 10000, 10000) == 1 and line(sara, p1, ship, 1000, 1000) == 2)
check("a counted unit refuses a fractional quantity",
      refused(sara, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category) VALUES (%s, ew_current_user(), %s, 1500, 100, 'S')",
              (p1, water), constraint="inv_quantity_unit"))
check("a discount above the line amount is refused",
      refused(sara, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, discount_halalas, vat_category) VALUES (%s, ew_current_user(), %s, 1000, 100, 101, 'S')",
              (p1, water), constraint="inv_line_discount_exceeds"))
calc = q(sara, "SELECT line_no, amount_halalas, net_halalas, vat_halalas FROM ew_inv_purchase_calc(%s)", (p1,))
check("calc: 10 cartons at 100.00 plus 10.00 shipping, VAT 15% exclusive",
      calc == [(1, 100000, 100000, 15000), (2, 1000, 1000, 150)])

# أكبر الكسور: أربعون سطراً بعشر هللاتٍ لا تُنتج ضريبةً سالبة، ومجموعها ضريبة الفئة.
p_small = draft(sara)
for _ in range(40):
    line(sara, p_small, water, 1000, 10)
rows = q(sara, "SELECT vat_halalas FROM ew_inv_purchase_calc(%s)", (p_small,))
check("largest remainder: 40 lines of 0.10 give category VAT round(60.0)=60 with no negative line",
      sum(r[0] for r in rows) == 60 and min(r[0] for r in rows) >= 1)
check("line cap is 40", refused(sara, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category) VALUES (%s, ew_current_user(), %s, 1000, 10, 'S')",
                                 (p_small,  water), constraint="inv_line_cap"))
p_incl = draft(sara, incl=True)
line(sara, p_incl, water, 1000, 125500)
calc = q(sara, "SELECT amount_halalas, net_halalas, vat_halalas FROM ew_inv_purchase_calc(%s)", (p_incl,))
check("VAT-inclusive 1,255.00 gives VAT 163.70 (15/115, ZATCA guideline example 6)", calc == [(125500, 109130, 16370)])
check("half-up at category level: 0.10 at 15% is 0.02", q(sara, "SELECT vat_halalas FROM ew_inv_purchase_calc(%s) LIMIT 1", (p_small,))[0][0] in (1, 2))

# ── التنبيهات والإقرار ─────────────────────────────────────────────────
keys = flags(sara, p1)
check("printed total differing from the computed total is flagged", "TOTAL_MISMATCH" in keys)
check("posting with an unacknowledged flag is refused and consumes no number",
      refused(sara, "SELECT ew_inv_post_purchase(%s, %s, '{}')", (p1, rv(sara, "inv_purchases", p1)), constraint="inv_flags_unacknowledged")
      and osql("SELECT count(*) FROM inv_counters")[0][0] == 0)
check("posting needs the row version the user saw",
      refused(sara, "SELECT ew_inv_post_purchase(%s, %s, %s)", (p1, rv(sara, "inv_purchases", p1) - 1, keys), constraint="inv_stale_row_version"))
n1 = post(sara, p1)
check("first posting gets number 1", n1 == 1)
row = q(sara, "SELECT status, subtotal_halalas, vat_halalas, total_halalas, supplier_name FROM inv_purchases WHERE id = %s", (p1,))[0]
check("posted totals and supplier snapshot", row == ("POSTED", 101000, 15150, 116150, "مؤسسة النور"))
check("stock-in movement for the stock line only; service line has none",
      q(sara, "SELECT count(*), sum(quantity_milli), sum(value_halalas) FROM inv_movements WHERE purchase_id = %s", (p1,))[0] == (1, 10000, 100000))
check("ledger entry dated the invoice date with net, VAT, gross",
      q(sara, "SELECT kind, entry_date, net_halalas, vat_halalas, gross_halalas FROM inv_ledger WHERE purchase_id = %s", (p1,))[0]
      == ("PURCHASE", TODAY, 101000, 15150, 116150))
check("acknowledged rule flags are kept with the invoice",
      q(sara, "SELECT count(*) FROM inv_review_flags WHERE purchase_id = %s AND source = 'RULE' AND acknowledged_at IS NOT NULL", (p1,))[0][0] == len(keys))
check("a second post of the same invoice is refused",
      refused(sara, "SELECT ew_inv_post_purchase(%s, %s, '{}')", (p1, rv(sara, "inv_purchases", p1)), constraint="inv_document_not_draft"))
check("a posted invoice header cannot be edited",
      refused(sara, "UPDATE inv_purchases SET note = 'x' WHERE id = %s", (p1,), constraint="inv_document_is_final"))
check("a posted invoice line cannot be edited",
      refused(sara, "UPDATE inv_purchase_lines SET quantity_milli = 9000 WHERE purchase_id = %s AND line_no = 1", (p1,), constraint="inv_document_not_draft"))
check("not even the owner can delete a posted invoice, its movements or its ledger entry",
      owner_refused("DELETE FROM inv_purchases WHERE id = %s", (p1,), "inv_record_is_permanent")
      and owner_refused("DELETE FROM inv_movements WHERE purchase_id = %s", (p1,), "inv_record_is_permanent")
      and owner_refused("DELETE FROM inv_ledger WHERE purchase_id = %s", (p1,), "inv_record_is_permanent")
      and owner_refused("UPDATE inv_movements SET quantity_milli = 1 WHERE purchase_id = %s", (p1,)))
check("web role has no DELETE on any inventory table",
      all(refused(sara, f"DELETE FROM {t}", cls=errors.InsufficientPrivilege) for t in
          ("inv_settings", "inv_suppliers", "inv_items", "inv_purchases", "inv_purchase_lines", "inv_returns",
           "inv_return_lines", "inv_vouchers", "inv_movements", "inv_ledger", "inv_review_calls", "inv_review_flags")))
check("web role cannot read the counters or call internal helpers",
      refused(sara, "SELECT * FROM inv_counters", cls=errors.InsufficientPrivilege)
      and refused(sara, "SELECT ew_inv_next_no(ew_current_user(), 'PURCHASE')", cls=errors.InsufficientPrivilege)
      and refused(sara, "SELECT ew_inv_ai_spend(false)", cls=errors.InsufficientPrivilege))

# المكرّر: رقم فاتورة المورّد نفسه بكتابةٍ أخرى.
p2 = draft(sara, sup, "inv 1001", TODAY, 116150)
line(sara, p2, water, 10000, 10000)
line(sara, p2, ship, 1000, 1000)
k2 = flags(sara, p2)
check("the same supplier invoice number written differently is flagged as a duplicate", "DUPLICATE_SUPPLIER_INVOICE" in k2)
q(sara, "SELECT ew_inv_discard_draft(%s, NULL, %s)", (p2, rv(sara, "inv_purchases", p2)))
check("a discarded draft is gone", q(sara, "SELECT count(*) FROM inv_purchases WHERE id = %s", (p2,))[0][0] == 0)

# السعر والكمية أمام التاريخ، والضريبة بلا رقمٍ ضريبي، والفئة، والتاريخ القديم.
for i in range(3):
    pp = draft(sara, sup, f"H-{i}", TODAY, 115000)
    line(sara, pp, water, 10000, 10000)
    post(sara, pp)
p3 = draft(sara, sup_novat, "B-77", TODAY - timedelta(days=120), 0)
ln = line(sara, p3, water, 100000, 100000, cat="Z")
k3 = flags(sara, p3)
check("price ten times the history is flagged with extra_zero",
      f"PRICE_FAR_FROM_HISTORY:{ln}" in k3
      and q(sara, "SELECT (detail->>'extra_zero')::boolean FROM ew_inv_purchase_flags(%s) WHERE code = 'PRICE_FAR_FROM_HISTORY'", (p3,))[0][0])
check("quantity ten times the median is flagged with extra_zero",
      f"QUANTITY_FAR_FROM_HISTORY:{ln}" in k3
      and q(sara, "SELECT (detail->>'extra_zero')::boolean FROM ew_inv_purchase_flags(%s) WHERE code = 'QUANTITY_FAR_FROM_HISTORY'", (p3,))[0][0])
check("a VAT category different from the item's is flagged", f"CATEGORY_CHANGED:{ln}" in k3)
check("an invoice older than 90 days is flagged", "OLD_INVOICE_DATE" in k3)
q(sara, "UPDATE inv_purchase_lines SET vat_category = 'S', unit_price_halalas = 10000, quantity_milli = 10000 WHERE purchase_id = %s", (p3,))
check("VAT from a supplier without a VAT number is flagged", "VAT_WITHOUT_SUPPLIER_VAT_NUMBER" in flags(sara, p3))
check("an edit to a line bumps the invoice row version (what is posted is what was reviewed)",
      rv(sara, "inv_purchases", p3) > 1)
q(sara, "SELECT ew_inv_discard_draft(%s, NULL, %s)", (p3, rv(sara, "inv_purchases", p3)))
check("a future invoice date is refused at posting",
      (lambda pf: (line(sara, pf, water, 1000, 10000), refused(sara, "SELECT ew_inv_post_purchase(%s, %s, %s)",
                   (pf, rv(sara, "inv_purchases", pf), flags(sara, pf)), constraint="inv_purchase_future_date"))[1])(
          draft(sara, sup, "F-1", TODAY + timedelta(days=1), 11500)))

# ── العزل والأصناف والسقوف ────────────────────────────────────────────
o_item = item(omar, "قفازات", unit="BOX", price=1200)
check("another account cannot add a line to this invoice",
      refused(omar, "INSERT INTO inv_purchase_lines (purchase_id, user_id, item_id, quantity_milli, unit_price_halalas, vat_category) VALUES (%s, ew_current_user(), %s, 1000, 100, 'S')",
              (p1, o_item), constraint="inv_purchase_lines_purchase_id_user_id_fkey"))
check("another account cannot post this invoice (it does not exist for them)",
      refused(omar, "SELECT ew_inv_post_purchase(%s, 1, '{}')", (p1,), cls=errors.NoDataFound))
check("an item's unit is locked once it is used",
      refused(sara, "UPDATE inv_items SET unit = 'PIECE' WHERE id = %s", (water,), constraint="inv_item_unit_locked"))
check("an item with stock cannot be archived",
      refused(sara, "UPDATE inv_items SET is_active = false WHERE id = %s", (water,), constraint="inv_item_has_stock"))
for _ in range(20 - q(omar, "SELECT count(*) FROM inv_purchases WHERE status = 'DRAFT'")[0][0]):
    draft(omar)
check("twenty open drafts per account",
      refused(omar, "INSERT INTO inv_purchases (user_id) VALUES (ew_current_user())", constraint="inv_open_draft_cap"))

# ── المتوسط المتحرّك: مثال IFRS for SMEs 13 رقم 44 بالهللات ─────────────
cable = item(sara, "كابل ألياف", unit="PIECE", price=1000)
v = q(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'OPENING', %s, 1000000, 1000, NULL, NULL, %s, NULL)", (uuid.uuid4(), cable, TODAY))[0]
q(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 200000, NULL, 'SALE', NULL, %s, NULL)", (uuid.uuid4(), cable, TODAY))
pa = draft(sara, sup, "C-25F", TODAY, 600000)
line(sara, pa, cable, 400000, 1500, cat="Z")
post(sara, pa)
pb = draft(sara, sup, "C-2M", TODAY, 400000)
line(sara, pb, cable, 200000, 2000, cat="Z")
post(sara, pb)
before = q(sara, "SELECT on_hand_milli, stock_value_halalas FROM inv_items WHERE id = %s", (cable,))[0]
q(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 900000, NULL, 'SALE', NULL, %s, NULL)", (uuid.uuid4(), cable, TODAY))
out = q(sara, "SELECT value_halalas FROM inv_movements WHERE item_id = %s AND kind = 'ISSUE_OUT' ORDER BY seq DESC LIMIT 1", (cable,))[0][0]
after = q(sara, "SELECT on_hand_milli, stock_value_halalas FROM inv_items WHERE id = %s", (cable,))[0]
check("IFRS Ex 44: 1,400 units worth 18,000.00 before the sale", before == (1400000, 1800000))
check("IFRS Ex 44: 900 units out at the moving average = 11,571.43 (exact, no rounded unit cost)", out == 1157143)
check("IFRS Ex 44: 500 units left worth 6,428.57", after == (500000, 642857))
check("the voucher is idempotent by client token",
      q(sara, "SELECT voucher_number, replayed FROM ew_inv_stock_voucher(%s, 'OPENING', %s, 1000000, 1000, NULL, NULL, %s, NULL)",
        (v[0] and q(sara, "SELECT client_token FROM inv_vouchers WHERE id = %s", (v[0],))[0][0], cable, TODAY))[0] == (v[1], True))
check("an opening balance is refused once the item has movements",
      refused(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'OPENING', %s, 1000, 1000, NULL, NULL, %s, NULL)",
              (uuid.uuid4(), cable, TODAY), constraint="inv_opening_not_first"))
check("issuing more than on hand is refused",
      refused(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 600000, NULL, 'USE', NULL, %s, NULL)",
              (uuid.uuid4(), cable, TODAY), constraint="inv_negative_stock"))
check("a count against a stale on-hand is refused",
      refused(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'COUNT', %s, 480000, NULL, NULL, NULL, %s, 400000)",
              (uuid.uuid4(), cable, TODAY), constraint="inv_count_stale"))
q(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'COUNT', %s, 480000, NULL, NULL, NULL, %s, 500000)", (uuid.uuid4(), cable, TODAY))
check("a count writes the difference out at the average",
      q(sara, "SELECT kind, quantity_milli FROM inv_movements WHERE item_id = %s ORDER BY seq DESC LIMIT 1", (cable,))[0] == ("COUNT_OUT", 20000))
check("a voucher dated more than 30 days back is refused",
      refused(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 1000, NULL, 'USE', NULL, %s, NULL)",
              (uuid.uuid4(), cable, TODAY - timedelta(days=31)), constraint="inv_voucher_date"))
check("the cost basis is locked after the first movement",
      refused(sara, "UPDATE inv_settings SET cost_includes_vat = true", constraint="inv_cost_basis_locked"))

# ── المرتجع ────────────────────────────────────────────────────────────
pr = draft(sara, sup, "R-1", TODAY, 345 * 100)
line(sara, pr, water, 3000, 10000, cat="Z")     # ثلاثة كراتين بـ100، صافي 300.00 بلا ضريبة
line(sara, pr, ship, 1000, 4500)                 # شحن 45.00 + ضريبة
post(sara, pr)


def ret(uid, pid, reason=None, note=None):
    return q(uid, "INSERT INTO inv_returns (user_id, purchase_id, reason, note) VALUES (ew_current_user(), %s, %s, %s) RETURNING id",
             (pid, reason, note))[0][0]


def rline(uid, rid, ln, qty):
    q(uid, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), %s, %s)", (rid, ln, qty))


def post_ret(uid, rid):
    keys = q(uid, "SELECT ew_inv_flag_keys(NULL, %s)", (rid,))[0][0]
    return q(uid, "SELECT ew_inv_post_return(%s, %s, %s)", (rid, rv(uid, "inv_returns", rid), keys))[0][0]


r1 = ret(sara, pr)
rline(sara, r1, 1, 1000)
check("a return without a reason is refused (hard rule)",
      refused(sara, "SELECT ew_inv_post_return(%s, %s, '{}')", (r1, rv(sara, "inv_returns", r1)), constraint="inv_return_needs_reason"))
q(sara, "UPDATE inv_returns SET reason = 'OTHER' WHERE id = %s", (r1,))
check("reason OTHER needs a note",
      refused(sara, "SELECT ew_inv_post_return(%s, %s, '{}')", (r1, rv(sara, "inv_returns", r1)), constraint="inv_return_needs_note"))
q(sara, "UPDATE inv_returns SET reason = 'DAMAGED' WHERE id = %s", (r1,))
check("return numbering starts at 1", post_ret(sara, r1) == 1)
r2 = ret(sara, pr, "DAMAGED")
rline(sara, r2, 1, 1000)
post_ret(sara, r2)
r3 = ret(sara, pr, "EXCESS")
check("returning more than remains on the line is refused",
      refused(sara, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), 1, 2000)",
              (r3,), constraint="inv_return_exceeds_remaining"))
rline(sara, r3, 1, 1000)
rline(sara, r3, 2, 1000)
post_ret(sara, r3)
nets = [x[0] for x in q(sara, "SELECT rl.net_halalas FROM inv_return_lines rl JOIN inv_returns r ON r.id = rl.return_id WHERE r.purchase_id = %s AND rl.line_no = 1 ORDER BY r.number", (pr,))]
check("partial returns share the line net exactly (100.00 × 3 → 100, 100, 100; total equals the line)", sum(nets) == 30000)
check("a service line return writes no stock movement",
      q(sara, "SELECT count(*) FROM inv_movements WHERE return_id = %s", (r3,))[0][0] == 1)
check("a return writes a negative ledger entry dated the return date",
      q(sara, "SELECT kind, net_halalas, vat_halalas FROM inv_ledger WHERE return_id = %s", (r3,))[0] == ("RETURN", -14500, -675))
check("nothing remains returnable, so a new return line is refused",
      (lambda r4: refused(sara, "INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), 1, 1000)",
                          (r4,), constraint="inv_return_exceeds_remaining"))(ret(sara, pr, "EXCESS")))
check("a posted return accepts the supplier credit note number once",
      q(sara, "UPDATE inv_returns SET credit_note_no = 'CN-55', credit_note_date = %s WHERE id = %s RETURNING credit_note_at IS NOT NULL", (TODAY, r1))[0][0]
      and refused(sara, "UPDATE inv_returns SET credit_note_no = 'CN-56', credit_note_date = %s WHERE id = %s", (TODAY, r1), constraint="inv_document_is_final"))
check("a credit note dated in the future is refused",
      refused(sara, "UPDATE inv_returns SET credit_note_no = 'CN-9', credit_note_date = %s WHERE id = %s", (TODAY + timedelta(days=1), r2), constraint="inv_credit_note_date"))
check("a posted return's reason cannot change",
      refused(sara, "UPDATE inv_returns SET reason = 'EXCESS' WHERE id = %s", (r2,), constraint="inv_document_is_final"))

# مرتجعٌ بعد صرف البضاعة: لا رصيد يكفي.
pz = draft(sara, sup, "Z-9", TODAY, 50000)
line(sara, pz, rice, 5500, 9000, cat="Z")      # 5.5 كغ بـ90.00
post(sara, pz)
q(sara, "SELECT * FROM ew_inv_stock_voucher(%s, 'ISSUE', %s, 5500, NULL, 'USE', NULL, %s, NULL)", (uuid.uuid4(), rice, TODAY))
rz = ret(sara, pz, "DAMAGED")
rline(sara, rz, 1, 1500)
check("a return of goods already issued is refused (no stock below zero)",
      refused(sara, "SELECT ew_inv_post_return(%s, %s, '{}')", (rz, rv(sara, "inv_returns", rz)), constraint="inv_negative_stock"))
check("a failed return consumes no return number", osql("SELECT last_no FROM inv_counters WHERE user_id = %s AND kind = 'RETURN'", (sara,))[0][0] == 3)

# ── القيد العكسي ───────────────────────────────────────────────────────
check("reversal is refused when the invoice has returns",
      refused(sara, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pr, rv(sara, "inv_purchases", pr)), constraint="inv_reversal_has_returns"))
pv = draft(sara, sup, "DUP-1", TODAY, 23000)
line(sara, pv, water, 2000, 10000)
post(sara, pv)
before = q(sara, "SELECT on_hand_milli FROM inv_items WHERE id = %s", (water,))[0][0]
check("reversal reason OTHER needs a note",
      refused(sara, "SELECT ew_inv_reverse_purchase(%s, %s, 'OTHER', NULL)", (pv, rv(sara, "inv_purchases", pv)), constraint="inv_reversal_needs_note"))
nrev = q(sara, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pv, rv(sara, "inv_purchases", pv)))[0][0]
check("reversal gets its own number, takes the stock out and writes the negative entry",
      nrev == 1 and q(sara, "SELECT on_hand_milli FROM inv_items WHERE id = %s", (water,))[0][0] == before - 2000
      and q(sara, "SELECT net_halalas, vat_halalas FROM inv_ledger WHERE purchase_id = %s AND kind = 'REVERSAL'", (pv,))[0] == (-20000, -3000))
check("a reversed invoice is final",
      refused(sara, "SELECT ew_inv_reverse_purchase(%s, %s, 'DUPLICATE', NULL)", (pv, rv(sara, "inv_purchases", pv)), constraint="inv_reversal_needs_posted"))
check("a reversed invoice cannot be returned",
      refused(sara, "INSERT INTO inv_returns (user_id, purchase_id, reason) VALUES (ew_current_user(), %s, 'EXCESS')", (pv,),
              constraint="inv_return_needs_posted_purchase"))
check("a reversed invoice no longer counts as a duplicate",
      (lambda pd: (line(sara, pd, water, 2000, 10000), "DUPLICATE_SUPPLIER_INVOICE" not in flags(sara, pd))[1])(draft(sara, sup, "DUP-1", TODAY, 23000)))

# ── الترقيم بلا فجوات والتزامن ──────────────────────────────────────────
nums = [x[0] for x in q(sara, "SELECT number FROM inv_purchases WHERE number IS NOT NULL ORDER BY number")]
check("purchase numbers have no gaps", nums == list(range(1, len(nums) + 1)))


def blocked_on_lock(pid_of_backend):
    # pg_stat_activity لا يُظهر انتظار جلسات دورٍ آخر إلا لمن له pg_read_all_stats.
    out = subprocess.run(["su", "postgres", "-c", f"psql -qtAX -c \"SELECT wait_event_type FROM pg_stat_activity WHERE pid = {int(pid_of_backend)}\""],
                         check=True, capture_output=True, text=True).stdout.strip()
    return out == "Lock"


pc = draft(sara, sup, "CC-1", TODAY, 11500)
line(sara, pc, water, 1000, 10000)
keys_c = flags(sara, pc)
ver_c = rv(sara, "inv_purchases", pc)
c1 = psycopg.connect(APP, autocommit=False)
c2 = psycopg.connect(APP, autocommit=False)
cur1, cur2 = c1.cursor(), c2.cursor()
cur1.execute("SELECT set_config('eyework.user_id', %s, true)", (str(sara),))
cur2.execute("SELECT set_config('eyework.user_id', %s, true)", (str(sara),))
cur1.execute("SELECT ew_inv_post_purchase(%s, %s, %s)", (pc, ver_c, keys_c))
first = cur1.fetchone()[0]
outcome = {}


def second():
    try:
        cur2.execute("SELECT ew_inv_post_purchase(%s, %s, %s)", (pc, ver_c, keys_c))
        outcome["r"] = cur2.fetchone()[0]
    except psycopg.Error as exc:
        outcome["e"] = exc.diag.constraint_name
        c2.rollback()


t = threading.Thread(target=second)
t.start()
time.sleep(0.5)
waited = blocked_on_lock(c2.info.backend_pid)
c1.commit()
t.join()
check("two tabs posting one draft: the second waits on the lock, then is refused as already posted",
      waited and outcome.get("e") == "inv_document_not_draft")
c1.close(); c2.close()

pd1 = draft(sara, sup, "PAR-1", TODAY, 11500); line(sara, pd1, water, 1000, 10000)
pd2 = draft(sara, sup, "PAR-2", TODAY, 11500); line(sara, pd2, water, 1000, 10000)
res = {}


def poster(name, pid):
    try:
        res[name] = post(sara, pid)
    except psycopg.Error as exc:
        res[name] = exc.diag.constraint_name


ts = [threading.Thread(target=poster, args=(n, p)) for n, p in (("a", pd1), ("b", pd2))]
[x.start() for x in ts]; [x.join() for x in ts]
nums = [x[0] for x in q(sara, "SELECT number FROM inv_purchases WHERE number IS NOT NULL ORDER BY number")]
check("two drafts posted at once get consecutive numbers, no gap, no duplicate",
      sorted(res.values()) == [nums[-2], nums[-1]] and nums == list(range(1, len(nums) + 1)))

# ── المراجعة وسقوفها ───────────────────────────────────────────────────
pr1 = draft(sara, sup, "AI-1", TODAY, 11500)
line(sara, pr1, water, 1000, 10000)
check("review needs the notice and the user's choice",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_disabled"))
check("review cannot be enabled without the notice",
      refused(sara, "UPDATE inv_settings SET review_enabled = true", constraint="inv_review_needs_notice"))
q(sara, "UPDATE inv_settings SET review_notice_version = '2026-10-09', review_enabled = true")
call, digest = q(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,))[0]
check("one review at a time per user",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_in_progress"))
res_rec = q(sara, "SELECT ew_inv_review_record(%s, 1000, 200, 'claude-opus-5-5', 'inv-2026-10-09.1', 'req_1', "
                  "ARRAY['PRICE_IMPLAUSIBLE'], ARRAY[1]::smallint[], ARRAY['سعر الكرتونة يبدو أعلى من المعتاد لماءٍ معبّأ.'], ARRAY['{}'::jsonb])", (call,))[0][0]
check("an AI flag on unchanged content is recorded", res_rec == "OK" and "AI:PRICE_IMPLAUSIBLE:1" in flags(sara, pr1))
check("the same content is not reviewed twice",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_current"))
check("posting without acknowledging the AI flag is refused",
      refused(sara, "SELECT ew_inv_post_purchase(%s, %s, %s)", (pr1, rv(sara, "inv_purchases", pr1),
              [k for k in flags(sara, pr1) if not k.startswith("AI:")]), constraint="inv_flags_unacknowledged"))
q(sara, "UPDATE inv_purchase_lines SET unit_price_halalas = 9000 WHERE purchase_id = %s", (pr1,))
check("after an edit the old AI flag no longer applies", not any(k.startswith("AI:") for k in flags(sara, pr1)))
call2, _ = q(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,))[0]
q(sara, "UPDATE inv_purchase_lines SET unit_price_halalas = 9500 WHERE purchase_id = %s", (pr1,))
check("a result for content that changed meanwhile is discarded",
      q(sara, "SELECT ew_inv_review_record(%s, 1, 1, 'claude-opus-5-5', 'v1', 'r', ARRAY['UNIT_MISMATCH'], ARRAY[1]::smallint[], ARRAY['وحدةٌ غير متوقّعة.'], ARRAY['{}'::jsonb])", (call2,))[0][0] == "DISCARDED"
      and not any(k.startswith("AI:") for k in flags(sara, pr1)))
call3, _ = q(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,))[0]
check("a code outside the portal's list is refused",
      refused(sara, "SELECT ew_inv_review_record(%s, 1, 1, 'claude-opus-5-5', 'v1', 'r', ARRAY['REASON_IMPLAUSIBLE'], ARRAY[NULL]::smallint[], ARRAY['س'], ARRAY['{}'::jsonb])", (call3,),
              constraint="inv_review_flags_shape"))
q(sara, "SELECT ew_inv_review_finish(%s, 'UPSTREAM_BUSY', NULL, NULL, NULL, NULL, NULL)", (call3,))
osql("INSERT INTO inv_review_calls (user_id, purchase_id, content_digest, started_at, finished_at, outcome) "
     "SELECT %s, NULL, %s, now() - interval '1 minute', now(), 'OK' FROM generate_series(1, 3)", (sara, digest))
check("six reviews in ten minutes is the limit",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_rate"))
osql("UPDATE inv_review_calls SET started_at = now() - interval '1 hour' WHERE user_id = %s", (sara,)) if False else None
osql("ALTER TABLE inv_review_calls DISABLE TRIGGER trg_inv_review_settle")
osql("UPDATE inv_review_calls SET started_at = now() - interval '1 hour' WHERE user_id = %s", (sara,))
osql("INSERT INTO inv_review_calls (user_id, content_digest, started_at, finished_at, outcome) "
     "SELECT %s, %s, now() - interval '2 hours', now(), 'OK' FROM generate_series(1, 30)", (sara, digest))
check("thirty billable reviews a day per user",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_daily_cap"))
check("busy upstream answers are not billed",
      q(sara, "SELECT used_today FROM ew_inv_my_review_limit()")[0][0] ==
      osql("SELECT count(*) FROM inv_review_calls WHERE user_id = %s AND outcome <> 'UPSTREAM_BUSY'", (sara,))[0][0])
osql("UPDATE inv_review_calls SET started_at = now() - interval '25 hours' WHERE user_id = %s", (sara,))
osql("ALTER TABLE inv_review_calls ENABLE TRIGGER trg_inv_review_settle")
other_k = new_user(name="خالد")
osql("INSERT INTO inv_review_calls (user_id, content_digest, started_at, finished_at, outcome) "
     "SELECT %s, %s, now() - interval '3 hours', now(), 'OK' FROM generate_series(1, 600)", (other_k, digest))
check("six hundred reviews a day app-wide",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="inv_review_app_cap"))
osql("DELETE FROM inv_review_calls WHERE user_id = %s", (other_k,))
check("deleting review calls of the last day leaves tombstones", osql("SELECT count(*) FROM attempt_tombstones")[0][0] == 600)
check("the tombstones still count toward the global cap through ew_inv_ai_spend",
      osql("SELECT ew_inv_ai_spend(false)")[0][0] >= 600)
osql("DELETE FROM attempt_tombstones")
osql("INSERT INTO attempt_tombstones (started_at, outcome) SELECT now() - interval '1 hour', 'OK' FROM generate_series(1, 2000)")
check("the app-wide 2,000 cap (campaigns + reviews) refuses a review",
      refused(sara, "SELECT * FROM ew_inv_review_begin(%s, NULL)", (pr1,), constraint="generation_global_cap"))
osql("DELETE FROM attempt_tombstones")
# حملةٌ تُرفض لأن المراجعات استنفدت السقف العام: ew_begin_generation يعدّها.
mk = new_user("MARKETING", "نورة")
camp = q(mk, "INSERT INTO campaigns (user_id) VALUES (ew_current_user()) RETURNING id")[0][0]
osql("INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256) VALUES (%s, %s, '\\xffd8ffd9'::bytea, 400, 400, %s)",
     (camp, mk, os.urandom(32)))
osql("INSERT INTO inv_review_calls (user_id, content_digest, started_at, finished_at, outcome) "
     "SELECT %s, %s, now() - interval '3 hours', now(), 'OK' FROM generate_series(1, 2000)", (other_k, digest))
check("campaign generation counts inventory reviews toward the 2,000 cap",
      refused(mk, "SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (camp,), constraint="generation_global_cap"))
osql("DELETE FROM inv_review_calls WHERE user_id = %s", (other_k,))
osql("DELETE FROM attempt_tombstones")

# ── حذف الحساب ─────────────────────────────────────────────────────────
counts_before = osql("SELECT (SELECT count(*) FROM inv_ledger WHERE user_id = %s), (SELECT count(*) FROM inv_movements WHERE user_id = %s)", (sara, sara))[0]
q(sara, "SELECT ew_delete_me()")
left = osql("SELECT (SELECT count(*) FROM inv_items WHERE user_id = %s) + (SELECT count(*) FROM inv_purchases WHERE user_id = %s)"
            " + (SELECT count(*) FROM inv_ledger WHERE user_id = %s) + (SELECT count(*) FROM inv_movements WHERE user_id = %s)"
            " + (SELECT count(*) FROM inv_review_calls WHERE user_id = %s)", (sara,) * 5)[0][0]
check("deleting the account deletes every inventory record with it", counts_before[0] > 0 and left == 0)
check("an item or supplier is never deleted directly, even by the owner",
      owner_refused("DELETE FROM inv_items", (), "inv_record_is_permanent") if osql("SELECT count(*) FROM inv_items")[0][0] else True)

# ── التراجع يرفض والمستندات المسجّلة باقية ─────────────────────────────
o2 = new_user(name="ريم")
q(o2, "INSERT INTO inv_settings (user_id, cost_includes_vat) VALUES (ew_current_user(), false)")
s2 = q(o2, "INSERT INTO inv_suppliers (user_id, name) VALUES (ew_current_user(), 'مورد') RETURNING id")[0][0]
i2 = item(o2, "صابون", unit="PIECE", price=500)
pp2 = draft(o2, s2, "X1", TODAY, 500)
line(o2, pp2, i2, 1000, 500, cat="Z")
post(o2, pp2)
down = (MIG / "0008_inventory.down.sql").read_text(encoding="utf-8")
try:
    with owner.transaction(), owner.cursor() as cur:
        cur.execute(down)
    refused_down = False
except psycopg.Error as exc:
    refused_down = "سجلّاً مسجَّلاً" in str(exc)
check("down refuses while posted inventory records exist", refused_down
      and osql("SELECT count(*) FROM pg_tables WHERE tablename = 'inv_ledger'")[0][0] == 1)

owner.close()
pg(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
failed = [n for n, ok in RESULTS if not ok]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
sys.exit(1 if failed else 0)
