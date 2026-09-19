"""
معايير قبول القسم 1 — بوابة اعتماد الممارس
============================================
كل اختبار هنا يقابل ضمانة من القواعد المطلقة. تعمل كلها مقابل PostgreSQL
حقيقي: الضمانات مفروضة في طبقة البيانات، فاختبارها بمحاكاة لا يثبت شيئاً.
"""

from __future__ import annotations

import pytest

from datetime import timedelta

from core.clock import now
from core.types import ALLOWED_TRANSITIONS, DELIVERABLE_STATUSES
from tests.conftest import cite_evidence, requires_db, set_actor

psycopg = pytest.importorskip("psycopg")
from psycopg import errors as pg_errors  # noqa: E402

pytestmark = requires_db

ALL_STATUSES = sorted(ALLOWED_TRANSITIONS)


def _insert(owner, seed, **overrides):
    """يُدرج مقترحاً بدور المالك ويُعيد معرّفه."""
    fields = {
        "tenant_id": seed.tenant_a,
        "patient_id": seed.patient_a,
        "kind": "PLAN",
        "status": "DRAFT",
        "payload": '{"steps": []}',
        "created_by": seed.practitioner_a,
    }
    fields.update(overrides)
    columns = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    with owner.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO proposals ({columns}) VALUES ({placeholders}) RETURNING id",
            list(fields.values()),
        )
        return cursor.fetchone()[0]


def _queue(owner, proposal_id):
    # بوابة القسم 3: لا دخول للطابور بلا استشهاد بمصدر مسترجَع. موضعه هنا
    # لأن هذه هي النقطة الوحيدة التي يمرّ منها DRAFT ← PENDING في هذا الملف.
    cite_evidence(owner, proposal_id)
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE proposals SET status='PENDING', queued_at=now() WHERE id=%s", (proposal_id,)
        )


def _approve(owner, proposal_id, reviewer, status="APPROVED"):
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE proposals SET status=%s, reviewer_id=%s, decision_at=now() WHERE id=%s",
            (status, reviewer, proposal_id),
        )


def _drive_to(owner, seed, status, **overrides):
    """يُنشئ مقترحاً ويقوده إلى الحالة المطلوبة عبر مسار مسموح فقط."""
    proposal = _insert(owner, seed, **overrides)
    if status == "DRAFT":
        return proposal

    _queue(owner, proposal)
    if status == "PENDING":
        return proposal

    with owner.cursor() as cursor:
        if status == "REJECTED":
            cursor.execute(
                "UPDATE proposals SET status='REJECTED', reviewer_id=%s, decision_at=now(),"
                " rejection_reason='سبب المراجعة' WHERE id=%s",
                (seed.practitioner_a, proposal),
            )
        elif status == "EXPIRED":
            cursor.execute("UPDATE proposals SET status='EXPIRED' WHERE id=%s", (proposal,))
        else:  # APPROVED | EDITED_APPROVED
            cursor.execute(
                "UPDATE proposals SET status=%s, reviewer_id=%s, decision_at=now() WHERE id=%s",
                (status, seed.practitioner_a, proposal),
            )
    return proposal


# ── صلاحية 48 ساعة ──────────────────────────────────────────────────────
def test_expiry_is_exactly_48_hours(owner, seed):
    proposal = _insert(owner, seed)
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT expires_at - created_at FROM proposals WHERE id=%s", (proposal,)
        )
        assert cursor.fetchone()[0].total_seconds() == 48 * 3600


def test_expiry_cannot_be_forged_on_insert(owner, seed):
    """المحفّز يفرض المدة حتى لو حاول المُدرِج تمديدها."""
    proposal = _insert(owner, seed, expires_at="2099-01-01T00:00:00Z")
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT expires_at - created_at FROM proposals WHERE id=%s", (proposal,)
        )
        assert cursor.fetchone()[0].total_seconds() == 48 * 3600


