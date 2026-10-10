"""
مكتب الدعم الفني: الخدمة
========================
كل SQL الدعم هنا، بهوية الجلسة وحدها (`db.session(user_id)`): القاعدة تقرأ صاحب الطلب من
`ew_current_user()`، فلا معرّف مستخدمٍ في أيّ عبارة. الكتابة كلّها دوالّ `ew_support_*`
و`ew_kb_*` في 0011، وما يُقرأ تقرؤه سياسات RLS لصاحبه وحده.

**ما يصل القاعدة من كلام العميل محذوفٌ قبلها** (`support_rules.mask`): البريد والروابط والأرقام
الطويلة؛ والقاعدة ترفض ما بقي منها.

**المسودة ثلاث معاملات** كما في الحملة: البدء (صفٌّ في الدفتر تحت كل السقوف، والتذكرة
ومقالاتها تُقرأ فيه)، ثم الاستدعاء بلا معاملةٍ مفتوحة، ثم التسجيل (المسودة واقتباساتها وإغلاق
الصفّ في معاملةٍ واحدة). وما فشل تسجيله يُغلق في رابعة بنتيجته: رسالةٌ وصلت أثناء الكتابة
`DISCARDED`، وجوابٌ رفضته فحوص القاعدة `OUTPUT_INVALID` (دُفع ثمنه فيُحسب).

**مراجعة سيمبول للردّ وللمقالة** عبر المراجِع المشترك (`reviewer.FEATURES`): بصمة الردّ بصمة
النصّ الذي يُنسخ، وبصمة المقالة بصمة آخر نسخها. و«انسخ الردّ» يمرّ ببوّابة القاعدة
(`ew_ai_gate`): ملاحظةٌ لم يُبتّ فيها تحجزه، وغير ذلك لا يحجز.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from contextlib import contextmanager
from typing import Iterator, Mapping, Sequence
from uuid import UUID

from psycopg import errors as pg_errors

from eyework import ai_log, assistant, reviewer, support_notice
from eyework import support_prompt as prompt
from eyework import support_rules as rules
from eyework.db import Database
from eyework.grounding import Article
from eyework.professions import Profession
from eyework.prompt_kit import ModelReply
from eyework.reviewer import ReviewFeature, ReviewRunner, Snapshot
from eyework.service_errors import Conflict, Invalid, NotFound

__all__ = [
    "ARTICLE_FEATURE",
    "REPLY_FEATURE",
    "SupportAiFailure",
    "accept_notice",
    "ack_flag",
    "add_message",
    "add_version",
    "classify",
    "confirm_reply",
    "create_article",
    "create_ticket",
    "decide_queue",
    "escalate",
    "events",
    "follow_up",
    "get_article",
    "get_settings",
    "get_ticket",
    "home",
    "improve",
    "list_articles",
    "list_tickets",
    "mark_review",
    "mask_preview",
    "phrases",
    "prepare_reply",
    "publish",
    "reject_draft",
    "release_reply",
    "reopen",
    "request_draft",
    "resolve",
    "return_escalation",
    "save_settings",
    "set_article_state",
]

PAGE_SIZE = 20
#: أحجام صفحات القوائم: 2 و3 للحجم الكبير، و10 و20 للعادي (العميل يطلب ما يعرضه الجدول بالضبط).
PAGE_SIZES = (2, 3, 4, 5, 10, 20)
MAX_PAGE = 500
TICKET_GONE = "التذكرة غير موجودة."
ARTICLE_GONE = "المقالة غير موجودة."
REPLY_GONE = "الردّ غير موجود."
FLAG_GONE = "التنبيه غير موجود."
DRAFT_GONE = "المسودة غير موجودة."
ARTICLE_STALE = "تغيّرت المقالة منذ عرضها. راجعها مرة أخرى."
#: المقالات التي يُبحث عنها لكل مسودة، ونصّ البحث من رسالة العميل الأخيرة.
SEARCH_LIMIT = 5
SEARCH_CHARS = 200
KB_IDS_MAX = 3


class SupportAiFailure(Exception):
    """استدعاءٌ لسيمبول لم يُنتج شيئاً: النتيجة (REFUSED، OUTPUT_INVALID، UPSTREAM_*، DOWN، SLOTS)."""

    def __init__(self, outcome: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(outcome)
        self.outcome = outcome
        self.retry_after_seconds = retry_after_seconds


# ── أدوات صغيرة ──────────────────────────────────────────────────────────
def _rows(cursor, statement: str, params: tuple = ()) -> list[dict]:
    cursor.execute(statement, params)
    return [dict(row) for row in cursor.fetchall()]


def _one(cursor, statement: str, params: tuple = ()) -> dict | None:
    cursor.execute(statement, params)
    row = cursor.fetchone()
    return None if row is None else dict(row)


def _iso(value) -> str | None:
    return None if value is None else value.isoformat()


def _page(page: int) -> int:
    if not 1 <= page <= MAX_PAGE:
        raise Invalid("PAGE", field="page")
    return page


def _size(size: int) -> int:
    if size not in PAGE_SIZES:
        raise Invalid("PAGE", field="size")
    return size


def _paged(rows: list[dict], items: list, page: int, total: int | None = None, size: int = PAGE_SIZE) -> dict:
    total = rows[0]["total"] if rows else (total or 0)
    return {"items": items, "page": page, "pages": max(1, -(-total // size)), "total": total}


@contextmanager
def _ticket_errors(gone: str = TICKET_GONE) -> Iterator[None]:
    """`no_data_found` من دوالّ القاعدة: الصفّ ليس لصاحب الجلسة أو لم يعد موجوداً."""
    try:
        yield
    except pg_errors.NoDataFound as error:
        raise NotFound("NOT_FOUND", gone) from error


def _masked(text: str, *, field: str = "text", limit: int = 4000) -> tuple[str, int]:
    """نصٌّ من كلام العميل أو الموظف بعد الحذف، أو `Invalid` إن فرغ أو طال."""
    masked, counts = rules.mask(text)
    if not 1 <= len(masked) <= limit:
        raise Invalid("TEXT" if field == "text" else "NOTE", field=field)
    return masked, min(500, sum(counts.values()))


def _note(text: str | None, field: str, low: int, high: int) -> str | None:
    """ملاحظةٌ قصيرة في سطرٍ (أو أسطر) بعد الحذف."""
    if text is None or not text.strip():
        return None
    masked, _ = rules.mask(text)
    if not low <= len(masked) <= high:
        raise Invalid("NOTE", field=field)
    return masked


# ── الطابور ───────────────────────────────────────────────────────────────
_TICKET_COLUMNS = """
SELECT t.id, t.number, t.status, t.priority, t.category, t.channel, t.customer_label, t.subject, t.row_version,
       t.created_at, t.updated_at, t.first_reply_due_at, t.first_replied_at, t.resolve_minutes, t.wait_seconds,
       t.clock_since, t.resolved_at, t.closed_at, t.texts_purged_at, t.escalation_target, t.resolution,
       t.close_reason, t.follow_up_of, now() AS now,
       (SELECT left(m.body, 140) FROM support_messages m
         WHERE m.ticket_id = t.id AND m.author = 'CUSTOMER' ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS preview,
       (SELECT m.id FROM support_messages m
         WHERE m.ticket_id = t.id AND m.author = 'CUSTOMER' ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_customer,
       d.id AS draft_id, d.based_on_message_id AS draft_based_on, d.result AS draft_result, d.body AS draft_body,
       d.rejected_at AS draft_rejected_at, d.suggested_priority,
       (SELECT r.state FROM support_replies r WHERE r.ticket_id = t.id AND r.state IN ('READY', 'RELEASED')) AS live_state,
       (SELECT count(*) FROM support_flags f JOIN support_replies r ON r.id = f.reply_id
         WHERE f.ticket_id = t.id AND f.state = 'OPEN' AND r.state = 'READY') AS open_flags
  FROM support_tickets t
  LEFT JOIN LATERAL (SELECT * FROM support_drafts x WHERE x.ticket_id = t.id ORDER BY x.seq DESC LIMIT 1) d ON true
"""
#: «بانتظار قراري»: مفتوحةٌ أمامها مسودةٌ لآخر رسالة لم يُقرَّر فيها، أو ردٌّ جاهزٌ لم يُؤكَّد.
_DECIDE_WHERE = """
 WHERE t.status IN ('NEW', 'OPEN', 'ESCALATED')
   AND (EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id AND r.state IN ('READY', 'RELEASED'))
        OR (d.id IS NOT NULL AND d.rejected_at IS NULL
            AND d.based_on_message_id = (SELECT m.id FROM support_messages m WHERE m.ticket_id = t.id
                                            AND m.author = 'CUSTOMER' ORDER BY m.created_at DESC, m.id DESC LIMIT 1)
            AND NOT EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id AND r.draft_id = d.id
                              AND r.state = 'SENT')))
