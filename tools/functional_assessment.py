"""
Functional Assessment Tool — نظام التقييم الوظيفي الشامل
==========================================================
5 مراحل: التاريخ → السريري → الوظيفي → النفسي → التصنيف
"""

import math
from typing import Optional


def run_functional_assessment(params: dict) -> dict:
    """
    تنفيذ التقييم الوظيفي بناءً على المرحلة والبيانات المُدخلة

    Args:
        params: {
            phase: [history | clinical_vision | functional | psychological | classification | full]
            data: {بيانات الفحص}
            calculate: [قائمة الحسابات المطلوبة] (اختياري)
        }
    """
    phase = params.get("phase", "classification")
    data = params.get("data", {})
    calculations = params.get("calculate", [])

    handlers = {
        "history":        _assess_history,
        "clinical_vision": _assess_clinical_vision,
        "functional":     _assess_functional,
        "psychological":  _assess_psychological,
        "classification": _assess_classification,
        "full":           _assess_full,
    }

    if phase not in handlers:
        return {
            "error": f"مرحلة التقييم '{phase}' غير معروفة",
            "valid_phases": list(handlers.keys())
        }

    result = handlers[phase](data)

    # إضافة الحسابات المطلوبة
    if calculations and "clinical_data" in data:
        result["calculations"] = _run_calculations(data, calculations)

    return result


# ─────────────────────────────────────────────
# المرحلة 1: التاريخ المرضي
# ─────────────────────────────────────────────

def _assess_history(data: dict) -> dict:
    """تحليل وتنظيم التاريخ المرضي"""

    diagnosis = data.get("diagnosis", "")
    onset = data.get("onset", "")
    stability = data.get("stability", "")
    medications = data.get("medications", [])
    comorbidities = data.get("comorbidities", [])
    chief_complaint = data.get("chief_complaint", "")
    goals = data.get("goals", [])
    occupation = data.get("occupation", "")
    living_situation = data.get("living_situation", "")
    age = data.get("age")

    flags = []

    # فحص العوامل ذات الأولوية
    high_risk_conditions = ["diabetes", "سكري", "stroke", "جلطة", "tbi", "إصابة رأس"]
    for cond in comorbidities:
        if any(h in cond.lower() for h in high_risk_conditions):
            flags.append(f"⚠️ حالة مصاحبة عالية الأهمية: {cond}")

    anti_vegf_meds = ["bevacizumab", "ranibizumab", "aflibercept", "اللقاح", "حقن"]
    for med in medications:
        if any(m in med.lower() for m in anti_vegf_meds):
            flags.append(f"📌 مريض يتلقى حقن Anti-VEGF — تنسيق مواعيد التأهيل مع الحقن")

    if age and int(age) >= 65:
        flags.append("👴 كبير السن — تقييم الحالة المعرفية والتوازن")

    # تحديد أولويات من الشكاوى والأهداف
    priorities = _extract_priorities(chief_complaint, goals)

    return {
        "phase": "history",
        "summary": {
            "diagnosis": diagnosis,
            "onset_type": onset,
            "stability": stability,
            "priority_complaints": priorities,
            "goals": goals,
            "occupation": occupation,
            "living_situation": living_situation,
        },
        "flags": flags,
        "missing_info": _identify_missing_history(data),
        "recommended_next": "clinical_vision"
    }


def _extract_priorities(complaint: str, goals: list) -> list:
    """استخلاص الأولويات الوظيفية"""
    priorities = []
    keywords = {
        "قراءة": "القراءة والكتابة",
        "reading": "القراءة والكتابة",
        "تنقل": "التنقل والتوجه",
        "mobility": "التنقل والتوجه",
        "طبخ": "مهارات المطبخ",
        "cooking": "مهارات المطبخ",
        "هاتف": "استخدام الأجهزة الرقمية",
        "phone": "استخدام الأجهزة الرقمية",
        "وجوه": "تمييز الوجوه والناس",
        "face": "تمييز الوجوه والناس",
    }
    text = (complaint + " " + " ".join(goals)).lower()
    seen = set()
    for kw, priority in keywords.items():
        if kw in text and priority not in seen:
            priorities.append(priority)
            seen.add(priority)
    return priorities or ["تحديد الأولويات يتطلب مزيداً من المعلومات"]


