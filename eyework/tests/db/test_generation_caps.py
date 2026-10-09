"""
سقوف كلفة النموذج وسلسلة النسخ
===============================
كل استدعاءٍ للنموذج يكلّف مالاً، نجح أم فشل. ولذلك لا تُكتب نسخةٌ إلا على
محاولةٍ مفتوحةٍ محسوبة لهذه الحملة وهذا المستخدم عمرها دون خمس دقائق، والسقوف
— محاولةٌ جارية واحدة، وستٌّ في عشر دقائق، وأربعون محسوبةً في اليوم لكل مستخدم،
وألفان في اليوم للجميع، وعشر نسخٍ لكل حملة — تُفرض في `ew_begin_generation` داخل
القاعدة. خادمٌ أخطأ، أو حلقةٌ تعيد المحاولة، أو دور الويب يحذف محاولاته، لا
يتجاوز شيئاً منها.

يثبت هذا الملف أن كل سقفٍ يرفض عند حدّه بقيدٍ مسمّى ويقبل دونه، وأن ما خرج من
نافذته لا يُحسب، وأن رقم النسخة وتسلسلها يكتبهما المحفّز لا الكاتب، وأن نتيجة
المحاولة تطابق ما كُتب عليها، وأن النسخة لا يُعاد كتابتها ولو بيد المالك.
"""

from __future__ import annotations

import functools
import hashlib
import io
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from PIL import Image
from psycopg import errors

from eyework.images import process
from eyework.tests.conftest import (
    DESCRIPTION,
    TITLE,
    add_version,
    as_user,
    create_campaign,
    make_user,
)

OTHER_TITLE = "حقيبة جلدية بنية بحزام"
OTHER_DESCRIPTION = DESCRIPTION + " تأتي بلونين: البني والأسود."
UNKNOWN_ATTEMPT = UUID("00000000-0000-4000-8000-000000000001")
PAST_RATE_WINDOW = timedelta(minutes=11)

_CURRENT = object()

_INSERT_VERSION = (
    "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
    " edit_presets, edit_note, served_model, prompt_version)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s, 'claude-opus-5-5', 'test') RETURNING version"
)
#: UPSTREAM_TIMEOUT: انقطع الانتظار وقد يكون الطلب حُسب، فيُعدّ في السقف اليومي والعام.
_SEED_ATTEMPTS = (
    "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at,"
    " outcome)"
    " SELECT %s, %s, 'INITIAL', sha256('seeded'::bytea), s.at, s.at + interval '20 seconds', 'UPSTREAM_TIMEOUT'"
    "   FROM generate_series(0, %s) AS g,"
    "        LATERAL (SELECT now() - %s - g * %s AS at) AS s"
)


@contextmanager
def rejected(error: type[Exception], constraint: str | None = None):
    with pytest.raises(error) as caught:
        yield caught
    if constraint is not None:
        assert caught.value.diag.constraint_name == constraint


@functools.cache
def clean_jpeg() -> tuple[bytes, int, int]:
    buffer = io.BytesIO()
    Image.effect_noise((640, 480), 40).convert("RGB").save(buffer, "JPEG")
    image = process(buffer.getvalue())
    return image.jpeg, image.width, image.height


def new_campaign(app, user: UUID, *, with_image: bool = True) -> UUID:
    """مسودةٌ بدور الويب، وصورتها بالمسار الإنتاجي متى طُلبت."""
    campaign = create_campaign(app, user, with_image=False)
    if with_image:
        jpeg, width, height = clean_jpeg()
        as_user(app, user)
        with app.cursor() as cursor:
            cursor.execute(
                "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (campaign, user, jpeg, width, height, hashlib.sha256(jpeg).digest()),
            )
    return campaign


def campaign_state(app, campaign: UUID) -> tuple[int, UUID | None]:
    with app.cursor() as cursor:
        cursor.execute("SELECT row_version, current_version_id FROM campaigns WHERE id = %s", (campaign,))
        return cursor.fetchone()


def begin(app, user: UUID, campaign: UUID, kind: str = "INITIAL", *,
          row: int | None = None, expected=_CURRENT) -> UUID:
    """`ew_begin_generation` بما يراه صاحب الحملة الآن، إلا ما يُطلب تغييره."""
    as_user(app, user)
    current_row, current_version = campaign_state(app, campaign)
    with app.cursor() as cursor:
        cursor.execute(
            "SELECT ew_begin_generation(%s, %s, %s, %s)",
            (campaign, kind, current_row if row is None else row,
             current_version if expected is _CURRENT else expected),
        )
        return cursor.fetchone()[0]


def finish(app, user: UUID, attempt: UUID, outcome: str = "OK") -> None:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_finish_generation(%s, %s, 0, 0)", (attempt, outcome))


