"""
فحص ما يكتبه النموذج قبل عرضه
=============================
كل نصٍّ يكتبه النموذج ويظهر للموظف — سبب الملاحظة واقتراحها، وجواب المساعد —
يمرّ من هنا. نصٌّ يُعرض تحت اسم الموظف يجب ألّا يحمل رابطاً ولا رقماً لم
يكتبه أحد، ولا نداءً يسبق النداء الذي يضعه التطبيق بنفسه.

القواعد قواعد نصّ الإعلان نفسها (`copy_rules`) وتزيد عليها: سطرٌ واحد (أو
أسطرٌ معدودة للجواب)، ولا سلسلة من تسعة أرقام، ولا نداءٌ ولا تحيةٌ في أول
السطر. والنظير في القاعدة `ew_ai_text_ok` وهو الأوسع؛ هذا الأشدّ: كل ما يقبله
هنا تقبله القاعدة (اختبارٌ في `tests/db/test_ai_layer.py` يقارنهما على مجموعة
نصوص)، فلا يُسقط قيدُ الجدول ملاحظةً مرّت من هنا.

لا اقتطاع: نصٌّ طويل يُرفض كلّه، لأن القصّ يغيّر المعنى بصمت.
"""

from __future__ import annotations

import re
import unicodedata

from eyework.copy_rules import (
    ARABIC_RATIO_MIN,
    _arabic_ratio,
    _control_characters,
    _EMAIL,
    _HANDLE,
    _MARKUP,
    _symbols,
    _URL,
)

__all__ = ["CODES", "arabic_ratio", "check", "has_bidi", "has_contact", "has_control", "has_markup", "has_symbols",
           "opens_with_vocative"]

#: رموز الرفض كما تُسجَّل (بلا نصّ).
CODES = ("LENGTH", "LINES", "CONTROL", "BIDI", "CONTACT", "DIGITS", "MARKUP", "SYMBOLS", "NOT_ARABIC", "VOCATIVE")

#: تسعة أرقامٍ فأكثر، لاتينية أو هندية، بينها مسافةٌ أو شرطةٌ واحدة على الأكثر.
_LONG_DIGITS = re.compile(r"(?:[0-9٠-٩۰-۹][ \-]?){8}[0-9٠-٩۰-۹]")
#: محارف الاتجاه الخفية: علامات الاتجاه (U+061C وU+200E وU+200F) والتضمين والقلب
#: (U+202A–U+202E) والعزل (U+2066–U+2069). أوسع من فئة نصّ الإعلان بالعلامات الثلاث،
#: وهي ما يضعه النموذج حول رمزٍ لاتيني في نصٍّ عربي، وما ترفضه القاعدة أيضاً.
_BIDI_CONTROLS = re.compile("[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
#: نداءٌ أو تحية في أول النصّ. كلمةٌ تبدأ بـ«يا» كاسم صنفٍ («ياقوت») تمرّ: النداء
#: «يا» تتبعه مسافة.
_VOCATIVE = re.compile(r"^(?:(?:يا|أيها|أيتها)\s|مرحب|أهلا|أهلاً|السلام عليك|عزيزي|عزيزتي)")
_SPACES = re.compile(r"[ \t ]{2,}")


def has_contact(text: str) -> bool:
    """رابطٌ أو بريد أو حسابٌ يبدأ بـ@ — وسيلة اتصالٍ لم يكتبها الموظف."""
    return bool(_URL.search(text) or _EMAIL.search(text) or _HANDLE.search(text))


def has_markup(text: str) -> bool:
    return bool(_MARKUP.search(text))


def has_control(text: str, *, allow_newline: bool = False) -> bool:
    """محارف تحكّم (فاصل السطر منها إلا حين يُسمح به)."""
    return _control_characters(text, allow_newline=allow_newline)


def has_bidi(text: str) -> bool:
    """محارف اتجاهٍ خفية تُظهر نصّاً غير الذي يُنسخ."""
    return bool(_BIDI_CONTROLS.search(text))


def has_symbols(text: str) -> bool:
    return _symbols(text)


def arabic_ratio(text: str) -> float:
    return _arabic_ratio(text)


def opens_with_vocative(text: str) -> bool:
    return bool(_VOCATIVE.match(text))


def check(text: str, min_length: int, max_length: int, *, lines: int = 1,
          vocative: bool = True) -> tuple[str | None, tuple[str, ...]]:
    """
    يُرجع (النصّ بعد التطبيع أو None، ورموز المخالفة). التطبيع توحيدٌ لـUnicode
    (NFC) ودمجٌ للمسافات المتكرّرة وقصٌّ للطرفين، لا تغييرٌ في المعنى.

    `lines`: عدد الأسطر المسموح؛ واحدٌ يعني لا فاصل سطر. `vocative`: يُرفض
    النداء والتحية في أول النصّ (التطبيق يضع النداء بنفسه).
    """
    normalized = _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip()
    codes: list[str] = []
    if not min_length <= len(normalized) <= max_length:
        codes.append("LENGTH")
    if normalized.count("\n") >= lines:
        codes.append("LINES")
    if _control_characters(normalized, allow_newline=lines > 1):
        codes.append("CONTROL")
    if _BIDI_CONTROLS.search(normalized):
        codes.append("BIDI")
    if has_contact(normalized):
        codes.append("CONTACT")
    if _LONG_DIGITS.search(normalized):
        codes.append("DIGITS")
    if has_markup(normalized):
        codes.append("MARKUP")
    if has_symbols(normalized):
        codes.append("SYMBOLS")
    if arabic_ratio(normalized) < ARABIC_RATIO_MIN:
        codes.append("NOT_ARABIC")
    if vocative and opens_with_vocative(normalized):
        codes.append("VOCATIVE")
    return (None if codes else normalized), tuple(codes)
