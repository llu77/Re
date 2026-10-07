"""
كاتبٌ مصطنع — للاختبارات وحدها
==============================
يُحقن عبر `create_app(copywriter=...)`. لا مفتاح بيئي في مسار الإنتاج
يستبدله؛ ولا تستورده إلا الاختبارات (اختبارٌ معماري يفرض ذلك).

يُرجع ما يُعطى بالترتيب، ويحفظ كل طلبٍ وصله ليُفحص ما أُرسل.
"""

from __future__ import annotations

from collections import deque

from eyework.copy_rules import check_copy
from eyework.copywriter import CopyOutcome
from eyework.prompt import CopyRequest

TITLE = "حقيبة جلدية بنية أنيقة"
DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف."
#: كلمة المساعد بأطول ما تُقبل تقريباً: الواجهة تُختبر على أسوأ حالاتها.
NOTE = "أبرزتُ خامة الجلد ولونه البني وحزام الكتف، ولم أذكر المقاس ولا بلد الصنع لأنهما لا يظهران في الصورة؛ أضفهما بملاحظة."


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