def insert_version(app, user: UUID, campaign: UUID, attempt: UUID | None, *, title: str = TITLE,
                   description: str = DESCRIPTION, presets: tuple[str, ...] = (),
                   note: str | None = None) -> int:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute(_INSERT_VERSION, (campaign, user, attempt, title, description, list(presets), note))
        return cursor.fetchone()[0]


def seed_attempts(owner, user: UUID, campaign: UUID, count: int, *,
                  newest: timedelta, spacing: timedelta) -> None:
    """محاولاتٌ منتهية بيد المالك، أحدثها قبل `newest` وبينها `spacing`."""
    with owner.cursor() as cursor:
        cursor.execute(_SEED_ATTEMPTS, (campaign, user, count - 1, newest, spacing))
        assert cursor.rowcount == count


def set_attempt_age(owner, attempt: UUID, age: timedelta) -> None:
    with owner.cursor() as cursor:
        cursor.execute("UPDATE generation_attempts SET started_at = now() - %s WHERE id = %s", (age, attempt))


def age_attempts(owner, user: UUID, by: timedelta) -> None:
    """يعيد محاولات المستخدم إلى الماضي. المحاولة المغلقة لا تُعدَّل ولو بيد المالك
    (`attempt_settled`)، فيُعطَّل حارسها للحظة التعديل وحدها، بيد مالك الجدول."""
    with owner.cursor() as cursor:
        cursor.execute("ALTER TABLE generation_attempts DISABLE TRIGGER trg_attempt_settle")
        try:
            cursor.execute(
                "UPDATE generation_attempts SET started_at = started_at - %s,"
                " finished_at = finished_at - %s WHERE user_id = %s",
                (by, by, user),
            )
        finally:
            cursor.execute("ALTER TABLE generation_attempts ENABLE TRIGGER trg_attempt_settle")


def attempt_count(owner, user: UUID) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM generation_attempts WHERE user_id = %s", (user,))
        return cursor.fetchone()[0]


def attempt_row(owner, attempt: UUID) -> tuple:
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT started_at, finished_at, outcome FROM generation_attempts WHERE id = %s", (attempt,)
        )
        return cursor.fetchone()


def attempts_in_last_day(owner) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM generation_attempts WHERE started_at > now() - interval '24 hours'")
        return cursor.fetchone()[0]


def campaign_status(owner, campaign: UUID) -> str:
    with owner.cursor() as cursor:
        cursor.execute("SELECT status FROM campaigns WHERE id = %s", (campaign,))
        return cursor.fetchone()[0]


def move_to(app, user: UUID, campaign: UUID, status: str) -> None:
    """ينقل حملةً عليها نسخة إلى `status` بدور الويب، عبر انتقالاتها المسموحة."""
    as_user(app, user)
    with app.cursor() as cursor:
        if status in ("COPY_APPROVED", "READY"):
            cursor.execute("UPDATE campaigns SET status = 'COPY_APPROVED' WHERE id = %s", (campaign,))
        if status == "READY":
            cursor.execute("UPDATE campaigns SET budget_sar = 500, days = 7 WHERE id = %s", (campaign,))
            cursor.execute("UPDATE campaigns SET status = 'READY' WHERE id = %s", (campaign,))
        if status == "CANCELLED":
            cursor.execute("UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s", (campaign,))
        cursor.execute("SELECT status FROM campaigns WHERE id = %s", (campaign,))
        assert cursor.fetchone()[0] == status


@contextmanager
def rival_connection(app_url):
    """اتصالٌ ثانٍ بدور الويب لا ينتظر قفلاً أكثر من ثلث ثانية."""
    with psycopg.connect(app_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '300ms'")
        yield connection


def versions_of(owner, campaign: UUID) -> list[int]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT version FROM copy_versions WHERE campaign_id = %s ORDER BY created_at, version",
                       (campaign,))
        return [row[0] for row in cursor.fetchall()]


@pytest.fixture
def draft(app, two_users) -> tuple[UUID, UUID]:
    """مسودةٌ بصورتها لمستخدمٍ واحد."""
    user, _ = two_users
    return user, new_campaign(app, user)


@pytest.fixture
def proposed(app, two_users) -> tuple[UUID, UUID]:
    """حملةٌ عليها نسختها الأولى بالمسار الإنتاجي."""
    user, _ = two_users
    campaign = new_campaign(app, user)
    add_version(app, user, campaign)
    return user, campaign


# ── لا نسخة إلا على محاولةٍ مفتوحةٍ محسوبة ─────────────────────────────


