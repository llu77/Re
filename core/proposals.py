"""
المقترحات — آلة الحالات ومستودعها
===================================
كل مخرج ذكاء اصطناعي قابل للاعتماد يمر من هنا. النظام يقترح، ولا يقرر ولا
يأذن: لا توجد في هذه الوحدة دالة تنقل مقترحاً إلى حالة قابلة للتسليم دون
`reviewer` مسمّى.

آلة الحالات مفروضة في قاعدة البيانات (محفّز `trg_proposal_transition`). ما هنا
طبقة رفيعة فوقها تعطي أخطاء مفهومة؛ قاعدة البيانات تبقى الحَكَم.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import UUID

from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from core import db
from core.types import (
    Actor,
    AffectedSide,
    InvalidTransition,
    Proposal,
    ProposalKind,
)

__all__ = [
    "approve",
    "create",
    "edit_and_approve",
    "expire_stale",
    "get",
    "reject",
    "review_queue",
    "submit",
]

_SELECT = """
SELECT id, tenant_id, patient_id, kind, status, payload, provenance, affected_side,
       priority, is_red_flag, version, created_at, queued_at, expires_at,
       reviewer_id, decision_at, rejection_reason
FROM proposals
"""


_BY_ID = _SELECT + " WHERE id = %s"

_PENDING_QUEUE = _SELECT + (
    " WHERE status = 'PENDING' AND expires_at > now()"
    " ORDER BY is_red_flag DESC, priority ASC, queued_at ASC LIMIT %s"
)


class ProposalNotFound(LookupError):
    """المقترح غير موجود، أو خارج نطاق المستأجر الحالي — لا نميّز بينهما."""


def _to_proposal(row: Mapping[str, Any]) -> Proposal:
    return Proposal(
        id=row["id"],
        patient_id=row["patient_id"],
        tenant_id=row["tenant_id"],
        kind=row["kind"],
        payload=row["payload"],
        provenance=row["provenance"],
        status=row["status"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        queued_at=row["queued_at"],
        reviewer_id=row["reviewer_id"],
        decision_at=row["decision_at"],
        rejection_reason=row["rejection_reason"],
        affected_side=row["affected_side"],
        version=row["version"],
    )


def _decide(
    proposal_id: UUID,
    actor: Actor,
    *,
    status: str,
    reason: str | None = None,
) -> Proposal:
    """قرار واحد على مقترح واحد. لا توجد نسخة جماعية من هذه الدالة عمداً."""
    try:
        with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
            cursor.execute(
                "UPDATE proposals SET status = %s, reviewer_id = %s, decision_at = now(),"
                " rejection_reason = %s WHERE id = %s RETURNING id",
                (status, actor.id, reason, proposal_id),
            )
            if cursor.fetchone() is None:
                raise ProposalNotFound(str(proposal_id))
    except pg_errors.CheckViolation as exc:
        raise InvalidTransition("?", status) from exc
    return get(proposal_id, actor)


def create(
    actor: Actor,
    *,
    patient_id: UUID,
    kind: ProposalKind,
    payload: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
    affected_side: AffectedSide | None = None,
    priority: int = 5,
    is_red_flag: bool = False,
) -> Proposal:
    """
    يُنشئ مسوّدة. لا تصل المريض بأي حال — التسليم يبدأ من الاعتماد لا الإنشاء.

    `affected_side` إلزامي للمحتوى المصوَّر، وقيد `CHECK` في قاعدة البيانات
    يرفض غير ذلك (القاعدة 4).
    """
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(
            "INSERT INTO proposals (tenant_id, patient_id, kind, payload, provenance,"
            " affected_side, priority, is_red_flag, created_by)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                actor.tenant_id,
                patient_id,
                kind,
                Jsonb(dict(payload)),
                Jsonb(dict(provenance or {})),
                affected_side,
                priority,
                is_red_flag,
                actor.id,
            ),
        )
        proposal_id = cursor.fetchone()["id"]
    return get(proposal_id, actor)


def get(proposal_id: UUID, actor: Actor) -> Proposal:
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(_BY_ID, (proposal_id,))
        row = cursor.fetchone()
    if row is None:
        raise ProposalNotFound(str(proposal_id))
    return _to_proposal(row)


def submit(proposal_id: UUID, actor: Actor) -> Proposal:
    """يدخل الطابور. `queued_at` هنا هو بداية قياس زمن المراجعة."""
    try:
        with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
            cursor.execute(
                "UPDATE proposals SET status = 'PENDING', queued_at = now()"
                " WHERE id = %s RETURNING id",
                (proposal_id,),
            )
            if cursor.fetchone() is None:
                raise ProposalNotFound(str(proposal_id))
    except pg_errors.CheckViolation as exc:
        raise InvalidTransition("?", "PENDING") from exc
    return get(proposal_id, actor)


def approve(proposal_id: UUID, actor: Actor) -> Proposal:
    """اعتماد كما هو."""
    return _decide(proposal_id, actor, status="APPROVED")


def reject(proposal_id: UUID, actor: Actor, reason: str) -> Proposal:
    """
    رفض بسبب نصي إلزامي.

    السبب الفارغ يرفضه قيد `rejection_needs_reason` في قاعدة البيانات؛ نفحصه
    هنا أيضاً لنعطي خطأً مفهوماً قبل رحلة الشبكة.
    """
    if not reason or not reason.strip():
        raise ValueError("الرفض يتطلب سبباً نصياً")
    return _decide(proposal_id, actor, status="REJECTED", reason=reason.strip())


def edit_and_approve(
    proposal_id: UUID,
    actor: Actor,
    *,
    payload: Mapping[str, Any],
    affected_side: AffectedSide | None = None,
) -> Proposal:
    """
    تعديل ثم اعتماد. النسخة الأصلية تُحفظ ولا تُطمس.

    الأصل يُنسخ إلى `proposal_versions` في نفس المعاملة، فإما أن يُحفظ الاثنان
    أو لا يتغير شيء.
    """
    try:
        with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
            cursor.execute(
                "INSERT INTO proposal_versions (proposal_id, version, payload, affected_side,"
                " edited_by) SELECT id, version, payload, affected_side, %s FROM proposals"
                " WHERE id = %s RETURNING proposal_id",
                (actor.id, proposal_id),
            )
            if cursor.fetchone() is None:
                raise ProposalNotFound(str(proposal_id))

            cursor.execute(
                "UPDATE proposals SET status = 'EDITED_APPROVED', reviewer_id = %s,"
                " decision_at = now(), payload = %s,"
                " affected_side = coalesce(%s, affected_side), version = version + 1"
                " WHERE id = %s RETURNING id",
                (actor.id, Jsonb(dict(payload)), affected_side, proposal_id),
            )
            if cursor.fetchone() is None:
                raise ProposalNotFound(str(proposal_id))
    except pg_errors.CheckViolation as exc:
        raise InvalidTransition("?", "EDITED_APPROVED") from exc
    return get(proposal_id, actor)


def review_queue(actor: Actor, limit: int = 50) -> Sequence[Proposal]:
    """
    الطابور مفروزاً: العلامات الحمراء أولاً، ثم الأولوية، ثم زمن الانتظار.

    المقترحات المنتهية صلاحيتها لا تظهر: مراجعتها لا تُنتج شيئاً قابلاً للتسليم.
    """
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(_PENDING_QUEUE, (limit,))
        rows = cursor.fetchall()
    return [_to_proposal(row) for row in rows]


def expire_stale(actor: Actor) -> int:
    """
    ينقل ما تجاوز مهلته إلى `EXPIRED`.

    المهلة مفروضة أصلاً عند التسليم، فهذا للنظافة والقياس لا للأمان: العرض
    يُسقط المنتهي سواء جرى هذا المسح أم لا.
    """
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(
            "UPDATE proposals SET status = 'EXPIRED'"
            " WHERE status = 'PENDING' AND expires_at <= now()"
        )
        return cursor.rowcount
