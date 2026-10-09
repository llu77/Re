"""
قواعد المخزون النقية
====================
ما يُحسب أو يُصاغ بلا قاعدةٍ ولا شبكة: توحيد النصّ المُدخل، وأرقام المستندات
كما تُعرض («ش-0007»، «ص-00012»)، والمبالغ والكميات بكلماتها العربية، ومهلة
إشعار المورّد الدائن، والمقترح طلبه من الصنف، وحاسبة الضريبة بالتقريب نفسه الذي
تحسب به القاعدة (`ew_inv_purchase_calc`). القاعدة تفرض الشكل من جديد؛ هذه
الوحدة تقدّم رسالةً أوضح قبلها وتصوغ ما يُعرض.

وحدةٌ نقية (اختبارٌ معماري): لا تستورد القاعدة ولا الويب، ولا تقرأ الساعة.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

__all__ = [
    "COUNT_REASONS",
    "COUNT_REASON_NAMES",
    "DOCUMENT_PREFIXES",
    "ISSUE_REASON_NAMES",
    "KINDS",
    "PAGE_SIZES",
    "RETURN_REASON_NAMES",
    "REVERSAL_REASON_NAMES",
    "UNITS",
    "UNIT_NAMES",
    "VAT_CATEGORIES",
    "VAT_CATEGORY_NAMES",
    "VAT_RATE_BP",
    "count_label",
    "credit_note_due",
    "document_label",
    "halalas_words",
    "item_code",
    "normalise_digits",
    "normalise_text",
    "quantity_words",
    "reorder_suggestion",
    "suggested_order",
    "vat_split",
    "voucher_label",
]

#: وحدات الأصناف كما في قيد `inv_item_unit`، بأسمائها العربية: الوزن والحجم والطول بكسور.
UNITS: tuple[str, ...] = ("PIECE", "BOX", "CARTON", "PACK", "PALLET", "KG", "LITRE", "METRE", "SERVICE")
UNIT_NAMES: dict[str, str] = {
    "PIECE": "قطعة", "BOX": "علبة", "CARTON": "كرتون", "PACK": "عبوة", "PALLET": "طبلية",
    "KG": "كيلوغرام", "LITRE": "لتر", "METRE": "متر", "SERVICE": "خدمة",
}
DECIMAL_UNITS = frozenset({"KG", "LITRE", "METRE"})
KINDS: dict[str, str] = {"STOCK": "صنفٌ يُخزَّن", "SERVICE": "خدمة"}
#: فئات الضريبة في معيار ZATCA: S الأساسية 15%، Z الصفرية، E المعفاة، O غير الخاضعة.
VAT_CATEGORIES: tuple[str, ...] = ("S", "Z", "E", "O")
VAT_CATEGORY_NAMES: dict[str, str] = {"S": "الأساسية 15%", "Z": "الصفرية", "E": "معفاة", "O": "غير خاضعة"}
VAT_RATE_BP: dict[str, int] = {"S": 1500, "Z": 0, "E": 0, "O": 0}
RETURN_REASON_NAMES: dict[str, str] = {
    "DAMAGED": "تالفة", "WRONG_ITEM": "صنفٌ غير المطلوب", "NOT_AS_SPECIFIED": "غير مطابقة للمواصفات",
    "EXCESS": "زائدة عن الطلب", "EXPIRED": "منتهية الصلاحية", "SHORT_DELIVERY": "نقصٌ في التسليم",
    "PRICE_ERROR": "خطأٌ في السعر", "OTHER": "سببٌ آخر",
}
REVERSAL_REASON_NAMES: dict[str, str] = {
    "DUPLICATE": "سُجّلت مرتين", "WRONG_SUPPLIER": "مورّدٌ غير الصحيح", "WRONG_DETAILS": "بياناتٌ غير صحيحة",
    "OTHER": "سببٌ آخر",
}
ISSUE_REASON_NAMES: dict[str, str] = {"SALE": "بيع", "USE": "استعمالٌ داخلي", "DAMAGE": "تلف", "OTHER": "سببٌ آخر"}
#: أسباب فرق الجرد: للعجز وللزيادة، كما يقبلها قيد `inv_count_line_reason_needed`.
COUNT_REASONS: dict[str, tuple[str, ...]] = {
    "SHORTAGE": ("DAMAGE", "EXPIRED", "THEFT_LOSS", "RECORDING_ERROR", "OTHER"),
    "SURPLUS": ("FOUND", "RECORDING_ERROR", "OTHER"),
}
COUNT_REASON_NAMES: dict[str, str] = {
    "DAMAGE": "تالف", "EXPIRED": "منتهي الصلاحية", "THEFT_LOSS": "فقدٌ أو سرقة", "RECORDING_ERROR": "خطأ تسجيل",
    "FOUND": "عُثر عليه", "OTHER": "سببٌ آخر",
}
COUNT_SCOPE_NAMES: dict[str, str] = {"ALL": "كل الأصناف", "CATEGORY": "تصنيف", "LOW": "تحت حدّ الطلب", "SELECTED": "أصنافٌ مختارة"}
#: حروف المستندات كما تُعرض (المواصفة §3.0): الفاتورة والمرتجع والقيد العكسي والسند والصنف والجلسة.
DOCUMENT_PREFIXES: dict[str, str] = {
    "PURCHASE": "ش", "RETURN": "ر", "REVERSAL": "ع", "VOUCHER": "س", "ITEM": "ص", "COUNT": "ج",
}
#: أحجام الصفحات: 4 و5 للحجم الكبير، و10 و20 للعادي.
PAGE_SIZES: tuple[int, ...] = (4, 5, 10, 20)
MAX_PAGE = 500

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_SPACES = re.compile(r"[ \t ]+")
_HALALA = Decimal("0.01")


def normalise_digits(text: str) -> str:
    """الأرقام العربية والفارسية إلى أرقامٍ غربية: ما يُحفظ ويُقارَن واحد."""
    return text.translate(_DIGITS)


def normalise_text(text: str) -> str:
    """NFKC، ومسافةٌ واحدة بين الكلمات، ومقصوص الطرفين: ما تشترطه `ew_inv_text_ok`."""
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def document_label(kind: str, number: int) -> str:
    """«ش-0007»: الحرف والشرطة وأربع خانات على الأقل، بالأرقام الغربية (القاعدة تخزّن العدد)."""
    return f"{DOCUMENT_PREFIXES[kind]}-{number:04d}"


def item_code(number: int) -> str:
    """رمز الصنف من رقمه: «ص-00012»، خمس خانات لأن الأصناف حتى خمسة آلاف."""
    return f"{DOCUMENT_PREFIXES['ITEM']}-{number:05d}"


def voucher_label(number: int) -> str:
    return document_label("VOUCHER", number)


def count_label(number: int) -> str:
    return document_label("COUNT", number)


def halalas_words(halalas: int) -> str:
    """«1,150.00 ر.س» من هللاتٍ صحيحة؛ السالب بعلامته."""
    sign = "−" if halalas < 0 else ""
    riyals = Decimal(abs(halalas)) / 100
    return f"{sign}{riyals.quantize(_HALALA):,} ر.س"


def quantity_words(milli: int, unit: str) -> str:
    """«12 كرتون» أو «2.5 كيلوغرام»: الكسر يظهر حين يوجد وحده، وبلا أصفارٍ زائدة."""
    whole, fraction = divmod(abs(milli), 1000)
    sign = "−" if milli < 0 else ""
    number = f"{sign}{whole:,}"
    if fraction:
        number += "." + f"{fraction:03d}".rstrip("0")
    return f"{number} {UNIT_NAMES.get(unit, unit)}"


def credit_note_due(return_date: datetime.date) -> datetime.date:
    """
    آخر يومٍ لإشعار المورّد الدائن: خمسة عشر يوماً من الشهر التالي لشهر المرتجع
    (دليل الهيئة للفوترة الضريبية، الإصدار الثالث، §7.2).
    """
    year, month = (return_date.year + 1, 1) if return_date.month == 12 else (return_date.year, return_date.month + 1)
    return datetime.date(year, month, 15)


def suggested_order(on_hand_milli: int, reorder_level_milli: int | None, target_level_milli: int | None) -> int | None:
    """المقترح طلبه: المستهدف ناقص الرصيد حين يكون الصنف تحت حدّ طلبه؛ وإلا لا شيء."""
    if reorder_level_milli is None or on_hand_milli > reorder_level_milli:
        return None
    if target_level_milli is None:
        return None
    return max(target_level_milli - on_hand_milli, 0)


def reorder_suggestion(issued_last_90_days_milli: int, movements: int, unit: str, lead_time_days: int = 14,
                       safety_days: int = 7) -> int | None:
    """
    اقتراحٌ حتمي لحدّ الطلب (قيود: الاستهلاك اليومي × مدّة التوريد + مخزون الأمان) من
    مصروف آخر تسعين يوماً. بأقلّ من ثلاث حركاتٍ لا اقتراح. يُقترح ولا يُطبَّق.
    """
    if movements < 3 or issued_last_90_days_milli <= 0:
        return None
    daily = Decimal(issued_last_90_days_milli) / 90
    level = daily * (lead_time_days + safety_days)
    if unit in DECIMAL_UNITS:
        return int(level.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return int((level / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP)) * 1000


def vat_split(amount_halalas: int, basis: str, category: str) -> tuple[int, int, int]:
    """
    حاسبة الضريبة: (قبل الضريبة، الضريبة، الإجمالي) بالتقريب نصفاً إلى أعلى على
    الهللة كما في القاعدة؛ والشامل ×15/115.
    """
    rate = Decimal(VAT_RATE_BP[category]) / 10000
    amount = Decimal(amount_halalas)
    if basis == "gross":
        vat = (amount * rate / (1 + rate)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return int(amount - vat), int(vat), amount_halalas
    vat = (amount * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return amount_halalas, int(vat), int(amount + vat)


def choices() -> dict:
    """ما تعرضه الواجهة للاختيار في بوابة المخزون، من الخادم وحده (`/api/choices`)."""
    return {
        "units": [{"code": unit, "name": UNIT_NAMES[unit], "decimals": unit in DECIMAL_UNITS} for unit in UNITS],
        "kinds": [{"code": code, "name": name} for code, name in KINDS.items()],
        "vat_categories": [{"code": code, "name": VAT_CATEGORY_NAMES[code], "rate_bp": VAT_RATE_BP[code]} for code in VAT_CATEGORIES],
        "return_reasons": [{"code": code, "name": name} for code, name in RETURN_REASON_NAMES.items()],
        "reversal_reasons": [{"code": code, "name": name} for code, name in REVERSAL_REASON_NAMES.items()],
        "issue_reasons": [{"code": code, "name": name} for code, name in ISSUE_REASON_NAMES.items()],
        "count_reasons": {direction: [{"code": code, "name": COUNT_REASON_NAMES[code]} for code in codes]
                          for direction, codes in COUNT_REASONS.items()},
        "count_scopes": [{"code": code, "name": name} for code, name in COUNT_SCOPE_NAMES.items()],
        "document_prefixes": dict(DOCUMENT_PREFIXES),
        "page_sizes": list(PAGE_SIZES),
        "limits": {"lines_per_document": 40, "open_drafts": 20, "items": 5000, "suppliers": 2000, "categories": 50,
                   "reps_per_supplier": 20, "voucher_days_back": 30, "expenses_max_days": 366},
    }
