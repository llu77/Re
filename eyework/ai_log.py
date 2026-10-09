"""
سجلٌّ بلا محتوى
===============
المدخل الوحيد الذي تسجّل منه وحدات الذكاء الاصطناعي (اختبارٌ معماري يرفض
`logger` و`print` فيها إلا من هنا). يقبل حقولاً مسمّاةً معدودة، كلّها أرقامٌ أو
رموزٌ قصيرة: الأداة، والنتيجة، والمعرّفات، والرموز، والزمن، وأعداد الملاحظات.

**لا نصّ قطّ.** لا سؤال ولا جواب ولا مطالبة ولا اسم ولا معرّف مستخدم، ولا
استثناء بوسائطه: رسائل العملاء وأسماء الأصناف وأسئلة الموظف لا تصل سجلّ
المشغّل. حقلٌ غير معروف خطأٌ برمجي يُرفع؛ وقيمةٌ نصّية لا تطابق شكل الرمز
تُكتب «?» بدلها، فلا يتسرّب نصٌّ حرّ ولو أخطأ مستدعٍ.

اختبار «الكناري» يمرّر نصّاً فريداً في كل مدخل ويتأكّد أنه لا يظهر في السجلّ.
"""

from __future__ import annotations

import logging
import re

__all__ = ["FIELDS", "event"]

logger = logging.getLogger("eyework.ai")

#: الحقول المقبولة وحدها.
FIELDS = frozenset({
    "feature", "outcome", "request_id", "api_request_id", "served_model", "prompt_version",
    "input_tokens", "output_tokens", "thinking_tokens", "cache_read", "cache_write",
    "latency_ms", "stop_reason", "refusal_category",
    "flags_kept", "flags_dropped", "drop_codes", "masks",
    "status", "reason", "constraint", "screen", "kind",
})
_LEVELS = {
    "debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
    "error": logging.ERROR, "critical": logging.CRITICAL,
}
#: شكل الرمز: حروفٌ لاتينية وأرقام وفواصل قصيرة. ما سواه ليس رمزاً.
_SAFE = re.compile(r"[A-Za-z0-9_.,:-]{1,128}")


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str) and _SAFE.fullmatch(value):
        return value
    return "?"


def event(name: str, *, level: str = "info", **fields: object) -> None:
    """حدثٌ واحد: اسمه وحقوله المعدودة. `None` لا يُكتب."""
    unknown = set(fields) - FIELDS
    if unknown:
        raise TypeError(f"حقولٌ لا يقبلها السجلّ: {sorted(unknown)}")
    parts = [f"{key}={_text(fields[key])}" for key in sorted(fields) if fields[key] is not None]
    logger.log(_LEVELS[level], "%s %s", _text(name), " ".join(parts))