@pytest.mark.parametrize("attempt", [None, UNKNOWN_ATTEMPT], ids=["missing", "unknown"])
def test_version_without_an_attempt_is_refused(app, owner, draft, attempt):
    """نسخةٌ بلا محاولة استدعاءٌ للنموذج لم يُحسب في أيّ سقف."""
    user, campaign = draft
    with rejected(errors.CheckViolation, "version_needs_open_attempt"):
        insert_version(app, user, campaign, attempt)
    assert versions_of(owner, campaign) == []


def test_version_on_a_finished_attempt_is_refused(app, owner, draft):
    """محاولةٌ أُغلقت ثم كُتبت عليها نسخة: نتيجتها المسجّلة كاذبة، وتُستعمل ثانيةً بلا حساب."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    finish(app, user, attempt, "UPSTREAM_TIMEOUT")
    with rejected(errors.CheckViolation, "version_needs_open_attempt"):
        insert_version(app, user, campaign, attempt)
    assert versions_of(owner, campaign) == []


def test_version_on_another_campaigns_attempt_is_refused(app, owner, two_users):
    """محاولةٌ واحدة تحمل نسخاً لحملاتٍ كثيرة فيُدفع لكلّها ثمن واحدة."""
    user, _ = two_users
    counted = new_campaign(app, user)
    other = new_campaign(app, user)
    attempt = begin(app, user, counted)
    with rejected(errors.CheckViolation, "version_needs_open_attempt"):
        insert_version(app, user, other, attempt)
    assert versions_of(owner, other) == []


@pytest.mark.parametrize("onto_their_campaign", [False, True], ids=["my-campaign", "their-campaign"])
def test_version_on_another_users_attempt_is_refused(app, owner, two_users, onto_their_campaign):
    """من يكتب على محاولة غيره يستهلك حصّة ذلك الغير ويُبقي حصّته كاملة."""
    mine, theirs = two_users
    my_campaign = new_campaign(app, mine)
    their_campaign = new_campaign(app, theirs)
    attempt = begin(app, theirs, their_campaign)
    target = their_campaign if onto_their_campaign else my_campaign
    with rejected(errors.CheckViolation, "version_needs_open_attempt"):
        insert_version(app, mine, target, attempt)
    assert versions_of(owner, my_campaign) == []
    assert versions_of(owner, their_campaign) == []


@pytest.mark.parametrize(("age", "accepted"), [
    (timedelta(minutes=4, seconds=50), True),
    (timedelta(minutes=5, seconds=1), False),
    (timedelta(hours=2), False),
], ids=["4m50s", "5m01s", "2h"])
def test_version_needs_an_attempt_younger_than_five_minutes(app, owner, draft, age, accepted):
    """محاولةٌ عالقة خرجت من سقف «الجارية»؛ نسخةٌ متأخّرة عليها تعني توليدين متوازيين."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    set_attempt_age(owner, attempt, age)
    if accepted:
        assert insert_version(app, user, campaign, attempt) == 1
    else:
        with rejected(errors.CheckViolation, "version_needs_open_attempt"):
            insert_version(app, user, campaign, attempt)
        assert versions_of(owner, campaign) == []


# ── الرقم والتسلسل يكتبهما المحفّز ─────────────────────────────────────


def test_versions_are_numbered_one_two_three_on_the_production_path(app, owner, draft):
    """رقمٌ مكرّر أو متخطٍّ يجعل «الحالية» و«المعتمدة» تشيران إلى غير ما رآه صاحبها."""
    user, campaign = draft
    add_version(app, user, campaign)
    add_version(app, user, campaign, presets=("SHORTER",))
    add_version(app, user, campaign, note="أضف ذكر الحزام")
    assert versions_of(owner, campaign) == [1, 2, 3]


def test_version_number_ignores_what_the_writer_claims(app, owner, draft):
    """رقمٌ يختاره الكاتب يسمح بنسختين برقمٍ واحد أو بقفزةٍ تتخطّى سقف العشر."""
    user, campaign = draft
    claimed = [(9, "INITIAL", []), (1, "EDIT", ["SHORTER"]), (1, "EDIT", ["SIMPLER"])]
    numbers = []
    for version, kind, presets in claimed:
        with owner.cursor() as cursor:
            cursor.execute(
                "INSERT INTO generation_attempts (campaign_id, user_id, kind, based_on_version_id, image_sha256)"
                " SELECT c.id, c.user_id, %s, CASE WHEN %s = 'EDIT' THEN c.current_version_id END, i.sha256"
                "   FROM campaigns c JOIN campaign_images i ON i.campaign_id = c.id"
                "  WHERE c.id = %s RETURNING id",
                (kind, kind, campaign),
            )
            attempt = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, version, title, description,"
                " edit_presets, served_model, prompt_version)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, 'claude-opus-5-5', 'test') RETURNING version",
                (campaign, user, attempt, version, TITLE, DESCRIPTION, presets),
            )
            numbers.append(cursor.fetchone()[0])
    assert numbers == [1, 2, 3]


