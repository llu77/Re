"""
الدخول والجلسات
===============
**بلا كتابة تقريباً.** الكتابة بالعين أغلى ما في التطبيق، فبيانات الدخول تأتي
من النظام: حقلٌ بـ`autocomplete=new-password` يجعل Safari يقترح كلمة مرورٍ
قوية تُحفظ في سلسلة مفاتيح iCloud. أن يملأها Face ID عند الدخول مع تشغيل تتبّع
العين لم يُتحقّق منه بعد (Apple توثّق التعبئة بالنقر)؛ وiPhone SE (الجيل الثالث)
بـTouch ID وحده، وبعد إعادة التشغيل يُطلب رمز الجهاز.

**حسابٌ بالتسجيل المفتوح، أو برابط، أو بالدعوة.** يُنشئ المستخدم حسابه بنفسه
(الاسم، وتاريخ الميلاد، والبريد، وكلمة المرور، والمهنة، وطريقة الاستخدام) بلا
رابطٍ حين يكون التسجيل مفتوحاً (`EYEWORK_REGISTRATION=open`، الافتراض)، أو برابط
تسجيلٍ يصدره المشغّل، أو يدعوه المشغّل إلى حسابٍ جاهز (`eyework.admin`). البريد
اسم الدخول، ولا يُرسَل إليه شيء: التطبيق لا يرسل بريداً، فلا تحقّق به ولا
استرداد. رابط تفعيلٍ جديد من المشغّل هو طريق الاسترداد الوحيد؛ ومن سجّل بلا
رابط يطلبه كتابةً إلى `EYEWORK_SUPPORT_CONTACT` من بريد حسابه نفسه.

**اسم الدخول لا يُخزَّن.** يُخزَّن HMAC له بمفتاحٍ خارج القاعدة؛ فنسخةٌ
مسرّبة من القاعدة لا تكشف من يستخدم التطبيق. الثمن معلَن: فقدُ المفتاح
يُغلق كل الحسابات حتى تُعاد الدعوات.

**الرموز تُخزَّن مجزّأة.** الرمز الخام يغادر مرةً واحدة في ملفّ تعريف
الارتباط؛ تسريب جدول الجلسات لا يسلّم جلسةً عاملة.

**زمنٌ متساوٍ.** مستخدمٌ غير موجود يدفع كلفة scrypt نفسها، والرسالة واحدة
لكل فشل — لا يُعرف من الاستجابة إن كان الاسم مسجّلاً.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import re
import secrets
import unicodedata
from functools import lru_cache
from uuid import UUID

from eyework.db import Database
from eyework.passwords import hash_password, verify_password
from eyework.professions import Profession
# نسخة «قبل أن تبدأ» تعيش في `terms.py` مع نصّها؛ تُصدَّر من هنا كما كانت.
from eyework.terms import TERMS_VERSION
from eyework.ui_size import UiSize

__all__ = [
    "EMAIL_MAX",
    "LOGIN_MAX",
    "LOGIN_MIN",
    "NAME_MAX",
    "PASSWORD_MAX",
    "PASSWORD_MIN",
    "AuthenticationFailed",
    "TERMS_VERSION",
    "RegistrationCodeInvalid",
    "RegistrationInvalid",
    "RegistrationTaken",
    "accept_terms",
    "activate",
    "check_birth_date",
    "check_email",
    "check_name",
    "check_password",
    "delete_me",
    "signup_code_usable",
    "hash_token",
    "login",
    "login_hmac",
    "logout",
    "new_token",
    "normalize_login",
    "open_registration_blocker",
    "open_session",
    "profession_of",
    "register",
    "resolve",
    "set_ui_size",
    "terms_version_of",
    "ui_size_of",
]

LOGIN_MIN, LOGIN_MAX = 3, 320
#: اثنا عشر حرفاً على الأقل. اقتراح Safari نفسه عشرون.
PASSWORD_MIN, PASSWORD_MAX = 12, 256

_LOOKUP = "SELECT user_id, password_hash FROM ew_login_lookup(%s)"
_OPEN = "SELECT ew_open_session(%s, %s)"
_OPEN_BY_PASSWORD = "SELECT ew_open_password_session(%s, %s)"
_RESOLVE = "SELECT ew_resolve_session(%s) AS user_id"
_REVOKE = "SELECT ew_revoke_session(%s)"
_ACTIVATE = "SELECT ew_activate(%s, %s, %s) AS user_id"
#: 0008: ثمانية معاملات آخرها طريقة الاستخدام؛ والتسجيل المفتوح بلا رمز دالّةٌ مستقلّة لا
#: يستدعيها الخادم إلا في الوضع المفتوح.
_REGISTER = "SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s, %s)"
_REGISTER_OPEN = "SELECT new_user, outcome FROM ew_register_open(%s, %s, %s, %s, %s, %s, %s)"
_OPEN_BLOCKER = "SELECT ew_open_registration_blocker() AS blocker"
_CODE_USABLE = "SELECT ew_signup_code_usable(%s) AS usable"
_PROFESSION = "SELECT ew_my_profession() AS profession"
_UI_SIZE = "SELECT ew_my_ui_size() AS ui_size"
_SET_UI_SIZE = "SELECT ew_set_my_ui_size(%s)"
_TERMS = "SELECT ew_my_terms_version() AS version"
_ACCEPT_TERMS = "SELECT ew_accept_terms(%s)"
_DELETE_ME = "SELECT ew_delete_me()"

#: نظير القيد display_name_shape (0003): حروفٌ عربية ولاتينية ومسافاتٌ مفردة.
NAME_MAX = 30
_NAME = re.compile(r"^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$")
#: بريدٌ بحروفٍ لاتينية بسيطة بعد التوحيد — نظير شرط اسم الدخول في أداة المشغّل.
EMAIL_MAX = 254
_EMAIL = re.compile(r"^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")
#: أقدم تاريخٍ يُقبل. وأحدثه «اليوم» بتوقيت الرياض، تفحصه القاعدة (ew_register):
#: بايثون هنا لا تقرأ الساعة.
_EARLIEST_BIRTH = datetime.date(1900, 1, 1)


class AuthenticationFailed(Exception):
    """فشل الدخول أو التفعيل. لا تفصيل عمداً."""


class RegistrationInvalid(Exception):
    """حقلٌ في التسجيل لا يُقبل. `field`: NAME أو BIRTH أو EMAIL أو PASSWORD."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


