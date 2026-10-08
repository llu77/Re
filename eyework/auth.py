"""
الدخول والجلسات
===============
**بلا كتابة تقريباً.** الكتابة بالعين أغلى ما في التطبيق، فبيانات الدخول تأتي
من النظام: حقلٌ بـ`autocomplete=new-password` يجعل Safari يقترح كلمة مرورٍ
قوية تُحفظ في سلسلة مفاتيح iCloud بنظرةٍ واحدة، ثم يملؤها Face ID في كل
دخول. لا تسجيلٌ ذاتي ولا استرداد بالبريد: الحساب يُنشأ بدعوة
(`eyework.admin`)، ورابط تفعيلٍ جديد هو طريق الاسترداد الوحيد.

**اسم الدخول لا يُخزَّن.** يُخزَّن HMAC له بمفتاحٍ خارج القاعدة؛ فنسخةٌ
مسرّبة من القاعدة لا تكشف من يستخدم التطبيق. الثمن معلَن: فقدُ المفتاح
يُغلق كل الحسابات حتى تُعاد الدعوات.

**الرموز تُخزَّن مجزّأة.** الرمز الخام يغادر مرةً واحدة في ملفّ تعريف
الارتباط؛ تسريب جدول الجلسات لا يسلّم جلسةً عاملة.

**زمنٌ متساوٍ.** مستخدمٌ غير موجود يدفع كلفة scrypt نفسها، والرسالة واحدة
لكل فشل — لا يُعرف من الاستجابة إن كان الاسم مسجّلاً.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
from functools import lru_cache
from uuid import UUID

from eyework.db import Database
from eyework.passwords import hash_password, verify_password

__all__ = [
    "LOGIN_MAX",
    "LOGIN_MIN",
    "PASSWORD_MAX",
    "PASSWORD_MIN",
    "AuthenticationFailed",
    "activate",
    "hash_token",
    "login",
    "login_hmac",
    "logout",
    "new_token",
    "normalize_login",
    "resolve",
]

LOGIN_MIN, LOGIN_MAX = 3, 320
#: اثنا عشر حرفاً على الأقل. اقتراح Safari نفسه عشرون.
PASSWORD_MIN, PASSWORD_MAX = 12, 256

_LOOKUP = "SELECT user_id, password_hash FROM ew_login_lookup(%s)"
_OPEN = "SELECT ew_open_session(%s, %s)"
_RESOLVE = "SELECT ew_resolve_session(%s) AS user_id"
_REVOKE = "SELECT ew_revoke_session(%s)"
_ACTIVATE = "SELECT ew_activate(%s, %s, %s) AS user_id"


class AuthenticationFailed(Exception):
    """فشل الدخول أو التفعيل. لا تفصيل عمداً."""


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


def _open_session(cursor, user_id: UUID) -> str:
    token = new_token()
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
        return _open_session(cursor, row["user_id"])


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
        return _open_session(cursor, user_id)


def resolve(db: Database, token: str) -> UUID | None:
    with db.session() as cursor:
        cursor.execute(_RESOLVE, (hash_token(token),))
        return cursor.fetchone()["user_id"]


def logout(db: Database, token: str) -> None:
    with db.session() as cursor:
        cursor.execute(_REVOKE, (hash_token(token),))