def test_app_cannot_name_the_version_number(app, draft):
    """دور الويب الذي يكتب الرقم بنفسه يتجاوز المحفّز متى أُضعف."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    as_user(app, user)
    with rejected(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, version, title, description,"
            " served_model, prompt_version) VALUES (%s, %s, %s, 5, %s, %s, 'claude-opus-5-5', 'test')",
            (campaign, user, attempt, TITLE, DESCRIPTION),
        )


@pytest.mark.parametrize(("preset", "title", "description", "accepted"), [
    ("NEW_TITLE", OTHER_TITLE, DESCRIPTION, True),
    ("NEW_TITLE", OTHER_TITLE, OTHER_DESCRIPTION, False),
    ("NEW_DESCRIPTION", TITLE, OTHER_DESCRIPTION, True),
    ("NEW_DESCRIPTION", OTHER_TITLE, OTHER_DESCRIPTION, False),
], ids=["title-kept-description", "title-changed-description",
        "description-kept-title", "description-changed-title"])
def test_single_field_edit_keeps_the_other_field(app, owner, proposed, preset, title, description,
                                                 accepted):
    """«عنوانٌ جديد» يُرجع وصفاً غير الذي قرأه صاحبه، فيُعتمد تغييرٌ لم يطلبه ولم ينتبه له."""
    user, campaign = proposed
    attempt = begin(app, user, campaign, "EDIT")
    if accepted:
        assert insert_version(app, user, campaign, attempt, title=title, description=description,
                              presets=(preset,)) == 2
    else:
        with rejected(errors.CheckViolation, "version_sequence"):
            insert_version(app, user, campaign, attempt, title=title, description=description,
                           presets=(preset,))
        assert versions_of(owner, campaign) == [1]


def test_edit_without_presets_or_note_is_refused(app, owner, proposed):
    """تعديلٌ بلا طلبٍ لا يُعرف لماذا كُتب، ويُعرض على صاحبه جواباً لسؤالٍ لم يسأله."""
    user, campaign = proposed
    attempt = begin(app, user, campaign, "EDIT")
    with rejected(errors.CheckViolation, "edit_has_reason"):
        insert_version(app, user, campaign, attempt, title=OTHER_TITLE)
    assert versions_of(owner, campaign) == [1]
    assert insert_version(app, user, campaign, attempt, title=OTHER_TITLE, note="عنوانٌ أوضح") == 2


def test_first_version_carries_no_edit_request(app, owner, draft):
    """نسخةٌ أولى تحمل طلب تعديل تشهد على طلبٍ لم يحدث."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    with rejected(errors.CheckViolation, "edit_has_reason"):
        insert_version(app, user, campaign, attempt, presets=("SHORTER",))
    assert versions_of(owner, campaign) == []


@pytest.mark.parametrize(("kind", "status"), [
    ("INITIAL", "CANCELLED"),
    ("EDIT", "COPY_APPROVED"),
    ("EDIT", "CANCELLED"),
])
def test_version_arriving_after_the_campaign_moved_on_is_refused(app, owner, two_users, kind, status):
    """صاحب الحملة اعتمد نصّه أو ألغاها والنموذج ما زال يكتب؛ نسخةٌ تصل بعدها تكتب فوق قراره."""
    user, _ = two_users
    campaign = new_campaign(app, user)
    if kind == "EDIT":
        add_version(app, user, campaign)
    attempt = begin(app, user, campaign, kind)
    move_to(app, user, campaign, status)
    before = versions_of(owner, campaign)
    with rejected(errors.CheckViolation, "version_sequence"):
        insert_version(app, user, campaign, attempt, title=OTHER_TITLE,
                       presets=("SHORTER",) if kind == "EDIT" else ())
    assert versions_of(owner, campaign) == before
    assert campaign_status(owner, campaign) == status


# ── ew_begin_generation: الحالة والصورة ─────────────────────────────────


@pytest.mark.parametrize("offset", [-1, 1])
def test_begin_refuses_an_unexpected_row_version(app, owner, draft, offset):
    """ضغطةٌ مكرّرة أو تبويبٌ قديم يفتح محاولةً ثانية تُحسب على صاحبها."""
    user, campaign = draft
    current, _ = campaign_state(app, campaign)
    with rejected(errors.CheckViolation, "stale_row_version"):
        begin(app, user, campaign, row=current + offset)
    assert attempt_count(owner, user) == 0


