"""
Referral Generator Tool
مولد خطابات الإحالة

Generates professional referral letters to 12+ specialties for
multidisciplinary vision rehabilitation management:
- Ophthalmology (طب وجراحة العيون)
- Neurology (طب الأعصاب)
- Psychiatry/Psychology (الطب النفسي)
- Pediatrics (طب الأطفال)
- Occupational Therapy (العلاج الوظيفي)
- Orientation & Mobility (التوجه والتنقل)
- Social Work (الخدمة الاجتماعية)
- Optometry (علم البصريات)
- Education (التعليم الخاص)
- Endocrinology (الغدد الصماء)
- Neurosurgery (جراحة الأعصاب)
- Geriatrics (طب كبار السن)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


# Specialty definitions
REFERRAL_SPECIALTIES = {
    "ophthalmology": {
        "arabic": "طب وجراحة العيون",
        "english": "Ophthalmology",
        "triggers": ["surgical_option", "disease_progression", "unexplained_vision_loss", "cataract", "glaucoma", "retina"],
        "urgency_indicators": ["sudden_vision_loss", "pain_with_vision_loss", "diplopia_new_onset"],
    },
    "neurology": {
        "arabic": "طب الأعصاب",
        "english": "Neurology",
        "triggers": ["homonymous_hemianopia", "visual_field_defect", "stroke_related_vision", "ms_vision", "optic_neuritis"],
        "urgency_indicators": ["sudden_field_loss", "visual_hallucinations", "papilledema"],
    },
    "psychiatry": {
        "arabic": "الطب النفسي",
        "english": "Psychiatry",
        "triggers": ["phq9_gte_15", "suicidal_ideation", "severe_depression", "anxiety_disorder"],
        "urgency_indicators": ["suicidal_ideation", "acute_psychiatric_crisis"],
    },
    "psychology": {
        "arabic": "علم النفس الإكلينيكي",
        "english": "Clinical Psychology",
        "triggers": ["phq9_5_to_14", "adjustment_disorder", "grief_counseling", "cognitive_behavioral"],
        "urgency_indicators": [],
    },
    "pediatrics": {
        "arabic": "طب الأطفال",
        "english": "Pediatrics",
        "triggers": ["patient_under_18", "cvi_assessment", "developmental_delay", "school_difficulties"],
        "urgency_indicators": ["developmental_regression", "suspected_abuse"],
    },
    "occupational_therapy": {
        "arabic": "العلاج الوظيفي",
        "english": "Occupational Therapy",
        "triggers": ["adl_impairment", "home_modification_needed", "workplace_adaptation", "fine_motor_issues"],
        "urgency_indicators": [],
    },
    "orientation_mobility": {
        "arabic": "التوجه والتنقل",
        "english": "Orientation & Mobility",
        "triggers": ["field_loss", "mobility_impairment", "cane_training", "independent_travel"],
        "urgency_indicators": [],
    },
    "social_work": {
        "arabic": "الخدمة الاجتماعية",
        "english": "Social Work",
        "triggers": ["financial_assistance", "social_isolation", "caregiver_support", "housing_needs"],
        "urgency_indicators": ["elder_abuse", "domestic_violence", "child_protection"],
    },
    "optometry": {
        "arabic": "علم البصريات",
        "english": "Optometry",
        "triggers": ["refractive_error", "spectacle_prescription", "contact_lens", "low_vision_aids_fitting"],
        "urgency_indicators": [],
    },
    "special_education": {
        "arabic": "التعليم الخاص وتكيف المناهج",
        "english": "Special Education",
        "triggers": ["school_age_child", "learning_difficulties", "braille_training", "adaptive_technology_school"],
        "urgency_indicators": [],
    },
    "endocrinology": {
        "arabic": "الغدد الصماء والسكري",
        "english": "Endocrinology",
        "triggers": ["diabetic_retinopathy", "uncontrolled_diabetes", "thyroid_eye_disease"],
        "urgency_indicators": ["rapidly_progressing_diabetic_retinopathy"],
    },
    "geriatrics": {
        "arabic": "طب كبار السن",
        "english": "Geriatrics",
        "triggers": ["patient_over_65", "falls_risk", "cognitive_impairment", "polypharmacy"],
        "urgency_indicators": ["acute_confusion", "high_falls_risk"],
    },
    "neurosurgery": {
        "arabic": "جراحة الأعصاب",
        "english": "Neurosurgery",
        "triggers": ["brain_tumor", "pituitary_adenoma", "compressive_optic_neuropathy", "hydrocephalus"],
        "urgency_indicators": ["compressive_optic_neuropathy_acute", "suspected_brain_tumor"],
    },
}

# Urgency levels
URGENCY_LEVELS = {
    "emergency": {
        "arabic": "طارئ - خلال 24 ساعة",
        "english": "Emergency - within 24 hours",
        "color": "red",
    },
    "urgent": {
        "arabic": "عاجل - خلال أسبوع",
        "english": "Urgent - within 1 week",
        "color": "orange",
    },
    "routine": {
        "arabic": "روتيني - خلال شهر",
        "english": "Routine - within 1 month",
        "color": "green",
    },
    "elective": {
        "arabic": "اختياري - حسب الأولوية",
        "english": "Elective - as appropriate",
        "color": "blue",
    },
}


def generate_referral(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for referral generation.

    Supported action values:
    - generate_letter: Generate a referral letter to a specific specialty
    - recommend_referrals: Suggest appropriate referrals based on clinical data
    - generate_all_needed: Generate all recommended referral letters

    Args:
        params: Dictionary with action and patient/clinical data

    Returns:
        Dictionary with referral letter(s) and recommendations
    """
    action = params.get("action", "recommend_referrals")

    actions = {
        "generate_letter": _generate_referral_letter,
        "recommend_referrals": _recommend_referrals,
        "generate_all_needed": _generate_all_needed_referrals,
    }

    handler = actions.get(action)
    if not handler:
        return {
            "error": f"Unknown action: {action}",
            "available_actions": list(actions.keys()),
            "available_specialties": list(REFERRAL_SPECIALTIES.keys()),
        }

    return handler(params)


