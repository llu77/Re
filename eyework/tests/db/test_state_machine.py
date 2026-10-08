"""
آلة حالات الحملة في القاعدة
============================
حالة الحملة تحمل قراراً بالمال وبنصٍّ رآه صاحبه. انتقالٌ خاطئ يعني إعلاناً
بنصٍّ لم يعتمده أو بمبلغٍ لم يؤكّده؛ ولذلك تُفرض الآلة في محفّزٍ يقرأ جدول
`campaign_transition`، لا في الخادم وحده، فلا يتجاوزها خطأٌ في الواجهة ولا
عبارةٌ كُتبت على عجل.

يثبت هذا الملف أن الجدول نظيرُ `eyework/states.py` بالضبط، وأن كل انتقالٍ
خارجه يُرفض بقيدٍ مسمّى ولو كتبه المالك، وأن المال لا يتغيّر إلا والنصّ معتمد
ومجالاه نظيرا `eyework/money.py` في الاتجاهين، وأن ما يشهد على القرار — النسخة
المعتمدة ورقم الصفّ والأوقات — يكتبه المحفّز وحده ولو حاول المالك غير ذلك، وأن
سقف الحملات المفتوحة يصمد أمام إدراجين متزامنين. والحالات تُبلغ بالمسار
الإنتاجي: مساعدات التجهيز، وعبارات `eyework.campaigns` نفسها بدور الويب.
"""

from __future__ import annotations

import functools
import hashlib
import io
import threading
import time
from contextlib import contextmanager
from uuid import UUID

import psycopg
import pytest
from PIL import Image
from psycopg import errors
from psycopg.rows import dict_row

from eyework import campaigns, money
from eyework.images import process
from eyework.states import ALLOWED_TRANSITIONS, FINAL, OPEN, Status
from eyework.tests.conftest import add_version, as_user, create_campaign, make_user, row_version

BUDGET = 500
DAYS = 10
OPEN_CAP = 20
SECOND_TITLE = "حقيبة جلدية بنية بحزام"
ROLES = ["app", "owner"]

ALLOWED = sorted(ALLOWED_TRANSITIONS, key=lambda pair: (pair[0].value, pair[1].value))
FORBIDDEN = [
    (source, target)
    for source in Status
    for target in Status
    if source is not target and (source, target) not in ALLOWED_TRANSITIONS
]

_SET_STATUS = "UPDATE campaigns SET status = %s WHERE id = %s"
_STATE = (
    "SELECT status, row_version, current_version_id, approved_version_id, budget_sar, days,"
    " approved_at, ready_at, cancelled_at FROM campaigns WHERE id = %s"
)


def _pair_id(pair: tuple[Status, Status]) -> str:
    return f"{pair[0].value}->{pair[1].value}"


@contextmanager
def rejected(error: type[Exception], constraint: str | None = None):
    with pytest.raises(error) as caught:
        yield
    if constraint is not None:
        assert caught.value.diag.constraint_name == constraint


