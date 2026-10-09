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

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from eyework.auth import EMAIL_MAX, LOGIN_MAX, LOGIN_MIN, PASSWORD_MAX, PASSWORD_MIN
from eyework.copy_rules import EDIT_NOTE_MAX, MAX_PRESETS, EditPreset
from eyework.professions import Profession
from eyework.ui_size import UiSize

__all__ = [
    "ActivateBody",
    "ApproveBody",
    "BudgetBody",
    "ConfirmBody",
    "DaysBody",
    "EditBody",
    "LoginBody",
    "PasskeyAddBody",
    "PasskeyAddOptionsBody",
    "PasskeyLoginBody",
    "RegisterBody",
    "SignupCodeBody",
    "RestoreBody",
    "RowVersionBody",
    "AssistantBody",
    "DecisionBody",
    "ReviewBody",
    "ScreenBody",
    "TermsBody",
    "UiSizeBody",
    # المخزون
    "CategoryBody",
    "CategoryPatchBody",
    "CountBody",
    "CountItemBody",
    "CountLineBody",
    "CountOpenBody",
    "CountPatchBody",
    "CountPostBody",
    "CreditNoteBody",
    "InventorySettingsBody",
    "IssueBody",
    "ItemCreateBody",
    "ItemPatchBody",
    "LineCreateBody",
    "LinePatchBody",
    "OpeningBody",
    "PostBody",
    "PurchaseCreateBody",
    "PurchasePatchBody",
    "RepBody",
    "RepPatchBody",
    "ReturnCreateBody",
    "ReturnLineBody",
    "ReturnPatchBody",
    "ReverseBody",
    "SupplierCreateBody",
    "SupplierPatchBody",
]

