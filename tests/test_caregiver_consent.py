"""
موافقة المرافق — وصولٌ لا يوجد بلا توثيق
=========================================
الضمان المُختبَر هنا: لا مسار يمنح مرافقاً وصولاً إلى بيانات مريض بلا صفّ
موافقة يحمل نصّها ومن أعطاها ومن وثّقها ومتى. الوصول **هو** الصفّ — لا إعداد
جانبي يوازيه — فسحبه يقطعه في اللحظة نفسها.
"""

from __future__ import annotations

import uuid

import pytest
from psycopg import errors as pg_errors

from core import caregivers, identity, proposals
from core.types import Actor
from tests.conftest import cite_evidence_as, requires_db, set_actor

pytestmark = requires_db

CONSENT = "أوافق على أن يطّلع مرافقي على خطتي وأن يسجّل أدائي نيابةً عني."
SECRET = "كلمة-مرور-المرافق"


@pytest.fixture
def actor_a(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


def _user(owner, tenant, role, email, *, password=None):
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (tenant, role, email, identity.hash_password(password or "x")),
        )
        return cursor.fetchone()[0]


@pytest.fixture
def caregiver(owner, seed):
    return _user(owner, seed.tenant_a, "CAREGIVER", "caregiver.a@example.test",
                 password=SECRET)


# ── الصفّ نفسه ──────────────────────────────────────────────────────────
def test_grant_records_the_consent_text_itself(actor_a, seed, caregiver):
    """النصّ يُخزَّن كما وُقِّع، لا إشارة إلى سياسة قد تتغيّر غداً."""
    link = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة المريض", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    assert link.consent_text == CONSENT
    assert link.consent_given_by == "PATIENT"
    assert link.granted_by == seed.practitioner_a
    assert link.is_active


def test_consent_cannot_be_blank(actor_a, seed, caregiver):
    with pytest.raises(caregivers.LinkRefused):
        caregivers.grant(
            actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
            relationship="زوجة", consent_text="   ", consent_given_by="PATIENT",
        )


def test_a_non_caregiver_account_cannot_be_linked(actor_a, seed, owner):
    """معرّف مستخدمٍ مخمَّن لا يصير وصولاً: الدور مفحوص في قاعدة البيانات."""
    ordinary = _user(owner, seed.tenant_a, "PATIENT", "someone.a@example.test")
    with pytest.raises(caregivers.LinkRefused):
        caregivers.grant(
            actor_a, patient_id=seed.patient_a, caregiver_user_id=ordinary,
            relationship="ابن", consent_text=CONSENT, consent_given_by="PATIENT",
        )


def test_a_caregiver_from_another_tenant_cannot_be_linked(actor_a, seed, owner):
    outsider = _user(owner, seed.tenant_b, "CAREGIVER", "caregiver.b@example.test")
    with pytest.raises(caregivers.LinkRefused):
        caregivers.grant(
            actor_a, patient_id=seed.patient_a, caregiver_user_id=outsider,
            relationship="ابن", consent_text=CONSENT, consent_given_by="PATIENT",
        )


def test_a_practitioner_cannot_link_another_tenants_patient(seed, caregiver):
    """عزل المستأجر: الصفّ يحمل مستأجر الفاعل، فمريض الآخر لا يطابقه."""
    actor_b = Actor(id=seed.practitioner_b, role="PRACTITIONER", tenant_id=seed.tenant_b)
    with pytest.raises(caregivers.LinkRefused):
        caregivers.grant(
            actor_b, patient_id=seed.patient_a, caregiver_user_id=caregiver,
            relationship="ابن", consent_text=CONSENT, consent_given_by="PATIENT",
        )


def test_one_active_patient_per_caregiver(actor_a, seed, caregiver, owner):
    """
    الحدّ مقصود: مرافق واحد لمريض واحد في آن.

    يفشل المنح أمام الممارس بدل أن يصير «أيّ المريضين؟» تخميناً عند الدخول.
    """
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO patients (tenant_id, file_number, display_name)"
            " VALUES (%s, 91, 'مريض آخر') RETURNING id",
            (seed.tenant_a,),
        )
        other_patient = cursor.fetchone()[0]

    caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    with pytest.raises(caregivers.LinkRefused):
        caregivers.grant(
            actor_a, patient_id=other_patient, caregiver_user_id=caregiver,
            relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
        )


def test_a_revoked_link_frees_the_caregiver(actor_a, seed, caregiver, owner):
    """السحب يُتيح منحاً جديداً — القيد على الفاعل لا على التاريخ."""
    first = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    caregivers.revoke(actor_a, first.id)

    again = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="GUARDIAN",
    )
    assert again.is_active
    assert again.id != first.id