def execute(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone() if cursor.description else None


def matched(connection, statement: str, params: tuple) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.rowcount


def apply_one(connection, statement: str, params: tuple) -> None:
    """عبارةٌ إنتاجية مشروطة بما رآه صاحبها، يجب أن تصيب صفّها."""
    assert matched(connection, statement, params) == 1


def state(connection, campaign: UUID) -> dict:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(_STATE, (campaign,))
        return cursor.fetchone()


@functools.cache
def clean_jpeg() -> tuple[bytes, int, int]:
    buffer = io.BytesIO()
    Image.effect_noise((640, 480), 40).convert("RGB").save(buffer, "JPEG")
    image = process(buffer.getvalue())
    return image.jpeg, image.width, image.height


def new_campaign(app, user: UUID, *, with_image: bool = True) -> UUID:
    """مسودةٌ بدور الويب، وصورتها بعبارة الإدراج الإنتاجية كما يُخرجها `images.process`."""
    campaign = create_campaign(app, user, with_image=False)
    if with_image:
        jpeg, width, height = clean_jpeg()
        execute(app, campaigns._INSERT_IMAGE, (campaign, user, jpeg, width, height, hashlib.sha256(jpeg).digest()))
    return campaign


def open_count(app) -> int:
    return execute(app, "SELECT count(*) FROM campaigns WHERE status = ANY(%s)", ([s.value for s in OPEN],))[0]


def blocked_on_a_lock(app, pid: int, racer: threading.Thread) -> bool:
    deadline = time.monotonic() + 5
    while racer.is_alive() and time.monotonic() < deadline:
        if execute(app, "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = %s", (pid,)) == (True,):
            return True
        time.sleep(0.01)
    return False


def approve(app, campaign: UUID, version: UUID) -> None:
    apply_one(app, campaigns._APPROVE, (campaign, row_version(app, campaign), version))


def set_money(app, campaign: UUID, budget: int = BUDGET, days: int = DAYS) -> None:
    apply_one(app, campaigns._SET_BUDGET, (budget, campaign, row_version(app, campaign)))
    apply_one(app, campaigns._SET_DAYS, (days, campaign, row_version(app, campaign)))


def drive(app, user: UUID, target: Status) -> UUID:
    """حملةٌ في الحالة المطلوبة بالمسار الإنتاجي. COPY_APPROVED تحمل المال فتقبل التأكيد."""
    campaign = new_campaign(app, user)
    if target is Status.DRAFT:
        return campaign
    if target is Status.CANCELLED:
        apply_one(app, campaigns._CANCEL, (campaign, row_version(app, campaign)))
        return campaign
    version = add_version(app, user, campaign)
    if target is Status.COPY_PROPOSED:
        return campaign
    approve(app, campaign, version)
    set_money(app, campaign)
    if target is Status.COPY_APPROVED:
        return campaign
    apply_one(app, campaigns._CONFIRM, (campaign, row_version(app, campaign), version, BUDGET, DAYS))
    return campaign


def two_versions(app, user: UUID) -> tuple[UUID, UUID, UUID]:
    """حملةٌ مقترَحة بنسختين؛ الثانية هي الحالية."""
    campaign = new_campaign(app, user)
    first = add_version(app, user, campaign)
    second = add_version(app, user, campaign, title=SECOND_TITLE, presets=("NEW_TITLE",))
    return campaign, first, second


def confirmable(app, user: UUID) -> tuple[UUID, UUID, UUID]:
    """حملةٌ معتمدةٌ بمالها، بنسختين، والمعتمدة هي الثانية."""
    campaign, first, second = two_versions(app, user)
    approve(app, campaign, second)
    set_money(app, campaign)
    return campaign, first, second


def open_drafts(app, user: UUID, count: int) -> None:
    for _ in range(count):
        create_campaign(app, user, with_image=False)


@pytest.fixture
def user(owner) -> UUID:
    return make_user(owner, login=b"campaign-owner")


# ── الجدول ونظيره ──────────────────────────────────────────────────────
def test_transition_table_is_the_states_module(app):
    """انتقالٌ يُضاف إلى الجدول أو إلى `states.py` وحده يفرّق ما تعرضه الواجهة عمّا تقبله القاعدة."""
    with app.cursor() as cursor:
        cursor.execute("SELECT from_status, to_status FROM campaign_transition")
        rows = cursor.fetchall()
    assert len(rows) == len(ALLOWED_TRANSITIONS)
    assert set(rows) == {(source.value, target.value) for source, target in ALLOWED_TRANSITIONS}


@pytest.mark.parametrize("statement", [
    "INSERT INTO campaign_transition (from_status, to_status) VALUES ('READY', 'COPY_APPROVED')",
    "UPDATE campaign_transition SET to_status = 'READY'",
    "DELETE FROM campaign_transition",
    "TRUNCATE campaign_transition",
])
def test_app_cannot_rewrite_the_transition_table(app, statement):
    """المحفّز يثق بالجدول؛ دور ويبٍ يكتب فيه يفتح لنفسه أيّ انتقال."""
    with rejected(errors.InsufficientPrivilege):
        execute(app, statement)


# ── كل زوجٍ من الحالات ─────────────────────────────────────────────────
@pytest.mark.parametrize(("source", "target"), ALLOWED, ids=[_pair_id(pair) for pair in ALLOWED])
def test_allowed_transition_succeeds(app, user, source, target):
    """آلةٌ ترفض انتقالاً مسموحاً تحبس صاحب الحملة في حالةٍ لا يخرج منها."""
    campaign = drive(app, user, source)
    assert state(app, campaign)["status"] == source.value
    if (source, target) == (Status.DRAFT, Status.COPY_PROPOSED):
        add_version(app, user, campaign)
    else:
        execute(app, _SET_STATUS, (target.value, campaign))
    assert state(app, campaign)["status"] == target.value


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(("source", "target"), FORBIDDEN, ids=[_pair_id(pair) for pair in FORBIDDEN])
def test_forbidden_transition_is_rejected(owner, app, user, role, source, target):
    """قفزةٌ إلى COPY_APPROVED أو READY، أو عودةٌ من حالةٍ نهائية، تتخطّى قراراً كان يجب أن يسبقها — ولو كتبها المالك."""
    connection = {"app": app, "owner": owner}[role]
    campaign = drive(app, user, source)
    before = state(owner, campaign)
    assert before["status"] == source.value
    expected = "campaign_is_final" if source in FINAL else "campaign_transition"
    with rejected(errors.CheckViolation, expected):
        execute(connection, _SET_STATUS, (target.value, campaign))
    assert state(owner, campaign) == before


@pytest.mark.parametrize("status", sorted(OPEN, key=lambda s: s.value))
def test_rewriting_an_open_status_is_not_a_transition(app, user, status):
    """كتابةٌ تُبقي الحالة كما هي لو أعادت ختم الاعتماد أو مسحت المال لصار تعديل المبلغ قراراً لم يتّخذه أحد."""
    campaign = drive(app, user, status)
    before = state(app, campaign)
    execute(app, _SET_STATUS, (status.value, campaign))
    assert state(app, campaign) == {**before, "row_version": before["row_version"] + 1}


def test_proposal_needs_a_copy(app, user):
    """«نصٌّ مقترَح» بلا نصّ حالةٌ كاذبة تُعرض على صاحبها."""
    campaign = new_campaign(app, user)
    with rejected(errors.CheckViolation, "copy_states_have_copy"):
        execute(app, _SET_STATUS, ("COPY_PROPOSED", campaign))


def test_confirmation_needs_budget_and_days(app, user):
    """تأكيدٌ بلا ميزانيةٍ أو بلا مدّة يُطلق حملةً لا يُعرف كم تُنفق ولا إلى متى."""
    campaign = new_campaign(app, user)
    approve(app, campaign, add_version(app, user, campaign))
    with rejected(errors.CheckViolation, "ready_is_complete"):
        execute(app, _SET_STATUS, ("READY", campaign))
    apply_one(app, campaigns._SET_BUDGET, (BUDGET, campaign, row_version(app, campaign)))
    with rejected(errors.CheckViolation, "ready_is_complete"):
        execute(app, _SET_STATUS, ("READY", campaign))


# ── الولادة مسودة ──────────────────────────────────────────────────────
NOT_A_BARE_DRAFT = [
    pytest.param("INSERT INTO campaigns (user_id, status) VALUES (%s, 'COPY_PROPOSED')", id="status-proposed"),
    pytest.param("INSERT INTO campaigns (user_id, status) VALUES (%s, 'COPY_APPROVED')", id="status-approved"),
    pytest.param("INSERT INTO campaigns (user_id, status) VALUES (%s, 'READY')", id="status-ready"),
    pytest.param("INSERT INTO campaigns (user_id, status, cancelled_at) VALUES (%s, 'CANCELLED', now())",
                 id="status-cancelled"),
    pytest.param("INSERT INTO campaigns (user_id, row_version) VALUES (%s, 7)", id="row_version"),
    pytest.param("INSERT INTO campaigns (user_id, current_version_id) VALUES (%s, gen_random_uuid())",
                 id="current_version_id"),
    pytest.param("INSERT INTO campaigns (user_id, approved_version_id) VALUES (%s, gen_random_uuid())",
                 id="approved_version_id"),
    pytest.param("INSERT INTO campaigns (user_id, budget_sar) VALUES (%s, 500)", id="budget_sar"),
    pytest.param("INSERT INTO campaigns (user_id, days) VALUES (%s, 10)", id="days"),
    pytest.param("INSERT INTO campaigns (user_id, approved_at) VALUES (%s, now())", id="approved_at"),
    pytest.param("INSERT INTO campaigns (user_id, ready_at) VALUES (%s, now())", id="ready_at"),
    pytest.param("INSERT INTO campaigns (user_id, cancelled_at) VALUES (%s, now())", id="cancelled_at"),
]


@pytest.mark.parametrize("statement", NOT_A_BARE_DRAFT)
def test_owner_can_only_insert_a_bare_draft(owner, user, statement):
    """حملةٌ تولد مقترَحةً أو معتمدةً أو بمال تتخطّى كل قرارٍ كان يجب أن يسبقها — ولو أدرجها المالك."""
    with rejected(errors.CheckViolation, "campaign_starts_as_draft"):
        execute(owner, statement, (user,))


@pytest.mark.parametrize("statement", NOT_A_BARE_DRAFT)
def test_app_can_only_name_the_user_on_insert(app, user, statement):
    """منحُ إدراجٍ أوسع من `user_id` يجعل المسودة النظيفة رهن ألّا يخطئ الخادم."""
    as_user(app, user)
    with rejected(errors.InsufficientPrivilege):
        execute(app, statement, (user,))


def test_app_insert_is_a_bare_draft(app, user):
    """ما يُدرجه الويب مسودةٌ بلا نصٍّ ولا مالٍ ولا قرار، برقم الصفّ الأوّل."""
    as_user(app, user)
    campaign = execute(app, campaigns._INSERT_CAMPAIGN, (user,))[0]
    assert state(app, campaign) == {
        "status": "DRAFT", "row_version": 1, "current_version_id": None, "approved_version_id": None,
        "budget_sar": None, "days": None, "approved_at": None, "ready_at": None, "cancelled_at": None,
    }


# ── الحالتان النهائيتان ─────────────────────────────────────────────────
@pytest.mark.parametrize(("role", "statement"), [
    ("app", "UPDATE campaigns SET status = 'DRAFT' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'COPY_PROPOSED' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'READY' WHERE id = %s"),
    ("app", "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s"),
    ("app", "UPDATE campaigns SET days = 20 WHERE id = %s"),
    ("owner", "UPDATE campaigns SET ready_at = now() - interval '1 day' WHERE id = %s"),
    ("owner", "UPDATE campaigns SET approved_at = NULL WHERE id = %s"),
    ("owner", "UPDATE campaigns SET budget_sar = 50 WHERE id = %s"),
])
def test_ready_rejects_every_change_but_cancellation(owner, app, user, role, statement):
    """حملةٌ مؤكَّدة بمبلغها ونصّها لا تتغيّر تحت صاحبها؛ الإلغاء وحده يبقى."""
    connection = {"app": app, "owner": owner}[role]
    campaign = drive(app, user, Status.READY)
    before = state(owner, campaign)
    with rejected(errors.CheckViolation, "campaign_is_final"):
        execute(connection, statement, (campaign,))
    assert state(owner, campaign) == before


def test_ready_can_still_be_cancelled(app, user):
    """إلغاءٌ مرفوض بعد التأكيد يُلزم صاحبه بإنفاقٍ لم يعد يريده؛ وما اعتمده يبقى شاهداً."""
    campaign = drive(app, user, Status.READY)
    before = state(app, campaign)
    apply_one(app, campaigns._CANCEL, (campaign, before["row_version"]))
    after = state(app, campaign)
    assert after["status"] == "CANCELLED" and after["cancelled_at"] is not None
    kept = ("approved_version_id", "approved_at", "ready_at", "budget_sar", "days")
    assert {key: after[key] for key in kept} == {key: before[key] for key in kept}


def test_cancellation_cannot_carry_a_money_change(app, user):
    """إلغاءٌ يغيّر المبلغ معه يترك في السجلّ رقماً لم يؤكّده أحد."""
    campaign = drive(app, user, Status.READY)
    with rejected(errors.CheckViolation, "money_only_while_approved"):
        execute(app, "UPDATE campaigns SET status = 'CANCELLED', budget_sar = 1000 WHERE id = %s", (campaign,))


@pytest.mark.parametrize(("role", "statement"), [
    ("app", "UPDATE campaigns SET status = 'DRAFT' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'COPY_PROPOSED' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'READY' WHERE id = %s"),
    ("app", "UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s"),
    ("app", "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s"),
    ("app", "UPDATE campaigns SET days = 20 WHERE id = %s"),
    ("owner", "UPDATE campaigns SET cancelled_at = now() - interval '1 day' WHERE id = %s"),
    ("owner", "UPDATE campaigns SET status = 'DRAFT', cancelled_at = NULL WHERE id = %s"),
])
def test_cancelled_rejects_every_change(owner, app, user, role, statement):
    """حملةٌ ملغاة تُبعث من جديد تُطلق إعلاناً تخلّى عنه صاحبه، وقد حُذفت صورته."""
    connection = {"app": app, "owner": owner}[role]
    campaign = drive(app, user, Status.CANCELLED)
    before = state(owner, campaign)
    with rejected(errors.CheckViolation, "campaign_is_final"):
        execute(connection, statement, (campaign,))
    assert state(owner, campaign) == before


# ── المال ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("source", "statement", "constraint"), [
    (Status.DRAFT, "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s", "money_only_while_approved"),
    (Status.DRAFT, "UPDATE campaigns SET days = 20 WHERE id = %s", "money_only_while_approved"),
    (Status.COPY_PROPOSED, "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s", "money_only_while_approved"),
    (Status.COPY_PROPOSED, "UPDATE campaigns SET days = 20 WHERE id = %s", "money_only_while_approved"),
    (Status.READY, "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s", "campaign_is_final"),
    (Status.READY, "UPDATE campaigns SET days = 20 WHERE id = %s", "campaign_is_final"),
])
def test_money_changes_only_while_copy_is_approved(app, user, source, statement, constraint):
    """مبلغٌ يُضبط قبل اعتماد النصّ أو بعد التأكيد مالٌ لم يُقرَّر على نصٍّ رآه صاحبه."""
    campaign = drive(app, user, source)
    before = state(app, campaign)
    with rejected(errors.CheckViolation, constraint):
        execute(app, statement, (campaign,))
    assert state(app, campaign) == before


