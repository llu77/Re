"""
Visual Calculator — الحاسبة البصرية المتخصصة
=============================================
تحويلات حدة الإبصار وحسابات التكبير والطباعة
"""

import math
from typing import Union


def calculate_visual_params(params: dict) -> dict:
    """
    تنفيذ الحسابات البصرية المطلوبة

    Args:
        params: {
            calculation_type: نوع الحساب
            input_values: القيم المدخلة
        }
    """
    calc_type = params.get("calculation_type", "")
    values = params.get("input_values", {})

    calculators = {
        "va_conversion": _convert_visual_acuity,
        "magnification_power": _calculate_magnification,
        "print_size": _estimate_print_size,
        "working_distance": _calculate_working_distance,
    }

    if calc_type not in calculators:
        return {
            "error": f"نوع الحساب '{calc_type}' غير مدعوم",
            "supported_types": list(calculators.keys())
        }

    return calculators[calc_type](values)


# ─────────────────────────────────────────────
# 1. تحويل حدة الإبصار
# ─────────────────────────────────────────────

def _convert_visual_acuity(values: dict) -> dict:
    """
    تحويل حدة الإبصار بين المقاييس:
    - Snellen (6/x أو 20/x)
    - LogMAR
    - Decimal

    input_values: {"from_format": "snellen_metric", "value": "6/60"}
    """
    from_format = values.get("from_format", "").lower()
    value = values.get("value", "")

    if not value:
        return {"error": "يجب تحديد القيمة"}

    try:
        # تحويل إلى Decimal أولاً كقيمة وسيطة
        decimal_va = _to_decimal(from_format, str(value))

        if decimal_va is None or decimal_va <= 0:
            return {"error": "قيمة حدة الإبصار غير صالحة"}

        # حساب LogMAR
        logmar = round(-math.log10(decimal_va), 2)

        # حساب Snellen المترية (6/x)
        snellen_metric_denominator = round(6 / decimal_va)
        snellen_metric = f"6/{snellen_metric_denominator}"

        # حساب Snellen الإمبريالية (20/x)
        snellen_imperial_denominator = round(20 / decimal_va)
        snellen_imperial = f"20/{snellen_imperial_denominator}"

        # تصنيف WHO
        who_category = _who_vi_category(decimal_va)

        return {
            "decimal": round(decimal_va, 3),
            "logmar": logmar,
            "snellen_metric": snellen_metric,
            "snellen_imperial": snellen_imperial,
            "who_category": who_category,
            "input_format": from_format,
            "input_value": str(value)
        }

    except (ValueError, ZeroDivisionError) as e:
        return {"error": f"خطأ في التحويل: {str(e)}"}


def _to_decimal(fmt: str, value: str) -> Union[float, None]:
    """تحويل أي صيغة لقيمة Decimal"""

    if fmt in ("snellen_metric", "snellen_6"):
        # مثال: "6/60" أو "6/36"
        if "/" in value:
            parts = value.split("/")
            return float(parts[0]) / float(parts[1])
        return None

    elif fmt in ("snellen_imperial", "snellen_20"):
        # مثال: "20/200" أو "20/40"
        if "/" in value:
            parts = value.split("/")
            return float(parts[0]) / float(parts[1])
        return None

    elif fmt == "logmar":
        logmar_val = float(value)
        return round(10 ** (-logmar_val), 3)

    elif fmt == "decimal":
        return float(value)

    else:
        # محاولة تلقائية
        if "/" in value:
            parts = value.split("/")
            return float(parts[0]) / float(parts[1])
        return float(value)


def _who_vi_category(decimal_va: float) -> str:
    """تصنيف ضعف البصر حسب WHO (ICD-11)"""
    if decimal_va >= 0.3:
        return "طبيعي أو قريب من الطبيعي"
    elif decimal_va >= 0.1:
        return "ضعف بصري معتدل (Moderate VI) — الفئة 1"
    elif decimal_va >= 0.05:
        return "ضعف بصري شديد (Severe VI) — الفئة 2"
    elif decimal_va >= 0.02:
        return "ضعف بصري عميق / إعاقة بصرية (Profound VI) — الفئة 3"
    elif decimal_va > 0:
        return "إدراك الضوء فقط — الفئة 4"
    else:
        return "لا إدراك للضوء (NLP) — الفئة 5 / العمى"


