"""
Arabic Reading Calculator Tool
حاسبة القراءة العربية

Specialized tool for calculating optimal reading parameters for Arabic text,
including diacritical marks (تشكيل), Quran reading, and RTL text considerations.
"""

import math
from typing import Dict, Any, Optional


# Arabic text constants
ARABIC_CHAR_COMPLEXITY = {
    "plain": 1.0,         # Arabic without diacritics
    "diacritical": 1.3,   # Arabic with تشكيل (harakat)
    "quran": 1.4,         # Quran text (full tashkeel + tajweed marks)
    "mixed": 1.15,        # Mixed Arabic/Latin
    "handwriting": 1.5,   # Handwritten Arabic (cursive complexity)
}

# Reading speed norms for Arabic (words per minute)
ARABIC_READING_NORMS = {
    "fluent_adult": {"min": 150, "max": 250, "avg": 200},
    "average_adult": {"min": 100, "max": 180, "avg": 140},
    "slow_reader": {"min": 50, "max": 100, "avg": 75},
    "low_vision": {"min": 20, "max": 80, "avg": 45},
    "child_6_8": {"min": 60, "max": 100, "avg": 80},
    "child_9_12": {"min": 100, "max": 150, "avg": 125},
    "elderly": {"min": 80, "max": 140, "avg": 110},
}

# Standard Arabic print sizes
ARABIC_PRINT_SIZES = {
    "newspaper": 8,           # جريدة
    "book_standard": 12,      # كتاب عادي
    "textbook": 14,           # كتاب مدرسي
    "large_print": 18,        # طباعة كبيرة
    "extra_large": 24,        # طباعة كبيرة جداً
    "quran_standard": 14,     # مصحف عادي
    "quran_large": 20,        # مصحف كبير
    "quran_tajweed": 16,      # مصحف تجويد
    "children_book": 18,      # كتاب أطفال
    "low_vision_min": 18,     # الحد الأدنى لضعف البصر
}

# Working distance recommendations (cm)
WORKING_DISTANCE_NORMS = {
    "optimal": 40,
    "near": 25,
    "intermediate": 60,
    "extended_near": 33,
}


