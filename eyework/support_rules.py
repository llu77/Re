"""
قواعد مكتب الدعم النقية
=======================
ما يُحسب بلا قاعدةٍ ولا شبكة قبل أن يصل أيّ نصٍّ إلى القاعدة أو إلى النموذج:

- **الحذف** (`mask`): البريد والروابط والأرقام الطويلة تُحذف من كل ما يلصقه الموظف من
  كلام العميل، ومن ملاحظاته وتلميحاته، قبل الحفظ. القاعدة تعيد الفحص
  (`ew_support_contact_free`) وترفض ما بقي.
- **الصورة الموحّدة** (`grounding.kb_norm`) التي يُطابَق بها الاقتباس والتنبيه، نظير `ew_kb_norm`.
- **اللغة** (`language_of`): عربيةٌ إن كانت الحروف العربية ثلث الحروف أو أكثر.
- **تنبيهات القواعد** (`rule_flags`) على كل ردٍّ يُجهَّز: وعدٌ لا تذكره المقالات، وطلب سرّ،
  وطلب معلوماتٍ بلا سؤال، ورابطٌ أو رقمٌ لا يرد في المقالات، ولغةٌ غير لغة العميل.
- **الأولوية المقترحة** من الأثر والإلحاح، نظير `ew_support_priority_for`.
- **الأسئلة والعبارات الجاهزة** ونصّ الردّ كما يُنسخ (التحية والتوقيع حول ما كُتب).

وحدةٌ نقية (اختبارٌ معماري): لا تستورد القاعدة ولا الويب ولا النموذج، ولا تقرأ الساعة.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from eyework.grounding import kb_norm

__all__ = [
    "CATEGORIES",
    "CHANNELS",
    "ESCALATION_TARGETS",
    "MASK_TOKENS",
    "PHRASES",
    "PRIORITIES",
    "PRIORITY_RANK",
    "QUESTIONS",
    "QUESTION_CLOSE",
    "QUESTION_INTRO",
    "REJECT_REASONS",
    "RESOLUTIONS",
    "RULE_CODES",
    "SECRET_PHRASES",
    "TRANSITIONS",
    "UPDATE_TEMPLATES",
    "compose_body",
    "contact_tokens",
    "contact_free",
    "flag_text",
    "kb_clean",
    "language_of",
    "mask",
    "normalize",
    "priority_for",
    "priority_reason",
    "rule_flags",
    "template_core",
    "text_ok",
]

# ── المفردات (القاعدة تفرضها بقيودها؛ هنا لرسائل أوضح قبلها) ─────────────
CHANNELS = ("MESSAGING", "EMAIL", "PHONE", "IN_PERSON", "WEB_FORM", "OTHER")
PRIORITIES = ("URGENT", "HIGH", "NORMAL", "LOW")
PRIORITY_RANK = {"URGENT": 4, "HIGH": 3, "NORMAL": 2, "LOW": 1}
CATEGORIES = ("ACCOUNT", "SOFTWARE", "HARDWARE", "PRINTING", "NETWORK", "EMAIL", "INSTALL", "HOW_TO", "OTHER")
ESCALATION_TARGETS = ("TIER2", "SUPERVISOR", "VENDOR", "FIELD_TECH", "OTHER_TEAM")
RESOLUTIONS = ("BY_PHONE", "IN_PERSON", "DUPLICATE", "NOT_SUPPORT", "NO_RESPONSE")
REJECT_REASONS = ("WRONG_INFO", "NOT_IN_KB", "MISUNDERSTOOD", "TONE", "TOO_LONG", "INCOMPLETE", "OUTDATED_ARTICLE",
                  "OTHER")
RULE_CODES = ("PROMISE", "ASKS_SECRET", "NO_QUESTION", "LINK_NOT_IN_KB", "LANGUAGE_MISMATCH")

#: نظير جدول `support_ticket_transition` (اختبارٌ يقارنهما).
TRANSITIONS = frozenset({
    ("NEW", "OPEN"), ("NEW", "PENDING"), ("NEW", "ESCALATED"), ("NEW", "RESOLVED"), ("NEW", "CLOSED"),
    ("OPEN", "PENDING"), ("OPEN", "ESCALATED"), ("OPEN", "RESOLVED"), ("OPEN", "CLOSED"),
    ("PENDING", "OPEN"), ("PENDING", "ESCALATED"), ("PENDING", "RESOLVED"), ("PENDING", "CLOSED"),
    ("ESCALATED", "OPEN"), ("ESCALATED", "CLOSED"),
    ("RESOLVED", "OPEN"), ("RESOLVED", "PENDING"), ("RESOLVED", "CLOSED"),
})

# ── التوحيد ─────────────────────────────────────────────────────────────
#: محارف الاتجاه الخفية والعلامة في أول الملف: لا تُرى ولا تُحفظ.
_INVISIBLE = re.compile("[‎‏‪-‮⁦-⁩﻿]")
#: محارف التحكّم عدا السطر الجديد (القاعدة ترفضها في `ew_support_text_ok`).
_CONTROL = re.compile("[\x00-\x09\x0b-\x1f\x7f]")


def normalize(text: str) -> str:
    """NFC، وأسطرٌ بـLF، بلا محارف خفية ولا تحكّم، بلا مسافاتٍ في آخر السطر ولا أكثر من سطرين فارغين."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text.replace("\t", " "))
    text = _CONTROL.sub("", text)
    text = "\n".join(line.rstrip(" ") for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" \n")