"""
_VIEWS = {
    "open": "t.status IN ('NEW', 'OPEN')",
    "pending": "t.status = 'PENDING'",
    "escalated": "t.status = 'ESCALATED'",
    "resolved": "t.status = 'RESOLVED'",
    "closed": "t.status = 'CLOSED'",
}
_ORDER = """
 ORDER BY CASE t.priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'NORMAL' THEN 2 ELSE 3 END,
          t.first_reply_due_at, t.number
"""
_COUNTS = """
SELECT (SELECT count(*) FROM support_tickets t
          LEFT JOIN LATERAL (SELECT * FROM support_drafts x WHERE x.ticket_id = t.id ORDER BY x.seq DESC LIMIT 1) d ON true
         WHERE t.status IN ('NEW', 'OPEN', 'ESCALATED')
           AND (EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id AND r.state IN ('READY', 'RELEASED'))
                OR (d.id IS NOT NULL AND d.rejected_at IS NULL
                    AND d.based_on_message_id = (SELECT m.id FROM support_messages m WHERE m.ticket_id = t.id
                                                    AND m.author = 'CUSTOMER' ORDER BY m.created_at DESC, m.id DESC LIMIT 1)
                    AND NOT EXISTS (SELECT 1 FROM support_replies r WHERE r.ticket_id = t.id AND r.draft_id = d.id
                                      AND r.state = 'SENT')))) AS decide,
       (SELECT count(*) FROM support_tickets WHERE status IN ('NEW', 'OPEN')) AS open,
       (SELECT count(*) FROM support_tickets WHERE status = 'PENDING') AS pending,
       (SELECT count(*) FROM support_tickets WHERE status = 'ESCALATED') AS escalated,
       (SELECT count(*) FROM kb_articles WHERE needs_review) AS kb_attention
"""
_SETTINGS = "SELECT signature, notice_version FROM support_settings"
_ENSURE_SETTINGS = "SELECT ew_support_close_due() AS closed"


def _sla(row: Mapping) -> dict:
    """زمن الخدمة من أوقات القاعدة: أول ردٍّ حتى يُردّ، ثم الحلّ؛ والساعة متوقّفة في PENDING."""
    now = row["now"]
    if row["status"] in ("RESOLVED", "CLOSED"):
        return {"kind": "RESOLVE", "state": "MET", "minutes": None}
    if row["first_replied_at"] is None:
        due = row["first_reply_due_at"]
        span = max(1.0, (due - row["created_at"]).total_seconds())
        left = (due - now).total_seconds()
        kind = "FIRST_REPLY"
    else:
        running = row["wait_seconds"] + (0 if row["clock_since"] is None else (now - row["clock_since"]).total_seconds())
        span = max(1.0, row["resolve_minutes"] * 60.0)
        left = span - running
        kind = "RESOLVE"
    if row["clock_since"] is None:
        return {"kind": kind, "state": "PAUSED", "minutes": None}
    if left < 0:
        return {"kind": kind, "state": "BREACHED", "minutes": int(-left // 60)}
    return {"kind": kind, "state": "DUE_SOON" if left <= span / 4 else "ON_TRACK", "minutes": int(left // 60)}


def _ticket_row(row: Mapping) -> dict:
    current_draft = (row["draft_id"] is not None and row["draft_rejected_at"] is None
                     and row["draft_based_on"] == row["last_customer"])
    return {
        "id": str(row["id"]), "number": row["number"], "status": row["status"], "priority": row["priority"],
        "category": row["category"], "channel": row["channel"], "customer_label": row["customer_label"],
        "subject": row["subject"], "preview": row["preview"], "sla": _sla(row),
        "badges": {
            "draft_ready": current_draft and row["draft_result"] == "DRAFT",
            "awaiting_confirmation": row["live_state"] == "RELEASED",
            "reply_ready": row["live_state"] == "READY",
            "open_flags": row["open_flags"],
            "suggested_priority": row["suggested_priority"],
        },
        "row_version": row["row_version"], "updated_at": _iso(row["updated_at"]),
    }


def home(db: Database, user_id: UUID) -> dict:
    """العدّادات والإشعار. الإغلاق الآلي لصاحب الجلسة يجري أولاً (المحلولة بعد أربعة أيام)."""
    with db.session(user_id) as cursor:
        cursor.execute(_ENSURE_SETTINGS)
        counts = _one(cursor, _COUNTS)
        settings = _one(cursor, _SETTINGS) or {}
    return {"counts": counts, "notice": support_notice.notice(settings.get("notice_version"))}


def decide_queue(db: Database, user_id: UUID, page: int, size: int = PAGE_SIZE) -> dict:
    page, size = _page(page), _size(size)
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _TICKET_COLUMNS.replace("SELECT t.id,", "SELECT count(*) OVER () AS total, t.id,", 1)
                     + _DECIDE_WHERE + _ORDER + " LIMIT %s OFFSET %s", (size, (page - 1) * size))
    return _paged(rows, [_ticket_row(row) for row in rows], page, size=size)


def list_tickets(db: Database, user_id: UUID, view: str, page: int, size: int = PAGE_SIZE) -> dict:
    if view not in _VIEWS:
        raise Invalid("VIEW", field="view")
    page, size = _page(page), _size(size)
    order = " ORDER BY t.updated_at DESC, t.number DESC" if view in ("resolved", "closed") else _ORDER
    with db.session(user_id) as cursor:
        rows = _rows(cursor, _TICKET_COLUMNS.replace("SELECT t.id,", "SELECT count(*) OVER () AS total, t.id,", 1)
                     + f" WHERE {_VIEWS[view]}" + order + " LIMIT %s OFFSET %s", (size, (page - 1) * size))
    return _paged(rows, [_ticket_row(row) for row in rows], page, size=size)


# ── التذكرة ─────────────────────────────────────────────────────────────
_TICKET = _TICKET_COLUMNS + " WHERE t.id = %s"
_MESSAGES = """
SELECT m.id, m.author, m.body, m.masked_count, m.created_at, r.core AS reply_core
  FROM support_messages m LEFT JOIN support_replies r ON r.id = m.reply_id
 WHERE m.ticket_id = %s ORDER BY m.created_at, m.id
"""
_LATEST_DRAFT = """
SELECT d.* FROM support_drafts d WHERE d.ticket_id = %s ORDER BY d.seq DESC LIMIT 1
"""
_CITATIONS = """
SELECT c.position, c.article_id, c.article_version, c.quote, a.number, v.title
  FROM support_draft_citations c
  JOIN kb_articles a ON a.id = c.article_id
  JOIN kb_versions v ON v.article_id = c.article_id AND v.version = c.article_version
 WHERE c.draft_id = %s ORDER BY c.position
"""
_LIVE_REPLY = "SELECT * FROM support_replies WHERE ticket_id = %s AND state IN ('READY', 'RELEASED')"
_REPLY = "SELECT * FROM support_replies WHERE id = %s"
_REPLY_FLAGS = "SELECT * FROM support_flags WHERE reply_id = %s ORDER BY created_at, id"
_TICKET_FLAGS = "SELECT * FROM support_flags WHERE ticket_id = %s AND reply_id IS NULL ORDER BY created_at, id"
_ESCALATION = """
SELECT target, note, created_at, returned_at, return_note FROM support_escalations
 WHERE ticket_id = %s ORDER BY created_at DESC LIMIT 1
"""
_SIGNATURE = "SELECT signature FROM support_settings"
_DRAFTS_TODAY = """
SELECT count(*) AS n FROM ai_requests
 WHERE feature = 'SUPPORT_DRAFT' AND subject_id = %s AND started_at > now() - interval '24 hours'