class RegistrationTaken(Exception):
    """
    البريد اسم دخولٍ لحسابٍ قائم. يُعدّ على رمز التسجيل (ثلاثٌ ثم يُقفل)، أو — بلا
    رمز — في دفتر التسجيل (ستّون في اليوم توقف التسجيل المفتوح) وفي حصّة الشبكة
    (ثلاثٌ في اليوم، `web/deps.Limiters.taken_open_net`).
    """


class RegistrationCodeInvalid(Exception):
    """رمز التسجيل غير موجود، أو استُعمل، أو انتهى، أو أُقفل."""


def normalize_login(username: str) -> str:
    """
    شكلٌ واحد لاسم الدخول: NFKC ثم casefold بلا مسافاتٍ حوله.

    «Ali@Example.SA » و«ali@example.sa» اسمٌ واحد؛ والحروف كاملة العرض التي
    تُنتجها بعض لوحات المفاتيح تُوحَّد مع نظيرها.
    """
    return unicodedata.normalize("NFKC", username).casefold().strip()


def login_hmac(key: bytes, username: str) -> bytes:
    return hmac.new(key, normalize_login(username).encode("utf-8"), hashlib.sha256).digest()


def new_token() -> str:
    """43 حرفاً من base64url — 256 بتّاً عشوائياً."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


@lru_cache(maxsize=1)
def _decoy_hash() -> str:
    """تجزئةٌ لا تطابق شيئاً، يُتحقَّق منها حين لا يوجد المستخدم ليتساوى الزمن."""
    return hash_password(secrets.token_urlsafe(24))


def open_session(cursor, user_id: UUID, *, by_password: bool = False) -> str:
    """
    جلسةٌ جديدة في معاملة المستدعي — مع ما يُثبت الدخول أو لا تكون. `by_password`
    للدخول بكلمة المرور وحده: يُحفظ وقته، فتُنشئ الجلسة مفتاح مرورٍ في دقائقها الأولى
    (`passkeys.add`)، ولا تُنشئه جلسةٌ فتحها مفتاحٌ أو رابطٌ أو تسجيل.
    """
    token = new_token()
    if by_password:
        cursor.execute(_OPEN_BY_PASSWORD, (user_id, hash_token(token)))
    else:
        cursor.execute(_OPEN, (user_id, hash_token(token)))
    return token


def login(db: Database, key: bytes, username: str, password: str) -> str:
    """يُرجع رمز جلسةٍ جديدة، أو يرفع `AuthenticationFailed`."""
    with db.session() as cursor:
        cursor.execute(_LOOKUP, (login_hmac(key, username),))
        row = cursor.fetchone()
        stored = row["password_hash"] if row else _decoy_hash()
        if not verify_password(password, stored) or row is None:
            raise AuthenticationFailed
        return open_session(cursor, row["user_id"], by_password=True)


def activate(db: Database, key: bytes, token: str, username: str, password: str) -> str:
    """
    يضع كلمة المرور برمز دعوةٍ صالح لاسم الدخول نفسه، ويفتح جلسة.

    الاسم مربوطٌ بالرمز: رابطٌ عُبث باسمه لا يُفعِّل، فلا يحفظ Safari كلمة
    المرور في سلسلة المفاتيح تحت اسمٍ غير اسم الحساب. والرمز يُستهلك في
    المعاملة نفسها التي تُفتح فيها الجلسة: إن فشل أحدهما لم يحدث أيّهما.
    """
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AuthenticationFailed
    password_hash = hash_password(password)
    with db.session() as cursor:
        cursor.execute(_ACTIVATE, (hash_token(token), login_hmac(key, username), password_hash))
        user_id = cursor.fetchone()["user_id"]
        if user_id is None:
            raise AuthenticationFailed
        return open_session(cursor, user_id)


#: حروف لوحات المفاتيح الفارسية والأردية التي تشبه العربية: تُوحَّد قبل الفحص.
_LETTER_FORMS = str.maketrans({"ی": "ي", "ک": "ك"})


def check_name(raw: str) -> str:
    """
    الاسم بمسافاتٍ مفردة، أو `RegistrationInvalid("NAME")`.

    المسافة التي تتركها اقتراحات لوحة المفاتيح في آخر الكلمة تُحذف، و«ی» و«ک»
    من لوحات الفارسية تصيران «ي» و«ك».
    """
    name = " ".join(raw.translate(_LETTER_FORMS).split())
    if not name or len(name) > NAME_MAX or not _NAME.match(name):
        raise RegistrationInvalid("NAME")
    return name


def check_email(raw: str) -> str:
    """البريد موحّداً كما يُحسب له HMAC، أو `RegistrationInvalid("EMAIL")`."""
    email = normalize_login(raw)
    if len(email) > EMAIL_MAX or not _EMAIL.match(email):
        raise RegistrationInvalid("EMAIL")
    return email


def check_birth_date(raw: str) -> datetime.date:
    """
    تاريخٌ ميلادي حقيقي بصيغة YYYY-MM-DD منذ 1900. وأنه ليس في المستقبل تفحصه
    القاعدة بتاريخ الرياض.

    «29 فبراير» في سنةٍ غير كبيسة تاريخٌ غير موجود فيُرفض، ولا يُصحَّح بصمت.
    """
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        raise RegistrationInvalid("BIRTH")
    try:
        birth = datetime.date.fromisoformat(raw)
    except ValueError as exc:
        raise RegistrationInvalid("BIRTH") from exc
    if birth < _EARLIEST_BIRTH:
        raise RegistrationInvalid("BIRTH")
    return birth


def check_password(raw: str) -> str:
    """كلمة المرور بطولها المقبول، أو `RegistrationInvalid("PASSWORD")`: فحصُ شكلٍ لا يمسّ القاعدة."""
    if not PASSWORD_MIN <= len(raw) <= PASSWORD_MAX:
        raise RegistrationInvalid("PASSWORD")
    return raw


def signup_code_usable(db: Database, code: str) -> bool:
    """تسأله الواجهة قبل الخطوة الأولى. لا يكشف شيئاً عن الحسابات."""
    with db.session() as cursor:
        cursor.execute(_CODE_USABLE, (hash_token(code),))
        return bool(cursor.fetchone()["usable"])


def register(db: Database, key: bytes, *, code: str | None, name: str, birth_date: datetime.date, email: str,
             password: str, profession: Profession, ui_size: UiSize) -> str:
    """
    يُنشئ حساباً مفعَّلاً بمهنته وطريقة استخدامه ويفتح جلسة: برمز تسجيلٍ صالح، أو
    بلا رمز (`code=None`) في الوضع المفتوح — والمسار وحده يقرّر الوضع، فلا يُستدعى
    الطريق المفتوح في وضعي code وclosed. القيم مفحوصةٌ قبل الاستدعاء (`check_*`)؛
    والقاعدة تفحص الرمز، والتاريخ، والسقوف اليومية قبل الإدراج — فعند الامتلاء
    يصل الجواب نفسه لكل بريد — وما ترفضه بقيدٍ يصل معالج القيود في `web/app.py`
    باسمه.

    البريد المأخوذ `RegistrationTaken`: يُعدّ على الرمز، أو بلا رمز في دفتر التسجيل.
    والتجزئة تُحسب قبل السؤال عنه، فكلفة الطلب واحدة في الحالين.
    """
    password_hash = hash_password(check_password(password))
    with db.session() as cursor:
        if code is None:
            cursor.execute(_REGISTER_OPEN, (login_hmac(key, email), password_hash, name, birth_date,
                                            profession.value, TERMS_VERSION, ui_size.value))
        else:
            cursor.execute(_REGISTER, (hash_token(code), login_hmac(key, email), password_hash, name,
                                       birth_date, profession.value, TERMS_VERSION, ui_size.value))
        row = cursor.fetchone()
        token = open_session(cursor, row["new_user"]) if row["outcome"] == "OK" else None
    # الاستثناء بعد المعاملة لا داخلها: داخلها يُلغي عدَّ «مأخوذ» على الرمز أو في الدفتر.
    if row["outcome"] == "CODE":
        raise RegistrationCodeInvalid
    if row["outcome"] == "TAKEN":
        raise RegistrationTaken
    return token


def open_registration_blocker(db: Database) -> str | None:
    """ما يمنع تسجيلاً بلا رابط الآن، باسم قيده، أو None. حال التطبيق كلّه؛ لا شيء عن أحد."""
    with db.session() as cursor:
        cursor.execute(_OPEN_BLOCKER)
        return cursor.fetchone()["blocker"]


def ui_size_of(db: Database, user_id: UUID) -> UiSize | None:
    """طريقة استخدام صاحب الجلسة، أو None إن لم يختر بعد: حساب الدعوة، أو حسابٌ أقدم من 0008."""
    with db.session(user_id) as cursor:
        cursor.execute(_UI_SIZE)
        value = cursor.fetchone()["ui_size"]
    return UiSize(value) if value is not None else None


def set_ui_size(db: Database, user_id: UUID, ui_size: UiSize) -> None:
    """يغيّرها صاحب الجلسة لحسابه وحده: الحساب من الجلسة، لا من الطلب."""
    with db.session(user_id) as cursor:
        cursor.execute(_SET_UI_SIZE, (ui_size.value,))


def terms_version_of(db: Database, user_id: UUID) -> str | None:
    """نسخة «قبل أن تبدأ» التي وافق عليها صاحب الجلسة، أو None لحساب دعوةٍ لم يوافق قطّ."""
    with db.session(user_id) as cursor:
        cursor.execute(_TERMS)
        return cursor.fetchone()["version"]


def accept_terms(db: Database, user_id: UUID) -> None:
    """
    يسجّل موافقة صاحب الجلسة على النسخة الحالية وحدها: لا نسخة من الطلب. والقاعدة لا
    تقبل الرجوع إلى أقدم ممّا وافق عليه (`terms_version_backwards`)، فبعد تراجعٍ عن
    إصدار لا تُمحى موافقة من وافق على الأحدث.
    """
    with db.session(user_id) as cursor:
        cursor.execute(_ACCEPT_TERMS, (TERMS_VERSION,))


def delete_me(db: Database, user_id: UUID) -> None:
    """يحذف صاحب الجلسة حسابه وكل ما يتبعه."""
    with db.session(user_id) as cursor:
        cursor.execute(_DELETE_ME)


def profession_of(db: Database, user_id: UUID) -> Profession | None:
    """مهنة صاحب الجلسة، تُقرأ من القاعدة في كل طلب: المشغّل قد يغيّرها."""
    with db.session(user_id) as cursor:
        cursor.execute(_PROFESSION)
        value = cursor.fetchone()["profession"]
    return Profession(value) if value is not None else None


def resolve(db: Database, token: str) -> UUID | None:
    with db.session() as cursor:
        cursor.execute(_RESOLVE, (hash_token(token),))
        return cursor.fetchone()["user_id"]


def logout(db: Database, token: str) -> None:
    with db.session() as cursor:
        cursor.execute(_REVOKE, (hash_token(token),))
