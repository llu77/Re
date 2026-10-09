"""
المراجِع في الخلفية
===================
يعمل عند ضغطة الاعتماد وحدها، ونتيجته لا تظهر إلا بعد ضغطة: لا شيء يُدفع إلى
شاشةٍ يستقرّ عليها نظرٌ (المواصفة §3.1). الضغطة تحفظ المسودة، وتجري الفحص
الحتمي، وتفتح صفّ الدفتر، ثم تنتظر `REVIEW_WAIT_SECONDS` على الأكثر داخل الطلب
نفسه، وتجيب DONE أو PENDING أو UNAVAILABLE. ما تأخّر يُكتب على بصمة المحتوى
ويُلتقى عند ضغطة «سجّل» عبر بوّابة القاعدة (`ew_ai_gate`).

**الذكاء لا يحجز العمل.** مراجعةٌ بطيئة أو فاشلة أو مرفوضة أو مسقوفة تدع
الموظف يعتمد؛ وما يحجز الاعتماد تنبيهٌ لم يُبتّ فيه وحده، والبتّ ضغطةٌ واحدة.

**السجلّ (`FEATURES`) تملؤه مساحات العمل**: كل مساحةٍ تسجّل قائمة فحوصها،
ودوالّ البدء والتسجيل والبصمة في القاعدة (دوالّ `SECURITY DEFINER` تكتبها هي)،
ومحمّلاً يبني الموضوع بأقلّ ما يلزم بهوية الجلسة. هذه الوحدة لا تعرف شكل
فاتورةٍ ولا ردّ.

**الاسم من الخادم.** النموذج يكتب الخبر بلا نداء؛ والعنوان «يا فلان، …»
يُركَّب هنا عند الردّ من `ew_my_display_name()` ولا يُخزَّن ولا يُرسَل.

كل سجلٍّ عبر `ai_log` بلا نصّ.
"""

from __future__ import annotations

import concurrent.futures as futures
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import UUID

from psycopg import errors as pg_errors

from eyework import ai_log, ai_text
from eyework.ai_limits import AI_SLOTS, MAX_FLAGS, REASON_LENGTH, REVIEW_WAIT_SECONDS, SUGGESTION_LENGTH
from eyework.db import Database
from eyework.model_gateway import Guard
from eyework.professions import Profession
from eyework.prompt_kit import Gateway, ModelCall, ModelReply
from eyework.reviewer_prompt import Catalogue, call as build_call
from eyework.service_errors import Conflict, NotFound

__all__ = [
    "FEATURES",
    "FLAGS_UNDECIDED",
    "MESSAGES",
    "ReviewFeature",
    "ReviewRunner",
    "Snapshot",
    "decide",
    "flags_undecided",
    "headline",
    "parse_flags",
    "review",
    "undecided_flags",
    "usage",
]

#: عازلا الاتجاه (FSI … PDI): اسمٌ لاتيني يبقى في جهته من «،».
ISOLATE = ("⁨", "⁩")

#: سطر الحالة الذي تعرضه خطوة التأكيد في مكانٍ ثابت (المواصفة §3.11).
MESSAGES: dict[str, str] = {
    "DOWN": "سيمبول غير متاح الآن. يمكنك المتابعة دون مراجعته.",
    "BUSY": "سيمبول يراجع عملاً آخر الآن. يمكنك المتابعة دون مراجعته.",
    "RATE": "راجع سيمبول أعمالاً كثيرة في وقتٍ قصير. يمكنك المتابعة دون مراجعته.",
    "DAILY": "انتهت مراجعات سيمبول لليوم. يمكنك المتابعة دونها.",
    "APP": "سيمبول مشغولٌ اليوم. يمكنك المتابعة دون مراجعته.",
    "FAILED": "لم تكتمل مراجعة سيمبول لهذا العمل. يمكنك المتابعة.",
    "PENDING": "لم تكتمل مراجعة سيمبول بعد. يمكنك المتابعة.",
}
FLAG_STALE = "تغيّر العمل بعد هذه الملاحظة. راجعه من جديد."
FLAG_CLOSED = "اعتُمد العمل، ولم يعد لهذه الملاحظة قرار."
FLAGS_UNDECIDED = "وصلت ملاحظةٌ من سيمبول بعد مراجعته. القرار لك."
NO_REVIEW = "لا مراجعة لهذا النوع من العمل."
NO_FLAG = "الملاحظة غير موجودة."