"""


def _flag_view(row: Mapping, ticket: Mapping | None = None) -> dict:
    facts: dict[str, str] = {}
    if row["code"] == "LANGUAGE_MISMATCH" and ticket is not None:
        facts = {"customer": ticket.get("language", "AR"), "reply": "EN" if ticket.get("language") == "AR" else "AR"}
    if row["code"] == "PRIORITY_BELOW_SUGGESTION" and ticket is not None:
        facts = {"priority": ticket.get("priority", ""), "suggested": ticket.get("suggested_priority") or "",
                 "because": ticket.get("because") or ""}
    if row["code"] == "RESOLVE_UNANSWERED" and ticket is not None:
        facts = {"resolution": ticket.get("resolution") or ""}
    message, reason = rules.flag_text(row["code"], row["evidence"], **facts)
    return {"id": str(row["id"]), "source": "RULE", "code": row["code"], "state": row["state"], "message": message,
            "reason": reason, "evidence": row["evidence"], "dismiss_reason": row["dismiss_reason"]}


def _reply_view(db: Database, user_id: UUID, cursor, reply: Mapping, language: str) -> dict:
    flags = [_flag_view(row, {"language": language}) for row in _rows(cursor, _REPLY_FLAGS, (reply["id"],))]
    return {
        "id": str(reply["id"]), "ticket_id": str(reply["ticket_id"]), "kind": reply["kind"],
        "origin": reply["origin"], "core": reply["core"], "body": reply["body"],
        "body_sha256": bytes(reply["body_sha256"]).hex(), "state": reply["state"],
        "release_via": reply["release_via"], "at": _iso(reply["created_at"]),
        "needs_review": reply["origin"] in ("EDITED", "MANUAL") and reply["state"] == "READY",
        "kb_article_ids": [str(k) for k in reply["kb_article_ids"]],
        "flags": flags,
    }


def _ai_flags(db: Database, user_id: UUID, reply: Mapping) -> list[dict]:
    return reviewer.flags_for(db, user_id, "SUPPORT_REPLY", reply["id"], bytes(reply["body_sha256"]))


def _draft_view(cursor, draft: Mapping | None, last_customer) -> dict | None:
    if draft is None:
        return None
    citations = [{"article_id": str(c["article_id"]), "number": c["number"], "title": c["title"],
                  "version": c["article_version"], "quote": c["quote"]} for c in _rows(cursor, _CITATIONS, (draft["id"],))]
    return {
        "id": str(draft["id"]), "seq": draft["seq"], "result": draft["result"], "reply_kind": draft["reply_kind"],
        "body": draft["body"], "subject": draft["subject"], "note_to_employee": draft["note_to_employee"],
        "suggestion": {
            "category": draft["suggested_category"], "priority": draft["suggested_priority"],
            "impact": draft["impact"], "urgency": draft["urgency"], "security_concern": draft["security_concern"],
            "escalate": draft["escalate_suggestion"],
            "because": rules.priority_reason(draft["impact"], draft["urgency"], draft["security_concern"]),
        },
        "citations": citations,
        "rejected": None if draft["rejected_at"] is None else {"reason": draft["reject_reason"], "note": draft["reject_note"]},
        "current": draft["based_on_message_id"] == last_customer and draft["rejected_at"] is None,
        "language": draft["language"],
        "at": _iso(draft["created_at"]),
    }


def _language(messages: Sequence[Mapping]) -> str:
    last = next((m for m in reversed(messages) if m["author"] == "CUSTOMER"), None)
    return rules.language_of(last["body"]) if last else "AR"


def _ticket_view(db: Database, user_id: UUID, ticket_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        row = _one(cursor, _TICKET, (ticket_id,))
        if row is None:
            raise NotFound("NOT_FOUND", TICKET_GONE)
        messages = _rows(cursor, _MESSAGES, (ticket_id,))
        language = _language(messages)
        draft = _one(cursor, _LATEST_DRAFT, (ticket_id,))
        draft_view = _draft_view(cursor, draft, row["last_customer"])
        live = _one(cursor, _LIVE_REPLY, (ticket_id,))
        live_view = None if live is None else _reply_view(db, user_id, cursor, live, language)
        escalation = _one(cursor, _ESCALATION, (ticket_id,))
        facts = {"priority": row["priority"], "suggested_priority": row["suggested_priority"], "language": language,
                 "resolution": row["resolution"],
                 "because": None if draft is None else rules.priority_reason(draft["impact"], draft["urgency"],
                                                                             draft["security_concern"])}
        ticket_flags = [_flag_view(f, facts) for f in _rows(cursor, _TICKET_FLAGS, (ticket_id,))]
        used = _one(cursor, _DRAFTS_TODAY, (ticket_id,))["n"]
        usage = reviewer.usage(cursor, "SUPPORT_DRAFT")
    if live_view is not None:
        live_view["ai_flags"] = _ai_flags(db, user_id, live)
    status = row["status"]
    open_states = ("NEW", "OPEN", "PENDING", "ESCALATED")
    has_customer = row["last_customer"] is not None
    current = draft_view is not None and draft_view["current"]
    view = _ticket_row(row)
    view.update({
        "messages": [{"id": str(m["id"]), "author": m["author"], "body": m["body"], "masked_count": m["masked_count"],
                      "at": _iso(m["created_at"])} for m in messages],
        "language": language,
        "draft": draft_view,
        "live_reply": live_view,
        "escalation": None if escalation is None else {
            "target": escalation["target"], "note": escalation["note"], "at": _iso(escalation["created_at"]),
            "returned_at": _iso(escalation["returned_at"]), "return_note": escalation["return_note"]},
        "flags": ticket_flags,
        "follow_up_of": None if row["follow_up_of"] is None else str(row["follow_up_of"]),
        "resolution": row["resolution"], "close_reason": row["close_reason"],
        "texts_purged": row["texts_purged_at"] is not None,
        "allowed": {
            "draft": status in open_states and has_customer and live is None,
            "send_as_is": status in open_states and live is None and current and draft["body"] is not None
                          and not (status == "ESCALATED" and draft["reply_kind"] == "ANSWER"),
            "edit": status in open_states and live is None and current and draft["body"] is not None,
            "write": status in open_states and live is None,
            "ask_info": status in open_states and live is None,
            "reject": current and live is None,
            "escalate": status in ("NEW", "OPEN", "PENDING") and live is None,
            "return_escalation": status == "ESCALATED" and live is None,
            "resolve": status in ("NEW", "OPEN", "PENDING") and live is None,
            "reopen": status == "RESOLVED",
            "follow_up": status == "CLOSED",
            "note": status in open_states,
        },
        "ai": {"draft_left_today": None if usage["per_day"] is None else max(0, min(
            usage["per_day"] - (usage["used_today"] or 0), 8 - used))},
    })
    return view


def get_ticket(db: Database, user_id: UUID, ticket_id: UUID) -> dict:
    return _ticket_view(db, user_id, ticket_id)


_EVENTS = """
SELECT count(*) OVER () AS total, at, actor, event, detail, from_status, to_status
  FROM support_events WHERE ticket_id = %s ORDER BY id DESC LIMIT %s OFFSET %s
"""


def events(db: Database, user_id: UUID, ticket_id: UUID, page: int) -> dict:
    page = _page(page)
    with db.session(user_id) as cursor:
        if _one(cursor, "SELECT 1 AS x FROM support_tickets WHERE id = %s", (ticket_id,)) is None:
            raise NotFound("NOT_FOUND", TICKET_GONE)
        rows = _rows(cursor, _EVENTS, (ticket_id, PAGE_SIZE, (page - 1) * PAGE_SIZE))
    return _paged(rows, [{"at": _iso(r["at"]), "actor": r["actor"], "event": r["event"], "detail": r["detail"],
                          "from_status": r["from_status"], "to_status": r["to_status"]} for r in rows], page)


# ── اللصق ───────────────────────────────────────────────────────────────
def mask_preview(text: str) -> dict:
    """ما سيُحفظ من النصّ الملصق، وما حُذف منه، ولغته. لا يُخزَّن شيء."""
    masked, counts = rules.mask(text)
    if not 1 <= len(masked) <= 4000:
        raise Invalid("TEXT", field="text")
    return {"text": masked, "masked": counts, "language": rules.language_of(masked)}


def _label(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    label = " ".join(value.split())
    if not 1 <= len(label) <= 30 or not rules.contact_free(label):
        raise Invalid("LABEL", field="customer_label")
    return label


def _subject(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    subject = rules.one_line(value)
    if not 3 <= len(subject) <= 80 or not rules.contact_free(subject):
        raise Invalid("SUBJECT", field="subject")
    return subject


def create_ticket(db: Database, user_id: UUID, fields: Mapping) -> tuple[dict, bool]:
    """(التذكرة، هل أُنشئت الآن). الضغطة المكرّرة بالرمز نفسه تُرجع التذكرة نفسها."""
    body, masked = _masked(fields["text"])
    label = _label(fields.get("customer_label"))
    subject = _subject(fields.get("subject"))
    with db.session(user_id) as cursor:
        existed = _one(cursor, "SELECT id FROM support_tickets WHERE client_token = %s", (fields["client_token"],))
        cursor.execute("SELECT ew_support_create_ticket(%s, %s, %s, %s, %s, %s, %s, %s) AS id",
                       (fields["client_token"], fields["channel"], fields.get("priority") or "NORMAL",
                        fields.get("category"), label, subject, body, masked))
        ticket_id = cursor.fetchone()["id"]
    return _ticket_view(db, user_id, ticket_id), existed is None


def add_message(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    body, masked = _masked(fields["text"])
    with db.session(user_id) as cursor, _ticket_errors():
        cursor.execute("SELECT ew_support_add_message(%s, %s, %s, %s, %s, %s)",
                       (ticket_id, fields["expected_row_version"], fields["author"], body, masked,
                        fields["client_token"]))
    return _ticket_view(db, user_id, ticket_id)


def follow_up(db: Database, user_id: UUID, closed_id: UUID, fields: Mapping) -> dict:
    body, masked = _masked(fields["text"])
    with db.session(user_id) as cursor, _ticket_errors():
        cursor.execute("SELECT ew_support_follow_up(%s, %s, %s, %s) AS id",
                       (closed_id, fields["client_token"], body, masked))
        new_id = cursor.fetchone()["id"]
    return _ticket_view(db, user_id, new_id)


def classify(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    subject = _subject(fields.get("subject"))
    with db.session(user_id) as cursor, _ticket_errors():
        if "subject" not in fields:
            subject = (_one(cursor, "SELECT subject FROM support_tickets WHERE id = %s", (ticket_id,)) or {}).get("subject")
        cursor.execute("SELECT ew_support_set_ticket(%s, %s, %s, %s, %s, %s)",
                       (ticket_id, fields["expected_row_version"], fields.get("category"), fields["priority"], subject,
                        fields.get("accept_draft_id")))
    return _ticket_view(db, user_id, ticket_id)


# ── المسودة ─────────────────────────────────────────────────────────────
_BEGIN_DRAFT = "SELECT request_id, based_on_message_id FROM ew_support_begin_draft(%s, %s)"
_THREAD = """
SELECT m.author, m.body, r.core AS reply_core
  FROM support_messages m LEFT JOIN support_replies r ON r.id = m.reply_id
 WHERE m.ticket_id = %s ORDER BY m.created_at, m.id