# ── آلة الحالات ─────────────────────────────────────────────────────────
def test_transition_table_matches_python_source(owner):
    """جدول القاعدة وملف الأنواع مصدر واحد. انحرافهما خطأ صامت خطير."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT from_status, to_status FROM proposal_transition")
        in_database = {(row[0], row[1]) for row in cursor.fetchall()}

    in_python = {
        (source, target)
        for source, targets in ALLOWED_TRANSITIONS.items()
        for target in targets
    }
    assert in_database == in_python


@pytest.mark.parametrize(
    "source, target",
    [
        (source, target)
        for source in ALL_STATUSES
        for target in ALL_STATUSES
        if target not in ALLOWED_TRANSITIONS[source] and source != target
    ],
)
def test_every_disallowed_transition_raises(owner, seed, source, target):
    proposal = _drive_to(owner, seed, source)
    with pytest.raises(psycopg.errors.Error):
        with owner.cursor() as cursor:
            cursor.execute(
                "UPDATE proposals SET status=%s, reviewer_id=%s, decision_at=now(),"
                " rejection_reason='سبب' WHERE id=%s",
                (target, seed.practitioner_a, proposal),
            )


def test_terminal_status_cannot_be_updated(owner, seed):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    _approve(owner, proposal, seed.practitioner_a)

    with pytest.raises(psycopg.errors.Error):
        with owner.cursor() as cursor:
            cursor.execute(
                "UPDATE proposals SET payload='{\"tampered\": true}' WHERE id=%s", (proposal,)
            )


# ── قيود لا يمكن الالتفاف عليها ─────────────────────────────────────────
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_requires_a_real_reason(owner, seed, reason):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    with pytest.raises(pg_errors.CheckViolation):
        with owner.cursor() as cursor:
            cursor.execute(
                "UPDATE proposals SET status='REJECTED', reviewer_id=%s, decision_at=now(),"
                " rejection_reason=%s WHERE id=%s",
                (seed.practitioner_a, reason, proposal),
            )


def test_decision_requires_named_reviewer(owner, seed):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    with pytest.raises(pg_errors.CheckViolation):
        with owner.cursor() as cursor:
            cursor.execute(
                "UPDATE proposals SET status='APPROVED', decision_at=now() WHERE id=%s",
                (proposal,),
            )


def test_illustration_without_affected_side_is_impossible(owner, seed):
    """القاعدة 4: الجانب المصاب غير قابل للقيمة الفارغة في المحتوى المصوَّر."""
    with pytest.raises(pg_errors.CheckViolation):
        _insert(owner, seed, kind="ILLUSTRATION_SET", affected_side=None)


def test_illustration_with_side_is_accepted(owner, seed):
    assert _insert(owner, seed, kind="ILLUSTRATION_SET", affected_side="LEFT")


def test_practitioner_without_license_is_impossible(owner, seed):
    with pytest.raises(pg_errors.CheckViolation):
        with owner.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (tenant_id, role, email, password_hash, license_number)"
                " VALUES (%s, 'PRACTITIONER', 'x@y.test', 'h', NULL)",
                (seed.tenant_a,),
            )


# ── سجل التدقيق append-only ─────────────────────────────────────────────
def test_audit_log_rejects_update(owner, seed):
    _insert(owner, seed)
    with pytest.raises(psycopg.errors.Error):
        with owner.cursor() as cursor:
            cursor.execute("UPDATE audit_log SET action='TAMPERED'")


def test_audit_log_rejects_delete(owner, seed):
    _insert(owner, seed)
    with pytest.raises(psycopg.errors.Error):
        with owner.cursor() as cursor:
            cursor.execute("DELETE FROM audit_log")


def test_every_transition_is_audited(owner, seed):
    set_actor(owner, actor_id=seed.practitioner_a)
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    _approve(owner, proposal, seed.practitioner_a)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT action, from_status, to_status, actor_id FROM audit_log"
            " WHERE entity_id=%s ORDER BY id",
            (proposal,),
        )
        rows = cursor.fetchall()

    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("CREATE", None, "DRAFT"),
        ("TRANSITION", "DRAFT", "PENDING"),
        ("TRANSITION", "PENDING", "APPROVED"),
    ]
    assert all(row[3] == seed.practitioner_a for row in rows), "كل انتقال منسوب إلى فاعل"


def test_rejection_reason_reaches_the_audit_log(owner, seed):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE proposals SET status='REJECTED', reviewer_id=%s, decision_at=now(),"
            " rejection_reason=%s WHERE id=%s",
            (seed.practitioner_a, "الجرعة غير مناسبة للحالة", proposal),
        )
        cursor.execute(
            "SELECT reason FROM audit_log WHERE entity_id=%s AND to_status='REJECTED'",
            (proposal,),
        )
        assert cursor.fetchone()[0] == "الجرعة غير مناسبة للحالة"


# ── نقطة العبور: لا مسار التفافي ────────────────────────────────────────
@pytest.mark.parametrize(
    "table", ["proposals", "proposal_versions", "patients", "users", "audit_log"]
)
def test_patient_role_cannot_touch_content_tables(patient_conn, table):
    """
    الضمانة البنيوية: دور المريض بلا أي صلاحية على جداول المحتوى.
    المسار الالتفافي مستحيل على مستوى الصلاحيات، لا ممنوع باتفاق.
    """
    with pytest.raises(pg_errors.InsufficientPrivilege):
        with patient_conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")  # noqa: S608 - اسم من قائمة ثابتة


@pytest.mark.parametrize("status", sorted(set(ALL_STATUSES) - DELIVERABLE_STATUSES))
def test_unapproved_content_never_reaches_the_patient(owner, patient_conn, seed, status):
    proposal = _insert(owner, seed)
    if status != "DRAFT":
        _queue(owner, proposal)
        if status == "REJECTED":
            with owner.cursor() as cursor:
                cursor.execute(
                    "UPDATE proposals SET status='REJECTED', reviewer_id=%s,"
                    " decision_at=now(), rejection_reason='سبب' WHERE id=%s",
                    (seed.practitioner_a, proposal),
                )
        elif status == "EXPIRED":
            with owner.cursor() as cursor:
                cursor.execute("UPDATE proposals SET status='EXPIRED' WHERE id=%s", (proposal,))

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 0, f"محتوى بحالة {status} وصل المريض"


def test_approved_content_reaches_the_patient(owner, patient_conn, seed):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    _approve(owner, proposal, seed.practitioner_a)

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT proposal_id FROM patient_deliverable_v")
        assert [row[0] for row in cursor.fetchall()] == [proposal]


def test_edited_approved_also_reaches_the_patient(owner, patient_conn, seed):
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    _approve(owner, proposal, seed.practitioner_a, status="EDITED_APPROVED")

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 1


def test_expired_approval_is_not_delivered(owner, patient_conn, seed):
    """
    مقترح اعتُمد ثم انقضت صلاحيته لا يُسلَّم.

    تُحاكى الصلاحية المنقضية بتأريخ الإنشاء لا بتعديل `expires_at` بعد
    الاعتماد: الصف النهائي غير قابل للتعديل، وهذه ضمانة مقصودة.
    """
    proposal = _drive_to(
        owner, seed, "APPROVED", created_at=now() - timedelta(hours=49)
    )

    with owner.cursor() as cursor:
        cursor.execute("SELECT expires_at < now() FROM proposals WHERE id=%s", (proposal,))
        assert cursor.fetchone()[0], "التهيئة لم تُنتج مقترحاً منتهي الصلاحية"

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 0


def test_patient_cannot_read_another_patients_content(owner, patient_conn, seed):
    """معيار القبول 7: مريض لا يقرأ بيانات مريض آخر."""
    other = _insert(owner, seed, tenant_id=seed.tenant_b, patient_id=seed.patient_b,
                    created_by=seed.practitioner_b)
    _queue(owner, other)
    _approve(owner, other, seed.practitioner_b)

    set_actor(patient_conn, patient_id=seed.patient_a)
    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 0


def test_delivery_is_closed_when_no_patient_context(owner, patient_conn, seed):
    """سياق غائب ⇒ لا شيء يُسلَّم. الفشل مغلق لا مفتوح."""
    proposal = _insert(owner, seed)
    _queue(owner, proposal)
    _approve(owner, proposal, seed.practitioner_a)

    with patient_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM patient_deliverable_v")
        assert cursor.fetchone()[0] == 0


# ── عزل المستأجرين ──────────────────────────────────────────────────────
def test_practitioner_cannot_read_other_tenant(owner, practitioner_conn, seed):
    _insert(owner, seed, tenant_id=seed.tenant_b, patient_id=seed.patient_b,
            created_by=seed.practitioner_b)

    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with practitioner_conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM proposals")
        assert cursor.fetchone()[0] == 0


def test_practitioner_cannot_write_into_other_tenant(owner, practitioner_conn, seed):
    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with pytest.raises(psycopg.errors.Error):
        with practitioner_conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO proposals (tenant_id, patient_id, kind, payload)"
                " VALUES (%s, %s, 'PLAN', '{}')",
                (seed.tenant_b, seed.patient_b),
            )


def test_practitioner_sees_own_tenant(owner, practitioner_conn, seed):
    proposal = _insert(owner, seed)
    set_actor(practitioner_conn, tenant_id=seed.tenant_a, actor_id=seed.practitioner_a)
    with practitioner_conn.cursor() as cursor:
        cursor.execute("SELECT id FROM proposals")
        assert [row[0] for row in cursor.fetchall()] == [proposal]


# ── قياس زمن المراجعة ───────────────────────────────────────────────────
def test_review_time_is_stored_and_queryable(owner, seed):
    proposal = _insert(owner, seed)
    cite_evidence(owner, proposal)
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE proposals SET status='PENDING', queued_at = now() - interval '90 seconds'"
            " WHERE id=%s",
            (proposal,),
        )
    _approve(owner, proposal, seed.practitioner_a)

    with owner.cursor() as cursor:
        cursor.execute("SELECT review_seconds FROM proposals WHERE id=%s", (proposal,))
        assert cursor.fetchone()[0] == pytest.approx(90, abs=5)


# ── امتيازات الأدوار ────────────────────────────────────────────────────
def test_connecting_owner_is_not_a_superuser(owner):
    """
    حتى دور المالك — الذي يُشغّل الترحيلات ويقرأ الجلسات — ليس superuser.

    الـsuperuser يتجاوز RLS، فيُبطل `FORCE ROW LEVEL SECURITY`، ويُظهر أيضاً
    قيم الصف المخالف في سجل الخادم عند انتهاك قيد. كلاهما يخالف القواعد.
    """
    with owner.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        is_superuser, bypasses_rls = cursor.fetchone()

    assert not is_superuser, "دور الاتصال superuser — RLS معطّل فعلياً"
    assert not bypasses_rls, "دور الاتصال يحمل BYPASSRLS — RLS معطّل فعلياً"


@pytest.mark.parametrize("role", ["app_practitioner", "app_patient"])
def test_application_roles_cannot_bypass_rls(owner, role):
    """
    دور التطبيق ليس superuser ولا يحمل BYPASSRLS.

    كلاهما يتجاوز عزل الصفوف **بصمت وبلا أي خطأ**: لا سياسة تُطبَّق، ولا سجل
    يُكتب، ولا اختبار آخر في هذا الملف يلاحظ. نشرٌ بدور كهذا يُبطل عزل
    المستأجرين وترشيح نقطة العبور معاً بينما يبقى كل شيء أخضر.
    """
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", (role,)
        )
        row = cursor.fetchone()

    assert row is not None, f"الدور {role} غير موجود — الترحيل لم يُطبَّق"
    is_superuser, bypasses_rls = row
    assert not is_superuser, f"{role} دور superuser — يتجاوز RLS كلياً"
    assert not bypasses_rls, f"{role} يحمل BYPASSRLS — يتجاوز RLS كلياً"


@pytest.mark.parametrize("role_conn", ["practitioner_conn", "patient_conn"])
def test_no_application_role_can_forge_an_audit_entry(request, seed, role_conn):
    """
    سجل التدقيق غير قابل للتزوير، لا append-only فحسب.

    المحفّزات تكتب بصلاحيات مالكها (SECURITY DEFINER)، فلا يحتاج أي دور تطبيق
    الكتابة المباشرة — وسحبها يعني أن كل صف في السجل واقعة حدثت فعلاً، لا
    سطراً كتبه من أراد.
    """
    connection = request.getfixturevalue(role_conn)
    with pytest.raises(pg_errors.InsufficientPrivilege):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_log (tenant_id, entity, entity_id, action)"
                " VALUES (%s, 'proposal', gen_random_uuid(), 'FORGED')",
                (seed.tenant_a,),
            )


def test_transitions_are_still_audited_after_the_revoke(owner, seed):
    """حارس: سحب الصلاحية لم يُسكِت السجل."""
    proposal = _drive_to(owner, seed, "APPROVED")
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM audit_log WHERE entity_id = %s", (proposal,)
        )
        assert cursor.fetchone()[0] == 3