#: قيود السقوف في `ew_ai_request_open` ← سبب «غير متاح». ما سواها خطأٌ يُرفع.
_CAP_REASONS = {
    "ai_rate": "RATE",
    "ai_daily_cap": "DAILY",
    "ai_new_account_daily_cap": "DAILY",
    "ai_feature_app_cap": "APP",
    "generation_global_cap": "APP",
    "generation_new_accounts_cap": "APP",
}
#: نتيجة المزوّد ← سبب «غير متاح»: الانقطاع DOWN، والرفض والجواب غير الصالح FAILED.
_FAILURE_REASONS = {
    "UPSTREAM_BUSY": "DOWN", "UPSTREAM_UNREACHABLE": "DOWN", "UPSTREAM_TIMEOUT": "DOWN", "UPSTREAM_ERROR": "DOWN",
    "REFUSED": "FAILED", "OUTPUT_INVALID": "FAILED",
}


@dataclass(frozen=True, slots=True)
class Snapshot:
    """الموضوع كما يراه النموذج، وبصمة محتواه كما تحسبها القاعدة."""

    payload: Mapping
    digest: bytes


@dataclass(frozen=True, slots=True)
class ReviewFeature:
    """ما تسجّله مساحة العمل لأداة مراجعةٍ واحدة (المواصفة §8.3)."""

    code: str
    kinds: frozenset[str]
    profession: Profession
    catalogue: Catalogue
    #: SQL ثابت: البدء `SELECT request_id, digest FROM …(%s)`، والتسجيل
    #: `SELECT …(%s, %s, %s) AS outcome`، والبصمة الحالية `SELECT …(%s) AS digest`.
    begin_sql: str
    record_sql: str
    digest_sql: str
    #: (المؤشّر، صاحب الجلسة، النوع، المعرّف، رقم الصفّ المتوقَّع) ← الموضوع بعد الفحص
    #: الحتمي، في معاملة البدء نفسها. يرفع NotFound أو Conflict أو Invalid(field).
    load: Callable[[Any, UUID, str, UUID, int | None], Snapshot]
    #: مفاتيح الموضوع المعلَنة: اختبارٌ يقارنها بقائمة المنع (لا اسم ولا بريد ولا معرّف).
    payload_keys: frozenset[str]


#: يملؤه كل مسار عمل عند استيراده؛ فارغٌ قبل الحزمة الثالثة.
FEATURES: dict[str, ReviewFeature] = {}

# ── العبارات ────────────────────────────────────────────────────────────
_STORED_REVIEW = """
SELECT 1 FROM ai_requests
 WHERE feature = %s AND subject_kind = %s AND subject_id = %s AND content_digest = %s AND outcome = 'OK'
 LIMIT 1
"""
_FLAG_COLUMNS = """
SELECT f.id, f.check_code, f.severity, f.field, f.line_no, f.reason, f.suggestion, f.evidence, f.content_digest,
       (SELECT d.choice FROM ai_flag_decisions d WHERE d.flag_id = f.id ORDER BY d.id DESC LIMIT 1) AS decision
  FROM ai_flags f
"""
_FLAGS_FOR_DIGEST = _FLAG_COLUMNS + """
 WHERE f.subject_kind = %s AND f.subject_id = %s AND f.content_digest = %s
   AND f.closed_at IS NULL AND f.erased_at IS NULL
 ORDER BY f.position, f.id
"""
_FLAGS_FOR_REQUEST = _FLAG_COLUMNS + " WHERE f.request_id = %s ORDER BY f.position, f.id"
_IN_FLIGHT = """
SELECT subject_kind, subject_id, content_digest FROM ai_requests
 WHERE feature = %s AND finished_at IS NULL
 ORDER BY started_at DESC LIMIT 1
"""
_FAIL = "SELECT ew_ai_request_fail(%s, %s, %s)"
_DECIDE = "SELECT choice, decided_at FROM ew_ai_decide(%s, %s)"
_FLAG = "SELECT id, feature, subject_kind, subject_id, content_digest, closed_at FROM ai_flags WHERE id = %s"
_DISPLAY_NAME = "SELECT ew_my_display_name() AS name"
_USAGE = "SELECT per_day, used_today FROM ew_ai_my_usage() WHERE feature = %s"