@pytest.mark.parametrize(("source", "statement"), [
    (Status.COPY_APPROVED, "UPDATE campaigns SET status = 'READY', budget_sar = 1000 WHERE id = %s"),
    (Status.COPY_APPROVED, "UPDATE campaigns SET status = 'READY', days = 20 WHERE id = %s"),
    (Status.COPY_APPROVED, "UPDATE campaigns SET status = 'COPY_PROPOSED', budget_sar = 1000 WHERE id = %s"),
    (Status.COPY_PROPOSED, "UPDATE campaigns SET status = 'COPY_APPROVED', budget_sar = 1000 WHERE id = %s"),
])
def test_money_cannot_ride_on_a_status_change(app, user, source, statement):
    """مبلغٌ يتغيّر في عبارة التأكيد نفسها يؤكّد رقماً لم يُعرض على صاحبه."""
    campaign = drive(app, user, source)
    with rejected(errors.CheckViolation, "money_only_while_approved"):
        execute(app, statement, (campaign,))


@pytest.mark.parametrize("statement", [
    "UPDATE campaigns SET budget_sar = 1000 WHERE id = %s",
    "UPDATE campaigns SET days = 20 WHERE id = %s",
    "UPDATE campaigns SET budget_sar = NULL WHERE id = %s",
    "UPDATE campaigns SET days = NULL WHERE id = %s",
])
def test_money_is_frozen_after_unapproval(app, user, statement):
    """تبويبٌ قديم يضبط المبلغ بعد التراجع عن الموافقة يغيّر مالاً قُرّر على نصٍّ لم يعد معتمداً."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    apply_one(app, campaigns._UNAPPROVE, (campaign, row_version(app, campaign)))
    before = state(app, campaign)
    assert (before["status"], before["budget_sar"], before["days"]) == ("COPY_PROPOSED", BUDGET, DAYS)
    with rejected(errors.CheckViolation, "money_only_while_approved"):
        execute(app, statement, (campaign,))
    assert state(app, campaign) == before


def test_money_changes_freely_while_copy_is_approved(app, user):
    """منعٌ يمتدّ إلى COPY_APPROVED يحرم صاحب الحملة من ضبط ميزانيته أصلاً."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    set_money(app, campaign, budget=1000, days=20)
    assert (state(app, campaign)["budget_sar"], state(app, campaign)["days"]) == (1000, 20)