"""
_SEARCH = "SELECT * FROM ew_kb_search(%s, %s)"
_DRAFT_BY_ID = "SELECT * FROM support_drafts WHERE id = %s"
_RECORD_DRAFT = """
SELECT ew_support_record_draft(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) AS id
"""
_FINISH = "SELECT ew_support_finish_call(%s, %s, %s)"
#: قيود التسجيل التي تعني «تغيّر ما كُتب له» لا «جوابٌ خاطئ»: يُسقط الاستدعاء ويُقال لماذا.
_DISCARD_CONSTRAINTS = frozenset({"support_draft_stale", "support_draft_needs_open_call", "ai_request_not_open",
                                  "support_citation_not_published"})


def _thread(rows: Sequence[Mapping]) -> tuple[prompt.ThreadMessage, ...]:
    """المحادثة كما تُرسل: الردّ المرسل بنصّه بلا تحيةٍ ولا توقيع (لا يحمل اسم العميل)."""
    out = []
    for row in rows:
        if row["author"] == "CUSTOMER":
            out.append(prompt.ThreadMessage("customer", row["body"]))
        elif row["author"] == "NOTE":
            out.append(prompt.ThreadMessage("internal_note", row["body"]))
        elif row["reply_core"]:
            out.append(prompt.ThreadMessage("employee_reply", row["reply_core"]))
    return tuple(out)


def _search(cursor, *queries: str | None) -> list[dict]:
    """أفضل المقالات المنشورة لنصوص البحث، بلا تكرار، بترتيبها."""
    found: dict[UUID, dict] = {}
    for query in queries:
        text = " ".join(rules.without_masks(query or "").split())[:SEARCH_CHARS]
        if len(text) < 2:
            continue
        for row in _rows(cursor, _SEARCH, (text, SEARCH_LIMIT)):
            found.setdefault(row["article_id"], row)
    return list(found.values())[:SEARCH_LIMIT]


def _article(row: Mapping) -> Article:
    return Article(str(row["article_id"]), row["version"], f"KB-{row['number']} · {row['title']}",
                   prompt.article_text(row["title"], row["issue"], row["environment"], row["resolution"], row["cause"]))


def _source(row: Mapping) -> str:
    return prompt.article_source(row["title"], row["issue"], row["environment"], row["resolution"], row["cause"])


def _presets(values: Sequence[str]) -> tuple[str, ...]:
    picked = tuple(dict.fromkeys(values))
    if len(picked) > 2 or any(p not in prompt.PRESETS for p in picked) or {"MORE_FORMAL", "WARMER"} <= set(picked):
        raise Invalid("PRESETS", field="presets")
    return picked


def _call(runner: ReviewRunner, request) -> ModelReply:
    """استدعاءٌ واحد بمقعدٍ من الحارس (القاطع والمقاعد)، أو `SupportAiFailure` قبل أن يُفتح شيء."""
    reason = runner.guard.acquire()
    if reason is not None:
        raise SupportAiFailure("DOWN" if reason == "DOWN" else "SLOTS")
    reply = None
    try:
        reply = runner.call(request)
        return reply
    finally:
        runner.guard.release(called=reply is not None)


def _finish(db: Database, user_id: UUID, request_id: UUID, outcome: str, usage: dict | None) -> None:
    with db.session(user_id) as cursor:
        cursor.execute(_FINISH, (request_id, outcome, None if usage is None else json.dumps(usage)))


def request_draft(db: Database, runner: ReviewRunner, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    """
    «اطلب مسودة» أو «أعد الكتابة». البدء يفتح صفّ الدفتر تحت السقوف ويقرأ ما يلزم؛ ثم
    الاستدعاء؛ ثم التسجيل. ما لم يُنتج مسودةً يُغلق بنتيجته ويُرفع `SupportAiFailure`.
    """
    presets = _presets(fields.get("presets") or ())
    hint = _note(fields.get("hint"), "hint", 1, 200)
    redraft_of = fields.get("redraft_of")
    if hint is not None and "\n" in hint:
        hint = " ".join(hint.split())
    with db.session(user_id) as cursor, _ticket_errors():
        # المسودة التي يُعاد كتابتها من التذكرة نفسها، قبل أن يُفتح صفٌّ في الدفتر.
        previous = _one(cursor, _DRAFT_BY_ID, (redraft_of,)) if redraft_of else None
        if redraft_of and (previous is None or previous["ticket_id"] != ticket_id):
            raise Invalid("DRAFT", field="redraft_of")
        cursor.execute(_BEGIN_DRAFT, (ticket_id, fields["expected_row_version"]))
        begun = cursor.fetchone()
        request_id, based_on = begun["request_id"], begun["based_on_message_id"]
        thread_rows = _rows(cursor, _THREAD, (ticket_id,))
        ticket = _one(cursor, "SELECT subject FROM support_tickets WHERE id = %s", (ticket_id,))
        last_customer = next((r["body"] for r in reversed(thread_rows) if r["author"] == "CUSTOMER"), "")
        found = _search(cursor, last_customer, ticket["subject"])
    language = rules.language_of(last_customer)
    request = prompt.DraftInput(
        messages=_thread(thread_rows), language=language, articles=tuple(_article(row) for row in found),
        presets=presets, hint=hint,
        rejected_because=None if previous is None else previous["reject_reason"],
        rejection_note=None if previous is None else previous["reject_note"],
        previous_draft=None if previous is None else (previous["body"] or ""),
    )
    call, refs = prompt.draft_call(request)
    sources = {str(row["article_id"]): _source(row) for row in found}
    try:
        reply = _call(runner, call)
    except Exception:
        # أيّ فشلٍ قبل الجواب (المقعد، أو خطأٌ غير متوقَّع في الطريق) يُغلق الطلب، فلا يبقى مفتوحاً يحجز التالي.
        _finish(db, user_id, request_id, "UPSTREAM_ERROR", None)
        raise
    if reply.outcome != "OK":
        _finish(db, user_id, request_id, reply.outcome, reply.usage)
        raise SupportAiFailure(reply.outcome, reply.retry_after_seconds)
    try:
        draft = prompt.parse_draft(reply.data, refs, sources, language, presets)
    except prompt.DraftInvalid as invalid:
        ai_log.event("support_draft_invalid", request_id=str(request_id), outcome=invalid.code)
        _finish(db, user_id, request_id, "OUTPUT_INVALID", reply.usage)
        raise SupportAiFailure("OUTPUT_INVALID") from invalid
    try:
        with db.session(user_id) as cursor:
            cursor.execute(_RECORD_DRAFT, (
                request_id, based_on, draft["result"], draft["reply_kind"], draft["body"], draft["subject"],
                draft["note"], draft["category"], draft["impact"], draft["urgency"], draft["security"],
                draft["escalate"], draft["language"], list(presets), hint, redraft_of,
                json.dumps(draft["citations"], ensure_ascii=False), json.dumps(reply.usage)))
    except pg_errors.IntegrityError as error:
        constraint = getattr(error.diag, "constraint_name", None) or ""
        discarded = constraint in _DISCARD_CONSTRAINTS
        ai_log.event("support_draft_unrecorded", level="warning" if discarded else "critical",
                     request_id=str(request_id), constraint=constraint)
        try:
            _finish(db, user_id, request_id, "DISCARDED" if discarded else "OUTPUT_INVALID", reply.usage)
        except pg_errors.Error:
            ai_log.event("support_draft_finish_failed", level="error", request_id=str(request_id))
        if discarded:
            raise
        raise SupportAiFailure("OUTPUT_INVALID") from error
    return _ticket_view(db, user_id, ticket_id)


def reject_draft(db: Database, user_id: UUID, draft_id: UUID, reason: str, note: str | None) -> dict:
    note = _note(note, "note", 1, 200)
    with db.session(user_id) as cursor, _ticket_errors(DRAFT_GONE):
        ticket = _one(cursor, "SELECT ticket_id FROM support_drafts WHERE id = %s", (draft_id,))
        cursor.execute("SELECT ew_support_reject_draft(%s, %s, %s)", (draft_id, reason, note))
    if ticket is None:
        raise NotFound("NOT_FOUND", DRAFT_GONE)
    return _ticket_view(db, user_id, ticket["ticket_id"])


# ── الردّ ───────────────────────────────────────────────────────────────
_KB_PUBLISHED = """
SELECT a.id AS article_id, a.number, v.version, v.title, v.issue, v.environment, v.resolution, v.cause
  FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id AND v.version = a.published_version
 WHERE a.id = ANY(%s) AND a.state = 'PUBLISHED'
