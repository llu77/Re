"""
قائمة فحوص مراجعة المخزون (`STOCK_REVIEW`)
==========================================
ما يراجعه سيمبول في مسودة فاتورة الشراء والمرتجع ممّا لا تحسبه القواعد الثابتة
(المواصفة §7.3): السعر حين لا تاريخ للصنف، ووحدةٌ لا تناسب الصنف، واسمٌ جديد
لصنفٍ موجود، وسبب إرجاعٍ لا يناسب البضاعة. القائمة والموضوع يُبنيان هنا بلا
قاعدةٍ ولا هوية؛ والمراجِع العام (`reviewer`) يرسلهما ويقرأ الجواب.

**الموضوع المرسَل** (`purchase_payload`، `return_payload`): أسماء الأصناف
ووحداتها وأنواعها وكمياتها وأسعار وحداتها قبل الضريبة وفئات ضريبتها، وعدد
مشتريات الصنف السابقة ووسيطا سعرها وكميتها، وأسماء الأصناف المرشَّحة للصنف
الجديد؛ وللمرتجع سبب الإرجاع رمزاً والأيام منذ الشراء. لا اسم ولا مورّد ولا
رقم ولا تاريخ ولا ملاحظة (اختبارٌ معماري على المفاتيح).

وحدةٌ نقية.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from eyework.inventory_rules import UNIT_NAMES
from eyework.reviewer_prompt import Catalogue, Check

__all__ = ["CATALOGUE", "PAYLOAD_KEYS", "purchase_payload", "return_payload", "sar", "quantity"]

PURCHASE = frozenset({"PURCHASE"})
RETURN = frozenset({"RETURN"})
#: المرشَّحون لصنفٍ جديد: خمسة على الأكثر، بتشابهٍ في مفتاح الاسم لا يقلّ عن النصف.
CANDIDATES_MAX = 5
CANDIDATE_RATIO = 0.5
#: مشتريات الصنف السابقة التي تُعدّ (كما في `ew_inv_purchase_flags`).
HISTORY_MAX = 10


def sar(halalas: int | None) -> str | None:
    """«45.50» من هللات: ريالاتٌ بخانتين، كما تُكتب على الفاتورة."""
    if halalas is None:
        return None
    return f"{Decimal(halalas) / 100:.2f}"


def quantity(milli: int | None) -> str | None:
    """«10» أو «2.5» من أجزاء الألف، بلا أصفارٍ زائدة."""
    if milli is None:
        return None
    whole, fraction = divmod(milli, 1000)
    if not fraction:
        return str(whole)
    return f"{whole}." + f"{fraction:03d}".rstrip("0")


def purchase_payload(lines: Iterable[Mapping]) -> dict:
    """
    موضوع فاتورة الشراء. كل سطر: `line_no`، `item_name`، `unit`، `kind`، `quantity_milli`،
    `unit_net_halalas`، `vat_category`، `history_count`، `median_price_halalas`،
    `median_quantity_milli`، `candidates` (ref، name، unit) للصنف الجديد.
    """
    rendered = []
    for line in lines:
        count = int(line.get("history_count") or 0)
        rendered.append({
            "line": line["line_no"],
            "item": line["item_name"],
            "unit": line["unit"],
            "kind": line["kind"],
            "quantity": quantity(line["quantity_milli"]),
            "unit_price": sar(line["unit_net_halalas"]),
            "vat": line["vat_category"],
            "history": {
                "count": count,
                "median_price": sar(line.get("median_price_halalas")),
                "median_quantity": quantity(line.get("median_quantity_milli")),
            },
            "new_item": count == 0,
            "candidates": [{"ref": ref, "item": name, "unit": unit}
                           for ref, name, unit in (line.get("candidates") or ())[:CANDIDATES_MAX]] if count == 0 else [],
        })
    return {"lines": rendered}


def return_payload(reason: str, lines: Iterable[Mapping]) -> dict:
    """
    موضوع المرتجع: سبب الإرجاع رمزاً (لا الملاحظة)، وكل سطر: `line_no`، `item_name`،
    `unit`، `kind`، `quantity_milli` (المرتجع)، `bought_milli`، `days_since_purchase`.
    """
    return {
        "reason": reason,
        "lines": [{
            "line": line["line_no"],
            "item": line["item_name"],
            "unit": line["unit"],
            "kind": line["kind"],
            "quantity": quantity(line["quantity_milli"]),
            "quantity_bought": quantity(line["bought_milli"]),
            "days_since_purchase": int(line["days_since_purchase"]),
        } for line in lines],
    }


#: مفاتيح الموضوعين معاً، كما تُعلَن في `ReviewFeature.payload_keys` ويقارنها اختبارٌ بما يُحمَّل فعلاً.
PAYLOAD_KEYS: frozenset[str] = frozenset({
    "lines", "line", "item", "unit", "kind", "quantity", "unit_price", "vat", "history", "count", "median_price",
    "median_quantity", "new_item", "candidates", "ref", "reason", "quantity_bought", "days_since_purchase",
})


def _line(payload: Mapping, number: int | None) -> Mapping | None:
    return next((item for item in payload.get("lines") or () if item.get("line") == number), None)


def _unit(code: str) -> str:
    return UNIT_NAMES.get(code, code)


def _line_evidence(payload: Mapping, number: int | None) -> tuple[str, ...]:
    """شواهد السطر من الأرقام التي أُرسلت: الصنف والكمية وسعر الوحدة، وتاريخه إن كان."""
    item = _line(payload, number)
    if item is None:
        return ()
    lines = [f"الصنف: {item['item']}",
             f"الكمية: {item['quantity']} {_unit(item['unit'])} بسعر {item['unit_price']} ر.س للوحدة قبل الضريبة"]
    history = item.get("history") or {}
    if history.get("count"):
        lines.append(f"آخر مشترياته: {history['count']}، وسيط سعرها {history.get('median_price')} ر.س")
    else:
        lines.append("لا مشترياتٍ مسجّلة لهذا الصنف من قبل")
    return tuple(lines)


def _candidate_evidence(payload: Mapping, number: int | None) -> tuple[str, ...]:
    item = _line(payload, number)
    if item is None:
        return ()
    names = "، ".join(f"«{candidate['item']}»" for candidate in item.get("candidates") or ())
    return (f"الصنف الجديد: {item['item']} ({_unit(item['unit'])})",
            f"أصنافٌ موجودة بأسماءٍ قريبة: {names}" if names else "لا أصناف قريبة الاسم")


def _return_evidence(payload: Mapping, number: int | None) -> tuple[str, ...]:
    lines = [f"سبب الإرجاع: {payload.get('reason')}"]
    for item in (payload.get("lines") or ())[:2]:
        lines.append(f"{item['item']}: {item['quantity']} من {item['quantity_bought']} {_unit(item['unit'])}، "
                     f"بعد {item['days_since_purchase']} يوماً من الشراء")
    return tuple(lines)


CATALOGUE = Catalogue("STOCK_REVIEW", (
    Check(
        "PRICE_IMPLAUSIBLE", PURCHASE, frozenset({"unit_price"}), True,
        "لسطرٍ عدد مشتريات صنفه السابقة أقلّ من ثلاث (history.count). سعر الوحدة قبل الضريبة بعيدٌ جداً عمّا "
        "يُتوقّع لمثل هذا الصنف بهذه الوحدة في السوق السعودية، نحو عشرة أضعافه أو عُشره. الفروق العادية بين "
        "الموردين ليست خطأً. لا تنبّه على سطرٍ له ثلاث مشترياتٍ فأكثر: القواعد تقارنه بتاريخه.",
        _line_evidence),
    Check(
        "UNIT_MISMATCH", PURCHASE, frozenset({"unit", "quantity"}), True,
        "وحدة السطر لا تناسب الصنف، كزيتٍ بالمتر أو كرتونة ماءٍ بالكيلوغرام، أو كميةٌ لا تُعقل بهذه الوحدة. "
        "الحقل unit للوحدة وquantity للكمية.",
        _line_evidence),
    Check(
        "SAME_AS_EXISTING_ITEM", PURCHASE, frozenset({"item"}), True,
        "لسطرٍ صنفه جديد (new_item) ومعه candidates. اسمه يدلّ على المنتج نفسه لصنفٍ في المرشَّحين بكتابةٍ أخرى، "
        "فيُسجَّل المنتج الواحد صنفين. اذكر في السبب اسم الصنف الموجود كما هو. الحجم أو اللون أو النوع المختلف "
        "يعني صنفاً مختلفاً.",
        _candidate_evidence),
    Check(
        "REASON_IMPLAUSIBLE", RETURN, frozenset({"reason"}), False,
        "سبب الإرجاع (reason) لا يناسب البضاعة أو المدّة منذ الشراء، كـEXPIRED لأداةٍ لا صلاحية لها، أو EXCESS "
        "بعد أشهرٍ طويلة. فحصٌ على المرتجع كلّه: line فارغ.",
        _return_evidence),
), "رقم السطر في المستند")
