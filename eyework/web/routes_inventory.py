"""
مسارات بوابة المخزون
====================
تحت `/api/inventory`، لأصحاب مهنة أمين المخزون وحدهم (403 لغيرهم). كل كتابةٍ على
صفٍّ قائم تحمل `expected_row_version` — ما رآه صاحبها — فالضغطة المكرّرة بالعين
تُرفض بـ409 بدل أن تُطبَّق مرتين؛ إلا اثنتين في جلسة الجرد لا تحتاجانه: إضافة منتجٍ إليها
(سطرٌ واحد للمنتج، فالضغطة الثانية 409 `INV_COUNT_LINE_EXISTS`) وتحديث أرصدتها (لا يمسّ
إلا سطراً تحرّك رصيده بعد اللقطة، فالضغطة الثانية لا تغيّر شيئاً). والقراءات (البحث أثناء الكتابة والصفحات) لها
حدّها (`inventory_read`)، والكتابات حدّ `mutation` نفسه.

مستند غيرك ⇒ 404 لا 403: لا يُكشف أنه موجود. ومراجعة سيمبول للمسودة من مسار
المراجعة المشترك (`POST /api/ai/review` بالأداة STOCK_REVIEW) لا من هنا.

كل SQL في `eyework/inventory.py`؛ المسارات لا تمسّ القاعدة.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from eyework import inventory
from eyework.inventory_rules import MAX_PAGE
from eyework.professions import Profession
from eyework.web.deps import enforce, require_profession, require_user
from eyework.web.schemas import (
    CategoryBody,
    CategoryPatchBody,
    CountBody,
    CountItemBody,
    CountLineBody,
    CountOpenBody,
    CountPatchBody,
    CountPostBody,
    CreditNoteBody,
    InventorySettingsBody,
    IssueBody,
    ItemCreateBody,
    ItemPatchBody,
    LineCreateBody,
    LinePatchBody,
    OpeningBody,
    PostBody,
    PurchaseCreateBody,
    PurchasePatchBody,
    RepBody,
    RepPatchBody,
    ReturnCreateBody,
    ReturnLineBody,
    ReturnPatchBody,
    ReverseBody,
    RowVersionBody,
    SupplierCreateBody,
    SupplierPatchBody,
)

__all__ = ["router"]

#: رقم السطر كما في القاعدة (inv_line_no_range): لا رقمٌ يخرج عن smallint فيصير خطأ خادم.
LineNo = Annotated[int, Path(ge=1, le=999)]

router = APIRouter(prefix="/api/inventory", dependencies=[Depends(require_profession(Profession.STOREKEEPER))])

Page = Query(1, ge=1, le=MAX_PAGE)
Size = Query(20, ge=4, le=20)


def _read(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.inventory_read, str(user_id))


def _write(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.mutation, str(user_id))


def _db(request: Request):
    return request.app.state.db


# ── الملخّص والإعدادات ────────────────────────────────────────────────
@router.get("/summary")
def summary(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.summary(_db(request), user_id)


@router.get("/settings")
def get_settings(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_settings(_db(request), user_id)


@router.put("/settings")
def put_settings(body: InventorySettingsBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.put_settings(_db(request), user_id, body.cost_includes_vat, body.store_name, body.store_location,
                                  body.expected_row_version)


# ── المورّدون ومندوبوهم ────────────────────────────────────────────────
@router.get("/suppliers")
def list_suppliers(request: Request, q: str | None = Query(None, max_length=60), page: int = Page, size: int = Size,
                   archived: bool = False, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_suppliers(_db(request), user_id, q, page, size, archived)


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(body: SupplierCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_supplier(_db(request), user_id, body.name, body.vat_number, body.cr_number, body.phone, body.note)


@router.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_supplier(_db(request), user_id, supplier_id)


@router.patch("/suppliers/{supplier_id}")
def patch_supplier(supplier_id: UUID, body: SupplierPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_supplier(_db(request), user_id, supplier_id, body.expected_row_version, fields)


@router.post("/suppliers/{supplier_id}/reps", status_code=status.HTTP_201_CREATED)
def create_rep(supplier_id: UUID, body: RepBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_rep(_db(request), user_id, supplier_id, body.name, body.mobile, body.is_default)


@router.patch("/suppliers/{supplier_id}/reps/{rep_id}")
def patch_rep(supplier_id: UUID, rep_id: UUID, body: RepPatchBody, request: Request,
              user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_rep(_db(request), user_id, supplier_id, rep_id, body.expected_row_version, fields)


# ── التصنيفات ──────────────────────────────────────────────────────────
@router.get("/categories")
def list_categories(request: Request, archived: bool = False, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return {"items": inventory.list_categories(_db(request), user_id, archived)}


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_category(_db(request), user_id, body.name)


@router.patch("/categories/{category_id}")
def patch_category(category_id: UUID, body: CategoryPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_category(_db(request), user_id, category_id, body.expected_row_version, fields)


# ── المنتجات ───────────────────────────────────────────────────────────
@router.get("/items")
def list_items(request: Request, q: str | None = Query(None, max_length=60),
               filter: Literal["all", "low", "service", "archived", "uncounted"] = "all",
               category_id: UUID | None = None, page: int = Page, size: int = Size,
               user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_items(_db(request), user_id, q, filter, category_id, page, size)


@router.get("/items/search")
def search_items(request: Request, q: str = Query(..., min_length=1, max_length=60), purchase_id: UUID | None = None,
                 user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.search_items(_db(request), user_id, q, purchase_id)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_item(_db(request), user_id, body.model_dump())


@router.get("/items/{item_id}")
def get_item(item_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_item(_db(request), user_id, item_id)


@router.get("/items/{item_id}/movements")
def item_movements(item_id: UUID, request: Request, page: int = Page, size: int = Size,
                   user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.item_movements(_db(request), user_id, item_id, page, size)


@router.patch("/items/{item_id}")
def patch_item(item_id: UUID, body: ItemPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_item(_db(request), user_id, item_id, body.expected_row_version, fields)


# ── فواتير الشراء ──────────────────────────────────────────────────────
@router.get("/purchases")
def list_purchases(request: Request, status_name: str | None = Query(None, alias="status", max_length=10),
                   q: str | None = Query(None, max_length=60), page: int = Page, size: int = Size,
                   user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_purchases(_db(request), user_id, status_name, q, page, size)


@router.post("/purchases", status_code=status.HTTP_201_CREATED)
def create_purchase(body: PurchaseCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_purchase(_db(request), user_id, body.model_dump(exclude_unset=True))


@router.get("/purchases/{purchase_id}")
def get_purchase(purchase_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_purchase(_db(request), user_id, purchase_id)


@router.patch("/purchases/{purchase_id}")
def patch_purchase(purchase_id: UUID, body: PurchasePatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_purchase(_db(request), user_id, purchase_id, body.expected_row_version, fields)


@router.post("/purchases/{purchase_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard_purchase(purchase_id: UUID, body: RowVersionBody, request: Request,
                     user_id: UUID = Depends(require_user)) -> Response:
    """نبذ المسودة. POST لا DELETE: الطلب بلا جسمٍ لا يحمل طوله فيرفضه الغلاف."""
    _write(request, user_id)
    inventory.discard_purchase(_db(request), user_id, purchase_id, body.expected_row_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/purchases/{purchase_id}/lines", status_code=status.HTTP_201_CREATED)
def add_line(purchase_id: UUID, body: LineCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude={"expected_row_version"})
    return inventory.add_line(_db(request), user_id, purchase_id, body.expected_row_version, fields)


@router.patch("/purchases/{purchase_id}/lines/{line_no}")
def patch_line(purchase_id: UUID, line_no: LineNo, body: LinePatchBody, request: Request,
               user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_line(_db(request), user_id, purchase_id, line_no, body.expected_row_version, fields)


@router.post("/purchases/{purchase_id}/lines/{line_no}/remove")
def remove_line(purchase_id: UUID, line_no: LineNo, body: RowVersionBody, request: Request,
                user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.remove_line(_db(request), user_id, purchase_id, line_no, body.expected_row_version)


@router.get("/purchases/{purchase_id}/flags")
def purchase_flags(purchase_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.purchase_flags(_db(request), user_id, purchase_id)


@router.post("/purchases/{purchase_id}/post")
def post_purchase(purchase_id: UUID, body: PostBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.post_purchase(_db(request), user_id, purchase_id, body.expected_row_version, list(body.acknowledged))


@router.post("/purchases/{purchase_id}/reverse")
def reverse_purchase(purchase_id: UUID, body: ReverseBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.reverse_purchase(_db(request), user_id, purchase_id, body.expected_row_version, body.reason, body.note)


# ── المرتجعات ──────────────────────────────────────────────────────────
@router.get("/returns")
def list_returns(request: Request, status_name: str | None = Query(None, alias="status", max_length=10),
                 awaiting_credit_note: bool = False, page: int = Page, size: int = Size,
                 user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_returns(_db(request), user_id, status_name, awaiting_credit_note, page, size)


@router.post("/returns", status_code=status.HTTP_201_CREATED)
def create_return(body: ReturnCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.create_return(_db(request), user_id, body.purchase_id, body.rep_id)


@router.get("/returns/{return_id}")
def get_return(return_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_return(_db(request), user_id, return_id)


@router.patch("/returns/{return_id}")
def patch_return(return_id: UUID, body: ReturnPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_return(_db(request), user_id, return_id, body.expected_row_version, fields)


@router.post("/returns/{return_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard_return(return_id: UUID, body: RowVersionBody, request: Request,
                   user_id: UUID = Depends(require_user)) -> Response:
    _write(request, user_id)
    inventory.discard_return(_db(request), user_id, return_id, body.expected_row_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/returns/{return_id}/lines/{line_no}")
def put_return_line(return_id: UUID, line_no: LineNo, body: ReturnLineBody, request: Request,
                    user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.put_return_line(_db(request), user_id, return_id, line_no, body.expected_row_version, body.quantity_milli)


@router.get("/returns/{return_id}/flags")
def return_flags(return_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.return_flags(_db(request), user_id, return_id)


@router.post("/returns/{return_id}/post")
def post_return(return_id: UUID, body: PostBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.post_return(_db(request), user_id, return_id, body.expected_row_version, list(body.acknowledged))


@router.put("/returns/{return_id}/credit-note")
def put_credit_note(return_id: UUID, body: CreditNoteBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.put_credit_note(_db(request), user_id, return_id, body.expected_row_version, body.number, body.date)


# ── السندات ────────────────────────────────────────────────────────────
def _voucher_status(view: dict) -> int:
    return status.HTTP_200_OK if view["replayed"] else status.HTTP_201_CREATED


@router.post("/stock/opening")
def opening(body: OpeningBody, request: Request, response: Response, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    view = inventory.stock_voucher(_db(request), user_id, "OPENING", body.model_dump())
    response.status_code = _voucher_status(view)
    return view


@router.post("/stock/issue")
def issue(body: IssueBody, request: Request, response: Response, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    view = inventory.stock_voucher(_db(request), user_id, "ISSUE", body.model_dump())
    response.status_code = _voucher_status(view)
    return view


@router.post("/stock/count")
def count(body: CountBody, request: Request, response: Response, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump()
    fields["quantity_milli"] = fields.pop("counted_milli")
    view = inventory.stock_voucher(_db(request), user_id, "COUNT", fields)
    response.status_code = _voucher_status(view)
    return view


@router.get("/vouchers")
def list_vouchers(request: Request, page: int = Page, size: int = Size, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_vouchers(_db(request), user_id, page, size)


# ── جلسات الجرد ────────────────────────────────────────────────────────
@router.get("/counts")
def list_counts(request: Request, page: int = Page, size: int = Size, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.list_counts(_db(request), user_id, page, size)


@router.post("/counts")
def open_count(body: CountOpenBody, request: Request, response: Response, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    view = inventory.open_count(_db(request), user_id, body.client_token, body.scope, body.category_id, body.item_ids,
                                body.blind, body.note)
    response.status_code = status.HTTP_200_OK if view["replayed"] else status.HTTP_201_CREATED
    return view


@router.get("/counts/{session_id}")
def get_count(session_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.get_count(_db(request), user_id, session_id)


@router.patch("/counts/{session_id}")
def patch_count(session_id: UUID, body: CountPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    fields = body.model_dump(exclude_unset=True, exclude={"expected_row_version"})
    return inventory.patch_count(_db(request), user_id, session_id, body.expected_row_version, fields)


@router.put("/counts/{session_id}/lines/{item_id}")
def set_count_line(session_id: UUID, item_id: UUID, body: CountLineBody, request: Request,
                   user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.set_count_line(_db(request), user_id, session_id, item_id, body.expected_row_version,
                                    body.counted_milli, body.unit_cost_halalas, body.reason, body.note,
                                    "note" in body.model_fields_set)


@router.post("/counts/{session_id}/items", status_code=status.HTTP_201_CREATED)
def add_count_item(session_id: UUID, body: CountItemBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.add_count_item(_db(request), user_id, session_id, body.item_id)


@router.post("/counts/{session_id}/refresh")
def refresh_count(session_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.refresh_count(_db(request), user_id, session_id)


@router.post("/counts/{session_id}/post")
def post_count(session_id: UUID, body: CountPostBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.post_count(_db(request), user_id, session_id, body.expected_row_version, body.occurred_on)


@router.post("/counts/{session_id}/cancel")
def cancel_count(session_id: UUID, body: CountPatchBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return inventory.cancel_count(_db(request), user_id, session_id, body.expected_row_version)


# ── المصروفات وحاسبة الضريبة ───────────────────────────────────────────
@router.get("/expenses")
def expenses(request: Request, from_day: str = Query(..., alias="from", min_length=10, max_length=10),
             to_day: str = Query(..., alias="to", min_length=10, max_length=10), page: int = Page, size: int = Size,
             user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.expenses(_db(request), user_id, from_day, to_day, page, size)


@router.get("/expenses/months")
def expense_months(request: Request, year: int = Query(..., ge=2000, le=2100), user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.expense_months(_db(request), user_id, year)


@router.get("/tools/vat")
def vat_tool(request: Request, amount_halalas: int = Query(..., ge=0, le=100_000_000_000_000),
             basis: Literal["net", "gross"] = "net", category: Literal["S", "Z", "E", "O"] = "S",
             user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return inventory.vat_tool(amount_halalas, basis, category)