"""
_DRAFT_SOURCES = """
SELECT a.id AS article_id, a.number, v.version, v.title, v.issue, v.environment, v.resolution, v.cause
  FROM support_draft_citations c
  JOIN kb_articles a ON a.id = c.article_id
  JOIN kb_versions v ON v.article_id = c.article_id AND v.version = c.article_version
 WHERE c.draft_id = %s
"""
_PREPARE = "SELECT ew_support_prepare_reply(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[]) AS id"


def prepare_reply(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping, *, template: bool = False) -> dict:
    """
    «جهّز الردّ»: النصّ النهائي (التحية باسم العميل، ثم الردّ، ثم التوقيع) وتنبيهات القواعد عليه.
    من المسودة كما هي، أو بعد تعديلها، أو بقلم الموظف، أو من الأسئلة الجاهزة؛ و`template` لإفادةٍ
    جاهزة يكتبها الخادم (إبلاغ العميل بالتصعيد).
    """
    kind = fields["kind"]
    questions = list(dict.fromkeys(fields.get("template_questions") or ()))
    kb_ids = list(dict.fromkeys(fields.get("kb_article_ids") or ()))
    if len(kb_ids) > KB_IDS_MAX:
        raise Invalid("KB_IDS", field="kb_article_ids")
    if questions and (kind != "ASK_INFO" or not 1 <= len(questions) <= 4
                      or any(code not in rules.QUESTIONS for code in questions)):
        raise Invalid("QUESTIONS", field="template_questions")
    with db.session(user_id) as cursor, _ticket_errors():
        ticket = _one(cursor, "SELECT customer_label FROM support_tickets WHERE id = %s", (ticket_id,))
        if ticket is None:
            raise NotFound("NOT_FOUND", TICKET_GONE)
        messages = _rows(cursor, _MESSAGES, (ticket_id,))
        language = _language(messages)
        draft_id = fields.get("draft_id")
        grounding = []
        if draft_id is not None:
            grounding += [_source(row) for row in _rows(cursor, _DRAFT_SOURCES, (draft_id,))]
        if kb_ids:
            published = _rows(cursor, _KB_PUBLISHED, (kb_ids,))
            if len(published) != len(kb_ids):
                raise Invalid("KB_IDS", field="kb_article_ids")
            grounding += [_source(row) for row in published]
        if questions:
            core, template = rules.template_core(questions, language), True
        else:
            core = rules.normalize(fields.get("core") or "")
        if not 20 <= len(core) <= 1200 or not rules.kb_clean(core):
            raise Invalid("REPLY_TEXT", field="core")
        signature = (_one(cursor, _SIGNATURE) or {}).get("signature")
        body = rules.compose_body(core, ticket["customer_label"], signature, language)
        flags = [] if template else rules.rule_flags(core, kind, language, grounding)
        cursor.execute(_PREPARE, (ticket_id, fields["expected_row_version"], fields["client_token"], draft_id, kind,
                                  template, core, body, json.dumps(flags, ensure_ascii=False), [str(k) for k in kb_ids]))
        reply_id = cursor.fetchone()["id"]
        reply = _one(cursor, _REPLY, (reply_id,))
        view = _reply_view(db, user_id, cursor, reply, language)
    view["ai_flags"] = _ai_flags(db, user_id, reply)
    return view


def _reply_or_404(cursor, reply_id: UUID) -> dict:
    reply = _one(cursor, _REPLY, (reply_id,))
    if reply is None:
        raise NotFound("NOT_FOUND", REPLY_GONE)
    return reply


def ack_flag(db: Database, user_id: UUID, flag_id: UUID, action: str, reason: str | None) -> dict:
    """
    «تابع رغم ذلك» (DISMISSED بسببه) أو «عدّل» (HEEDED). الأخذ بتنبيه ردٍّ جاهز يسحبه في المعاملة نفسها: ما يُنسخ
    بعدها ردٌّ يُكتب من جديد، لا النصّ نفسه بلا سبب.
    """
    with db.session(user_id) as cursor, _ticket_errors(FLAG_GONE):
        cursor.execute("SELECT ew_support_ack_flag(%s, %s, %s)", (flag_id, action, reason))
        flag = _one(cursor, "SELECT * FROM support_flags WHERE id = %s", (flag_id,))
        if action == "HEEDED" and flag["reply_id"] is not None:
            live = _one(cursor, "SELECT state FROM support_replies WHERE id = %s", (flag["reply_id"],))
            if live is not None and live["state"] == "READY":
                cursor.execute("SELECT ew_support_confirm_reply(%s, false)", (flag["reply_id"],))
    return _flag_view(flag)


def release_reply(db: Database, user_id: UUID, reply_id: UUID, via: str, body_sha256: str) -> dict:
    """«انسخ» أو «شارك»: النصّ الذي يُنسخ هو المحفوظ بعينه، ولا تنبيه بلا قرار."""
    try:
        digest = bytes.fromhex(body_sha256)
    except ValueError as error:
        raise Invalid("HASH", field="body_sha256") from error
    try:
        with db.session(user_id) as cursor, _ticket_errors(REPLY_GONE):
            cursor.execute("SELECT ew_support_release_reply(%s, %s, %s)", (reply_id, via, digest))
            reply = _one(cursor, _REPLY, (reply_id,))
    except pg_errors.IntegrityError as error:
        if getattr(error.diag, "constraint_name", None) == "ai_flags_undecided":
            raise reviewer.flags_undecided(db, user_id, "SUPPORT_REPLY", reply_id, digest) from error
        raise
    return _ticket_view(db, user_id, reply["ticket_id"])


def confirm_reply(db: Database, user_id: UUID, reply_id: UUID, sent: bool) -> dict:
    with db.session(user_id) as cursor, _ticket_errors(REPLY_GONE):
        reply = _reply_or_404(cursor, reply_id)
        cursor.execute("SELECT ew_support_confirm_reply(%s, %s)", (reply_id, sent))
    return _ticket_view(db, user_id, reply["ticket_id"])


# ── التصعيد والحلّ ──────────────────────────────────────────────────────
def escalate(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    note = _note(fields["note"], "note", 10, 1000)
    if note is None:
        raise Invalid("NOTE", field="note")
    with db.session(user_id) as cursor, _ticket_errors():
        cursor.execute("SELECT ew_support_escalate(%s, %s, %s, %s)",
                       (ticket_id, fields["expected_row_version"], fields["target"], note))
    if fields.get("notify_customer"):
        # «أبلغ العميل»: إفادةٌ جاهزة بلغته، تُنسخ وتُرسل كأيّ ردّ. التصعيد قد تمّ: إن تعذّر تجهيز الإفادة
        # (توقيعٌ لا يُقبل مثلاً) عادت التذكرة مصعّدةً بلا ردّ، ولا يُقال للموظف إن التصعيد لم يتمّ.
        with db.session(user_id) as cursor:
            version = _one(cursor, "SELECT row_version FROM support_tickets WHERE id = %s", (ticket_id,))["row_version"]
            messages = _rows(cursor, _MESSAGES, (ticket_id,))
        language = _language(messages)
        try:
            prepare_reply(db, user_id, ticket_id, {
                "kind": "UPDATE", "expected_row_version": version, "client_token": uuid.uuid4(),
                "core": rules.UPDATE_TEMPLATES["ESCALATED"][0 if language == "AR" else 1]}, template=True)
        except (Invalid, Conflict, pg_errors.IntegrityError) as error:
            ai_log.event("support_escalation_notice_skipped", level="warning", reason=type(error).__name__)
    return _ticket_view(db, user_id, ticket_id)


def return_escalation(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    note = _note(fields.get("note"), "note", 3, 500)
    with db.session(user_id) as cursor, _ticket_errors():
        cursor.execute("SELECT ew_support_return_escalation(%s, %s, %s)",
                       (ticket_id, fields["expected_row_version"], note))
    return _ticket_view(db, user_id, ticket_id)


def resolve(db: Database, user_id: UUID, ticket_id: UUID, fields: Mapping) -> dict:
    try:
        with db.session(user_id) as cursor, _ticket_errors():
            cursor.execute("SELECT ew_support_resolve(%s, %s, %s, %s)",
                           (ticket_id, fields["expected_row_version"], fields["resolution"],
                            bool(fields.get("confirmed"))))
    except pg_errors.IntegrityError as error:
        if getattr(error.diag, "constraint_name", None) == "support_resolve_unanswered":
            message, reason = rules.flag_text("RESOLVE_UNANSWERED", resolution=fields["resolution"])
            raise Conflict("UNANSWERED", "آخر رسالةٍ من العميل بلا ردّ.", {
                "flag": {"code": "RESOLVE_UNANSWERED", "message": message, "reason": reason},
                "confirmable": fields["resolution"] in ("DUPLICATE", "NOT_SUPPORT")}) from error
        raise
    return _ticket_view(db, user_id, ticket_id)


def reopen(db: Database, user_id: UUID, ticket_id: UUID, expected_row_version: int) -> dict:
    with db.session(user_id) as cursor, _ticket_errors():
        cursor.execute("SELECT ew_support_reopen(%s, %s)", (ticket_id, expected_row_version))
    return _ticket_view(db, user_id, ticket_id)


# ── قاعدة المعرفة ───────────────────────────────────────────────────────
_ARTICLE_ROW = """
SELECT count(*) OVER () AS total, a.id, a.number, a.state, a.published_version, a.latest_version, a.needs_review,
       a.needs_review_reason, a.reuse_count, a.row_version, a.updated_at, a.source_ticket_id, v.title
  FROM kb_articles a
  JOIN kb_versions v ON v.article_id = a.id AND v.version = a.latest_version