def _recommend_referrals(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze clinical data and recommend appropriate referrals.
    """
    clinical_flags = params.get("clinical_flags", {})
    patient_age = params.get("patient_age", 40)
    va_decimal = params.get("va_decimal")
    phq9_score = params.get("phq9_score")
    diagnosis = params.get("diagnosis", "")
    field_loss = params.get("field_loss", False)
    adl_impaired = params.get("adl_impaired", False)
    social_needs = params.get("social_needs", False)
    is_student = params.get("is_student", False)
    has_diabetes = params.get("has_diabetes", False)

    age = int(patient_age) if str(patient_age).isdigit() else 40
    is_child = age < 18
    is_elderly = age >= 65

    recommended = []
    urgent_referrals = []

    # Auto-detect flags from structured inputs
    all_flags = dict(clinical_flags)

    if is_child:
        all_flags["patient_under_18"] = True
    if is_elderly:
        all_flags["patient_over_65"] = True
    if va_decimal and float(va_decimal) < 0.1:
        all_flags["severe_vision_loss"] = True
    if phq9_score:
        phq9 = int(phq9_score)
        if phq9 >= 15:
            all_flags["phq9_gte_15"] = True
        elif phq9 >= 5:
            all_flags["phq9_5_to_14"] = True
        if all_flags.get("suicidal_ideation"):
            all_flags["suicidal_ideation"] = True
    if field_loss:
        all_flags["field_loss"] = True
        all_flags["mobility_impairment"] = True
    if adl_impaired:
        all_flags["adl_impairment"] = True
    if social_needs:
        all_flags["social_isolation"] = True
    if is_student:
        all_flags["school_age_child"] = True
    if has_diabetes:
        all_flags["diabetic_retinopathy"] = True

    # Check each specialty
    for specialty_key, specialty_info in REFERRAL_SPECIALTIES.items():
        specialty_triggered = False
        is_urgent = False

        # Check triggers
        for trigger in specialty_info["triggers"]:
            if all_flags.get(trigger):
                specialty_triggered = True
                break

        # Check urgency indicators
        if specialty_triggered:
            for urgency_trigger in specialty_info["urgency_indicators"]:
                if all_flags.get(urgency_trigger):
                    is_urgent = True
                    break

        if specialty_triggered:
            referral_item = {
                "specialty": specialty_key,
                "specialty_arabic": specialty_info["arabic"],
                "specialty_english": specialty_info["english"],
                "urgency": "urgent" if is_urgent else "routine",
                "triggered_by": [t for t in specialty_info["triggers"] if all_flags.get(t)],
            }
            if is_urgent:
                urgent_referrals.append(referral_item)
            else:
                recommended.append(referral_item)

    # Sort by priority
    all_referrals = urgent_referrals + recommended

    return {
        "action": "recommend_referrals",
        "total_referrals_recommended": len(all_referrals),
        "urgent_referrals": urgent_referrals,
        "routine_referrals": recommended,
        "all_referrals": all_referrals,
        "flags_detected": {k: v for k, v in all_flags.items() if v},
        "priority_order": [r["specialty_arabic"] for r in all_referrals],
        "note": "يُنصح بإصدار خطابات الإحالة العاجلة فوراً والروتينية خلال الزيارة الحالية",
    }


def _generate_referral_letter(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a professional referral letter to a specific specialty.
    """
    specialty_key = params.get("specialty")
    if not specialty_key:
        return {"error": "يرجى تحديد التخصص (specialty)"}

    specialty_info = REFERRAL_SPECIALTIES.get(specialty_key)
    if not specialty_info:
        return {
            "error": f"التخصص غير معروف: {specialty_key}",
            "available_specialties": list(REFERRAL_SPECIALTIES.keys())
        }

    # Patient info
    patient_name = params.get("patient_name", "___________")
    patient_id = params.get("patient_id", "___________")
    patient_age = params.get("patient_age", "___")
    patient_gender = params.get("patient_gender", "ذكر/أنثى")
    patient_dob = params.get("patient_dob", "")

    # Referring clinician
    referring_clinician = params.get("referring_clinician", "أخصائي تأهيل بصري")
    referring_facility = params.get("referring_facility", "عيادة التأهيل البصري")
    clinician_contact = params.get("clinician_contact", "")

    # Clinical data
    diagnosis = params.get("diagnosis", "")
    va_be = params.get("va_better_eye", "")
    va_we = params.get("va_worse_eye", "")
    visual_fields = params.get("visual_fields", "")
    current_medications = params.get("current_medications", [])
    relevant_history = params.get("relevant_history", "")
    reason_for_referral = params.get("reason_for_referral", "")
    urgency = params.get("urgency", "routine")

    # Date
    today = datetime.now().strftime("%Y/%m/%d")
    hijri_note = ""  # Could add Hijri date conversion

    # Build letter content
    letter = _build_letter(
        specialty_key=specialty_key,
        specialty_info=specialty_info,
        patient_name=patient_name,
        patient_id=patient_id,
        patient_age=patient_age,
        patient_gender=patient_gender,
        patient_dob=patient_dob,
        referring_clinician=referring_clinician,
        referring_facility=referring_facility,
        clinician_contact=clinician_contact,
        diagnosis=diagnosis,
        va_be=va_be,
        va_we=va_we,
        visual_fields=visual_fields,
        current_medications=current_medications,
        relevant_history=relevant_history,
        reason_for_referral=reason_for_referral,
        urgency=urgency,
        date=today,
        additional_info=params.get("additional_info", {}),
    )

    return {
        "action": "generate_letter",
        "specialty": specialty_key,
        "specialty_arabic": specialty_info["arabic"],
        "urgency": urgency,
        "urgency_arabic": URGENCY_LEVELS[urgency]["arabic"],
        "letter_arabic": letter["arabic"],
        "letter_english": letter.get("english"),
        "generated_date": today,
        "patient_name": patient_name,
    }


def _build_letter(
    specialty_key: str,
    specialty_info: dict,
    patient_name: str,
    patient_id: str,
    patient_age,
    patient_gender: str,
    patient_dob: str,
    referring_clinician: str,
    referring_facility: str,
    clinician_contact: str,
    diagnosis: str,
    va_be: str,
    va_we: str,
    visual_fields: str,
    current_medications: list,
    relevant_history: str,
    reason_for_referral: str,
    urgency: str,
    date: str,
    additional_info: dict,
) -> dict:
    """Build the actual letter content."""

    urgency_header = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS["routine"])
    urgency_arabic = urgency_header["arabic"]

    # Build Arabic letter
    arabic_lines = [
        f"التاريخ: {date}",
        "",
        f"إلى: الزميل/الزميلة المحترم/ة",
        f"قسم/عيادة: {specialty_info['arabic']}",
        "",
        f"{'─' * 50}",
        f"[{urgency_arabic.upper()}]",
        f"{'─' * 50}",
        "",
        "الموضوع: خطاب إحالة",
        "",
        f"السلام عليكم ورحمة الله وبركاته،",
        "",
        f"أتشرف بإحالة المريض/المريضة:",
        "",
        f"  الاسم: {patient_name}",
        f"  الرقم: {patient_id}",
        f"  العمر: {patient_age} سنة",
        f"  الجنس: {patient_gender}",
    ]

    if patient_dob:
        arabic_lines.append(f"  تاريخ الميلاد: {patient_dob}")

    arabic_lines += [
        "",
        "التشخيص الرئيسي:",
        f"  {diagnosis or 'يُرجى مراجعة الملف المرفق'}",
        "",
        "الحالة البصرية:",
    ]

    if va_be:
        arabic_lines.append(f"  حدة البصر - العين الأفضل: {va_be}")
    if va_we:
        arabic_lines.append(f"  حدة البصر - العين الأضعف: {va_we}")
    if visual_fields:
        arabic_lines.append(f"  المجال البصري: {visual_fields}")

    if relevant_history:
        arabic_lines += [
            "",
            "التاريخ المرضي ذو الصلة:",
            f"  {relevant_history}",
        ]

    if current_medications:
        arabic_lines += [
            "",
            "الأدوية الحالية:",
        ]
        for med in current_medications:
            arabic_lines.append(f"  - {med}")

    # Specialty-specific reason
    if not reason_for_referral:
        reason_for_referral = _get_default_reason(specialty_key, diagnosis, va_be)

    arabic_lines += [
        "",
        "سبب الإحالة:",
        f"  {reason_for_referral}",
        "",
        "المطلوب:",
    ]

    # Specialty-specific requests
    specific_requests = _get_specialty_requests(specialty_key, additional_info)
    for req in specific_requests:
        arabic_lines.append(f"  • {req}")

    arabic_lines += [
        "",
        "يُرجى إعلامنا بنتيجة التقييم لمواصلة خطة التأهيل المتكاملة.",
        "",
        "مع جزيل الشكر والتقدير،",
        "",
        f"د. / أ. {referring_clinician}",
        f"أخصائي تأهيل بصري",
        f"المنشأة: {referring_facility}",
    ]

    if clinician_contact:
        arabic_lines.append(f"للتواصل: {clinician_contact}")

    arabic_letter = "\n".join(arabic_lines)

    # English letter (shorter, professional)
    english_lines = [
        f"Date: {date}",
        f"",
        f"To: Colleague",
        f"Department: {specialty_info['english']}",
        f"",
        f"Re: Referral Letter [{urgency.upper()}]",
        f"",
        f"Dear Colleague,",
        f"",
        f"I am referring the following patient for your evaluation:",
        f"",
        f"  Name: {patient_name}",
        f"  ID: {patient_id}",
        f"  Age: {patient_age} years",
        f"",
        f"Diagnosis: {diagnosis or 'Please refer to attached notes'}",
        f"",
    ]

    if va_be:
        english_lines.append(f"Visual Acuity (better eye): {va_be}")
    if va_we:
        english_lines.append(f"Visual Acuity (worse eye): {va_we}")

    english_lines += [
        f"",
        f"Reason for referral: {reason_for_referral}",
        f"",
        f"Requested:",
    ]
    for req in specific_requests:
        english_lines.append(f"  • {req}")

    english_lines += [
        f"",
        f"Please share your findings to coordinate rehabilitation care.",
        f"",
        f"Yours sincerely,",
        f"{referring_clinician}",
        f"Low Vision Rehabilitation Specialist",
        f"{referring_facility}",
    ]

    return {
        "arabic": arabic_letter,
        "english": "\n".join(english_lines),
    }


