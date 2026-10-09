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

__all__ = ["ErrorSpec", "AI_OUTCOMES", "CONSTRAINTS", "EDIT_REQUEST", "IMAGE", "REGISTRATION",
           "REGISTRATION_CONSTRAINTS", "TERMS_REQUIRED", "UNUSABLE", "GENERIC", "AI_ASSISTANT", "AI_INVALID",
           "AI_REVIEW_INVALID"]


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
    "campaign_needs_marketing": ErrorSpec(403, "PROFESSION", "هذه الأداة لبوابة مهنةٍ أخرى."),
    "passkey_cap": ErrorSpec(409, "PASSKEY_CAP", "لهذا الحساب عشرة مفاتيح مرور، وهو الحدّ."),
    # الواجهة لا تعرض هذا: الإنشاء بعد الدخول بكلمة المرور صامتٌ نجح أو لم ينجح.
    "passkey_needs_password_sign_in": ErrorSpec(403, "PASSKEY_UPGRADE",
                                                "يُنشأ مفتاح المرور بعد الدخول بكلمة المرور مباشرةً."),
    "passkey_login_ceiling": ErrorSpec(503, "PASSKEY_BUSY",
                                       "الدخول بمفتاح المرور مشغولٌ الآن. ادخل بكلمة المرور، أو حاول بعد قليل.",
                                       60),
    "registration_daily_cap": ErrorSpec(503, "REGISTER_FULL",
                                        "اكتمل عدد الحسابات الجديدة لهذا اليوم. حاول غداً.", 3600),
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
    # طبقة الذكاء الاصطناعي (0009): كما تصل مسارات المساعد والقرار واعتماد مساحات
    # العمل. مسار المراجعة لا يُرجع هذه الرموز: السقوف عنده 200 «غير متاح».
    "ai_feature_profession": ErrorSpec(403, "PROFESSION", "هذه الأداة لبوابة مهنةٍ أخرى."),
    "ai_request_in_progress": ErrorSpec(409, "AI_BUSY", "سيمبول يجيب عن سؤالك السابق. انتظر قليلاً."),
    "ai_rate": ErrorSpec(429, "AI_RATE", "أسئلةٌ كثيرة في وقتٍ قصير. حاول بعد دقائق.", 600),
    "ai_daily_cap": ErrorSpec(429, "AI_DAILY", "انتهت أسئلة اليوم. تتجدّد خلال 24 ساعة.", 3600),
    "ai_new_account_daily_cap": ErrorSpec(429, "AI_NEW_DAILY", "انتهت أسئلة اليوم. تتجدّد خلال 24 ساعة.", 3600),
    "ai_feature_app_cap": ErrorSpec(503, "AI_APP_BUSY", "سيمبول مشغولٌ اليوم. حاول لاحقاً.", 3600),
    "ai_flags_undecided": ErrorSpec(409, "FLAGS_UNDECIDED", "وصلت ملاحظةٌ من سيمبول بعد مراجعته. القرار لك."),
    "ai_flag_closed": ErrorSpec(409, "FLAG_CLOSED", "اعتُمد العمل، ولم يعد لهذه الملاحظة قرار."),
    "ai_decision_undo": ErrorSpec(409, "UNDO_INVALID", "لا تراجع إلا عن «تابع رغم ذلك»."),
    "ai_decision_cap": ErrorSpec(429, "DECISION_CAP", "قراراتٌ كثيرة على هذه الملاحظة."),
    "ai_decision_choice": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    # خللٌ في الخادم لا في الطلب: يُسجَّل القيد ويُجاب كخطأٍ داخلي.
    "ai_request_not_open": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_flags_shape": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_usage_shape": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_flag_texts": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_flag_immutable": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_outcome_needs_record": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    "ai_feature_unknown": ErrorSpec(500, "INTERNAL", "حدث خطأ. حاول مرة أخرى."),
    # التسجيل المفتوح (0008): السقوف تُفحص قبل الإدراج، فالجواب عند الامتلاء واحدٌ لكل بريد.
    "registration_open_daily_cap": ErrorSpec(503, "REGISTER_FULL",
                                             "اكتمل عدد الحسابات الجديدة لهذا اليوم. حاول غداً.", 3600),
    "registration_open_paused": ErrorSpec(503, "REGISTER_PAUSED", "إنشاء الحسابات متوقّفٌ مؤقتاً. حاول غداً.", 3600),
    "generation_new_account_cap": ErrorSpec(429, "AI_NEW_DAILY",
                                            "للحساب الجديد عشرة طلبات كتابةٍ في اليوم خلال أسبوعه الأول. حاول غداً.",
                                            3600),
    "generation_new_accounts_cap": ErrorSpec(503, "AI_NEW_BUSY",
                                             "بلغت الحسابات الجديدة حدّها من طلبات الكتابة اليوم. حاول غداً.", 3600),
    "new_account_campaign_cap": ErrorSpec(409, "NEW_OPEN_CAP",
                                          "للحساب الجديد ثلاث حملاتٍ مفتوحة في أسبوعه الأول. أكمل إحداها أو ألغِها أولاً."),
    "terms_version_backwards": ErrorSpec(409, "TERMS_STALE", "وافقتَ على نسخةٍ أحدث من هذه. أعد تحميل الصفحة."),
}

#: ليس قيداً: بوّابة الموافقة (`web/deps.require_current_terms`). لا يُرسَل شيءٌ إلى
#: مزوّد النموذج لمن لم يوافق على النسخة الحالية من «قبل أن تبدأ».
TERMS_REQUIRED = ErrorSpec(403, "TERMS", "تغيّر ما يُرسَل إلى Anthropic منذ وافقت. اقرأه ووافق عليه أولاً.")

