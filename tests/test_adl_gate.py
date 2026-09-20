"""
وحدتا النشاط اليومي — التفويض والترتيب مفروضين في طبقة البيانات
================================================================
معيار القبول 5: «اختبار يثبت أن مستوى مطبخ غير مصرَّح به لا يمكن فتحه بأي
مسار». «بأي مسار» تعني ثلاثة مسارات تُجرَّب هنا صراحةً: استعلامٌ مباشر بدور
المريض، ونقطة العبور، ومحتوىً معتمدٌ يسمّي المهمة.

وقاعدة اللبس مفروضة بالنسق نفسه الذي فُرضت به بوابة الصور: الحكم مربوط
ببصمة الحمولة، فتعديلها يُبطله بلا أن يتذكّر أحد.
"""

from __future__ import annotations

import pytest
from psycopg import errors as pg_errors

from core import delivery, proposals
from core.adl import gate as adl_gate
from core.adl import kitchen
from core.adl.types import (
    KITCHEN_TIERS,
    SUSPENDED_ON_RED_FLAG,
    DressingOrderViolation,
)
from core.types import Actor
from tests.conftest import cite_evidence_as, requires_db, set_actor

pytestmark = requires_db

HEAT_TIERS = sorted(SUSPENDED_ON_RED_FLAG)
COLD_TIERS = sorted({tier.tier for tier in KITCHEN_TIERS} - SUSPENDED_ON_RED_FLAG)


@pytest.fixture
def actor(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


@pytest.fixture
def other_actor(seed) -> Actor:
    return Actor(id=seed.practitioner_b, role="PRACTITIONER", tenant_id=seed.tenant_b)


def dressing_payload(*steps: tuple[str, str, str]) -> dict:
    return {
        "module": "DRESSING",
        "steps": [
            {"action": action, "side": side, "garment": garment}
            for action, side, garment in steps
        ],
    }


CORRECT_ORDER = (("DON", "AFFECTED", "قميص"), ("DON", "SOUND", "قميص"))
WRONG_ORDER = (("DON", "SOUND", "قميص"), ("DON", "AFFECTED", "قميص"))


def _dressing_proposal(actor, seed, *steps):
    proposal = proposals.create(
        actor,
        patient_id=seed.patient_a,
        kind="PLAN",
        payload=dressing_payload(*steps),
    )
    cite_evidence_as(actor, proposal.id)
    return proposal


def _open_codes(patient_id) -> set[str]:
    return {task.code for task in delivery.list_adl_tasks(patient_id)}


def _open_tiers(patient_id) -> set[int]:
    return {
        task.tier
        for task in delivery.list_adl_tasks(patient_id)
        if task.module == "KITCHEN"
    }


def _report_red_flag(owner, seed, *, reporter) -> str:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO red_flag_reports (tenant_id, patient_id, body, reported_by)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (seed.tenant_a, seed.patient_a, "دوار شديد عند الوقوف", reporter),
        )
        return cursor.fetchone()[0]


# ══ معيار القبول 5 ══════════════════════════════════════════════════════
def test_an_unauthorized_tier_cannot_be_opened_by_any_path(
    actor, seed, owner, patient_conn
):
    """
    ثلاثة مسارات، ولا واحد منها يفتح مستوىً غير مفوَّض.

    المسار الأول هو الحاسم: دور المريض لا يملك صلاحية على الجدولين أصلاً،
    فالالتفاف مستحيل لا ممنوع. والثاني والثالث يثبتان أن ما فوق الصلاحيات
    لا يسرّب شيئاً أيضاً.
    """
    set_actor(patient_conn, patient_id=seed.patient_a)

    # ١ — استعلام مباشر: لا صلاحية.
    for table in ("adl_task", "kitchen_tier", "kitchen_authorization"):
        with patient_conn.cursor() as cursor, pytest.raises(
            pg_errors.InsufficientPrivilege
        ):
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")  # noqa: S608 — اسم ثابت
        patient_conn.rollback()

    # ٢ — نقطة العبور: لا مهمة مطبخ واحدة بلا تفويض.
    assert _open_tiers(seed.patient_a) == set()

    # ٣ — محتوى معتمد يسمّي المهمة لا يفتحها: التفويض ليس نصّاً في خطة.
    plan = proposals.create(
        actor,
        patient_id=seed.patient_a,
        kind="PLAN",
        payload={"tasks": ["KITCHEN_STOVETOP"], "tier": 3},
    )
    cite_evidence_as(actor, plan.id)
    proposals.approve(proposals.submit(plan.id, actor).id, actor)

    assert _open_tiers(seed.patient_a) == set(), "خطة معتمدة فتحت مستوىً غير مفوَّض"