def _identify_missing_history(data: dict) -> list:
    """تحديد المعلومات المفقودة من التاريخ"""
    required = {
        "diagnosis": "التشخيص الطبي",
        "age": "العمر",
        "chief_complaint": "الشكوى الرئيسية",
        "goals": "أهداف المريض",
        "medications": "الأدوية الحالية",
    }
    missing = []
    for field, label in required.items():
        if not data.get(field):
            missing.append(label)
    return missing


# ─────────────────────────────────────────────
# المرحلة 2: التقييم البصري السريري
# ─────────────────────────────────────────────

def _assess_clinical_vision(data: dict) -> dict:
    """تحليل نتائج الفحوصات البصرية"""

    va_right = data.get("va_right", "")
    va_left = data.get("va_left", "")
    va_both = data.get("va_both", "")
    visual_field = data.get("visual_field", "")
    contrast_sensitivity = data.get("contrast_sensitivity", "")
    color_vision = data.get("color_vision", "")
    glare_sensitivity = data.get("glare_sensitivity", "")

    # تحليل حدة الإبصار
    va_analysis = {}
    for eye, va in [("right", va_right), ("left", va_left), ("both", va_both)]:
        if va:
            decimal = _parse_va_to_decimal(va)
            if decimal is not None:
                va_analysis[eye] = {
                    "input": va,
                    "decimal": round(decimal, 3),
                    "logmar": round(-math.log10(decimal), 2) if decimal > 0 else 3.0,
                    "who_category": _who_category(decimal)
                }

    # تقييم المجال البصري
    field_type = _classify_visual_field(visual_field)

    # توصيات أجهزة مبدئية
    best_va_decimal = None
    if va_analysis:
        best_va_decimal = max(
            (v["decimal"] for v in va_analysis.values()),
            default=None
        )

    preliminary_device_hints = _get_preliminary_device_hints(best_va_decimal, field_type)

    return {
        "phase": "clinical_vision",
        "visual_acuity": va_analysis,
        "best_va": {
            "decimal": best_va_decimal,
            "who_category": _who_category(best_va_decimal) if best_va_decimal else "غير محدد"
        },
        "visual_field_type": field_type,
        "contrast_sensitivity": contrast_sensitivity or "لم يُقيَّم",
        "color_vision": color_vision or "لم يُقيَّم",
        "glare_sensitivity": glare_sensitivity or "لم يُقيَّم",
        "preliminary_device_hints": preliminary_device_hints,
        "recommended_next": "functional"
    }


def _parse_va_to_decimal(va: str) -> Optional[float]:
    """تحويل حدة إبصار لقيمة Decimal"""
    va = str(va).strip().upper()

    special = {"CF": 0.014, "HM": 0.005, "LP": 0.002, "NLP": 0.0}
    if va in special:
        return special[va]

    if "/" in va:
        try:
            parts = va.split("/")
            return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            return None

    try:
        val = float(va)
        # إذا بدت قيمة LogMAR (عادةً 0.0 - 3.0)
        if 0 <= val <= 3.0 and "." in str(va):
            if val > 1.5:
                return 10 ** (-val)
        return val
    except ValueError:
        return None


def _who_category(decimal: Optional[float]) -> str:
    if decimal is None:
        return "غير محدد"
    if decimal >= 0.3:
        return "طبيعي (≥ 6/18)"
    elif decimal >= 0.1:
        return "ضعف معتدل — الفئة 1 (6/18-6/60)"
    elif decimal >= 0.05:
        return "ضعف شديد — الفئة 2 (6/60-3/60)"
    elif decimal >= 0.02:
        return "ضعف عميق — الفئة 3 (3/60-1/60)"
    elif decimal > 0:
        return "إدراك الضوء فقط — الفئة 4"
    else:
        return "لا إدراك للضوء (NLP) — الفئة 5"


