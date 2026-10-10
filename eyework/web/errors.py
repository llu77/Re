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
           "AI_REVIEW_INVALID", "INVENTORY_INVALID"]


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
    **{name: spec for name, spec in (
        # المخزون (0010): ما يقوله الصفّ المخالف بما يفعله المستخدم بعده (المواصفة §5.4).
        ("inv_needs_storekeeper", ErrorSpec(403, "PROFESSION", "هذه الأداة لبوابة مهنةٍ أخرى.")),
        ("inv_not_owner", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_count_daily_cap", ErrorSpec(409, "INV_COUNT_CAP", "فتحت عشر جلسات جردٍ اليوم، وهو الحدّ. أكمل المفتوحة أو عُد غداً.")),
        ("inv_managed_columns", ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب.")),
        ("inv_starts_as_draft", ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب.")),
        ("inv_voucher_kind", ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب.")),
        ("inv_one_document", ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب.")),
        ("inv_stale_row_version", ErrorSpec(409, "STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")),
        ("inv_document_transition", ErrorSpec(409, "STALE", "تغيّر المستند منذ عرضه. راجعه مرة أخرى.")),
        ("inv_document_not_draft", ErrorSpec(409, "INV_POSTED", "سُجّل هذا المستند، ولا يتغيّر بعد تسجيله.")),
        ("inv_document_is_final", ErrorSpec(409, "INV_FINAL", "المستند المسجَّل لا يتغيّر. التصحيح بمرتجعٍ أو بقيدٍ عكسي.")),
        ("inv_record_is_permanent", ErrorSpec(409, "INV_FINAL", "المستند المسجَّل لا يتغيّر. التصحيح بمرتجعٍ أو بقيدٍ عكسي.")),
        ("inv_reversal_needs_posted", ErrorSpec(409, "INV_FINAL", "المستند المسجَّل لا يتغيّر. التصحيح بمرتجعٍ أو بقيدٍ عكسي.")),
        ("inv_needs_settings", ErrorSpec(409, "INV_SETUP", "أجب أولاً عن سؤال ضريبة المشتريات في إعدادات المخزون.")),
        ("inv_cost_basis_locked", ErrorSpec(409, "INV_COST_BASIS_LOCKED", "لا يتغيّر هذا بعد أول تسجيل: معنى كل تكلفةٍ سابقة يتغيّر معه.")),
        ("inv_open_draft_cap", ErrorSpec(409, "INV_DRAFT_CAP", "لديك عشرون مسودةً مفتوحة. سجّل بعضها أو احذفه أولاً.")),
        ("inv_supplier_cap", ErrorSpec(409, "INV_SUPPLIER_CAP", "بلغت قائمة الموردين ألفي مورّد، وهو الحدّ.")),
        ("inv_item_cap", ErrorSpec(409, "INV_ITEM_CAP", "بلغت قائمة المنتجات خمسة آلاف، وهو الحدّ.")),
        ("inv_category_cap", ErrorSpec(409, "INV_CATEGORY_CAP", "بلغت التصنيفات خمسين، وهو الحدّ.")),
        ("inv_rep_cap", ErrorSpec(409, "INV_REP_CAP", "لهذا المورّد عشرون مندوباً، وهو الحدّ.")),
        ("inv_suppliers_name", ErrorSpec(409, "INV_SUPPLIER_EXISTS", "يوجد مورّدٌ بهذا الاسم. اختره من القائمة.")),
        ("inv_items_name", ErrorSpec(409, "INV_ITEM_EXISTS", "يوجد منتجٌ بهذا الاسم. اختره من القائمة.")),
        ("inv_items_barcode", ErrorSpec(409, "INV_BARCODE_EXISTS", "هذا الباركود لمنتجٍ آخر.")),
        ("inv_categories_name", ErrorSpec(409, "INV_CATEGORY_EXISTS", "يوجد تصنيفٌ بهذا الاسم.")),
        ("inv_supplier_reps_name", ErrorSpec(409, "INV_REP_EXISTS", "لهذا المورّد مندوبٌ بهذا الاسم.")),
        ("inv_supplier_name_shape", ErrorSpec(422, "INV_NAME", "الاسم من حرفٍ إلى ستين، في سطرٍ واحد.")),
        ("inv_item_name_shape", ErrorSpec(422, "INV_NAME", "الاسم من حرفٍ إلى ستين، في سطرٍ واحد.")),
        ("inv_rep_name_shape", ErrorSpec(422, "INV_NAME", "الاسم من حرفٍ إلى ستين، في سطرٍ واحد.")),
        ("inv_category_name_shape", ErrorSpec(422, "INV_NAME", "اسم التصنيف من حرفٍ إلى أربعين، في سطرٍ واحد.")),
        ("inv_store_name_shape", ErrorSpec(422, "INV_NAME", "اسم المخزن من حرفٍ إلى ستين، في سطرٍ واحد.")),
        ("inv_store_location_shape", ErrorSpec(422, "INV_NOTE", "موقع المخزن حتى مئةٍ وعشرين حرفاً، في سطرٍ واحد.")),
        ("inv_supplier_vat_shape", ErrorSpec(422, "INV_VAT_NUMBER", "الرقم الضريبي خمس عشرة خانة، أولها وآخرها 3.")),
        ("inv_supplier_cr_shape", ErrorSpec(422, "INV_CR_NUMBER", "رقم السجل التجاري عشر خانات.")),
        ("inv_supplier_phone_shape", ErrorSpec(422, "INV_PHONE", "رقم الهاتف كما يُكتب: 05xxxxxxxx أو +9665xxxxxxxx.")),
        ("inv_rep_mobile_shape", ErrorSpec(422, "INV_PHONE", "رقم الجوال كما يُكتب: 05xxxxxxxx أو +9665xxxxxxxx.")),
        ("inv_item_code_shape", ErrorSpec(422, "INV_CODE", "رمز المورّد حروفٌ لاتينية وأرقام، حتى عشرين.")),
        ("inv_item_barcode_shape", ErrorSpec(422, "INV_BARCODE", "الباركود أرقامٌ فقط: 8 أو 12 إلى 14 رقماً.")),
        ("inv_item_exemption_shape", ErrorSpec(422, "INV_NOTE", "سبب الإعفاء حتى ثمانين حرفاً، في سطرٍ واحد.")),
        ("inv_item_exemption_needs_category", ErrorSpec(422, "INV_EXEMPTION", "سبب الإعفاء لغير الفئة الأساسية.")),
        ("inv_item_price_range", ErrorSpec(422, "INV_PRICE", "السعر من صفرٍ إلى عشرة ملايين ريال، وسعر المنتج أكبر من صفر.")),
        ("inv_item_selling_range", ErrorSpec(422, "INV_PRICE", "سعر البيع من صفرٍ إلى عشرة ملايين ريال.")),
        ("inv_line_price_range", ErrorSpec(422, "INV_PRICE", "السعر من صفرٍ إلى عشرة ملايين ريال.")),
        ("inv_voucher_cost_range", ErrorSpec(422, "INV_PRICE", "تكلفة الوحدة من صفرٍ إلى عشرة ملايين ريال.")),
        ("inv_count_line_cost_range", ErrorSpec(422, "INV_PRICE", "تكلفة الوحدة من صفرٍ إلى عشرة ملايين ريال.")),
        ("inv_item_reorder_shape", ErrorSpec(422, "INV_REORDER", "حدّ الطلب كميةٌ بوحدة المنتج.")),
        ("inv_item_target_shape", ErrorSpec(422, "INV_TARGET", "الكمية المستهدفة بوحدة المنتج، ولا تقلّ عن حدّ الطلب.")),
        ("inv_item_unit_matches_kind", ErrorSpec(422, "INV_UNIT", "وحدة الخدمة «خدمة»، ووحدة المنتج المخزَّن غيرها.")),
        ("inv_item_service_has_no_stock", ErrorSpec(422, "INV_UNIT", "الخدمة بلا رصيدٍ ولا باركود ولا حدّ طلب.")),
        ("inv_item_unit_locked", ErrorSpec(409, "INV_UNIT_LOCKED", "وحدة المنتج لا تتغيّر بعد استعماله. أنشئ منتجاً بالوحدة الصحيحة.")),
        ("inv_item_has_stock", ErrorSpec(409, "INV_ITEM_HAS_STOCK", "في المنتج رصيد. اصرفه أو صحّحه بالجرد قبل أرشفته.")),
        ("inv_item_archived", ErrorSpec(409, "INV_ITEM_ARCHIVED", "المنتج مؤرشف. أعِد تفعيله أو اختر غيره.")),
        ("inv_supplier_archived", ErrorSpec(409, "INV_SUPPLIER_ARCHIVED", "المورّد مؤرشف أو غير موجود. أعِد تفعيله أو اختر غيره.")),
        ("inv_category_archived", ErrorSpec(409, "INV_CATEGORY_ARCHIVED", "التصنيف مؤرشف أو غير موجود. أعِد تفعيله أو اختر غيره.")),
        ("inv_rep_not_of_supplier", ErrorSpec(409, "INV_REP", "المندوب ليس من مندوبي هذا المورّد. اختر مندوباً من قائمته.")),
        ("inv_purchase_no_shape", ErrorSpec(422, "INV_DOC_NO", "رقم المستند حروفٌ وأرقام وفواصل بسيطة، حتى أربعين.")),
        ("inv_purchase_delivery_note_shape", ErrorSpec(422, "INV_DOC_NO", "رقم سند التسليم حروفٌ وأرقام وفواصل بسيطة، حتى أربعين.")),
        ("inv_return_credit_note_shape", ErrorSpec(422, "INV_DOC_NO", "رقم المستند حروفٌ وأرقام وفواصل بسيطة، حتى أربعين.")),
        ("inv_purchase_date_floor", ErrorSpec(422, "INV_DATE", "التاريخ غير صحيح.")),
        ("inv_purchase_received_floor", ErrorSpec(422, "INV_DATE", "تاريخ الاستلام غير صحيح.")),
        ("inv_purchase_printed_total", ErrorSpec(422, "INV_AMOUNT", "المبلغ غير صحيح.")),
        ("inv_purchase_printed_vat", ErrorSpec(422, "INV_AMOUNT", "المبلغ غير صحيح.")),
        ("inv_purchase_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_return_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_voucher_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_count_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_count_line_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_supplier_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_item_note_shape", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_purchase_reversal_note", ErrorSpec(422, "INV_NOTE", "الملاحظة من حرفٍ إلى مئتين، في سطرٍ واحد.")),
        ("inv_line_cap", ErrorSpec(409, "INV_LINE_CAP", "في المستند أربعون سطراً، وهو الحدّ. سجّل الباقي في مستندٍ ثانٍ.")),
        ("inv_quantity_unit", ErrorSpec(422, "INV_QUANTITY", "الكمية بالعدد الصحيح للقطعة والكرتون ونحوهما، وبثلاث خاناتٍ عشرية للوزن والحجم والطول.")),
        ("inv_line_quantity_range", ErrorSpec(422, "INV_QUANTITY", "الكمية أكبر من صفر.")),
        ("inv_line_received_range", ErrorSpec(422, "INV_RECEIVED", "الكمية المستلمة من صفرٍ إلى كمية الفاتورة.")),
        ("inv_return_line_quantity_range", ErrorSpec(422, "INV_QUANTITY", "الكمية أكبر من صفر.")),
        ("inv_voucher_quantity_range", ErrorSpec(422, "INV_QUANTITY", "الكمية غير صحيحة.")),
        ("inv_count_line_counted_range", ErrorSpec(422, "INV_QUANTITY", "المعدود صفرٌ فأكثر.")),
        ("inv_line_discount_exceeds", ErrorSpec(422, "INV_DISCOUNT", "الخصم من صفرٍ إلى مبلغ السطر.")),
        ("inv_line_discount_range", ErrorSpec(422, "INV_DISCOUNT", "الخصم من صفرٍ إلى مبلغ السطر.")),
        ("inv_purchase_lines_purchase_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_purchase_lines_item_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_return_lines_return_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_return_lines_purchase_id_line_no_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_movements_item_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المنتج أو المستند.")),
        ("inv_purchases_supplier_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المورّد.")),
        ("inv_purchases_rep_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المندوب.")),
        ("inv_returns_rep_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المندوب.")),
        ("inv_returns_purchase_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على الفاتورة.")),
        ("inv_items_category_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على التصنيف.")),
        ("inv_items_preferred_supplier_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المورّد.")),
        ("inv_supplier_reps_supplier_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على المورّد.")),
        ("inv_count_sessions_category_id_user_id_fkey", ErrorSpec(404, "NOT_FOUND", "لم يُعثر على التصنيف.")),
        ("inv_purchase_incomplete", ErrorSpec(422, "INV_INCOMPLETE", "ينقص الفاتورة ما يلزم لتسجيلها: المورّد، ورقم فاتورته، وتاريخها، وإجماليها المطبوع.")),
        ("inv_purchase_future_date", ErrorSpec(422, "INV_FUTURE_DATE", "تاريخ الفاتورة أو الاستلام لم يأتِ بعد بتوقيت الرياض.")),
        ("inv_purchase_no_lines", ErrorSpec(422, "INV_NO_LINES", "أضف سطراً واحداً على الأقل.")),
        ("inv_return_no_lines", ErrorSpec(422, "INV_NO_LINES", "أضف سطراً واحداً على الأقل.")),
        ("inv_flags_unacknowledged", ErrorSpec(409, "FLAGS_CHANGED", "تغيّرت التنبيهات منذ عرضها. راجعها ثم سجّل.")),
        ("inv_return_needs_posted_purchase", ErrorSpec(409, "INV_RETURN_SOURCE", "المرتجع من فاتورةٍ مسجّلة لم تُعكس.")),
        ("inv_return_exceeds_remaining", ErrorSpec(422, "INV_RETURN_QTY", "الكمية أكبر ممّا بقي من هذا السطر بعد المرتجعات السابقة.")),
        ("inv_return_needs_reason", ErrorSpec(422, "INV_RETURN_REASON", "اختر سبب الإرجاع.")),
        ("inv_return_reason", ErrorSpec(422, "INV_RETURN_REASON", "اختر سبب الإرجاع من القائمة.")),
        ("inv_return_needs_note", ErrorSpec(422, "INV_REASON_NOTE", "مع «سببٌ آخر» اكتب السبب في الملاحظة.")),
        ("inv_reversal_needs_note", ErrorSpec(422, "INV_REASON_NOTE", "مع «سببٌ آخر» اكتب السبب في الملاحظة.")),
        ("inv_count_needs_note", ErrorSpec(422, "INV_REASON_NOTE", "مع «سببٌ آخر» اكتب السبب في الملاحظة.")),
        ("inv_voucher_needs_note", ErrorSpec(422, "INV_REASON_NOTE", "مع «سببٌ آخر» اكتب السبب في الملاحظة.")),
        ("inv_voucher_needs_reason", ErrorSpec(422, "INV_REASON", "اختر سبب الصرف من القائمة.")),
        ("inv_return_date", ErrorSpec(422, "INV_RETURN_DATE", "تاريخ المرتجع بين تاريخ الفاتورة واليوم.")),
        ("inv_credit_note_date", ErrorSpec(422, "INV_CREDIT_NOTE_DATE", "تاريخ الإشعار الدائن بين تاريخ الفاتورة واليوم.")),
        ("inv_return_credit_note_complete", ErrorSpec(422, "INV_CREDIT_NOTE", "رقم الإشعار الدائن وتاريخه معاً.")),
        ("inv_negative_stock", ErrorSpec(409, "INV_STOCK", "الرصيد لا يكفي: صُرف من المنتج أو أُرجع منه بعد ذلك. صحّح الرصيد بالجرد أولاً إن كان خطأً.")),
        ("inv_movement_needs_stock_item", ErrorSpec(422, "INV_SERVICE", "الخدمة لا رصيد لها.")),
        ("inv_reversal_needs_reason", ErrorSpec(422, "INV_REVERSAL_REASON", "اختر سبب القيد العكسي.")),
        ("inv_reversal_has_returns", ErrorSpec(409, "INV_REVERSAL_RETURNS", "من هذه الفاتورة مرتجعات، فلا تُعكس. سجّل مرتجعاً بما بقي منها.")),
        ("inv_voucher_date", ErrorSpec(422, "INV_VOUCHER_DATE", "تاريخ السند في الثلاثين يوماً الأخيرة.")),
        ("inv_count_stale", ErrorSpec(409, "INV_COUNT_STALE", "تغيّر رصيد المنتج منذ بدء الجرد. حدّث الأرصدة وأعِد العدّ.")),
        ("inv_count_needs_cost", ErrorSpec(422, "INV_COST", "لا رصيد يُحسب منه متوسط. اكتب تكلفة الوحدة.")),
        ("inv_count_needs_reason", ErrorSpec(422, "INV_COUNT_REASON", "اختر سبب الفرق بين المعدود والرصيد.")),
        ("inv_count_reason_direction", ErrorSpec(422, "INV_COUNT_REASON", "السبب لا يناسب اتجاه الفرق: للعجز أسبابه وللزيادة أسبابها.")),
        ("inv_count_line_reason_needed", ErrorSpec(422, "INV_COUNT_REASON", "السبب يناسب اتجاه الفرق، ولا سبب بلا فرق.")),
        ("inv_count_line_reason", ErrorSpec(422, "INV_COUNT_REASON", "اختر سبب الفرق من القائمة.")),
        ("inv_count_session_open", ErrorSpec(409, "INV_COUNT_OPEN", "لديك جلسة جردٍ مفتوحة. أكملها أو ألغِها أولاً.")),
        ("inv_count_sessions_open", ErrorSpec(409, "INV_COUNT_OPEN", "لديك جلسة جردٍ مفتوحة. أكملها أو ألغِها أولاً.")),
        ("inv_count_line_uncounted", ErrorSpec(422, "INV_COUNT_REASON", "اكتب العدد أولاً: السبب لسطرٍ معدود.")),
        ("inv_count_not_open", ErrorSpec(409, "INV_COUNT_CLOSED", "انتهت هذه الجلسة، ولا تتغيّر.")),
        ("inv_count_scope", ErrorSpec(422, "INV_COUNT_SCOPE", "اختر نطاق الجرد: الكل، أو تصنيفاً، أو ما تحت حدّ الطلب، أو منتجاتٍ بعينها.")),
        ("inv_count_no_items", ErrorSpec(422, "INV_COUNT_EMPTY", "لا منتجات في هذا النطاق.")),
        ("inv_count_line_exists", ErrorSpec(409, "INV_COUNT_LINE_EXISTS", "هذا المنتج في الكشف من قبل.")),
        ("inv_count_nothing_counted", ErrorSpec(422, "INV_COUNT_NOTHING", "لم يُعدّ شيءٌ بعد. اكتب المعدود لسطرٍ واحد على الأقل.")),
        ("inv_opening_not_first", ErrorSpec(409, "INV_OPENING", "الرصيد الافتتاحي لمنتجٍ بلا حركاتٍ سابقة، وبتكلفة وحدته.")),
        ("inv_counter_range", ErrorSpec(409, "INV_NUMBER_CAP", "بلغ ترقيم هذا النوع من المستندات حدّه.")),
    )},
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

#: ما ترفضه خدمة المخزون قبل القاعدة (`service_errors.Invalid`)، بحقله.
INVENTORY_INVALID: dict[str, ErrorSpec] = {
    "INCOMPLETE": CONSTRAINTS["inv_purchase_incomplete"],
    "PAGE": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    "FILTER": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    "STATUS": ErrorSpec(422, "INVALID", "قيمةٌ غير صالحة في الطلب."),
    "INV_DATE": ErrorSpec(422, "INV_DATE", "التاريخ غير صحيح: سنة-شهر-يوم."),
    "INV_PERIOD": ErrorSpec(422, "INV_PERIOD", "الفترة من يومٍ إلى آخر بعده، في سنةٍ على الأكثر."),
    "INV_NO_LINES": ErrorSpec(422, "INV_NO_LINES", "أضف سطراً واحداً على الأقل."),
    "INV_RETURN_REASON": ErrorSpec(422, "INV_RETURN_REASON", "اختر سبب الإرجاع."),
}