def _get_default_reason(specialty_key: str, diagnosis: str, va: str) -> str:
    """Get default referral reason based on specialty."""
    reasons = {
        "ophthalmology": (
            "لتقييم إمكانية التدخل الجراحي أو العلاجي وتحسين الوظيفة البصرية"
        ),
        "neurology": (
            "لتقييم سبب الاضطراب البصري العصبي وتحديد خطة العلاج المناسبة"
        ),
        "psychiatry": (
            "لتقييم وعلاج الاضطراب الاكتئابي المرتبط بفقدان البصر"
        ),
        "psychology": (
            "لتلقي الدعم النفسي والعلاج السلوكي المعرفي للتكيف مع فقدان البصر"
        ),
        "pediatrics": (
            "لتقييم التطور ومتابعة تأثير ضعف البصر على النمو والتعلم"
        ),
        "occupational_therapy": (
            "لتقييم القدرات الوظيفية وتعديل بيئة المنزل وتدريب المهارات اليومية"
        ),
        "orientation_mobility": (
            "لتدريب المريض على التنقل المستقل والآمن باستخدام العصا والتقنيات المساعدة"
        ),
        "social_work": (
            "لتقييم الاحتياجات الاجتماعية والمادية وتنسيق خدمات الدعم"
        ),
        "optometry": (
            "لإعادة تقييم وصفة النظارات وملاءمة مساعدات ضعف البصر"
        ),
        "special_education": (
            "لتقييم الاحتياجات التعليمية الخاصة ووضع خطة تعليمية مكيّفة"
        ),
        "endocrinology": (
            "لتحسين ضبط مرض السكري والحد من تقدم اعتلال الشبكية السكري"
        ),
        "geriatrics": (
            "لتقييم شامل للمسن مع التركيز على خطر السقوط والإدارة المتعددة للأمراض"
        ),
        "neurosurgery": (
            "لتقييم ضرورة التدخل الجراحي في الآفة الضاغطة على المسارات البصرية"
        ),
    }
    return reasons.get(specialty_key, "للتقييم والمتابعة المتخصصة")


