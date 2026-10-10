"""
«سيمبول»: المساعد في زرّ المحادثة العائم
=======================================
يحادث الموظف عن عمله من مصدرين لا غير: بيانات الشاشة التي يسأل منها، وأدوات
قراءةٍ يطلبها (`TOOLS`: المنتجات، الحملات، قاعدة المعرفة، حاسبة الضريبة…)؛ ولا
يشرح له مهنته، فهو يعرفها. الأداة تقرأ ولا تغيّر، وتعمل بهوية الجلسة وتحت العزل،
وما تعيده يمرّ بالإخفاء قبل أن يصل النموذج؛ وأداتان على الأكثر لكل سؤال، والوقت
كلّه داخل عقد الطلب. ولا يفعل شيئاً بنفسه: يقترح شاشةً (`DESTINATIONS`) فيظهر
زرٌّ يضغطه الموظف. ويقول إنه لا يعرف حين لا يعرف.

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
from decimal import Decimal, InvalidOperation
from uuid import UUID

from eyework import ai_log, clock
from eyework.ai_limits import ASSISTANT as ASSISTANT_CALL, FEATURES, QUESTION_LENGTH, SCREEN_DATA_CHARS
from eyework.assistant_prompt import (
    DONT_KNOW_TEXT, HISTORY_MAX, Destination, Parsed, ScreenContext, Tool, call as build_call, check_answer, check_question,
    parse,
)
from eyework.db import Database
from eyework.inventory_rules import halalas_words, normalise_digits, vat_split
from eyework.model_gateway import Guard
from eyework.professions import Profession
from eyework.prompt_kit import Gateway
from eyework.redact import redact
from eyework.reviewer import usage
from eyework.service_errors import Invalid, NotFound

__all__ = [
    "DESTINATIONS", "MAX_TOOL_CALLS", "SCREENS", "TOOLS", "AssistantError", "Destination", "ScreenContext", "Tool", "ask",
    "choices", "fit", "register", "register_destinations", "register_tool",
]

#: أداتان على الأكثر لكل سؤال: ثلاثة استدعاءاتٍ للنموذج في عقد الطلب.
MAX_TOOL_CALLS = 2
#: ما يبقى من عقد الطلب لاستدعاءٍ آخر: إن لم يبقَ فلا أداة بعد.
_LEASE_SECONDS = FEATURES["ASSISTANT"].lease_seconds

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
    ready_questions=("من أين أبدأ عملي اليوم؟",),
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


TOOLS: dict[str, Tool] = {}
DESTINATIONS: dict[Profession, tuple[Destination, ...]] = {}


def register_tool(tool: Tool) -> None:
    TOOLS[tool.name] = tool


def register_destinations(profession: Profession, destinations: tuple[Destination, ...]) -> None:
    """وجهات مهنةٍ بمعرّفات بنود رئيسيتها في العميل (lib/workspace.ts، يقارنهما اختبار)."""
    DESTINATIONS[profession] = destinations


def tools_for(profession: Profession) -> tuple[Tool, ...]:
    return tuple(tool for tool in TOOLS.values() if tool.serves(profession))


register(HOME)
register(CAMPAIGN)


# ── أدوات المساعد المشتركة وأدوات التسويق ────────────────────────────────
def _vat(cursor, user_id: UUID, text: str) -> tuple[str, ...]:
    """الضريبة 15% على مبلغٍ بالريال، بالتقريب نفسه في القاعدة وحاسبة المخزون: قبلها وشاملةً لها."""
    raw = normalise_digits(text).replace(",", "").replace("٬", "").strip()
    raw = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return ("لم يُفهم المبلغ: يُكتب رقماً بالريال، مثل 115.",)
    if not Decimal("0.01") <= amount <= Decimal("100000000"):
        return ("المبلغ خارج ما تحسبه الأداة (من هللةٍ إلى مئة مليون ريال).",)
    halalas = int((amount * 100).to_integral_value())
    net, vat, gross = vat_split(halalas, "net", "S")
    g_net, g_vat, g_gross = vat_split(halalas, "gross", "S")
    return (f"{halalas_words(halalas)} قبل الضريبة: الضريبة {halalas_words(vat)}، والإجمالي {halalas_words(gross)}.",
            f"{halalas_words(halalas)} شاملةً الضريبة: قبلها {halalas_words(g_net)}، والضريبة {halalas_words(g_vat)}.")


_CAMPAIGN_LIST = """
SELECT c.status, v.title, c.budget_sar, c.days, c.updated_at::date AS updated
  FROM campaigns c
  LEFT JOIN copy_versions v ON v.id = c.current_version_id
 WHERE c.status <> 'CANCELLED'
 ORDER BY c.updated_at DESC, c.id
 LIMIT 8
