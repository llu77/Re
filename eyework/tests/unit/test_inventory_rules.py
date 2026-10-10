"""
قواعد المخزون النقية ونصوص تنبيهاته وقائمة فحوصه
================================================
ما يُصاغ ويُحسب بلا قاعدة: أرقام المستندات، والمبالغ والكميات بكلماتها، ومهلة
الإشعار الدائن، والمقترح طلبه، وحاسبة الضريبة بتقريب القاعدة، ونصوص التنبيهات
باسم صاحب الحساب أو بدونه، وموضوع المراجعة بمفاتيحه المعلَنة وحدها.
"""

from __future__ import annotations

import datetime

import pytest

from eyework import inventory_flags, inventory_prompt, inventory_rules as rules
from eyework.reviewer_prompt import call


def test_document_labels_and_item_codes_are_prefixed_and_padded():
    assert rules.document_label("PURCHASE", 7) == "ش-0007"
    assert rules.document_label("RETURN", 3) == "ر-0003"
    assert rules.document_label("REVERSAL", 1) == "ع-0001"
    assert rules.voucher_label(12) == "س-0012"
    assert rules.count_label(4) == "ج-0004"
    assert rules.item_code(12) == "ص-00012" and rules.item_code(4999) == "ص-04999"


def test_money_and_quantities_read_as_the_storekeeper_writes_them():
    assert rules.halalas_words(115000) == "1,150.00 ر.س"
    assert rules.halalas_words(-250) == "−2.50 ر.س"
    assert rules.quantity_words(12000, "CARTON") == "12 كرتون"
    assert rules.quantity_words(2500, "KG") == "2.5 كيلوغرام"
    assert rules.quantity_words(1250000, "LITRE") == "1,250 لتر"
    assert rules.normalise_text("  كرتونة   ماء ") == "كرتونة ماء"
    assert rules.normalise_digits("٣٠٠٠٠٠٠٠٠٠٠٠٠٠٣") == "300000000000003"


def test_the_credit_note_is_due_on_the_fifteenth_of_the_following_month():
    assert rules.credit_note_due(datetime.date(2026, 10, 9)) == datetime.date(2026, 11, 15)
    assert rules.credit_note_due(datetime.date(2026, 12, 31)) == datetime.date(2027, 1, 15)


def test_the_order_suggestion_and_the_reorder_level_helper_suggest_and_never_decide():
    assert rules.suggested_order(15000, 20000, 60000) == 45000
    assert rules.suggested_order(25000, 20000, 60000) is None          # فوق الحدّ
    assert rules.suggested_order(15000, 20000, None) is None           # بلا مستهدف
    assert rules.suggested_order(15000, None, 60000) is None
    assert rules.reorder_suggestion(90000, 5, "CARTON") == 21000       # 1000/يوم × 21 يوماً
    assert rules.reorder_suggestion(90000, 2, "CARTON") is None        # أقلّ من ثلاث حركات
    assert rules.reorder_suggestion(0, 5, "CARTON") is None
    assert rules.reorder_suggestion(4500, 4, "KG") == 1050             # بالكسور للوزن


@pytest.mark.parametrize("amount, basis, category, expected", [
    (10000, "net", "S", (10000, 1500, 11500)),
    (11500, "gross", "S", (10000, 1500, 11500)),
    (1, "net", "S", (1, 0, 1)),
    (3, "net", "S", (3, 0, 3)),                 # 0.45 ← صفر
    (4, "net", "S", (4, 1, 5)),                 # 0.6 ← واحد
    (30, "net", "S", (30, 5, 35)),              # 4.5 ← خمسة (التقريب إلى الزوجي يعطي أربعة)
    (4550, "net", "S", (4550, 683, 5233)),      # 682.5 ← 683
    (10000, "net", "Z", (10000, 0, 10000)),
    (10000, "gross", "O", (10000, 0, 10000)),
])
def test_the_vat_calculator_rounds_half_up_like_the_database(amount, basis, category, expected):
    assert rules.vat_split(amount, basis, category) == expected


def test_flag_texts_carry_the_name_in_isolates_or_start_at_the_subject():
    line = {"item": {"name": "أرز بسمتي", "unit": "KG"}}
    text = inventory_flags.render("PRICE_FAR_FROM_HISTORY", 2, {"price": 9000, "reference": 900, "basis": "HISTORY", "extra_zero": True},
                                  "سارة", line=line)
    assert text == "يا ⁨سارة⁩، سعر «أرز بسمتي» في السطر 2 هو 90.00 ر.س للكيلوغرام، ووسيط آخر مشترياته 9.00 ر.س. ربما زِيد صفر."
    bare = inventory_flags.render("TOTAL_MISMATCH", None, {"computed": 115000, "printed": 116000}, None)
    assert bare.startswith("إجمالي الأسطر المحسوب 1,150.00 ر.س والمكتوب على فاتورة المورّد 1,160.00 ر.س، والفرق 10.00 ر.س.")
    short = inventory_flags.render("SHORT_DELIVERY", 1, {"invoiced": 10000, "received": 8000}, "سارة",
                                   line={"item": {"name": "ماء", "unit": "CARTON"}})
    assert "وصل من «ماء» في السطر 1 8 كرتون من 10 كرتون" in short
    duplicate = inventory_flags.render("DUPLICATE_SUPPLIER_INVOICE", None,
                                       {"number": 7, "invoice_date": "2026-10-01", "supplier_invoice_no": "A-1"}, "سارة")
    assert "ش-0007 بتاريخ 1/10/2026" in duplicate
    assert inventory_flags.flag_key("ZERO_PRICE", 3) == "ZERO_PRICE:3" and inventory_flags.flag_key("NO_VAT_CHARGED", None) == "NO_VAT_CHARGED"
    assert inventory_flags.LEVELS["DUPLICATE_SUPPLIER_INVOICE"] == "high"
    for code in inventory_flags.LEVELS:
        assert isinstance(inventory_flags.render(code, 1, {"number": 1, "invoice_date": "2026-01-01", "total": 1, "computed": 1,
                                                           "printed": 2, "days": 1, "price": 1, "reference": 1, "quantity": 1,
                                                           "category": "S", "usual": "Z", "invoiced": 2, "received": 1},
                                                 None, line=line), str)