def _classify_visual_field(vf_description: str) -> str:
    if not vf_description:
        return "غير محدد"
    vf_lower = vf_description.lower()
    if any(w in vf_lower for w in ["مركزي", "central", "scotoma", "بقعة عمياء"]):
        return "فقد مركزي (Central Loss)"
    elif any(w in vf_lower for w in ["محيطي", "peripheral", "نفقي", "tunnel"]):
        return "فقد محيطي (Peripheral Loss)"
    elif any(w in vf_lower for w in ["نصفي", "hemi", "hemianopia", "quadrant"]):
        return "فقد نصفي أو ربعي (Hemianopia/Quadrantanopia)"
    elif any(w in vf_lower for w in ["متقطع", "scattered", "patchy"]):
        return "فقد متقطع (Scattered)"
    elif any(w in vf_lower for w in ["سليم", "intact", "كامل", "full", "normal"]):
        return "سليم (Normal Field)"
    return f"غير مصنف — يحتاج مراجعة: {vf_description[:50]}"


def _get_preliminary_device_hints(va_decimal: Optional[float], field_type: str) -> list:
    hints = []
    if va_decimal is None:
        return ["تحديد الأجهزة يتطلب قياس حدة الإبصار أولاً"]

    if va_decimal >= 0.3:
        hints.append("حدة إبصار قريبة من الطبيعي — قد تكفي نظارات تصحيح مناسبة")
    elif va_decimal >= 0.1:
        hints.append("يُنصح بمكبر يدوي أو Stand magnifier (3-5x) للقراءة")
    elif va_decimal >= 0.05:
        hints.append("يحتاج مكبر قوي (6-10x) أو مكبر إلكتروني محمول")
    elif va_decimal >= 0.02:
        hints.append("يحتاج CCTV أو مكبر إلكتروني طاولي — قد يلزم Text-to-Speech")
    else:
        hints.append("التقنيات الغير بصرية ضرورية: قارئ شاشة، Braille، صوتي")

    if "Hemianopia" in field_type or "نصفي" in field_type:
        hints.append("فقد نصفي — تدريب Scanning + احتمال استخدام Prisms")
    elif "Peripheral" in field_type or "محيطي" in field_type:
        hints.append("فقد محيطي — تحديات التنقل تفوق القراءة — تقييم O&M ضروري")

    return hints


# ─────────────────────────────────────────────
# المرحلة 3: التقييم الوظيفي
# ─────────────────────────────────────────────

def _assess_functional(data: dict) -> dict:
    """تقييم القدرات الوظيفية في الأنشطة اليومية"""

    reading_data = data.get("reading", {})
    adl_data = data.get("adl", {})
    mobility_data = data.get("mobility", {})
    digital_data = data.get("digital_devices", {})

    # تقييم القراءة
    reading_result = _assess_reading(reading_data)

    # تقييم ADL
    adl_score = _calculate_adl_score(adl_data)

    # تقييم التنقل
    mobility_result = _assess_mobility(mobility_data)

    # تحديد أكثر المجالات تأثراً
    impact_areas = []
    if reading_result.get("reading_level") in ["صعوبة شديدة", "عجز تام"]:
        impact_areas.append("القراءة والكتابة")
    if adl_score.get("independence_level") in ["اعتماد شديد", "اعتماد كامل"]:
        impact_areas.append("الأنشطة اليومية")
    if mobility_result.get("mobility_level") in ["قيود شديدة", "عجز"]:
        impact_areas.append("التنقل والتوجه")

    return {
        "phase": "functional",
        "reading": reading_result,
        "adl": adl_score,
        "mobility": mobility_result,
        "digital_competency": digital_data.get("level", "لم يُقيَّم"),
        "priority_areas": impact_areas,
        "recommended_next": "psychological"
    }