@pytest.mark.parametrize("budget", [0, 75, 10_050, -50, 49])
def test_budget_outside_the_check_is_rejected(app, user, budget):
    """مبلغٌ صفريّ أو كسريّ الخطوة أو فوق السقف يُخزَّن لو أخطأ الخادم في فحصه."""
    assert not money.is_valid_budget(budget)
    campaign = drive(app, user, Status.COPY_APPROVED)
    with rejected(errors.CheckViolation, "budget_in_domain"):
        execute(app, "UPDATE campaigns SET budget_sar = %s WHERE id = %s", (budget, campaign))
    assert state(app, campaign)["budget_sar"] == BUDGET


def test_every_budget_the_money_module_accepts_is_stored(app, user):
    """قيدٌ أضيق من `money.py` يرفض مبلغاً عرضته الواجهة مقبولاً، فيفشل الطلب بعد اختياره."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    for budget in money.BUDGET_VALUES:
        execute(app, "UPDATE campaigns SET budget_sar = %s WHERE id = %s", (budget, campaign))
        assert state(app, campaign)["budget_sar"] == budget


def test_budget_check_refuses_what_the_money_module_refuses(app, user):
    """قيدٌ أوسع من `money.py` يخزّن مبلغاً لا تقرؤه الواجهة: `budget_short` يرفضه فتتعطّل صفحة الحملة، وREADY لا تُصلَح."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    stored = []
    for budget in (*range(-1, 6001), *range(6025, 10_101, 25)):
        if money.is_valid_budget(budget):
            continue
        try:
            execute(app, "UPDATE campaigns SET budget_sar = %s WHERE id = %s", (budget, campaign))
        except errors.CheckViolation as exc:
            assert exc.diag.constraint_name == "budget_in_domain"
        else:
            stored.append(budget)
    assert stored == []