def one_line(text: str) -> str:
    """حقلٌ في سطرٍ واحد: الأسطر تصير مسافات."""
    return re.sub(r"\s+", " ", normalize(text)).strip()


def text_ok(text: str, multiline: bool) -> bool:
    """نظير `ew_support_text_ok`."""
    return (text == text.strip(" \n") and not _CONTROL.search(text) and not _INVISIBLE.search(text)
            and (multiline or "\n" not in text))


# ── الحذف ───────────────────────────────────────────────────────────────
MASK_EMAIL = "[بريد محذوف]"
MASK_LINK = "[رابط محذوف]"
MASK_NUMBER = "[رقم محذوف]"
MASK_TOKENS = (MASK_EMAIL, "[رابط محذوف", MASK_NUMBER)

_DIGIT = "[0-9٠-٩۰-۹]"
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_LINK = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
#: تسعة أرقامٍ فأكثر (لاتينية أو عربية أو فارسية)، بينها مسافةٌ أو شَرطةٌ واحدة على الأكثر.
_LONG_NUMBER = re.compile(rf"\+?(?:{_DIGIT}[ -]?){{8}}{_DIGIT}(?:[ -]?{_DIGIT})*")
#: ما يُفحص في الردّ والمقالة: سبعة أرقامٍ فأكثر (هاتفٌ أو رقمٌ يُتّبع).
_SEVEN_DIGITS = re.compile(rf"\+?(?:{_DIGIT}[ -]?){{6}}{_DIGIT}(?:[ -]?{_DIGIT})*")


_HOST = re.compile(r"(?i)^(?:https?://)?(?:[^/@\s]*@)?([^/:?#\s]+)")


def _host(url: str) -> str | None:
    match = _HOST.match(url)
    host = match.group(1).lower() if match else None
    if not host:
        return None
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    host = host.lower().removeprefix("www.")
    # اسمٌ يحمل أرقاماً طويلة يُحذف كلّه: لا يعود الرقم من باب الرابط.
    return host if re.fullmatch(r"[a-z0-9.-]{1,80}", host) and not re.search(r"[0-9]{9}", host) else None


def mask(text: str) -> tuple[str, dict[str, int]]:
    """
    (النصّ بعد الحذف، وعدد ما حُذف من كلّ نوع). الرابط يبقى منه اسم موقعه («[رابط محذوف:
    example.com]») ليعرف الموظف أيّ خدمةٍ قصد العميل؛ والمسار والمعاملات قد تحمل رموزاً أو
    بياناتٍ شخصية. والدالّة مستقرّة: `mask(mask(x)) == mask(x)`.
    """
    counts = {"email": 0, "link": 0, "number": 0}
    text = normalize(text)

    def email(_match: re.Match) -> str:
        counts["email"] += 1
        return MASK_EMAIL

    def link(match: re.Match) -> str:
        counts["link"] += 1
        host = _host(match.group(0))
        return f"[رابط محذوف: {host}]" if host else MASK_LINK

    def number(_match: re.Match) -> str:
        counts["number"] += 1
        return MASK_NUMBER

    text = _EMAIL.sub(email, text)
    text = _LINK.sub(link, text)
    text = _LONG_NUMBER.sub(number, text)
    return text, counts


def contact_free(text: str) -> bool:
    """نظير `ew_support_contact_free`: بلا بريدٍ ولا تسعة أرقامٍ متتالية."""
    return not _EMAIL.search(text) and not re.search(rf"(?:{_DIGIT}[ -]?){{8}}{_DIGIT}", text)