"""
_KB_VIEWS = {
    "published": "a.state = 'PUBLISHED'",
    "attention": "a.needs_review",
    "drafts": "a.state = 'DRAFT'",
    "archived": "a.state = 'ARCHIVED'",
}
_VERSIONS = """
SELECT version, title, issue, environment, resolution, cause, created_at
  FROM kb_versions WHERE article_id = %s ORDER BY version DESC
"""


def _article_row(row: Mapping) -> dict:
    return {"id": str(row["id"]), "number": row["number"], "state": row["state"], "title": row["title"],
            "published_version": row["published_version"], "latest_version": row["latest_version"],
            "needs_review": row["needs_review"], "needs_review_reason": row["needs_review_reason"],
            "reuse_count": row["reuse_count"], "row_version": row["row_version"], "updated_at": _iso(row["updated_at"])}


def list_articles(db: Database, user_id: UUID, view: str, q: str | None, page: int, size: int = PAGE_SIZE) -> dict:
    page, size = _page(page), _size(size)
    with db.session(user_id) as cursor:
        if q is not None and q.strip():
            query = " ".join(q.split())
            if not 2 <= len(query) <= 200:
                raise Invalid("SEARCH", field="q")
            ids = [row["article_id"] for row in _rows(cursor, _SEARCH, (query, 10))]
            rows = _rows(cursor, _ARTICLE_ROW + " WHERE a.id = ANY(%s)", (ids,))
            order = {article_id: n for n, article_id in enumerate(ids)}
            rows.sort(key=lambda row: order[row["id"]])
            # أقرب عشر مقالات، مقسّمةً بحجم صفحة العميل كما تُقسّم القوائم.
            items = [_article_row(r) for r in rows[(page - 1) * size:page * size]]
            return {"items": items, "page": page, "pages": max(1, -(-len(rows) // size)), "total": len(rows)}
        if view not in _KB_VIEWS:
            raise Invalid("VIEW", field="view")
        rows = _rows(cursor, _ARTICLE_ROW + f" WHERE {_KB_VIEWS[view]} ORDER BY a.number DESC LIMIT %s OFFSET %s",
                     (size, (page - 1) * size))
    return _paged(rows, [_article_row(r) for r in rows], page, size=size)


def _article_view(db: Database, user_id: UUID, article_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        row = _one(cursor, _ARTICLE_ROW + " WHERE a.id = %s", (article_id,))
        if row is None:
            raise NotFound("NOT_FOUND", ARTICLE_GONE)
        versions = _rows(cursor, _VERSIONS, (article_id,))
        cursor.execute("SELECT ew_kb_current_digest(%s) AS digest", (article_id,))
        digest = cursor.fetchone()["digest"]
    view = _article_row(row)
    view["versions"] = [{"version": v["version"], "title": v["title"], "issue": v["issue"],
                         "environment": v["environment"], "resolution": v["resolution"], "cause": v["cause"],
                         "at": _iso(v["created_at"])} for v in versions]
    view["source_ticket_id"] = None if row["source_ticket_id"] is None else str(row["source_ticket_id"])
    view["digest"] = None if digest is None else bytes(digest).hex()
    view["flags"] = [] if digest is None else reviewer.flags_for(db, user_id, "KB_ARTICLE", article_id, bytes(digest))
    return view


def get_article(db: Database, user_id: UUID, article_id: UUID) -> dict:
    return _article_view(db, user_id, article_id)


def _article_fields(fields: Mapping) -> tuple[str, str, str | None, str, str | None]:
    values = {}
    for key, (low, high) in prompt.ARTICLE_LENGTHS.items():
        raw = fields.get(key)
        value = None if raw is None else rules.normalize(raw)
        if key == "title" and value is not None:
            value = rules.one_line(value)
        if key in ("environment", "cause") and not value:
            values[key] = None
            continue
        if value is None or not low <= len(value) <= high:
            raise Invalid("KB_FIELD", field=key)
        values[key] = value
    if not rules.kb_clean(" ".join(v or "" for v in values.values())):
        raise Invalid("KB_SENSITIVE", field="resolution")
    return values["title"], values["issue"], values["environment"], values["resolution"], values["cause"]


@contextmanager
def _article_errors() -> Iterator[None]:
    try:
        with _ticket_errors(ARTICLE_GONE):
            yield
    except pg_errors.IntegrityError as error:
        if getattr(error.diag, "constraint_name", None) == "stale_row_version":
            raise Conflict("STALE", ARTICLE_STALE) from error
        raise


def create_article(db: Database, user_id: UUID, fields: Mapping) -> dict:
    title, issue, environment, resolution, cause = _article_fields(fields)
    with db.session(user_id) as cursor, _article_errors():
        cursor.execute("SELECT ew_kb_create(%s, %s, %s, %s, %s, %s, %s) AS id",
                       (fields["client_token"], title, issue, environment, resolution, cause,
                        fields.get("source_ticket_id")))
        article_id = cursor.fetchone()["id"]
    return _article_view(db, user_id, article_id)


def add_version(db: Database, user_id: UUID, article_id: UUID, fields: Mapping) -> dict:
    title, issue, environment, resolution, cause = _article_fields(fields)
    with db.session(user_id) as cursor, _article_errors():
        cursor.execute("SELECT ew_kb_add_version(%s, %s, %s, %s, %s, %s, %s)",
                       (article_id, fields["expected_row_version"], title, issue, environment, resolution, cause))
    return _article_view(db, user_id, article_id)


def publish(db: Database, user_id: UUID, article_id: UUID, expected_row_version: int, version: int) -> dict:
    try:
        with db.session(user_id) as cursor, _article_errors():
            cursor.execute("SELECT ew_kb_publish(%s, %s, %s::smallint)", (article_id, expected_row_version, version))
    except pg_errors.IntegrityError as error:
        if getattr(error.diag, "constraint_name", None) == "ai_flags_undecided":
            with db.session(user_id) as cursor:
                cursor.execute("SELECT ew_kb_current_digest(%s) AS digest", (article_id,))
                digest = bytes(cursor.fetchone()["digest"])
            raise reviewer.flags_undecided(db, user_id, "KB_ARTICLE", article_id, digest) from error
        raise
    return _article_view(db, user_id, article_id)


def set_article_state(db: Database, user_id: UUID, article_id: UUID, expected_row_version: int, state: str) -> dict:
    with db.session(user_id) as cursor, _article_errors():
        cursor.execute("SELECT ew_kb_set_state(%s, %s, %s)", (article_id, expected_row_version, state))
    return _article_view(db, user_id, article_id)


def mark_review(db: Database, user_id: UUID, article_id: UUID, expected_row_version: int, needs: bool) -> dict:
    with db.session(user_id) as cursor, _article_errors():
        cursor.execute("SELECT ew_kb_mark_review(%s, %s, %s)", (article_id, expected_row_version, needs))
    return _article_view(db, user_id, article_id)


_REJECTIONS = """
SELECT reject_reason AS reason, count(*) AS count FROM support_drafts
 WHERE rejected_at > now() - make_interval(days => %s) GROUP BY reject_reason ORDER BY count(*) DESC, reject_reason
"""
_GAPS = """
SELECT d.id AS draft_id, d.ticket_id, t.number AS ticket_number, d.reject_reason AS reason, d.reject_note AS note,
       d.rejected_at AS at
  FROM support_drafts d JOIN support_tickets t ON t.id = d.ticket_id
 WHERE d.rejected_at > now() - make_interval(days => %s) AND d.reject_reason IN ('NOT_IN_KB', 'WRONG_INFO', 'OUTDATED_ARTICLE')
 ORDER BY d.rejected_at DESC LIMIT 20