@pytest.mark.parametrize("days", [0, 31, -1])
def test_days_outside_the_check_are_rejected(app, user, days):
    """مدّةٌ صفرية أو أطول من شهر تُخزَّن لو أخطأ الخادم في فحصها."""
    assert not money.is_valid_days(days)
    campaign = drive(app, user, Status.COPY_APPROVED)
    with rejected(errors.CheckViolation, "days_in_range"):
        execute(app, "UPDATE campaigns SET days = %s WHERE id = %s", (days, campaign))
    assert state(app, campaign)["days"] == DAYS


def test_days_check_is_the_money_module(app, user):
    """قيد المدّة ونظيره في `money.py` يقبلان الأيام نفسها، لا أضيق ولا أوسع."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    for days in range(-1, 33):
        if money.is_valid_days(days):
            execute(app, "UPDATE campaigns SET days = %s WHERE id = %s", (days, campaign))
            assert state(app, campaign)["days"] == days
        else:
            with rejected(errors.CheckViolation, "days_in_range"):
                execute(app, "UPDATE campaigns SET days = %s WHERE id = %s", (days, campaign))


# ── الاعتماد ────────────────────────────────────────────────────────────
def test_approval_records_the_version_on_screen(app, user):
    """العميل لا يسمّي ما يُعتمد: المحفّز يسجّل النسخة الحالية لحظة الموافقة ووقتها."""
    campaign, _, second = two_versions(app, user)
    with app.transaction():
        stamped = execute(
            app,
            "UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s"
            " RETURNING approved_version_id, current_version_id, approved_at = now()",
            (campaign,),
        )
    assert stamped == (second, second, True)


def test_owner_cannot_approve_another_version(owner, app, user):
    """اعتمادُ نسخةٍ غير المعروضة ينشر نصّاً لم يره صاحبه — ولو كتبه المالك."""
    campaign, first, second = two_versions(app, user)
    with owner.transaction():
        stamped = execute(
            owner,
            "UPDATE campaigns SET status = 'COPY_APPROVED', approved_version_id = %s,"
            " approved_at = '2000-01-01' WHERE id = %s RETURNING approved_version_id, approved_at = now()",
            (first, campaign),
        )
    assert stamped == (second, True)


def test_owner_cannot_swap_the_approved_version_later(owner, app, user):
    """نسخةٌ معتمدة تُستبدل بعد الموافقة تجعل التأكيد يُطلق نصّاً غير الذي وُوفق عليه."""
    campaign, first, second = two_versions(app, user)
    approve(app, campaign, second)
    approved_at = state(owner, campaign)["approved_at"]
    execute(
        owner,
        "UPDATE campaigns SET approved_version_id = %s, approved_at = now() - interval '1 day' WHERE id = %s",
        (first, campaign),
    )
    after = state(owner, campaign)
    assert (after["approved_version_id"], after["approved_at"]) == (second, approved_at)


def test_approved_copy_cannot_move_under_the_approval(owner, app, user):
    """نسخةٌ حالية تتبدّل والحملة معتمدة تعرض نصّاً غير الذي وُوفق عليه — ولو بدّلها المالك."""
    campaign, first, _ = confirmable(app, user)
    before = state(owner, campaign)
    with rejected(errors.CheckViolation, "approved_copy_is_fixed"):
        execute(owner, "UPDATE campaigns SET current_version_id = %s WHERE id = %s", (first, campaign))
    assert state(owner, campaign) == before


def test_approval_cannot_be_written_without_the_transition(owner, app, user):
    """اعتمادٌ مكتوب على حملةٍ مقترَحة يُظهر نصّاً لم يُوافَق عليه معتمداً."""
    campaign, _, second = two_versions(app, user)
    execute(
        owner,
        "UPDATE campaigns SET approved_version_id = %s, approved_at = now() WHERE id = %s",
        (second, campaign),
    )
    after = state(owner, campaign)
    assert (after["status"], after["approved_version_id"], after["approved_at"]) == ("COPY_PROPOSED", None, None)


def test_approved_is_current_holds_without_the_trigger(owner, app, user):
    """القيد حاجزٌ ثانٍ: لو عُطّل المحفّز لما أمكن مع ذلك اعتمادُ نسخةٍ غير الحالية."""
    campaign, first, second = two_versions(app, user)
    approve(app, campaign, second)
    with owner.transaction():
        execute(owner, "ALTER TABLE campaigns DISABLE TRIGGER trg_campaign_guard")
        with rejected(errors.CheckViolation, "approved_is_current"):
            with owner.transaction():
                execute(owner, "UPDATE campaigns SET approved_version_id = %s WHERE id = %s", (first, campaign))
        raise psycopg.Rollback
    assert state(owner, campaign)["approved_version_id"] == second


def test_unapproval_clears_the_approval_and_keeps_the_money(app, user):
    """اعتمادٌ يبقى بعد التراجع يسمح بتأكيد نصٍّ عُدّل بعده؛ ومالٌ يُمسح يُعاد إدخاله خطأً."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    apply_one(app, campaigns._UNAPPROVE, (campaign, row_version(app, campaign)))
    after = state(app, campaign)
    assert after["status"] == "COPY_PROPOSED"
    assert (after["approved_version_id"], after["approved_at"]) == (None, None)
    assert (after["budget_sar"], after["days"]) == (BUDGET, DAYS)


