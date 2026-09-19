"""
طبقة المجال فوق البوابة
========================
تختبر `core.proposals` و`core.delivery` كما تستدعيهما الـAPI: عبر الأدوار
والتجمّعات الحقيقية، لا بمحاكاة.
"""

from __future__ import annotations

import pytest

from core import db, delivery, proposals
from core.types import Actor, InvalidTransition
from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
def practitioner(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


@pytest.fixture
def other_practitioner(seed) -> Actor:
    return Actor(id=seed.practitioner_b, role="PRACTITIONER", tenant_id=seed.tenant_b)


@pytest.fixture(autouse=True)
def _reset_pools():
    """التجمّعات تُعاد تهيئتها بعد كل اختبار حتى لا تتسرب اتصالات بين الحالات."""
    yield
    db.shutdown()


def _plan(actor, seed, **overrides):
    return proposals.create(
        actor, patient_id=seed.patient_a, kind="PLAN",
        payload={"home_program": "تمارين يومية"}, **overrides
    )


# ── دورة الحياة ─────────────────────────────────────────────────────────
def test_created_proposal_starts_as_draft(practitioner, seed):
    proposal = _plan(practitioner, seed)
    assert proposal.status == "DRAFT"
    assert not proposal.is_deliverable


def test_draft_is_not_deliverable_to_the_patient(practitioner, seed):
    _plan(practitioner, seed)
    assert delivery.get_deliverable(seed.patient_a, "PLAN") is None
    assert list(delivery.list_deliverables(seed.patient_a)) == []


def test_pending_is_not_deliverable_to_the_patient(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    assert delivery.get_deliverable(seed.patient_a, "PLAN") is None


def test_approved_becomes_deliverable(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    approved = proposals.approve(proposal.id, practitioner)

    assert approved.status == "APPROVED"
    assert approved.reviewer_id == practitioner.id
    assert approved.decision_at is not None

    delivered = delivery.get_deliverable(seed.patient_a, "PLAN")
    assert delivered is not None
    assert delivered.proposal_id == proposal.id
    assert delivered.payload["home_program"] == "تمارين يومية"


def test_rejected_never_becomes_deliverable(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    rejected = proposals.reject(proposal.id, practitioner, "الجرعة غير مناسبة")

    assert rejected.status == "REJECTED"
    assert rejected.rejection_reason == "الجرعة غير مناسبة"
    assert delivery.get_deliverable(seed.patient_a, "PLAN") is None


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_rejection_without_reason_is_refused(practitioner, seed, reason):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    with pytest.raises(ValueError):
        proposals.reject(proposal.id, practitioner, reason)


def test_approving_a_draft_is_refused(practitioner, seed):
    """لا اعتماد لما لم يدخل الطابور."""
    proposal = _plan(practitioner, seed)
    with pytest.raises(InvalidTransition):
        proposals.approve(proposal.id, practitioner)


def test_approved_proposal_cannot_be_decided_twice(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    proposals.approve(proposal.id, practitioner)
    with pytest.raises(InvalidTransition):
        proposals.reject(proposal.id, practitioner, "تراجعت")


# ── التعديل يحفظ نسخة ولا يطمس الأصل ────────────────────────────────────
def test_edit_and_approve_preserves_the_original(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    edited = proposals.edit_and_approve(
        proposal.id, practitioner, payload={"home_program": "نسخة المراجِع"}
    )

    assert edited.status == "EDITED_APPROVED"
    assert edited.version == 2
    assert edited.payload["home_program"] == "نسخة المراجِع"

    with db.session("practitioner", tenant_id=practitioner.tenant_id,
                    actor_id=practitioner.id) as cursor:
        cursor.execute(
            "SELECT version, payload FROM proposal_versions WHERE proposal_id = %s",
            (proposal.id,),
        )
        original = cursor.fetchall()

    assert len(original) == 1
    assert original[0]["version"] == 1
    assert original[0]["payload"]["home_program"] == "تمارين يومية", "الأصل طُمس"


def test_edited_approved_is_delivered(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    proposals.edit_and_approve(proposal.id, practitioner, payload={"home_program": "معدّل"})

    delivered = delivery.get_deliverable(seed.patient_a, "PLAN")
    assert delivered is not None and delivered.payload["home_program"] == "معدّل"


# ── القاعدة 4 عبر طبقة المجال ───────────────────────────────────────────
def test_illustration_without_side_is_refused(practitioner, seed):
    from psycopg import errors as pg_errors

    with pytest.raises(pg_errors.CheckViolation):
        proposals.create(
            practitioner, patient_id=seed.patient_a, kind="ILLUSTRATION_SET",
            payload={"svg": "<svg/>"}, affected_side=None,
        )


def test_illustration_with_side_is_accepted(practitioner, seed):
    proposal = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="ILLUSTRATION_SET",
        payload={"svg": "<svg/>"}, affected_side="RIGHT",
    )
    assert proposal.affected_side == "RIGHT"


# ── الطابور ─────────────────────────────────────────────────────────────
def test_queue_puts_red_flags_first(practitioner, seed):
    routine = _plan(practitioner, seed, priority=1)
    red_flag = _plan(practitioner, seed, priority=9, is_red_flag=True)
    for proposal in (routine, red_flag):
        proposals.submit(proposal.id, practitioner)

    queue = proposals.review_queue(practitioner)
    assert [p.id for p in queue] == [red_flag.id, routine.id]


def test_queue_orders_by_priority_then_wait(practitioner, seed):
    low = _plan(practitioner, seed, priority=7)
    high = _plan(practitioner, seed, priority=2)
    for proposal in (low, high):
        proposals.submit(proposal.id, practitioner)

    assert [p.id for p in proposals.review_queue(practitioner)] == [high.id, low.id]


def test_queue_excludes_decided_proposals(practitioner, seed):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    proposals.approve(proposal.id, practitioner)
    assert proposals.review_queue(practitioner) == []


# ── العزل ───────────────────────────────────────────────────────────────
def test_practitioner_cannot_read_another_tenants_proposal(practitioner, other_practitioner, seed):
    proposal = _plan(practitioner, seed)
    with pytest.raises(proposals.ProposalNotFound):
        proposals.get(proposal.id, other_practitioner)


def test_practitioner_cannot_decide_another_tenants_proposal(
    practitioner, other_practitioner, seed
):
    proposal = _plan(practitioner, seed)
    proposals.submit(proposal.id, practitioner)
    with pytest.raises(proposals.ProposalNotFound):
        proposals.approve(proposal.id, other_practitioner)

    assert proposals.get(proposal.id, practitioner).status == "PENDING", "تغيّرت الحالة"


def test_patient_sees_only_their_own_content(practitioner, other_practitioner, seed):
    mine = _plan(practitioner, seed)
    proposals.submit(mine.id, practitioner)
    proposals.approve(mine.id, practitioner)

    theirs = proposals.create(
        other_practitioner, patient_id=seed.patient_b, kind="PLAN", payload={"x": 1}
    )
    proposals.submit(theirs.id, other_practitioner)
    proposals.approve(theirs.id, other_practitioner)

    assert [d.proposal_id for d in delivery.list_deliverables(seed.patient_a)] == [mine.id]
    assert [d.proposal_id for d in delivery.list_deliverables(seed.patient_b)] == [theirs.id]
