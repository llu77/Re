"""
أجسام الطلبات
=============
كل حقلٍ بنوعه الصارم وحدوده، ولا حقل زائد (`extra="forbid"`): «"500"» نصّاً
ليست ميزانية، وحقلٌ لا نعرفه لا يُتجاهل بصمت.

الرقم صارم (`StrictInt`) والنصّ صارم (`StrictStr`)؛ والمعرّف وخيار التعديل
يُحوَّلان من نصّ JSON لأن هذا شكلهما الوحيد فيه.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from eyework.auth import EMAIL_MAX, LOGIN_MAX, LOGIN_MIN, PASSWORD_MAX, PASSWORD_MIN
from eyework.copy_rules import EDIT_NOTE_MAX, MAX_PRESETS, EditPreset
from eyework.professions import Profession

__all__ = [
    "ActivateBody",
    "ApproveBody",
    "BudgetBody",
    "ConfirmBody",
    "DaysBody",
    "EditBody",
    "LoginBody",
    "PasskeyAddBody",
    "PasskeyLoginBody",
    "RegisterBody",
    "SignupCodeBody",
    "RestoreBody",
    "RowVersionBody",
]

RowVersion = Annotated[StrictInt, Field(ge=1, le=2_000_000_000)]
#: شكل رموز التسجيل والتفعيل: 43 حرفاً من base64url (`auth.new_token`).
SignupCode = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginBody(_Body):
    username: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=LOGIN_MAX)]
    password: Annotated[StrictStr, Field(min_length=1, max_length=PASSWORD_MAX)]


class ActivateBody(_Body):
    token: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]
    username: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=LOGIN_MAX)]
    password: Annotated[StrictStr, Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)]


class RegisterBody(_Body):
    """
    الأنواع والأطوال هنا؛ والشكل (الاسم، والبريد، والتاريخ، والعمر) في
    `auth.check_*`، فيعود لكل حقلٍ رمزه ورسالته وتعرف الواجهة أيّ خطوةٍ تُصلَح.
    """

    code: SignupCode
    name: Annotated[StrictStr, Field(min_length=1, max_length=60)]
    birth_date: Annotated[StrictStr, Field(min_length=10, max_length=10)]
    email: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=EMAIL_MAX)]
    password: Annotated[StrictStr, Field(min_length=1, max_length=PASSWORD_MAX)]
    profession: Profession
    #: الموافقة على الإشعار: لا حساب تسجيلٍ بدونها، فلا قيمة غير `true`.
    accept_terms: Literal[True]


class SignupCodeBody(_Body):
    code: SignupCode


# ── مفاتيح المرور ──────────────────────────────────────────────────────
# ما ترسله الواجهة من ردّ الجهاز: بايتاته بترميز base64url بلا حشو، وبالأسماء
# التي تقرؤها py_webauthn. الأطوال حدودٌ للطلب لا للمفتاح: ما في داخلها تفحصه
# المكتبة، وما يُحفظ تحدّه القاعدة.
def _base64url(max_length: int):
    return Annotated[StrictStr, Field(min_length=2, max_length=max_length, pattern=r"^[A-Za-z0-9_-]+$")]


#: معرّف المفتاح حتى 1023 بايتاً ⇒ 1364 حرفاً.
CredentialId = _base64url(1364)
ClientData = _base64url(4096)
AuthenticatorData = _base64url(2048)
Signature = _base64url(2048)
#: معرّف المستخدم حتى 64 بايتاً ⇒ 86 حرفاً.
UserHandle = _base64url(86)
AttestationObject = _base64url(12_000)
Transport = Annotated[StrictStr, Field(pattern=r"^[a-z-]{1,20}$")]


class _AssertionResponse(_Body):
    clientDataJSON: ClientData
    authenticatorData: AuthenticatorData
    signature: Signature
    #: معرّف المستخدم الذي حفظه الجهاز. غيابه رفضٌ في `passkeys.sign_in` كسائر الفشل.
    userHandle: UserHandle | None = None


class _AttestationResponse(_Body):
    clientDataJSON: ClientData
    attestationObject: AttestationObject
    #: ما لا تعرفه py_webauthn منها يُترك ولا يُحفظ.
    transports: Annotated[list[Transport], Field(max_length=8)] = []


class _Credential(_Body):
    id: CredentialId
    rawId: CredentialId
    type: Literal["public-key"]
    authenticatorAttachment: Literal["platform", "cross-platform"] | None = None


class PasskeyLoginBody(_Credential):
    response: _AssertionResponse


class PasskeyAddBody(_Credential):
    response: _AttestationResponse


class RowVersionBody(_Body):
    expected_row_version: RowVersion


class EditBody(RowVersionBody):
    expected_version_id: UUID
    presets: Annotated[list[EditPreset], Field(max_length=MAX_PRESETS)] = []
    note: Annotated[StrictStr, Field(min_length=1, max_length=EDIT_NOTE_MAX)] | None = None


class RestoreBody(RowVersionBody):
    expected_version_id: UUID
    target: Literal["previous", "newest"]


class ApproveBody(RowVersionBody):
    version_id: UUID


class BudgetBody(RowVersionBody):
    budget_sar: StrictInt


class DaysBody(RowVersionBody):
    days: StrictInt


class ConfirmBody(RowVersionBody):
    version_id: UUID
    budget_sar: StrictInt
    days: StrictInt