def _assess_reading(reading_data: dict) -> dict:
    cps = reading_data.get("critical_print_size")
    speed = reading_data.get("reading_speed_wpm")
    distance = reading_data.get("working_distance_cm")
    fatigue_minutes = reading_data.get("fatigue_minutes")

    level = "لم يُقيَّم"
    if speed is not None:
        if speed >= 100:
            level = "جيد (≥ 100 كلمة/دقيقة)"
        elif speed >= 40:
            level = "وظيفي (40-99 كلمة/دقيقة)"
        elif speed >= 10:
            level = "صعوبة (10-39 كلمة/دقيقة)"
        else:
            level = "صعوبة شديدة (< 10 كلمة/دقيقة)"
    elif cps is not None:
        if cps <= 0.8:
            level = "قراءة وظيفية ممكنة"
        elif cps <= 1.2:
            level = "صعوبة متوسطة"
        else:
            level = "صعوبة شديدة — يلزم مكبر"

    return {
        "reading_level": level,
        "critical_print_size": cps,
        "reading_speed_wpm": speed,
        "working_distance_cm": distance,
        "fatigue_minutes": fatigue_minutes,
    }


def _calculate_adl_score(adl_data: dict) -> dict:
    """حساب درجة الاستقلالية في الأنشطة اليومية (0-3 لكل نشاط)"""
    activities = {
        "medication_management": "إدارة الأدوية",
        "cooking": "الطبخ",
        "personal_care": "العناية الشخصية",
        "shopping": "التسوق",
        "money_management": "إدارة المال",
        "phone_use": "استخدام الهاتف",
        "reading_labels": "قراءة الملصقات",
    }

    total = 0
    assessed = 0
    details = {}

    for key, label in activities.items():
        score = adl_data.get(key)
        if score is not None:
            score = int(score)
            total += score
            assessed += 1
            levels = {3: "مستقل تماماً", 2: "مستقل مع صعوبة", 1: "يحتاج مساعدة", 0: "عاجز تماماً"}
            details[label] = {"score": score, "level": levels.get(score, str(score))}

    if assessed == 0:
        return {"independence_level": "لم يُقيَّم", "details": {}}

    percentage = (total / (assessed * 3)) * 100

    if percentage >= 80:
        independence = "اعتماد ذاتي عالٍ"
    elif percentage >= 60:
        independence = "اعتماد ذاتي متوسط"
    elif percentage >= 40:
        independence = "اعتماد جزئي"
    elif percentage >= 20:
        independence = "اعتماد شديد"
    else:
        independence = "اعتماد كامل"

    return {
        "independence_level": independence,
        "score_percentage": round(percentage, 1),
        "total_score": f"{total}/{assessed * 3}",
        "details": details,
    }


def _assess_mobility(mobility_data: dict) -> dict:
    indoor = mobility_data.get("indoor", "لم يُقيَّم")
    outdoor = mobility_data.get("outdoor", "لم يُقيَّم")
    falls = mobility_data.get("falls_last_year", None)
    aids = mobility_data.get("current_aids", [])

    level = "لم يُقيَّم"
    if falls is not None:
        if falls == 0 and outdoor not in ["محدود", "عاجز"]:
            level = "جيد"
        elif falls <= 2:
            level = "قيود متوسطة"
        else:
            level = "قيود شديدة — خطر سقوط مرتفع"

    return {
        "mobility_level": level,
        "indoor": indoor,
        "outdoor": outdoor,
        "falls_last_year": falls,
        "current_aids": aids,
        "om_referral_needed": falls is not None and falls > 1,
    }


# ─────────────────────────────────────────────
# المرحلة 4: الفحص النفسي المبدئي
# ─────────────────────────────────────────────