def test_no_task_is_listed_without_patient_context(actor, seed, patient_conn):
    """
    سياق غائب ⇒ لا شيء، كما في `patient_deliverable_v`.

    «الفشل مغلق» خاصية تُحفظ في كل عروض المريض أو لا تكون خاصية: استدعاءٌ
    ينسى ضبط السياق يجب أن يعود فارغاً لا ناقصاً — فالفارغ يُلاحَظ، والناقص
    يُصدَّق.
    """
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis="أوّلي")

    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_adl_task_v")
        assert cursor.fetchone()[0] == 0


def test_the_gate_opens_when_the_tier_is_authorized(actor, seed):
    """حارس: لولاه لمرّ الاختبار أعلاه على عرضٍ لا يُرجع شيئاً أبداً."""
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=3, basis="اجتاز تقييم الموقد بإشراف")
    assert 3 in _open_tiers(seed.patient_a)


def test_every_tier_is_independently_gated(actor, seed):
    """تفويض مستوىً لا يفتح ما تحته ولا ما فوقه. لا تسلسل ضمني."""
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=2, basis="يقطع بأمان بلوح مثبَّت")
    assert _open_tiers(seed.patient_a) == {2}


def test_authorizing_the_top_tier_alone_is_possible(actor, seed):
    """
    قرار معلَن: لا تسلسل مفروض.

    الاختبار يوثّقه بدل أن يُترك ضمنياً؛ من يضيف التسلسل لاحقاً يراه هنا
    قراراً يُنقَض لا سهواً يُصحَّح.
    """
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=4, basis="يطبخ مستقلاً منذ سنوات")
    assert _open_tiers(seed.patient_a) == {4}


# ══ التعليق عند علامة حمراء ═════════════════════════════════════════════
def test_an_open_red_flag_suspends_the_heat_tiers(actor, seed, owner):
    """
    البلاغ غير المُستلَم يُخفي الحرارة ويُبقي البارد.

    ولا يكتب شيئاً: التفويض يبقى قائماً، والمهمة تعود بمجرد أن يستلم إنسانٌ
    البلاغ. لو كان سحباً تلقائياً لكان النظام قد قرّر، ولاحتاج قرار إنسان
    ثانياً لإعادة ما سحبه.
    """
    for tier in (1, 2, 3, 4):
        kitchen.authorize(actor, patient_id=seed.patient_a, tier=tier, basis=f"مستوى {tier}")
    assert _open_tiers(seed.patient_a) == {1, 2, 3, 4}

    report = _report_red_flag(owner, seed, reporter=seed.practitioner_a)
    assert _open_tiers(seed.patient_a) == set(COLD_TIERS), "الحرارة لم تُعلَّق"
    assert set(HEAT_TIERS).isdisjoint(_open_tiers(seed.patient_a))

    active = kitchen.for_patient(actor, seed.patient_a)
    assert len(active) == 4, "التعليق سحب تفويضاً — وهو شرط قراءة لا كتابة"

    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE red_flag_reports SET acknowledged_by = %s, acknowledged_at = now()"
            " WHERE id = %s",
            (seed.practitioner_a, report),
        )

    assert _open_tiers(seed.patient_a) == {1, 2, 3, 4}, "الاستلام لم يرفع التعليق"


def test_dressing_tasks_survive_a_red_flag(actor, seed, owner):
    """
    بلاغٌ عن ألم كتف لا يمنع لبس قميص.

    منعُ كل شيء عند كل بلاغ يجعل البلاغ عقوبةً فيُحجم المريض عن الإبلاغ،
    وهو أسوأ ما يمكن أن يفعله نظام سلامة بنفسه.
    """
    _report_red_flag(owner, seed, reporter=seed.practitioner_a)
    codes = _open_codes(seed.patient_a)
    assert {"DRESS_UPPER", "DRESS_LOWER", "DRESS_FOOTWEAR"} <= codes


