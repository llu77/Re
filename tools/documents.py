"""
Document Generator — مولد الوثائق الطبية
==========================================
إنشاء تقارير SOAP، خطط علاجية، ملخصات حالة، خطابات إحالة
يتطلب موافقة مسبقة من المستخدم قبل إنشاء أي وثيقة
"""

from datetime import datetime


def generate_medical_document(params: dict) -> dict:
    """
    إنشاء وثيقة طبية منسقة

    Args:
        params: {
            document_type: نوع الوثيقة
            content: بيانات الوثيقة
            format: "markdown" | "text"
            consent_confirmed: True (يجب أن يكون True)
        }
    """
    document_type = params.get("document_type", "")
    content = params.get("content", {})
    fmt = params.get("format", "markdown")

    if not document_type:
        return {"error": "يجب تحديد نوع الوثيقة"}

    if not content:
        return {"error": "محتوى الوثيقة فارغ"}

    generators = {
        "assessment_report": _generate_assessment_report,
        "treatment_plan": _generate_treatment_plan,
        "case_summary": _generate_case_summary,
        "referral_letter": _generate_referral_letter,
        "progress_note": _generate_progress_note,
        "school_report": _generate_school_report,
    }

    if document_type not in generators:
        return {
            "error": f"نوع الوثيقة '{document_type}' غير مدعوم",
            "supported_types": list(generators.keys())
        }

    document_text = generators[document_type](content, fmt)

    return {
        "document_type": document_type,
        "format": fmt,
        "document": document_text,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "disclaimer": "⚠️ هذه الوثيقة أُنشئت بمساعدة الذكاء الاصطناعي وتتطلب مراجعة من متخصص مؤهل قبل الاستخدام الرسمي."
    }


# ─────────────────────────────────────────────
# 1. تقرير التقييم
# ─────────────────────────────────────────────

