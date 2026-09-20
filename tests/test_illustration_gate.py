"""
بوابة الصور — القاعدة 4
=========================
«كل صورة تصل المريض تجتاز تحققاً آلياً من الجانب المصاب، ثم اعتماد ممارس.
الصورة الفاشلة تُحجب ولا يوجد مسار تسليم بديل.»

العيب الذي تمنعه هذه الاختبارات ليس فرضياً: ثلاثة من مولّدات هذا المستودع
كانت تستقبل `side` وتتجاهله، فتُنتج لليمين واليسار الصورة نفسها حرفياً —
وحقل «الجانب المصاب» في قاعدة البيانات يقول «يمين» بينما الرسم لا يقول شيئاً.
لذلك يقيس التحقق المخرَج ولا يسأل المولّد.
"""

from __future__ import annotations

import pytest
from psycopg import errors as pg_errors

from core import illustration_gate, illustrations, proposals
from core.illustrations import (
    BILATERAL_TOLERANCE,
    LATERAL_THRESHOLD,
    SIDE_BEARING_TYPES,
    SIDE_NEUTRAL_TYPES,
    IllustrationRejected,
)
from core.types import Actor
from tests.conftest import requires_db
from tools.visual_exercises import generate_visual_exercise

pytestmark = requires_db

LEGACY_SIDE = {"LEFT": "left", "RIGHT": "right", "BILATERAL": "both"}
ALL_TYPES = sorted(SIDE_BEARING_TYPES | SIDE_NEUTRAL_TYPES)


def _svg(exercise_type: str, side: str, difficulty: int = 3) -> str:
    return generate_visual_exercise({
        "exercise_type": exercise_type,
        "difficulty": difficulty,
        "side": LEGACY_SIDE[side],
    })["svg"]


def _payload(exercise_type: str, side: str, difficulty: int = 3) -> dict:
    return {
        "illustrations": [
            {"exercise_type": exercise_type, "svg": _svg(exercise_type, side, difficulty)}
        ]
    }


@pytest.fixture
def actor(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


def _illustration_proposal(actor, seed, exercise_type, side, difficulty=3):
    return proposals.create(
        actor,
        patient_id=seed.patient_a,
        kind="ILLUSTRATION_SET",
        payload=_payload(exercise_type, side, difficulty),
        affected_side=side,
    )


# ── القياس نفسه ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("exercise_type", ALL_TYPES)
@pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
def test_every_generator_stays_outside_the_thresholds(exercise_type, difficulty):
    """
    الحارس ضد تآكل الفنّ.

    العتبتان مقيستان على هذه المولّدات؛ تعديلٌ يُضعف علامة الجانب أو يُدخل
    انحيازاً في رسمٍ محايد يُسقط البناء هنا، لا في عيادة.
    """
    import xml.etree.ElementTree as ElementTree

    def bias(side: str) -> float:
        root = ElementTree.fromstring(_svg(exercise_type, side, difficulty))
        return illustrations._lateral_bias(root)[0]

    assert abs(bias("BILATERAL")) <= BILATERAL_TOLERANCE, "رسمٌ للجانبين منحاز"

    if exercise_type in SIDE_BEARING_TYPES:
        assert -bias("LEFT") >= LATERAL_THRESHOLD, "علامة اليسار أضعف من العتبة"
        assert bias("RIGHT") >= LATERAL_THRESHOLD, "علامة اليمين أضعف من العتبة"
    else:
        assert abs(bias("LEFT")) <= BILATERAL_TOLERANCE
        assert abs(bias("RIGHT")) <= BILATERAL_TOLERANCE


@pytest.mark.parametrize("exercise_type", sorted(SIDE_BEARING_TYPES))
def test_art_for_one_side_is_refused_when_the_other_is_claimed(exercise_type):
    """العيب التاريخي بعينه: الحقل يقول جانباً والرسم يقول غيره."""
    for drawn, claimed in (("LEFT", "RIGHT"), ("RIGHT", "LEFT")):
        with pytest.raises(IllustrationRejected):
            illustrations.verify(
                _svg(exercise_type, drawn), exercise_type=exercise_type, side=claimed
            )


@pytest.mark.parametrize("exercise_type", sorted(SIDE_BEARING_TYPES))
def test_bilateral_art_cannot_claim_a_side(exercise_type):
    """رسمٌ بلا جانب لا يُسلَّم على أنه لجانب — وهذا ما كان يحدث صامتاً."""
    with pytest.raises(IllustrationRejected):
        illustrations.verify(
            _svg(exercise_type, "BILATERAL"), exercise_type=exercise_type, side="LEFT"
        )


@pytest.mark.parametrize("exercise_type", sorted(SIDE_NEUTRAL_TYPES))
def test_a_side_neutral_type_refuses_a_side(exercise_type):
    with pytest.raises(IllustrationRejected):
        illustrations.verify(
            _svg(exercise_type, "BILATERAL"), exercise_type=exercise_type, side="RIGHT"
        )


def test_an_unclassified_type_is_refused():
    """نوع بلا تصنيف لا يُفحص، ولا يُسلَّم بلا فحص."""
    with pytest.raises(IllustrationRejected):
        illustrations.verify(
            _svg("scanning_grid", "LEFT"), exercise_type="mystery_drill", side="LEFT"
        )


# ── السلامة ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "hostile",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<script>fetch("https://x.test")</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect x="0" y="0" width="10" height="10" onclick="alert(1)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<image href="https://x.test/p.png" width="10" height="10"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect width="10" height="10" style="fill:url(https://x.test/a)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<foreignObject width="10" height="10"><b>x</b></foreignObject></svg>',
    ],
)
def test_hostile_markup_is_refused(hostile):
    """
    البوابة تعرض هذا الـSVG ترميماً لا نصاً، فالقائمة بيضاء لا سوداء.

    القائمة السوداء تُنسي دائماً شيئاً؛ البيضاء ترفض ما لم يُذكر.
    """
    with pytest.raises(IllustrationRejected):
        illustrations.verify(hostile, exercise_type="scanning_grid", side="LEFT")


