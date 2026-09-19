"""
أداء المريض والالتزام
======================
ما يسجّله المريض بنفسه عن أدائه، والالتزام المحسوب منه.

تدقيق المرحلة 0: لم يكن في النظام كيان جلسة إطلاقاً، وما كان يُحفظ باسم
«أداء» كان مخرج `random.random()`. كل ما هنا أداء حقيقي مصدره المريض.

**حدود اليوم تعريف واحد.** `local_day` يحسبه محفّز في قاعدة البيانات من
`occurred_at`، ونظيره في `core.clock.local_day`، واختبار يقارن التنفيذين.
لا مستدعٍ يحسب اليوم بنفسه، فلا تختلف إجابة «هل أدّى جلسة اليوم؟» باختلاف
المسار — وهو ما تفرضه القاعدة 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Sequence
from uuid import UUID

from psycopg import errors as pg_errors

from core import db
from core.clock import local_day, now

__all__ = [
    "AdherenceWindow",
    "DayRecord",
    "SessionOutcome",
    "SessionRecord",
    "adherence",
    "did_session_today",
    "history",
    "record",
]

SessionOutcome = Literal["DONE", "PARTIAL", "UNABLE"]

#: أقصى قِدَم تُقبل فيه مزامنة متأخرة — مطابق لقيد قاعدة البيانات.
MAX_SYNC_AGE = timedelta(days=30)


class PlanNotDeliverable(Exception):
    """الخطة غير معتمدة أو لا تخص هذا المريض. لا يُسجَّل أداء على محتوى لم يصل."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: UUID
    patient_id: UUID
    plan_id: UUID
    outcome: SessionOutcome
    occurred_at: datetime
    recorded_at: datetime
    local_day: date
    step_index: int | None = None
    reason: str | None = None
    difficulty: int | None = None
    pain: int | None = None


@dataclass(frozen=True, slots=True)
class DayRecord:
    """يوم تقويمي محلي واحد وما سُجِّل فيه."""

    day: date
    sessions: int
    completed: int

    @property
    def is_adherent(self) -> bool:
        """يوم ملتزَم به: أُدّيت فيه جلسة واحدة على الأقل كاملة أو جزئياً."""
        return self.sessions > 0


@dataclass(frozen=True, slots=True)
class AdherenceWindow:
    """الالتزام على نافذة أيام تقويمية محلية — لا على فروق 24 ساعة."""

    since: date
    until: date
    days: Sequence[DayRecord]

    @property
    def total_days(self) -> int:
        return (self.until - self.since).days + 1

    @property
    def adherent_days(self) -> int:
        return sum(1 for day in self.days if day.is_adherent)

    @property
    def percentage(self) -> float:
        """نسبة الأيام التي سُجِّلت فيها جلسة. نافذة بلا أيام ⇒ صفر لا خطأ."""
        return round(100 * self.adherent_days / self.total_days, 1) if self.total_days else 0.0


_INSERT_SESSION = """
INSERT INTO patient_sessions
    (tenant_id, patient_id, plan_id, step_index, outcome, reason, difficulty, pain,
     occurred_at, recorded_by, client_uuid)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (patient_id, client_uuid) DO NOTHING
RETURNING id, patient_id, plan_id, outcome, occurred_at, recorded_at, local_day,
          step_index, reason, difficulty, pain
"""

_SELECT_BY_CLIENT_UUID = """
SELECT id, patient_id, plan_id, outcome, occurred_at, recorded_at, local_day,
       step_index, reason, difficulty, pain
FROM patient_sessions WHERE patient_id = %s AND client_uuid = %s
"""

_HISTORY = """
SELECT id, patient_id, plan_id, outcome, occurred_at, recorded_at, local_day,
       step_index, reason, difficulty, pain
FROM patient_sessions
WHERE local_day BETWEEN %s AND %s
ORDER BY occurred_at DESC
"""

_ADHERENCE = """
SELECT local_day,
       count(*) AS sessions,
       count(*) FILTER (WHERE outcome = 'DONE') AS completed
FROM patient_sessions
WHERE local_day BETWEEN %s AND %s
GROUP BY local_day
ORDER BY local_day
"""