GENERIC = ErrorSpec(422, "CONSTRAINT", "الطلب يخالف قيداً. راجع القيم وحاول مرة أخرى.")

#: نتائج الكاتب غير الناجحة. المحاولة حُسبت في كل حال.
AI_OUTCOMES: dict[str, ErrorSpec] = {
    "REFUSED": ErrorSpec(422, "AI_REFUSED", "لا يستطيع المساعد الكتابة عن هذه الصورة. جرّب صورةً أخرى للمنتج."),
    # الرفض عاد لأن نموذج البديل كان مشغولاً: ليس حكماً على الصورة.
    "REFUSED_RETRY": ErrorSpec(503, "AI_BUSY", "تعذّر إكمال الطلب الآن. حاول بعد قليل.", 30),
    # التعديل لا يطلب صورةً أخرى: الحملة بعد اقتراح النصّ لا تقبل تغيير صورتها.
    "EDIT_REFUSED": ErrorSpec(422, "AI_EDIT_REFUSED",
                              "لم يكتب المساعد هذا التعديل. جرّب خياراتٍ أخرى أو غيّر الملاحظة."),
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


#: التسجيل: لكل حقلٍ رسالته، فتعود الواجهة إلى خطوته.
REGISTRATION: dict[str, ErrorSpec] = {
    "NAME": ErrorSpec(422, "REGISTER_INVALID", "الاسم: حروفٌ عربية أو لاتينية فقط، حتى 30 حرفاً."),
    "BIRTH": ErrorSpec(422, "REGISTER_INVALID", "تاريخ الميلاد غير صحيح أو لم يأتِ بعد. اختر السنة والشهر واليوم من جديد."),
    "CONSENT": ErrorSpec(422, "REGISTER_INVALID", "الموافقة على الإشعار مطلوبة لإنشاء الحساب."),
    "EMAIL": ErrorSpec(422, "REGISTER_INVALID", "البريد غير صحيح. مثال: name@example.com"),
    "PASSWORD": ErrorSpec(422, "REGISTER_INVALID", "كلمة المرور من 12 حرفاً على الأقل."),
    "TAKEN": ErrorSpec(409, "REGISTER_TAKEN",
                       "يوجد حسابٌ بهذا البريد. ادخل به، أو اكتب بريداً آخر."),
    "CODE": ErrorSpec(410, "REGISTER_CODE",
                      "رابط التسجيل غير صالح أو انتهى. اطلب رابطاً جديداً ممّن أعطاك إياه."),
    "CLOSED": ErrorSpec(403, "REGISTER_CLOSED", "التسجيل مغلق. اطلب دعوةً ممّن يدير التطبيق."),
    "LINK_REQUIRED": ErrorSpec(403, "REGISTER_LINK", "التسجيل هنا برابطٍ ممّن يدير التطبيق. اطلبه منه."),
    "UI_SIZE": ErrorSpec(422, "REGISTER_INVALID", "اختر كيف تستخدم الجهاز: باللمس أو بتتبّع العين."),
    "TERMS": ErrorSpec(409, "REGISTER_TERMS", "تغيّر نصّ «قبل أن تبدأ» منذ قرأته. اقرأه من جديد، ثم وافق."),
}

#: قيود القاعدة على التسجيل ← الحقل الذي يُصلَح. «اليوم» بتاريخ الرياض في القاعدة لا بساعة بايثون.
REGISTRATION_CONSTRAINTS: dict[str, str] = {
    "registration_birth_date": "BIRTH",
    "registration_needs_consent": "CONSENT",
    "birth_date_range": "BIRTH",
    "display_name_shape": "NAME",
    "registration_needs_name": "NAME",
    "registration_needs_ui_size": "UI_SIZE",
    "ui_size_known": "UI_SIZE",
}


#: «اسأل سيمبول» حين لا يجيب (المواصفة §4.6). السقوف في القاعدة تصل عبر CONSTRAINTS.
AI_ASSISTANT: dict[str, ErrorSpec] = {
    "AI_BUSY": ErrorSpec(503, "AI_BUSY", "سيمبول يجيب عن سؤالك السابق. انتظر قليلاً.", 30),
    "AI_UNAVAILABLE": ErrorSpec(503, "AI_UNAVAILABLE", "سيمبول غير متاح الآن. حاول بعد قليل.", 30),
    "AI_REFUSED": ErrorSpec(422, "AI_REFUSED", "لم يُجب سيمبول عن هذا السؤال. جرّب صيغةً أخرى."),
    "AI_INVALID": ErrorSpec(502, "AI_INVALID", "لم يكتمل جواب سيمبول. حاول مرةً أخرى."),
}

#: مدخلات مسارات الذكاء الاصطناعي التي تُرفض قبل أيّ استدعاء، بحقلها.
AI_INVALID: dict[str, ErrorSpec] = {
    "QUESTION": ErrorSpec(422, "QUESTION", "اكتب سؤالاً من 3 إلى 300 حرف."),
    "READY": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    "SCREEN_ID": ErrorSpec(422, "INVALID", "هذه الشاشة تحتاج معرّفاً."),
}
#: الفحص الحتمي لمسار العمل رفض الموضوع قبل المراجعة: الحقل يعود ليُفتح.
AI_REVIEW_INVALID = ErrorSpec(422, "INVALID", "في العمل ما يُصلَح قبل المراجعة.")