class _Capped(Exception):
    """قيدٌ من `ew_ai_request_open`؛ يُرفع من داخل المعاملة فتُلغى، ويُقرأ بعدها."""

    def __init__(self, constraint: str, error: Exception) -> None:
        super().__init__(constraint)
        self.constraint = constraint
        self.error = error


@dataclass(frozen=True, slots=True)
class _Result:
    status: str
    reason: str | None
    flags: list[dict]


# ── ما يُعرض ────────────────────────────────────────────────────────────
def headline(display_name: str | None, reason: str) -> str:
    """«يا ⁨فلان⁩، الخبر» — الاسم من قاعدتنا عند الردّ، لا من النموذج ولا من التخزين."""
    name = (display_name or "").strip()
    return f"يا {ISOLATE[0]}{name}{ISOLATE[1]}، {reason}" if name else reason


def _flag_view(row: Mapping, display_name: str | None) -> dict:
    return {
        "id": str(row["id"]),
        "check": row["check_code"],
        "severity": row["severity"],
        "field": row["field"],
        "line": row["line_no"],
        "headline": headline(display_name, row["reason"] or ""),
        "suggestion": row["suggestion"],
        "evidence": list(row["evidence"] or []),
        "decision": row["decision"],
    }


def _rows(cursor, statement: str, params: tuple) -> list[dict]:
    cursor.execute(statement, params)
    return [dict(row) for row in cursor.fetchall()]


def usage(cursor, feature: str) -> dict:
    """حدّ اليوم وما استُعمل منه لأداةٍ من أدوات مهنة صاحب الجلسة."""
    cursor.execute(_USAGE, (feature,))
    row = cursor.fetchone()
    return {"per_day": None, "used_today": None} if row is None else {
        "per_day": row["per_day"], "used_today": row["used_today"]}


# ── قراءة جواب النموذج ─────────────────────────────────────────────────
def _one_flag(item: object, catalogue: Catalogue, kind: str, lines: frozenset[int], payload: Mapping) -> dict | str:
    """ملاحظةٌ واحدة بعد كل فحوص §3.5، أو رمز إسقاطها. كل ملاحظةٍ تسقط وحدها."""
    if not isinstance(item, dict) or set(item) != {"check", "severity", "field", "line", "reason", "suggestion"}:
        return "SHAPE"
    check = catalogue.check(item["check"]) if isinstance(item["check"], str) else None
    if check is None or kind not in check.applies_to:
        return "CHECK"
    if item["severity"] not in ("HIGH", "MEDIUM"):
        return "SEVERITY"
    if item["field"] not in check.fields:
        return "FIELD"
    line = item["line"]
    if check.line_level:
        if isinstance(line, bool) or not isinstance(line, int) or line not in lines:
            return "LINE"
    elif line is not None:
        return "LINE"
    if not isinstance(item["reason"], str) or not isinstance(item["suggestion"], str):
        return "SHAPE"
    reason, codes = ai_text.check(item["reason"], *REASON_LENGTH)
    if codes:
        return f"REASON_{codes[0]}"
    suggestion = None
    if item["suggestion"].strip():
        suggestion, codes = ai_text.check(item["suggestion"], *SUGGESTION_LENGTH)
        if codes:
            return f"SUGGESTION_{codes[0]}"
    evidence = [str(line_text) for line_text in tuple(check.evidence(payload, line))[:3]]
    return {"check": check.code, "severity": item["severity"], "field": item["field"], "line": line,
            "reason": reason, "suggestion": suggestion, "evidence": evidence}


def parse_flags(reply: object, catalogue: Catalogue, kind: str, payload: Mapping) -> tuple[list[dict], list[str]]:
    """
    (الملاحظات المقبولة بشكل `ew_ai_flags_put`، ورموز ما أُسقط). ثلاثٌ على الأكثر،
    HIGH أولاً ثم ترتيب النموذج. الشواهد يبنيها الخادم من الأرقام التي أرسلها، لا
    النموذج.
    """
    raw = reply.get("flags") if isinstance(reply, dict) else None
    if not isinstance(raw, list):
        return [], ["SHAPE"]
    lines = frozenset(catalogue.line_numbers(payload))
    kept: list[dict] = []
    dropped: list[str] = []
    for item in raw:
        result = _one_flag(item, catalogue, kind, lines, payload)
        if isinstance(result, str):
            dropped.append(result)
        else:
            kept.append(result)
    kept.sort(key=lambda flag: 0 if flag["severity"] == "HIGH" else 1)
    if len(kept) > MAX_FLAGS:
        dropped.extend(["EXCESS"] * (len(kept) - MAX_FLAGS))
        kept = kept[:MAX_FLAGS]
    return kept, dropped


