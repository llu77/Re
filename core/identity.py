"""
الهوية والجلسات
================
بوابتان بمصادقة مستقلة: جلسة `PRACTITIONER` لا تصلح لبوابة المريض والعكس،
ويُفرض ذلك عند كل طلب لا عند تسجيل الدخول فقط.

تجزئة كلمات المرور بـ`hashlib.scrypt` من المكتبة القياسية — لا تبعية إضافية،
ومعاملاتها مخزَّنة مع التجزئة فتبقى قابلة للترقية لاحقاً.

الرموز تُخزَّن مجزّأة: تسريب قاعدة البيانات لا يسلّم جلسات عاملة.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from core import db
from core.clock import now
from core.types import Actor, Gate, Role

__all__ = [
    "AuthenticationFailed",
    "SESSION_LIFETIME",
    "Principal",
    "authenticate",
    "hash_password",
    "resolve_session",
    "revoke_session",
    "revoke_user_sessions",
    "verify_password",
]

SESSION_LIFETIME = timedelta(hours=12)

# معاملات scrypt: N=2^15 يوازن بين الكلفة والأمان على عتاد خادم اعتيادي.
# `maxmem` صريح: حدّ OpenSSL الافتراضي 32 MiB وهو ما تحتاجه هذه المعاملات
# بالضبط (128·N·r)، فيفشل بلا هامش. تركه افتراضياً يُسقط المصادقة كلياً.
_SCRYPT = {"n": 2**15, "r": 8, "p": 1, "dklen": 64, "maxmem": 64 * 1024 * 1024}
_SALT_BYTES = 16


class AuthenticationFailed(Exception):
    """بيانات اعتماد غير صحيحة، أو جلسة غير صالحة. لا نفصّل عمداً."""


@dataclass(frozen=True, slots=True)
class Principal:
    """صاحب الطلب بعد التحقق: هويته ودوره وبوابته."""

    actor: Actor
    gate: Gate
    session_id: UUID
    patient_id: UUID | None = None


def hash_password(password: str) -> str:
    """`scrypt$<salt>$<hash>` — المعاملات ضمنية في الصيغة وقابلة للترقية."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """مقارنة بزمن ثابت. صيغة مجهولة ⇒ فشل، لا استثناء يكشف التفاصيل."""
    try:
        scheme, salt_hex, expected_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **_SCRYPT
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), expected_hex)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_USER_BY_EMAIL = (
    "SELECT u.id, u.tenant_id, u.role, u.password_hash, u.is_active,"
    " COALESCE("
    "   (SELECT p.id FROM patients p WHERE p.user_id = u.id LIMIT 1),"
    "   (SELECT l.patient_id FROM caregiver_links l"
    "     WHERE l.caregiver_user_id = u.id AND l.revoked_at IS NULL)"
    " ) AS patient_id"
    " FROM users u WHERE u.email = %s"
)

_INSERT_SESSION = (
    "INSERT INTO sessions (user_id, gate, token_hash, expires_at)"
    " VALUES (%s, %s, %s, %s) RETURNING id"
)

#: سياق المريض للحساب: ملفّه هو، أو ملفّ من يرافقه بموافقة سارية.
#:
#: يُقرأ في كل طلب لا عند تسجيل الدخول وحده، فسحبُ الموافقة يقطع الوصول فوراً.
#: ولا `LIMIT` في الشقّ الثاني عمداً: الفهرس الجزئي يضمن صفّاً فاعلاً واحداً
#: لكل مرافق، ولو خُرق ذلك يوماً لرفع استعلامٌ فرعيّ بصفّين خطأً — فيفشل
#: الدخول مغلقاً بدل أن يُختار مريض بالتخمين.
_SESSION_BY_TOKEN = (
    "SELECT s.id, s.gate, s.expires_at, u.id AS user_id, u.tenant_id, u.role, u.is_active,"
    " COALESCE("
    "   (SELECT p.id FROM patients p WHERE p.user_id = u.id LIMIT 1),"
    "   (SELECT l.patient_id FROM caregiver_links l"
    "     WHERE l.caregiver_user_id = u.id AND l.revoked_at IS NULL)"
    " ) AS patient_id"
    " FROM sessions s JOIN users u ON u.id = s.user_id"
    " WHERE s.token_hash = %s AND s.revoked_at IS NULL"
)

#: الدور المسموح لكل بوابة. جلسة بوابة لا تصلح للأخرى.
_GATE_ROLES: dict[Gate, frozenset[Role]] = {
    "PRACTITIONER": frozenset({"PRACTITIONER", "ADMIN"}),
    "PATIENT": frozenset({"PATIENT", "CAREGIVER"}),
}


def authenticate(email: str, password: str, gate: Gate) -> tuple[str, Principal]:
    """
    يتحقق من بيانات الاعتماد ويفتح جلسة للبوابة المطلوبة.

    يُعيد الرمز الخام مرة واحدة فقط؛ المخزَّن تجزئته.
    """
    with db.session("owner") as cursor:
        cursor.execute(_USER_BY_EMAIL, (email,))
        row = cursor.fetchone()

        # نُجري التحقق حتى مع مستخدم غير موجود ليتساوى زمن الاستجابة.
        stored = row["password_hash"] if row else hash_password(secrets.token_hex(8))
        if not verify_password(password, stored) or row is None or not row["is_active"]:
            raise AuthenticationFailed("بيانات اعتماد غير صحيحة")

        if row["role"] not in _GATE_ROLES[gate]:
            raise AuthenticationFailed("هذه البوابة لا تقبل هذا الدور")

        token = secrets.token_urlsafe(32)
        cursor.execute(
            _INSERT_SESSION,
            (row["id"], gate, _hash_token(token), now() + SESSION_LIFETIME),
        )
        session_id = cursor.fetchone()["id"]

    principal = Principal(
        actor=Actor(id=row["id"], role=row["role"], tenant_id=row["tenant_id"]),
        gate=gate,
        session_id=session_id,
        patient_id=row["patient_id"],
    )
    return token, principal


def resolve_session(token: str, gate: Gate) -> Principal:
    """
    يحوّل رمزاً إلى هوية موثَّقة، أو يرفض.

    `gate` يُفحص هنا لا عند تسجيل الدخول فقط: رمز بوابة الممارس لا يفتح بوابة
    المريض حتى لو كان صالحاً.
    """
    with db.session("owner") as cursor:
        cursor.execute(_SESSION_BY_TOKEN, (_hash_token(token),))
        row = cursor.fetchone()

    if row is None or not row["is_active"]:
        raise AuthenticationFailed("جلسة غير صالحة")
    if row["expires_at"] <= now():
        raise AuthenticationFailed("انتهت الجلسة")
    if row["gate"] != gate or row["role"] not in _GATE_ROLES[gate]:
        raise AuthenticationFailed("جلسة لا تخص هذه البوابة")

    return Principal(
        actor=Actor(id=row["user_id"], role=row["role"], tenant_id=row["tenant_id"]),
        gate=gate,
        session_id=row["id"],
        patient_id=row["patient_id"],
    )


def revoke_session(session_id: UUID) -> None:
    with db.session("owner") as cursor:
        cursor.execute(
            "UPDATE sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL",
            (session_id,),
        )


def revoke_user_sessions(user_id: UUID) -> int:
    """
    إبطال فوري لكل جلسات مستخدم.

    يُستدعى عند سحب الموافقة أو تغيير الدور: استمرار جلسة قديمة بعد أيٍّ منهما
    يعني وصولاً بصلاحيات لم تعد قائمة.
    """
    with db.session("owner") as cursor:
        cursor.execute(
            "UPDATE sessions SET revoked_at = now()"
            " WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
        return cursor.rowcount