def _get_specialty_requests(specialty_key: str, additional_info: dict) -> list:
    """Get specific clinical requests for each specialty."""
    requests_map = {
        "ophthalmology": [
            "تقييم إمكانية التدخل الجراحي (إزالة ساد، ليزر، حقن...)",
            "مراجعة الأدوية الحالية وفاعليتها",
            "تصوير متقدم (OCT / Visual Fields / Fluorescein Angiography) إذا لزم",
            "تقرير بالحالة وتوقعات التطور",
        ],
        "neurology": [
            "تقييم عصبي كامل مع تصوير (MRI Brain & Orbits)",
            "تخطيط كهربية الدماغ إذا لزم",
            "فحص المجال البصري الرسمي (Automated Perimetry)",
            "استشارة بشأن العلاج الدوائي المناسب",
        ],
        "psychiatry": [
            "تقييم نفسي شامل",
            "خطة علاجية (دوائية / نفسية) للاكتئاب المرتبط بفقدان البصر",
            "متابعة شهرية وإبلاغنا بالتقدم",
            "النظر في العلاج النفسي المتخصص (ACT / CBT)",
        ],
        "psychology": [
            "تقييم نفسي وتحديد مرحلة التكيف مع فقدان البصر",
            "جلسات علاج سلوكي معرفي (CBT) أو قبول والتزام (ACT)",
            "دعم مجموعي مع مرضى ضعف البصر إن أمكن",
        ],
        "pediatrics": [
            "تقييم شامل للنمو والتطور",
            "التحقق من التطعيمات والفحوص الروتينية",
            "تقييم احتمالية وجود سبب جهازي لضعف البصر",
            "التنسيق مع فريق CVI إذا أُشير إليه",
        ],
        "occupational_therapy": [
            "تقييم أنشطة الحياة اليومية (ADL Assessment)",
            "توصيات تعديل البيئة المنزلية",
            "تدريب على استخدام المساعدات التكنولوجية",
            "خطة تأهيل وظيفي مكتوبة",
        ],
        "orientation_mobility": [
            "تقييم مهارات التوجه والتنقل الحالية",
            "تدريب على استخدام العصا البيضاء",
            "تدريب على استخدام النظام (تقنيات O&M)",
            "تقييم إمكانية استخدام الكلاب المُرشدة إن لزم",
        ],
        "social_work": [
            "تقييم شامل للاحتياجات الاجتماعية والمادية",
            "المساعدة في الحصول على إعانات وخدمات الإعاقة",
            "تنسيق الدعم الأسري",
            "ربط المريض بمنظمات ضعف البصر في المجتمع",
        ],
        "optometry": [
            "إعادة تقييم الإضافة البصرية للقراءة",
            "اختبار وملاءمة مساعدات ضعف البصر (مكبرات، نظارات)",
            "تحديد أفضل تصحيح انكساري ممكن",
        ],
        "special_education": [
            "تقييم الاحتياجات التعليمية الخاصة",
            "وضع خطة IEP (Individual Education Plan)",
            "تدريب على البرايل / اللوح المكبّر / التقنيات المساعدة",
            "تنسيق مع المدرسة لتوفير البيئة التعليمية المناسبة",
        ],
        "endocrinology": [
            "مراجعة ضبط السكري وتعديل الخطة العلاجية",
            "فحص HbA1c ومستويات السكر",
            "تقييم الأمراض المصاحبة للسكري",
            "التنسيق لتقليل تقدم اعتلال الشبكية",
        ],
        "geriatrics": [
            "تقييم شامل للمسن (Comprehensive Geriatric Assessment)",
            "تقييم خطر السقوط وتدابير الوقاية",
            "مراجعة الأدوية (Polypharmacy Review)",
            "تقييم الوظيفة الإدراكية (Cognitive Assessment)",
        ],
        "neurosurgery": [
            "تقييم الحاجة للتدخل الجراحي",
            "مراجعة التصوير المقطعي / الرنين المغناطيسي",
            "تحديد التوقيت الأمثل للتدخل",
        ],
    }

    base_requests = requests_map.get(specialty_key, ["تقييم متخصص وإعداد تقرير مفصل"])

    # Add additional specific requests from params
    extra = additional_info.get("additional_requests", [])
    if extra:
        base_requests.extend(extra)

    return base_requests