# ─────────────────────────────────────────────
# 2. حساب قوة العدسة المكبرة
# ─────────────────────────────────────────────

def _calculate_magnification(values: dict) -> dict:
    """
    حساب قوة التكبير المطلوبة للقراءة

    input_values: {
        "visual_acuity_decimal": 0.1,    # حدة الإبصار الحالية
        "target_print_size_N": 8,         # حجم الطباعة المستهدف (N8 = قراءة عادية)
        "reading_distance_cm": 40         # مسافة القراءة (اختيارية، افتراضي: 40)
    }

    الصيغة: M = VA_needed / VA_current
    أو: M = target_N_size / current_threshold_N_size
    """
    va_decimal = values.get("visual_acuity_decimal")
    target_n = values.get("target_print_size_N", 8)
    reading_distance = values.get("reading_distance_cm", 40)

    if va_decimal is None:
        return {"error": "يجب تحديد حدة الإبصار (visual_acuity_decimal)"}

    try:
        va_decimal = float(va_decimal)
        target_n = float(target_n)
        reading_distance = float(reading_distance)

        if va_decimal <= 0:
            return {"error": "حدة الإبصار يجب أن تكون أكبر من صفر"}

        # N8 تتطلب حدة إبصار 0.3 (6/20) كحد أدنى عند 40 سم
        # الصيغة: حجم الطباعة يتناسب عكسياً مع حدة الإبصار
        # N1 ≈ حدة إبصار 1.0 decimal عند 40 سم
        # N8 ≈ حدة إبصار 0.125 decimal عند 40 سم
        threshold_n_at_normal_va = target_n
        required_va_for_target = threshold_n_at_normal_va / 64  # N1 = 1/64 decimal rough approximation

        # حساب التكبير المطلوب
        magnification_needed = required_va_for_target / va_decimal if va_decimal > 0 else None

        # الطريقة الأبسط والأكثر استخداماً سريرياً:
        # M = target_VA / current_VA = (0.3) / (current_decimal) للقراءة N8
        standard_reading_va = 0.3  # ما يلزم لقراءة N8 بشكل مريح
        magnification_simple = round(standard_reading_va / va_decimal, 1)

        # حساب قوة العدسة بالديوبتر (D = M × 2.5 للعدسة المكبرة القياسية)
        lens_power_diopter = round(magnification_simple * 2.5, 1)

        # مسافة العمل مع العدسة (f = 100/D سم)
        working_distance_with_lens = round(100 / lens_power_diopter, 1) if lens_power_diopter > 0 else None

        return {
            "current_va_decimal": va_decimal,
            "target_print_size": f"N{int(target_n)}",
            "recommended_magnification": f"{magnification_simple}x",
            "lens_power_diopter": f"{lens_power_diopter}D",
            "working_distance_with_lens_cm": working_distance_with_lens,
            "note": "هذا تقدير أولي. يجب تجربة العدسة مع المريض للوصول للقوة المثلى",
            "formula_used": f"M = {standard_reading_va} (VA للقراءة المريحة) ÷ {va_decimal} (VA الحالي)"
        }

    except (ValueError, ZeroDivisionError) as e:
        return {"error": f"خطأ في الحساب: {str(e)}"}


# ─────────────────────────────────────────────
# 3. تقدير حجم الطباعة المناسب
# ─────────────────────────────────────────────