# ── الحوض والانتظار ────────────────────────────────────────────────────
class ReviewRunner:
    """
    يملك حوض الخيوط الذي تكمل فيه المراجعة بعد أن يجيب الطلب، والحارس (القاطع
    والمقاعد)، والبوّابة. يُنشأ مع التطبيق، ويبدأ حوضه في `lifespan` ويُغلق معه
    بإلغاء ما لم يبدأ؛ ما بقي مفتوحاً يُغلق ABANDONED في `purge`.
    """

    def __init__(self, gateway: Gateway, guard: Guard | None = None, *,
                 wait_seconds: float = REVIEW_WAIT_SECONDS, workers: int = AI_SLOTS) -> None:
        self.gateway = gateway
        self.guard = guard or Guard()
        self.wait_seconds = wait_seconds
        self._workers = workers
        self._pool: futures.ThreadPoolExecutor | None = None

    def start(self) -> None:
        self._pool = futures.ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="ai-review")

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def submit(self, job: Callable[[], Any]) -> futures.Future:
        if self._pool is None:
            raise RuntimeError("حوض المراجعة لم يبدأ")
        return self._pool.submit(job)

    def wait(self, future: futures.Future) -> Any:
        """نتيجة المهمّة إن انتهت في المهلة، وإلا None وتكمل في الخلفية."""
        try:
            return future.result(timeout=self.wait_seconds)
        except futures.TimeoutError:
            return None

    def call(self, request: ModelCall) -> ModelReply:
        """استدعاءٌ واحد يُسجَّل في القاطع."""
        reply = self.gateway.call(request)
        self.guard.record(reply)
        return reply


# ── المراجعة ────────────────────────────────────────────────────────────
def _fail(db: Database, user_id: UUID, request_id: UUID, outcome: str, usage_json: dict | None) -> None:
    with db.session(user_id) as cursor:
        cursor.execute(_FAIL, (request_id, outcome, None if usage_json is None else json.dumps(usage_json)))


def _job(db: Database, runner: ReviewRunner, user_id: UUID, feature: ReviewFeature, kind: str,
         request_id: UUID, snapshot: Snapshot) -> Callable[[], _Result]:
    """المهمّة في الخلفية بهوية الطلب الموثَّق؛ لا معرّف من النموذج ولا من الموضوع."""

    def run() -> _Result:
        try:
            reply = runner.call(build_call(feature.catalogue, kind, snapshot.payload))
            if reply.outcome != "OK":
                _fail(db, user_id, request_id, reply.outcome, reply.usage)
                return _Result("UNAVAILABLE", _FAILURE_REASONS[reply.outcome], [])
            flags, dropped = parse_flags(reply.data, feature.catalogue, kind, snapshot.payload)
            ai_log.event("review_parsed", feature=feature.code, request_id=str(request_id), flags_kept=len(flags),
                         flags_dropped=len(dropped), drop_codes=",".join(dropped) or None)
            with db.session(user_id) as cursor:
                cursor.execute(feature.record_sql, (request_id, json.dumps(flags, ensure_ascii=False),
                                                    json.dumps(reply.usage)))
                outcome = cursor.fetchone()["outcome"]
                rows = _rows(cursor, _FLAGS_FOR_REQUEST, (request_id,)) if outcome == "OK" else []
            ai_log.event("review_recorded", feature=feature.code, request_id=str(request_id), outcome=outcome)
            return _Result("DONE", None, rows) if outcome == "OK" else _Result("UNAVAILABLE", "FAILED", [])
        except Exception as error:
            # الصفّ المفتوح يحجز صاحبه عن المراجعة ما بقي عقده؛ يُغلق محسوباً.
            ai_log.event("review_failed", level="error", feature=feature.code, request_id=str(request_id),
                         outcome=type(error).__name__)
            try:
                _fail(db, user_id, request_id, "UPSTREAM_ERROR", None)
            except Exception:
                ai_log.event("review_fail_unrecorded", level="error", feature=feature.code,
                             request_id=str(request_id))
            raise
        finally:
            runner.guard.release()

    return run