_TODAY = "SELECT count(*) AS sessions FROM patient_sessions WHERE local_day = %s"


def _to_record(row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        patient_id=row["patient_id"],
        plan_id=row["plan_id"],
        outcome=row["outcome"],
        occurred_at=row["occurred_at"],
        recorded_at=row["recorded_at"],
        local_day=row["local_day"],
        step_index=row["step_index"],
        reason=row["reason"],
        difficulty=row["difficulty"],
        pain=row["pain"],
    )


def record(
    *,
    tenant_id: UUID,
    patient_id: UUID,
    plan_id: UUID,
    outcome: SessionOutcome,
    recorded_by: UUID,
    client_uuid: UUID,
    occurred_at: datetime | None = None,
    step_index: int | None = None,
    reason: str | None = None,
    difficulty: int | None = None,
    pain: int | None = None,
) -> SessionRecord:
    """
    يسجّل جلسة. آمن لإعادة الإرسال.

    `client_uuid` يأتي من الجهاز، فإعادة المزامنة بعد انقطاع تُعيد السجل
    نفسه بدل أن تُضاعفه — «بلا تكرار ولا فقد» يتطلب الاثنين.

    `occurred_at` من الجهاز أيضاً، فالمريض قد يسجّل جلسة أدّاها أمس. قيود
    قاعدة البيانات ترفض المستقبل والقِدَم المفرط، و`local_day` يُشتق منه
    لا من لحظة الاستلام.
    """
    moment = occurred_at or now()
    try:
        with db.session("patient", patient_id=patient_id, actor_id=recorded_by) as cursor:
            cursor.execute(
                _INSERT_SESSION,
                (tenant_id, patient_id, plan_id, step_index, outcome, reason,
                 difficulty, pain, moment, recorded_by, client_uuid),
            )
            row = cursor.fetchone()
            if row is None:
                # ON CONFLICT DO NOTHING: التسجيلة موجودة من مزامنة سابقة.
                cursor.execute(_SELECT_BY_CLIENT_UUID, (patient_id, client_uuid))
                row = cursor.fetchone()
    except (pg_errors.CheckViolation, pg_errors.ForeignKeyViolation) as exc:
        raise PlanNotDeliverable(str(exc)) from exc

    return _to_record(row)


def history(patient_id: UUID, *, since: date, until: date) -> Sequence[SessionRecord]:
    with db.session("patient", patient_id=patient_id) as cursor:
        cursor.execute(_HISTORY, (since, until))
        return [_to_record(row) for row in cursor.fetchall()]


def adherence(patient_id: UUID, *, days: int = 30, until: date | None = None) -> AdherenceWindow:
    """
    الالتزام على أيام تقويمية محلية.

    الأيام بلا تسجيل لا تُعيدها قاعدة البيانات؛ نُكملها هنا بصفر بدل أن
    نقسم على عدد الأيام المسجَّلة — وإلا صار مريض سجّل يوماً واحداً ملتزماً
    بنسبة 100%.
    """
    end = until or local_day(now())
    start = end - timedelta(days=days - 1)

    with db.session("patient", patient_id=patient_id) as cursor:
        cursor.execute(_ADHERENCE, (start, end))
        recorded = {row["local_day"]: row for row in cursor.fetchall()}

    full_window = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = recorded.get(day)
        full_window.append(
            DayRecord(
                day=day,
                sessions=row["sessions"] if row else 0,
                completed=row["completed"] if row else 0,
            )
        )
    return AdherenceWindow(since=start, until=end, days=full_window)


def did_session_today(patient_id: UUID) -> bool:
    """
    هل أدّى المريض جلسة اليوم؟

    التنفيذ الوحيد لهذا السؤال في النظام. اليوم هو اليوم التقويمي المحلي
    من `core.clock`، ومقارنته بعمود `local_day` الذي يملؤه المحفّز.
    """
    with db.session("patient", patient_id=patient_id) as cursor:
        cursor.execute(_TODAY, (local_day(now()),))
        return cursor.fetchone()["sessions"] > 0