def _generate_all_needed_referrals(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate all needed referral letters based on clinical assessment.
    First recommends, then generates all letters.
    """
    # Step 1: Get recommendations
    recommendations = _recommend_referrals(params)

    if recommendations.get("error"):
        return recommendations

    all_referrals = recommendations.get("all_referrals", [])

    if not all_referrals:
        return {
            "action": "generate_all_needed",
            "message": "لا توجد إحالات مطلوبة بناءً على البيانات المقدمة",
            "clinical_flags": recommendations.get("flags_detected", {}),
        }

    # Step 2: Generate each letter
    generated_letters = []
    for ref in all_referrals:
        letter_params = {
            **params,
            "specialty": ref["specialty"],
            "urgency": ref["urgency"],
        }
        letter = _generate_referral_letter(letter_params)
        generated_letters.append({
            "specialty": ref["specialty"],
            "specialty_arabic": ref["specialty_arabic"],
            "urgency": ref["urgency"],
            "urgency_arabic": ref.get("urgency_arabic", URGENCY_LEVELS[ref["urgency"]]["arabic"]),
            "letter_arabic": letter.get("letter_arabic", ""),
        })

    return {
        "action": "generate_all_needed",
        "total_referrals": len(generated_letters),
        "urgent_count": len([r for r in generated_letters if r["urgency"] == "urgent"]),
        "routine_count": len([r for r in generated_letters if r["urgency"] == "routine"]),
        "referral_letters": generated_letters,
        "summary": recommendations,
    }