def test_a_broken_document_is_refused():
    with pytest.raises(IllustrationRejected):
        illustrations.verify("<svg><rect", exercise_type="scanning_grid", side="LEFT")


# ── البوابة في قاعدة البيانات ───────────────────────────────────────────
def test_an_unverified_illustration_cannot_enter_the_queue(actor, seed):
    proposal = _illustration_proposal(actor, seed, "scanning_grid", "RIGHT")
    with pytest.raises(proposals.IllustrationNotVerified):
        proposals.submit(proposal.id, actor)


def test_a_verified_illustration_enters_the_queue(actor, seed):
    proposal = _illustration_proposal(actor, seed, "scanning_grid", "RIGHT")
    verdicts = illustration_gate.verify_proposal(actor, proposal.id)

    assert [v.side for v in verdicts] == ["RIGHT"]
    assert verdicts[0].bias >= LATERAL_THRESHOLD
    assert proposals.submit(proposal.id, actor).status == "PENDING"


def test_the_gate_holds_for_a_direct_update(actor, seed, practitioner_conn):
    """المنع في المحفّز لا في `core.proposals`: `UPDATE` مباشر يُرفض أيضاً."""
    from tests.conftest import set_actor

    proposal = _illustration_proposal(actor, seed, "scanning_grid", "LEFT")
    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with practitioner_conn.cursor() as cursor:
        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "UPDATE proposals SET status='PENDING', queued_at=now() WHERE id=%s",
                (proposal.id,),
            )


def test_art_for_the_wrong_side_is_blocked_and_recorded(actor, seed, owner):
    """
    المقترح يقول «يمين» والرسم مرسوم لليسار: يُحجب، ويُسجَّل سبب الحجب.

    الحجب الصامت يُخفي عيباً في المولّد؛ الحجب المسجَّل يكشفه.
    """
    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind="ILLUSTRATION_SET",
        payload={"illustrations": [
            {"exercise_type": "scanning_grid", "svg": _svg("scanning_grid", "LEFT")}
        ]},
        affected_side="RIGHT",
    )

    with pytest.raises(illustration_gate.IllustrationBlocked):
        illustration_gate.verify_proposal(actor, proposal.id)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT verdict, reason, bias FROM illustration_verification"
            " WHERE proposal_id = %s",
            (proposal.id,),
        )
        verdict, reason, bias = cursor.fetchone()

    assert verdict == "BLOCKED"
    assert "الجانب" in reason
    assert bias is None
    with pytest.raises(proposals.IllustrationNotVerified):
        proposals.submit(proposal.id, actor)


def test_one_bad_image_blocks_the_whole_set(actor, seed):
    """
    لا تسليم جزئي: صورة واحدة تفشل تُسقط المجموعة.

    تسليم ما نجح منها هو «مسار التسليم البديل» الذي تمنعه القاعدة 4 نصاً.
    """
    proposal = proposals.create(
        actor, patient_id=seed.patient_a, kind="ILLUSTRATION_SET",
        payload={"illustrations": [
            {"exercise_type": "scanning_grid", "svg": _svg("scanning_grid", "LEFT")},
            {"exercise_type": "reading_ruler", "svg": _svg("reading_ruler", "RIGHT")},
        ]},
        affected_side="LEFT",
    )
    with pytest.raises(illustration_gate.IllustrationBlocked):
        illustration_gate.verify_proposal(actor, proposal.id)