@pytest.mark.parametrize(("status", "with_copy"), [
    ("COPY_PROPOSED", True),
    ("COPY_APPROVED", True),
    ("READY", True),
    ("CANCELLED", True),
    ("CANCELLED", False),
], ids=["proposed", "approved", "ready", "cancelled", "cancelled-draft"])
def test_initial_generation_needs_a_draft(app, owner, two_users, status, with_copy):
    """«أوّل نسخة» على حملةٍ لها نص أو أُغلقت تكتب نسخةً لا مكان لها في السلسلة وتُحسب."""
    user, _ = two_users
    campaign = new_campaign(app, user)
    if with_copy:
        add_version(app, user, campaign)
    move_to(app, user, campaign, status)
    before = attempt_count(owner, user)
    with rejected(errors.CheckViolation, "generation_wrong_state"):
        begin(app, user, campaign, "INITIAL")
    assert attempt_count(owner, user) == before


@pytest.mark.parametrize("status", ["DRAFT", "COPY_APPROVED", "READY", "CANCELLED"])
def test_edit_needs_proposed_copy(app, owner, two_users, status):
    """تعديلٌ على مسودةٍ بلا نصّ أو على نصٍّ اعتُمد أو أُغلق استدعاءٌ مدفوع لا يُكتب منه شيء."""
    user, _ = two_users
    campaign = new_campaign(app, user)
    if status != "DRAFT":
        add_version(app, user, campaign)
    move_to(app, user, campaign, status)
    before = attempt_count(owner, user)
    with rejected(errors.CheckViolation, "generation_wrong_state"):
        begin(app, user, campaign, "EDIT")
    assert attempt_count(owner, user) == before


def test_edit_needs_the_version_its_author_is_looking_at(app, owner, proposed):
    """تعديلٌ طُلب على نسخةٍ قديمة يُطبَّق على نصٍّ لم يره صاحبه."""
    user, campaign = proposed
    _, first = campaign_state(app, campaign)
    add_version(app, user, campaign, presets=("SHORTER",))
    for stale in (first, None):
        with rejected(errors.CheckViolation, "generation_wrong_state"):
            begin(app, user, campaign, "EDIT", expected=stale)
    assert attempt_count(owner, user) == 2


def test_unknown_generation_kind_is_refused(app, owner, draft):
    """نوعٌ مجهول يتخطّى فحوص الحالة كلّها لأنها مكتوبةٌ للنوعين المعروفين."""
    user, campaign = draft
    with rejected(errors.CheckViolation, "generation_wrong_state"):
        begin(app, user, campaign, "REWRITE")
    assert attempt_count(owner, user) == 0


def test_initial_generation_needs_an_image(app, owner, two_users):
    """النموذج بلا صورة يكتب نصّاً عن لا شيء، والاستدعاء يُدفع."""
    user, _ = two_users
    campaign = new_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "generation_needs_image"):
        begin(app, user, campaign)
    assert attempt_count(owner, user) == 0


@pytest.mark.parametrize(("caller", "error"), [
    ("inactive", errors.InsufficientPrivilege),
    ("anonymous", errors.InsufficientPrivilege),
    ("stranger", errors.NoDataFound),
])
def test_begin_needs_an_active_user_and_their_own_campaign(app, owner, two_users, caller, error):
    """حسابٌ معطَّل أو طلبٌ بلا هوية يحرق حصّة النموذج، ومن يبدأ على حملة غيره يُحسب عليه ما لا يملكه."""
    user, stranger = two_users
    campaign = new_campaign(app, user)
    if caller == "inactive":
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET is_active = false WHERE id = %s", (user,))
    as_user(app, {"inactive": user, "anonymous": None, "stranger": stranger}[caller])
    with rejected(error), app.cursor() as cursor:
        cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (campaign,))
    assert attempts_in_last_day(owner) == 0


# ── السقوف ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("age", "blocked"), [
    (timedelta(0), True),
    (timedelta(minutes=4, seconds=50), True),
    (timedelta(minutes=5, seconds=1), False),
], ids=["fresh", "4m50s", "5m01s"])
def test_one_generation_at_a_time_per_user(app, owner, two_users, age, blocked):
    """طلبان متوازيان يضاعفان الكلفة؛ ومحاولةٌ عالقة لا تحبس صاحبها إلى الأبد."""
    user, _ = two_users
    first = new_campaign(app, user)
    second = new_campaign(app, user)
    running = begin(app, user, first)
    set_attempt_age(owner, running, age)
    if blocked:
        with rejected(errors.CheckViolation, "generation_in_progress"):
            begin(app, user, second)
        assert attempt_count(owner, user) == 1
    else:
        assert begin(app, user, second) != running


def test_another_users_running_attempt_does_not_block(app, two_users):
    """سقف «الجارية» على الجميع يجعل مستخدماً واحداً يوقف الخدمة عن غيره."""
    user, other = two_users
    begin(app, other, new_campaign(app, other))
    assert begin(app, user, new_campaign(app, user)) is not None