def _begin(cursor, feature: ReviewFeature, subject_id: UUID) -> tuple[UUID, bytes]:
    """دالّة البدء في القاعدة: صفٌّ في الدفتر وبصمةٌ، أو قيدٌ يُرفع `_Capped`."""
    try:
        cursor.execute(feature.begin_sql, (subject_id,))
    except pg_errors.NoDataFound as error:
        raise NotFound("NOT_FOUND", NO_REVIEW) from error
    except (pg_errors.IntegrityError, pg_errors.InsufficientPrivilege) as error:
        constraint = getattr(error.diag, "constraint_name", None) or ""
        if constraint in _CAP_REASONS or constraint in ("ai_request_in_progress", "ai_review_current"):
            raise _Capped(constraint, error) from error
        raise
    row = cursor.fetchone()
    return row["request_id"], bytes(row["digest"])


def _after_cap(db: Database, user_id: UUID, feature: ReviewFeature, kind: str, subject_id: UUID,
               digest: bytes, capped: _Capped) -> _Result:
    """ما يُقال بعد قيدٍ من القاعدة. مراجعةٌ جارية للموضوع نفسه PENDING، ولغيره BUSY."""
    if capped.constraint == "ai_review_current":
        with db.session(user_id) as cursor:
            return _Result("DONE", None, _rows(cursor, _FLAGS_FOR_DIGEST, (kind, subject_id, digest)))
    if capped.constraint == "ai_request_in_progress":
        with db.session(user_id) as cursor:
            cursor.execute(_IN_FLIGHT, (feature.code,))
            row = cursor.fetchone()
        same = (row is not None and row["subject_kind"] == kind and row["subject_id"] == subject_id
                and bytes(row["content_digest"] or b"") == digest)
        return _Result("PENDING", None, []) if same else _Result("UNAVAILABLE", "BUSY", [])
    return _Result("UNAVAILABLE", _CAP_REASONS[capped.constraint], [])


def _response(db: Database, user_id: UUID, feature: ReviewFeature, kind: str, subject_id: UUID,
              digest: bytes, result: _Result) -> dict:
    with db.session(user_id) as cursor:
        cursor.execute(_DISPLAY_NAME)
        name = cursor.fetchone()["name"]
        allowance = usage(cursor, feature.code)
    reason = result.reason
    message = MESSAGES.get("PENDING" if result.status == "PENDING" else (reason or ""))
    return {
        "subject": {"kind": kind, "id": str(subject_id), "digest": digest.hex()},
        "review": {"status": result.status, "reason": reason, "message": message},
        "flags": [_flag_view(row, name) for row in result.flags],
        "usage": allowance,
    }


