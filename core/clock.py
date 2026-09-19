"""
مصدر الزمن الوحيد
=================
القاعدة: يُخزَّن كل وقت بـUTC واعٍ، ويُعرض بتوقيت Asia/Riyadh، ويُشتق كل
حساب التزام من تعريف واحد لحدود اليوم.

تدقيق المرحلة 0 وجد 38 استدعاءً لـ`datetime.now()` محلياً ساذجاً، وصفر منطق
لحدود اليوم. أي حساب التزام فوق ذلك كان سيعطي إجابات مختلفة باختلاف منطقة
الخادم. اختبار معماري يفشل البناء إن ظهر `datetime.now()` أو `date.today()`
خارج هذه الوحدة.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

__all__ = [
    "DISPLAY_TZ",
    "day_bounds",
    "ensure_utc",
    "local_day",
    "now",
    "to_display",
]

#: منطقة العرض. التخزين دائماً UTC؛ هذه للعرض ولحدود اليوم التقويمي المحلي.
DISPLAY_TZ = ZoneInfo("Asia/Riyadh")


def now() -> datetime:
    """اللحظة الحالية بـUTC واعٍ. المصدر الوحيد للوقت في النظام."""
    return datetime.now(timezone.utc)


def ensure_utc(moment: datetime) -> datetime:
    """
    تطبيع لحظة إلى UTC واعٍ.

    يرفض اللحظة الساذجة صراحةً: تخمين منطقتها هو تحديداً الخطأ الذي يجعل
    «هل أدّى جلسة اليوم؟» يعطي إجابتين مختلفتين من مسارين.
    """
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(
            "لحظة بلا منطقة زمنية. استخدم core.clock.now() أو مرّر لحظة واعية."
        )
    return moment.astimezone(timezone.utc)


def to_display(moment: datetime) -> datetime:
    """اللحظة نفسها معبَّراً عنها بتوقيت العرض. لا تُخزَّن هذه النتيجة أبداً."""
    return ensure_utc(moment).astimezone(DISPLAY_TZ)


def local_day(moment: datetime) -> date:
    """
    اليوم التقويمي المحلي الذي تقع فيه اللحظة.

    هذا هو التعريف الوحيد لحدود اليوم في النظام. كل حساب التزام يمر من هنا،
    فتتطابق إجابة «هل أدّى جلسة اليوم؟» من أي مسار.
    """
    return to_display(moment).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """
    حدود يوم تقويمي محلي، بـUTC، نصف مفتوحة: [البداية، البداية+يوم).

    محسوبة بالانتقال عبر المنطقة المحلية لا بإضافة 24 ساعة، فتبقى صحيحة عند
    أي انتقال توقيت.
    """
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=DISPLAY_TZ)
    end_local = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=DISPLAY_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