@pytest.mark.parametrize(("count", "newest"), [
    pytest.param(6, timedelta(minutes=1), id="rate"),
    pytest.param(40, PAST_RATE_WINDOW, id="daily"),
])
def test_other_users_attempts_do_not_count_against_a_user(app, owner, two_users, count, newest):
    """سقفٌ شخصيّ يعدّ محاولات غيره يجعل مستخدماً كثير الطلب يحبس الآخرين عن حصصهم."""
    user, other = two_users
    campaign = new_campaign(app, user)
    seed_attempts(owner, other, new_campaign(app, other, with_image=False), count,
                  newest=newest, spacing=timedelta(seconds=10))
    assert begin(app, user, campaign) is not None


def test_seventh_attempt_in_ten_minutes_is_refused(app, owner, draft):
    """بلا سقفٍ قصير تحرق حلقةٌ في الخادم أو نقراتٌ متتابعة حصّة اليوم في دقائق، ولو وُزّعت على حملاتٍ عدّة."""
    user, campaign = draft
    elsewhere = new_campaign(app, user, with_image=False)
    seed_attempts(owner, user, elsewhere, 5, newest=timedelta(minutes=1, seconds=30),
                  spacing=timedelta(minutes=2))
    sixth = begin(app, user, campaign)
    finish(app, user, sixth, "UPSTREAM_ERROR")
    with rejected(errors.CheckViolation, "generation_rate"):
        begin(app, user, campaign)
    assert attempt_count(owner, user) == 6


def test_forty_first_attempt_in_a_day_is_refused(app, owner, draft):
    """ستٌّ كل عشر دقائق طوال اليوم أكثر من ثمانمئة استدعاء لمستخدمٍ واحد، ولو وُزّعت على حملاتٍ عدّة."""
    user, campaign = draft
    elsewhere = new_campaign(app, user, with_image=False)
    seed_attempts(owner, user, elsewhere, 39, newest=PAST_RATE_WINDOW, spacing=timedelta(minutes=37))
    fortieth = begin(app, user, campaign)
    finish(app, user, fortieth, "UPSTREAM_TIMEOUT")
    with rejected(errors.CheckViolation, "generation_daily_cap"):
        begin(app, user, campaign)
    assert attempt_count(owner, user) == 40


def test_two_thousand_attempts_a_day_stop_everyone(app, owner, two_users):
    """سقوف المستخدم وحدها لا تحدّ الفاتورة متى كثرت الحسابات أو سُرقت."""
    user, other = two_users
    third = make_user(owner, login=b"user-c")
    campaign = new_campaign(app, user)
    seed_attempts(owner, other, new_campaign(app, other, with_image=False), 1000,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(seconds=84))
    seed_attempts(owner, third, new_campaign(app, third, with_image=False), 999,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(seconds=84))
    last = begin(app, user, campaign)
    finish(app, user, last, "UPSTREAM_TIMEOUT")
    with rejected(errors.CheckViolation, "generation_global_cap"):
        begin(app, user, campaign)
    assert attempt_count(owner, user) == 1


def test_deleting_accounts_does_not_make_room_under_the_global_cap(app, owner, two_users):
    """
    حذف الحساب يحذف محاولاته، والسقف العام يعدّها: يبقى منها أثرٌ بلا هوية يعدّه
    السقف يومها، فلا يُفرغه حذفٌ بعد استهلاك.
    """
    user, other = two_users
    third = make_user(owner, login=b"user-c")
    campaign = new_campaign(app, user)
    seed_attempts(owner, other, new_campaign(app, other, with_image=False), 1000,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(seconds=84))
    seed_attempts(owner, third, new_campaign(app, third, with_image=False), 999,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(seconds=84))
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id IN (%s, %s)", (other, third))
        cursor.execute("SELECT count(*) FROM attempt_tombstones")
        assert cursor.fetchone()[0] == 1999
    last = begin(app, user, campaign)
    finish(app, user, last, "UPSTREAM_TIMEOUT")
    with rejected(errors.CheckViolation, "generation_global_cap"):
        begin(app, user, campaign)


def test_traces_older_than_a_day_do_not_count_under_the_global_cap(app, owner, two_users):
    """
    `purge` يحذف الأثر بعد يومه مرةً في اليوم، فقد يبقى أثرٌ عمره بين يومٍ ويومين حتى
    يمرّ. السقف يعدّ آخر 24 ساعة وحدها، فأثرٌ أقدم لا يغلقه على أحد.
    """
    user, _ = two_users
    campaign = new_campaign(app, user)
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO attempt_tombstones (started_at, outcome)"
                       " SELECT now() - interval '25 hours', 'OK' FROM generate_series(1, 2000)")
    begin(app, user, campaign)