def review(db: Database, runner: ReviewRunner, user_id: UUID, feature_code: str, kind: str, subject_id: UUID,
           expected_row_version: int | None) -> dict:
    """
    ضغطة «راجع» كاملةً (المواصفة §3.2): في معاملةٍ واحدة يحمّل مسار العمل موضوعه
    ويفحصه حتمياً، فإن رُوجع المحتوى نفسه من قبل عادت ملاحظاته بلا استدعاء؛ وإلا
    حُجز مقعدٌ (أو عاد «غير متاح» من غير أن يُفتح شيء) وفُتح صفّ الدفتر. بعد
    الإيداع تُرسل المهمّة إلى الحوض ويُنتظر حتى `wait_seconds`.
    """
    feature = FEATURES.get(feature_code)
    if feature is None or kind not in feature.kinds:
        raise NotFound("NOT_FOUND", NO_REVIEW)
    reason = runner.guard.acquire()
    slot_held = reason is None
    handed_over = False
    try:
        result: _Result | None = None
        try:
            with db.session(user_id) as cursor:
                snapshot = feature.load(cursor, user_id, kind, subject_id, expected_row_version)
                digest = snapshot.digest
                cursor.execute(_STORED_REVIEW, (feature.code, kind, subject_id, digest))
                if cursor.fetchone() is not None:
                    result = _Result("DONE", None, _rows(cursor, _FLAGS_FOR_DIGEST, (kind, subject_id, digest)))
                elif not slot_held:
                    ai_log.event("review_unavailable", feature=feature.code, reason=reason)
                    result = _Result("UNAVAILABLE", reason, [])
                else:
                    request_id, digest = _begin(cursor, feature, subject_id)
        except _Capped as capped:
            ai_log.event("review_capped", feature=feature.code, constraint=capped.constraint)
            result = _after_cap(db, user_id, feature, kind, subject_id, snapshot.digest, capped)
        if result is None:
            # الصفّ مودَع؛ المهمّة تملك المقعد من هنا وتُعيده في نهايتها.
            job = _job(db, runner, user_id, feature, kind, request_id, Snapshot(snapshot.payload, digest))
            try:
                future = runner.submit(job)
            except RuntimeError:
                _fail(db, user_id, request_id, "UPSTREAM_ERROR", None)
                result = _Result("UNAVAILABLE", "DOWN", [])
            else:
                handed_over = True
                try:
                    result = runner.wait(future)
                except Exception:
                    result = _Result("UNAVAILABLE", "FAILED", [])
                if result is None:
                    result = _Result("PENDING", None, [])
        return _response(db, user_id, feature, kind, subject_id, digest, result)
    finally:
        if slot_held and not handed_over:
            runner.guard.release()


# ── القرارات والبوّابة ─────────────────────────────────────────────────
def decide(db: Database, user_id: UUID, flag_id: UUID, action: str, digest: str | None) -> dict:
    """
    «عدّل» أو «تابع رغم ذلك» أو «تراجع» على ملاحظة صاحب الجلسة. بصمةٌ أرسلها
    العميل تُقارن ببصمة الملاحظة، وبصمة الموضوع الآن تُقارن بها عبر دالّة مسار
    العمل: اختلافٌ ⇒ FLAG_STALE؛ وملاحظةٌ أُغلقت بالاعتماد ⇒ FLAG_CLOSED.
    """
    with db.session(user_id) as cursor:
        cursor.execute(_FLAG, (flag_id,))
        row = cursor.fetchone()
        if row is None:
            raise NotFound("NOT_FOUND", NO_FLAG)
        if row["closed_at"] is not None:
            raise Conflict("FLAG_CLOSED", FLAG_CLOSED)
        stored = bytes(row["content_digest"])
        if digest is not None and bytes.fromhex(digest) != stored:
            raise Conflict("FLAG_STALE", FLAG_STALE)
        feature = FEATURES.get(row["feature"])
        if feature is not None:
            cursor.execute(feature.digest_sql, (row["subject_id"],))
            current = cursor.fetchone()["digest"]
            if current is None or bytes(current) != stored:
                raise Conflict("FLAG_STALE", FLAG_STALE)
        cursor.execute(_DECIDE, (flag_id, action))
        decided = cursor.fetchone()
    ai_log.event("flag_decided", outcome=action)
    return {"flag_id": str(flag_id), "decision": decided["choice"], "decided_at": decided["decided_at"].isoformat()}


def undecided_flags(db: Database, user_id: UUID, kind: str, subject_id: UUID, digest: bytes) -> list[dict]:
    """ملاحظات البصمة الحالية التي آخر قرارٍ فيها غير «تابع رغم ذلك»، بشكل جواب المراجعة."""
    with db.session(user_id) as cursor:
        cursor.execute(_DISPLAY_NAME)
        name = cursor.fetchone()["name"]
        rows = _rows(cursor, _FLAGS_FOR_DIGEST, (kind, subject_id, digest))
    return [_flag_view(row, name) for row in rows if row["decision"] != "PROCEED"]


def flags_undecided(db: Database, user_id: UUID, kind: str, subject_id: UUID, digest: bytes) -> Conflict:
    """
    ما ترفعه خدمة مسار العمل حين تردّ دالّة اعتمادها بقيد `ai_flags_undecided`:
    409 FLAGS_UNDECIDED ومعه الملاحظات، فتفتح الواجهة «قبل المتابعة».
    """
    return Conflict("FLAGS_UNDECIDED", FLAGS_UNDECIDED,
                    {"flags": undecided_flags(db, user_id, kind, subject_id, digest)})