"""


def _campaigns(cursor, user_id: UUID, text: str) -> tuple[str, ...]:
    cursor.execute(_CAMPAIGN_LIST)
    rows = cursor.fetchall()
    if not rows:
        return ("لا حملات بعد.",)
    lines = []
    for row in rows:
        line = f"«{row['title'] or 'بلا نصّ بعد'}» — {STATUS_NAMES.get(row['status'], row['status'])}"
        if row["budget_sar"] is not None:
            line += f"، الميزانية {row['budget_sar']} ريال"
        if row["days"] is not None:
            line += f" لـ{row['days']} يوماً"
        lines.append(line + f" (آخر تعديل {row['updated'].isoformat()})")
    return fit(lines)


register_tool(Tool(
    name="VAT", profession=None,
    description="يحسب ضريبة القيمة المضافة (15%) لمبلغٍ بالريال: قبلها وشاملةً لها.",
    input_hint="المبلغ بالريال", label="حاسبة الضريبة", run=_vat,
))
register_tool(Tool(
    name="CAMPAIGNS", profession=Profession.MARKETING,
    description="حملات الموظف الثماني الأحدث: العنوان والحالة والميزانية والمدّة.",
    input_hint=None, label="حملاتك", run=_campaigns,
))
register_destinations(Profession.MARKETING, (
    Destination("new", "حملة جديدة"),
    Destination("campaigns", "حملاتي"),
))


def choices() -> dict:
    """ما تعرضه الواجهة: حدّ السؤال والأسئلة الجاهزة لكل شاشة (لـ/api/choices)."""
    return {"question_max": QUESTION_LENGTH[1],
            "ready": {kind: list(screen.ready_questions) for kind, screen in SCREENS.items()}}


def _fail(db: Database, user_id: UUID, request_id: UUID, outcome: str, usage_json: dict | None) -> None:
    with db.session(user_id) as cursor:
        cursor.execute(_FAIL, (request_id, outcome, None if usage_json is None else json.dumps(usage_json)))


def _history(history: list | tuple | None) -> tuple[tuple[str, str], ...]:
    """آخر ثلاثة أسئلةٍ بأجوبتها كما يرسلها العميل: كلٌّ يُفحص ويُخفى كالسؤال."""
    if not history:
        return ()
    turns = []
    for question, answer in list(history)[-HISTORY_MAX:]:
        try:
            question = check_question(question)
        except Invalid:
            raise Invalid("HISTORY", field="history") from None
        turns.append((redact(question)[0], redact(check_answer(answer))[0]))
    return tuple(turns)


def _add_usage(total: dict | None, usage_json: dict | None) -> dict | None:
    """مجموع ما استهلكته استدعاءات السؤال الواحد، للدفتر: الأعداد تُجمع، والباقي من آخر استدعاء."""
    if usage_json is None:
        return total
    if total is None:
        return dict(usage_json)
    merged = dict(usage_json)
    for key, value in total.items():
        if isinstance(value, int) and isinstance(usage_json.get(key), int):
            merged[key] = value + usage_json[key]
    return merged


def _run_tool(db: Database, user_id: UUID, tool: Tool, text: str) -> tuple[str, ...]:
    """الأداة بهوية الجلسة وتحت العزل، وكل سطرٍ بعد الإخفاء."""
    with db.session(user_id) as cursor:
        return tuple(redact(line)[0] for line in tool.run(cursor, user_id, text))


def ask(db: Database, gateway: Gateway, guard: Guard, user_id: UUID, screen_kind: str, screen_id: UUID | None,
        question: str | None, ready: int | None, history: list | tuple | None = None) -> dict:
    """
    سؤالٌ في محادثة: الشاشة من السجلّ بمهنة الجلسة، والسؤال والمحادثة بعد فحصهما وإخفائهما (أو
    سؤالٌ جاهز بفهرسه)، ثم الحارس، ثم صفّ الدفتر، ثم النموذج — ومعه الأدوات التي يطلبها، أداتان على
    الأكثر — ثم الفحص، ثم الإغلاق. ما يفشل يُغلق محسوباً ويرفع `AssistantError` برمزه.
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
    turns = _history(history)

    reason = guard.acquire()
    if reason is not None:
        ai_log.event("assistant_unavailable", reason=reason)
        raise AssistantError("AI_UNAVAILABLE" if reason == "DOWN" else "AI_BUSY", 30)
    called = False
    started = clock.monotonic()
    usage_total: dict | None = None
    results: list[tuple[str, str, tuple[str, ...]]] = []
    used_tools: list[dict] = []
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
        tools = tools_for(profession)
        destinations = DESTINATIONS.get(profession, ())
        while True:
            try:
                reply = gateway.call(build_call(screen, profession, lines, sent, history=turns,
                                                results=tuple(results), tools=tools, destinations=destinations))
            except Exception:
                _fail(db, user_id, request_id, "UPSTREAM_ERROR", usage_total)
                raise
            called = True
            guard.record(reply)
            usage_total = _add_usage(usage_total, reply.usage)
            if reply.outcome != "OK":
                break
            parsed, codes = parse(reply.data, tools, destinations)
            if parsed is None or parsed.status != "TOOL":
                break
            elapsed = clock.monotonic() - started
            asked = (parsed.tool, parsed.tool_input)
            if len(results) >= MAX_TOOL_CALLS or asked in {(name, text) for name, text, _ in results} \
                    or elapsed + ASSISTANT_CALL.deadline_seconds > _LEASE_SECONDS:
                # أداةٌ ثالثة، أو مكرّرة، أو لا وقت لاستدعاءٍ آخر: لا جواب من البيانات هذه المرة.
                parsed = Parsed("DONT_KNOW", DONT_KNOW_TEXT, ())
                ai_log.event("assistant_tool_stop", screen=screen.kind, tools=len(results))
                break
            tool = TOOLS[parsed.tool]
            try:
                found = _run_tool(db, user_id, tool, parsed.tool_input)
            except Exception:
                _fail(db, user_id, request_id, "UPSTREAM_ERROR", usage_total)
                raise
            results.append((tool.name, parsed.tool_input, found))
            used_tools.append({"name": tool.name, "label": tool.label, "input": parsed.tool_input})
            ai_log.event("assistant_tool", screen=screen.kind, tool=tool.name)
    finally:
        # شاشةٌ مرفوضة أو سقفٌ أو انهيارٌ قبل الجواب: لم يُسجَّل شيءٌ في القاطع، فيعود إذن التجربة.
        guard.release(called=called)

    if reply.outcome != "OK":
        _fail(db, user_id, request_id, reply.outcome, usage_total)
        raise AssistantError(_ERROR_FOR[reply.outcome], reply.retry_after_seconds)
    if parsed is None:
        _fail(db, user_id, request_id, "OUTPUT_INVALID", usage_total)
        ai_log.event("assistant_invalid", screen=screen.kind, drop_codes=",".join(codes))
        raise AssistantError("AI_INVALID")
    with db.session(user_id) as cursor:
        cursor.execute(_FINISH, (request_id, "OK" if parsed.status == "ANSWER" else parsed.status,
                                 json.dumps(usage_total)))
        allowance = usage(cursor, "ASSISTANT")
    ai_log.event("assistant_answered", screen=screen.kind, outcome=parsed.status, masks=masks, tools=len(used_tools))
    place = next((d for d in destinations if d.id == parsed.open), None)
    return _answer(parsed, sent, allowance, used_tools, place)


def _answer(parsed: Parsed, sent: str, allowance: dict, used_tools: list[dict] | None = None,
            place: Destination | None = None) -> dict:
    return {"status": parsed.status, "text": parsed.text, "question_sent": sent, "usage": allowance,
            "tools": used_tools or [], "open": None if place is None else {"id": place.id, "label": place.label}}
