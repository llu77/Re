"""
الأخطاء ورسائلها
================
جدولٌ واحد من الرمز إلى (الحالة، الرسالة العربية). رسالة الخطأ من القاعدة لا
تصل العميل ولا السجلّ أبداً: `diag.message_detail` في PostgreSQL يحمل قيم
الصفّ المخالف — وقد تكون نصّ إعلانٍ أو بايتات صورة.

الرسائل قصيرة وتقول ما يفعله المستخدم بعدها، لا ما حدث في الخادم.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ErrorSpec", "AI_OUTCOMES", "CONSTRAINTS", "EDIT_REQUEST", "IMAGE", "UNUSABLE", "GENERIC"]


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    status: int
    code: str
    detail: str
    retry_after: int | None = None


_STALE = "تغيّرت الحملة منذ عرضها. راجعها مرة أخرى."

#: قيود القاعدة بأسمائها.
CONSTRAINTS: dict[str, ErrorSpec] = {
    "stale_row_version": ErrorSpec(409, "STALE", _STALE),
    "generation_wrong_state": ErrorSpec(409, "STALE", _STALE),
    "generation_needs_image": ErrorSpec(409, "NO_IMAGE", "اختر صورة المنتج أولاً."),
    "generation_in_progress": ErrorSpec(409, "WRITING", "المساعد يكتب الآن. انتظر حتى ينتهي."),
    "generation_rate": ErrorSpec(429, "AI_RATE", "طلباتٌ كثيرة خلال وقتٍ قصير. حاول بعد دقائق.", 600),
    "generation_daily_cap": ErrorSpec(429, "AI_DAILY", "بلغتَ حدّ اليوم من طلبات الكتابة. حاول غداً.", 3600),
    "generation_global_cap": ErrorSpec(503, "AI_BUSY", "خدمة الكتابة مشغولة الآن. حاول لاحقاً.", 600),
    "version_cap": ErrorSpec(409, "VERSION_CAP", "بلغت هذه الحملة عشر نسخ، وهو الحدّ."),
    "open_campaign_cap": ErrorSpec(409, "OPEN_CAP", "لديك عشرون حملةً مفتوحة. أكمل بعضها أو ألغِه أولاً."),
    "campaign_is_final": ErrorSpec(409, "FINAL", "الحملة معتمدة أو ملغاة ولا تتغيّر."),
    "campaign_transition": ErrorSpec(409, "STALE", _STALE),
    "money_only_while_approved": ErrorSpec(409, "STALE", _STALE),
    "image_only_in_draft": ErrorSpec(409, "STALE", _STALE),
    "approved_copy_is_fixed": ErrorSpec(409, "STALE", _STALE),
    "version_sequence": ErrorSpec(409, "STALE", _STALE),
    "version_needs_open_attempt": ErrorSpec(409, "STALE", _STALE),
    "version_image_changed": ErrorSpec(409, "STALE", _STALE),
    "image_locked_during_generation": ErrorSpec(409, "WRITING", "المساعد يكتب الآن. انتظر حتى ينتهي."),
    "current_version_target": ErrorSpec(409, "STALE", _STALE),
    "budget_in_domain": ErrorSpec(422, "BUDGET_RANGE", "اختر مبلغاً من القيم المعروضة."),
    "days_in_range": ErrorSpec(422, "DAYS_RANGE", "المدّة من يومٍ واحد إلى ثلاثين يوماً."),
}

GENERIC = ErrorSpec(422, "CONSTRAINT", "الطلب يخالف قيداً. راجع القيم وحاول مرة أخرى.")

#: نتائج الكاتب غير الناجحة. المحاولة حُسبت في كل حال.
AI_OUTCOMES: dict[str, ErrorSpec] = {
    "REFUSED": ErrorSpec(422, "AI_REFUSED", "لا يستطيع المساعد الكتابة عن هذه الصورة. جرّب صورةً أخرى للمنتج."),
    "OUTPUT_INVALID": ErrorSpec(502, "AI_OUTPUT_INVALID", "لم يكتمل النصّ هذه المرة. حاول مرة أخرى."),
    "UPSTREAM_BUSY": ErrorSpec(503, "AI_BUSY", "خدمة الكتابة مشغولة الآن. حاول بعد قليل.", 30),
    "UPSTREAM_TIMEOUT": ErrorSpec(504, "AI_TIMEOUT", "تأخّرت خدمة الكتابة. حاول مرة أخرى."),
    "UPSTREAM_ERROR": ErrorSpec(503, "AI_UNAVAILABLE", "خدمة الكتابة غير متاحة الآن."),
}

#: الصورة لا تصلح لإعلان. ليست خطأً: الحملة تبقى مسودةً لصورةٍ أخرى.
UNUSABLE: dict[str, str] = {
    "NO_PRODUCT": "لا يظهر منتجٌ واضح في الصورة. اختر صورةً أخرى.",
    "UNCLEAR_PHOTO": "الصورة غير واضحة. اختر صورةً أوضح للمنتج.",
    "MULTIPLE_PRODUCTS": "في الصورة أكثر من منتج. اختر صورةً لمنتجٍ واحد.",
    "NOT_ALLOWED": "لا يمكن كتابة إعلانٍ لهذا المنتج.",
}

#: رفض الصورة قبل تخزينها.
IMAGE: dict[str, ErrorSpec] = {
    "EMPTY": ErrorSpec(415, "IMAGE_TYPE", "اختر صورةً بصيغة JPEG أو PNG أو WebP."),
    "UNSUPPORTED_TYPE": ErrorSpec(415, "IMAGE_TYPE", "اختر صورةً بصيغة JPEG أو PNG أو WebP."),
    "TOO_LARGE": ErrorSpec(413, "IMAGE_TOO_LARGE", "الصورة أكبر من ١٢ ميغابايت. اختر صورةً أصغر."),
    "TOO_SMALL": ErrorSpec(422, "IMAGE_TOO_SMALL", "الصورة صغيرة جداً. اختر صورةً أوضح."),
    "BAD_ASPECT": ErrorSpec(422, "IMAGE_ASPECT", "الصورة طويلةٌ أو عريضة أكثر من اللازم."),
    "TOO_MANY_PIXELS": ErrorSpec(422, "IMAGE_PIXELS", "أبعاد الصورة كبيرة جداً. اختر صورةً أصغر."),
    "ANIMATED": ErrorSpec(422, "IMAGE_ANIMATED", "الصور المتحركة غير مدعومة. اختر صورةً ثابتة."),
    "CORRUPT": ErrorSpec(422, "IMAGE_UNREADABLE", "تعذّرت قراءة الصورة. اختر صورةً أخرى."),
    "METADATA_SURVIVED": ErrorSpec(422, "IMAGE_UNREADABLE", "تعذّرت قراءة الصورة. اختر صورةً أخرى."),
}

#: طلب التعديل.
EDIT_REQUEST: dict[str, ErrorSpec] = {
    "EDIT_EMPTY": ErrorSpec(422, "EDIT_EMPTY", "اختر تعديلاً واحداً على الأقل، أو اكتب ملاحظة."),
    "PRESET_CONFLICT": ErrorSpec(422, "EDIT_CONFLICT", "اخترتَ تعديلين متعاكسين. اختر أحدهما."),
    "PRESET_DUPLICATE": ErrorSpec(422, "EDIT_DUPLICATE", "تعديلٌ مكرّر."),
    "PRESET_TOO_MANY": ErrorSpec(422, "EDIT_TOO_MANY", "ثلاثة تعديلاتٍ على الأكثر في كل طلب."),
    "NOTE_LENGTH": ErrorSpec(422, "NOTE_LENGTH", "الملاحظة من حرفٍ إلى مئتي حرف."),
    "NOTE_CONTROL": ErrorSpec(422, "NOTE_CONTROL", "في الملاحظة محارف غير مقبولة."),
    "BUDGET_RANGE": ErrorSpec(422, "BUDGET_RANGE", "اختر مبلغاً من القيم المعروضة."),
    "RESTORE_TARGET": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    "DAYS_RANGE": ErrorSpec(422, "DAYS_RANGE", "المدّة من يومٍ واحد إلى ثلاثين يوماً."),
}