def calculate_arabic_reading_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for Arabic reading calculations.

    Supported calculations:
    - optimal_print_size: Calculate minimum and recommended print size
    - magnification_needed: Calculate required magnification
    - working_distance: Calculate optimal reading distance
    - reading_speed_estimation: Estimate reading speed with low vision
    - quran_requirements: Specific requirements for Quran reading
    - full_arabic_assessment: Complete Arabic reading assessment

    Args:
        params: Dictionary with calculation type and parameters

    Returns:
        Dictionary with calculation results
    """
    calc_type = params.get("calculation_type", "full_arabic_assessment")

    calculators = {
        "optimal_print_size": _calculate_optimal_print_size,
        "magnification_needed": _calculate_magnification_needed,
        "working_distance": _calculate_working_distance,
        "reading_speed_estimation": _estimate_reading_speed,
        "quran_requirements": _calculate_quran_requirements,
        "full_arabic_assessment": _full_arabic_assessment,
    }

    calculator = calculators.get(calc_type)
    if not calculator:
        return {
            "error": f"Unknown calculation type: {calc_type}",
            "available_types": list(calculators.keys())
        }

    return calculator(params)


def _parse_va_to_decimal(va_string: str) -> Optional[float]:
    """Parse various visual acuity formats to decimal."""
    if not va_string:
        return None

    va_str = str(va_string).strip().upper()

    # Special values
    special_map = {
        "CF": 0.02, "HM": 0.01, "LP": 0.005, "NLP": 0.0,
        "PL": 0.005, "NO LIGHT PERCEPTION": 0.0,
        "COUNTING FINGERS": 0.02, "HAND MOTION": 0.01,
        "LIGHT PERCEPTION": 0.005,
    }
    if va_str in special_map:
        return special_map[va_str]

    # Snellen fraction (e.g., 6/60, 20/200)
    if "/" in va_str:
        parts = va_str.split("/")
        try:
            numerator = float(parts[0])
            denominator = float(parts[1])
            if denominator == 0:
                return None
            decimal = numerator / denominator
            # Convert to 6-metre standard if needed
            if numerator == 20:
                decimal = (6 / denominator) * (numerator / 6)
                decimal = numerator / denominator * (6 / 20)
                decimal = 6 / (denominator * 20 / numerator)
                # Simpler: 20/X = 6/(X * 6/20)
                decimal = 20 / denominator  # simplified to fraction of 20
                decimal = numerator / denominator  # raw fraction
            return decimal
        except (ValueError, ZeroDivisionError):
            return None

    # LogMAR (e.g., 0.3, 1.0, -0.1)
    try:
        val = float(va_str)
        if -0.3 <= val <= 3.0:
            # Likely LogMAR
            return 10 ** (-val)
        # Otherwise treat as decimal
        return val
    except ValueError:
        pass

    return None


def _decimal_to_snellen_6m(decimal_va: float) -> str:
    """Convert decimal VA to Snellen 6-metre format."""
    if decimal_va <= 0.005:
        return "LP"
    if decimal_va <= 0.01:
        return "HM"
    if decimal_va <= 0.02:
        return "CF"

    # Standard Snellen values
    snellen_map = [
        (1.0, "6/6"), (0.8, "6/7.5"), (0.67, "6/9"), (0.5, "6/12"),
        (0.4, "6/15"), (0.3, "6/18"), (0.2, "6/30"), (0.1, "6/60"),
        (0.05, "6/120"), (0.033, "6/180"), (0.025, "6/240"), (0.02, "CF"),
    ]

    # Find closest
    for threshold, label in snellen_map:
        if decimal_va >= threshold:
            return label

    denominator = round(6 / decimal_va)
    return f"6/{denominator}"


def _calculate_optimal_print_size(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate optimal Arabic print size based on visual acuity.

    Formula: Minimum print size (pt) = (Reference print size × Reference VA) / Patient VA
    Arabic adjustment: multiply by text complexity factor
    """
    va_input = params.get("visual_acuity")
    text_type = params.get("text_type", "plain")  # plain, diacritical, quran, mixed
    desired_reading_distance = params.get("reading_distance_cm", 40)  # cm
    target_reserve = params.get("magnification_reserve", 2.0)  # 2x reserve for comfort

    if not va_input:
        return {"error": "يرجى تحديد حدة البصر (visual_acuity)"}

    decimal_va = _parse_va_to_decimal(str(va_input))
    if decimal_va is None or decimal_va <= 0:
        return {"error": f"قيمة حدة البصر غير صحيحة: {va_input}"}

    complexity_factor = ARABIC_COMPLEXITY = ARABIC_CHAR_COMPLEXITY.get(text_type, 1.0)

    # M-unit calculation at desired distance
    # 1 M-unit = text readable at 1 metre by person with VA 1.0 (6/6)
    # Minimum print size in M-units = reading_distance(m) / decimal_VA
    reading_distance_m = desired_reading_distance / 100
    minimum_m_units = reading_distance_m / decimal_va

    # Convert M-units to points (1 M-unit ≈ 8.84 pt at standard conditions)
    # More practical: use threshold acuity formula
    # At 40cm, threshold letter size = 0.4 / decimal_VA (in cm)
    threshold_height_cm = reading_distance_m / decimal_va / 10  # Approximate
    threshold_pt = threshold_height_cm * 28.35  # 1 cm ≈ 28.35 pt

    # Apply Arabic complexity
    minimum_pt_arabic = threshold_pt * complexity_factor

    # Apply reserve factor (2x for comfortable reading)
    recommended_pt = minimum_pt_arabic * target_reserve

    # Round to standard print sizes
    standard_sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]

    min_standard = next((s for s in standard_sizes if s >= minimum_pt_arabic), 72)
    recommended_standard = next((s for s in standard_sizes if s >= recommended_pt), 72)

    # Special override for Quran
    if text_type == "quran":
        recommended_standard = max(recommended_standard, 18)
        min_standard = max(min_standard, 16)

    # Determine category
    if decimal_va >= 0.5:
        category = "طبيعي - لا يحتاج تعديلات خاصة"
    elif decimal_va >= 0.3:
        category = "إعاقة بصرية خفيفة - طباعة كبيرة قد تساعد"
    elif decimal_va >= 0.1:
        category = "إعاقة بصرية متوسطة - طباعة كبيرة ضرورية"
    elif decimal_va >= 0.05:
        category = "إعاقة بصرية شديدة - مكبرات مطلوبة"
    else:
        category = "إعاقة بصرية عميقة - مساعدات بصرية متخصصة مطلوبة"

    return {
        "calculation_type": "optimal_print_size",
        "input": {
            "visual_acuity": va_input,
            "decimal_va": round(decimal_va, 3),
            "snellen_6m": _decimal_to_snellen_6m(decimal_va),
            "text_type": text_type,
            "reading_distance_cm": desired_reading_distance,
        },
        "results": {
            "minimum_print_size_pt": round(minimum_pt_arabic, 1),
            "minimum_standard_size_pt": min_standard,
            "recommended_print_size_pt": round(recommended_pt, 1),
            "recommended_standard_size_pt": recommended_standard,
            "minimum_m_units": round(minimum_m_units, 2),
            "complexity_factor": complexity_factor,
        },
        "practical_recommendations": {
            "arabic_plain": f"{recommended_standard} pt",
            "arabic_diacritical": f"{next((s for s in standard_sizes if s >= recommended_pt * 1.3), 72)} pt",
            "quran_reading": f"{max(recommended_standard, 18)} pt",
            "newspaper": "استخدم مكبر إذا الجريدة 8pt" if recommended_standard > 14 else "ممكن قراءة الجريدة",
        },
        "category": category,
        "low_vision_classification": _get_lv_classification(decimal_va),
    }


