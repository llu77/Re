"""
Device Recommender — قاعدة بيانات الأجهزة المساعدة البصرية
============================================================
توصيات مخصصة بناءً على: VA + نوع الفقد البصري + المهمة + العمر + القدرات
"""


# ═══════════════════════════════════════════════════════════════
# قاعدة بيانات الأجهزة
# ═══════════════════════════════════════════════════════════════

DEVICE_DATABASE = {
    # ─── مكبرات بصرية ───
    "handheld_magnifier": {
        "name": "مكبر يدوي (Hand Magnifier)",
        "power_range": "2x-20x",
        "best_for": ["near_reading", "spot_reading", "labels"],
        "pros": ["رخيص", "محمول", "سهل الاستخدام"],
        "cons": ["يحتاج يداً حرة", "للاستخدام المؤقت", "مسافة عمل قصيرة"],
        "va_range": (0.02, 0.3),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal"],
        "price_range": "50-500 ريال",
        "examples": ["مكبر Eschenbach", "مكبر Coil"]
    },
    "stand_magnifier": {
        "name": "مكبر ثابت / Stand Magnifier",
        "power_range": "2x-15x",
        "best_for": ["near_reading", "writing", "prolonged_reading"],
        "pros": ["مسافة عمل ثابتة", "لا يحتاج تثبيت", "مريح لكبار السن"],
        "cons": ["ثقيل نسبياً", "يحتاج إضاءة خلفية"],
        "va_range": (0.02, 0.2),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "كبار السن والبالغين",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "tremor"],
        "price_range": "100-800 ريال",
        "examples": ["Eschenbach Stand", "Coil Stand Magnifier"]
    },
    "spectacle_microscope": {
        "name": "نظارة تكبيرية (Spectacle Microscope)",
        "power_range": "2x-12x",
        "best_for": ["near_reading", "writing", "prolonged_tasks"],
        "pros": ["تحرير اليدين", "للمهام المطولة"],
        "cons": ["مسافة عمل محدودة جداً", "رأس مائل", "لا تصلح للمشي"],
        "va_range": (0.02, 0.15),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "البالغين",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "limited_dexterity"],
        "price_range": "500-3000 ريال",
        "examples": ["Ocutech", "Designs for Vision Reading Microscope"]
    },
    "monocular_telescope": {
        "name": "منظار أحادي (Monocular Telescope)",
        "power_range": "2.5x-10x",
        "best_for": ["distance_viewing", "tv", "signs", "faces"],
        "pros": ["للمسافات البعيدة", "محمول"],
        "cons": ["مجال رؤية ضيق", "يحتاج تدريباً", "لا يصلح للمشي"],
        "va_range": (0.02, 0.2),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "البالغين",
        "cognitive_req": "normal",
        "hand_function_req": ["normal"],
        "price_range": "300-2000 ريال",
        "examples": ["Schweizer Monocular", "Eschenbach MaxDetail"]
    },
    "bioptic_telescope": {
        "name": "نظارة Bioptic التلسكوبية",
        "power_range": "2x-6x",
        "best_for": ["distance_viewing", "driving_in_some_countries"],
        "pros": ["للقيادة (في دول تسمح)", "تحرير اليدين"],
        "cons": ["تكلفة عالية", "يحتاج تدريباً مكثفاً"],
        "va_range": (0.1, 0.3),
        "field_types": ["central_loss"],
        "suitable_ages": "18-65 سنة",
        "cognitive_req": "normal",
        "hand_function_req": ["normal"],
        "price_range": "3000-15000 ريال",
        "examples": ["Ocutech Bioptic"]
    },
    # ─── أجهزة إلكترونية ───
    "portable_eves": {
        "name": "مكبر إلكتروني محمول (EVES)",
        "power_range": "2x-22x",
        "best_for": ["near_reading", "writing", "shopping", "labels", "medication_management"],
        "pros": ["محمول", "ألوان وتباين قابل للتعديل", "شاشة عرض واضحة"],
        "cons": ["تكلفة متوسطة-عالية", "يحتاج شحن"],
        "va_range": (0.01, 0.2),
        "field_types": ["central_loss", "general_reduction", "peripheral_loss"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "tremor"],
        "price_range": "1500-6000 ريال",
        "examples": ["Optelec Compact", "Humanware Explore", "Prodigi Duo"]
    },
    "cctv_desktop": {
        "name": "مكبر إلكتروني طاولي (CCTV)",
        "power_range": "2x-75x",
        "best_for": ["near_reading", "prolonged_reading", "writing", "computer"],
        "pros": ["تكبير عالٍ جداً", "شاشة كبيرة", "راحة للعين"],
        "cons": ["ثقيل وكبير", "غير محمول", "سعر مرتفع"],
        "va_range": (0.005, 0.15),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "mild_impairment",
        "hand_function_req": ["normal", "tremor", "limited_dexterity"],
        "price_range": "4000-20000 ريال",
        "examples": ["Optelec ClearView", "Humanware Prodigi Connect", "Enhanced Vision"]
    },
    "smart_glasses_orcam": {
        "name": "نظارة ذكية OrCam MyEye",
        "power_range": "N/A - OCR device",
        "best_for": ["near_reading", "labels", "money_management", "faces", "shopping"],
        "pros": ["يقرأ النص بصوت عالٍ", "يتعرف على الوجوه", "تحرير اليدين"],
        "cons": ["سعر مرتفع جداً", "يحتاج تدريب", "لا يُكبّر الصورة"],
        "va_range": (0.0, 0.3),
        "field_types": ["central_loss", "peripheral_loss", "general_reduction"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "limited_dexterity", "one_hand"],
        "price_range": "15000-25000 ريال",
        "examples": ["OrCam MyEye Pro", "OrCam Read"]
    },
    # ─── تقنيات مساعدة رقمية ───
    "screen_reader": {
        "name": "قارئ الشاشة (Screen Reader)",
        "power_range": "N/A - software",
        "best_for": ["computer", "smartphone", "email", "web_browsing"],
        "pros": ["مجاني (NVDA, VoiceOver)", "شامل لكل محتوى الشاشة"],
        "cons": ["منحنى تعلم حاد", "يتطلب تدريباً مكثفاً"],
        "va_range": (0.0, 0.05),
        "field_types": ["central_loss", "general_reduction", "peripheral_loss"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "limited_dexterity"],
        "price_range": "مجاني - 3000 ريال/سنة",
        "examples": ["NVDA (مجاني)", "JAWS (مدفوع)", "VoiceOver (iOS/Mac)", "TalkBack (Android)"]
    },
    "screen_magnifier_software": {
        "name": "برنامج تكبير الشاشة",
        "power_range": "2x-36x",
        "best_for": ["computer", "smartphone"],
        "pros": ["رخيص/مجاني", "تكبير مرن", "سهل الاستخدام"],
        "cons": ["للشاشات فقط"],
        "va_range": (0.05, 0.3),
        "field_types": ["central_loss", "general_reduction"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "tremor"],
        "price_range": "مجاني - 2000 ريال/سنة",
        "examples": ["ZoomText", "Windows Magnifier (مجاني)", "Apple Zoom (مجاني)"]
    },
    "seeing_ai_app": {
        "name": "تطبيق Seeing AI (Microsoft)",
        "power_range": "N/A - AI app",
        "best_for": ["labels", "shopping", "money_management", "faces", "documents"],
        "pros": ["مجاني", "متعدد الوظائف", "سهل الاستخدام", "يدعم العربية"],
        "cons": ["يحتاج هاتف ذكي وإنترنت"],
        "va_range": (0.0, 0.2),
        "field_types": ["central_loss", "general_reduction", "peripheral_loss"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal"],
        "price_range": "مجاني",
        "examples": ["Seeing AI (iOS/Android)", "Be My Eyes (مجاني + خيار مدفوع)"]
    },
    # ─── فلاتر وعدسات متخصصة ───
    "absorptive_filters": {
        "name": "فلاتر امتصاص الضوء (NoIR / Corning)",
        "power_range": "N/A - filters",
        "best_for": ["glare_reduction", "outdoor_mobility", "photophobia"],
        "pros": ["تقليل الإبهار", "تحسين التباين", "أشكال متعددة"],
        "cons": ["تغيير إدراك الألوان", "تحتاج تجربة للاختيار الصحيح"],
        "va_range": (0.0, 1.0),
        "field_types": ["all"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["all"],
        "price_range": "200-600 ريال",
        "examples": ["NoIR Series", "Corning CPF 550", "Eschenbach Filters"]
    },
    "fresnel_prism": {
        "name": "منشور فريزنل (Fresnel Prism)",
        "power_range": "15-20 diopters",
        "best_for": ["hemianopia", "mobility", "reading_with_field_loss"],
        "pros": ["يُوسع الوعي بالمجال المفقود", "غير مكلف"],
        "cons": ["يقلل حدة الإبصار قليلاً", "يحتاج تدريب"],
        "va_range": (0.1, 1.0),
        "field_types": ["hemianopia", "quadrantanopia"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["all"],
        "price_range": "200-500 ريال",
        "examples": ["3M Fresnel Prism (15-20Δ)", "Peli Peripheral Prism Glasses"]
    },
    # ─── أدوات التنقل ───
    "white_cane_id": {
        "name": "العصا البيضاء التعريفية (ID Cane)",
        "power_range": "N/A",
        "best_for": ["identification", "indoor_mobility"],
        "pros": ["رخيصة", "تُعرِّف بضعف البصر"],
        "cons": ["لا تحمي من العوائق العلوية"],
        "va_range": (0.0, 0.1),
        "field_types": ["all"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal", "limited_dexterity"],
        "price_range": "50-200 ريال",
        "examples": ["عصا بيضاء قابلة للطي"]
    },
    "white_cane_long": {
        "name": "العصا البيضاء الطويلة (Long Cane)",
        "power_range": "N/A",
        "best_for": ["outdoor_mobility", "navigation"],
        "pros": ["تحمي من العوائق", "تُعرِّف العوائق السفلية"],
        "cons": ["يحتاج تدريب O&M متخصص"],
        "va_range": (0.0, 0.1),
        "field_types": ["peripheral_loss", "general_reduction"],
        "suitable_ages": "جميع الأعمار",
        "cognitive_req": "normal",
        "hand_function_req": ["normal"],
        "price_range": "100-400 ريال",
        "examples": ["عصا Ambutech", "عصا NFB"]
    },
}


# ═══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def recommend_devices(params: dict) -> dict:
    """
    توصية الأجهزة المساعدة المناسبة للمريض

    Args:
        params: {
            visual_acuity: "6/60" أو "0.1" أو "LogMAR 1.0"
            field_type: central_loss | peripheral_loss | hemianopia | scattered | general_reduction | normal_field
            task: near_reading | distance_viewing | mobility | writing | computer | cooking | grooming | medication_management | shopping
            patient_age: int (اختياري)
            cognitive_status: normal | mild_impairment | moderate_impairment
            hand_function: normal | tremor | limited_dexterity | one_hand
        }
    """
    va_str = params.get("visual_acuity", "")
    field_type = params.get("field_type", "general_reduction")
    task = params.get("task", "near_reading")
    age = params.get("patient_age")
    cognitive = params.get("cognitive_status", "normal")
    hand_func = params.get("hand_function", "normal")

    # تحويل VA لـ Decimal
    va_decimal = _parse_va_to_decimal(va_str)

    if va_decimal is None:
        return {
            "error": "لم يُتمكن من تفسير حدة الإبصار",
            "hint": "استخدم: '6/60' أو '0.1' أو 'CF' أو 'HM' أو 'LP'"
        }

    # الحصول على التوصيات
    recommendations = _filter_devices(va_decimal, field_type, task, cognitive, hand_func, age)

    # ترتيب حسب الأولوية
    primary = [r for r in recommendations if r["priority"] == "primary"]
    secondary = [r for r in recommendations if r["priority"] == "secondary"]

    # تحذيرات خاصة
    warnings = _generate_warnings(va_decimal, field_type, age, task)

    return {
        "patient_profile": {
            "va_decimal": va_decimal,
            "va_who_category": _who_category(va_decimal),
            "field_type": field_type,
            "task": task,
            "cognitive": cognitive,
            "hand_function": hand_func,
        },
        "primary_recommendations": primary[:3],
        "secondary_recommendations": secondary[:2],
        "warnings": warnings,
        "next_steps": _get_next_steps(va_decimal, field_type, task),
        "total_devices_evaluated": len(DEVICE_DATABASE),
        "note": "الاختيار النهائي يتطلب تجربة عملية مع المريض"
    }


def _parse_va_to_decimal(va: str) -> float:
    if not va:
        return None
    va = str(va).strip().upper()
    specials = {"CF": 0.014, "HM": 0.005, "LP": 0.002, "NLP": 0.001}
    if va in specials:
        return specials[va]
    # إزالة بادئة LogMAR
    if va.startswith("LOGMAR"):
        try:
            logmar_val = float(va.replace("LOGMAR", "").strip())
            return round(10 ** (-logmar_val), 4)
        except ValueError:
            pass
    if "/" in va:
        try:
            parts = va.split("/")
            return round(float(parts[0]) / float(parts[1]), 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        val = float(va)
        if 0 <= val <= 3.0 and "." in str(va) and val <= 1.5:
            return round(10 ** (-val), 4)
        return val
    except ValueError:
        return None


def _who_category(decimal):
    if decimal is None:
        return "غير محدد"
    if decimal >= 0.3:
        return "طبيعي"
    elif decimal >= 0.1:
        return "ضعف معتدل"
    elif decimal >= 0.05:
        return "ضعف شديد"
    elif decimal >= 0.02:
        return "ضعف عميق"
    elif decimal > 0:
        return "إدراك ضوء فقط"
    return "لا إدراك للضوء"


def _filter_devices(va, field, task, cognitive, hand_func, age):
    results = []

    for dev_id, device in DEVICE_DATABASE.items():
        score = 0
        priority = "secondary"

        # فحص نطاق VA
        va_range = device.get("va_range", (0, 1))
        if not (va_range[0] <= va <= va_range[1]):
            continue

        # فحص المهمة
        best_for = device.get("best_for", [])
        if task in best_for:
            score += 3
            priority = "primary"
        elif any(t in best_for for t in [task.replace("_", " "), "all"]):
            score += 1

        # فحص نوع الفقد البصري
        field_types = device.get("field_types", [])
        if field in field_types or "all" in field_types:
            score += 2

        # فحص الحالة المعرفية
        cog_req = device.get("cognitive_req", "normal")
        cognitive_levels = ["normal", "mild_impairment", "moderate_impairment"]
        if cognitive_levels.index(cognitive) <= cognitive_levels.index(cog_req):
            score += 1

        # فحص وظيفة اليد
        hand_reqs = device.get("hand_function_req", ["normal"])
        if hand_func in hand_reqs or "all" in hand_reqs:
            score += 1

        # إضافة للنتائج
        if score >= 2:
            results.append({
                "device_id": dev_id,
                "name": device["name"],
                "power_range": device.get("power_range", ""),
                "pros": device.get("pros", []),
                "cons": device.get("cons", []),
                "examples": device.get("examples", []),
                "price_range": device.get("price_range", ""),
                "priority": priority,
                "match_score": score
            })

    # ترتيب حسب الدرجة
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def _generate_warnings(va, field, age, task):
    warnings = []
    if va < 0.02:
        warnings.append("⚠️ حدة إبصار منخفضة جداً — التقنيات الصوتية والبرايل ضرورية بالتوازي مع الأجهزة البصرية")
    if "hemianopia" in field.lower() or "نصفي" in field.lower():
        warnings.append("⚠️ فقد نصفي — أي جهاز بصري يجب مصاحبته بتدريب Scanning وإحالة لـ O&M")
    if age and int(age) >= 75:
        warnings.append("⚠️ كبر السن — تبسيط أقصى في الأجهزة، تدريب تدريجي، دعم الأسرة")
    if task == "mobility" and va < 0.05:
        warnings.append("⚠️ للتنقل — إحالة عاجلة لأخصائي التوجه والتنقل (O&M Specialist)")
    return warnings


def _get_next_steps(va, field, task):
    steps = ["تجربة الأجهزة الموصى بها عملياً مع المريض"]
    if va < 0.05:
        steps.append("تقييم احتياجات التقنيات الصوتية والرقمية")
    if task == "near_reading":
        steps.append("قياس MNREAD لتحديد CPS الدقيق")
    if "peripheral" in field.lower() or "hemianopia" in field.lower():
        steps.append("إحالة لأخصائي التوجه والتنقل (O&M)")
    steps.append("متابعة بعد 4-6 أسابيع لتقييم التكيف")
    return steps