"""


def improve(db: Database, user_id: UUID, days: int) -> dict:
    """«تحسين المسودات»: أسباب الرفض، والتذاكر التي نقصتها القاعدة، والمقالات التي تحتاج نظرة."""
    with db.session(user_id) as cursor:
        rejections = _rows(cursor, _REJECTIONS, (days,))
        gaps = _rows(cursor, _GAPS, (days,))
        attention = _rows(cursor, _ARTICLE_ROW + f" WHERE {_KB_VIEWS['attention']} ORDER BY a.number DESC LIMIT 20")
    return {
        "rejections": [{"reason": r["reason"], "count": r["count"]} for r in rejections],
        "gaps": [{"draft_id": str(g["draft_id"]), "ticket_id": str(g["ticket_id"]), "ticket_number": g["ticket_number"],
                  "reason": g["reason"], "note": g["note"], "at": _iso(g["at"])} for g in gaps],
        "attention": [_article_row(a) for a in attention],
    }


# ── الإعدادات والإشعار ──────────────────────────────────────────────────
_SLA_TARGETS = "SELECT priority, first_reply_minutes, resolve_minutes FROM support_sla_targets"


def get_settings(db: Database, user_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_ENSURE_SETTINGS)
        settings = _one(cursor, _SETTINGS) or {}
        sla = {r["priority"]: {"first_reply_minutes": r["first_reply_minutes"], "resolve_minutes": r["resolve_minutes"]}
               for r in _rows(cursor, _SLA_TARGETS)}
        usage = [{"kind": code, **reviewer.usage(cursor, code)}
                 for code in ("SUPPORT_DRAFT", "SUPPORT_REPLY_REVIEW", "SUPPORT_ARTICLE_REVIEW")]
    return {"signature": settings.get("signature"), "sla": sla, "ai_usage": usage,
            "notice": support_notice.notice(settings.get("notice_version"))}


#: «لم يُرسل»: يبقى الحقل كما هو.
KEEP = object()


def save_settings(db: Database, user_id: UUID, signature: str | None | object, sla: Mapping | None) -> dict:
    if isinstance(signature, str):
        signature = rules.one_line(signature) or None
        if signature is not None and (not 2 <= len(signature) <= 60 or not rules.contact_free(signature)):
            raise Invalid("SIGNATURE", field="signature")
    targets = None
    if sla:
        targets = {}
        for priority, value in sla.items():
            if priority not in rules.PRIORITIES:
                raise Invalid("SLA", field="sla")
            targets[priority] = [value["first_reply_minutes"], value["resolve_minutes"]]
    with db.session(user_id) as cursor:
        if signature is KEEP:
            signature = (_one(cursor, _SETTINGS) or {}).get("signature")
        cursor.execute("SELECT ew_support_save_settings(%s, %s)",
                       (signature, None if targets is None else json.dumps(targets)))
    return get_settings(db, user_id)


def accept_notice(db: Database, user_id: UUID, version: str) -> None:
    if version != support_notice.VERSION:
        raise Invalid("NOTICE_VERSION", field="version")
    with db.session(user_id) as cursor:
        cursor.execute("SELECT ew_support_accept_notice(%s)", (version,))


def notice_version(db: Database, user_id: UUID) -> str | None:
    """النسخة التي وافق عليها صاحب الجلسة، لحارس المسارات."""
    with db.session(user_id) as cursor:
        row = _one(cursor, "SELECT notice_version FROM support_settings")
    return None if row is None else row["notice_version"]


def phrases() -> dict:
    return {
        "phrases": [{"id": code, "ar": ar, "en": en} for code, (ar, en) in rules.PHRASES.items()],
        "questions": [{"code": code, "ar": ar, "en": en} for code, (ar, en) in rules.QUESTIONS.items()],
        "update_templates": [{"code": code, "ar": ar, "en": en} for code, (ar, en) in rules.UPDATE_TEMPLATES.items()],
    }


# ── المراجِع: الردّ والمقالة ────────────────────────────────────────────
_REVIEW_REPLY = """
SELECT r.id, r.ticket_id, r.kind, r.core, r.body_sha256, r.draft_id, r.state, r.origin, r.kb_article_ids
  FROM support_replies r WHERE r.id = %s
"""
_LAST_CUSTOMER = """
SELECT body FROM support_messages WHERE ticket_id = %s AND author = 'CUSTOMER' ORDER BY created_at DESC, id DESC LIMIT 1
"""


def _require_current_notice(cursor) -> None:
    """
    مراجعتا الردّ والمقالة تمرّان بالمسار المشترك `/api/ai/review`، لا بحارس مسارات المكتب: فتُفحص هنا النسخة
    الحالية من إشعار المكتب قبل أن يُفتح شيء (والقاعدة تفحص أن إشعاراً ما قُبل).
    """
    row = _one(cursor, "SELECT notice_version FROM support_settings")
    if not support_notice.is_current(None if row is None else row["notice_version"]):
        raise Conflict("NOTICE", detail="اقرأ إشعار مكتب الدعم ووافق عليه أولاً.")


def _load_reply(cursor, user_id: UUID, kind: str, reply_id: UUID, _expected: int | None) -> Snapshot:
    """
    الردّ كما يراه المراجِع: آخر رسالةٍ من العميل، ونوعه، وجمله، والمقالات التي اقتبست منها مسودته والتي أدرج
    الموظف خطواتها؛ وإن لم تكن فأقرب ثلاثٍ منشورة لرسالة العميل.
    """
    _require_current_notice(cursor)
    reply = _one(cursor, _REVIEW_REPLY, (reply_id,))
    if reply is None or reply["state"] != "READY" or reply["origin"] not in ("EDITED", "MANUAL"):
        raise NotFound("NOT_FOUND", reviewer.NO_REVIEW)
    last = (_one(cursor, _LAST_CUSTOMER, (reply["ticket_id"],)) or {}).get("body", "")
    rows = _rows(cursor, _DRAFT_SOURCES, (reply["draft_id"],)) if reply["draft_id"] else []
    if reply["kb_article_ids"]:
        cited = {row["title"] for row in rows}
        rows += [row for row in _rows(cursor, _KB_PUBLISHED, (list(reply["kb_article_ids"]),)) if row["title"] not in cited]
    if not rows:
        rows = _search(cursor, last)[:3]
    articles = [(row["title"], prompt.article_text(row["title"], row["issue"], row["environment"], row["resolution"],
                                                   row["cause"])) for row in rows]
    payload = prompt.reply_payload(last, reply["kind"], reply["core"], articles)
    return Snapshot(payload, bytes(reply["body_sha256"]))


_REVIEW_ARTICLE = """
SELECT a.id, a.state, a.latest_version, a.published_version, v.title, v.issue, v.environment, v.resolution, v.cause
  FROM kb_articles a JOIN kb_versions v ON v.article_id = a.id AND v.version = a.latest_version
 WHERE a.id = %s