def _estimate_print_size(values: dict) -> dict:
    """
    تقدير حجم الطباعة المناسب بدون مكبر

    input_values: {
        "visual_acuity_decimal": 0.1,
        "reading_distance_cm": 40
    }
    """
    va_decimal = values.get("visual_acuity_decimal")
    reading_distance = values.get("reading_distance_cm", 40)

    if va_decimal is None:
        return {"error": "يجب تحديد حدة الإبصار"}

    try:
        va_decimal = float(va_decimal)
        reading_distance = float(reading_distance)

        if va_decimal <= 0:
            return {"error": "حدة الإبصار يجب أن تكون أكبر من صفر"}

        # حجم الطباعة المقروء (N-notation)
        # N1 عند VA=1.0 decimal و 40 سم → N = (0.3 / VA) × 8 تقريباً
        readable_n_size = round((0.3 / va_decimal) * 8)

        # حجم النقطة (pt) المقابل
        # N8 ≈ 12pt, N1 ≈ 1.5pt
        font_pt = round(readable_n_size * 1.5)

        # تصنيف مستوى الطباعة
        if readable_n_size <= 8:
            level = "يستطيع قراءة طباعة عادية (N8)"
        elif readable_n_size <= 12:
            level = "يحتاج طباعة كبيرة (Large Print)"
        elif readable_n_size <= 20:
            level = "يحتاج طباعة كبيرة جداً أو مكبر"
        else:
            level = "يحتاج مكبر إلكتروني أو قارئ شاشة"

        return {
            "visual_acuity_decimal": va_decimal,
            "reading_distance_cm": reading_distance,
            "minimum_readable_n_size": f"N{readable_n_size}",
            "approximate_font_pt": f"{font_pt}pt",
            "assessment": level,
            "recommendation": _get_print_recommendation(readable_n_size)
        }

    except (ValueError, ZeroDivisionError) as e:
        return {"error": f"خطأ في الحساب: {str(e)}"}


def _get_print_recommendation(n_size: int) -> str:
    if n_size <= 8:
        return "يمكن استخدام مواد الطباعة العادية"
    elif n_size <= 12:
        return "كتب Large Print (18pt+)، تكبير شاشة 150%"
    elif n_size <= 20:
        return "مكبر بصري (3-5x)، تكبير شاشة 200-300%، تطبيقات قراءة"
    else:
        return "مكبر إلكتروني (CCTV/EVES)، Text-to-Speech، قارئ شاشة"


# ─────────────────────────────────────────────
# 4. حساب مسافة العمل المثالية
# ─────────────────────────────────────────────

def _calculate_working_distance(values: dict) -> dict:
    """
    حساب المسافة المثالية للعمل/القراءة

    input_values: {
        "lens_power_diopter": 10,         # قوة العدسة بالديوبتر
        "preferred_retinal_locus": false   # استخدام PRL (اختياري)
    }
    أو:
    input_values: {
        "magnification": 4,               # قوة التكبير (x)
    }
    """
    lens_power = values.get("lens_power_diopter")
    magnification = values.get("magnification")

    try:
        if lens_power is not None:
            lens_power = float(lens_power)
            if lens_power <= 0:
                return {"error": "قوة العدسة يجب أن تكون أكبر من صفر"}

            # مسافة التركيز البؤري = 100/D سم
            focal_distance_cm = round(100 / lens_power, 1)
            # مسافة العمل الفعلية أقل قليلاً من البؤرية
            working_distance_cm = round(focal_distance_cm * 0.9, 1)

            return {
                "lens_power_diopter": lens_power,
                "focal_distance_cm": focal_distance_cm,
                "recommended_working_distance_cm": working_distance_cm,
                "formula": f"f = 100 / {lens_power}D = {focal_distance_cm} سم",
                "note": "مسافة العمل الفعلية عادةً أقل 10% من المسافة البؤرية"
            }

        elif magnification is not None:
            magnification = float(magnification)
            if magnification <= 0:
                return {"error": "قوة التكبير يجب أن تكون أكبر من صفر"}

            # D = M × 2.5 (قياسي)
            equivalent_diopter = magnification * 2.5
            focal_distance_cm = round(100 / equivalent_diopter, 1)
            working_distance_cm = round(focal_distance_cm * 0.9, 1)

            return {
                "magnification": f"{magnification}x",
                "equivalent_diopter": f"{equivalent_diopter}D",
                "focal_distance_cm": focal_distance_cm,
                "recommended_working_distance_cm": working_distance_cm,
                "formula": f"D = {magnification}x × 2.5 = {equivalent_diopter}D → f = {focal_distance_cm} سم"
            }

        else:
            return {"error": "يجب تحديد إما قوة العدسة (lens_power_diopter) أو قوة التكبير (magnification)"}

    except (ValueError, ZeroDivisionError) as e:
        return {"error": f"خطأ في الحساب: {str(e)}"}