def _generate_assessment_report(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    patient_name = content.get("patient_name", "[اسم المريض]")
    patient_age = content.get("patient_age", "[العمر]")
    diagnosis = content.get("diagnosis", "[التشخيص]")
    va_right = content.get("va_right", "[VA العين اليمنى]")
    va_left = content.get("va_left", "[VA العين اليسرى]")
    visual_field = content.get("visual_field", "[المجال البصري]")
    contrast_sensitivity = content.get("contrast_sensitivity", "[حساسية التباين]")
    functional_limitations = content.get("functional_limitations", "[القيود الوظيفية]")
    patient_goals = content.get("patient_goals", "[أهداف المريض]")
    recommendations = content.get("recommendations", "[التوصيات]")
    assessor = content.get("assessor", "[المُقيِّم]")

    if fmt == "markdown":
        return f"""# تقرير التقييم البصري الوظيفي

**التاريخ:** {date_str}
**المريض:** {patient_name} | **العمر:** {patient_age}
**المُقيِّم:** {assessor}

---

## 1. التشخيص الطبي
{diagnosis}

---

## 2. نتائج الفحص البصري

| الفحص | العين اليمنى | العين اليسرى |
|-------|-------------|-------------|
| حدة الإبصار (مع تصحيح) | {va_right} | {va_left} |

**المجال البصري:** {visual_field}
**حساسية التباين:** {contrast_sensitivity}

---

## 3. التقييم الوظيفي
{functional_limitations}

---

## 4. أهداف المريض
{patient_goals}

---

## 5. التوصيات
{recommendations}

---

> ⚠️ **تنبيه:** هذا تقرير مساعد وليس بديلاً عن التشخيص الطبي المباشر.
"""
    else:
        return f"""تقرير التقييم البصري الوظيفي
التاريخ: {date_str}
المريض: {patient_name} | العمر: {patient_age}
المقيّم: {assessor}

التشخيص: {diagnosis}

نتائج الفحص:
- حدة الإبصار اليمنى: {va_right}
- حدة الإبصار اليسرى: {va_left}
- المجال البصري: {visual_field}
- حساسية التباين: {contrast_sensitivity}

التقييم الوظيفي: {functional_limitations}
أهداف المريض: {patient_goals}
التوصيات: {recommendations}

تنبيه: هذا تقرير مساعد وليس بديلاً عن التشخيص الطبي المباشر.
"""


# ─────────────────────────────────────────────
# 2. خطة العلاج
# ─────────────────────────────────────────────

def _generate_treatment_plan(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    patient_name = content.get("patient_name", "[اسم المريض]")
    diagnosis = content.get("diagnosis", "[التشخيص]")
    short_term_goals = content.get("short_term_goals", "[الأهداف قصيرة المدى]")
    medium_term_goals = content.get("medium_term_goals", "[الأهداف متوسطة المدى]")
    long_term_goals = content.get("long_term_goals", "[الأهداف طويلة المدى]")
    interventions = content.get("interventions", "[التدخلات]")
    devices = content.get("devices", "[الأجهزة المساعدة]")
    schedule = content.get("schedule", "[الجدول الزمني]")
    success_criteria = content.get("success_criteria", "[معايير النجاح]")
    follow_up = content.get("follow_up", "[خطة المتابعة]")

    if fmt == "markdown":
        return f"""# خطة التأهيل البصري

**التاريخ:** {date_str}
**المريض:** {patient_name}
**التشخيص:** {diagnosis}

---

## الأهداف (SMART Goals)

### قصيرة المدى (1-4 أسابيع)
{short_term_goals}

### متوسطة المدى (1-3 أشهر)
{medium_term_goals}

### طويلة المدى (3-12 شهر)
{long_term_goals}

---

## التدخلات المخططة
{interventions}

### الأجهزة المساعدة الموصى بها
{devices}

---

## الجدول الزمني
{schedule}

---

## معايير النجاح
{success_criteria}

---

## خطة المتابعة
{follow_up}

---

> ⚠️ تتطلب هذه الخطة مراجعة دورية وتعديل حسب تقدم المريض.
"""
    else:
        return f"""خطة التأهيل البصري
التاريخ: {date_str} | المريض: {patient_name}
التشخيص: {diagnosis}

الأهداف قصيرة المدى: {short_term_goals}
الأهداف متوسطة المدى: {medium_term_goals}
الأهداف طويلة المدى: {long_term_goals}

التدخلات: {interventions}
الأجهزة: {devices}
الجدول: {schedule}
معايير النجاح: {success_criteria}
المتابعة: {follow_up}
"""


# ─────────────────────────────────────────────
# 3. ملخص الحالة (SOAP Note)
# ─────────────────────────────────────────────

def _generate_case_summary(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    subjective = content.get("subjective", "[شكوى المريض وتاريخ الحالة]")
    objective = content.get("objective", "[نتائج الفحوصات والقياسات]")
    assessment = content.get("assessment", "[التحليل والتفسير السريري]")
    plan = content.get("plan", "[الخطة العلاجية]")
    patient_name = content.get("patient_name", "[اسم المريض]")

    if fmt == "markdown":
        return f"""# ملخص الحالة — SOAP Note

**التاريخ:** {date_str}
**المريض:** {patient_name}

---

## S — Subjective (ذاتي)
{subjective}

---

## O — Objective (موضوعي)
{objective}

---

## A — Assessment (التقييم)
{assessment}

---

## P — Plan (الخطة)
{plan}

---

> ⚠️ هذا ملخص مساعد. القرار النهائي للمتخصص المعالج.
"""
    else:
        return f"""SOAP Note - {date_str}
المريض: {patient_name}

S: {subjective}
O: {objective}
A: {assessment}
P: {plan}
"""


# ─────────────────────────────────────────────
# 4. خطاب الإحالة
# ─────────────────────────────────────────────

def _generate_referral_letter(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    referring_clinician = content.get("referring_clinician", "[اسم المُحيل]")
    referred_to = content.get("referred_to", "[الجهة المُحال إليها]")
    patient_name = content.get("patient_name", "[اسم المريض]")
    patient_dob = content.get("patient_dob", "[تاريخ الميلاد]")
    reason_for_referral = content.get("reason_for_referral", "[سبب الإحالة]")
    clinical_summary = content.get("clinical_summary", "[ملخص سريري]")
    urgency = content.get("urgency", "روتيني")

    if fmt == "markdown":
        return f"""# خطاب إحالة

**التاريخ:** {date_str}
**من:** {referring_clinician}
**إلى:** {referred_to}

---

**المريض:** {patient_name}
**تاريخ الميلاد:** {patient_dob}
**درجة الاستعجال:** {urgency}

---

## سبب الإحالة
{reason_for_referral}

---

## الملخص السريري
{clinical_summary}

---

يرجى تقييم هذا المريض وإخبارنا بنتيجة التقييم والخطة العلاجية.

شاكراً تعاونكم،
**{referring_clinician}**

---

> ⚠️ هذا الخطاب لأغراض استشارية ويجب مراجعته من الطبيب المعالج.
"""
    else:
        return f"""خطاب إحالة
التاريخ: {date_str}
من: {referring_clinician} | إلى: {referred_to}
المريض: {patient_name} | تاريخ الميلاد: {patient_dob}
الاستعجال: {urgency}

سبب الإحالة: {reason_for_referral}
الملخص السريري: {clinical_summary}

{referring_clinician}
"""


# ─────────────────────────────────────────────
# 5. مذكرة التقدم
# ─────────────────────────────────────────────

def _generate_progress_note(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    patient_name = content.get("patient_name", "[اسم المريض]")
    session_number = content.get("session_number", "[رقم الجلسة]")
    goals_addressed = content.get("goals_addressed", "[الأهداف التي تم تناولها]")
    progress_observed = content.get("progress_observed", "[التقدم الملاحظ]")
    challenges = content.get("challenges", "[التحديات]")
    next_session_plan = content.get("next_session_plan", "[خطة الجلسة القادمة]")
    clinician = content.get("clinician", "[الأخصائي]")

    if fmt == "markdown":
        return f"""# مذكرة تقدم

**التاريخ:** {date_str}
**المريض:** {patient_name}
**الجلسة رقم:** {session_number}
**الأخصائي:** {clinician}

---

## الأهداف التي تم تناولها
{goals_addressed}

---

## التقدم الملاحظ
{progress_observed}

---

## التحديات والملاحظات
{challenges}

---

## خطة الجلسة القادمة
{next_session_plan}

---

**توقيع الأخصائي:** {clinician}
**التاريخ:** {date_str}
"""
    else:
        return f"""مذكرة تقدم - {date_str}
المريض: {patient_name} | الجلسة: {session_number}
الأخصائي: {clinician}

الأهداف: {goals_addressed}
التقدم: {progress_observed}
التحديات: {challenges}
الجلسة القادمة: {next_session_plan}
"""


# ─────────────────────────────────────────────
# 6. تقرير المدرسة (للحالات البيدياترية)
# ─────────────────────────────────────────────

def _generate_school_report(content: dict, fmt: str) -> str:
    date_str = datetime.now().strftime("%Y/%m/%d")

    student_name = content.get("student_name", "[اسم الطالب]")
    student_age = content.get("student_age", "[العمر]")
    grade = content.get("grade", "[الصف الدراسي]")
    school_name = content.get("school_name", "[اسم المدرسة]")
    diagnosis = content.get("diagnosis", "[التشخيص البصري]")

    va_right = content.get("va_right", "[VA اليمنى]")
    va_left = content.get("va_left", "[VA اليسرى]")
    visual_field = content.get("visual_field", "[المجال البصري]")
    contrast_sensitivity = content.get("contrast_sensitivity", "[حساسية التباين]")

    functional_impact = content.get("functional_impact", "[تأثير ضعف البصر على الأداء الدراسي]")
    reading_ability = content.get("reading_ability", "[قدرات القراءة والكتابة]")

    classroom_accommodations = content.get("classroom_accommodations", [
        "الجلوس في الصف الأول",
        "تكبير المواد المطبوعة",
        "وقت إضافي للاختبارات",
    ])
    assistive_devices = content.get("assistive_devices", "[الأجهزة المساعدة الموصى بها]")

    iep_goals = content.get("iep_goals", "[أهداف خطة التعليم الفردية]")
    specialist_name = content.get("specialist_name", "[اسم أخصائي التأهيل]")
    next_review = content.get("next_review", "[تاريخ المراجعة القادمة]")

    # Format accommodations list
    if isinstance(classroom_accommodations, list):
        accommodations_text = "\n".join(f"- {a}" for a in classroom_accommodations)
    else:
        accommodations_text = str(classroom_accommodations)

    if fmt == "markdown":
        return f"""# تقرير التأهيل البصري للطالب

**التاريخ:** {date_str}
**الطالب:** {student_name} | **العمر:** {student_age} | **الصف:** {grade}
**المدرسة:** {school_name}
**الأخصائي:** {specialist_name}

---

## 1. التشخيص البصري
{diagnosis}

---

## 2. نتائج الفحص البصري

| الفحص | العين اليمنى | العين اليسرى |
|-------|-------------|-------------|
| حدة الإبصار (مع تصحيح) | {va_right} | {va_left} |

**المجال البصري:** {visual_field}
**حساسية التباين:** {contrast_sensitivity}

---

## 3. الأثر على الأداء الدراسي
{functional_impact}

**قدرات القراءة والكتابة:**
{reading_ability}

---

## 4. التسهيلات الصفية الموصى بها
{accommodations_text}

---

## 5. الأجهزة المساعدة الموصى بها
{assistive_devices}

---

## 6. أهداف خطة التعليم الفردية (IEP Goals)
{iep_goals}

---

## 7. التوصيات للمعلمين والإدارة

- تزويد الطالب بنسخ رقمية من الكتب المدرسية
- التأكد من الإضاءة الكافية في مقعد الطالب
- السماح باستخدام الأجهزة المساعدة داخل الفصل
- تقديم الاختبارات بصيغة مكبّرة أو رقمية
- إخطار المعلمين الجدد باحتياجات الطالب في كل فصل دراسي

---

## 8. موعد المراجعة القادمة
{next_review}

---

**للتواصل مع أخصائي التأهيل البصري بشأن أي استفسارات متعلقة بالطالب**

---

> ⚠️ **تنبيه:** هذا التقرير أُعدّ بمساعدة الذكاء الاصطناعي ويتطلب مراجعة وتوقيع الأخصائي المعالج قبل الاستخدام الرسمي.
"""
    else:
        return f"""تقرير التأهيل البصري للطالب
التاريخ: {date_str}
الطالب: {student_name} | العمر: {student_age} | الصف: {grade}
المدرسة: {school_name}
الأخصائي: {specialist_name}

التشخيص: {diagnosis}

نتائج الفحص:
- حدة الإبصار اليمنى: {va_right}
- حدة الإبصار اليسرى: {va_left}
- المجال البصري: {visual_field}
- حساسية التباين: {contrast_sensitivity}

الأثر على الأداء الدراسي: {functional_impact}

التسهيلات الصفية:
{accommodations_text}

الأجهزة المساعدة: {assistive_devices}

أهداف IEP: {iep_goals}

موعد المراجعة: {next_review}

تنبيه: هذا التقرير يتطلب مراجعة الأخصائي المعالج.
"""
