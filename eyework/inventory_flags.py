"""
نصوص تنبيهات القواعد في المخزون
================================
القاعدة تحسب التنبيه رمزاً وسطراً وتفاصيل (`ew_inv_purchase_flags`،
`ew_inv_return_flags`)؛ وهذه الوحدة تصوغه جملةً عربية باسم صاحب الحساب كما
تُعرض (المواصفة §7.2). الجمل أخبارٌ لا أوامر، ولا تفترض جنس القارئ، والمبالغ
«1,150.00 ر.س» والتواريخ يوم/شهر/سنة.

«يا {name}، » تُسقط حين لا اسم (حساب دعوةٍ بلا اسم) فتبدأ الجملة بموضوعها.
وحدةٌ نقية.
"""

from __future__ import annotations

import datetime
from typing import Mapping

from eyework.inventory_rules import UNIT_NAMES, VAT_CATEGORY_NAMES, document_label, halalas_words, quantity_words

__all__ = ["LEVELS", "flag_key", "render"]

#: مستوى التنبيه: «high» يُعرض أوّلاً وبإطارٍ أثقل، وما سواه عادي.
LEVELS: dict[str, str] = {
    "DUPLICATE_SUPPLIER_INVOICE": "high",
    "POSSIBLE_DUPLICATE": "normal",
    "TOTAL_MISMATCH": "normal",
    "VAT_MISMATCH": "normal",
    "VAT_WITHOUT_SUPPLIER_VAT_NUMBER": "normal",
    "NO_VAT_CHARGED": "normal",
    "OLD_INVOICE_DATE": "normal",
    "ZERO_PRICE": "normal",
    "PRICE_FAR_FROM_HISTORY": "normal",
    "QUANTITY_FAR_FROM_HISTORY": "normal",
    "CATEGORY_CHANGED": "normal",
    "SHORT_DELIVERY": "normal",
    "FULL_RETURN": "normal",
    "OLD_PURCHASE": "normal",
}
#: عازلا الاتجاه حول الاسم، كما في `reviewer.ISOLATE`.
_ISOLATE = ("⁨", "⁩")


def flag_key(code: str, line_no: int | None) -> str:
    """مفتاح الإقرار كما تطلبه `ew_inv_check_ack`: «رمز» أو «رمز:سطر»."""
    return code if line_no is None else f"{code}:{line_no}"


def _date(value: object) -> str:
    if isinstance(value, datetime.date):
        return f"{value.day}/{value.month}/{value.year}"
    if isinstance(value, str) and len(value) == 10:
        year, month, day = value.split("-")
        return f"{int(day)}/{int(month)}/{int(year)}"
    return str(value)


def _for_unit(unit: str) -> str:
    """«للكرتون» لا «للالكرتون»: الوحدة بلا «ال» بعد «لل»."""
    return "لل" + UNIT_NAMES.get(unit, unit)


def _zero_sentence(detail: Mapping) -> str:
    if detail.get("extra_zero"):
        return " ربما زِيد صفر."
    if detail.get("missing_zero"):
        return " ربما نقص صفر."
    return ""


