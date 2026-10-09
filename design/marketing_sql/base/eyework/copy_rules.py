"""
قواعد نصّ الإعلان
=================
ما يقترحه النموذج لا يُعرض على المستخدم قبل أن يمرّ هنا، ولا يُخزَّن إلا
بعد ذلك. قسمان:

**رفضٌ صلب** — النصّ لا يُعرض أصلاً، والمحاولة تُحسب ويُطلب غيرها:
الطول خارج الحدود، أو محارف تحكّم، أو محارف اتجاهٍ خفية تجعل ما يُرى غير ما
يُنسخ (U+202A–U+202E وU+2066–U+2069)، أو رابط أو بريد أو رقم هاتف. الأخيرة
لأن نصّاً يحمل وسيلة اتصال لم يكتبها المستخدم بابٌ للاحتيال باسمه.

**تنبيهٌ ليّن** — النصّ يُعرض، ومعه «تحقّق من هذه العبارة قبل الموافقة»:
سعرٌ أو خصم، أو ادّعاءٌ صحّي، أو مبالغة لا يمكن التحقّق منها. القرار للمستخدم
(النظام يقترح ولا يقرّر)، والتنبيه يضع أمامه ما يستحقّ نظرةً ثانية.

لا اقتطاع أبداً: نصٌّ طويل يُرفض ولا يُقصّ، لأن القصّ يغيّر المعنى بصمت.

الحدود ورموز التعديل هنا ثوابت، ونظيرها في القاعدة قيود CHECK؛ واختبارٌ
يقارن الاثنين.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ARABIC_RATIO_MIN",
    "DESCRIPTION_MAX",
    "DESCRIPTION_MIN",
    "EDIT_NOTE_MAX",
    "NOTE_TO_USER_MAX",
    "MAX_PRESETS",
    "PRESET_CONFLICTS",
    "PRESET_INSTRUCTIONS",
    "TITLE_MAX",
    "TITLE_MIN",
    "CopyCheck",
    "CopyWarning",
    "EditPreset",
    "check_copy",
    "check_edit_request",
    "check_note_to_user",
]

TITLE_MIN, TITLE_MAX = 8, 60
#: كلمة «سيمبول» للمستخدم بجانب النصّ المقترح. قصيرة لتبقى الشاشة بلا تمرير.
NOTE_TO_USER_MAX = 120
DESCRIPTION_MIN, DESCRIPTION_MAX = 40, 240
#: نسبة الحروف العربية بين كل الحروف. أسماء العلامات اللاتينية مقبولة؛ نصٌّ
#: إنجليزيٌّ كامل ليس ما طُلب.
ARABIC_RATIO_MIN = 0.6
#: أسطرٌ قليلة في الوصف مقبولة؛ أكثر منها قائمةٌ لا وصف.
DESCRIPTION_MAX_LINES = 4
EDIT_NOTE_MAX = 200
MAX_PRESETS = 3


class EditPreset(str, Enum):
    SHORTER = "SHORTER"
    SIMPLER = "SIMPLER"
    MORE_FORMAL = "MORE_FORMAL"
    MORE_LIVELY = "MORE_LIVELY"
    NEW_TITLE = "NEW_TITLE"
    NEW_DESCRIPTION = "NEW_DESCRIPTION"


#: ما يُرسَل إلى النموذج لكل خيار — جملٌ ثابتة يكتبها الخادم، لا نصٌّ من العميل.
PRESET_INSTRUCTIONS: dict[EditPreset, str] = {
    EditPreset.SHORTER: "اجعل العنوان والوصف أقصر مما سبق، دون حذف معلومةٍ صحيحة مهمة، ودون أن يقلّ العنوان عن ثلاث كلمات ولا الوصف عن جملتين قصيرتين.",
    EditPreset.SIMPLER: "استعمل كلماتٍ أبسط وجملاً أقصر يفهمها كل قارئ.",
    EditPreset.MORE_FORMAL: "اجعل الأسلوب أكثر رسميةً ووقاراً.",
    EditPreset.MORE_LIVELY: "اجعل الأسلوب أكثر حيويةً وجاذبية، دون مبالغةٍ ولا ادّعاء.",
    EditPreset.NEW_TITLE: "اكتب عنواناً جديداً مختلفاً عن السابق. الوصف لن يتغيّر.",
    EditPreset.NEW_DESCRIPTION: "اكتب وصفاً جديداً مختلفاً عن السابق. العنوان لن يتغيّر.",
}

#: خياران متعاكسان لا يُطلبان معاً.
PRESET_CONFLICTS = (
    frozenset({EditPreset.MORE_FORMAL, EditPreset.MORE_LIVELY}),
    frozenset({EditPreset.NEW_TITLE, EditPreset.NEW_DESCRIPTION}),
)


class CopyWarning(str, Enum):
    PRICE = "PRICE"
    HEALTH_CLAIM = "HEALTH_CLAIM"
    SUPERLATIVE = "SUPERLATIVE"


@dataclass(frozen=True, slots=True)
class CopyCheck:
    #: رموز الرفض الصلب. غير فارغة ⇒ لا يُعرض النصّ ولا يُخزَّن.
    errors: tuple[str, ...]
    warnings: tuple[CopyWarning, ...]
    #: النصّ بعد التطبيع (NFC، ومسافاتٌ متتالية مسافةً واحدة) — هو ما يُخزَّن.
    title: str = ""
    description: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


# ── الرفض الصلب ─────────────────────────────────────────────────────────
#: محارف الاتجاه التي تُظهر نصّاً غير الذي يُنسخ (Trojan Source).
_BIDI_CONTROLS = re.compile("[‪-‮⁦-⁩]")
_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|sa|io|co|me|app|store|shop)\b)", re.IGNORECASE)
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
#: معرّف حسابٍ في شبكةٍ اجتماعية: وسيلة اتصالٍ كالرقم والرابط.
_HANDLE = re.compile(r"@\w")
#: سبعة أرقام فأكثر، لاتينية أو عربية، تفصلها مسافاتٌ أو شرطات — شكل الهاتف.
_PHONE = re.compile(r"(?:[0-9٠-٩۰-۹][\s\-]?){7,}")
#: وسمٌ أو ترميز: نصّ إعلانٍ لا يحتاجهما، وهما بابٌ لإدراج ما لم يُقصد.
_MARKUP = re.compile(r"[#<>]")
_SPACES = re.compile(r"[ \t ]{2,}")


#: رموزٌ من فئة So شائعةٌ في وصف المنتجات وليست تعبيرية: «360°» و«®».
_ALLOWED_SYMBOLS = frozenset("°®™©")


def _symbols(text: str) -> bool:
    """رموز تعبيرية ورموزٌ أخرى، ومحارف خاصة أو بدائل منفردة."""
    return any(unicodedata.category(char) in ("So", "Co", "Cs") and char not in _ALLOWED_SYMBOLS
               for char in text)


def _arabic_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(1 for char in letters if "؀" <= char <= "ۿ" or "ݐ" <= char <= "ݿ")
    return arabic / len(letters)


def _normalize_copy(text: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFC", text))


def _control_characters(text: str, *, allow_newline: bool) -> bool:
    for char in text:
        if char == "\n" and allow_newline:
            continue
        if unicodedata.category(char) == "Cc":
            return True
    return False


# ── التنبيه الليّن ──────────────────────────────────────────────────────
_TASHKEEL = re.compile("[ً-ٰٟـ]")

#: كلماتٌ تُطابَق كلمةً كاملة، مع ما يلتصق بها من أداةٍ أو ضمير — فلا تُنبّه
#: «صحي» على «صحيح». وما ليس كلمةً (رموز العملة والنسبة) يُطابَق كما هو.
_WORDS: dict[CopyWarning, tuple[str, ...]] = {
    CopyWarning.PRICE: ("ريال", "سعر", "خصم", "تخفيض", "مجانا", "مجاني", "sar"),
    CopyWarning.HEALTH_CLAIM: (
        "يعالج", "علاج", "يشفي", "شفاء", "طبي", "يقي", "وقايه", "مرض", "امراض", "صحي",
        "مناعه", "دواء", "سريري",
    ),
    CopyWarning.SUPERLATIVE: ("الافضل", "الاقوى", "الاجود", "مضمون", "الوحيد", "لا مثيل"),
}
_SYMBOLS: dict[CopyWarning, tuple[str, ...]] = {
    CopyWarning.PRICE: ("ر.س", "﷼", "$", "%", "٪"),
    CopyWarning.HEALTH_CLAIM: (),
    CopyWarning.SUPERLATIVE: ("رقم 1", "رقم ١", "100%", "١٠٠٪"),
}
_PREFIXES = "و|ف|ب|ل|ك|ال|وال|بال|فال|كال|لل"
_SUFFIXES = "ه|ات|ي|يه|ين|ون|ها"


def _normalize(text: str) -> str:
    """إزالة التشكيل والتطويل وتوحيد الألف والتاء المربوطة — للمطابقة وحدها."""
    text = _TASHKEEL.sub("", text.casefold())
    return (
        text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    )


_PATTERNS: dict[CopyWarning, re.Pattern[str]] = {
    kind: re.compile(
        rf"(?<!\w)(?:{_PREFIXES})?(?:{'|'.join(re.escape(_normalize(w)) for w in words)})(?:{_SUFFIXES})?(?!\w)"
    )
    for kind, words in _WORDS.items()
}


def _warnings(text: str) -> tuple[CopyWarning, ...]:
    normalized = _normalize(text)
    found = []
    for kind in CopyWarning:
        if _PATTERNS[kind].search(normalized) or any(_normalize(s) in normalized for s in _SYMBOLS[kind]):
            found.append(kind)
    return tuple(found)


def check_copy(title: str, description: str) -> CopyCheck:
    """
    يفحص اقتراح النموذج بعد تطبيعه. لا يقتطع ولا يعيد الصياغة: التطبيع
    توحيدٌ قانوني لـUnicode ودمجٌ للمسافات المتكرّرة، لا تغييرٌ في المعنى.
    """
    title, description = _normalize_copy(title), _normalize_copy(description)
    errors: list[str] = []

    if not TITLE_MIN <= len(title) <= TITLE_MAX:
        errors.append("TITLE_LENGTH")
    if not DESCRIPTION_MIN <= len(description) <= DESCRIPTION_MAX:
        errors.append("DESCRIPTION_LENGTH")
    if title != title.strip() or description != description.strip():
        errors.append("SURROUNDING_SPACE")
    if _control_characters(title, allow_newline=False):
        errors.append("TITLE_CONTROL")
    if _control_characters(description, allow_newline=True):
        errors.append("DESCRIPTION_CONTROL")
    if description.count("\n") >= DESCRIPTION_MAX_LINES:
        errors.append("DESCRIPTION_LINES")

    combined = f"{title}\n{description}"
    if _BIDI_CONTROLS.search(combined):
        errors.append("BIDI_CONTROL")
    if _URL.search(combined) or _EMAIL.search(combined) or _HANDLE.search(combined):
        errors.append("CONTACT_LINK")
    if _PHONE.search(combined):
        errors.append("CONTACT_PHONE")
    if _MARKUP.search(combined):
        errors.append("MARKUP")
    if _symbols(combined):
        errors.append("SYMBOLS")
    if _arabic_ratio(combined) < ARABIC_RATIO_MIN:
        errors.append("NOT_ARABIC")

    return CopyCheck(errors=tuple(errors), warnings=_warnings(combined), title=title, description=description)


def check_edit_request(presets: list[EditPreset], note: str | None) -> str | None:
    """
    طلب التعديل: خيارٌ واحد على الأقل أو ملاحظة. يُرجع رمز الخطأ أو `None`.

    الملاحظة نصٌّ حرّ من المستخدم يذهب إلى النموذج بين محدِّدَين، فتُرفض فيها
    محارف التحكّم والاتجاه الخفيّ كما تُرفض في النصّ المقترح.
    """
    unique = set(presets)
    if len(unique) != len(presets):
        return "PRESET_DUPLICATE"
    if len(presets) > MAX_PRESETS:
        return "PRESET_TOO_MANY"
    if any(conflict <= unique for conflict in PRESET_CONFLICTS):
        return "PRESET_CONFLICT"
    if note is not None:
        if not 1 <= len(note) <= EDIT_NOTE_MAX or note != note.strip():
            return "NOTE_LENGTH"
        if _control_characters(note, allow_newline=False) or _BIDI_CONTROLS.search(note):
            return "NOTE_CONTROL"
    if not presets and note is None:
        return "EDIT_EMPTY"
    return None


def check_note_to_user(note: str) -> tuple[str | None, tuple[str, ...]]:
    """
    كلمة المساعد للمستخدم: تُعرض ولا تُنشر، فلا تُفشل الكتابة إن خالفت.
    يُرجع (النصّ بعد التطبيع أو None، ورموز المخالفة). فارغةٌ مقبولة: لا كلمة.
    """
    note = _normalize_copy(note)
    if not note:
        return None, ()
    errors: list[str] = []
    if len(note) > NOTE_TO_USER_MAX or note != note.strip():
        errors.append("NOTE_LENGTH")
    if _control_characters(note, allow_newline=False) or _BIDI_CONTROLS.search(note):
        errors.append("NOTE_CONTROL")
    if _URL.search(note) or _EMAIL.search(note) or _HANDLE.search(note) or _PHONE.search(note):
        errors.append("NOTE_CONTACT")
    if _MARKUP.search(note) or _symbols(note):
        errors.append("NOTE_SYMBOLS")
    if _arabic_ratio(note) < ARABIC_RATIO_MIN:
        errors.append("NOTE_NOT_ARABIC")
    return (None if errors else note), tuple(errors)
