"""
«اسأل سيمبول»: المساعد في الزرّ العائم
=====================================
يجيب عن سؤالٍ واحد عن عمل الموظف من مصدرين لا غير: مهامّ مهنته ومهاراتها
المترجمة من مصادرها، وبيانات الشاشة التي يسأل منها. لا أدوات فلا يفعل شيئاً؛
ويقول إنه لا يعرف حين لا يعرف.

**العميل يرسل نوع الشاشة ومعرّفها لا بياناتها.** سجلّ الشاشات (`SCREENS`)
يحمّل البيانات بهوية الجلسة وتحت العزل، بنودٌ كاملة حتى ثلاثة آلاف حرف ثم
سطر عدد؛ وكل سطرٍ يمرّ بالإخفاء (`redact`) قبل الإرسال. شاشةٌ من غير مهنة
الموظف 404.

**لا يُخزَّن سؤالٌ ولا جواب.** الدفتر يعرف أن سؤالاً سُئل ومتى وبكم
(`ew_assistant_begin`/`ew_assistant_finish`)، وطلبٌ واحد في الطيران لكل
مستخدم تفرضه القاعدة. وما يُرسَل إلى الموظف في «سؤالك: …» هو ما غادر فعلاً،
بأقنعته.

الحزمة الأولى تسجّل شاشتين على بيانات الحملات: الرئيسية والحملة؛ وكل مساحة
عملٍ تضيف شاشاتها.
"""

from __future__ import annotations

import json
from uuid import UUID

from eyework import ai_log
from eyework.ai_limits import QUESTION_LENGTH, SCREEN_DATA_CHARS
from eyework.assistant_prompt import Parsed, ScreenContext, call as build_call, check_question, parse
from eyework.db import Database
from eyework.model_gateway import Guard
from eyework.professions import PORTALS, Profession
from eyework.prompt_kit import Gateway
from eyework.redact import redact
from eyework.reviewer import usage
from eyework.service_errors import Invalid, NotFound

__all__ = ["SCREENS", "AssistantError", "ScreenContext", "ask", "choices", "fit", "register"]

NO_SCREEN = "لا شاشة بهذا الاسم في بوابتك."
#: لا بيانات عملٍ في الرئيسية لمهنةٍ لم تصل أدواتها بعد (الحزمتان 3 و4).
NO_TOOLS_YET = "لا أدوات عملٍ في هذه الشاشة بعد."

_PROFESSION = "SELECT ew_my_profession() AS profession"
_BEGIN = "SELECT ew_assistant_begin() AS request"
_FINISH = "SELECT ew_assistant_finish(%s, %s, %s)"
_FAIL = "SELECT ew_ai_request_fail(%s, %s, %s)"
#: الحملات بحالاتها، والأحدث خمساً بعناوينها: بيانات صاحب الجلسة وحده تحت العزل.
_CAMPAIGN_COUNTS = "SELECT status, count(*) AS n FROM campaigns WHERE status <> 'CANCELLED' GROUP BY status"
_RECENT_CAMPAIGNS = """
SELECT c.status, v.title, c.updated_at::date AS updated
  FROM campaigns c
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
 WHERE c.status <> 'CANCELLED'
 ORDER BY c.updated_at DESC, c.id
 LIMIT 5
"""
#: الحملة الواحدة: الحالة والنصّ والمال والمدّة. لا معرّف ولا صورة ولا تاريخ ميلاد.
_CAMPAIGN = """
SELECT c.status, c.budget_sar, c.days, v.title, v.description, v.warnings,
       (SELECT count(*) FROM copy_versions cv WHERE cv.campaign_id = c.id) AS versions_used
  FROM campaigns c
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
 WHERE c.id = %s
"""

STATUS_NAMES = {
    "DRAFT": "مسودة", "COPY_PROPOSED": "نصٌّ مقترح", "COPY_APPROVED": "نصٌّ معتمد",
    "READY": "جاهزة", "CANCELLED": "ملغاة",
}
WARNING_NAMES = {"PRICE": "سعر أو خصم", "HEALTH_CLAIM": "ادّعاءٌ صحي", "SUPERLATIVE": "مبالغة"}


