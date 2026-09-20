"""
بوابة الصور — الفحص وتسجيل حكمه
=================================
المدخل الوحيد الذي يُنتج صفّ تحقق في قاعدة البيانات. ما لم يمرّ من هنا لا
يملك صفّاً، وما لا صفّ له لا يتقدّم خطوة واحدة: محفّز الانتقالات يرفض أي
`ILLUSTRATION_SET` بلا تحقق ناجح لجانبه ولبصمة حمولته.

**البصمة تُحسب في قاعدة البيانات لا هنا.** تمثيل `jsonb` النصّي مُطبَّع
بقواعد PostgreSQL، وإعادة بنائه في بايثون تعني تطبيعين يفترقان يوماً ما
بصمت — فيمرّ رسمٌ لم يُفحص. الاستعلام يقرأ البصمة من الصفّ نفسه.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import UUID

from psycopg.types.json import Jsonb

from core import db
from core.illustrations import (
    IllustrationRejected,
    Verdict,
    verify_set,
)
from core.types import Actor

__all__ = [
    "IllustrationBlocked",
    "illustrations_of",
    "record_pass",
    "verdicts_for",
    "verify_proposal",
]


class IllustrationBlocked(IllustrationRejected):
    """
    الصورة محجوبة، والحجب مسجَّل.

    ترث من `IllustrationRejected` فمستدعٍ يمسك الأصل يمسك هذه أيضاً: لا
    يوجد فرع يظن أن الحجب المسجَّل أخفّ من الحجب غير المسجَّل.
    """


_PROPOSAL = """
SELECT p.kind, p.affected_side, p.payload, p.status,
       encode(sha256(convert_to(p.payload::text, 'UTF8')), 'hex') AS payload_sha256
FROM proposals p WHERE p.id = %s
"""

_RECORD = """
INSERT INTO illustration_verification
    (proposal_id, payload_sha256, side, verdict, bias, detail, reason, verified_by)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""


def illustrations_of(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """
    يستخرج الصور من حمولة المقترح.

    الشكل المتوقَّع: `{"illustrations": [{"exercise_type": ..., "svg": ...}]}`.
    حمولة لا تحمله ليست مجموعة صور، ورفضها هنا أوضح من فحص فارغ يمرّ.
    """
    items = payload.get("illustrations")
    if not isinstance(items, list) or not items:
        raise IllustrationRejected("حمولة الصور فارغة أو بشكل غير متوقَّع")

    extracted = []
    for item in items:
        if not isinstance(item, dict):
            raise IllustrationRejected("عنصر صورة ليس كائناً")
        svg, exercise_type = item.get("svg"), item.get("exercise_type")
        if not isinstance(svg, str) or not isinstance(exercise_type, str):
            raise IllustrationRejected("صورة بلا `svg` أو بلا `exercise_type`")
        extracted.append({"svg": svg, "exercise_type": exercise_type})
    return extracted


def verify_proposal(actor: Actor, proposal_id: UUID) -> Sequence[Verdict]:
    """
    يفحص صور مقترح ويسجّل الحكم، أو يرفع `IllustrationBlocked` بعد تسجيله.

    الرفض جماعي: صورة واحدة تفشل تُسقط المجموعة كلها. التسليم الجزئي هو
    «مسار التسليم البديل» الذي تمنعه القاعدة 4 نصاً.

    ثلاث خطوات لا خطوة واحدة، وهذا مقصود: القراءة، ثم الفحص (بلا قاعدة
    بيانات)، ثم التسجيل. رفعُ الاستثناء داخل معاملة التسجيل يُجهضها، فيضيع
    صفّ الحجب نفسه — وحجبٌ غير مسجَّل يُخفي العيب الذي سبّبه.
    """
    kind, side, payload, digest = _read(actor, proposal_id)
    if kind != "ILLUSTRATION_SET":
        raise IllustrationRejected(f"النوع {kind} ليس مجموعة صور")

    try:
        verdicts = verify_set(illustrations_of(payload), side=side)
    except IllustrationRejected as exc:
        _record(actor, proposal_id, digest, side, verdict="BLOCKED", reason=str(exc))
        raise IllustrationBlocked(str(exc)) from exc

    _record(actor, proposal_id, digest, side, verdict="PASS", verdicts=verdicts)
    return verdicts


def _read(actor: Actor, proposal_id: UUID):
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_PROPOSAL, (proposal_id,))
        row = cursor.fetchone()
    if row is None:
        raise IllustrationRejected("لا مقترح بهذا المعرّف في نطاقك")
    return row["kind"], row["affected_side"], row["payload"], row["payload_sha256"]


def _record(
    actor: Actor,
    proposal_id: UUID,
    digest: str,
    side: str,
    *,
    verdict: str,
    reason: str | None = None,
    verdicts: Sequence[Verdict] = (),
) -> None:
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(
            _RECORD,
            (proposal_id, digest, side, verdict,
             _weakest(verdicts), Jsonb(_detail(verdicts)), reason, actor.id),
        )


def _weakest(verdicts: Sequence[Verdict]) -> float | None:
    """أضعف انحياز في المجموعة: هو الذي يحدّ ثقتنا بها، لا متوسطها."""
    if not verdicts:
        return None
    return min(verdicts, key=lambda verdict: abs(verdict.bias)).bias


def _detail(verdicts: Sequence[Verdict]) -> dict:
    return {
        "images": [
            {
                "exercise_type": verdict.exercise_type,
                "bias": verdict.bias,
                "elements": verdict.element_count,
                "svg_sha256": verdict.svg_sha256,
            }
            for verdict in verdicts
        ]
    }


def verdicts_for(payload: Mapping[str, Any], side: str) -> Sequence[Verdict]:
    """فحص حمولة لم تُخزَّن بعد. يستعمله `edit_and_approve` قبل أن يكتبها."""
    return verify_set(illustrations_of(payload), side=side)


def record_pass(
    cursor,
    actor: Actor,
    proposal_id: UUID,
    side: str,
    payload: Mapping[str, Any],
    verdicts: Sequence[Verdict],
) -> None:
    """
    يسجّل نجاحاً داخل معاملة قائمة، **قبل** كتابة الحمولة لا بعدها.

    محفّز الانتقالات يفحص وجود صفّ التحقق أثناء `UPDATE` نفسه، فصفٌّ يُكتب
    بعده يأتي متأخراً. والبصمة تُحسب من الحمولة الجديدة بالتعبير الذي
    ستحسبه به قاعدة البيانات بعد الكتابة، فلا يفترق التطبيعان.
    """
    cursor.execute(
        "SELECT encode(sha256(convert_to(%s::jsonb::text, 'UTF8')), 'hex') AS digest",
        (Jsonb(dict(payload)),),
    )
    cursor.execute(
        _RECORD,
        (proposal_id, cursor.fetchone()["digest"], side, "PASS",
         _weakest(verdicts), Jsonb(_detail(verdicts)), None, actor.id),
    )