def test_the_suspension_policy_matches_the_schema(owner):
    """
    `SUSPENDED_ON_RED_FLAG` في بايثون و`suspends_on_red_flag` في المخطط
    بيانٌ واحد في موضعين. انحرافهما يعني أن أحدهما يكذب، والعرض يقرأ المخطط.
    """
    with owner.cursor() as cursor:
        cursor.execute("SELECT tier, suspends_on_red_flag FROM kitchen_tier ORDER BY tier")
        rows = cursor.fetchall()

    assert [tier.tier for tier in KITCHEN_TIERS] == [row[0] for row in rows]
    assert SUSPENDED_ON_RED_FLAG == {tier for tier, suspends in rows if suspends}


# ══ السحب ═══════════════════════════════════════════════════════════════
def test_revocation_closes_the_tier_immediately(actor, seed):
    grant = kitchen.authorize(
        actor, patient_id=seed.patient_a, tier=2, basis="تقييم أوّلي"
    )
    assert _open_tiers(seed.patient_a) == {2}

    kitchen.revoke(actor, grant.id)
    assert _open_tiers(seed.patient_a) == set(), "المهمة بقيت مفتوحة بعد السحب"


def test_a_revoked_tier_can_be_granted_again(actor, seed):
    """السحب نهائي للصفّ لا للمستوى: القرار يُراجَع بقرار جديد بأساسه."""
    grant = kitchen.authorize(actor, patient_id=seed.patient_a, tier=2, basis="أوّلي")
    kitchen.revoke(actor, grant.id)
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=2, basis="أعيد التقييم بعد تحسّن")
    assert _open_tiers(seed.patient_a) == {2}


def test_a_second_active_grant_for_one_tier_is_refused(actor, seed):
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis="أوّلي")
    with pytest.raises(kitchen.AuthorizationRefused) as raised:
        kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis="مكرّر")
    assert isinstance(raised.value.__cause__, pg_errors.UniqueViolation), (
        "الرافض يجب أن يكون الفهرس الجزئي لا فحصاً في بايثون"
    )


# ══ الأساس والثبات والتدقيق ═════════════════════════════════════════════
@pytest.mark.parametrize("basis", ["", "   ", "\n\t "])
def test_authorization_needs_a_basis(actor, seed, basis):
    """تفويضٌ بلا أساس قرارٌ بلا سبب، ولا يُراجَع لأنه لا يقول شيئاً."""
    with pytest.raises(ValueError):
        kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis=basis)


def test_a_blank_basis_is_refused_by_the_schema_too(actor, seed, owner):
    """الفحص في بايثون للرسالة؛ الحَكَم هو القيد."""
    with owner.cursor() as cursor, pytest.raises(pg_errors.CheckViolation):
        cursor.execute(
            "INSERT INTO kitchen_authorization (tenant_id, patient_id, tier, basis, granted_by)"
            " VALUES (%s, %s, 1, '   ', %s)",
            (seed.tenant_a, seed.patient_a, seed.practitioner_a),
        )


def test_authorization_rows_are_immutable_and_audited(actor, seed, owner):
    grant = kitchen.authorize(
        actor, patient_id=seed.patient_a, tier=3, basis="اجتاز تقييم الموقد"
    )

    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE kitchen_authorization SET basis = 'غيّرته' WHERE id = %s",
                (grant.id,),
            )
    owner.rollback()

    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute("DELETE FROM kitchen_authorization WHERE id = %s", (grant.id,))
    owner.rollback()

    kitchen.revoke(actor, grant.id)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT action, actor_id, reason FROM audit_log"
            " WHERE entity = 'kitchen_authorization' AND entity_id = %s"
            " ORDER BY occurred_at, id",
            (grant.id,),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == ["GRANT", "REVOKE"]
    assert all(row[1] == seed.practitioner_a for row in rows), "الفعل غير منسوب لفاعله"
    assert rows[0][2] == "اجتاز تقييم الموقد", "الأساس غير مسجَّل في التدقيق"


