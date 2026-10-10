"""
الأعداد بالكلمات العربية
========================
يُعاد المبلغ والمدّة بالكلمات قبل الاعتماد، لأن الرقم وحده يُقرأ خطأً بسهولة
— صفرٌ زائد في ميزانية لا يلفت عيناً متعبة، و«ألفان وخمسمئة ريال» يلفتها.

القواعد لمعدودٍ مذكّر (ريال، يوم)، في موضع الرفع:

    1        ريال واحد · يوم واحد            المعدود أولاً
    2        ريالان · يومان                  المثنى وحده
    3–10     ثلاثة أيام · عشرة ريالات         العدد بالتاء + جمعٌ مجرور
    11–99    أحد عشر يوماً · خمسون ريالاً      مفردٌ منصوب
    مئات وآلاف تامّة   مئة ريال · مئتا ريال · ألفا ريال · ثلاثة آلاف ريال
    المركّب يأخذ صيغة جزئه الأخير: ألفان وخمسمئة ريال · مئة وخمسون ريالاً

**موضع الرفع وحده.** الإعراب يغيّر الصيغة («لمدة يومين»)، فلا تُدرج هذه
الكلمات إلا بعد عنوانٍ ونقطتين: «المدة: يومان». واختبار الواجهة يتحقّق
من ذلك.

**المجال مغلق.** ما بعد المئة إذا انتهى بواحد أو اثنين («مئة وواحد») له
صيغٌ يختلف فيها النحاة، فلا تُخمَّن: ترفع الدالة `ValueError`. ومجال الميزانية
(مضاعفات الخمسين) والمدّة (حتى ثلاثين) لا يبلغانه أصلاً — اختبارٌ يمرّ على
كل قيمة فيهما.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DAY", "RIYAL", "Noun", "in_words"]


@dataclass(frozen=True, slots=True)
class Noun:
    """صيغ المعدود المذكّر الخمس."""

    singular: str    # ريال واحد — يتقدّم المعدودُ العددَ
    dual: str        # ريالان
    plural: str      # ثلاثة ريالات
    accusative: str  # أحد عشر ريالاً
    genitive: str    # مئة ريال


RIYAL = Noun("ريال", "ريالان", "ريالات", "ريالاً", "ريال")
DAY = Noun("يوم", "يومان", "أيام", "يوماً", "يوم")

#: مع المعدود المذكّر تأتي الأعداد من ثلاثة إلى عشرة بالتاء.
_UNITS = {3: "ثلاثة", 4: "أربعة", 5: "خمسة", 6: "ستة", 7: "سبعة",
          8: "ثمانية", 9: "تسعة", 10: "عشرة"}
_TENS = {2: "عشرون", 3: "ثلاثون", 4: "أربعون", 5: "خمسون",
         6: "ستون", 7: "سبعون", 8: "ثمانون", 9: "تسعون"}
_HUNDREDS = {1: "مئة", 3: "ثلاثمئة", 4: "أربعمئة", 5: "خمسمئة", 6: "ستمئة",
             7: "سبعمئة", 8: "ثمانمئة", 9: "تسعمئة"}

_UPPER = 999_999


def _below_hundred(n: int) -> str:
    if n == 1:
        return "واحد"
    if n == 2:
        return "اثنان"
    if n <= 10:
        return _UNITS[n]
    if n == 11:
        return "أحد عشر"
    if n == 12:
        return "اثنا عشر"
    if n < 20:
        return f"{_UNITS[n - 10]} عشر"
    tens, unit = divmod(n, 10)
    if unit == 0:
        return _TENS[tens]
    return f"{_below_hundred(unit)} و{_TENS[tens]}"


def _below_thousand(n: int, *, construct: bool) -> str:
    """`construct`: يليه المعدود مباشرةً، فتُحذف نون «مئتان»."""
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds == 2:
        parts.append("مئتا" if construct and rest == 0 else "مئتان")
    elif hundreds:
        parts.append(_HUNDREDS[hundreds])
    if rest:
        parts.append(_below_hundred(rest))
    return " و".join(parts)


def _thousands(count: int, *, followed: bool) -> str:
    """`count` من الآلاف. `followed`: يليه جزءٌ بواو، فلا يُضاف إلى المعدود."""
    tail = count % 100
    if count == 1:
        return "ألف"
    if count == 2:
        return "ألفان" if followed else "ألفا"
    if count < 100:
        words = _below_hundred(count)
    elif tail in (1, 2):
        raise ValueError(f"صيغة خارج المجال المدعوم: {count} ألفاً")
    else:
        words = _below_thousand(count, construct=tail == 0)

    if tail == 0:
        return f"{words} ألف"
    if tail <= 10:
        return f"{words} آلاف"
    return f"{words} ألفاً" if followed else f"{words} ألف"


def in_words(n: int, noun: Noun) -> str:
    """
    العدد ومعدوده بالكلمات، في موضع الرفع.

    يرفض ما ليس عدداً صحيحاً موجباً، ويرفض `bool` صراحةً — `True` عددٌ
    صحيح في بايثون، و«ريال واحد» من قيمةٍ منطقية خطأٌ صامت.
    """
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= _UPPER:
        raise ValueError(f"خارج المجال: {n!r}")
    if n == 1:
        return f"{noun.singular} واحد"
    if n == 2:
        return noun.dual

    tail = n % 100
    if n > 100 and tail in (1, 2):
        raise ValueError(f"صيغة خارج المجال المدعوم: {n}")

    thousands, rest = divmod(n, 1000)
    parts = []
    if thousands:
        parts.append(_thousands(thousands, followed=rest > 0))
    if rest:
        parts.append(_below_thousand(rest, construct=True))
    number = " و".join(parts)

    if tail == 0:
        form = noun.genitive
    elif tail <= 10:
        form = noun.plural
    else:
        form = noun.accusative
    return f"{number} {form}"