def kb_clean(text: str) -> bool:
    """نظير `ew_support_kb_clean`: بلا رقم هويةٍ أو إقامة، ولا بطاقةٍ ولا آيبان."""
    if re.search(r"(^|[^0-9٠-٩])[12١٢][0-9٠-٩]{9}([^0-9٠-٩]|$)", text):
        return False
    if re.search(r"(?:[0-9٠-٩][ -]?){12}[0-9٠-٩]", text):
        return False
    return not re.search(r"(?i)SA[0-9]{2} ?[0-9]{4}", text)


def contact_tokens(text: str) -> list[str]:
    """البريد والروابط والأرقام من سبعة فأكثر في نصّ ردٍّ أو مسودة، بترتيب ظهورها."""
    found: list[tuple[int, str]] = []
    for pattern in (_EMAIL, _LINK, _SEVEN_DIGITS):
        for match in pattern.finditer(text):
            token = match.group(0).rstrip(".,،؛:)]»")
            if not any(start <= match.start() < start + len(seen) for start, seen in found):
                found.append((match.start(), token))
    return [token for _start, token in sorted(found)]


# ── اللغة ───────────────────────────────────────────────────────────────
_ARABIC_LETTER = re.compile("[ء-يٮ-ۓۺ-ۼ]")


def language_of(text: str) -> str:
    """AR إن كانت الحروف العربية ثلث الحروف أو أكثر، وإلا EN (والنصّ بلا حروف عربيّ)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "AR"
    arabic = sum(1 for ch in letters if _ARABIC_LETTER.match(ch))
    return "AR" if arabic * 10 >= len(letters) * 3 else "EN"


# ── تنبيهات القواعد ─────────────────────────────────────────────────────
_PROMISE = re.compile(
    r"خلال \d+ (?:دقيقة|دقائق|ساعة|ساعات|يوم|أيام)|غداً|غدا|اليوم نفسه|نضمن|مضمون|تعويض|استرداد|استرجاع المبلغ|مجاناً|مجانا"
    r"|[0-9٠-٩]+ ?(?:ريال|ر\.س|٪|%)"
    r"|(?i:within \d+ (?:minutes?|hours?|days?)|guarantee\w*|refund\w*|compensat\w*|free of charge|\d+ ?(?:SAR|%))")
SECRET_PHRASES = ("كلمة المرور", "كلمة السر", "رمز التحقق", "رمز التحقّق", "الرمز المرسل", "OTP", "رقم البطاقة", "CVV",
                  "رقم الهوية", "الآيبان", "password", "verification code")
_SECRET = re.compile("|".join(re.escape(phrase) for phrase in SECRET_PHRASES), re.IGNORECASE)


def _evidence(text: str) -> str | None:
    """اقتباسٌ صالحٌ للقاعدة: من حرفين إلى 200 في سطره."""
    text = text.strip()
    if len(text) < 2:
        return None
    return text[:200].strip()


def rule_flags(core: str, kind: str, customer_language: str, grounding: Iterable[str]) -> list[dict]:
    """
    تنبيهات القواعد على ردٍّ مجهَّز، بشكل `ew_support_prepare_reply`: [{"code", "evidence"}].
    `grounding` نصوص المقالات التي يستند إليها الردّ (اقتباسات المسودة وما أُدرج من القاعدة).
    """
    sources = [kb_norm(text) for text in grounding]
    flags: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    def add(code: str, evidence: str | None) -> None:
        key = (code, evidence)
        if key not in seen:
            seen.add(key)
            flags.append({"code": code, "evidence": evidence})

    for match in _PROMISE.finditer(core):
        phrase = match.group(0)
        if not any(kb_norm(phrase) in source for source in sources):
            add("PROMISE", _evidence(phrase))
    for match in _SECRET.finditer(core):
        add("ASKS_SECRET", _evidence(match.group(0)))
    if kind == "ASK_INFO" and "؟" not in core and "?" not in core:
        add("NO_QUESTION", None)
    for token in contact_tokens(core):
        if not any(kb_norm(token) in source for source in sources):
            add("LINK_NOT_IN_KB", _evidence(token))
    if language_of(core) != customer_language:
        add("LANGUAGE_MISMATCH", None)
    return flags[:8]


#: نصّ تنبيه القاعدة (الخبر والسبب)، يُركَّب هنا من الرمز ولا يُخزَّن. `{evidence}` مقصوص.
_FLAG_TEXTS = {
    "PROMISE": ("في الردّ ما يُقرأ وعداً بموعدٍ أو مبلغ.",
                "«{evidence}» لا يرد في المقالات المقتبسة، والوعد يُلزم جهة العمل."),
    "ASKS_SECRET": ("الردّ يطلب من العميل معلومةً سرّية.",
                    "«{evidence}»؛ كلمات المرور ورموز التحقّق وأرقام البطاقات والهويات لا تُطلب في الرسائل، ومن يطلبها يشبه المحتال."),
    "NO_QUESTION": ("طلب المعلومات بلا سؤال.",
                    "الردّ من نوع «طلب معلومات» وليس فيه علامة استفهام، فلن يعرف العميل ما المطلوب منه."),
    "LINK_NOT_IN_KB": ("في الردّ رابطٌ أو رقمٌ لا يرد في قاعدة المعرفة.",
                       "«{evidence}» لم يُنقل من مقالةٍ معتمدة، ورابطٌ أو رقمٌ خاطئ يرسل العميل إلى غير جهة العمل."),
    "LANGUAGE_MISMATCH": ("لغة الردّ غير لغة العميل.", "كتب العميل {customer}، والردّ {reply}."),
    "PRIORITY_BELOW_SUGGESTION": ("الأولوية المختارة أدنى من المقترحة.",
                                  "الأولوية «{priority}» والمقترحة «{suggested}»، لأن الرسالة تذكر {because}."),
    "RESOLVE_UNANSWERED": ("آخر رسالةٍ من العميل بلا ردّ.",
                           "حلّ التذكرة «{resolution}» دون ردٍّ مكتوب قد يترك العميل ينتظر جواباً."),
}
PRIORITY_NAMES = {"URGENT": "عاجلة", "HIGH": "عالية", "NORMAL": "عادية", "LOW": "منخفضة"}
RESOLUTION_NAMES = {"REPLIED": "بالردّ", "BY_PHONE": "بالهاتف", "IN_PERSON": "حضورياً", "DUPLICATE": "مكرّرة",
                    "NOT_SUPPORT": "ليست طلب دعم", "NO_RESPONSE": "لم يردّ العميل"}
_LANGUAGE_NAMES = {"AR": "بالعربية", "EN": "بالإنجليزية"}


def _short(text: str | None, limit: int = 80) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip() + "…"


def flag_text(code: str, evidence: str | None = None, **facts: str) -> tuple[str, str]:
    """(الخبر، السبب) لتنبيه قاعدة. الحقائق الإضافية: customer وreply للغة، وpriority وsuggested
    وbecause للأولوية، وresolution للحلّ بلا ردّ."""
    message, reason = _FLAG_TEXTS[code]
    values = {"evidence": _short(evidence), **facts}
    if code == "LANGUAGE_MISMATCH":
        values["customer"] = _LANGUAGE_NAMES.get(facts.get("customer", ""), "")
        values["reply"] = _LANGUAGE_NAMES.get(facts.get("reply", ""), "")
    if code == "PRIORITY_BELOW_SUGGESTION":
        values["priority"] = PRIORITY_NAMES.get(facts.get("priority", ""), "")
        values["suggested"] = PRIORITY_NAMES.get(facts.get("suggested", ""), "")
    if code == "RESOLVE_UNANSWERED":
        values["resolution"] = RESOLUTION_NAMES.get(facts.get("resolution", ""), "")
    return message, reason.format_map(_Blank(values))


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return ""


# ── الأولوية ────────────────────────────────────────────────────────────
def priority_for(impact: str, urgency: str, security: bool) -> str:
    """نظير `ew_support_priority_for`: مصفوفة الأثر والإلحاح، والشبهة الأمنية عالية."""
    if impact == "WIDESPREAD" and urgency == "STOPPED":
        return "URGENT"
    if security or urgency == "STOPPED" or (impact == "WIDESPREAD" and urgency == "DEGRADED"):
        return "HIGH"
    if urgency == "DEGRADED" or impact == "WIDESPREAD":
        return "NORMAL"
    return "LOW"


def priority_reason(impact: str, urgency: str, security: bool) -> str:
    """ما يتمّ به «لأن الرسالة تذكر …» في بطاقة الاقتراح. أوّل ما يصدق."""
    if impact == "WIDESPREAD" and urgency == "STOPPED":
        return "توقّف العمل لأكثر من مستخدم"
    if security:
        return "شبهةً أمنية"
    if urgency == "STOPPED":
        return "توقّف عمل المستخدم كلّياً"
    if impact == "WIDESPREAD" and urgency == "DEGRADED":
        return "تعطّلاً جزئياً لأكثر من مستخدم"
    if urgency == "DEGRADED":
        return "تعطّلاً جزئياً"
    if impact == "WIDESPREAD":
        return "طلباً يخصّ أكثر من مستخدم"
    return "طلباً لا يوقف العمل"


# ── الأسئلة والعبارات الجاهزة ────────────────────────────────────────────
QUESTIONS = {
    "ERROR_TEXT": ("ما نصّ رسالة الخطأ كما تظهر على الشاشة؟", "What exactly does the error message on the screen say?"),
    "WHEN_STARTED": ("متى بدأت المشكلة؟ وهل تغيّر شيءٌ قبلها، كتحديثٍ أو جهازٍ جديد؟",
                     "When did the problem start? Did anything change just before, such as an update or a new device?"),
    "DEVICE": ("ما نوع الجهاز، وما نظام تشغيله؟", "What device are you using, and which operating system?"),
    "SCOPE": ("هل المشكلة على جهازكم وحده، أم على أجهزةٍ أخرى أيضاً؟",
              "Does the problem happen only on your device, or on others too?"),
    "STEPS": ("ما الخطوات التي تؤدّي إلى المشكلة، خطوةً خطوة؟", "What steps lead to the problem, one by one?"),
    "TRIED": ("ما الذي جُرِّب حتى الآن لحلّها؟", "What has been tried so far to fix it?"),
    "SCREENSHOT": ("هل يمكن إرسال صورةٍ للشاشة تُظهر المشكلة، دون بياناتٍ شخصية؟",
                   "Could you send a screenshot that shows the problem, without personal details?"),
}
QUESTION_INTRO = ("لنساعد في حلّ المشكلة بسرعة، نرجو تزويدنا بما يلي:", "To help us solve this quickly, please tell us:")
QUESTION_CLOSE = ("وسنعود إليكم فور وصولها.", "We will get back to you as soon as we have these.")
UPDATE_TEMPLATES = {
    "ESCALATED": ("أُحيلت المسألة إلى الفريق المختص، وسنبلغكم بما يصل.",
                  "We have passed your request to the specialist team and will let you know as soon as we hear back."),
    "WORKING": ("نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة.",
                "We are working on the problem now and will get back to you with the result."),
}
PHRASES = {
    "THANKS_SORRY": ("شكراً على تواصلكم، ونأسف لما حدث.", "Thank you for contacting us, and we are sorry for the trouble."),
    "WORKING": ("نعمل على المشكلة الآن، وسنعود إليكم بالنتيجة.",
                "We are working on the problem now and will get back to you with the result."),
    "CONFIRM_FIXED": ("هل حُلّت المشكلة بعد هذه الخطوات؟ أخبرونا لنغلق الطلب أو نتابع.",
                      "Did these steps fix the problem? Let us know so we can close the request or continue."),
    "PATIENCE": ("شكراً على صبركم.", "Thank you for your patience."),
    "MORE_HELP": ("هل من شيءٍ آخر يمكننا المساعدة فيه؟ يسعدنا ذلك.", "Is there anything else we can help with? We would be glad to."),
}


def template_core(codes: Iterable[str], language: str) -> str:
    """طلب المعلومات من أسئلةٍ جاهزة: التمهيد، ثم الأسئلة مرقّمة، ثم الختام، بلغة العميل."""
    index = 0 if language == "AR" else 1
    picked = list(dict.fromkeys(codes))
    lines = [QUESTION_INTRO[index]]
    lines += [f"{n}. {QUESTIONS[code][index]}" for n, code in enumerate(picked, start=1)]
    lines.append(QUESTION_CLOSE[index])
    return "\n".join(lines)


def compose_body(core: str, customer_label: str | None, signature: str | None, language: str) -> str:
    """ما يُنسخ للعميل: التحية باسمه إن عُرف، ثم الردّ، ثم توقيع الموظف إن كتبه."""
    if language == "AR":
        greeting = f"مرحباً {customer_label}،" if customer_label else "مرحباً،"
    else:
        greeting = f"Hello {customer_label}," if customer_label else "Hello,"
    parts = [greeting, core]
    if signature:
        parts.append(signature)
    return "\n\n".join(parts)