def test_a_revoked_grant_cannot_be_revived(actor, seed, owner):
    grant = kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis="أوّلي")
    kitchen.revoke(actor, grant.id)

    with owner.cursor() as cursor, pytest.raises(
        pg_errors.CheckViolation, match="مسحوب بالفعل"
    ):
        cursor.execute(
            "UPDATE kitchen_authorization SET revoked_at = NULL, revoked_by = NULL"
            " WHERE id = %s",
            (grant.id,),
        )


def test_only_a_licensed_practitioner_authorizes(seed, owner):
    """
    قيدٌ على `users` يمنع ممارساً بلا رقم ترخيص، فاشتراط الدور اشتراطُ ترخيص.

    التفويض يفتح موقداً لمريض بشلل نصفي؛ وهو قرار سريري لا صلاحية إدارية.
    """
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'ADMIN', 'admin@example.test', 'x') RETURNING id",
            (seed.tenant_a,),
        )
        admin = cursor.fetchone()[0]

        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "INSERT INTO kitchen_authorization"
                " (tenant_id, patient_id, tier, basis, granted_by)"
                " VALUES (%s, %s, 1, 'قرار إداري', %s)",
                (seed.tenant_a, seed.patient_a, admin),
            )


def test_tenant_isolation_on_authorizations(actor, other_actor, seed):
    """ممارس من مستأجر لا يرى تفويضات غيره ولا يمنح لمريضه."""
    kitchen.authorize(actor, patient_id=seed.patient_a, tier=1, basis="أوّلي")

    assert kitchen.for_patient(other_actor, seed.patient_a) == []

    with pytest.raises(kitchen.AuthorizationRefused) as raised:
        kitchen.authorize(
            other_actor, patient_id=seed.patient_a, tier=2, basis="من مستأجر آخر"
        )
    assert isinstance(
        raised.value.__cause__,
        (pg_errors.ForeignKeyViolation, pg_errors.InsufficientPrivilege),
    ), "العزل يجب أن يفرضه المخطط لا الطبقة"


# ══ ترتيب اللبس مفروضاً في المخطط ═══════════════════════════════════════
def test_a_recorded_block_is_still_a_rejection(actor, seed):
    """
    `DressingBlocked` ترث من `DressingRejected`.

    فمستدعٍ يمسك الأصل يمسك هذه أيضاً، ولا يوجد فرعٌ يظن أن الحجب المسجَّل
    أخفّ من الحجب غير المسجَّل.
    """
    from core.adl.types import DressingRejected

    assert issubclass(adl_gate.DressingBlocked, DressingRejected)

    proposal = _dressing_proposal(actor, seed, *WRONG_ORDER)
    with pytest.raises(DressingRejected):
        adl_gate.verify_proposal(actor, proposal.id)


def test_a_wrong_order_program_never_enters_the_queue(actor, seed):
    proposal = _dressing_proposal(actor, seed, *WRONG_ORDER)

    with pytest.raises(adl_gate.DressingBlocked, match="الجانب المصاب"):
        adl_gate.verify_proposal(actor, proposal.id)

    with pytest.raises(proposals.DressingNotVerified):
        proposals.submit(proposal.id, actor)

    assert proposals.get(proposal.id, actor).status == "DRAFT"


def test_the_block_is_recorded_not_silent(actor, seed, owner):
    """
    حجبٌ غير مسجَّل يُخفي العيب الذي سبّبه.

    رفعُ الاستثناء داخل معاملة التسجيل كان يُجهضها فيضيع الصفّ نفسه — وهو
    العيب الذي كُشف في بوابة الصور، ويُفحص هنا قبل أن يتكرر.
    """
    proposal = _dressing_proposal(actor, seed, *WRONG_ORDER)
    with pytest.raises(adl_gate.DressingBlocked):
        adl_gate.verify_proposal(actor, proposal.id)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT verdict, reason FROM dressing_verification WHERE proposal_id = %s",
            (proposal.id,),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == ["BLOCKED"]
    assert "قميص" in rows[0][1], "سبب الحجب لا يسمّي الخطوة المخالفة"