def test_the_trace_of_a_deleted_attempt_has_no_identity_and_only_counts_its_day(app, owner, two_users):
    user, _ = two_users
    campaign = new_campaign(app, user)
    recent = begin(app, user, campaign)
    finish(app, user, recent, "OUTPUT_INVALID")
    unbilled = begin(app, user, new_campaign(app, user))
    finish(app, user, unbilled, "UPSTREAM_BUSY")
    old = begin(app, user, new_campaign(app, user))
    finish(app, user, old, "OUTPUT_INVALID")
    with owner.cursor() as cursor:
        cursor.execute("ALTER TABLE generation_attempts DISABLE TRIGGER trg_attempt_settle")
        try:
            cursor.execute("UPDATE generation_attempts SET started_at = now() - interval '25 hours',"
                           " finished_at = now() - interval '25 hours' WHERE id = %s", (old,))
        finally:
            cursor.execute("ALTER TABLE generation_attempts ENABLE TRIGGER trg_attempt_settle")
        cursor.execute("DELETE FROM users WHERE id = %s", (user,))
        cursor.execute("SELECT column_name FROM information_schema.columns"
                       " WHERE table_name = 'attempt_tombstones' ORDER BY column_name")
        # 0008: علامةُ «من حسابٍ مفتوحٍ جديد» لحصّة الجدد، لا هوية.
        assert [row[0] for row in cursor.fetchall()] == ["new_account", "outcome", "started_at"]
        cursor.execute("SELECT outcome FROM attempt_tombstones")
        assert [row[0] for row in cursor.fetchall()] == ["OUTPUT_INVALID"]


def test_concurrent_begins_by_one_user_are_serialized(app, owner, app_url, two_users):
    """طلبان في اللحظة نفسها لا يرى أيٌّ منهما محاولة الآخر، فيمرّان معاً ويتخطّيان سقف «الجارية»."""
    user, _ = two_users
    first = new_campaign(app, user)
    second = new_campaign(app, user)
    with rival_connection(app_url) as rival:
        with app.transaction():
            begin(app, user, first)
            with rejected(errors.LockNotAvailable):
                begin(rival, user, second)
        with rejected(errors.CheckViolation, "generation_in_progress"):
            begin(rival, user, second)
    assert attempt_count(owner, user) == 1


def test_concurrent_begins_cannot_overshoot_the_global_cap(app, owner, app_url, two_users):
    """مستخدمون كثيرون عند الحدّ في اللحظة نفسها يرى كلٌّ منهم الألفين ناقصةً واحدة، فيمرّون جميعاً."""
    user, other = two_users
    third = make_user(owner, login=b"user-c")
    seed_attempts(owner, third, new_campaign(app, third, with_image=False), 1999,
                  newest=PAST_RATE_WINDOW, spacing=timedelta(seconds=30))
    mine = new_campaign(app, user)
    theirs = new_campaign(app, other)
    with rival_connection(app_url) as rival:
        with app.transaction():
            begin(app, user, mine)
            with pytest.raises((errors.LockNotAvailable, errors.CheckViolation)) as caught:
                begin(rival, other, theirs)
        if isinstance(caught.value, errors.CheckViolation):
            assert caught.value.diag.constraint_name == "generation_global_cap"
    assert attempts_in_last_day(owner) == 2000


@pytest.mark.parametrize(("count", "newest", "foreign"), [
    pytest.param(6, timedelta(minutes=10, seconds=30), False, id="rate"),
    pytest.param(40, timedelta(hours=24, minutes=1), False, id="daily"),
    pytest.param(2000, timedelta(hours=24, minutes=1), True, id="global"),
])
def test_attempts_outside_their_window_do_not_count(app, owner, two_users, count, newest, foreign):
    """سقفٌ يعدّ ما خرج من نافذته يحبس صاحبه بعد أن انقضت المدّة التي وُضع لها."""
    user, other = two_users
    campaign = new_campaign(app, user)
    if foreign:
        seed_attempts(owner, other, new_campaign(app, other, with_image=False), count,
                      newest=newest, spacing=timedelta(seconds=1))
    else:
        seed_attempts(owner, user, campaign, count, newest=newest, spacing=timedelta(seconds=1))
    assert begin(app, user, campaign) is not None


def test_eleventh_version_is_refused(app, owner, draft):
    """حملةٌ بلا سقف نسخٍ تبتلع حصّة اليوم في تعديلاتٍ لا تنتهي."""
    user, campaign = draft
    add_version(app, user, campaign)
    for _ in range(9):
        age_attempts(owner, user, PAST_RATE_WINDOW)
        add_version(app, user, campaign, presets=("SHORTER",))
    age_attempts(owner, user, PAST_RATE_WINDOW)
    with rejected(errors.CheckViolation, "version_cap"):
        begin(app, user, campaign, "EDIT")
    assert versions_of(owner, campaign) == list(range(1, 11))
    assert attempt_count(owner, user) == 10