"""


def _load_article(cursor, user_id: UUID, kind: str, article_id: UUID, _expected: int | None) -> Snapshot:
    """آخر نسخةٍ من مقالةٍ لم تُنشر، وأقرب ثلاثٍ منشورةٍ إليها (غيرها)."""
    _require_current_notice(cursor)
    row = _one(cursor, _REVIEW_ARTICLE, (article_id,))
    if row is None or row["state"] in ("ARCHIVED", "DISCARDED") or row["published_version"] == row["latest_version"]:
        raise NotFound("NOT_FOUND", reviewer.NO_REVIEW)
    similar = [r for r in _search(cursor, f"{row['title']} {row['issue']}") if r["article_id"] != article_id][:3]
    payload = prompt.article_payload(row, [(r["title"], prompt.article_text(
        r["title"], r["issue"], r["environment"], r["resolution"], r["cause"])) for r in similar])
    cursor.execute("SELECT ew_kb_current_digest(%s) AS digest", (article_id,))
    return Snapshot(payload, bytes(cursor.fetchone()["digest"]))


def _reply_fixture(owner_cursor, user_id: UUID) -> UUID:
    """ردٌّ كتبه موظفٌ على تذكرة، بدور المالك: موضوعٌ نموذجي لاختبار المحمّل."""
    owner_cursor.execute("SELECT set_config('eyework.user_id', %s, true)", (str(user_id),))
    owner_cursor.execute("SELECT ew_support_accept_notice(%s)", (support_notice.VERSION,))
    owner_cursor.execute("SELECT ew_support_create_ticket(%s, 'MESSAGING', 'NORMAL', NULL, 'سارة', NULL, %s, 0::smallint) AS id",
                         (uuid.uuid4(), "الطابعة لا تطبع منذ الصباح."))
    ticket = owner_cursor.fetchone()["id"]
    owner_cursor.execute("SELECT ew_support_prepare_reply(%s, 1, %s, NULL, 'ANSWER', false, %s, %s, '[]') AS id",
                         (ticket, uuid.uuid4(), "أعيدوا تشغيل الطابعة ثم اطبعوا صفحة اختبار.",
                          "مرحباً سارة،\n\nأعيدوا تشغيل الطابعة ثم اطبعوا صفحة اختبار."))
    return owner_cursor.fetchone()["id"]


def _article_fixture(owner_cursor, user_id: UUID) -> UUID:
    owner_cursor.execute("SELECT set_config('eyework.user_id', %s, true)", (str(user_id),))
    owner_cursor.execute("SELECT ew_kb_create(%s, %s, %s, NULL, %s, NULL, NULL) AS id",
                         (uuid.uuid4(), "الطابعة لا تطبع", "الطابعة لا تطبع أيّ صفحة.",
                          "1. أعد تشغيل الطابعة.\n2. اطبع صفحة اختبار."))
    return owner_cursor.fetchone()["id"]


REPLY_FEATURE = ReviewFeature(
    code="SUPPORT_REPLY_REVIEW", kinds=frozenset({"SUPPORT_REPLY"}), profession=Profession.SUPPORT,
    catalogue=prompt.REPLY_CATALOGUE,
    begin_sql="SELECT request_id, content_digest AS digest FROM ew_support_review_begin(%s)",
    record_sql="SELECT ew_support_review_record(%s, %s, %s) AS outcome",
    digest_sql="SELECT (SELECT body_sha256 FROM support_replies WHERE id = %s AND state = 'READY') AS digest",
    load=_load_reply, payload_keys=prompt.REPLY_PAYLOAD_KEYS, fixture=_reply_fixture,
)
ARTICLE_FEATURE = ReviewFeature(
    code="SUPPORT_ARTICLE_REVIEW", kinds=frozenset({"KB_ARTICLE"}), profession=Profession.SUPPORT,
    catalogue=prompt.ARTICLE_CATALOGUE,
    begin_sql="SELECT request_id, content_digest AS digest FROM ew_kb_review_begin(%s, NULL)",
    record_sql="SELECT ew_kb_review_record(%s, %s, %s) AS outcome",
    digest_sql="SELECT ew_kb_current_digest(%s) AS digest",
    load=_load_article, payload_keys=prompt.ARTICLE_PAYLOAD_KEYS, fixture=_article_fixture,
)
reviewer.FEATURES["SUPPORT_REPLY_REVIEW"] = REPLY_FEATURE
reviewer.FEATURES["SUPPORT_ARTICLE_REVIEW"] = ARTICLE_FEATURE



# ── «اسأل سيمبول» في المكتب ─────────────────────────────────────────────
#: ما يقرؤه المساعد من شاشات الدعم: أعدادٌ وحالات، ولا نصّ من رسائل العملاء ولا ردودهم.
_STATUS_NAMES = {"NEW": "جديدة", "OPEN": "مفتوحة", "PENDING": "بانتظار العميل", "ESCALATED": "مُصعَّدة",
                 "RESOLVED": "محلولة", "CLOSED": "مغلقة"}
_DRAFT_NAMES = {"DRAFT": "مسودة جاهزة", "CANNOT_ANSWER": "لم يجد في قاعدة المعرفة ما يجيب",
                "NOT_SUPPORT": "رأى أنها ليست طلب دعم"}
_SCREEN_TICKET = """
SELECT t.number, t.status, t.priority, t.category,
       (SELECT d.result FROM support_drafts d WHERE d.ticket_id = t.id ORDER BY d.seq DESC LIMIT 1) AS draft,
       (SELECT r.state FROM support_replies r WHERE r.ticket_id = t.id AND r.state IN ('READY', 'RELEASED')) AS live,
       (SELECT count(*) FROM support_messages m WHERE m.ticket_id = t.id AND m.author = 'CUSTOMER') AS customer_messages
  FROM support_tickets t WHERE t.id = %s
"""
_ASSISTANT_HOME = assistant.SCREENS["HOME"]


def _assistant_home(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute("SELECT ew_my_profession() AS profession")
    if cursor.fetchone()["profession"] != Profession.SUPPORT.value:
        return _ASSISTANT_HOME.load(cursor, user_id, screen_id)
    c = _one(cursor, _COUNTS)
    return assistant.fit([
        f"بانتظار قرارك: {c['decide']}، والتذاكر المفتوحة: {c['open']}، وبانتظار العميل: {c['pending']}، "
        f"والمُصعَّدة: {c['escalated']}",
        f"مقالاتٌ تحتاج مراجعة: {c['kb_attention']}"])


def _assistant_ticket(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    row = _one(cursor, _SCREEN_TICKET, (screen_id,))
    if row is None:
        raise NotFound("SCREEN", assistant.NO_SCREEN)
    lines = [f"التذكرة #{row['number']}: {_STATUS_NAMES.get(row['status'], row['status'])}، "
             f"أولوية {rules.PRIORITY_NAMES.get(row['priority'], row['priority'])}",
             f"رسائل العميل فيها: {row['customer_messages']}"]
    if row["draft"]:
        lines.append(f"آخر مسودةٍ من سيمبول: {_DRAFT_NAMES.get(row['draft'], row['draft'])}")
    if row["live"]:
        lines.append("ردٌّ جاهز لم يُرسل بعد" if row["live"] == "READY" else "ردٌّ نُسخ ولم يُؤكَّد إرساله")
    return assistant.fit(lines)


# ── أدوات سيمبول لموظف الدعم: تقرأ ولا تغيّر ───────────────────────────
def _tool_kb(cursor, user_id: UUID, text: str) -> tuple[str, ...]:
    """أقرب ثلاث مقالاتٍ منشورة: العنوان والمشكلة وأوّل الحلّ؛ والنصّ كلّه يمرّ بالإخفاء بعدها."""
    query = " ".join(text.split())
    if not 2 <= len(query) <= 200:
        return ("يُكتب ما يُبحث عنه بكلمتين على الأقل.",)
    rows = _rows(cursor, _SEARCH, (query, 3))
    if not rows:
        return (f"لا مقالة منشورة تطابق «{query}».",)
    lines = []
    for row in rows:
        resolution = " ".join(row["resolution"].split())
        if len(resolution) > 220:
            resolution = resolution[:220].rsplit(" ", 1)[0] + "…"
        lines.append(f"KB-{row['number']} «{row['title']}»: {' '.join(row['issue'].split())} — الحلّ: {resolution}")
    return assistant.fit(lines)


def _tool_desk(cursor, user_id: UUID, text: str) -> tuple[str, ...]:
    c = _one(cursor, _COUNTS)
    return (f"بانتظار قرارك: {c['decide']}، والتذاكر المفتوحة: {c['open']}، وبانتظار العميل: {c['pending']}، "
            f"والمُصعَّدة: {c['escalated']}، ومقالاتٌ تحتاج مراجعة: {c['kb_attention']}",)


assistant.register_tool(assistant.Tool(
    name="KB", profession=Profession.SUPPORT,
    description="أقرب ثلاث مقالاتٍ منشورة في قاعدة المعرفة لما يُبحث عنه: العنوان والمشكلة وأوّل الحلّ.",
    input_hint="المشكلة بكلماتٍ قليلة", label="بحث في قاعدة المعرفة", run=_tool_kb,
))
assistant.register_tool(assistant.Tool(
    name="DESK", profession=Profession.SUPPORT,
    description="أعداد المكتب الآن: بانتظار القرار، والمفتوحة، وبانتظار العميل، والمُصعَّدة، والمقالات التي تحتاج مراجعة.",
    input_hint=None, label="أعداد المكتب", run=_tool_desk,
))
#: معرّفات بنود رئيسية الدعم في العميل (lib/workspace.ts)، بأسمائها.
assistant.register_destinations(Profession.SUPPORT, (
    assistant.Destination("new", "تذكرة جديدة"),
    assistant.Destination("decide", "بانتظار قراري"),
    assistant.Destination("open", "التذاكر المفتوحة"),
    assistant.Destination("pending", "بانتظار العميل"),
    assistant.Destination("escalated", "المُصعَّدة"),
    assistant.Destination("knowledge", "قاعدة المعرفة"),
))


assistant.register(dataclasses.replace(
    _ASSISTANT_HOME, load=_assistant_home,
    extra_labels={**_ASSISTANT_HOME.extra_labels, Profession.SUPPORT: (
        "بانتظار قراري", "التذاكر المفتوحة", "تذكرة جديدة", "بانتظار العميل", "المُصعَّدة", "قاعدة المعرفة")},
))
assistant.register(assistant.ScreenContext(
    kind="SUPPORT_TICKET", profession=Profession.SUPPORT, title="التذكرة",
    labels=("أرسل كما هي", "عدّل ثم أرسل", "اطلب معلومات", "صعّد", "ارفض المسودة", "حُلّت دون ردٍّ مكتوب"),
    ready_questions=("متى أصعّد التذكرة بدل أن أردّ؟", "ماذا أفعل إن كانت مسودة سيمبول خاطئة؟"),
    needs_id=True, load=_assistant_ticket,
))
