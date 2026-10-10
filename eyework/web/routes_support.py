"""
مسارات مكتب الدعم الفني
=======================
تحت `/api/support`، لأصحاب مهنة الدعم الفني وحدهم (403 لغيرهم). كل كتابةٍ على تذكرةٍ أو
مقالةٍ قائمة تحمل `expected_row_version`، والإنشاء والرسالة والردّ تحمل `client_token`:
الضغطة المكرّرة بالعين تُرجع ما أُنشئ أولاً بدل أن تُنشئ ثانياً.

**حاجزان قبل كلام العملاء وسيمبول.** ما يأخذ كلام عميلٍ أو يستدعي سيمبول يطلب الموافقة على
نسخة إشعار المكتب الحالية (409 NOTICE)؛ وما يستدعي سيمبول يطلب أيضاً الموافقة على «قبل أن
تبدأ» (403 TERMS). والقاعدة ترفض كلام العملاء لمن لم يوافق على الإشعار قطّ.

**مراجعة الردّ والمقالة** من مسار المراجعة المشترك (`POST /api/ai/review` بالأداتين
SUPPORT_REPLY_REVIEW وSUPPORT_ARTICLE_REVIEW) لا من هنا، وقرار «عدّل/تابع» من مسار القرار
المشترك.

كل SQL في `eyework/support.py`؛ المسارات لا تمسّ القاعدة.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from eyework import support, support_notice
from eyework.professions import Profession
from eyework.web.deps import enforce, require_current_terms, require_profession, require_user
from eyework.web.schemas import (
    ArticleCreateBody,
    ArticleNeedsReviewBody,
    ArticlePublishBody,
    ArticleStateBody,
    ArticleVersionBody,
    ClassifyBody,
    ConfirmReplyBody,
    DraftRequestBody,
    EscalateBody,
    EscalationReturnBody,
    FlagActionBody,
    FollowUpBody,
    MaskPreviewBody,
    MessageBody,
    NoticeBody,
    RejectDraftBody,
    ReleaseBody,
    ReplyBody,
    ResolveBody,
    RowVersionBody,
    SupportSettingsBody,
    TicketBody,
)

__all__ = ["router"]

router = APIRouter(prefix="/api/support", dependencies=[Depends(require_profession(Profession.SUPPORT))])

Page = Query(1, ge=1, le=support.MAX_PAGE)
Size = Query(support.PAGE_SIZE, ge=2, le=support.PAGE_SIZE)


def _db(request: Request):
    return request.app.state.db


def _read(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.support_read, str(user_id))


def _write(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.mutation, str(user_id))


def _paste(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.mutation, str(user_id))
    enforce(request.app.state.limiters.support_paste, str(user_id))


def _ai(request: Request, user_id: UUID) -> None:
    enforce(request.app.state.limiters.mutation, str(user_id))
    enforce(request.app.state.limiters.ai, str(user_id))


def require_support_notice(request: Request, user_id: UUID = Depends(require_user)) -> UUID:
    """النسخة الحالية من إشعار المكتب (أو أحدث) قبل كلام العملاء وقبل سيمبول."""
    if not support_notice.is_current(support.notice_version(_db(request), user_id)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail={"code": "NOTICE", "detail": "اقرأ إشعار مكتب الدعم ووافق عليه أولاً."})
    return user_id


def _ai_ready(request: Request, user_id: UUID = Depends(require_current_terms)) -> UUID:
    """ما يستدعي سيمبول: «قبل أن تبدأ» ثم إشعار المكتب."""
    return require_support_notice(request, user_id)


# ── الرئيسية والطوابير ───────────────────────────────────────────────────
@router.get("/home")
def home(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.home(_db(request), user_id)


@router.get("/decide")
def decide(request: Request, page: int = Page, size: int = Size, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.decide_queue(_db(request), user_id, page, size)


@router.get("/tickets")
def tickets(request: Request, view: Literal["open", "pending", "escalated", "resolved", "closed"] = Query("open"),
            page: int = Page, size: int = Size, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.list_tickets(_db(request), user_id, view, page, size)


# ── اللصق والتذكرة ──────────────────────────────────────────────────────
@router.post("/mask-preview")
def mask_preview(body: MaskPreviewBody, request: Request, user_id: UUID = Depends(require_support_notice)) -> dict:
    _paste(request, user_id)
    return support.mask_preview(body.text)


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketBody, request: Request, response: Response,
                  user_id: UUID = Depends(require_support_notice)) -> dict:
    _paste(request, user_id)
    view, created = support.create_ticket(_db(request), user_id, body.model_dump())
    if not created:
        response.status_code = status.HTTP_200_OK
    return view


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.get_ticket(_db(request), user_id, ticket_id)


@router.get("/tickets/{ticket_id}/events")
def ticket_events(ticket_id: UUID, request: Request, page: int = Page, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.events(_db(request), user_id, ticket_id, page)


@router.post("/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
def add_message(ticket_id: UUID, body: MessageBody, request: Request,
                user_id: UUID = Depends(require_support_notice)) -> dict:
    _paste(request, user_id)
    return support.add_message(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/follow-up", status_code=status.HTTP_201_CREATED)
def follow_up(ticket_id: UUID, body: FollowUpBody, request: Request,
              user_id: UUID = Depends(require_support_notice)) -> dict:
    _paste(request, user_id)
    return support.follow_up(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/classification")
def classify(ticket_id: UUID, body: ClassifyBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    # الموضوع يتغيّر حين يُرسل (null يمحوه)؛ و«اعتمد المقترح» بلا موضوعٍ يُبقيه كما هو.
    return support.classify(_db(request), user_id, ticket_id, body.model_dump(exclude_unset=True))


# ── المسودة ─────────────────────────────────────────────────────────────
@router.post("/tickets/{ticket_id}/drafts", status_code=status.HTTP_201_CREATED)
def request_draft(ticket_id: UUID, body: DraftRequestBody, request: Request, user_id: UUID = Depends(_ai_ready)) -> dict:
    _ai(request, user_id)
    return support.request_draft(_db(request), request.app.state.review_runner, user_id, ticket_id, body.model_dump())


@router.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: UUID, body: RejectDraftBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.reject_draft(_db(request), user_id, draft_id, body.reason, body.note)


# ── الردّ ───────────────────────────────────────────────────────────────
@router.post("/tickets/{ticket_id}/replies", status_code=status.HTTP_201_CREATED)
def prepare_reply(ticket_id: UUID, body: ReplyBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.prepare_reply(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/flags/{flag_id}")
def ack_flag(flag_id: UUID, body: FlagActionBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    if (body.action == "DISMISSED") != (body.reason is not None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"code": "INVALID", "detail": "تجاوز التنبيه يحتاج سببه، والأخذ به لا يحتاج."})
    return support.ack_flag(_db(request), user_id, flag_id, body.action, body.reason)


@router.post("/replies/{reply_id}/release")
def release_reply(reply_id: UUID, body: ReleaseBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.release_reply(_db(request), user_id, reply_id, body.via, body.body_sha256)


@router.post("/replies/{reply_id}/confirm")
def confirm_reply(reply_id: UUID, body: ConfirmReplyBody, request: Request,
                  user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.confirm_reply(_db(request), user_id, reply_id, body.sent)


# ── التصعيد والحلّ ──────────────────────────────────────────────────────
@router.post("/tickets/{ticket_id}/escalate")
def escalate(ticket_id: UUID, body: EscalateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.escalate(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/escalation-return")
def return_escalation(ticket_id: UUID, body: EscalationReturnBody, request: Request,
                      user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.return_escalation(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/resolve")
def resolve(ticket_id: UUID, body: ResolveBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.resolve(_db(request), user_id, ticket_id, body.model_dump())


@router.post("/tickets/{ticket_id}/reopen")
def reopen(ticket_id: UUID, body: RowVersionBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.reopen(_db(request), user_id, ticket_id, body.expected_row_version)


# ── قاعدة المعرفة ───────────────────────────────────────────────────────
@router.get("/kb")
def list_articles(request: Request,
                  view: Literal["published", "attention", "drafts", "archived"] = Query("published"),
                  q: str | None = Query(None, max_length=200), page: int = Page, size: int = Size,
                  user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    if q:
        enforce(request.app.state.limiters.support_search, str(user_id))
    return support.list_articles(_db(request), user_id, view, q, page, size)


@router.get("/kb/{article_id}")
def get_article(article_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.get_article(_db(request), user_id, article_id)


@router.post("/kb", status_code=status.HTTP_201_CREATED)
def create_article(body: ArticleCreateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.create_article(_db(request), user_id, body.model_dump())


@router.post("/kb/{article_id}/versions")
def add_version(article_id: UUID, body: ArticleVersionBody, request: Request,
                user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.add_version(_db(request), user_id, article_id, body.model_dump())


@router.post("/kb/{article_id}/publish")
def publish(article_id: UUID, body: ArticlePublishBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.publish(_db(request), user_id, article_id, body.expected_row_version, body.version)


@router.post("/kb/{article_id}/state")
def set_state(article_id: UUID, body: ArticleStateBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.set_article_state(_db(request), user_id, article_id, body.expected_row_version, body.state)


@router.post("/kb/{article_id}/needs-review")
def needs_review(article_id: UUID, body: ArticleNeedsReviewBody, request: Request,
                 user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    return support.mark_review(_db(request), user_id, article_id, body.expected_row_version, body.needs_review)


@router.get("/improve")
def improve(request: Request, days: int = Query(30, ge=1, le=90), user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.improve(_db(request), user_id, days)


# ── الإعدادات والإشعار والعبارات ─────────────────────────────────────────
@router.get("/settings")
def get_settings(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.get_settings(_db(request), user_id)


@router.put("/settings")
def save_settings(body: SupportSettingsBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _write(request, user_id)
    sla = None if body.sla is None else {k: v.model_dump() for k, v in body.sla.items()}
    # التوقيع يتغيّر حين يُرسل وحده (null يمحوه)؛ وحفظ أهداف الوقت وحدها لا يمسّه.
    signature = body.signature if "signature" in body.model_fields_set else support.KEEP
    return support.save_settings(_db(request), user_id, signature, sla)


@router.post("/notice", status_code=status.HTTP_204_NO_CONTENT)
def accept_notice(body: NoticeBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    _write(request, user_id)
    support.accept_notice(_db(request), user_id, body.version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/phrases")
def phrases(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    _read(request, user_id)
    return support.phrases()
