"""
أداء المريض · الالتزام · التصعيد — معايير قبول القسم 2
========================================================
تركيز هذا الملف على ما سمّاه التدقيق «منطقة خطر عالية»: حدود اليوم.

سؤال «هل أدّى جلسة اليوم؟» يجب أن يعطي الإجابة نفسها من أي مسار. الرياض
+03 دائماً، فمنتصف الليل المحلي هو 21:00 UTC — وكل اختبار هنا يدور حول تلك
اللحظة، لأن حساب الالتزام على فروق 24 ساعة بدل الأيام التقويمية يخطئ عندها
تحديداً.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from core import db, escalation, proposals, sessions
from core.clock import local_day, now
from core.types import Actor
from tests.conftest import cite_evidence_as, requires_db

psycopg = pytest.importorskip("psycopg")

pytestmark = requires_db

#: منتصف الليل بتوقيت الرياض = 21:00 UTC في اليوم السابق.
RIYADH_MIDNIGHT_UTC_HOUR = 21


@pytest.fixture(autouse=True)
def _reset_pools():
    yield
    db.shutdown()


@pytest.fixture
def practitioner(seed) -> Actor:
    return Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)


@pytest.fixture
def approved_plan(practitioner, seed):
    """خطة معتمدة — لا تُسجَّل جلسة على غيرها."""
    plan = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="PLAN",
        payload={"home_program": "تمارين يومية"},
    )
    cite_evidence_as(practitioner, plan.id)
    proposals.submit(plan.id, practitioner)
    return proposals.approve(plan.id, practitioner).id


def _record(seed, plan_id, **overrides):
    fields = {
        "tenant_id": seed.tenant_a,
        "patient_id": seed.patient_a,
        "plan_id": plan_id,
        "outcome": "DONE",
        "recorded_by": seed.practitioner_a,
        "client_uuid": uuid4(),
    }
    fields.update(overrides)
    return sessions.record(**fields)


# ── حدود اليوم ──────────────────────────────────────────────────────────
def test_local_day_matches_python(owner):
    """
    نظيرا `local_day` — في SQL وفي Python — يعطيان اليوم نفسه.

    انحرافهما يعني أن الالتزام المعروض للمريض يخالف الالتزام المخزَّن، وهو
    خطأ صامت لا يكشفه شيء آخر.
    """
    moments = [
        datetime(2026, 3, 15, hour, minute, tzinfo=timezone.utc)
        for hour in (0, 12, 20, 21, 23)
        for minute in (0, 59)
    ]
    moments += [
        datetime(2026, 12, 31, 21, 0, tzinfo=timezone.utc),
        datetime(2027, 1, 1, 20, 59, 59, tzinfo=timezone.utc),
        datetime(2026, 2, 28, 21, 0, tzinfo=timezone.utc),
    ]

    with owner.cursor() as cursor:
        for moment in moments:
            cursor.execute("SELECT local_day(%s)", (moment,))
            assert cursor.fetchone()[0] == local_day(moment), f"اختلاف عند {moment}"


@pytest.mark.parametrize(
    "utc_hour, expected_offset_days",
    [(20, 0), (RIYADH_MIDNIGHT_UTC_HOUR, 1), (23, 1)],
)
def test_session_lands_on_the_local_calendar_day(
    seed, approved_plan, utc_hour, expected_offset_days
):
    """20:59 UTC ما زال أمس محلياً؛ 21:00 UTC هو اليوم التالي."""
    base = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2)
    moment = base.replace(hour=utc_hour, minute=0)

    recorded = _record(seed, approved_plan, occurred_at=moment)

    assert recorded.local_day == moment.date() + timedelta(days=expected_offset_days)
    assert recorded.local_day == local_day(moment)


def test_two_sessions_minutes_apart_can_fall_on_different_days(seed, approved_plan):
    """دقيقتان حول منتصف الليل المحلي = يومان مختلفان في حساب الالتزام."""
    base = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=3)
    before = base.replace(hour=RIYADH_MIDNIGHT_UTC_HOUR - 1, minute=59)
    after = base.replace(hour=RIYADH_MIDNIGHT_UTC_HOUR, minute=1)

    first = _record(seed, approved_plan, occurred_at=before)
    second = _record(seed, approved_plan, occurred_at=after)

    assert (after - before) < timedelta(minutes=5)
    assert first.local_day != second.local_day
    assert second.local_day == first.local_day + timedelta(days=1)


def test_did_session_today_is_false_before_any_session(seed, approved_plan):
    assert sessions.did_session_today(seed.patient_a) is False


def test_did_session_today_is_true_after_recording(seed, approved_plan):
    _record(seed, approved_plan)
    assert sessions.did_session_today(seed.patient_a) is True


def test_yesterdays_session_does_not_count_as_today(seed, approved_plan):
    """جلسة أمس لا تجعل اليوم ملتزَماً به."""
    _record(seed, approved_plan, occurred_at=now() - timedelta(days=1))
    assert sessions.did_session_today(seed.patient_a) is False


def test_did_session_today_agrees_with_the_adherence_window(seed, approved_plan):
    """مسارا الإجابة عن «اليوم» لا يختلفان."""
    _record(seed, approved_plan)
    window = sessions.adherence(seed.patient_a, days=7)
    today_in_window = next(d for d in window.days if d.day == local_day(now()))

    assert sessions.did_session_today(seed.patient_a) == today_in_window.is_adherent


# ── المزامنة المتأخرة ───────────────────────────────────────────────────
def test_late_sync_counts_on_the_day_it_happened(seed, approved_plan):
    """
    جلسة أُدّيت قبل ثلاثة أيام وتُزامَن اليوم تُحسب في يومها.

    الاعتماد على لحظة الاستلام كان سيجعل انقطاع الشبكة يبدو التزاماً مثالياً
    في يوم العودة وانقطاعاً كاملاً في أيام الانقطاع.
    """
    happened = now() - timedelta(days=3)
    recorded = _record(seed, approved_plan, occurred_at=happened)

    assert recorded.local_day == local_day(happened)
    assert recorded.local_day != local_day(recorded.recorded_at)

    window = sessions.adherence(seed.patient_a, days=7)
    adherent = {day.day for day in window.days if day.is_adherent}
    assert adherent == {local_day(happened)}


def test_resending_the_same_client_uuid_does_not_duplicate(seed, approved_plan):
    """إعادة المزامنة بعد انقطاع لا تُضاعف السجل — ولا تفقده."""
    client_uuid = uuid4()
    first = _record(seed, approved_plan, client_uuid=client_uuid)
    second = _record(seed, approved_plan, client_uuid=client_uuid)

    assert first.id == second.id

    window = sessions.adherence(seed.patient_a, days=2)
    assert sum(day.sessions for day in window.days) == 1


def test_distinct_client_uuids_are_two_sessions(seed, approved_plan):
    _record(seed, approved_plan)
    _record(seed, approved_plan)
    window = sessions.adherence(seed.patient_a, days=2)
    assert sum(day.sessions for day in window.days) == 2


def test_a_future_session_is_refused(seed, approved_plan):
    """ساعة جهاز خاطئة ليست مزامنة متأخرة."""
    with pytest.raises(sessions.PlanNotDeliverable):
        _record(seed, approved_plan, occurred_at=now() + timedelta(hours=2))


def test_an_ancient_session_is_refused(seed, approved_plan):
    with pytest.raises(sessions.PlanNotDeliverable):
        _record(seed, approved_plan, occurred_at=now() - timedelta(days=60))


# ── الالتزام ────────────────────────────────────────────────────────────
def test_adherence_counts_calendar_days_not_sessions(seed, approved_plan):
    """ثلاث جلسات في يوم واحد = يوم ملتزَم به واحد، لا ثلاثة."""
    for _ in range(3):
        _record(seed, approved_plan)

    window = sessions.adherence(seed.patient_a, days=10)
    assert window.adherent_days == 1
    assert window.percentage == 10.0


def test_adherence_window_includes_days_without_sessions(seed, approved_plan):
    """
    الأيام الخالية تدخل المقام.

    بدونها يظهر مريض سجّل يوماً واحداً من ثلاثين ملتزماً بنسبة 100%.
    """
    _record(seed, approved_plan)
    window = sessions.adherence(seed.patient_a, days=30)

    assert window.total_days == 30
    assert len(window.days) == 30
    assert window.adherent_days == 1
    assert window.percentage == pytest.approx(3.3)


def test_adherence_is_zero_without_any_session(seed, approved_plan):
    window = sessions.adherence(seed.patient_a, days=7)
    assert window.adherent_days == 0 and window.percentage == 0.0


# ── سلامة السجل ─────────────────────────────────────────────────────────
def test_session_on_an_unapproved_plan_is_refused(practitioner, seed):
    """لا أداء على محتوى لم يصل المريض."""
    draft = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="PLAN", payload={"x": 1}
    )
    with pytest.raises(sessions.PlanNotDeliverable):
        _record(seed, draft.id)


def test_session_on_another_patients_plan_is_refused(practitioner, seed):
    """
    معرّف خطة مريض آخر لا يُقبل حتى لو خُمِّن.

    المفتاح الخارجي وحده كان يمرّره: فحصه يتجاوز عزل الصفوف.
    """
    other = Actor(id=seed.practitioner_b, role="PRACTITIONER", tenant_id=seed.tenant_b)
    theirs = proposals.create(
        other, patient_id=seed.patient_b, kind="PLAN", payload={"x": 1}
    )
    cite_evidence_as(other, theirs.id)
    proposals.submit(theirs.id, other)
    proposals.approve(theirs.id, other)

    with pytest.raises(sessions.PlanNotDeliverable):
        _record(seed, theirs.id)


def test_a_recorded_session_cannot_be_rewritten(owner, seed, approved_plan):
    """سجل الواقعة يُصحَّح بتسجيل جديد لا بتعديل القديم."""
    recorded = _record(seed, approved_plan)
    with owner.cursor() as cursor:
        with pytest.raises(psycopg.errors.Error):
            cursor.execute(
                "UPDATE patient_sessions SET outcome = 'DONE' WHERE id = %s", (recorded.id,)
            )


def test_a_recorded_session_cannot_be_deleted(owner, seed, approved_plan):
    recorded = _record(seed, approved_plan)
    with owner.cursor() as cursor:
        with pytest.raises(psycopg.errors.Error):
            cursor.execute("DELETE FROM patient_sessions WHERE id = %s", (recorded.id,))


def test_patient_cannot_read_another_patients_sessions(seed, approved_plan):
    """معيار القبول 7 على سجل الأداء."""
    _record(seed, approved_plan)
    assert sessions.adherence(seed.patient_b, days=7).adherent_days == 0
    assert sessions.did_session_today(seed.patient_b) is False


# ── التصعيد ─────────────────────────────────────────────────────────────
def test_red_flag_reaches_the_practitioner_queue(practitioner, seed):
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="ألم حاد في الصدر منذ الصباح", reported_by=seed.practitioner_a,
    )
    queue = escalation.open_reports(practitioner)
    assert [item.id for item in queue] == [flag.id]
    assert queue[0].reported_at is not None, "البلاغ بلا طابع زمني"


def test_the_acknowledgement_carries_no_clinical_content(seed):
    """
    الرد تأكيد استلام فقط: لا تشخيص ولا طمأنة ولا نصيحة.

    النص ثابت ولا يعتمد على محتوى البلاغ، فلا يمكن أن يتحوّل إلى جواب سريري.
    """
    worrying = "هل هذا الألم طبيعي بعد العملية؟"
    _, first = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body=worrying, reported_by=seed.practitioner_a,
    )
    _, second = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="شيء مختلف تماماً", reported_by=seed.practitioner_a,
    )

    assert first == second == escalation.ACKNOWLEDGEMENT
    assert worrying not in first
    for reassurance in ("طبيعي", "لا تقلق", "على الأرجح", "غالباً"):
        assert reassurance not in first, f"الرد يحمل طمأنة: {reassurance}"


def test_acknowledging_records_the_escalation_time(practitioner, seed):
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="دوخة شديدة", reported_by=seed.practitioner_a,
    )
    acknowledged = escalation.acknowledge(flag.id, practitioner, note="اتُّصل بالمريض")

    assert acknowledged.acknowledged_by == practitioner.id
    assert acknowledged.escalation_seconds is not None
    assert acknowledged.escalation_seconds >= 0
    assert escalation.open_reports(practitioner) == []


def test_a_report_cannot_be_acknowledged_twice(practitioner, seed):
    """زمن التصعيد يُقاس مرة واحدة ولا يُستبدل."""
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="ضيق تنفس", reported_by=seed.practitioner_a,
    )
    escalation.acknowledge(flag.id, practitioner)
    with pytest.raises(escalation.AlreadyAcknowledged):
        escalation.acknowledge(flag.id, practitioner)


def test_a_report_body_cannot_be_rewritten(owner, seed):
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="نص البلاغ الأصلي", reported_by=seed.practitioner_a,
    )
    with owner.cursor() as cursor:
        with pytest.raises(psycopg.errors.Error):
            cursor.execute(
                "UPDATE red_flag_reports SET body = 'نص بديل' WHERE id = %s", (flag.id,)
            )


def test_a_report_cannot_be_deleted(owner, seed):
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="بلاغ", reported_by=seed.practitioner_a,
    )
    with owner.cursor() as cursor:
        with pytest.raises(psycopg.errors.Error):
            cursor.execute("DELETE FROM red_flag_reports WHERE id = %s", (flag.id,))


def test_an_empty_report_is_refused(seed):
    for body in ("", "   "):
        with pytest.raises(ValueError):
            escalation.report(
                tenant_id=seed.tenant_a, patient_id=seed.patient_a,
                body=body, reported_by=seed.practitioner_a,
            )


def test_practitioner_does_not_see_another_tenants_reports(practitioner, seed):
    escalation.report(
        tenant_id=seed.tenant_b, patient_id=seed.patient_b,
        body="بلاغ مستأجر آخر", reported_by=seed.practitioner_b,
    )
    assert escalation.open_reports(practitioner) == []


def test_every_report_and_acknowledgement_is_audited(owner, practitioner, seed):
    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a,
        body="خدر في الأطراف", reported_by=seed.practitioner_a,
    )
    escalation.acknowledge(flag.id, practitioner)

    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT action, to_status FROM audit_log WHERE entity = 'red_flag'"
            " AND entity_id = %s ORDER BY id",
            (flag.id,),
        )
        assert [tuple(row) for row in cursor.fetchall()] == [
            ("REPORT", "OPEN"),
            ("ACKNOWLEDGE", "ACKNOWLEDGED"),
        ]