# ── ثبات الصفّ ──────────────────────────────────────────────────────────
def test_consent_row_is_immutable_except_for_revocation(actor_a, seed, caregiver, owner):
    link = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE caregiver_links SET consent_text = 'نصّ آخر' WHERE id = %s",
                (link.id,),
            )
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute("DELETE FROM caregiver_links WHERE id = %s", (link.id,))


def test_revocation_is_final(actor_a, seed, caregiver, owner):
    link = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    caregivers.revoke(actor_a, link.id)

    assert caregivers.revoke(actor_a, link.id) is None
    with owner.cursor() as cursor:
        with pytest.raises(pg_errors.CheckViolation):
            cursor.execute(
                "UPDATE caregiver_links SET revoked_at = NULL, revoked_by = NULL"
                " WHERE id = %s",
                (link.id,),
            )


def test_every_grant_and_revocation_is_audited(actor_a, seed, caregiver, owner):
    link = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    caregivers.revoke(actor_a, link.id)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT action, actor_id, to_status FROM audit_log"
            " WHERE entity = 'caregiver_link' AND entity_id = %s ORDER BY occurred_at",
            (link.id,),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == ["GRANT", "REVOKE"]
    assert all(row[1] == seed.practitioner_a for row in rows)
    assert [row[2] for row in rows] == ["ACTIVE", "REVOKED"]


# ── الوصول ──────────────────────────────────────────────────────────────
def test_a_caregiver_without_consent_has_no_patient_context(owner, seed, caregiver):
    """حساب مرافق بلا صفّ موافقة يجتاز المصادقة ولا يملك مريضاً — فشل مغلق."""
    _token, principal = identity.authenticate("caregiver.a@example.test", SECRET, "PATIENT")
    assert principal.actor.role == "CAREGIVER"
    assert principal.patient_id is None


def test_consent_grants_the_patient_context(actor_a, seed, caregiver):
    caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    _token, principal = identity.authenticate("caregiver.a@example.test", SECRET, "PATIENT")
    assert principal.patient_id == seed.patient_a


def test_revocation_cuts_access_immediately(actor_a, seed, caregiver):
    """
    الجلسة المفتوحة تموت مع السحب: المحفّز يُبطلها، والاشتقاق يقرأ الصفّ في
    كل طلب. الوصول لا ينتظر انتهاء الرمز.
    """
    link = caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    token, _ = identity.authenticate("caregiver.a@example.test", SECRET, "PATIENT")
    assert identity.resolve_session(token, "PATIENT").patient_id == seed.patient_a

    caregivers.revoke(actor_a, link.id)

    with pytest.raises(identity.AuthenticationFailed):
        identity.resolve_session(token, "PATIENT")


def test_a_caregiver_reads_only_the_linked_patient(actor_a, seed, caregiver, patient_conn):
    """
    المرافق يقرأ عبر نقطة العبور نفسها بسياق المريض المرتبط. سياق مريض آخر
    لا يُعطيه شيئاً — عزل الصفوف لا يعرف «مرافقاً» أصلاً، بل مريضاً واحداً.
    """
    caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    plan = proposals.create(
        actor_a, patient_id=seed.patient_a, kind="PLAN", payload={"steps": []},
    )
    cite_evidence_as(actor_a, plan.id)
    proposals.submit(plan.id, actor_a)
    proposals.approve(plan.id, actor_a)

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 1

    set_actor(patient_conn, patient_id=seed.patient_b)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 0


def test_a_session_recorded_by_a_caregiver_is_attributed_to_them(
    actor_a, seed, caregiver, owner
):
    """
    النسبة لمن نفّذ لا لمن يخصّه السجل: `recorded_by` هو المرافق، و`patient_id`
    هو المريض. بلا هذا التمييز تصير متابعة الأداء رواية عن شخص غير من أدّى.
    """
    from core import sessions

    caregivers.grant(
        actor_a, patient_id=seed.patient_a, caregiver_user_id=caregiver,
        relationship="زوجة", consent_text=CONSENT, consent_given_by="PATIENT",
    )
    plan = proposals.create(
        actor_a, patient_id=seed.patient_a, kind="PLAN", payload={"steps": []},
    )
    cite_evidence_as(actor_a, plan.id)
    proposals.submit(plan.id, actor_a)
    proposals.approve(plan.id, actor_a)

    record = sessions.record(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a, plan_id=plan.id,
        outcome="DONE", recorded_by=caregiver, client_uuid=uuid.uuid4(),
    )

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT recorded_by, patient_id FROM patient_sessions WHERE id = %s",
            (record.id,),
        )
        recorded_by, patient_id = cursor.fetchone()

    assert recorded_by == caregiver
    assert patient_id == seed.patient_a


def test_the_patient_role_cannot_read_the_consent_table(patient_conn, seed):
    """جدول الموافقات ليس محتوى مريض: دور المريض ممنوع منه كلياً."""
    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            cursor.execute("SELECT * FROM caregiver_links")