def test_the_review_catalogue_sends_only_the_declared_keys_and_no_identity():
    lines = [{"line_no": 1, "item_name": "أرز بسمتي", "unit": "KG", "kind": "STOCK", "quantity_milli": 25000,
              "unit_net_halalas": 9000, "vat_category": "S", "history_count": 0, "median_price_halalas": None,
              "median_quantity_milli": None, "candidates": [(1, "أرز", "KG")]},
             {"line_no": 2, "item_name": "ماء", "unit": "CARTON", "kind": "STOCK", "quantity_milli": 10000,
              "unit_net_halalas": 4550, "vat_category": "S", "history_count": 4, "median_price_halalas": 4400,
              "median_quantity_milli": 12000, "candidates": [(1, "x", "BOX")]}]
    payload = inventory_prompt.purchase_payload(lines)
    assert payload["lines"][0]["quantity"] == "25" and payload["lines"][0]["unit_price"] == "90.00"
    assert payload["lines"][0]["new_item"] and payload["lines"][0]["candidates"] == [{"ref": 1, "item": "أرز", "unit": "KG"}]
    assert not payload["lines"][1]["new_item"] and payload["lines"][1]["candidates"] == []
    assert payload["lines"][1]["history"] == {"count": 4, "median_price": "44.00", "median_quantity": "12"}
    returned = inventory_prompt.return_payload("EXPIRED", [{"line_no": 1, "item_name": "مطرقة", "unit": "PIECE", "kind": "STOCK",
                                                           "quantity_milli": 1000, "bought_milli": 3000, "days_since_purchase": 400}])
    assert returned["lines"][0]["quantity_bought"] == "3" and returned["reason"] == "EXPIRED"

    def keys(value, found):
        if isinstance(value, dict):
            for key, inner in value.items():
                found.add(key)
                keys(inner, found)
        elif isinstance(value, list):
            for inner in value:
                keys(inner, found)
        return found

    assert keys(payload, set()) | keys(returned, set()) == set(inventory_prompt.PAYLOAD_KEYS)
    catalogue = inventory_prompt.CATALOGUE
    assert catalogue.codes == ("PRICE_IMPLAUSIBLE", "REASON_IMPLAUSIBLE", "SAME_AS_EXISTING_ITEM", "UNIT_MISMATCH")
    assert catalogue.check("REASON_IMPLAUSIBLE").applies_to == frozenset({"RETURN"}) and not catalogue.check("REASON_IMPLAUSIBLE").line_level
    evidence = catalogue.check("SAME_AS_EXISTING_ITEM").evidence(payload, 1)
    assert evidence == ("الصنف الجديد: أرز بسمتي (كيلوغرام)", "أصنافٌ موجودة بأسماءٍ قريبة: «أرز»")
    assert catalogue.check("PRICE_IMPLAUSIBLE").evidence(payload, 2)[2] == "آخر مشترياته: 4، وسيط سعرها 44.00 ر.س"
    assert catalogue.check("REASON_IMPLAUSIBLE").evidence(returned, None)[0] == "سبب الإرجاع: EXPIRED"
    request = call(catalogue, "PURCHASE", payload)
    assert request.feature == "STOCK_REVIEW" and "أرز بسمتي" in request.user
    assert set(request.schema["properties"]["flags"]["items"]["properties"]["check"]["enum"]) == set(catalogue.codes)


def test_the_choices_name_every_unit_reason_and_cap():
    choices = rules.choices()
    assert [u["code"] for u in choices["units"]] == list(rules.UNITS)
    assert {c["code"]: c["rate_bp"] for c in choices["vat_categories"]} == {"S": 1500, "Z": 0, "E": 0, "O": 0}
    assert [r["code"] for r in choices["return_reasons"]][-3:] == ["SHORT_DELIVERY", "PRICE_ERROR", "OTHER"]
    assert choices["count_reasons"]["SHORTAGE"][0] == {"code": "DAMAGE", "name": "تالف"}
    assert choices["limits"]["lines_per_document"] == 40 and choices["document_prefixes"]["COUNT"] == "ج"


def test_a_draft_return_is_valued_like_its_posting():
    """ثلثٌ من سطرٍ صافيه 100.00 بعد خصمٍ وضريبته 15.00: 33.33 و5.00؛ وآخر ما بقي يأخذ الباقي كلّه."""
    assert rules.return_share(1000, 3000, 3000, 10000, 1500, 0, 0) == (3333, 500)
    assert rules.return_share(2000, 2000, 3000, 10000, 1500, 3333, 500) == (6667, 1000)
    assert rules.return_share(1500, 3000, 3000, 10001, 1501, 0, 0) == (5001, 751)   # النصف إلى أعلى
    assert rules.return_share(0, 3000, 3000, 10000, 1500, 0, 0) == (0, 0)