def test_a_correct_program_passes_and_is_delivered(actor, seed):
    proposal = _dressing_proposal(actor, seed, *CORRECT_ORDER)
    adl_gate.verify_proposal(actor, proposal.id)
    approved = proposals.approve(proposals.submit(proposal.id, actor).id, actor)

    assert approved.status == "APPROVED"
    assert delivery.get_deliverable(seed.patient_a, "PLAN") is not None


def test_editing_a_dressing_program_invalidates_its_check(actor, seed, owner):
    """
    الحكم مربوط ببصمة الحمولة، فاستبدالها يُبطله بلا أن يتذكّر أحد.

    هذا هو الباب الذي أُغلق في بوابة الصور: فحصُ برنامجٍ سليم ثم استبداله
    قبل الاعتماد.
    """
    proposal = _dressing_proposal(actor, seed, *CORRECT_ORDER)
    adl_gate.verify_proposal(actor, proposal.id)
    proposals.submit(proposal.id, actor)

    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE proposals SET payload = %s WHERE id = %s",
            (__import__("json").dumps(dressing_payload(*WRONG_ORDER)), proposal.id),
        )

    with pytest.raises(Exception) as raised:
        proposals.approve(proposal.id, actor)
    assert "لم يجتز" in str(raised.value) or raised.type.__name__ == "InvalidTransition"

    assert proposals.get(proposal.id, actor).status == "PENDING"


def test_edit_and_approve_rechecks_the_new_program(actor, seed):
    """المسار المشروع للتعديل يفحص ما سيكتبه، في معاملته نفسها."""
    proposal = _dressing_proposal(actor, seed, *CORRECT_ORDER)
    adl_gate.verify_proposal(actor, proposal.id)
    proposals.submit(proposal.id, actor)

    with pytest.raises(DressingOrderViolation):
        proposals.edit_and_approve(
            proposal.id, actor, payload=dressing_payload(*WRONG_ORDER)
        )
    assert proposals.get(proposal.id, actor).status == "PENDING"

    edited = proposals.edit_and_approve(
        proposal.id,
        actor,
        payload=dressing_payload(
            ("DON", "AFFECTED", "قميص"),
            ("DON", "SOUND", "قميص"),
            ("DON", "BOTH", "قميص"),
        ),
    )
    assert edited.status == "EDITED_APPROVED"


def test_the_gate_holds_for_a_direct_update(actor, seed, practitioner_conn):
    """
    البوابة في المحفّز لا في بايثون: `UPDATE` مباشر بدور الممارس يُرفض أيضاً.

    لو كان الفحص في طبقة المجال وحدها لكان تجاوزه سطراً واحداً من SQL.
    """
    proposal = _dressing_proposal(actor, seed, *WRONG_ORDER)
    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)

    with practitioner_conn.cursor() as cursor, pytest.raises(pg_errors.CheckViolation):
        cursor.execute(
            "UPDATE proposals SET status = 'PENDING', queued_at = now() WHERE id = %s",
            (proposal.id,),
        )


def test_dressing_steps_cannot_hide_in_an_undeclared_payload(actor, seed):
    """
    خطوات لبس في حمولة لا تعلن نفسها كانت تمرّ بلا فحص.

    وهو «مسار التسليم البديل» نفسه الذي أُغلق في الصور: البوابة تحرس ما يقول
    `module = DRESSING`، فما لا يقوله لا يُقبل حمله للخطوات أصلاً.
    """
    with pytest.raises(pg_errors.CheckViolation):
        proposals.create(
            actor,
            patient_id=seed.patient_a,
            kind="PLAN",
            payload={"steps": [{"action": "DON", "side": "SOUND", "garment": "قميص"}]},
        )


def test_a_plan_without_dressing_steps_is_untouched(actor, seed):
    """حارس: المحفّز لا يعترض خططاً عادية تحمل كلمة `steps`."""
    proposal = proposals.create(
        actor,
        patient_id=seed.patient_a,
        kind="PLAN",
        payload={"steps": [{"action": "WALK", "minutes": 10}]},
    )
    assert proposal.status == "DRAFT"
