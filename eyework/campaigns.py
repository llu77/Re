"""
خدمة الحملات
============
كل وصولٍ إلى جداول الحملة يمرّ من هنا، بعباراتٍ ثابتة في أعلى الملف وبدور
`eyework_app` وهويةِ صاحب الجلسة. القاعدة تفرض الضمانات (العزل، والحالات،
والسقوف، وثبات ما اعتُمد)؛ وهذه الوحدة تترجم أخطاءها إلى نتائج يفهمها
الويب، ولا تكرّر فحصاً تفرضه القاعدة إلا لتقدّم رسالةً أوضح قبله.

**كل كتابةٍ مشروطةٌ بما رآه صاحبها.** `expected_row_version` في كل طلب: ضغطةٌ
مكرّرة بالعين، أو إعادة إرسال، أو تبويبٌ قديم، تُرفض بـ`Conflict` بدل أن
تُطبَّق مرتين. والتأكيد مشروطٌ فوق ذلك بالنسخة والمبلغ والمدّة نفسها.

**النموذج خارج كل معاملة.** المحاولة تُفتح وتُحسب في معاملة، ثم يُستدعى
النموذج بلا قفلٍ محجوز، ثم تُكتب النسخة وتُغلق المحاولة في معاملةٍ ثانية.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from uuid import UUID

from psycopg import errors as pg_errors

from eyework.copy_rules import EditPreset, check_edit_request
from eyework.copywriter import Copywriter, CopyOutcome
from eyework.db import Database
from eyework.images import ProcessedImage
from eyework.money import (
    budget_in_words,
    budget_short,
    daily_amount,
    days_in_words,
    days_short,
    is_valid_budget,
    is_valid_days,
)
from eyework.prompt import PROMPT_VERSION, CopyRequest, PreviousCopy

__all__ = [
    "MAX_PAGE",
    "PAGE_SIZE",
    "AiFailure",
    "Conflict",
    "Invalid",
    "NotFound",
    "Unusable",
    "approve",
    "cancel",
    "confirm",
    "create",
    "edit",
    "generate",
    "get",
    "image_bytes",
    "list_page",
    "remaining_generations",
    "replace_image",
    "restore",
    "set_budget",
    "set_days",
    "unapprove",
]

#: ثلاث حملاتٍ في الصفحة: قائمةٌ تُقرأ بالعين بلا تمرير.
PAGE_SIZE = 3
#: آخر صفحةٍ يقبلها المسار؛ «الأقدم» لا يُعرض بعدها.
MAX_PAGE = 100
DAILY_GENERATIONS = 40
VERSIONS_PER_CAMPAIGN = 10

#: استدعاءاتٌ متزامنة للنموذج في العملية الواحدة. ما زاد ينتظر دوره خارجاً
#: برسالة «مشغولة» بدل أن يحجز خيطاً دقيقةً كاملة.
_GENERATIONS = threading.BoundedSemaphore(8)


class NotFound(Exception):
    """غير موجود — أو لغير صاحب الجلسة، ولا فرق في الجواب."""


class Conflict(Exception):
    """تغيّرت الحملة منذ رآها صاحب الطلب. `code` يسمّي السبب."""

    def __init__(self, code: str = "STALE") -> None:
        super().__init__(code)
        self.code = code


class Invalid(Exception):
    """مدخلٌ لا يُقبل. `code` رمزٌ ثابت."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AiFailure(Exception):
    """لم يُكتب نصٌّ هذه المرة. المحاولة حُسبت."""

    def __init__(self, outcome: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(outcome)
        self.outcome = outcome
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class Unusable:
    """الصورة لا تُظهر منتجاً واحداً صالحاً. الحملة تبقى مسودة لصورةٍ أخرى."""

    reason: str
    view: dict
    #: ما يقترحه المساعد لصورةٍ أصلح، إن كتب شيئاً.
    note: str | None = None


# ── العبارات ────────────────────────────────────────────────────────────
_VIEW = """
SELECT c.id, c.status, c.row_version, c.budget_sar, c.days,
       c.current_version_id, c.approved_version_id,
       c.created_at, c.updated_at, c.ready_at,
       v.version, v.title, v.description, v.warnings, v.based_on_version_id, v.assistant_note,
       (SELECT cv.id FROM copy_versions cv WHERE cv.campaign_id = c.id
         ORDER BY cv.version DESC LIMIT 1) AS newest_version_id,
       EXISTS (SELECT 1 FROM generation_attempts a
                WHERE a.campaign_id = c.id AND a.finished_at IS NULL
                  AND a.started_at > now() - interval '5 minutes') AS generating,
       i.width AS image_width, i.height AS image_height, encode(i.sha256, 'hex') AS image_sha256,
       (SELECT count(*) FROM copy_versions cv WHERE cv.campaign_id = c.id) AS versions_used
  FROM campaigns c
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
  LEFT JOIN campaign_images i ON i.campaign_id = c.id
 WHERE c.id = %s
"""

_LIST = """
SELECT c.id, c.status, c.updated_at, v.title
  FROM campaigns c
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
 WHERE c.status <> 'CANCELLED'
 ORDER BY c.updated_at DESC, c.id
 LIMIT %s OFFSET %s
"""

# ما يعدّه السقف اليومي في `ew_begin_generation` بالضبط: ما ربما فُوتر وحده.
_REMAINING = """
SELECT count(*) AS used FROM generation_attempts
 WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'
"""

_INSERT_CAMPAIGN = "INSERT INTO campaigns (user_id) VALUES (%s) RETURNING id"
_INSERT_IMAGE = """
INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)
VALUES (%s, %s, %s, %s, %s, %s)
"""
_LOCK_DRAFT = "SELECT row_version, status FROM campaigns WHERE id = %s FOR UPDATE"
_REPLACE_IMAGE = """
UPDATE campaign_images SET jpeg = %s, width = %s, height = %s, sha256 = %s
 WHERE campaign_id = %s
"""
_IMAGE = "SELECT jpeg FROM campaign_images WHERE campaign_id = %s"

_BEGIN = "SELECT ew_begin_generation(%s, %s, %s, %s) AS attempt"
_FINISH = "SELECT ew_finish_generation(%s, %s, %s, %s)"
_GENERATION_INPUT = """
SELECT i.jpeg, v.title, v.description
  FROM campaigns c
  JOIN campaign_images i ON i.campaign_id = c.id
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
 WHERE c.id = %s
"""
_INSERT_VERSION = """
INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description, edit_presets,
                           edit_note, warnings, served_model, prompt_version, api_request_id,
                           assistant_note)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_APPROVE = """
UPDATE campaigns SET status = 'COPY_APPROVED'
 WHERE id = %s AND row_version = %s AND status = 'COPY_PROPOSED' AND current_version_id = %s
RETURNING id
"""
_RESTORE_PREVIOUS = """
UPDATE campaigns c SET current_version_id = v.based_on_version_id
  FROM copy_versions v
 WHERE c.id = %s AND c.row_version = %s AND c.status = 'COPY_PROPOSED'
   AND c.current_version_id = %s AND v.id = c.current_version_id
   AND v.based_on_version_id IS NOT NULL
RETURNING c.id
"""
_RESTORE_NEWEST = """
UPDATE campaigns c SET current_version_id = n.id
  FROM (SELECT id FROM copy_versions WHERE campaign_id = %s ORDER BY version DESC LIMIT 1) n
 WHERE c.id = %s AND c.row_version = %s AND c.status = 'COPY_PROPOSED'
   AND c.current_version_id = %s AND c.current_version_id <> n.id
RETURNING c.id
"""
_UNAPPROVE = """
UPDATE campaigns SET status = 'COPY_PROPOSED'
 WHERE id = %s AND row_version = %s AND status = 'COPY_APPROVED'
RETURNING id
"""
_SET_BUDGET = """
UPDATE campaigns SET budget_sar = %s
 WHERE id = %s AND row_version = %s AND status = 'COPY_APPROVED'
RETURNING id
"""
_SET_DAYS = """
UPDATE campaigns SET days = %s
 WHERE id = %s AND row_version = %s AND status = 'COPY_APPROVED'
RETURNING id
"""
_CONFIRM = """
UPDATE campaigns SET status = 'READY'
 WHERE id = %s AND row_version = %s AND status = 'COPY_APPROVED'
   AND approved_version_id = %s AND budget_sar = %s AND days = %s
RETURNING id
"""
_CANCEL = """
UPDATE campaigns SET status = 'CANCELLED'
 WHERE id = %s AND row_version = %s AND status <> 'CANCELLED'
RETURNING id
"""
_EXISTS = "SELECT 1 FROM campaigns WHERE id = %s"


# ── العرض ───────────────────────────────────────────────────────────────
def _view(cursor, campaign_id: UUID) -> dict:
    cursor.execute(_VIEW, (campaign_id,))
    row = cursor.fetchone()
    if row is None:
        raise NotFound
    budget, days = row["budget_sar"], row["days"]
    daily = None
    if budget is not None and days is not None:
        amount, exact = daily_amount(budget, days)
        daily = {"amount": str(amount), "exact": exact}
    copy = None
    if row["current_version_id"] is not None:
        copy = {
            "version_id": str(row["current_version_id"]),
            "version": row["version"],
            "title": row["title"],
            "description": row["description"],
            "warnings": list(row["warnings"]),
            #: كلمة «سيمبول» للمستخدم عن هذه النسخة، أو None.
            "assistant_note": row["assistant_note"],
            "can_restore_previous": row["based_on_version_id"] is not None,
            "can_restore_newest": row["newest_version_id"] != row["current_version_id"],
        }
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "row_version": row["row_version"],
        "image": None if row["image_sha256"] is None else {
            "width": row["image_width"], "height": row["image_height"], "tag": row["image_sha256"][:16],
        },
        "copy": copy,
        "approved_version_id": None if row["approved_version_id"] is None else str(row["approved_version_id"]),
        "generating": row["generating"],
        "budget": None if budget is None else {
            "sar": budget, "short": budget_short(budget), "words": budget_in_words(budget)},
        "days": None if days is None else {"n": days, "short": days_short(days), "words": days_in_words(days)},
        "daily": daily,
        "versions_left": max(0, VERSIONS_PER_CAMPAIGN - row["versions_used"]),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "ready_at": None if row["ready_at"] is None else row["ready_at"].isoformat(),
    }


def get(db: Database, user_id: UUID, campaign_id: UUID) -> dict:
    with db.session(user_id) as cursor:
        return _view(cursor, campaign_id)


def list_page(db: Database, user_id: UUID, page: int) -> dict:
    """الأحدث أولاً، ثلاثٌ في الصفحة. الملغاة لا تُعرض: صورها حُذفت ولا عمل فيها."""
    with db.session(user_id) as cursor:
        cursor.execute(_LIST, (PAGE_SIZE + 1, (page - 1) * PAGE_SIZE))
        rows = cursor.fetchall()
    return {
        "items": [
            {"id": str(r["id"]), "status": r["status"], "title": r["title"],
             "updated_at": r["updated_at"].isoformat()}
            for r in rows[:PAGE_SIZE]
        ],
        "has_more": len(rows) > PAGE_SIZE and page < MAX_PAGE,
    }


def display_name(db: Database, user_id: UUID) -> str | None:
    """اسم صاحب الجلسة كما وضعه المشغّل، أو None. لا يُرسَل إلى النموذج أبداً."""
    with db.session(user_id) as cursor:
        cursor.execute("SELECT ew_my_display_name() AS name")
        return cursor.fetchone()["name"]


def remaining_generations(db: Database, user_id: UUID) -> int:
    with db.session(user_id) as cursor:
        cursor.execute(_REMAINING)
        return max(0, DAILY_GENERATIONS - cursor.fetchone()["used"])


def image_bytes(db: Database, user_id: UUID, campaign_id: UUID) -> bytes:
    with db.session(user_id) as cursor:
        cursor.execute(_IMAGE, (campaign_id,))
        row = cursor.fetchone()
    if row is None:
        raise NotFound
    return bytes(row["jpeg"])


# ── الصورة ──────────────────────────────────────────────────────────────
def create(db: Database, user_id: UUID, image: ProcessedImage) -> dict:
    """حملةٌ جديدة بصورتها، في معاملةٍ واحدة: لا حملة بلا صورة."""
    with db.session(user_id) as cursor:
        cursor.execute(_INSERT_CAMPAIGN, (user_id,))
        campaign_id = cursor.fetchone()["id"]
        cursor.execute(_INSERT_IMAGE, (campaign_id, user_id, image.jpeg, image.width, image.height, image.sha256))
        return _view(cursor, campaign_id)


def replace_image(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int,
                  image: ProcessedImage) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_LOCK_DRAFT, (campaign_id,))
        row = cursor.fetchone()
        if row is None:
            raise NotFound
        if row["row_version"] != expected_row_version or row["status"] != "DRAFT":
            raise Conflict
        cursor.execute(_REPLACE_IMAGE, (image.jpeg, image.width, image.height, image.sha256, campaign_id))
        return _view(cursor, campaign_id)


# ── النصّ ───────────────────────────────────────────────────────────────
def _begin(db: Database, user_id: UUID, campaign_id: UUID, kind: str, expected_row_version: int,
           expected_version: UUID | None) -> tuple[UUID, bytes, PreviousCopy | None]:
    with db.session(user_id) as cursor:
        try:
            cursor.execute(_BEGIN, (campaign_id, kind, expected_row_version, expected_version))
        except pg_errors.NoDataFound as exc:
            raise NotFound from exc
        attempt = cursor.fetchone()["attempt"]
        cursor.execute(_GENERATION_INPUT, (campaign_id,))
        row = cursor.fetchone()
    previous = None if row["title"] is None else PreviousCopy(row["title"], row["description"])
    return attempt, bytes(row["jpeg"]), previous


def _close(db: Database, user_id: UUID, attempt: UUID, outcome: str, tokens: tuple) -> None:
    with db.session(user_id) as cursor:
        cursor.execute(_FINISH, (attempt, outcome, *tokens))


def _finish(db: Database, user_id: UUID, campaign_id: UUID, attempt: UUID, outcome: CopyOutcome,
            presets: tuple[EditPreset, ...], note: str | None) -> dict | Unusable:
    tokens = (outcome.input_tokens, outcome.output_tokens)
    if outcome.outcome == "OK":
        try:
            with db.session(user_id) as cursor:
                cursor.execute(_INSERT_VERSION, (
                    campaign_id, user_id, attempt, outcome.title, outcome.description,
                    [p.value for p in presets], note, [w.value for w in outcome.warnings],
                    outcome.served_model, PROMPT_VERSION, outcome.request_id, outcome.note,
                ))
                cursor.execute(_FINISH, (attempt, "OK", *tokens))
                return _view(cursor, campaign_id)
        except Exception as exc:
            # النصّ لم يُكتب، والمحاولة تُغلق محسوبةً في كل حال — محاولةٌ تبقى
            # مفتوحة تمنع صاحبها من غيرها خمس دقائق.
            _close(db, user_id, attempt, "DISCARDED", tokens)
            if isinstance(exc, pg_errors.CheckViolation) and exc.diag.constraint_name in (
                "version_sequence", "version_needs_open_attempt",
            ):
                # تغيّرت الحملة أثناء الكتابة: أُلغيت، أو انقضى عقد المحاولة.
                raise Conflict("CHANGED_WHILE_WRITING") from exc
            raise

    with db.session(user_id) as cursor:
        cursor.execute(_FINISH, (attempt, outcome.outcome, *tokens))
        if outcome.outcome == "UNUSABLE_PHOTO":
            return Unusable(reason=outcome.reason or "NO_PRODUCT", view=_view(cursor, campaign_id),
                            note=outcome.note)
    raise AiFailure(outcome.outcome, outcome.retry_after_seconds)


def _write(db: Database, writer: Copywriter, user_id: UUID, attempt: UUID, request: CopyRequest) -> CopyOutcome:
    """الكاتب لا يرفع في مساره المعتاد؛ وإن رفع فالمحاولة تُغلق قبل أن ينتشر الخطأ."""
    try:
        return writer.write(request)
    except Exception:
        _close(db, user_id, attempt, "UPSTREAM_ERROR", (None, None))
        raise


class _Slot:
    """مقعدٌ من مقاعد التوليد المتزامن، يُحجز قبل فتح المحاولة فلا تُحسب محاولةٌ لم تبدأ."""

    def __enter__(self) -> None:
        if not _GENERATIONS.acquire(blocking=False):
            raise AiFailure("UPSTREAM_BUSY", 60)

    def __exit__(self, *exc) -> None:
        _GENERATIONS.release()


def generate(db: Database, writer: Copywriter, user_id: UUID, campaign_id: UUID,
             expected_row_version: int) -> dict | Unusable:
    """النسخة الأولى من صورة المسودة."""
    with _Slot():
        attempt, jpeg, _ = _begin(db, user_id, campaign_id, "INITIAL", expected_row_version, None)
        outcome = _write(db, writer, user_id, attempt, CopyRequest(jpeg=jpeg))
        return _finish(db, user_id, campaign_id, attempt, outcome, (), None)


def edit(db: Database, writer: Copywriter, user_id: UUID, campaign_id: UUID, expected_row_version: int,
         expected_version_id: UUID, presets: list[EditPreset], note: str | None) -> dict | Unusable:
    """نسخةٌ جديدة من النسخة التي يراها صاحبها، بالخيارات وملاحظته."""
    problem = check_edit_request(presets, note)
    if problem:
        raise Invalid(problem)
    with _Slot():
        attempt, jpeg, previous = _begin(
            db, user_id, campaign_id, "EDIT", expected_row_version, expected_version_id)
        request = CopyRequest(jpeg=jpeg, previous=previous, presets=tuple(presets), edit_note=note)
        outcome = _write(db, writer, user_id, attempt, request)
        try:
            result = _finish(db, user_id, campaign_id, attempt, outcome, tuple(presets), note)
        except AiFailure as failure:
            # رفض التعديل حكمٌ على الطلب لا على الصورة؛ والرفض لانشغال البديل يبقى كما هو.
            if failure.outcome == "REFUSED" and not failure.retry_after_seconds:
                raise AiFailure("EDIT_REFUSED", None) from failure
            raise
        if isinstance(result, Unusable):
            # الصورة قُبلت من قبل ولا تُستبدل بعد اقتراح النصّ: «اختر صورةً أخرى»
            # لا يمكن تنفيذه. المحاولة سُجّلت محسوبةً كما دُفعت.
            raise AiFailure("EDIT_REFUSED", None)
        return result


# ── القرار والمال ───────────────────────────────────────────────────────
def _guarded(db: Database, user_id: UUID, campaign_id: UUID, statement: str, params: tuple) -> dict:
    """عبارةٌ مشروطة بما رآه صاحبها: صفرُ صفوف ⇒ غير موجود، أو تغيّر منذ رآه."""
    with db.session(user_id) as cursor:
        cursor.execute(statement, params)
        if cursor.fetchone() is None:
            cursor.execute(_EXISTS, (campaign_id,))
            raise NotFound if cursor.fetchone() is None else Conflict
        return _view(cursor, campaign_id)


def approve(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int,
            version_id: UUID) -> dict:
    """يعتمد النسخة المعروضة نفسها. القاعدة تسجّلها هي، لا ما يرسله العميل."""
    return _guarded(db, user_id, campaign_id, _APPROVE, (campaign_id, expected_row_version, version_id))


def restore(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int,
            expected_version_id: UUID, target: str) -> dict:
    """
    يعرض النسخة التي بُني عليها التعديل الأخير (`previous`)، أو يعود إلى أحدث
    نسخة (`newest`) — بلا استدعاءٍ للنموذج، وكلٌّ منهما يُلغي الآخر.

    تراجعٌ عن طلب تعديلٍ جاء بنصٍّ أسوأ، وتراجعٌ عن التراجع: ضغطةٌ واحدة
    خاطئة بالنظر لا تُفقد نسخةً.
    """
    if target == "previous":
        return _guarded(db, user_id, campaign_id, _RESTORE_PREVIOUS,
                        (campaign_id, expected_row_version, expected_version_id))
    if target == "newest":
        return _guarded(db, user_id, campaign_id, _RESTORE_NEWEST,
                        (campaign_id, campaign_id, expected_row_version, expected_version_id))
    raise Invalid("RESTORE_TARGET")


def unapprove(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int) -> dict:
    return _guarded(db, user_id, campaign_id, _UNAPPROVE, (campaign_id, expected_row_version))


def set_budget(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int,
               budget_sar: int) -> dict:
    """قيمةٌ مطلقة لا فرق: الضغطة المكرّرة تضع القيمة نفسها مرتين."""
    if not is_valid_budget(budget_sar):
        raise Invalid("BUDGET_RANGE")
    return _guarded(db, user_id, campaign_id, _SET_BUDGET, (budget_sar, campaign_id, expected_row_version))


def set_days(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int, days: int) -> dict:
    if not is_valid_days(days):
        raise Invalid("DAYS_RANGE")
    return _guarded(db, user_id, campaign_id, _SET_DAYS, (days, campaign_id, expected_row_version))


def confirm(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int,
            version_id: UUID, budget_sar: int, days: int) -> dict:
    """
    التأكيد مشروطٌ بكل ما عُرض: النسخة والمبلغ والمدّة ورقم الصفّ. أيّ اختلاف
    ⇒ `Conflict`، فلا يُعتمد إلا ما رآه صاحبه لحظة الضغط.
    """
    return _guarded(db, user_id, campaign_id, _CONFIRM,
                    (campaign_id, expected_row_version, version_id, budget_sar, days))


def cancel(db: Database, user_id: UUID, campaign_id: UUID, expected_row_version: int) -> dict:
    return _guarded(db, user_id, campaign_id, _CANCEL, (campaign_id, expected_row_version))