RowVersion = Annotated[StrictInt, Field(ge=1, le=2_000_000_000)]
#: شكل رموز التسجيل والتفعيل: 43 حرفاً من base64url (`auth.new_token`).
SignupCode = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]
#: نسخة «قبل أن تبدأ»: تاريخ سريانها (`terms.TERMS_VERSION`).
TermsVersion = Annotated[StrictStr, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]


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

    الرمز غائبٌ في التسجيل المفتوح. والنسخة ما عُرض على صاحب الطلب: إن تغيّرت منذ
    عرضها فلا حساب.
    """

    code: SignupCode | None = None
    name: Annotated[StrictStr, Field(min_length=1, max_length=60)]
    birth_date: Annotated[StrictStr, Field(min_length=10, max_length=10)]
    email: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=EMAIL_MAX)]
    password: Annotated[StrictStr, Field(min_length=1, max_length=PASSWORD_MAX)]
    profession: Profession
    #: طريقة الاستخدام يختارها صاحب الحساب: لا حساب بلا اختيار، والقاعدة تشترطها كذلك.
    ui_size: UiSize
    #: الموافقة على الإشعار: لا حساب تسجيلٍ بدونها، فلا قيمة غير `true`.
    accept_terms: Literal[True]
    terms_version: TermsVersion


class SignupCodeBody(_Body):
    code: SignupCode


class UiSizeBody(_Body):
    ui_size: UiSize


class TermsBody(_Body):
    #: ما عُرض ووافق عليه: يُقبل إن كان النسخة الحالية وحدها.
    terms_version: TermsVersion


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


class PasskeyAddOptionsBody(_Body):
    """اسم الدخول الذي دخل به للتوّ: يُعرض في المفتاح، وتطابقه القاعدة مع الحساب."""

    username: Annotated[StrictStr, Field(min_length=LOGIN_MIN, max_length=LOGIN_MAX)]


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


# ── طبقة الذكاء الاصطناعي ──────────────────────────────────────────────
#: رمز أداةٍ أو نوع موضوع: نظير قيود القاعدة ai_feature_code وai_request_subject_kind.
UpperCode = Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z_]{2,39}$")]
#: بصمة المحتوى كما تُعرض: 64 خانةً ستّ عشرية.
Digest = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class ReviewBody(_Body):
    """ضغطة «راجع»: الأداة، ونوع الموضوع، ومعرّفه، وما رآه صاحبه من رقم الصفّ إن كان له (المواصفة §8.2)."""

    feature: UpperCode
    subject_kind: UpperCode
    subject_id: UUID
    expected_row_version: RowVersion | None = None


class DecisionBody(_Body):
    """
    «عدّل» أو «تابع رغم ذلك» أو «تراجع»، مع بصمة المحتوى الذي عُرضت عليه الملاحظة
    (المواصفة §3.7 و§8.2): بلا بصمةٍ لا قرار، فلا يُسجَّل قرارٌ على محتوىً لم يعد صاحبه يراه.
    """

    choice: Literal["EDIT", "PROCEED", "UNDO"]
    digest: Digest


class ScreenBody(_Body):
    kind: UpperCode
    id: UUID | None = None


class AssistantBody(_Body):
    """سؤالٌ مكتوب أو فهرس سؤالٍ جاهز، واحدٌ منهما لا كلاهما."""

    screen: ScreenBody
    question: Annotated[StrictStr, Field(min_length=1, max_length=400)] | None = None
    ready_question: Annotated[StrictInt, Field(ge=0, le=2)] | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "AssistantBody":
        if (self.question is None) == (self.ready_question is None):
            raise ValueError("سؤالٌ واحد: مكتوبٌ أو جاهز")
        return self


# ── المخزون ────────────────────────────────────────────────────────────
# الأنواع والأطوال هنا؛ والشكل الدقيق (الرقم الضريبي 3…3، الباركود، التاريخ) تفحصه القاعدة
# والخدمة بعد توحيد الأرقام العربية، فيعود لكل قيدٍ رمزه ورسالته (web/errors).
Halalas = Annotated[StrictInt, Field(ge=0, le=100_000_000_000_000)]
UnitPrice = Annotated[StrictInt, Field(ge=0, le=1_000_000_000)]
ItemPrice = Annotated[StrictInt, Field(ge=1, le=1_000_000_000)]
Milli = Annotated[StrictInt, Field(ge=1, le=1_000_000_000)]
CountMilli = Annotated[StrictInt, Field(ge=0, le=1_000_000_000_000)]
InvName = Annotated[StrictStr, Field(min_length=1, max_length=60)]
CategoryName = Annotated[StrictStr, Field(min_length=1, max_length=40)]
DocNo = Annotated[StrictStr, Field(min_length=1, max_length=40)]
InvNote = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Exemption = Annotated[StrictStr, Field(min_length=1, max_length=80)]
VatNumber = Annotated[StrictStr, Field(min_length=15, max_length=15)]
CrNumber = Annotated[StrictStr, Field(min_length=10, max_length=10)]
Phone = Annotated[StrictStr, Field(min_length=10, max_length=13)]
SupplierCode = Annotated[StrictStr, Field(min_length=1, max_length=20)]
Barcode = Annotated[StrictStr, Field(min_length=8, max_length=14)]
Day = Annotated[StrictStr, Field(min_length=10, max_length=10)]
FlagKey = Annotated[StrictStr, Field(pattern=r"^[A-Z_]{3,40}(:[0-9]{1,3})?$")]
VatCategory = Literal["S", "Z", "E", "O"]
Unit = Literal["PIECE", "BOX", "CARTON", "PACK", "PALLET", "KG", "LITRE", "METRE", "SERVICE"]
ItemKind = Literal["STOCK", "SERVICE"]
ReturnReason = Literal["DAMAGED", "WRONG_ITEM", "NOT_AS_SPECIFIED", "EXCESS", "EXPIRED", "SHORT_DELIVERY", "PRICE_ERROR", "OTHER"]
ReversalReason = Literal["DUPLICATE", "WRONG_SUPPLIER", "WRONG_DETAILS", "OTHER"]
IssueReason = Literal["SALE", "USE", "DAMAGE", "OTHER"]
CountReason = Literal["DAMAGE", "EXPIRED", "THEFT_LOSS", "RECORDING_ERROR", "FOUND", "OTHER"]
CountScope = Literal["ALL", "CATEGORY", "LOW", "SELECTED"]


class InventorySettingsBody(_Body):
    cost_includes_vat: StrictBool
    store_name: InvName | None = None
    store_location: Annotated[StrictStr, Field(min_length=1, max_length=120)] | None = None
    #: None عند الإنشاء الأوّل وحده.
    expected_row_version: RowVersion | None = None


class SupplierCreateBody(_Body):
    name: InvName
    vat_number: VatNumber | None = None
    cr_number: CrNumber | None = None
    phone: Phone | None = None
    note: InvNote | None = None


class SupplierPatchBody(_Body):
    expected_row_version: RowVersion
    name: InvName | None = None
    vat_number: VatNumber | None = None
    cr_number: CrNumber | None = None
    phone: Phone | None = None
    note: InvNote | None = None
    is_active: StrictBool | None = None


class RepBody(_Body):
    name: InvName
    mobile: Phone | None = None
    is_default: StrictBool = False


class RepPatchBody(_Body):
    expected_row_version: RowVersion
    name: InvName | None = None
    mobile: Phone | None = None
    is_default: StrictBool | None = None
    is_active: StrictBool | None = None


class CategoryBody(_Body):
    name: CategoryName


class CategoryPatchBody(_Body):
    expected_row_version: RowVersion
    name: CategoryName | None = None
    is_active: StrictBool | None = None


class ItemCreateBody(_Body):
    name: InvName
    kind: ItemKind
    unit: Unit
    price_halalas: ItemPrice
    vat_category: VatCategory = "S"
    vat_exemption_reason: Exemption | None = None
    supplier_code: SupplierCode | None = None
    barcode: Barcode | None = None
    category_id: UUID | None = None
    selling_price_halalas: UnitPrice | None = None
    selling_price_includes_vat: StrictBool = True
    reorder_level_milli: CountMilli | None = None
    target_level_milli: Milli | None = None
    preferred_supplier_id: UUID | None = None
    note: InvNote | None = None


class ItemPatchBody(_Body):
    expected_row_version: RowVersion
    name: InvName | None = None
    kind: ItemKind | None = None
    unit: Unit | None = None
    price_halalas: ItemPrice | None = None
    vat_category: VatCategory | None = None
    vat_exemption_reason: Exemption | None = None
    supplier_code: SupplierCode | None = None
    barcode: Barcode | None = None
    category_id: UUID | None = None
    selling_price_halalas: UnitPrice | None = None
    selling_price_includes_vat: StrictBool | None = None
    reorder_level_milli: CountMilli | None = None
    target_level_milli: Milli | None = None
    preferred_supplier_id: UUID | None = None
    note: InvNote | None = None
    is_active: StrictBool | None = None


class PurchaseCreateBody(_Body):
    supplier_id: UUID | None = None
    rep_id: UUID | None = None
    supplier_invoice_no: DocNo | None = None
    invoice_date: Day | None = None
    received_on: Day | None = None
    delivery_note_no: DocNo | None = None
    prices_include_vat: StrictBool = False
    printed_total_halalas: Halalas | None = None
    printed_vat_halalas: Halalas | None = None
    note: InvNote | None = None


class PurchasePatchBody(PurchaseCreateBody):
    expected_row_version: RowVersion
    prices_include_vat: StrictBool | None = None


class LineCreateBody(_Body):
    expected_row_version: RowVersion
    item_id: UUID
    quantity_milli: Milli
    unit_price_halalas: UnitPrice
    discount_halalas: Halalas = 0
    #: فارغٌ: فئة المنتج.
    vat_category: VatCategory | None = None
    received_quantity_milli: CountMilli | None = None


class LinePatchBody(_Body):
    expected_row_version: RowVersion
    item_id: UUID | None = None
    quantity_milli: Milli | None = None
    unit_price_halalas: UnitPrice | None = None
    discount_halalas: Halalas | None = None
    vat_category: VatCategory | None = None
    received_quantity_milli: CountMilli | None = None


class PostBody(RowVersionBody):
    acknowledged: Annotated[list[FlagKey], Field(max_length=80)] = []


class ReverseBody(RowVersionBody):
    reason: ReversalReason
    note: InvNote | None = None


class ReturnCreateBody(_Body):
    purchase_id: UUID
    rep_id: UUID | None = None


class ReturnPatchBody(_Body):
    expected_row_version: RowVersion
    return_date: Day | None = None
    reason: ReturnReason | None = None
    note: InvNote | None = None
    rep_id: UUID | None = None


class ReturnLineBody(RowVersionBody):
    #: صفرٌ يزيل السطر.
    quantity_milli: CountMilli


class CreditNoteBody(RowVersionBody):
    number: DocNo
    date: Day


class OpeningBody(_Body):
    client_token: UUID
    item_id: UUID
    quantity_milli: Milli
    unit_cost_halalas: UnitPrice
    occurred_on: Day


class IssueBody(_Body):
    client_token: UUID
    item_id: UUID
    quantity_milli: Milli
    reason: IssueReason
    note: InvNote | None = None
    occurred_on: Day


class CountBody(_Body):
    client_token: UUID
    item_id: UUID
    counted_milli: CountMilli
    expected_on_hand_milli: CountMilli
    unit_cost_halalas: UnitPrice | None = None
    reason: CountReason | None = None
    note: InvNote | None = None
    occurred_on: Day


class CountOpenBody(_Body):
    client_token: UUID
    scope: CountScope
    category_id: UUID | None = None
    item_ids: Annotated[list[UUID], Field(max_length=200)] | None = None
    blind: StrictBool = True
    note: InvNote | None = None


class CountPatchBody(RowVersionBody):
    blind: StrictBool | None = None
    note: InvNote | None = None


class CountLineBody(RowVersionBody):
    #: فارغٌ: لم يُعدّ بعد (يمحو ما كُتب).
    counted_milli: CountMilli | None = None
    unit_cost_halalas: UnitPrice | None = None
    reason: CountReason | None = None
    note: InvNote | None = None


class CountItemBody(_Body):
    item_id: UUID


class CountPostBody(RowVersionBody):
    occurred_on: Day
