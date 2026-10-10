"""
أخطاء الخدمات
=============
ثلاثة أصنافٍ تشترك فيها كل خدمات التطبيق (الحملات، والمراجِع، والمساعد، وما
يأتي بعدها): غير موجود، وتعارضٌ مع ما رآه صاحب الطلب، ومدخلٌ لا يُقبل. كانت في
`campaigns.py` وحدها، ونُقلت هنا لأن أربع خدماتٍ تحتاجها؛ و`campaigns` يعيد
تصديرها فلا يتغيّر ما كان يستوردها منه.

وحدةٌ نقية: لا قاعدة ولا ويب. طبقة الويب تترجم كل صنفٍ إلى حالةٍ ورسالةٍ
عربية (`web/app.py`)، ولا تعرف الخدمة شيئاً عن HTTP.
"""

from __future__ import annotations

__all__ = ["Conflict", "Invalid", "NotFound"]


class NotFound(Exception):
    """
    غير موجود — أو لغير صاحب الجلسة، ولا فرق في الجواب.

    `code` و`detail` اختياريان: الحملة تكتفي بالافتراضي، والملاحظة والشاشة
    تسمّيان نفسيهما كي لا يُقال «الحملة غير موجودة» عن ملاحظة.
    """

    def __init__(self, code: str = "NOT_FOUND", detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


class Conflict(Exception):
    """
    تغيّر الشيء منذ رآه صاحب الطلب. `code` يسمّي السبب، و`detail` رسالته إن
    لم تكن رسالة الحملة، و`extra` حقولٌ تُضاف إلى الجواب (كالملاحظات التي
    لم يُبتّ فيها عند الاعتماد).
    """

    def __init__(self, code: str = "STALE", detail: str | None = None, extra: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.extra = extra


class Invalid(Exception):
    """مدخلٌ لا يُقبل. `code` رمزٌ ثابت، و`field` الحقل الذي يُصلَح إن عُرف، و`extra` حقولٌ تُضاف إلى الجواب."""

    def __init__(self, code: str, field: str | None = None, extra: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.field = field
        self.extra = extra