def _assess_psychological(data: dict) -> dict:
    """تقييم نفسي مبدئي — لا يُغني عن التقييم المتخصص"""

    mood = data.get("mood_description", "")
    sleep = data.get("sleep", "")
    social = data.get("social_engagement", "")
    phq2_responses = data.get("phq2", [])
    risk_factors = data.get("risk_factors", [])

    # PHQ-2 مبدئي
    phq2_score = None
    phq2_interpretation = ""
    if len(phq2_responses) >= 2:
        try:
            phq2_score = sum(int(r) for r in phq2_responses[:2])
            if phq2_score >= 3:
                phq2_interpretation = "إيجابي — يُنصح بإجراء PHQ-9 الكامل"
            else:
                phq2_interpretation = "سلبي — لا يُشير لاكتئاب في الوقت الحالي"
        except (ValueError, TypeError):
            phq2_interpretation = "خطأ في البيانات"

    # عوامل الخطر
    known_risks = [
        "recent_vision_loss", "فقدان بصر حديث",
        "social_isolation", "عزلة اجتماعية",
        "living_alone", "يعيش وحده",
        "previous_depression", "اكتئاب سابق",
        "chronic_pain", "ألم مزمن"
    ]
    identified_risks = [r for r in risk_factors if any(k in r.lower() for k in known_risks)]

    referral_urgency = "لا يلزم في الوقت الحالي"
    if phq2_score is not None and phq2_score >= 3:
        referral_urgency = "ينصح بإجراء PHQ-9 وتقييم نفسي متخصص"
    elif len(identified_risks) >= 2:
        referral_urgency = "عوامل خطر متعددة — مراقبة دقيقة مع توفير الدعم النفسي"

    return {
        "phase": "psychological",
        "mood": mood,
        "sleep": sleep,
        "social_engagement": social,
        "phq2_score": phq2_score,
        "phq2_interpretation": phq2_interpretation,
        "identified_risk_factors": identified_risks,
        "referral_urgency": referral_urgency,
        "note": "⚠️ هذا تقييم مبدئي — لا يُغني عن PHQ-9 الكامل والتقييم النفسي المتخصص",
        "recommended_next": "classification"
    }


# ─────────────────────────────────────────────
# المرحلة 5: التصنيف والتوصيات
# ─────────────────────────────────────────────

def _assess_classification(data: dict) -> dict:
    """تصنيف الحالة وإعطاء توصيات التأهيل"""

    va_right = data.get("va_right", "")
    va_left = data.get("va_left", "")
    visual_field = data.get("visual_field", "")
    age = data.get("age")
    diagnosis = data.get("diagnosis", "")

    # حساب best VA
    best_decimal = None
    for va in [va_right, va_left]:
        d = _parse_va_to_decimal(va)
        if d is not None:
            if best_decimal is None or d > best_decimal:
                best_decimal = d

    who_cat = _who_category(best_decimal)
    field_type = _classify_visual_field(visual_field)

    # الأولويات التأهيلية
    rehab_priorities = _determine_rehab_priorities(best_decimal, field_type, age, diagnosis)

    # الجلسات المقترحة
    sessions = _recommend_sessions(best_decimal, field_type)

    return {
        "phase": "classification",
        "who_vi_classification": who_cat,
        "best_va_decimal": best_decimal,
        "visual_field_type": field_type,
        "rehab_priorities": rehab_priorities,
        "recommended_sessions": sessions,
        "follow_up_timeline": "4-6 أسابيع للتقييم الأولي، ثم 3 أشهر",
    }