def render(code: str, line_no: int | None, detail: Mapping, display_name: str | None, *,
           line: Mapping | None = None) -> str:
    """
    جملة التنبيه. `line` بيانات السطر المعنيّ من المستند (اسم الصنف ووحدته وسعره
    وكميته) حين يكون التنبيه على سطر؛ و`detail` ما حسبته القاعدة.
    """
    item = (line or {}).get("item", {})
    name = item.get("name", "")
    unit = item.get("unit", "")
    if code == "DUPLICATE_SUPPLIER_INVOICE":
        text = (f"رقم فاتورة المورّد «{detail.get('supplier_invoice_no', '')}» مسجّلٌ من قبل لهذا المورّد في فاتورة "
                f"الشراء {document_label('PURCHASE', detail['number'])} بتاريخ {_date(detail.get('invoice_date'))}. "
                "تسجيلها ثانيةً يضاعف المصروف والمخزون.")
    elif code == "POSSIBLE_DUPLICATE":
        text = (f"لهذا المورّد فاتورةٌ مسجّلة بالتاريخ نفسه والإجمالي نفسه ({halalas_words(detail['total'])}) هي "
                f"{document_label('PURCHASE', detail['number'])}، برقمٍ آخر. قد تكون الفاتورة نفسها.")
    elif code == "TOTAL_MISMATCH":
        diff = detail["printed"] - detail["computed"]
        text = (f"إجمالي الأسطر المحسوب {halalas_words(detail['computed'])} والمكتوب على فاتورة المورّد "
                f"{halalas_words(detail['printed'])}، والفرق {halalas_words(diff)}. يكون السبب عادةً كميةً أو سعراً "
                "أو خصماً في أحد الأسطر، أو خصماً على الفاتورة كلّها.")
    elif code == "VAT_MISMATCH":
        text = (f"الضريبة المحسوبة {halalas_words(detail['computed'])} والمكتوبة على فاتورة المورّد "
                f"{halalas_words(detail['printed'])}. الضريبة الأساسية 15% من المبلغ قبل الضريبة، فالفرق يعني فئة "
                "ضريبةٍ أخرى في سطرٍ أو أكثر، أو خطأً في الفاتورة.")
    elif code == "VAT_WITHOUT_SUPPLIER_VAT_NUMBER":
        text = ("على الأسطر ضريبةٌ بنسبة 15%، ولا رقم ضريبياً للمورّد هنا. الفاتورة الضريبية تحمل رقم المورّد "
                "الضريبي، ودونه قد لا تُخصم ضريبة هذه المشتريات. إن كان الرقم مطبوعاً على الفاتورة فمكانه في "
                "بيانات المورّد.")
    elif code == "NO_VAT_CHARGED":
        text = ("المورّد مسجّلٌ في الضريبة، ولا ضريبة على أيّ سطر. إن كانت الفاتورة تذكر 15% ففئة الضريبة في "
                "الأسطر تحتاج تعديلاً.")
    elif code == "OLD_INVOICE_DATE":
        text = f"تاريخ الفاتورة قبل {detail['days']} يوماً. إن كان التاريخ صحيحاً فلا شيء غيره."
    elif code == "ZERO_PRICE":
        text = f"سعر «{name}» في السطر {line_no} صفر. يصحّ هذا إن كان هديةً من المورّد."
    elif code == "PRICE_FAR_FROM_HISTORY":
        ref_label = "وسيط آخر مشترياته" if detail.get("basis") == "HISTORY" else "سعره المحدَّد عند إنشائه"
        text = (f"سعر «{name}» في السطر {line_no} هو {halalas_words(int(detail['price']))} {_for_unit(unit)}، "
                f"و{ref_label} {halalas_words(int(detail['reference']))}.") + _zero_sentence(detail)
    elif code == "QUANTITY_FAR_FROM_HISTORY":
        text = (f"كمية «{name}» في السطر {line_no} هي {quantity_words(int(detail['quantity']), unit)}، ووسيط آخر "
                f"مشترياته {quantity_words(int(detail['reference']), unit)}.") + _zero_sentence(detail)
    elif code == "CATEGORY_CHANGED":
        text = (f"فئة الضريبة لـ«{name}» في السطر {line_no} «{VAT_CATEGORY_NAMES.get(detail['category'], detail['category'])}»، "
                f"وفئته المعتادة «{VAT_CATEGORY_NAMES.get(detail['usual'], detail['usual'])}».")
    elif code == "SHORT_DELIVERY":
        text = (f"وصل من «{name}» في السطر {line_no} {quantity_words(int(detail['received']), unit)} من "
                f"{quantity_words(int(detail['invoiced']), unit)} في الفاتورة. تُسجَّل الفاتورة كما هي، ثم يُسجَّل "
                "مرتجعٌ بسبب نقص التسليم بما لم يصل.")
    elif code == "FULL_RETURN":
        text = ("هذا المرتجع يعيد الفاتورة كلّها. إن كانت سُجّلت خطأً فالقيد العكسي أصحّ؛ وإن رُدّت البضاعة "
                "كلّها فعلاً فالمرتجع صحيح.")
    elif code == "OLD_PURCHASE":
        text = (f"الفاتورة بتاريخ {_date(detail.get('invoice_date'))}، قبل {detail['days']} يوماً من المرتجع. "
                "قد لا يقبل المورّد إرجاعاً بعد مدّةٍ كهذه.")
    else:
        text = "في المستند ما يستحقّ نظرةً قبل تسجيله."
    if display_name:
        return f"يا {_ISOLATE[0]}{display_name}{_ISOLATE[1]}، {text}"
    return text