@pytest.mark.parametrize("statement", [
    "UPDATE campaigns SET approved_version_id = current_version_id WHERE id = %s",
    "UPDATE campaigns SET row_version = 1 WHERE id = %s",
    "UPDATE campaigns SET approved_at = now() WHERE id = %s",
    "UPDATE campaigns SET ready_at = now() WHERE id = %s",
    "UPDATE campaigns SET cancelled_at = now() WHERE id = %s",
    "UPDATE campaigns SET updated_at = now() WHERE id = %s",
    "UPDATE campaigns SET created_at = now() WHERE id = %s",
    "UPDATE campaigns SET user_id = user_id WHERE id = %s",
])
def test_app_updates_only_status_and_money(app, user, statement):
    """منحٌ أوسع من الحالة والمال يجعل كل عمودٍ يشهد على القرار رهن خطأٍ في الخادم."""
    campaign = drive(app, user, Status.COPY_PROPOSED)
    with rejected(errors.InsufficientPrivilege):
        execute(app, statement, (campaign,))


# ── رقم الصفّ والأوقات ─────────────────────────────────────────────────
def test_row_version_moves_by_exactly_one_per_write(app, user):
    """رقمٌ يقفز أو يثبت يجعل الشرط على ما رآه صاحبه يقبل عبارةً قديمة أو يرفض الحديثة."""
    campaign = new_campaign(app, user)
    assert row_version(app, campaign) == 1
    add_version(app, user, campaign)
    assert row_version(app, campaign) == 2
    add_version(app, user, campaign, title=SECOND_TITLE, presets=("NEW_TITLE",))
    assert row_version(app, campaign) == 3
    for statement in (
        "UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s",
        "UPDATE campaigns SET budget_sar = 500 WHERE id = %s",
        "UPDATE campaigns SET budget_sar = 500 WHERE id = %s",
        "UPDATE campaigns SET days = 10 WHERE id = %s",
        "UPDATE campaigns SET status = 'COPY_PROPOSED' WHERE id = %s",
        "UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s",
        "UPDATE campaigns SET status = 'READY' WHERE id = %s",
        "UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s",
    ):
        before = row_version(app, campaign)
        execute(app, statement, (campaign,))
        assert row_version(app, campaign) == before + 1
    assert row_version(app, campaign) == 11


