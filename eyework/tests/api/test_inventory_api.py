"""
بوابة المخزون عبر الواجهة البرمجية
==================================
التطبيق الحقيقي بالبوّابة المصطنعة: أمين مخزونٍ يُعدّ مخزنه ومورّديه ومندوبيهم
وتصنيفاته ومنتجاته، ويسجّل فاتورة شراءٍ بتنبيهاتها وإقرارها، ويراجعها مع سيمبول
(المسار المشترك `/api/ai/review` بالأداة STOCK_REVIEW) فتحجز ملاحظته التسجيل حتى
يُبتّ، ثم مرتجعاً وإشعاره الدائن، وسنداتٍ وجلسة جرد، ويقرأ المصروفات والملخّص.
ومهنةٌ أخرى 403، ومستند غيره 404، والضغطة المكرّرة 409.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from eyework import auth, config, inventory, reviewer
from eyework.assistant import NO_SCREEN
from eyework.db import Database
from eyework.inventory_prompt import PAYLOAD_KEYS
from eyework.tests.api.conftest import LOGIN_KEY, ORIGIN, add_user, expect, log_in
from eyework.tests.api.test_ai_review import _keys, check_loader_keys
from eyework.tests.conftest import app_url_for
from eyework.tests.fakes import FakeGateway, flag, review_reply
from eyework.web.app import create_app

KEEPER = "keeper@example.sa"
OTHER = "other-keeper@example.sa"
MARKETER = "marketer@example.sa"
NAME = "سارة"
BASE = "/api/inventory"


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def server(owner, owner_url, writer, gateway):
    settings = config.Settings(app_database_url=app_url_for(owner_url), login_key=LOGIN_KEY,
                               anthropic_api_key=None, public_origin=ORIGIN)
    database = Database(settings.app_database_url)
    try:
        yield create_app(settings, copywriter=writer, gateway=gateway, database=database)
    finally:
        database.close()


def _signed_in(owner, browser, username: str, *, profession: str = "STOREKEEPER"):
    user_id = add_user(owner, username, profession=profession)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = %s WHERE id = %s", (NAME, user_id))
    client = browser()
    assert log_in(client, username).status_code == 204
    return client, user_id


@pytest.fixture
def keeper(owner, browser):
    return _signed_in(owner, browser, KEEPER)


@pytest.fixture
def other(owner, browser):
    return _signed_in(owner, browser, OTHER)


@pytest.fixture
def today(owner) -> str:
    with owner.cursor() as cursor:
        cursor.execute("SELECT ew_riyadh_today()")
        return cursor.fetchone()[0].isoformat()


# ── أدوات ───────────────────────────────────────────────────────────────
def setup(client, **overrides) -> dict:
    body = {"cost_includes_vat": False, **overrides}
    return expect(client.put(f"{BASE}/settings", json=body))


def supplier(client, name="مؤسسة النور", vat="300000000000003", **extra) -> dict:
    return expect(client.post(f"{BASE}/suppliers", json={"name": name, "vat_number": vat, **extra}), 201)


def item(client, name, unit="CARTON", price=4550, kind="STOCK", **extra) -> dict:
    return expect(client.post(f"{BASE}/items", json={"name": name, "kind": kind, "unit": unit, "price_halalas": price, **extra}), 201)


def draft(client, sup, no="INV-1001", day=None, printed=None, **extra) -> dict:
    body = {"supplier_id": sup["id"], "supplier_invoice_no": no, "invoice_date": day, "printed_total_halalas": printed, **extra}
    return expect(client.post(f"{BASE}/purchases", json=body), 201)


def line(client, purchase, itm, qty, price, **extra) -> dict:
    body = {"expected_row_version": purchase["row_version"], "item_id": itm["id"], "quantity_milli": qty,
            "unit_price_halalas": price, **extra}
    return expect(client.post(f"{BASE}/purchases/{purchase['id']}/lines", json=body), 201)


def flags_of(client, purchase) -> dict:
    return expect(client.get(f"{BASE}/purchases/{purchase['id']}/flags"))


def post(client, purchase, acknowledged=None) -> dict:
    keys = [f["key"] for f in flags_of(client, purchase)["flags"]] if acknowledged is None else acknowledged
    return expect(client.post(f"{BASE}/purchases/{purchase['id']}/post",
                              json={"expected_row_version": purchase["row_version"], "acknowledged": keys}))


def review(client, kind: str, subject_id: str, row_version: int):
    return client.post("/api/ai/review", json={"feature": "STOCK_REVIEW", "subject_kind": kind, "subject_id": subject_id,
                                               "expected_row_version": row_version})


def _scene(client, today):
    """إعدادٌ ومورّدٌ بمندوب، ومنتجان، وفاتورةٌ بسطرٍ واحد غير مسجّلة."""
    setup(client)
    sup = supplier(client)
    rep = expect(client.post(f"{BASE}/suppliers/{sup['id']}/reps", json={"name": "أحمد", "mobile": "0501234567", "is_default": True}), 201)
    water = item(client, "كرتونة ماء ٣٣٠ مل", price=10000, reorder_level_milli=20000)
    rice = item(client, "أرز بسمتي", unit="KG", price=900)
    p = draft(client, sup, day=today, printed=115000)
    p = line(client, p, water, 10000, 10000)
    return sup, rep, water, rice, p


# ── المهنة والإعداد والبيانات الأساسية ──────────────────────────────────
def test_only_a_storekeeper_enters_and_settings_name_the_store(owner, browser, keeper):
    client, _ = keeper
    marketer, _ = _signed_in(owner, browser, MARKETER, profession="MARKETING")
    assert marketer.get(f"{BASE}/summary").status_code == 403
    assert marketer.put(f"{BASE}/settings", json={"cost_includes_vat": False}).json()["code"] == "PROFESSION"
    assert client.get(f"{BASE}/settings").json()["code"] == "INV_SETUP"
    view = setup(client, store_name="مستودع الدمام")
    assert (view["store_name"], view["store_location"], view["cost_basis_locked"], view["row_version"]) == ("مستودع الدمام", None, False, 1)
    assert client.put(f"{BASE}/settings", json={"cost_includes_vat": True}).status_code == 409
    view = expect(client.put(f"{BASE}/settings", json={"cost_includes_vat": True, "expected_row_version": 1, "store_location": "حي الفيصلية"}))
    assert (view["cost_includes_vat"], view["store_location"], view["row_version"]) == (True, "حي الفيصلية", 2)
    summary = expect(client.get(f"{BASE}/summary"))
    assert summary["settings"]["store_name"] == "مستودع الدمام" and summary["attention"]["drafts"] == 0


def test_suppliers_reps_categories_and_items_carry_what_the_storekeeper_needs(keeper, other):
    client, _ = keeper
    setup(client)
    sup = supplier(client, cr_number="1010123456", phone="0112345678", note="يورّد الصباح")
    assert sup["same_vat_number"] == [] and sup["cr_number"] == "1010123456"
    twin = supplier(client, "النور للتجارة")
    assert [s["name"] for s in twin["same_vat_number"]] == ["مؤسسة النور"]
    assert client.post(f"{BASE}/suppliers", json={"name": "مؤسسه النور"}).json()["code"] == "INV_SUPPLIER_EXISTS"
    assert client.post(f"{BASE}/suppliers", json={"name": "س", "vat_number": "310000000000004"}).json()["code"] == "INV_VAT_NUMBER"
    # المندوبون: الافتراضي واحد، والجوال بشكله.
    ahmad = expect(client.post(f"{BASE}/suppliers/{sup['id']}/reps", json={"name": "أحمد", "mobile": "0501234567", "is_default": True}), 201)
    khalid = expect(client.post(f"{BASE}/suppliers/{sup['id']}/reps", json={"name": "خالد", "is_default": True}), 201)
    reps = expect(client.get(f"{BASE}/suppliers/{sup['id']}"))["reps"]
    assert [(r["name"], r["is_default"]) for r in reps] == [("خالد", True), ("أحمد", False)]
    assert client.post(f"{BASE}/suppliers/{sup['id']}/reps", json={"name": "سعد", "mobile": "12345"}).status_code == 422
    assert client.post(f"{BASE}/suppliers/{sup['id']}/reps", json={"name": "سعد", "mobile": "0599999999x"}).json()["code"] == "INV_PHONE"
    renamed = expect(client.patch(f"{BASE}/suppliers/{sup['id']}/reps/{khalid['id']}",
                                  json={"expected_row_version": khalid["row_version"], "name": "خالد العمري", "mobile": "0500000000"}))
    assert renamed["name"] == "خالد العمري"
    # التصنيفات والمنتجات: رقمٌ من العدّاد، وباركود فريد، وأقرب الأسماء معلومةً.
    drinks = expect(client.post(f"{BASE}/categories", json={"name": "مشروبات"}), 201)
    assert client.post(f"{BASE}/categories", json={"name": "مشروبات"}).json()["code"] == "INV_CATEGORY_EXISTS"
    water = item(client, "كرتونة ماء ٣٣٠ مل", category_id=drinks["id"], barcode="6281001234567", selling_price_halalas=2500,
                 reorder_level_milli=20000, target_level_milli=60000, preferred_supplier_id=sup["id"])
    assert (water["number"], water["code"], water["category"]["name"], water["barcode"]) == (1, "ص-00001", "مشروبات", "6281001234567")
    assert water["preferred_supplier"]["rep_name"] == "خالد العمري" and water["similar"] == []
    near = item(client, "ماء ٣٣٠ مل كرتونة")   # الكلمات نفسها بترتيبٍ آخر
    assert near["number"] == 2 and [s["name"] for s in near["similar"]] == ["كرتونة ماء ٣٣٠ مل"]
    assert client.post(f"{BASE}/items", json={"name": "ماء", "kind": "STOCK", "unit": "BOX", "price_halalas": 100, "barcode": "6281001234567"}).json()["code"] == "INV_BARCODE_EXISTS"
    assert client.post(f"{BASE}/items", json={"name": "ماء ٢", "kind": "STOCK", "unit": "BOX", "price_halalas": 100, "barcode": "12345678"}).status_code == 201
    assert client.post(f"{BASE}/items", json={"name": "شحن", "kind": "SERVICE", "unit": "CARTON", "price_halalas": 100}).json()["code"] == "INV_UNIT"
    assert client.post(f"{BASE}/items", json={"name": "دواء", "kind": "STOCK", "unit": "BOX", "price_halalas": 100, "vat_exemption_reason": "دواء"}).json()["code"] == "INV_EXEMPTION"
    assert client.patch(f"{BASE}/items/{water['id']}", json={"expected_row_version": water["row_version"], "target_level_milli": 10000}).json()["code"] == "INV_TARGET"
    patched = expect(client.patch(f"{BASE}/items/{water['id']}", json={"expected_row_version": water["row_version"], "barcode": None, "note": "رفّ 3"}))
    assert patched["barcode"] is None and patched["note"] == "رفّ 3" and patched["row_version"] == 2
    # البحث بالاسم أو الرمز أو الباركود، وكشف المنتجات وقيمة المخزون.
    found = expect(client.get(f"{BASE}/items/search", params={"q": "12345678"}))
    assert [i["name"] for i in found["items"]] == ["ماء ٢"] and found["create"] == {"name": "12345678"}
    found = expect(client.get(f"{BASE}/items/search", params={"q": "كرتونة ماء ٣٣٠ مل"}))
    assert found["create"] is None and found["items"][0]["code"] == "ص-00001"
    page = expect(client.get(f"{BASE}/items", params={"filter": "low", "size": 4}))
    assert [i["name"] for i in page["items"]] == ["كرتونة ماء ٣٣٠ مل"] and page["stock_value_halalas"] == 0
    assert expect(client.get(f"{BASE}/items", params={"category_id": drinks["id"]}))["total"] == 1
    # عزل الحساب الآخر: لا يرى شيئاً، ومنتج غيره 404.
    other_client, _ = other
    setup(other_client)
    assert expect(other_client.get(f"{BASE}/items"))["total"] == 0
    assert other_client.get(f"{BASE}/items/{water['id']}").status_code == 404
    assert other_client.patch(f"{BASE}/items/{water['id']}", json={"expected_row_version": 2, "name": "x"}).status_code == 404


# ── فاتورة الشراء: التنبيهات والإقرار والتسجيل ──────────────────────────
def test_a_purchase_is_posted_with_every_flag_acknowledged_and_the_row_version_seen(keeper, today):
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    assert p["missing"] == [] and p["totals"] == {"net": 100000, "vat": 15000, "gross": 115000}
    p = expect(client.patch(f"{BASE}/purchases/{p['id']}", json={"expected_row_version": p["row_version"], "printed_total_halalas": 116000,
                                                                "rep_id": rep["id"], "delivery_note_no": "DN-7", "received_on": today}))
    assert p["rep"]["name"] == "أحمد" and p["delivery_note_no"] == "DN-7"
    p = expect(client.patch(f"{BASE}/purchases/{p['id']}/lines/1", json={"expected_row_version": p["row_version"], "received_quantity_milli": 8000}))
    flags = flags_of(client, p)
    keys = sorted(f["key"] for f in flags["flags"])
    assert keys == ["SHORT_DELIVERY:1", "TOTAL_MISMATCH"]
    short = next(f for f in flags["flags"] if f["code"] == "SHORT_DELIVERY")
    assert short["text"].startswith(f"يا ⁨{NAME}⁩، وصل من «كرتونة ماء ٣٣٠ مل» في السطر 1 8 كرتون من 10 كرتون")
    assert flags["ai"] == [] and len(flags["digest"]) == 64
    # الإقرار الناقص 409 بالتنبيهات الحالية، والصفّ القديم 409، ثم التسجيل.
    refused = client.post(f"{BASE}/purchases/{p['id']}/post", json={"expected_row_version": p["row_version"], "acknowledged": ["TOTAL_MISMATCH"]})
    assert refused.status_code == 409 and refused.json()["code"] == "FLAGS_CHANGED"
    assert sorted(f["key"] for f in refused.json()["flags"]) == keys
    stale = client.post(f"{BASE}/purchases/{p['id']}/post", json={"expected_row_version": p["row_version"] - 1, "acknowledged": keys})
    assert stale.status_code == 409 and stale.json()["code"] == "STALE"
    posted = post(client, p)
    assert (posted["status"], posted["number"], posted["label"], posted["rep"]["mobile"]) == ("POSTED", 1, "ش-0001", "0501234567")
    assert sorted(f["key"] for f in posted["acknowledged"]) == keys
    assert posted["lines"][0]["remaining_milli"] == 10000 and posted["returnable"]
    assert client.patch(f"{BASE}/purchases/{p['id']}", json={"expected_row_version": posted["row_version"], "note": "x"}).json()["code"] == "INV_POSTED"
    assert client.post(f"{BASE}/purchases/{p['id']}/discard", json={"expected_row_version": posted["row_version"]}).json()["code"] == "INV_POSTED"
    detail = expect(client.get(f"{BASE}/items/{water['id']}"))
    assert (detail["on_hand_milli"], detail["stock_value_halalas"], detail["avg_cost_halalas"]) == (10000, 100000, 10000)
    assert detail["recent_purchases"][0]["document"] == "ش-0001" and detail["suggested_order_milli"] is None
    movements = expect(client.get(f"{BASE}/items/{water['id']}/movements"))
    assert (movements["items"][0]["kind"], movements["items"][0]["in_milli"], movements["items"][0]["document"]) == ("PURCHASE_IN", 10000, "ش-0001")
    # القوائم والمصروفات والملخّص.
    listed = expect(client.get(f"{BASE}/purchases", params={"status": "posted", "q": "النور"}))
    assert listed["total"] == 1 and listed["items"][0]["label"] == "ش-0001"
    month = today[:7]
    expenses = expect(client.get(f"{BASE}/expenses", params={"from": f"{month}-01", "to": today}))
    assert expenses["totals"]["purchases"] == {"net": 100000, "vat": 15000, "gross": 115000}
    assert expenses["entries"]["items"][0]["document"] == "ش-0001"
    assert client.get(f"{BASE}/expenses", params={"from": today, "to": f"{month}-01"}).json()["code"] == "INV_PERIOD"
    summary = expect(client.get(f"{BASE}/summary"))
    assert summary["month_totals"]["net"]["gross"] == 115000 and summary["stock_value"] == 100000
    # نقص التسليم يبقى في «يحتاج انتباهك» حتى يُسجَّل مرتجعٌ بما لم يصل، ولا يكفي مرتجعٌ بأقلّ منه.
    assert summary["attention"]["short_delivery"] == 1
    for quantity, waiting in ((1000, 1), (1000, 0)):
        r = expect(client.post(f"{BASE}/returns", json={"purchase_id": p["id"]}), 201)
        r = expect(client.put(f"{BASE}/returns/{r['id']}/lines/1", json={"expected_row_version": r["row_version"], "quantity_milli": quantity}))
        r = expect(client.patch(f"{BASE}/returns/{r['id']}", json={"expected_row_version": r["row_version"], "reason": "SHORT_DELIVERY"}))
        keys = [f["key"] for f in expect(client.get(f"{BASE}/returns/{r['id']}/flags"))["flags"]]
        expect(client.post(f"{BASE}/returns/{r['id']}/post", json={"expected_row_version": r["row_version"], "acknowledged": keys}))
        assert expect(client.get(f"{BASE}/summary"))["attention"]["short_delivery"] == waiting


def test_a_second_tab_posting_the_same_draft_is_refused_and_the_draft_can_be_discarded(keeper, today):
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    fresh = expect(client.get(f"{BASE}/purchases/{p['id']}"))
    assert post(client, fresh)["status"] == "POSTED"
    again = client.post(f"{BASE}/purchases/{p['id']}/post", json={"expected_row_version": fresh["row_version"], "acknowledged": []})
    assert again.status_code == 409 and again.json()["code"] == "INV_POSTED"
    # مسودةٌ أخرى: سطرٌ يُحذف ثم تُنبذ المسودة كلّها.
    d = draft(client, sup, no="INV-2", day=today, printed=1000)
    d = line(client, d, rice, 2500, 900)
    assert d["lines"][0]["item"]["unit_name"] == "كيلوغرام"
    d = expect(client.post(f"{BASE}/purchases/{d['id']}/lines/1/remove", json={"expected_row_version": d["row_version"]}))
    assert d["lines"] == [] and "lines" in d["missing"]
    assert client.post(f"{BASE}/purchases/{d['id']}/discard", json={"expected_row_version": d["row_version"]}).status_code == 204
    assert client.get(f"{BASE}/purchases/{d['id']}").status_code == 404


# ── مراجعة سيمبول عبر المسار المشترك ────────────────────────────────────
def test_symbols_review_sends_the_minimum_and_its_flag_gates_the_posting(keeper, owner, gateway, today):
    client, user_id = keeper
    sup, rep, water, rice, p = _scene(client, today)
    near = item(client, "مياه 330 كرتون")
    p = line(client, expect(client.get(f"{BASE}/purchases/{p['id']}")), near, 5000, 1800)
    # اسمٌ كتبه المورّد برقم جوال: يُرسَل بعد الإخفاء.
    chip = item(client, "شريحة بيانات 0559876543", price=2500)
    p = line(client, expect(client.get(f"{BASE}/purchases/{p['id']}")), chip, 1000, 2500)
    gateway.queue(review_reply(flag(check="SAME_AS_EXISTING_ITEM", field="item", line=2,
                                    reason="«مياه 330 كرتون» يبدو المنتج نفسه «كرتونة ماء ٣٣٠ مل» الموجود.",
                                    suggestion="استعمل المنتج الموجود بدلاً منه.")))
    body = expect(review(client, "PURCHASE", p["id"], p["row_version"]))
    assert body["review"]["status"] == "DONE" and len(body["flags"]) == 1
    shown = body["flags"][0]
    assert shown["headline"].startswith(f"يا ⁨{NAME}⁩، ") and shown["line"] == 2
    assert shown["evidence"][0] == "الصنف الجديد: مياه 330 كرتون (كرتون)"
    # ما غادر: الأسطر بأسماء المنتجات ووحداتها وأسعارها، والمرشَّح، بلا اسمٍ ولا مورّد ولا رقم فاتورة.
    (call,) = gateway.calls
    sent = json.loads(call.user.split(">", 1)[1].rsplit("<", 1)[0])
    assert sent["lines"][1]["new_item"] and sent["lines"][1]["candidates"][0]["item"] == "كرتونة ماء ٣٣٠ مل"
    assert sent["lines"][0]["unit_price"] == "100.00" and sent["lines"][0]["history"]["count"] == 0
    assert sent["lines"][2]["item"] == "شريحة بيانات [رقم]"
    for forbidden in (NAME, "مؤسسة النور", "INV-1001", "300000000000003", today, "0559876543", "0501234567"):
        assert forbidden not in call.user
    assert _keys(sent, set()) <= set(PAYLOAD_KEYS)
    # الملاحظة التي لم يُبتّ فيها تحجز التسجيل (409 FLAGS_UNDECIDED)، و«تابع رغم ذلك» يفتحه.
    fresh = expect(client.get(f"{BASE}/purchases/{p['id']}"))
    blocked = client.post(f"{BASE}/purchases/{p['id']}/post", json={"expected_row_version": fresh["row_version"],
                                                                   "acknowledged": [f["key"] for f in flags_of(client, fresh)["flags"]]})
    assert blocked.status_code == 409 and blocked.json()["code"] == "FLAGS_UNDECIDED" and len(blocked.json()["flags"]) == 1
    stored = flags_of(client, fresh)
    assert stored["ai"][0]["id"] == shown["id"] and stored["ai"][0]["decision"] is None
    assert expect(client.post(f"/api/ai/flags/{shown['id']}/decision", json={"choice": "PROCEED", "digest": body["subject"]["digest"]}))["decision"] == "PROCEED"
    posted = post(client, expect(client.get(f"{BASE}/purchases/{p['id']}")))
    assert posted["status"] == "POSTED"
    with owner.cursor() as cursor:
        cursor.execute("SELECT closed_at IS NOT NULL FROM ai_flags WHERE id = %s", (shown["id"],))
        assert cursor.fetchone()[0]
    # الفحص الحتمي قبل الاستدعاء: مسودةٌ بلا أسطر 422، وفاتورةٌ مسجّلة 404.
    empty = draft(client, sup, no="INV-3", day=today, printed=1000)
    assert review(client, "PURCHASE", empty["id"], empty["row_version"]).status_code == 422
    assert review(client, "PURCHASE", p["id"], posted["row_version"]).status_code == 404
    assert len(gateway.calls) == 1


def test_the_review_loader_sends_exactly_the_declared_keys(owner, server):
    """ما يحمّله المحمّل فعلاً للفاتورة والمرتجع: مفاتيحهما معاً هي المعلَنة، بلا مفتاح هوية."""
    from eyework.tests.architecture.test_rules import _identity_key

    user_id = add_user(owner, KEEPER, profession="STOREKEEPER")
    with owner.cursor() as cursor:
        purchase = inventory.FEATURE.fixture(cursor, user_id)
    db = server.state.db
    with db.session(user_id) as cursor:
        purchase_snapshot = inventory.FEATURE.load(cursor, user_id, "PURCHASE", purchase, None)
        cursor.execute("INSERT INTO inv_items (user_id, name, kind, unit, price_halalas) VALUES (ew_current_user(), 'أرز', 'STOCK', 'KG', 900) RETURNING id")
    # مرتجعٌ من فاتورةٍ مسجّلة، بدور التطبيق وهوية صاحبه.
    with db.session(user_id) as cursor:
        cursor.execute("SELECT ew_inv_post_purchase(%s, (SELECT row_version FROM inv_purchases WHERE id = %s), ew_inv_flag_keys(%s, NULL))",
                       (purchase, purchase, purchase))
        cursor.execute("INSERT INTO inv_returns (user_id, purchase_id, reason) VALUES (ew_current_user(), %s, 'EXCESS') RETURNING id", (purchase,))
        return_id = cursor.fetchone()["id"]
        cursor.execute("INSERT INTO inv_return_lines (return_id, user_id, line_no, quantity_milli) VALUES (%s, ew_current_user(), 1, 2000)", (return_id,))
    with db.session(user_id) as cursor:
        return_snapshot = inventory.FEATURE.load(cursor, user_id, "RETURN", return_id, None)
    found = _keys(purchase_snapshot.payload, set()) | _keys(return_snapshot.payload, set())
    assert found == set(inventory.FEATURE.payload_keys), found ^ set(inventory.FEATURE.payload_keys)
    assert not [key for key in found if _identity_key(key)]
    assert purchase_snapshot.payload["lines"][0]["candidates"][0]["item"] == "كرتونة ماء ٣٣٠ مل"
    assert return_snapshot.payload["reason"] == "EXCESS" and return_snapshot.payload["lines"][0]["quantity"] == "2"


# ── المرتجع والقيد العكسي والسندات ──────────────────────────────────────
def test_a_return_takes_its_share_and_waits_for_the_credit_note(keeper, today):
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    posted = post(client, expect(client.get(f"{BASE}/purchases/{p['id']}")))
    r = expect(client.post(f"{BASE}/returns", json={"purchase_id": p["id"], "rep_id": rep["id"]}), 201)
    assert (r["status"], r["return_date"], r["purchase"]["label"], r["credit_note_due"][:4]) == ("DRAFT", today, "ش-0001", today[:4])
    assert r["lines"][0]["remaining_milli"] == 10000 and r["lines"][0]["quantity_milli"] == 0
    r = expect(client.put(f"{BASE}/returns/{r['id']}/lines/1", json={"expected_row_version": r["row_version"], "quantity_milli": 3000}))
    assert r["lines"][0]["quantity_milli"] == 3000
    # المسودة تعرض قيمة التسجيل نفسها: حصّةٌ من صافي السطر وضريبته (لا الكمية × السعر قبل الخصم).
    assert r["totals"] == {"net": 30000, "vat": 4500, "gross": 34500}
    too_many = client.put(f"{BASE}/returns/{r['id']}/lines/1", json={"expected_row_version": r["row_version"], "quantity_milli": 11000})
    assert too_many.json()["code"] == "INV_RETURN_QTY"
    no_reason = client.post(f"{BASE}/returns/{r['id']}/post", json={"expected_row_version": r["row_version"], "acknowledged": []})
    assert no_reason.json()["code"] == "INV_RETURN_REASON"
    # تاريخٌ لا يُكتب على مستند (والموعد بعده في سنةٍ لا توجد) حقلٌ خاطئ، لا خطأ خادم.
    far = client.patch(f"{BASE}/returns/{r['id']}", json={"expected_row_version": r["row_version"], "return_date": "9999-12-31"})
    assert (far.status_code, far.json()["code"], far.json()["field"]) == (422, "INV_DATE", "return_date")
    r = expect(client.patch(f"{BASE}/returns/{r['id']}", json={"expected_row_version": r["row_version"], "reason": "SHORT_DELIVERY"}))
    keys = [f["key"] for f in expect(client.get(f"{BASE}/returns/{r['id']}/flags"))["flags"]]
    r = expect(client.post(f"{BASE}/returns/{r['id']}/post", json={"expected_row_version": r["row_version"], "acknowledged": keys}))
    assert (r["status"], r["label"], r["totals"], r["rep"]["name"]) == ("POSTED", "ر-0001", {"net": 30000, "vat": 4500, "gross": 34500}, "أحمد")
    waiting = expect(client.get(f"{BASE}/returns", params={"awaiting_credit_note": True}))
    assert waiting["total"] == 1 and waiting["items"][0]["credit_note_overdue"] is False
    r = expect(client.put(f"{BASE}/returns/{r['id']}/credit-note", json={"expected_row_version": r["row_version"], "number": "CN-9", "date": today}))
    assert r["credit_note"] == {"number": "CN-9", "date": today}
    assert client.put(f"{BASE}/returns/{r['id']}/credit-note", json={"expected_row_version": r["row_version"], "number": "CN-10", "date": today}).json()["code"] == "INV_FINAL"
    assert expect(client.get(f"{BASE}/returns", params={"awaiting_credit_note": True}))["total"] == 0
    after = expect(client.get(f"{BASE}/purchases/{p['id']}"))
    assert after["lines"][0]["remaining_milli"] == 7000 and after["returns"][0]["label"] == "ر-0001"
    assert client.post(f"{BASE}/purchases/{p['id']}/reverse", json={"expected_row_version": after["row_version"], "reason": "DUPLICATE"}).json()["code"] == "INV_REVERSAL_RETURNS"
    assert expect(client.get(f"{BASE}/summary"))["attention"]["awaiting_credit_note"] == 0
    # «من أيّ فاتورة؟» تعرض ما بقي فيه ما يُرجَع: بعد إرجاع الباقي تغيب الفاتورة.
    returnable = lambda: [row["id"] for row in expect(client.get(f"{BASE}/purchases", params={"status": "returnable"}))["items"]]
    assert returnable() == [p["id"]]
    r = expect(client.post(f"{BASE}/returns", json={"purchase_id": p["id"]}), 201)
    r = expect(client.put(f"{BASE}/returns/{r['id']}/lines/1", json={"expected_row_version": r["row_version"], "quantity_milli": 7000}))
    r = expect(client.patch(f"{BASE}/returns/{r['id']}", json={"expected_row_version": r["row_version"], "reason": "EXCESS"}))
    keys = [f["key"] for f in expect(client.get(f"{BASE}/returns/{r['id']}/flags"))["flags"]]
    expect(client.post(f"{BASE}/returns/{r['id']}/post", json={"expected_row_version": r["row_version"], "acknowledged": keys}))
    assert returnable() == [] and [row["id"] for row in expect(client.get(f"{BASE}/purchases", params={"status": "posted"}))["items"]] == [p["id"]]


def test_vouchers_are_idempotent_and_a_reversal_takes_the_stock_out(keeper, today):
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    token = str(uuid4())
    body = {"client_token": token, "item_id": rice["id"], "quantity_milli": 20500, "unit_cost_halalas": 900, "occurred_on": today}
    first = expect(client.post(f"{BASE}/stock/opening", json=body), 201)
    again = expect(client.post(f"{BASE}/stock/opening", json=body), 200)
    assert (first["label"], first["replayed"], again["replayed"], again["number"]) == ("س-0001", False, True, 1)
    assert client.post(f"{BASE}/stock/issue", json={"client_token": str(uuid4()), "item_id": rice["id"], "quantity_milli": 30000,
                                                    "reason": "SALE", "occurred_on": today}).json()["code"] == "INV_STOCK"
    counted = client.post(f"{BASE}/stock/count", json={"client_token": str(uuid4()), "item_id": rice["id"], "counted_milli": 20000,
                                                       "expected_on_hand_milli": 20500, "occurred_on": today})
    assert counted.json()["code"] == "INV_COUNT_REASON"
    counted = expect(client.post(f"{BASE}/stock/count", json={"client_token": str(uuid4()), "item_id": rice["id"], "counted_milli": 20000,
                                                              "expected_on_hand_milli": 20500, "reason": "DAMAGE", "occurred_on": today}), 201)
    assert counted["on_hand_before_milli"] == 20500 and counted["reason"] == "DAMAGE"
    assert expect(client.get(f"{BASE}/vouchers"))["total"] == 2
    posted = post(client, expect(client.get(f"{BASE}/purchases/{p['id']}")))
    reversed_ = expect(client.post(f"{BASE}/purchases/{p['id']}/reverse", json={"expected_row_version": posted["row_version"],
                                                                                "reason": "OTHER", "note": "سُجّلت لمورّدٍ آخر"}))
    assert reversed_["status"] == "REVERSED" and reversed_["reversal"]["label"] == "ع-0001"
    assert expect(client.get(f"{BASE}/items/{water['id']}"))["on_hand_milli"] == 0
    assert expect(client.get(f"{BASE}/tools/vat", params={"amount_halalas": 11500, "basis": "gross"})) == {"net_halalas": 10000, "vat_halalas": 1500, "gross_halalas": 11500}


# ── جلسة الجرد ──────────────────────────────────────────────────────────
def test_a_count_session_is_counted_blind_refreshed_and_posted(keeper, today):
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    post(client, expect(client.get(f"{BASE}/purchases/{p['id']}")))
    expect(client.post(f"{BASE}/stock/opening", json={"client_token": str(uuid4()), "item_id": rice["id"], "quantity_milli": 20500,
                                                      "unit_cost_halalas": 900, "occurred_on": today}), 201)
    token = str(uuid4())
    session = expect(client.post(f"{BASE}/counts", json={"client_token": token, "scope": "ALL"}), 201)
    assert (session["label"], session["items_total"], session["blind"], session["last_purchase_label"]) == ("ج-0001", 2, True, "ش-0001")
    # عدٌّ مغلق: الرصيد مخفيٌّ حتى يُعدّ، في السطر وفي منتَجه.
    assert [(line["book_milli"], line["item"]["on_hand_milli"]) for line in session["lines"]] == [(None, None), (None, None)]
    assert expect(client.post(f"{BASE}/counts", json={"client_token": token, "scope": "ALL"}), 200)["replayed"]
    assert client.post(f"{BASE}/counts", json={"client_token": str(uuid4()), "scope": "ALL"}).json()["code"] == "INV_COUNT_OPEN"
    sid = session["id"]
    put = f"{BASE}/counts/{sid}/lines"
    # العدّ المغلق: أوّل حفظٍ بلا سببٍ يكشف الرصيد الدفتري والفرق؛ والسبب واجبٌ قبل الترحيل لا قبل الكشف.
    session = expect(client.put(f"{put}/{water['id']}", json={"expected_row_version": session["row_version"], "counted_milli": 8000}))
    water_line = next(line for line in session["lines"] if line["item"]["id"] == water["id"])
    assert (water_line["book_milli"], water_line["difference_milli"], water_line["reason"], session["counted_so_far"]) == (10000, -2000, None, 1)
    unreasoned = client.post(f"{BASE}/counts/{sid}/post", json={"expected_row_version": session["row_version"], "occurred_on": today})
    assert unreasoned.json()["code"] == "INV_COUNT_REASON"
    wrong = client.put(f"{put}/{water['id']}", json={"expected_row_version": session["row_version"], "counted_milli": 8000, "reason": "FOUND"})
    assert wrong.json()["code"] == "INV_COUNT_REASON"
    session = expect(client.put(f"{put}/{water['id']}", json={"expected_row_version": session["row_version"], "counted_milli": 8000, "reason": "DAMAGE"}))
    water_line = next(line for line in session["lines"] if line["item"]["id"] == water["id"])
    assert (water_line["book_milli"], water_line["difference_milli"], water_line["reason"]) == (10000, -2000, "DAMAGE")
    session = expect(client.put(f"{put}/{rice['id']}", json={"expected_row_version": session["row_version"], "counted_milli": 20500}))
    # رصيدٌ تحرّك بعد اللقطة: الترحيل يتوقّف حتى يُحدَّث ويُعاد العدّ.
    expect(client.post(f"{BASE}/stock/issue", json={"client_token": str(uuid4()), "item_id": rice["id"], "quantity_milli": 500,
                                                    "reason": "SALE", "occurred_on": today}), 201)
    stale = client.post(f"{BASE}/counts/{sid}/post", json={"expected_row_version": session["row_version"], "occurred_on": today})
    assert stale.json()["code"] == "INV_COUNT_STALE"
    session = expect(client.post(f"{BASE}/counts/{sid}/refresh"))
    rice_line = next(line for line in session["lines"] if line["item"]["id"] == rice["id"])
    assert session["refreshed"] == 1 and rice_line["counted_milli"] is None
    session = expect(client.post(f"{BASE}/counts/{sid}/post", json={"expected_row_version": session["row_version"], "occurred_on": today}))
    assert (session["status"], session["items_counted"], session["items_matched"]) == ("POSTED", 1, 0)
    assert all(line["book_milli"] is not None for line in session["lines"])
    assert expect(client.get(f"{BASE}/items/{water['id']}"))["on_hand_milli"] == 8000
    listed = expect(client.get(f"{BASE}/counts"))
    assert listed["items"][0]["label"] == "ج-0001"
    # جلسةٌ ثانية على منتجاتٍ مختارة، يُضاف إليها منتجٌ ثم تُلغى وتحتفظ برقمها.
    second = expect(client.post(f"{BASE}/counts", json={"client_token": str(uuid4()), "scope": "SELECTED", "item_ids": [water["id"]], "blind": False}), 201)
    assert second["lines"][0]["book_milli"] == 8000
    second = expect(client.post(f"{BASE}/counts/{second['id']}/items", json={"item_id": rice["id"]}), 201)
    assert second["items_total"] == 2 and second["lines"][1]["added_during_count"]
    cancelled = expect(client.post(f"{BASE}/counts/{second['id']}/cancel", json={"expected_row_version": second["row_version"]}))
    assert (cancelled["status"], cancelled["label"]) == ("CANCELLED", "ج-0002")
    assert client.put(f"{BASE}/counts/{second['id']}/lines/{water['id']}", json={"expected_row_version": cancelled["row_version"], "counted_milli": 1000}).json()["code"] == "INV_COUNT_CLOSED"
    assert expect(client.get(f"{BASE}/summary"))["attention"]["open_count"] is None


def test_the_choices_carry_the_inventory_vocabulary(server, browser):
    client = browser()
    choices = expect(client.get("/api/choices"))["inventory"]
    assert [u["code"] for u in choices["units"]][:3] == ["PIECE", "BOX", "CARTON"]
    assert choices["document_prefixes"]["ITEM"] == "ص" and choices["page_sizes"] == [2, 3, 4, 5, 10, 20]
    assert [r["code"] for r in choices["count_reasons"]["SURPLUS"]] == ["FOUND", "RECORDING_ERROR", "OTHER"]


def test_a_vat_inclusive_draft_offers_the_price_rounded_like_the_calculator(keeper, today):
    """45.50 قبل الضريبة ضريبتها 6.825: نصفٌ إلى أعلى ← 52.33 في المنتقي وفي حاسبة الضريبة معاً."""
    client, _ = keeper
    setup(client)
    water = item(client, "كرتونة ماء ٣٣٠ مل", price=4550)
    p = draft(client, supplier(client), day=today, prices_include_vat=True)
    found = expect(client.get(f"{BASE}/items/search", params={"q": "كرتونة", "purchase_id": p["id"]}))
    assert [(i["id"], i["price_entry_halalas"]) for i in found["items"]] == [(water["id"], 5233)]
    assert expect(client.get(f"{BASE}/tools/vat", params={"amount_halalas": 4550}))["gross_halalas"] == 5233


def test_the_assistant_reads_only_the_keepers_own_inventory_screens(keeper, other, today):
    """شاشة منتجٍ أو فاتورةٍ أو جردٍ لغير صاحبها، أو بمعرّفٍ لا يوجد: 404 بنصّ الشاشة لا بنصّ الحملة."""
    client, _ = keeper
    sup, rep, water, rice, p = _scene(client, today)
    ask = {"ready_question": 0}
    assert client.post("/api/ai/assistant", json={"screen": {"kind": "INVENTORY_ITEM", "id": water["id"]}, **ask}).status_code == 200
    stranger, _ = other
    setup(stranger)
    for kind, screen_id in (("INVENTORY_ITEM", water["id"]), ("INVENTORY_PURCHASE", p["id"]), ("INVENTORY_COUNT", str(uuid4()))):
        refused = stranger.post("/api/ai/assistant", json={"screen": {"kind": kind, "id": screen_id}, **ask})
        assert (refused.status_code, refused.json()["detail"]) == (404, NO_SCREEN), kind


@pytest.mark.parametrize(("body", "code"), [
    ({"name": "مؤسسة النور", "vat_number": "30000000000003"}, "INV_VAT_NUMBER"),
    ({"name": "مؤسسة النور", "cr_number": "101234567"}, "INV_CR_NUMBER"),
    ({"name": "مؤسسة النور", "phone": "011234567"}, "INV_PHONE"),
    ({"name": "م" * 61}, "INV_NAME"),
])
def test_a_wrongly_sized_supplier_field_is_named_by_its_own_message(keeper, body, code):
    """خانةٌ ناقصة أو زائدة تعود برمز حقلها ورسالته من القاعدة، لا «قيمةٌ غير صالحة» عامّة."""
    client, _ = keeper
    setup(client)
    answer = client.post(f"{BASE}/suppliers", json=body)
    assert (answer.status_code, answer.json()["code"]) == (422, code)