def _determine_rehab_priorities(va: Optional[float], field: str, age, diagnosis: str) -> list:
    priorities = []

    if va is not None:
        if va < 0.1:
            priorities.append("الأجهزة الإلكترونية المكبرة (CCTV/EVES) والتقنيات الصوتية")
        elif va < 0.3:
            priorities.append("العدسات المكبرة والتدريب على استخدامها")
        else:
            priorities.append("تحسين ظروف الإضاءة والتباين")

    if "hemianopia" in field.lower() or "نصفي" in field:
        priorities.append("تدريب Scanning والتوعية بالمجال المفقود")
        priorities.append("تقييم إمكانية استخدام Fresnel Prisms")
    elif "peripheral" in field.lower() or "محيطي" in field:
        priorities.append("تقييم التنقل وبرنامج O&M")

    if age and int(age) >= 65:
        priorities.append("تقييم خطر السقوط وتعديلات المنزل")

    diag_lower = diagnosis.lower()
    if any(d in diag_lower for d in ["amd", "ضمور بقعي", "macular"]):
        priorities.append("تدريب PRL (Preferred Retinal Locus)")
    elif any(d in diag_lower for d in ["رأب", "retinitis pigmentosa", "rp"]):
        priorities.append("تدريب التكيف مع الإضاءة المنخفضة")
    elif any(d in diag_lower for d in ["جلوكوما", "glaucoma", "زرق"]):
        priorities.append("برنامج O&M + Scanning Training")

    return priorities or ["تحديد الأولويات يتطلب مزيداً من بيانات التقييم"]


def _recommend_sessions(va: Optional[float], field: str) -> dict:
    if va is None:
        return {"frequency": "غير محدد", "duration_weeks": "غير محدد"}

    if va < 0.05:
        return {
            "frequency": "3-4 مرات/أسبوع",
            "duration_weeks": "12-16 أسبوع",
            "session_length_min": 60,
            "home_practice_daily_min": 30
        }
    elif va < 0.1:
        return {
            "frequency": "2-3 مرات/أسبوع",
            "duration_weeks": "8-12 أسبوع",
            "session_length_min": 45,
            "home_practice_daily_min": 20
        }
    else:
        return {
            "frequency": "1-2 مرات/أسبوع",
            "duration_weeks": "6-8 أسابيع",
            "session_length_min": 45,
            "home_practice_daily_min": 15
        }


# ─────────────────────────────────────────────
# التقييم الكامل
# ─────────────────────────────────────────────

def _assess_full(data: dict) -> dict:
    """تشغيل جميع مراحل التقييم"""
    return {
        "phase": "full",
        "history": _assess_history(data),
        "clinical_vision": _assess_clinical_vision(data),
        "functional": _assess_functional(data),
        "psychological": _assess_psychological(data),
        "classification": _assess_classification(data),
    }


# ─────────────────────────────────────────────
# الحسابات الإضافية
# ─────────────────────────────────────────────

def _run_calculations(data: dict, calculations: list) -> dict:
    """تنفيذ الحسابات المطلوبة"""
    results = {}
    clinical = data.get("clinical_data", data)

    if "who_classification" in calculations:
        va_str = clinical.get("va_right") or clinical.get("va_left", "")
        d = _parse_va_to_decimal(str(va_str))
        results["who_classification"] = _who_category(d)

    if "magnification_need" in calculations:
        va_str = clinical.get("va_right") or clinical.get("va_left", "")
        d = _parse_va_to_decimal(str(va_str))
        if d and d > 0:
            mag = round(0.3 / d, 1)
            results["magnification_need"] = {
                "power": f"{mag}x",
                "lens_diopter": f"{round(mag * 2.5, 0)}D",
                "note": "قيمة تقديرية — تجربة عملية ضرورية"
            }

    if "cps_estimation" in calculations:
        va_str = clinical.get("va_right") or clinical.get("va_left", "")
        d = _parse_va_to_decimal(str(va_str))
        if d and d > 0:
            cps_logmar = round(-math.log10(d) + 0.3, 1)
            results["cps_estimation"] = {
                "estimated_cps_logmar": cps_logmar,
                "note": "تقدير تقريبي — قياس MNREAD الفعلي أدق"
            }

    return results