@pytest.mark.parametrize("statement", [
    "UPDATE campaigns SET row_version = 100 WHERE id = %s",
    "UPDATE campaigns SET row_version = row_version + 1 WHERE id = %s",
    "UPDATE campaigns SET row_version = row_version - 1 WHERE id = %s",
    "UPDATE campaigns SET created_at = created_at - interval '1 day' WHERE id = %s",
    "UPDATE campaigns SET id = gen_random_uuid() WHERE id = %s",
])
def test_owner_cannot_write_managed_columns(owner, app, user, statement):
    """رقم صفٍّ يختاره كاتبٌ يجعل عبارةً قديمة تبدو حديثة فتُطبَّق مرتين."""
    campaign = drive(app, user, Status.COPY_PROPOSED)
    before = state(owner, campaign)
    with rejected(errors.CheckViolation, "campaign_managed_columns"):
        execute(owner, statement, (campaign,))
    assert state(owner, campaign) == before


def test_owner_cannot_move_a_campaign_to_another_user(owner, app, two_users):
    """حملةٌ تنتقل إلى حسابٍ آخر تكشف صورة صاحبها ونصّه لغيره."""
    first, second = two_users
    campaign = new_campaign(app, first)
    with rejected(errors.CheckViolation, "campaign_managed_columns"):
        execute(owner, "UPDATE campaigns SET user_id = %s WHERE id = %s", (second, campaign))


def test_created_and_updated_at_are_set_on_insert(owner, user):
    """وقت إنشاءٍ يكتبه المُدرِج يزوّر ترتيب القائمة وعمر الحملة."""
    with owner.transaction():
        stamped = execute(
            owner,
            "INSERT INTO campaigns (user_id, created_at, updated_at) VALUES (%s, '2000-01-01', '2000-01-01')"
            " RETURNING created_at = now() AND updated_at = now()",
            (user,),
        )
    assert stamped == (True,)


def test_updated_at_belongs_to_the_trigger(owner, app, user):
    """وقت تعديلٍ يُكتب بيدٍ يرتّب القائمة على غير آخر تغييرٍ فعلي."""
    campaign = new_campaign(app, user)
    with owner.transaction():
        forged = execute(
            owner,
            "UPDATE campaigns SET updated_at = '2000-01-01' WHERE id = %s RETURNING updated_at = now()",
            (campaign,),
        )
    assert forged == (True,)
    with app.transaction():
        moved = execute(
            app,
            "UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s RETURNING updated_at = now()",
            (campaign,),
        )
    assert moved == (True,)


def test_ready_at_is_stamped_only_by_confirmation(owner, app, user):
    """وقت تأكيدٍ يُكتب قبل التأكيد أو بتاريخٍ آخر يشهد على قرارٍ لم يقع حينها."""
    campaign = drive(app, user, Status.COPY_APPROVED)
    early = execute(
        owner, "UPDATE campaigns SET ready_at = '2000-01-01' WHERE id = %s RETURNING ready_at", (campaign,)
    )
    assert early == (None,)
    with owner.transaction():
        stamped = execute(
            owner,
            "UPDATE campaigns SET status = 'READY', ready_at = '2000-01-01' WHERE id = %s"
            " RETURNING ready_at = now()",
            (campaign,),
        )
    assert stamped == (True,)


def test_cancelled_at_is_stamped_only_by_cancellation(owner, app, user):
    """وقت إلغاءٍ على حملةٍ قائمة، أو بتاريخٍ آخر، يكذب في سجلّ ما حدث."""
    campaign = new_campaign(app, user)
    early = execute(
        owner, "UPDATE campaigns SET cancelled_at = '2000-01-01' WHERE id = %s RETURNING cancelled_at", (campaign,)
    )
    assert early == (None,)
    with owner.transaction():
        stamped = execute(
            owner,
            "UPDATE campaigns SET status = 'CANCELLED', cancelled_at = '2000-01-01' WHERE id = %s"
            " RETURNING cancelled_at = now()",
            (campaign,),
        )
    assert stamped == (True,)