def test_editing_the_payload_invalidates_the_verification(actor, seed):
    """
    التحقق مرتبط ببصمة الحمولة، فتعديلها يُبطله تلقائياً.

    بدون هذا الربط يمكن فحص رسمٍ سليم ثم استبداله عند التعديل والاعتماد —
    وهو الباب الذي يفتحه `edit_and_approve` على مصراعيه.
    """
    proposal = _illustration_proposal(actor, seed, "scanning_grid", "LEFT")
    illustration_gate.verify_proposal(actor, proposal.id)
    proposals.submit(proposal.id, actor)

    swapped = {"illustrations": [
        {"exercise_type": "scanning_grid", "svg": _svg("scanning_grid", "RIGHT")}
    ]}
    with pytest.raises(IllustrationRejected) as raised:
        proposals.edit_and_approve(proposal.id, actor, payload=swapped)
    assert "LEFT" in str(raised.value)

    # ولا شيء كُتب: المقترح ما زال في الطابور بحمولته الأصلية.
    after = proposals.get(proposal.id, actor)
    assert after.status == "PENDING"
    assert after.payload == _payload("scanning_grid", "LEFT")


def test_a_verification_row_is_immutable(actor, seed, owner):
    proposal = _illustration_proposal(actor, seed, "reading_ruler", "RIGHT")
    illustration_gate.verify_proposal(actor, proposal.id)

    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE illustration_verification SET verdict = 'PASS',"
                " reason = NULL WHERE proposal_id = %s",
                (proposal.id,),
            )
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "DELETE FROM illustration_verification WHERE proposal_id = %s",
                (proposal.id,),
            )


def test_a_blocked_row_needs_a_reason(owner, seed, actor):
    proposal = _illustration_proposal(actor, seed, "scanning_grid", "LEFT")
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "INSERT INTO illustration_verification"
                " (proposal_id, payload_sha256, side, verdict, verified_by)"
                " VALUES (%s, %s, 'LEFT', 'BLOCKED', %s)",
                (proposal.id, "a" * 64, seed.practitioner_a),
            )


def test_the_patient_role_cannot_read_verifications(patient_conn, seed):
    from tests.conftest import set_actor

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute("SELECT * FROM illustration_verification")


def test_an_approved_illustration_reaches_the_patient(actor, seed):
    """الطرف الآخر من الضمان: ما اجتاز التحقق والاعتماد يصل فعلاً."""
    from core import delivery

    proposal = _illustration_proposal(actor, seed, "tracking_exercise", "LEFT")
    illustration_gate.verify_proposal(actor, proposal.id)
    proposals.submit(proposal.id, actor)
    proposals.approve(proposal.id, actor)

    delivered = delivery.get_deliverable(seed.patient_a, "ILLUSTRATION_SET")
    assert delivered is not None
    assert delivered.affected_side == "LEFT"
    assert delivered.payload["illustrations"][0]["exercise_type"] == "tracking_exercise"


def test_a_plan_cannot_smuggle_an_image(actor, seed):
    """
    الصور تسكن نوعاً واحداً محروساً.

    خطةٌ تحمل رسماً داخل خطوة كانت تصل المريض بلا أي فحص — بوابة التحقق
    تحرس `ILLUSTRATION_SET` وحده. المنع الآن بنيوي: لا SVG في حمولة أي نوع
    آخر، فلا يوجد مسار ثانٍ تصل منه صورة.
    """
    smuggled = {
        "steps": [
            {
                "title": "تمرين",
                "text": "…",
                "illustration": _svg("scanning_grid", "RIGHT"),
            }
        ]
    }
    with pytest.raises(pg_errors.CheckViolation):
        proposals.create(
            actor, patient_id=seed.patient_a, kind="PLAN", payload=smuggled
        )


def test_a_plan_may_name_an_exercise_without_carrying_its_image(actor, seed):
    """الخطة تشير إلى الصورة باسم تمرينها، والبوابة تجلبها من المعتمد."""
    named = {"steps": [{"title": "تمرين", "text": "…", "illustration": "scanning_grid"}]}
    plan = proposals.create(
        actor, patient_id=seed.patient_a, kind="PLAN", payload=named
    )
    assert plan.payload["steps"][0]["illustration"] == "scanning_grid"


def test_an_edit_cannot_smuggle_an_image_either(actor, seed):
    """المحفّز على `payload` لا على الإدراج وحده."""
    from tests.conftest import cite_evidence_as

    plan = proposals.create(
        actor, patient_id=seed.patient_a, kind="PLAN", payload={"steps": []}
    )
    cite_evidence_as(actor, plan.id)
    proposals.submit(plan.id, actor)

    with pytest.raises(Exception) as raised:
        proposals.edit_and_approve(
            plan.id, actor,
            payload={"steps": [{"illustration": _svg("scanning_grid", "LEFT")}]},
        )
    assert "بوابة التحقق" in str(raised.value) or "انتقال" in str(raised.value)
