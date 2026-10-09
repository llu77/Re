"""
مفاتيح المرور
=============
دخولٌ بلا كتابةٍ ولا اسم: زرٌّ واحد، ثم يؤكّد النظام بـFace ID أو Touch ID أو
رمز الجهاز. كلمة المرور تبقى بديلاً: مفاتيح المرور تشترط سلسلة مفاتيح iCloud
والمصادقة بخطوتين، ولا يملكهما كل مستخدم.

**المفتاح يُنشئه المتصفّح بعد الدخول بكلمة المرور**، كما تفعل التطبيقات (الإنشاء
المشروط، `mediation: 'conditional'`)، ولا زرّ للإضافة. فالإضافة لجلسة الطلب
نفسها، ما دامت قائمةً وفُتحت بكلمة المرور قبل خمس دقائق على الأكثر
(`UPGRADE_SECONDS`)؛ تفحص القاعدة ذلك عند التحدّي وفي معاملة الحفظ. ولا يُشترط في
ردّ الإنشاء علَما الحضور والتحقّق: المتصفّح يضعهما صفراً في الإنشاء المشروط
(WebAuthn Level 3، §5.1.3 و§7.1)، وما يثبت صاحب الحساب هو كلمة المرور قبل لحظات.
والدخول بالمفتاح بعدها يشترطهما كما كان.

**التحقّق في py_webauthn** (مثبّتةٌ على 3.0.1 بموافقة المالك)، لا في تحليل
CBOR وCOSE مكتوبٍ هنا: نوع clientDataJSON، والتحدّي، والأصل، وتجزئة معرّف
الطرف، وعلَما الحضور (UP) والتحقّق (UV)، والتوقيع، وعدّاد التوقيع. وما لا تفحصه
هي يُفحص هنا: أن الطقس لم يجرِ داخل إطار (`crossOrigin`)، وأن معرّف المستخدم
العائد مع التوقيع لصاحب المفتاح نفسه.

**التحدّي في القاعدة** (`passkey_challenges`): يُستهلك قبل التحقّق في المعاملة
نفسها، ويبقى مستهلَكاً ولو فشل التحقّق؛ ومهلته تفرضها القاعدة لا المتصفّح.

**معرّف المستخدم في المفتاح** (`user.id`) ليس رقم الحساب: HMAC له بمفتاح أسماء
الدخول. يحفظه الجهاز ويعيده مع كل توقيع، فيُطابَق مع صاحب المفتاح.

**لا جواب يكشف حساباً.** طلب الدخول بلا اسم؛ وكل فشلٍ فيه — تحدٍّ منتهٍ أو
مستعمل، ومفتاحٌ مجهول أو لحسابٍ محذوف أو موقوف، وتوقيعٌ خاطئ، وعدّادٌ رجع —
`PasskeyRejected` واحد بلا تفصيل.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, parse_client_data_json
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.options_to_json_dict import options_to_json_dict
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from eyework import auth
from eyework.db import Database

__all__ = [
    "CHALLENGE_SECONDS",
    "LOGIN_CHALLENGES_MAX",
    "MAX_PASSKEYS",
    "PasskeyRejected",
    "RP_NAME",
    "UPGRADE_SECONDS",
    "UPGRADE_TIMEOUT_SECONDS",
    "add",
    "add_options",
    "login_options",
    "rp_id",
    "sign_in",
    "user_handle",
]

#: مهلة التحدّي — نظير القيد passkey_challenge_window والدالّة ew_passkey_challenge (0006).
#: خمس دقائق: الخيارات تُجلب حين تُعرض الشاشة، والضغط بالنظر يأخذ وقته.
CHALLENGE_SECONDS = 300
#: نظير السقف passkey_cap (0006).
MAX_PASSKEYS = 10
#: الإضافة لجلسةٍ فُتحت بكلمة المرور منذ هذا على الأكثر — نظير الشرط في
#: ew_passkey_add_challenge وew_passkey_add (0007).
UPGRADE_SECONDS = 300
#: تحدّيات الدخول السارية في القاعدة كلّها — نظير passkey_login_ceiling (0007).
LOGIN_CHALLENGES_MAX = 10_000
#: مهلة الإنشاء المشروط (`timeout` في خياراته): الدخول ينتظره قبل الانتقال إلى الرئيسية.
#: المتصفّح يرفض فوراً حين لا تتحقّق شروطه، لكن Chromium 141 ومعه مُصادِقٌ متّصل ينتظر
#: المهلة كلّها ثم يرفض — بمهلة التحدّي كانت خمس دقائق. ومؤقّتها في المتصفّح نفسه
#: (lifetimeTimer في WebAuthn)، لا في الصفحة.
UPGRADE_TIMEOUT_SECONDS = 5
#: اسم الطرف كما يعرضه النظام في نافذة المفتاح.
RP_NAME = "صياغة"

_CHALLENGE_BYTES = 32
#: حدّا ما يُحفظ — نظيرا القيدين passkey_credential_id_shape وpasskey_public_key_shape.
_CREDENTIAL_ID_MAX = 1023
_PUBLIC_KEY_MAX = 2048
#: ES256 وRS256 وحدهما.
_ALGORITHMS = [COSEAlgorithmIdentifier.ECDSA_SHA_256, COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256]
_TRANSPORTS = frozenset(transport.value for transport in AuthenticatorTransport)
_HANDLE_CONTEXT = b"eyework/passkey-user/"

#: ما ترفعه المكتبة لمدخلٍ مشوّه أو توقيعٍ لا يصحّ. كلّه رفضٌ لا خطأ خادم. وRecursionError
#: من json.loads على clientDataJSON متداخلٍ بعمق (`[[[…]]]` في حدود طول الحقل).
_REJECTED = (WebAuthnException, InvalidSignature, ValueError, TypeError, KeyError, IndexError, RecursionError)

_LOGIN_CHALLENGE = "SELECT ew_passkey_login_challenge(%s)"
_ADD_CHALLENGE = "SELECT ew_passkey_add_challenge(%s, %s, %s)"
_TAKE = "SELECT ew_passkey_take_challenge(%s, %s) AS taken"
_LOOKUP = "SELECT user_id, public_key, sign_count FROM ew_passkey_lookup(%s)"
_SIGNED_IN = "SELECT ew_passkey_signed_in(%s, %s) AS user_id"
_MINE = "SELECT credential_id, transports FROM ew_my_passkeys()"
_ADD = "SELECT ew_passkey_add(%s, %s, %s, %s, %s) AS added"
_NAME = "SELECT ew_my_display_name() AS name"


class PasskeyRejected(Exception):
    """فشل الدخول أو الإضافة بمفتاح مرور. لا تفصيل عمداً."""


def rp_id(origin: str) -> str:
    """معرّف الطرف: مضيف الأصل العام (`config.public_origin`) بلا مخطّطٍ ولا منفذ."""
    return origin.split("://", 1)[1].split(":", 1)[0]


def user_handle(key: bytes, user_id: UUID) -> bytes:
    """معرّف المستخدم في المفتاح: ثابتٌ للحساب، ولا يُعرف منه رقمه دون المفتاح."""
    return hmac.new(key, _HANDLE_CONTEXT + user_id.bytes, hashlib.sha256).digest()


def _digest(challenge: bytes) -> bytes:
    return hashlib.sha256(challenge).digest()


def _decode(value: str) -> bytes:
    try:
        return base64url_to_bytes(value)
    except ValueError as exc:
        raise PasskeyRejected from exc


def _challenge_of(credential: dict[str, Any]) -> bytes:
    """
    التحدّي كما وقّعه الجهاز. والطقس داخل إطارٍ مرفوض: التطبيق لا يُؤطَّر
    (`frame-ancestors 'none'`)، فإطارٌ يحمله ليس منّا — والمكتبة لا تفحص هذا.
    """
    try:
        client = parse_client_data_json(_decode(credential["response"]["clientDataJSON"]))
    except _REJECTED as exc:
        raise PasskeyRejected from exc
    if client.cross_origin or len(client.challenge) != _CHALLENGE_BYTES:
        raise PasskeyRejected
    return client.challenge


def _take(cursor, challenge: bytes, purpose: str) -> bool:
    cursor.execute(_TAKE, (_digest(challenge), purpose))
    return bool(cursor.fetchone()["taken"])


# ── الدخول ─────────────────────────────────────────────────────────────
def login_options(db: Database, origin: str) -> dict[str, Any]:
    """
    خيارات `navigator.credentials.get`: بلا قائمة مفاتيح (`allowCredentials`
    فارغة)، فيعرض الجهاز مفاتيحه لهذا الموقع ولا يُسأل المستخدم عن اسمه.
    """
    challenge = secrets.token_bytes(_CHALLENGE_BYTES)
    with db.session() as cursor:
        cursor.execute(_LOGIN_CHALLENGE, (_digest(challenge),))
    return options_to_json_dict(generate_authentication_options(
        rp_id=rp_id(origin),
        challenge=challenge,
        timeout=CHALLENGE_SECONDS * 1000,
        user_verification=UserVerificationRequirement.REQUIRED,
    ))


def sign_in(db: Database, key: bytes, origin: str, credential: dict[str, Any]) -> str:
    """يُرجع رمز جلسةٍ جديدة، أو يرفع `PasskeyRejected`."""
    challenge = _challenge_of(credential)
    raw_id = _decode(credential["rawId"])
    handle = credential["response"].get("userHandle")
    with db.session() as cursor:
        token = _sign_in(cursor, key, origin, credential, challenge, raw_id,
                         _decode(handle) if handle is not None else None)
    # الرفض بعد المعاملة لا داخلها: داخلها يُلغي استهلاك التحدّي.
    if token is None:
        raise PasskeyRejected
    return token


def _sign_in(cursor, key: bytes, origin: str, credential: dict[str, Any], challenge: bytes,
             raw_id: bytes, handle: bytes | None) -> str | None:
    if not _take(cursor, challenge, "LOGIN") or handle is None:
        return None
    cursor.execute(_LOOKUP, (raw_id,))
    row = cursor.fetchone()
    if row is None or not hmac.compare_digest(handle, user_handle(key, row["user_id"])):
        return None
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(origin),
            expected_origin=origin,
            credential_public_key=bytes(row["public_key"]),
            credential_current_sign_count=row["sign_count"],
            require_user_verification=True,
        )
    except _REJECTED:
        return None
    cursor.execute(_SIGNED_IN, (raw_id, verified.new_sign_count))
    user_id = cursor.fetchone()["user_id"]
    if user_id is None:
        return None
    return auth.open_session(cursor, user_id)


# ── الإضافة: بعد الدخول بكلمة المرور ───────────────────────────────────
def add_options(db: Database, key: bytes, origin: str, user_id: UUID, session: bytes,
                username: str) -> dict[str, Any]:
    """
    خيارات `navigator.credentials.create` بالإنشاء المشروط، لصاحب جلسةٍ فُتحت
    بكلمة المرور الآن (`session`: تجزئة رمز جلسة الطلب). مفتاحٌ يحفظه الجهاز
    (`residentKey: required`) فيُدخَل به بلا اسم، وبلا شهادة جهاز (`attestation: none`).

    `user.name` اسم الدخول كما كُتب في الدخول: يُنشئ Safari المفتاح حين يكون قد ملأ
    للتوّ كلمة المرور لحسابٍ بالاسم نفسه. والقاعدة تطابقه مع الحساب، فلا يُعرض في
    المفتاح اسمٌ لغير صاحبه؛ ولا يُحفظ. واسم العرض اسمه في التطبيق إن وُضع.

    `userVerification: preferred` لا `required`: مع `required` يرفض المتصفّح الإنشاء
    المشروط (`ConstraintError`) حين لا يستطيع التحقّق دون نافذة. ومفاتيحه المحفوظة
    تُسمّى (`excludeCredentials`) فلا يُنشأ المفتاح نفسه مرتين.
    """
    challenge = secrets.token_bytes(_CHALLENGE_BYTES)
    with db.session(user_id) as cursor:
        cursor.execute(_ADD_CHALLENGE, (_digest(challenge), session, auth.login_hmac(key, username)))
        cursor.execute(_NAME)
        name = cursor.fetchone()["name"]
        cursor.execute(_MINE)
        existing = cursor.fetchall()
    return options_to_json_dict(generate_registration_options(
        rp_id=rp_id(origin),
        rp_name=RP_NAME,
        user_id=user_handle(key, user_id),
        user_name=username,
        user_display_name=name or username,
        challenge=challenge,
        timeout=UPGRADE_TIMEOUT_SECONDS * 1000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(
                id=bytes(row["credential_id"]),
                transports=[AuthenticatorTransport(t) for t in row["transports"]] or None,
            )
            for row in existing
        ],
        supported_pub_key_algs=_ALGORITHMS,
    ))


def add(db: Database, origin: str, user_id: UUID, session: bytes, credential: dict[str, Any]) -> None:
    """يحفظ مفتاحاً جديداً لصاحب الجلسة، أو يرفع `PasskeyRejected`."""
    challenge = _challenge_of(credential)
    raw_id = _decode(credential["rawId"])
    transports = sorted(set(credential["response"].get("transports", ())) & _TRANSPORTS)
    with db.session(user_id) as cursor:
        added = _add(cursor, origin, session, credential, challenge, raw_id, transports)
    if not added:
        raise PasskeyRejected


def _add(cursor, origin: str, session: bytes, credential: dict[str, Any], challenge: bytes, raw_id: bytes,
         transports: list[str]) -> bool:
    if not _take(cursor, challenge, "ADD"):
        return False
    try:
        # الإنشاء المشروط بلا حضورٍ ولا تحقّق (انظر رأس الملف): صاحب الحساب أثبته
        # كلمةُ المرور، والقاعدة تفحص جلستها في هذه المعاملة.
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(origin),
            expected_origin=origin,
            require_user_presence=False,
            require_user_verification=False,
            supported_pub_key_algs=_ALGORITHMS,
        )
    except _REJECTED:
        return False
    # المعرّف المعلن هو المعرّف الموقَّع، وكلاهما في حدود ما يُحفظ.
    if (verified.credential_id != raw_id or len(raw_id) > _CREDENTIAL_ID_MAX
            or len(verified.credential_public_key) > _PUBLIC_KEY_MAX):
        return False
    cursor.execute(_ADD, (session, raw_id, verified.credential_public_key, verified.sign_count, transports))
    return bool(cursor.fetchone()["added"])