# ── عبارة التأكيد ──────────────────────────────────────────────────────
def test_confirm_applies_once(app, user):
    """ضغطتان على «أكّد» تؤكّدان مرةً واحدة: الثانية تحمل رقم صفٍّ قديماً."""
    campaign, _, second = confirmable(app, user)
    seen = (campaign, row_version(app, campaign), second, BUDGET, DAYS)
    assert matched(app, campaigns._CONFIRM, seen) == 1
    after = state(app, campaign)
    assert matched(app, campaigns._CONFIRM, seen) == 0
    assert after["status"] == "READY" and state(app, campaign) == after


@pytest.mark.parametrize("stale", ["row_version", "version", "budget", "days"])
def test_confirm_bound_to_anything_not_on_screen_changes_nothing(app, user, stale):
    """تأكيدٌ بنسخةٍ أو مبلغٍ أو مدّةٍ غير المعروضة الآن يُطلق ما لم يره صاحبه."""
    campaign, first, second = confirmable(app, user)
    current = row_version(app, campaign)
    seen = {"row_version": current, "version": second, "budget": BUDGET, "days": DAYS}
    seen[stale] = {"row_version": current - 1, "version": first, "budget": BUDGET + 50, "days": DAYS + 1}[stale]
    before = state(app, campaign)
    params = (campaign, seen["row_version"], seen["version"], seen["budget"], seen["days"])
    assert matched(app, campaigns._CONFIRM, params) == 0
    assert state(app, campaign) == before


def test_confirm_from_a_stale_tab_changes_nothing(app, user):
    """تبويبٌ قديم يعرض خمسمئة ريال بعد أن صارت ألفاً في تبويبٍ آخر لا يؤكّد أيّاً منهما."""
    campaign, _, second = confirmable(app, user)
    seen = row_version(app, campaign)
    apply_one(app, campaigns._SET_BUDGET, (1000, campaign, seen))
    assert matched(app, campaigns._CONFIRM, (campaign, seen, second, BUDGET, DAYS)) == 0
    assert matched(app, campaigns._CONFIRM, (campaign, seen, second, 1000, DAYS)) == 0
    assert state(app, campaign)["status"] == "COPY_APPROVED"


# ── سقف الحملات المفتوحة ───────────────────────────────────────────────
def test_twenty_first_open_campaign_is_refused(app, user):
    """بلا سقفٍ يراكم حسابٌ واحد صوراً ومحاولاتٍ بلا حدّ؛ والحالتان النصّيتان مفتوحتان كالمسودة."""
    drive(app, user, Status.COPY_PROPOSED)
    drive(app, user, Status.COPY_APPROVED)
    open_drafts(app, user, OPEN_CAP - 2)
    with rejected(errors.CheckViolation, "open_campaign_cap"):
        create_campaign(app, user, with_image=False)


def test_finished_campaigns_do_not_count_toward_the_cap(app, user):
    """حملةٌ مؤكَّدة أو ملغاة تحجز مكان جديدةٍ فيُمنع صاحبها بعد عشرين حملةً منتهية."""
    drive(app, user, Status.READY)
    drive(app, user, Status.CANCELLED)
    open_drafts(app, user, OPEN_CAP - 1)
    last = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "open_campaign_cap"):
        create_campaign(app, user, with_image=False)
    apply_one(app, campaigns._CANCEL, (last, row_version(app, last)))
    assert state(app, create_campaign(app, user, with_image=False))["status"] == "DRAFT"


def test_open_cap_is_per_user(app, two_users):
    """سقفٌ يبلغه مستخدمٌ لا يمنع غيره من حملته الأولى."""
    first, second = two_users
    open_drafts(app, first, OPEN_CAP)
    assert state(app, create_campaign(app, second, with_image=False))["status"] == "DRAFT"


def test_racing_inserts_cannot_both_take_the_last_place(app, app_url, user):
    """إدراجان متزامنان يريان تسع عشرة مفتوحة فيمرّان معاً، ويتجاوز الحساب السقف بعددِ ما يفتح من تبويبات."""
    open_drafts(app, user, OPEN_CAP - 1)
    outcome = {}
    with psycopg.connect(app_url) as first, psycopg.connect(app_url) as second:
        for connection in (first, second):
            as_user(connection, user)
            connection.commit()

        def insert_second() -> None:
            try:
                execute(second, campaigns._INSERT_CAMPAIGN, (user,))
                second.commit()
                outcome["inserted"] = True
            except errors.CheckViolation as exc:
                second.rollback()
                outcome["constraint"] = exc.diag.constraint_name

        execute(first, campaigns._INSERT_CAMPAIGN, (user,))
        racer = threading.Thread(target=insert_second)
        racer.start()
        waited = blocked_on_a_lock(app, second.info.backend_pid, racer)
        first.commit()
        racer.join(timeout=10)
    assert waited
    assert outcome == {"constraint": "open_campaign_cap"}
    assert open_count(app) == OPEN_CAP
