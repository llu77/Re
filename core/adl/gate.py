"""
بوابة برنامج اللبس — الفحص وتسجيل حكمه
========================================
المدخل الوحيد الذي يُنتج صفّ فحصٍ لبرنامج لبس. ما لم يمرّ من هنا لا يملك
صفّاً، وما لا صفّ له لا يتقدّم خطوة واحدة: محفّز الانتقالات يرفض أي حمولة
تقول `module = 'DRESSING'` بلا فحصٍ ناجح مرتبطٍ ببصمتها.

**البصمة تُحسب في قاعدة البيانات لا هنا** — للسبب نفسه الذي في بوابة الصور:
تمثيل `jsonb` النصّي مُطبَّع بقواعد PostgreSQL، وإعادة بنائه في بايثون
تطبيعٌ ثانٍ يفترق يوماً ما بصمت فيمرّ برنامجٌ لم يُفحص.

ثلاث خطوات لا خطوة واحدة: القراءة، ثم الفحص (بلا قاعدة بيانات)، ثم التسجيل.
رفعُ الاستثناء داخل معاملة التسجيل يُجهضها فيضيع صفّ الحجب نفسه — وحجبٌ غير
مسجَّل يُخفي العيب الذي سبّبه.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import UUID

from psycopg.types.json import Jsonb

from core import db
from core.adl.dressing import DressingStep, verify_program
from core.adl.types import DressingRejected
from core.types import Actor

__all__ = [
    "DressingBlocked",
    "declares_dressing",
    "record_pass",
    "steps_for",
    "verify_proposal",
]

#: الحمولة التي تخضع للبوابة تقول ذلك عن نفسها. محفّز
#: `trg_dressing_declares_itself` يمنع حمولةً تحمل خطوات لبس ولا تعلنها،
#: فالإعلان ليس اتفاقاً بل شرطٌ بنيوي.
DRESSING_MODULE = "DRESSING"


class DressingBlocked(DressingRejected):
    """
    برنامج محجوب، والحجب مسجَّل.

    يرث من `DressingRejected` فمستدعٍ يمسك الأصل يمسك هذه أيضاً: لا فرع
    يظن أن الحجب المسجَّل أخفّ من الحجب غير المسجَّل.
    """


_PROPOSAL = """
SELECT p.payload, p.kind, p.status,
       encode(sha256(convert_to(p.payload::text, 'UTF8')), 'hex') AS payload_sha256
FROM proposals p WHERE p.id = %s
"""

_RECORD = """
INSERT INTO dressing_verification
    (proposal_id, payload_sha256, verdict, detail, reason, verified_by)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id
"""


def declares_dressing(payload: Mapping[str, Any]) -> bool:
    """هل هذه الحمولة برنامج لبس؟ سؤال واحد بجواب واحد في موضع واحد."""
    return payload.get("module") == DRESSING_MODULE


def verify_proposal(actor: Actor, proposal_id: UUID) -> tuple[DressingStep, ...]:
    """يفحص برنامج مقترح ويسجّل الحكم، أو يرفع `DressingBlocked` بعد تسجيله."""
    payload, digest = _read(actor, proposal_id)
    if not declares_dressing(payload):
        raise DressingRejected("حمولة هذا المقترح لا تعلن أنها برنامج لبس")

    try:
        steps = verify_program(payload)
    except DressingRejected as exc:
        _record(actor, proposal_id, digest, verdict="BLOCKED", reason=str(exc))
        raise DressingBlocked(str(exc)) from exc

    _record(actor, proposal_id, digest, verdict="PASS", steps=steps)
    return steps


def steps_for(payload: Mapping[str, Any]) -> tuple[DressingStep, ...]:
    """فحص حمولة لم تُخزَّن بعد. يستعمله `edit_and_approve` قبل أن يكتبها."""
    return verify_program(payload)


def record_pass(
    cursor,
    actor: Actor,
    proposal_id: UUID,
    payload: Mapping[str, Any],
    steps: Sequence[DressingStep],
) -> None:
    """
    يسجّل نجاحاً داخل معاملة قائمة، **قبل** كتابة الحمولة لا بعدها.

    محفّز الانتقالات يفحص وجود الصفّ أثناء `UPDATE` نفسه، فصفٌّ يُكتب بعده
    يأتي متأخراً. والبصمة تُحسب من الحمولة الجديدة بالتعبير الذي ستحسبه به
    قاعدة البيانات بعد الكتابة، فلا يفترق التطبيعان.
    """
    cursor.execute(
        "SELECT encode(sha256(convert_to(%s::jsonb::text, 'UTF8')), 'hex') AS digest",
        (Jsonb(dict(payload)),),
    )
    cursor.execute(
        _RECORD,
        (proposal_id, cursor.fetchone()["digest"], "PASS",
         Jsonb(_detail(steps)), None, actor.id),
    )


def _read(actor: Actor, proposal_id: UUID) -> tuple[Mapping[str, Any], str]:
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_PROPOSAL, (proposal_id,))
        row = cursor.fetchone()
    if row is None:
        raise DressingRejected("لا مقترح بهذا المعرّف في نطاقك")
    return row["payload"], row["payload_sha256"]


def _record(
    actor: Actor,
    proposal_id: UUID,
    digest: str,
    *,
    verdict: str,
    reason: str | None = None,
    steps: Sequence[DressingStep] = (),
) -> None:
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(
            _RECORD,
            (proposal_id, digest, verdict, Jsonb(_detail(steps)), reason, actor.id),
        )


def _detail(steps: Sequence[DressingStep]) -> dict:
    """ما فُحص كما فُهم — لا كما كُتب. فرقٌ بينهما يعني عيباً في التحليل."""
    return {
        "steps": [
            {"action": step.action, "side": step.side, "garment": step.garment}
            for step in steps
        ]
    }