class AssistantError(Exception):
    """تعذّر الجواب هذه المرة. `code` من جدول `web/errors.AI_ASSISTANT`."""

    def __init__(self, code: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


#: نتيجة المزوّد ← رمز الخطأ.
_ERROR_FOR = {
    "REFUSED": "AI_REFUSED", "OUTPUT_INVALID": "AI_INVALID",
    "UPSTREAM_BUSY": "AI_UNAVAILABLE", "UPSTREAM_UNREACHABLE": "AI_UNAVAILABLE",
    "UPSTREAM_TIMEOUT": "AI_UNAVAILABLE", "UPSTREAM_ERROR": "AI_UNAVAILABLE",
}


def fit(items: list[str], *, budget: int = SCREEN_DATA_CHARS) -> tuple[str, ...]:
    """بنودٌ كاملة بترتيبها حتى الميزانية، ثم سطر عددٍ لما بقي؛ لا بند يُقصّ في منتصفه."""
    kept: list[str] = []
    used = 0
    for index, item in enumerate(items):
        if used + len(item) > budget:
            kept.append(f"و{len(items) - index} بنداً آخر")
            break
        kept.append(item)
        used += len(item)
    return tuple(kept)


# ── الشاشتان المسجَّلتان في الحزمة الأولى ────────────────────────────────
def _home(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_PROFESSION)
    if cursor.fetchone()["profession"] != Profession.MARKETING.value:
        return (NO_TOOLS_YET,)
    cursor.execute(_CAMPAIGN_COUNTS)
    counts = {row["status"]: row["n"] for row in cursor.fetchall()}
    if not counts:
        return ("لا حملات بعد.",)
    summary = "حملاتك: " + "، ".join(f"{n} {STATUS_NAMES.get(status, status)}" for status, n in sorted(counts.items()))
    cursor.execute(_RECENT_CAMPAIGNS)
    recent = [f"حملة «{row['title'] or 'بلا نصّ بعد'}» — {STATUS_NAMES.get(row['status'], row['status'])}"
              f" (آخر تعديل {row['updated'].isoformat()})" for row in cursor.fetchall()]
    return fit([summary, *recent])


def _campaign(cursor, user_id: UUID, screen_id: UUID | None) -> tuple[str, ...]:
    cursor.execute(_CAMPAIGN, (screen_id,))
    row = cursor.fetchone()
    if row is None:
        raise NotFound
    lines = [f"الحالة: {STATUS_NAMES.get(row['status'], row['status'])}"]
    if row["title"]:
        lines.append(f"العنوان: {row['title']}")
        lines.append(f"الوصف: {row['description']}")
        warnings = [WARNING_NAMES.get(w, w) for w in (row["warnings"] or [])]
        if warnings:
            lines.append("تنبيهات على النصّ: " + "، ".join(warnings))
    if row["budget_sar"] is not None:
        lines.append(f"الميزانية: {row['budget_sar']} ريال")
    if row["days"] is not None:
        lines.append(f"المدّة: {row['days']} يوم")
    lines.append(f"نسخ النصّ المكتوبة: {row['versions_used']} من 10")
    return fit(lines)


#: أزرار الشاشات كما تُعرض اليوم في العميل الثابت؛ العميل الجديد يحدّثها مع شاشاته.
HOME = ScreenContext(
    kind="HOME", profession=None, title="الرئيسية",
    labels=("حسابي",),
    extra_labels={Profession.MARKETING: ("حملة جديدة", "حملاتي")},
    ready_questions=("من أين أبدأ عملي اليوم؟", "ما أهمّ مهامّ مهنتي؟"),
    needs_id=False, load=_home,
)
CAMPAIGN = ScreenContext(
    kind="CAMPAIGN", profession=Profession.MARKETING, title="الحملة",
    labels=("اكتب لي العنوان والوصف", "اطلب نسخة جديدة", "النسخة السابقة", "متابعة للتأكيد",
            "نعم، اعتمد الحملة", "نعم، ألغِ الحملة"),
    ready_questions=("ماذا أتحقّق منه قبل اعتماد الحملة؟", "كيف أطلب نسخةً أخرى من النصّ؟"),
    needs_id=True, load=_campaign,
)

SCREENS: dict[str, ScreenContext] = {}


def register(screen: ScreenContext) -> None:
    SCREENS[screen.kind] = screen


register(HOME)
register(CAMPAIGN)


def choices() -> dict:
    """ما تعرضه الواجهة: حدّ السؤال والأسئلة الجاهزة لكل شاشة (لـ/api/choices)."""
    return {"question_max": QUESTION_LENGTH[1],
            "ready": {kind: list(screen.ready_questions) for kind, screen in SCREENS.items()}}


def _fail(db: Database, user_id: UUID, request_id: UUID, outcome: str, usage_json: dict | None) -> None:
    with db.session(user_id) as cursor:
        cursor.execute(_FAIL, (request_id, outcome, None if usage_json is None else json.dumps(usage_json)))


def ask(db: Database, gateway: Gateway, guard: Guard, user_id: UUID, screen_kind: str, screen_id: UUID | None,
        question: str | None, ready: int | None) -> dict:
    """
    سؤالٌ واحد: الشاشة من السجلّ بمهنة الجلسة، والسؤال بعد فحصه وإخفائه (أو
    سؤالٌ جاهز بفهرسه)، ثم الحارس، ثم صفّ الدفتر، ثم النموذج، ثم الفحص، ثم
    الإغلاق. ما يفشل يُغلق محسوباً ويرفع `AssistantError` برمزه.
    """
    screen = SCREENS.get(screen_kind)
    if screen is None:
        raise NotFound("SCREEN", NO_SCREEN)
    if screen.needs_id and screen_id is None:
        raise Invalid("SCREEN_ID", field="screen")
    if ready is not None:
        if not 0 <= ready < len(screen.ready_questions):
            raise Invalid("READY", field="ready_question")
        sent, masks = screen.ready_questions[ready], 0
    else:
        sent, masks = redact(check_question(question or ""))

    reason = guard.acquire()
    if reason is not None:
        ai_log.event("assistant_unavailable", reason=reason)
        raise AssistantError("AI_UNAVAILABLE" if reason == "DOWN" else "AI_BUSY", 30)
    try:
        with db.session(user_id) as cursor:
            cursor.execute(_PROFESSION)
            value = cursor.fetchone()["profession"]
            profession = Profession(value) if value is not None else None
            if profession is None or not screen.serves(profession):
                raise NotFound("SCREEN", NO_SCREEN)
            lines = tuple(redact(line)[0] for line in screen.load(cursor, user_id, screen_id))
            cursor.execute(_BEGIN)
            request_id = cursor.fetchone()["request"]
        portal = PORTALS[profession]
        try:
            reply = gateway.call(build_call(portal, screen, profession, lines, sent))
        except Exception:
            _fail(db, user_id, request_id, "UPSTREAM_ERROR", None)
            raise
        guard.record(reply)
    finally:
        guard.release()

    if reply.outcome != "OK":
        _fail(db, user_id, request_id, reply.outcome, reply.usage)
        raise AssistantError(_ERROR_FOR[reply.outcome], reply.retry_after_seconds)
    parsed, codes = parse(reply.data, portal)
    if parsed is None:
        _fail(db, user_id, request_id, "OUTPUT_INVALID", reply.usage)
        ai_log.event("assistant_invalid", screen=screen.kind, drop_codes=",".join(codes))
        raise AssistantError("AI_INVALID")
    with db.session(user_id) as cursor:
        cursor.execute(_FINISH, (request_id, "OK" if parsed.status == "ANSWER" else parsed.status,
                                 json.dumps(reply.usage)))
        allowance = usage(cursor, "ASSISTANT")
    ai_log.event("assistant_answered", screen=screen.kind, outcome=parsed.status, masks=masks)
    return _answer(parsed, sent, allowance)


def _answer(parsed: Parsed, sent: str, allowance: dict) -> dict:
    return {"status": parsed.status, "text": parsed.text, "question_sent": sent, "sources": parsed.sources,
            "usage": allowance}
