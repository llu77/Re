"""
إخفاء بيانات الغير قبل الإرسال
==============================
كل نصٍّ كتبه شخصٌ غير الموظف — رسالة عميل، سبب مرتجع، اسم صنفٍ وصل من
مورّد — وكل سؤالٍ للمساعد، يمرّ من هنا قبل أن يغادر إلى مزوّد النموذج. يُرسَل
أقلّ ما يلزم: لا هاتف ولا بريد ولا هوية ولا بطاقة ولا حساب.

**الأرقام بالهندية واللاتينية سواء.** تُحسب المطابقة على نسخةٍ أرقامها
لاتينية، ويُستبدل في النصّ الأصلي بالموضع، فلا تتغيّر حروفٌ لم تُطابَق.

**تسعة أرقام فأكثر.** الحدّ الذي تستعمله قاعدة الدعم نفسها
(`ew_support_contact_free`): يغطّي الجوال (05…، +966…)، والهوية والإقامة
(عشرة)، والبطاقة والحساب؛ ويبقي الأسعار والكميات والتواريخ وأرقام الطلبات
القصيرة كما هي. فالموظف يرى في «سؤالك: …» ما غادر فعلاً.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["redact"]

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
#: النطاق الأخير حروفٌ لاتينية: علامة الترقيم العربية بعد البريد ليست منه.
_EMAIL = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[A-Za-z0-9-]+")
_URL = re.compile(r"(?:https?://|www\.)[^\s،؟]+", re.IGNORECASE)
#: الآيبان السعودي: SA ثم 22 خانة، بمسافاتٍ أو بدونها.
_IBAN = re.compile(r"\bSA\s?\d{2}(?:\s?[0-9A-Z]{4}){5}\b", re.IGNORECASE)
#: تسعة أرقامٍ فأكثر، بينها مسافةٌ أو شرطةٌ واحدة على الأكثر، وقبلها + اختيارية.
_LONG_NUMBER = re.compile(r"\+?\d(?:[ -]?\d){8,}")
_MASKS = ((_EMAIL, "[بريد]"), (_URL, "[رابط]"), (_IBAN, "[حساب]"), (_LONG_NUMBER, "[رقم]"))


def _free(spans: list[tuple[int, int, str]], start: int, end: int) -> bool:
    return not any(s < end and start < e for s, e, _ in spans)


def redact(text: str, names: tuple[str, ...] = ()) -> tuple[str, int]:
    """
    (النصّ بعد الإخفاء، وعدد ما أُخفي). `names`: أسماءٌ محفوظة عندنا تُطابَق
    حرفياً وتصير «العميل» — كاسم عميل التذكرة.
    """
    text = unicodedata.normalize("NFC", text)
    probe = text.translate(_DIGITS)
    spans: list[tuple[int, int, str]] = []
    for pattern, mask in _MASKS:
        for match in pattern.finditer(probe):
            if _free(spans, match.start(), match.end()):
                spans.append((match.start(), match.end(), mask))
    for name in names:
        if not name:
            continue
        for match in re.finditer(re.escape(name), text):
            if _free(spans, match.start(), match.end()):
                spans.append((match.start(), match.end(), "العميل"))
    out = text
    for start, end, mask in sorted(spans, reverse=True):
        out = out[:start] + mask + out[end:]
    return out, len(spans)
