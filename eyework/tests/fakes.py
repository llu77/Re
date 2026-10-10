"""
كاتبٌ وبوّابةٌ مصطنعان — للاختبارات وحدها
=========================================
يُحقنان عبر `create_app(copywriter=..., gateway=...)`. لا مفتاح بيئي في مسار
الإنتاج يستبدلهما؛ ولا يستوردهما إلا الاختبارات (اختبارٌ معماري يفرض ذلك).

كلٌّ منهما يُرجع ما يُعطى بالترتيب، ويحفظ كل طلبٍ وصله ليُفحص ما أُرسل.
والبوّابة تُحبس (`hold`) فيبقى الاستدعاء معلّقاً حتى يُطلق (`release`): تأخيرٌ
يملكه الاختبار بلا `sleep`، به تُختبر PENDING والنتيجة المتأخّرة.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import replace

from eyework.copy_rules import check_copy
from eyework.copywriter import CopyOutcome
from eyework.prompt import CopyRequest
from eyework.prompt_kit import ModelCall, ModelReply

TITLE = "حقيبة جلدية بنية أنيقة"
DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف."
#: كلمة المساعد بأطول ما تُقبل تقريباً: الواجهة تُختبر على أسوأ حالاتها.
NOTE = "أبرزتُ خامة الجلد ولونه البني وحزام الكتف، ولم أذكر المقاس ولا بلد الصنع لأنهما لا يظهران؛ يمكن إضافتهما بملاحظة."


def ok(title: str = TITLE, description: str = DESCRIPTION, note: str | None = NOTE) -> CopyOutcome:
    check = check_copy(title, description)
    assert check.ok, check.errors
    return CopyOutcome("OK", title=title, description=description, warnings=check.warnings, note=note,
                       served_model="claude-opus-5-5", request_id="req_fake",
                       input_tokens=1000, output_tokens=200)


class FakeCopywriter:
    def __init__(self, *outcomes: CopyOutcome) -> None:
        self.outcomes: deque[CopyOutcome] = deque(outcomes)
        self.requests: list[CopyRequest] = []

    def queue(self, *outcomes: CopyOutcome) -> None:
        self.outcomes.extend(outcomes)

    def write(self, request: CopyRequest) -> CopyOutcome:
        self.requests.append(request)
        if not self.outcomes:
            return ok(
                title=f"عنوان النسخة رقم {len(self.requests)} للمنتج",
                description=DESCRIPTION,
            )
        return self.outcomes.popleft()


# ── البوّابة ────────────────────────────────────────────────────────────
#: سببٌ واقتراحٌ بلا نداء، كما يُطلب من النموذج.
REASON = "سعر الوحدة في السطر 3 (45 ريالاً) أعلى بعشرة أضعاف من آخر شراءٍ للصنف (4.50 ريال)."
SUGGESTION = "إن كان السعر للكرتونة فأدخل سعر الحبّة أو غيّر الوحدة."
ANSWER = "ابدأ من «حملة جديدة» لتكتب نصّ منتجٍ من صورته، ثم راجع «حملاتي» لما ينتظر اعتمادك."


def model_reply(outcome: str = "OK", data: dict | None = None, *, retry_after: int | None = None,
                status: int | None = None, request_id: str | None = "req_fake", model: str | None = "claude-opus-5-5",
                input_tokens: int = 1200, output_tokens: int = 150, cache_read: int = 900, cache_write: int = 0,
                stop_reason: str | None = None, refusal_category: str | None = None) -> ModelReply:
    """جوابٌ بشكل البوّابة الحقيقية. ما ليس OK بلا بيانات؛ وما لم يُعالَج بلا أرقام."""
    processed = outcome not in ("UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_ERROR")
    usage = {"prompt_version": "test", "api_request_id": request_id}
    if processed:
        usage.update(input=input_tokens, output=output_tokens, cache_read=cache_read, cache_write=cache_write,
                     model=model)
    return ModelReply(outcome, data if outcome == "OK" else None, usage,
                      stop_reason or ("end_turn" if outcome == "OK" else None), refusal_category, processed,
                      retry_after, status)


def flag(check: str = "PRICE_IMPLAUSIBLE", severity: str = "HIGH", field: str = "unit_cost", line: int | None = 3,
         reason: str = REASON, suggestion: str = SUGGESTION) -> dict:
    """ملاحظةٌ بالمفاتيح الستّة التي يكتبها النموذج (الشواهد يبنيها الخادم)."""
    return {"check": check, "severity": severity, "field": field, "line": line, "reason": reason,
            "suggestion": suggestion}


#: مسودة دعمٍ بلا مقالة: طلب معلوماتٍ بسؤال، كما يكتبها سيمبول حين لا تجيب القاعدة.
ASK_BODY = "لنساعدكم بسرعة، ما نصّ رسالة الخطأ كما تظهر على الشاشة؟"


def draft_reply(status: str = "CANNOT_ANSWER", kind: str = "ASK_INFO", body: str = ASK_BODY,
                citations: tuple[dict, ...] = (), subject: str = "الطابعة لا تطبع", category: str = "PRINTING",
                impact: str = "SINGLE", urgency: str = "DEGRADED", security: bool = False, escalate: str = "NONE",
                note: str = "لا مقالة في القاعدة عن هذه المشكلة.") -> ModelReply:
    """جواب مسودة الدعم بحقوله الأحد عشر."""
    return model_reply("OK", {"status": status, "reply_kind": kind, "body": body, "citations": list(citations),
                              "subject": subject, "category": category, "impact": impact, "urgency": urgency,
                              "security_concern": security, "escalate": escalate, "note_to_employee": note})


def review_reply(*flags: dict) -> ModelReply:
    return model_reply("OK", {"flags": list(flags)})


def assistant_reply(status: str = "ANSWER", answer: str = ANSWER, used: tuple[str, ...] = ("T1", "SCREEN"),
                    tool: str = "NONE", tool_input: str = "", open: str = "NONE") -> ModelReply:
    return model_reply("OK", {"status": status, "answer": answer, "used": list(used), "tool": tool,
                              "tool_input": tool_input, "open": open})


def tool_request(tool: str, tool_input: str = "") -> ModelReply:
    """المساعد يطلب أداة قراءة: status = TOOL بلا جواب."""
    return assistant_reply("TOOL", "", (), tool, tool_input)


class FakeGateway:
    """
    يُرجع الأجوبة بالترتيب، وبلا أجوبة مجدولة يُرجع جواباً ناجحاً يناسب الأداة
    (مراجعةٌ بلا ملاحظات، أو جوابٌ مؤسَّس). كل استدعاءٍ يُحفظ في `calls`.
    """

    def __init__(self, *replies: ModelReply) -> None:
        self.replies: deque[ModelReply] = deque(replies)
        self.calls: list[ModelCall] = []
        self._released = threading.Event()
        self._released.set()

    def queue(self, *replies: ModelReply) -> None:
        self.replies.extend(replies)

    def hold(self) -> None:
        """الاستدعاءات التالية تبقى معلّقة حتى `release()`: تأخيرٌ بلا نوم."""
        self._released.clear()

    def release(self) -> None:
        self._released.set()

    def call(self, request: ModelCall) -> ModelReply:
        self.calls.append(request)
        self._released.wait(timeout=30.0)
        if self.replies:
            reply = self.replies.popleft()
        elif request.feature == "ASSISTANT":
            reply = assistant_reply()
        elif request.feature == "SUPPORT_DRAFT":
            reply = draft_reply()
        else:
            reply = review_reply()
        return replace(reply, usage={**reply.usage, "prompt_version": request.prompt_version})