def _calculate_magnification_needed(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate required magnification for Arabic reading tasks.

    Magnification = Reference size / Current threshold size
                  = Desired reading size / Current minimum readable size
    """
    va_input = params.get("visual_acuity")
    target_material = params.get("target_material", "book_standard")  # newspaper, book_standard, etc.
    current_reading_distance = params.get("current_distance_cm", 40)
    text_type = params.get("text_type", "plain")

    if not va_input:
        return {"error": "يرجى تحديد حدة البصر"}

    decimal_va = _parse_va_to_decimal(str(va_input))
    if decimal_va is None or decimal_va <= 0:
        return {"error": f"قيمة حدة البصر غير صحيحة: {va_input}"}

    # Target print size
    target_pt = ARABIC_PRINT_SIZES.get(target_material, 12)

    # Current threshold at desired distance
    reading_distance_m = current_reading_distance / 100

    # Threshold in pt at current distance
    # Approximate: threshold = distance_cm / decimal_VA / 3.5 (empirical)
    current_threshold_pt = current_reading_distance / decimal_va / 3.5

    # Apply Arabic complexity
    complexity = ARABIC_CHAR_COMPLEXITY.get(text_type, 1.0)
    current_threshold_pt *= complexity

    # Required magnification
    if current_threshold_pt <= target_pt:
        required_magnification = 1.0
        can_read_without_aid = True
    else:
        required_magnification = current_threshold_pt / target_pt
        can_read_without_aid = False

    # Recommended magnification (with 2x reserve)
    recommended_magnification = required_magnification * 2.0

    # Round to available powers
    available_powers = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 16.0, 20.0]

    min_mag = next((p for p in available_powers if p >= required_magnification), 20.0)
    rec_mag = next((p for p in available_powers if p >= recommended_magnification), 20.0)

    # Device suggestions based on magnification
    device_suggestions = _suggest_device_by_magnification(rec_mag, text_type)

    return {
        "calculation_type": "magnification_needed",
        "input": {
            "visual_acuity": va_input,
            "decimal_va": round(decimal_va, 3),
            "target_material": target_material,
            "target_print_size_pt": target_pt,
            "text_type": text_type,
            "reading_distance_cm": current_reading_distance,
        },
        "results": {
            "current_threshold_pt": round(current_threshold_pt, 1),
            "can_read_without_aid": can_read_without_aid,
            "minimum_magnification": round(required_magnification, 1),
            "minimum_standard_power": min_mag,
            "recommended_magnification": round(recommended_magnification, 1),
            "recommended_standard_power": rec_mag,
        },
        "device_suggestions": device_suggestions,
        "arabic_notes": {
            "plain_text": f"تكبير {min_mag}x للنص العادي",
            "diacritical": f"تكبير {next((p for p in available_powers if p >= required_magnification * 1.3), 20.0)}x للنص المشكّل",
            "quran": f"تكبير {next((p for p in available_powers if p >= max(required_magnification * 1.4, 2.0)), 20.0)}x للقرآن الكريم",
        }
    }


def _calculate_working_distance(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate optimal working distance for Arabic reading with given magnification.

    Working distance = Focal length of magnifier
    For a +D diopter lens: focal length (m) = 1/D
    """
    magnification = params.get("magnification_power")
    va_input = params.get("visual_acuity")
    lens_type = params.get("lens_type", "single")  # single, bifocal, prismatic

    if not magnification and not va_input:
        return {"error": "يرجى تحديد قوة التكبير أو حدة البصر"}

    results = {}

    if magnification:
        mag = float(magnification)

        # Diopter power of equivalent lens
        # Magnification = D/4 (near point formula) so D = 4 × Magnification
        diopter_power = mag * 4

        # Working distance
        working_distance_m = 1 / diopter_power if diopter_power > 0 else 0.25
        working_distance_cm = working_distance_m * 100

        results["magnification_based"] = {
            "input_magnification": mag,
            "equivalent_diopters": round(diopter_power, 1),
            "working_distance_cm": round(working_distance_cm, 1),
            "working_distance_mm": round(working_distance_cm * 10, 0),
        }

    if va_input:
        decimal_va = _parse_va_to_decimal(str(va_input))
        if decimal_va and decimal_va > 0:
            # Optimal near working distance based on Kestenbaum rule
            # Kestenbaum reading add (D) = 1/decimal_VA
            kestenbaum_add = 1 / decimal_va
            kestenbaum_distance_cm = 100 / kestenbaum_add

            # With reserve (×2): recommended add = 2/decimal_VA
            reserve_add = 2 / decimal_va
            reserve_distance_cm = 100 / reserve_add

            results["va_based"] = {
                "visual_acuity": va_input,
                "kestenbaum_add_diopters": round(kestenbaum_add, 1),
                "kestenbaum_distance_cm": round(kestenbaum_distance_cm, 1),
                "recommended_add_diopters": round(reserve_add, 1),
                "recommended_distance_cm": round(reserve_distance_cm, 1),
                "arabic_quran_note": f"للقرآن الكريم: يُنصح بـ {max(round(reserve_add * 1.4), int(reserve_add))}D لوضوح التشكيل الكامل",
            }

    # Ergonomics for Arabic/RTL reading
    ergonomics = _arabic_reading_ergonomics(
        working_distance_cm if magnification else results.get("va_based", {}).get("recommended_distance_cm", 40)
    )

    return {
        "calculation_type": "working_distance",
        "results": results,
        "ergonomic_recommendations": ergonomics,
        "rtl_considerations": {
            "reading_direction": "يمين إلى يسار (RTL)",
            "fatigue_note": "القراءة العربية بمسافة قريبة جداً تزيد من التعب البصري",
            "rest_breaks": "استراحة 5-10 دقائق كل 20-30 دقيقة قراءة",
            "lighting": "إضاءة من اليسار لتجنب الظل على النص",
        }
    }


def _estimate_reading_speed(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate Arabic reading speed with low vision and rehabilitation goals.
    """
    va_input = params.get("visual_acuity")
    patient_age = params.get("patient_age", "adult")
    text_type = params.get("text_type", "plain")
    using_aids = params.get("using_aids", False)
    reading_history = params.get("reading_history", "normal")  # normal, slow, impaired

    if not va_input:
        return {"error": "يرجى تحديد حدة البصر"}

    decimal_va = _parse_va_to_decimal(str(va_input))
    if decimal_va is None:
        return {"error": f"قيمة حدة البصر غير صحيحة: {va_input}"}

    # Base speed for age group
    age_category = "average_adult"
    if isinstance(patient_age, int) or (isinstance(patient_age, str) and patient_age.isdigit()):
        age = int(patient_age)
        if age < 9:
            age_category = "child_6_8"
        elif age < 13:
            age_category = "child_9_12"
        elif age > 65:
            age_category = "elderly"
    elif patient_age == "child":
        age_category = "child_9_12"
    elif patient_age == "elderly":
        age_category = "elderly"

    base_norms = ARABIC_READING_NORMS[age_category]
    base_speed = base_norms["avg"]

    # Apply VA reduction factor
    if decimal_va >= 0.5:
        va_factor = 1.0
    elif decimal_va >= 0.3:
        va_factor = 0.85
    elif decimal_va >= 0.2:
        va_factor = 0.70
    elif decimal_va >= 0.1:
        va_factor = 0.50
    elif decimal_va >= 0.05:
        va_factor = 0.30
    else:
        va_factor = 0.15

    # Apply text complexity
    complexity_factor = 1 / ARABIC_CHAR_COMPLEXITY.get(text_type, 1.0)

    # Apply aid benefit
    aid_factor = 1.2 if using_aids else 1.0

    # Estimated speed
    estimated_speed = base_speed * va_factor * complexity_factor * aid_factor

    # Functional categories
    if estimated_speed >= 100:
        functional_category = "قراءة وظيفية كاملة"
        can_read_newspaper = True
        can_read_quran = True
        rehabilitation_goal = "الحفاظ على الأداء الحالي"
    elif estimated_speed >= 60:
        functional_category = "قراءة وظيفية جيدة"
        can_read_newspaper = True
        can_read_quran = True
        rehabilitation_goal = "تحسين السرعة إلى ≥100 كلمة/دقيقة"
    elif estimated_speed >= 40:
        functional_category = "قراءة وظيفية محدودة"
        can_read_newspaper = "مع مساعدات"
        can_read_quran = "مع مساعدات"
        rehabilitation_goal = "تحسين السرعة إلى ≥60 كلمة/دقيقة"
    elif estimated_speed >= 20:
        functional_category = "قراءة متحدية"
        can_read_newspaper = False
        can_read_quran = "مع مساعدات متخصصة"
        rehabilitation_goal = "استخدام مساعدات إلكترونية + تدريب"
    else:
        functional_category = "قراءة شديدة التحدي"
        can_read_newspaper = False
        can_read_quran = "بمساعدة سمعية + بصرية"
        rehabilitation_goal = "النظر في بدائل سمعية + مساعدات تكبير متقدمة"

    # Rehabilitation timeline
    rehab_timeline = _estimate_reading_rehab_timeline(decimal_va, estimated_speed)

    return {
        "calculation_type": "reading_speed_estimation",
        "input": {
            "visual_acuity": va_input,
            "decimal_va": round(decimal_va, 3),
            "age_category": age_category,
            "text_type": text_type,
        },
        "results": {
            "estimated_wpm": round(estimated_speed, 0),
            "functional_category": functional_category,
            "va_reduction_factor": va_factor,
            "text_complexity_factor": round(1 / ARABIC_CHAR_COMPLEXITY.get(text_type, 1.0), 2),
        },
        "functional_reading": {
            "can_read_newspaper": can_read_newspaper,
            "can_read_quran": can_read_quran,
            "can_read_medicine_labels": estimated_speed >= 20,
            "can_read_street_signs": decimal_va >= 0.1,
        },
        "rehabilitation_goal": rehabilitation_goal,
        "expected_improvement": rehab_timeline,
        "arabic_specific": {
            "diacritical_speed_penalty": "25-30% أبطأ مع التشكيل",
            "quran_speed_note": "القرآن يتطلب تركيزاً أعلى للتجويد",
            "rtl_fatigue": "RTL يسبب تعباً أقل لأصحاب ضعف البصر مقارنة بـ LTR عند استخدام مكبرات يدوية",
        }
    }


def _calculate_quran_requirements(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Specific calculations for Quran reading with low vision.

    Special considerations:
    - Full tashkeel (diacritical marks) required
    - Tajweed color coding in some editions
    - Minimum size for waqf marks and ayah numbers
    - Warsh/Hafs font differences
    """
    va_input = params.get("visual_acuity")
    quran_edition = params.get("quran_edition", "standard")  # standard, tajweed, warsh, uthmani
    desired_distance_cm = params.get("desired_distance_cm", 40)
    patient_age = params.get("patient_age", "adult")

    if not va_input:
        return {"error": "يرجى تحديد حدة البصر"}

    decimal_va = _parse_va_to_decimal(str(va_input))
    if decimal_va is None or decimal_va <= 0:
        return {"error": f"قيمة حدة البصر غير صحيحة: {va_input}"}

    # Quran editions and their minimum readable sizes
    edition_requirements = {
        "standard": {"min_pt": 14, "name": "مصحف قياسي", "complexity": 1.4},
        "tajweed": {"min_pt": 16, "name": "مصحف التجويد الملوّن", "complexity": 1.5},
        "warsh": {"min_pt": 14, "name": "رواية ورش", "complexity": 1.45},
        "uthmani": {"min_pt": 16, "name": "المصحف العثماني", "complexity": 1.5},
        "large_print": {"min_pt": 20, "name": "مصحف كبير الخط", "complexity": 1.4},
        "bilingual": {"min_pt": 12, "name": "مصحف مع ترجمة", "complexity": 1.3},
    }

    edition_data = edition_requirements.get(quran_edition, edition_requirements["standard"])
    complexity = edition_data["complexity"]

    # Calculate threshold
    reading_distance_m = desired_distance_cm / 100
    threshold_pt_raw = (reading_distance_m / decimal_va) * 100  # rough estimate
    threshold_pt_arabic = threshold_pt_raw * complexity

    # More accurate: based on angular resolution
    # Angular threshold = 1/VA (in decimal arc minutes converted to size at distance)
    angular_threshold_arcmin = 1 / decimal_va  # arc minutes for 1.0 = 1 arc min
    threshold_height_cm = 2 * reading_distance_m * math.tan(math.radians(angular_threshold_arcmin / 60))
    threshold_pt_accurate = threshold_height_cm * 100 * 2.835  # cm to pt
    threshold_pt_with_complexity = threshold_pt_accurate * complexity

    # Quran-specific minimum
    quran_minimum_pt = max(threshold_pt_with_complexity * 2, edition_data["min_pt"])

    # Available Quran sizes
    quran_standard_sizes = [14, 16, 18, 20, 24, 28, 32, 36, 48]
    recommended_quran_size = next((s for s in quran_standard_sizes if s >= quran_minimum_pt), 48)

    # Can they read standard Quran?
    can_read_standard = threshold_pt_with_complexity <= 14
    can_read_large_print = threshold_pt_with_complexity <= 20

    # Magnification for standard Quran (14pt)
    if threshold_pt_with_complexity > 14:
        mag_for_standard = threshold_pt_with_complexity / 14
    else:
        mag_for_standard = 1.0

    # Device recommendations
    quran_devices = _recommend_quran_devices(decimal_va, mag_for_standard)

    # Digital Quran options
    digital_options = []
    if decimal_va < 0.3:
        digital_options.extend([
            "تطبيق مصحف مع تكبير النص (متاح على iOS/Android)",
            "جهاز قارئ القرآن الإلكتروني مع شاشة كبيرة",
            "مصحف إلكتروني مضيء",
        ])
    if decimal_va < 0.1:
        digital_options.extend([
            "تطبيق استماع للقرآن الكريم مع متابعة النص",
            "قارئ القرآن الصوتي",
            "مصحف برايل",
        ])

    # Psychological consideration
    psychological_note = ""
    if decimal_va < 0.1:
        psychological_note = "⚠️ صعوبة قراءة القرآن تؤثر نفسياً على المريض - يجب مناقشة البدائل بحساسية واحترام"

    return {
        "calculation_type": "quran_requirements",
        "input": {
            "visual_acuity": va_input,
            "decimal_va": round(decimal_va, 3),
            "quran_edition": edition_data["name"],
            "desired_distance_cm": desired_distance_cm,
        },
        "results": {
            "threshold_pt_without_tashkeel": round(threshold_pt_accurate, 1),
            "threshold_pt_with_tashkeel": round(threshold_pt_with_complexity, 1),
            "minimum_quran_size_pt": round(quran_minimum_pt, 1),
            "recommended_quran_size_pt": recommended_quran_size,
            "can_read_standard_quran_14pt": can_read_standard,
            "can_read_large_print_quran_20pt": can_read_large_print,
            "magnification_for_standard_quran": round(mag_for_standard, 1),
        },
        "practical_recommendations": {
            "best_quran_size": f"{recommended_quran_size} pt",
            "recommended_devices": quran_devices,
            "digital_options": digital_options if digital_options else ["المصحف الورقي بالحجم الموصى به كافٍ"],
            "lighting_requirements": "إضاءة موجهة ≥500 lux للنص المشكّل",
            "rest_recommendations": "استراحة كل 20 دقيقة - القراءة المشكّلة مجهدة بصرياً",
        },
        "tajweed_special_note": (
            "ملاحظة التجويد: مصاحف التجويد الملوّنة تتطلب تكبيراً إضافياً 20-30% "
            "لتمييز الألوان المختلفة عند ضعف الحساسية للتباين"
        ),
        "psychological_note": psychological_note,
    }


def _full_arabic_assessment(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive Arabic reading assessment combining all calculations.
    """
    va_input = params.get("visual_acuity")
    if not va_input:
        return {"error": "يرجى تحديد حدة البصر (visual_acuity)"}

    decimal_va = _parse_va_to_decimal(str(va_input))
    if decimal_va is None or decimal_va <= 0:
        return {"error": f"قيمة حدة البصر غير صحيحة: {va_input}"}

    patient_age = params.get("patient_age", "adult")
    reading_goals = params.get("reading_goals", ["newspaper", "quran", "book"])

    # Run all calculations
    print_size_result = _calculate_optimal_print_size({
        "visual_acuity": va_input,
        "text_type": "plain",
        "reading_distance_cm": 40,
    })

    diacritical_size_result = _calculate_optimal_print_size({
        "visual_acuity": va_input,
        "text_type": "diacritical",
        "reading_distance_cm": 40,
    })

    magnification_result = _calculate_magnification_needed({
        "visual_acuity": va_input,
        "target_material": "book_standard",
        "text_type": "plain",
    })

    quran_result = _calculate_quran_requirements({
        "visual_acuity": va_input,
        "quran_edition": "standard",
        "desired_distance_cm": 40,
        "patient_age": patient_age,
    })

    speed_result = _estimate_reading_speed({
        "visual_acuity": va_input,
        "text_type": "plain",
        "patient_age": patient_age,
    })

    working_dist_result = _calculate_working_distance({
        "visual_acuity": va_input,
    })

    # Compile summary
    summary = {
        "patient_va": va_input,
        "decimal_va": round(decimal_va, 3),
        "snellen": _decimal_to_snellen_6m(decimal_va),
        "lv_classification": _get_lv_classification(decimal_va),
    }

    # Key recommendations
    recommendations = {
        "optimal_plain_arabic_pt": print_size_result.get("results", {}).get("recommended_standard_size_pt"),
        "optimal_diacritical_pt": diacritical_size_result.get("results", {}).get("recommended_standard_size_pt"),
        "optimal_quran_pt": quran_result.get("results", {}).get("recommended_quran_size_pt"),
        "required_magnification": magnification_result.get("results", {}).get("recommended_standard_power"),
        "estimated_reading_speed_wpm": speed_result.get("results", {}).get("estimated_wpm"),
        "recommended_reading_distance_cm": working_dist_result.get("results", {}).get("va_based", {}).get("recommended_distance_cm"),
        "functional_reading_category": speed_result.get("results", {}).get("functional_category"),
    }

    # Priority interventions
    interventions = []
    if decimal_va < 0.3:
        interventions.append("تقييم المكبرات البصرية المناسبة")
    if decimal_va < 0.2:
        interventions.append("جهاز تكبير إلكتروني (CCTV/Tablet)")
    if decimal_va < 0.1:
        interventions.append("مصادر قرآنية صوتية/رقمية")
    interventions.append("تحسين إضاءة بيئة القراءة")
    if float(speed_result.get("results", {}).get("estimated_wpm", 100)) < 60:
        interventions.append("تدريب على مهارات القراءة بضعف البصر")

    return {
        "calculation_type": "full_arabic_assessment",
        "summary": summary,
        "key_recommendations": recommendations,
        "priority_interventions": interventions,
        "detailed_results": {
            "print_size_plain": print_size_result.get("results"),
            "print_size_diacritical": diacritical_size_result.get("results"),
            "magnification": magnification_result.get("results"),
            "quran": quran_result.get("results"),
            "reading_speed": speed_result.get("results"),
        },
        "quran_devices": quran_result.get("practical_recommendations", {}).get("recommended_devices", []),
        "rtl_ergonomics": working_dist_result.get("rtl_considerations", {}),
    }


# --- Helper Functions ---

def _get_lv_classification(decimal_va: float) -> str:
    """Get WHO/ICD-11 visual impairment classification."""
    if decimal_va >= 0.3:
        return "طبيعي أو قريب من الطبيعي"
    elif decimal_va >= 0.1:
        return "إعاقة بصرية متوسطة (WHO Category 1)"
    elif decimal_va >= 0.05:
        return "إعاقة بصرية شديدة (WHO Category 2)"
    elif decimal_va >= 0.02:
        return "إعاقة بصرية عميقة (WHO Category 3)"
    elif decimal_va > 0:
        return "كفيف تقريباً (WHO Category 4)"
    else:
        return "كفيف كلياً (WHO Category 5)"


def _suggest_device_by_magnification(magnification: float, text_type: str) -> list:
    """Suggest appropriate devices based on required magnification."""
    devices = []

    if magnification <= 2.0:
        devices.append("نظارات قراءة قوية (reading spectacles)")
        if text_type in ["quran", "diacritical"]:
            devices.append("عدسة مكبرة بضوء +8D")
    elif magnification <= 4.0:
        devices.append("مكبر يدوي 4-8x")
        devices.append("نظارات مع عدسات مكبرة")
    elif magnification <= 8.0:
        devices.append("مكبر يدوي 8-16x")
        devices.append("مكبر قائم (stand magnifier)")
        devices.append("جهاز CCTV (تلفزيون المساعدة)")
    else:
        devices.append("جهاز CCTV للقراءة")
        devices.append("تطبيق تكبير على الجهاز اللوحي")
        devices.append("كاميرا عرض مع شاشة كبيرة")

    return devices


def _recommend_quran_devices(decimal_va: float, required_mag: float) -> list:
    """Recommend specific devices for Quran reading."""
    devices = []

    if decimal_va >= 0.3:
        devices.append("مصحف كبير الخط 18-20pt")
    elif decimal_va >= 0.2:
        devices.append("مصحف كبير الخط 24pt")
        devices.append("مكبر يدوي بإضاءة")
    elif decimal_va >= 0.1:
        devices.append("مكبر إلكتروني يدوي (digital handheld)")
        devices.append(f"مصحف مكبّر {required_mag:.0f}x على تطبيق")
        devices.append("جهاز CCTV مع مصحف")
    else:
        devices.append("تطبيق مصحف مع تكبير شاشة كامل")
        devices.append("قارئ نصوص إلكتروني بصوت")
        devices.append("استماع لتلاوة مصحوبة بمتابعة النص على شاشة كبيرة")

    return devices


def _arabic_reading_ergonomics(working_distance_cm: float) -> dict:
    """Provide ergonomic recommendations for Arabic reading."""
    if working_distance_cm < 15:
        posture = "مسافة قريبة جداً - احرص على وضعية جلوس مريحة ودعم للذراعين"
        fatigue_risk = "مرتفع"
    elif working_distance_cm < 25:
        posture = "مسافة قريبة - استخدم حامل كتب لتثبيت الزاوية المناسبة"
        fatigue_risk = "متوسط-مرتفع"
    elif working_distance_cm <= 40:
        posture = "مسافة مناسبة - وضعية الجلوس المريحة كافية"
        fatigue_risk = "منخفض"
    else:
        posture = "مسافة بعيدة نسبياً - قد تحتاج لحامل كتب أو منضدة مائلة"
        fatigue_risk = "منخفض"

    return {
        "working_distance_cm": round(working_distance_cm, 1),
        "posture_recommendation": posture,
        "fatigue_risk": fatigue_risk,
        "lighting_recommendation": "إضاءة خلفية موجهة من الكتف الأيسر (لمنع الظل عند القراءة RTL)",
        "rest_protocol": "قاعدة 20-20-20: كل 20 دقيقة، انظر 20 قدم (6م) لمدة 20 ثانية",
        "reading_stand": working_distance_cm < 30,
        "contrast_enhancement": "استخدم ورق أبيض لامع أو شاشة بتباين عالٍ (نص أسود / خلفية بيضاء أو صفراء)",
    }


def _estimate_reading_rehab_timeline(decimal_va: float, current_speed: float) -> dict:
    """Estimate rehabilitation timeline for reading improvement."""
    if decimal_va >= 0.3:
        target_wpm = 150
        months = 1
        sessions = 4
    elif decimal_va >= 0.2:
        target_wpm = 120
        months = 2
        sessions = 8
    elif decimal_va >= 0.1:
        target_wpm = 80
        months = 3
        sessions = 12
    elif decimal_va >= 0.05:
        target_wpm = 50
        months = 4
        sessions = 16
    else:
        target_wpm = 30
        months = 6
        sessions = 24

    return {
        "current_estimated_wpm": round(current_speed, 0),
        "target_wpm": target_wpm,
        "expected_months": months,
        "recommended_sessions": sessions,
        "note": "التوقعات تقريبية وتعتمد على التحفيز والممارسة المنتظمة",
    }