# ── ew_finish_generation ────────────────────────────────────────────────


def test_ok_outcome_needs_a_version(app, owner, draft):
    """«نجح» بلا نسخة يُخفي عن كل مراجعةٍ استدعاءً مدفوعاً لم يُنتج شيئاً."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    with rejected(errors.CheckViolation, "outcome_matches_version"):
        finish(app, user, attempt, "OK")
    assert attempt_row(owner, attempt)[1:] == (None, None)
    finish(app, user, attempt, "OUTPUT_INVALID")
    assert attempt_row(owner, attempt)[2] == "OUTPUT_INVALID"


@pytest.mark.parametrize("outcome", ["REFUSED", "DISCARDED", "UPSTREAM_ERROR"])
def test_version_needs_an_ok_outcome(app, owner, draft, outcome):
    """نسخةٌ معروضة على محاولةٍ «فشلت» تجعل سجلّ الفشل غير ما رآه المستخدم."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    insert_version(app, user, campaign, attempt)
    with rejected(errors.CheckViolation, "outcome_matches_version"):
        finish(app, user, attempt, outcome)
    assert attempt_row(owner, attempt)[1:] == (None, None)
    finish(app, user, attempt, "OK")
    assert attempt_row(owner, attempt)[2] == "OK"


def test_attempt_is_finished_once(app, owner, draft):
    """نتيجةٌ تُعاد كتابتها بعد الإغلاق تمحو ما سُجّل عن استدعاءٍ مدفوع وتزوّر سجلّ الفشل."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    finish(app, user, attempt, "UPSTREAM_TIMEOUT")
    before = attempt_row(owner, attempt)
    with rejected(errors.NoDataFound):
        finish(app, user, attempt, "DISCARDED")
    assert attempt_row(owner, attempt) == before


def test_user_cannot_finish_another_users_attempt(app, owner, two_users):
    """من يغلق محاولة غيره يحرّر عنه سقف «الجارية» أو يزوّر نتيجتها."""
    user, other = two_users
    attempt = begin(app, other, new_campaign(app, other))
    with rejected(errors.NoDataFound):
        finish(app, user, attempt, "UPSTREAM_ERROR")
    assert attempt_row(owner, attempt)[1:] == (None, None)


# ── ما كُتب لا يُعاد كتابته ─────────────────────────────────────────────


@pytest.mark.parametrize("statement", [
    "UPDATE copy_versions SET title = 'عنوانٌ آخر كُتب بعد العرض'",
    "UPDATE copy_versions SET description = description || ' بخصمٍ خاص اليوم.'",
    "UPDATE copy_versions SET warnings = '{}'",
    "UPDATE copy_versions SET attempt_id = attempt_id",
])
def test_versions_are_append_only_even_for_the_owner(owner, proposed, statement):
    """نصٌّ يتغيّر بعد عرضه يجعل ما اعتمده صاحبه غير ما يُنشر باسمه."""
    _, campaign = proposed
    with owner.cursor() as cursor:
        cursor.execute("SELECT title, description, warnings FROM copy_versions WHERE campaign_id = %s",
                       (campaign,))
        before = cursor.fetchone()
        with rejected(errors.InsufficientPrivilege) as caught:
            cursor.execute(statement)
        assert caught.value.diag.message_primary == "append-only: copy_versions"
        cursor.execute("SELECT title, description, warnings FROM copy_versions WHERE campaign_id = %s",
                       (campaign,))
        assert cursor.fetchone() == before


@pytest.mark.parametrize("statement", [
    "UPDATE generation_attempts SET started_at = started_at - interval '1 day'",
    "UPDATE generation_attempts SET finished_at = now(), outcome = 'DISCARDED'",
    "DELETE FROM generation_attempts",
    "TRUNCATE generation_attempts CASCADE",
    "INSERT INTO generation_attempts (campaign_id, user_id, kind) SELECT id, user_id, 'EDIT' FROM campaigns",
])
def test_app_cannot_rewrite_its_own_quota(app, owner, draft, statement):
    """دور الويب الذي يحذف محاولاته أو يرجّع أوقاتها أو يفتحها بنفسه يصفّر كل سقفٍ يُحسب منها."""
    user, campaign = draft
    attempt = begin(app, user, campaign)
    before = attempt_row(owner, attempt)
    as_user(app, user)
    with rejected(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute(statement)
    assert attempt_row(owner, attempt) == before
    assert attempt_count(owner, user) == 1
