"""
Fixation Stability Analyzer — محلل ثبات التثبيت
================================================
يحسب BCEA (Bivariate Contour Ellipse Area) من إحداثيات تتبع العين
لتقييم جودة التثبيت اللامركزي (PRL) في مرضى الـ AMD.

المرجع العلمي:
  Crossland & Rubin (2002). The use of an infrared eyetracker to measure
  fixation stability. Optometry & Vision Science, 79(11), 735-739.
"""

import math
from typing import List, Tuple, Optional

# ── ثوابت كاي-تربيع ──
# chi2.ppf(p, df=2) لمستويات ثقة شائعة
CHI2_VALUES = {
    0.50: 1.3863,
    0.68: 2.2789,
    0.90: 4.6052,
    0.95: 5.9915,
    0.99: 9.2103,
}


class FixationStabilityAnalyzer:
    """
    محلل ثبات التثبيت بناءً على حساب BCEA.

    BCEA = π × χ² × σx × σy × √(1 - ρ²)

    حيث:
      σx, σy = الانحراف المعياري لإحداثيات العين
      ρ = معامل ارتباط بيرسون بين x و y
      χ² = قيمة كاي-تربيع للمستوى الاحتمالي المطلوب
    """

    def __init__(self, probability_level: float = 0.68):
        if probability_level not in CHI2_VALUES:
            closest = min(CHI2_VALUES.keys(), key=lambda k: abs(k - probability_level))
            probability_level = closest
        self.probability_level = probability_level
        self.chi_sq_val = CHI2_VALUES[probability_level]

    def calculate_bcea(self, x_coords: List[float], y_coords: List[float]) -> float:
        """
        حساب BCEA بالدرجات المربعة (deg²).

        Args:
            x_coords: إحداثيات X لنقاط التثبيت (بالدرجات البصرية)
            y_coords: إحداثيات Y لنقاط التثبيت

        Returns:
            مساحة BCEA بالدرجات المربعة. inf إذا البيانات غير كافية.
        """
        n = len(x_coords)
        if n < 3 or len(y_coords) < 3 or n != len(y_coords):
            return float("inf")

        # المتوسطات
        mean_x = sum(x_coords) / n
        mean_y = sum(y_coords) / n

        # الانحراف المعياري (population)
        var_x = sum((xi - mean_x) ** 2 for xi in x_coords) / n
        var_y = sum((yi - mean_y) ** 2 for yi in y_coords) / n
        std_x = math.sqrt(var_x)
        std_y = math.sqrt(var_y)

        if std_x == 0 or std_y == 0:
            return 0.0  # تثبيت مثالي

        # معامل الارتباط (بيرسون)
        cov_xy = sum((x_coords[i] - mean_x) * (y_coords[i] - mean_y) for i in range(n)) / n
        rho = cov_xy / (std_x * std_y)
        rho = max(-0.999, min(0.999, rho))  # تجنب sqrt سالب

        # BCEA = π × χ² × σx × σy × √(1 - ρ²)
        bcea = math.pi * self.chi_sq_val * std_x * std_y * math.sqrt(1 - rho ** 2)
        return round(bcea, 4)

    def classify_stability(self, bcea: float) -> dict:
        """
        تصنيف ثبات التثبيت وفق معايير Fujii (2003).

        Returns:
            dict مع: grade, label, label_ar, description
        """
        if bcea <= 1.0:
            return {
                "grade": "stable",
                "label": "Stable Fixation",
                "label_ar": "تثبيت مستقر",
                "description": "BCEA ≤ 1.0 deg² — Excellent fixation, comparable to normal foveal fixation.",
            }
        elif bcea <= 4.0:
            return {
                "grade": "relatively_stable",
                "label": "Relatively Stable",
                "label_ar": "تثبيت مستقر نسبياً",
                "description": "BCEA 1.0–4.0 deg² — Good eccentric fixation. PRL is functional.",
            }
        elif bcea <= 10.0:
            return {
                "grade": "relatively_unstable",
                "label": "Relatively Unstable",
                "label_ar": "تثبيت غير مستقر نسبياً",
                "description": "BCEA 4.0–10.0 deg² — Training may improve stability.",
            }
        else:
            return {
                "grade": "unstable",
                "label": "Unstable Fixation",
                "label_ar": "تثبيت غير مستقر",
                "description": "BCEA > 10.0 deg² — Significant instability. Biofeedback training strongly indicated.",
            }

    def estimate_prl_location(
        self, x_coords: List[float], y_coords: List[float]
    ) -> dict:
        """
        تقدير موقع نقطة التثبيت اللامركزي (PRL).

        Returns:
            dict مع: x, y (متوسط الموقع), eccentricity (المسافة من المركز),
            quadrant (الربع البصري)
        """
        n = len(x_coords)
        if n == 0:
            return {"x": 0, "y": 0, "eccentricity": 0, "quadrant": "unknown"}

        cx = sum(x_coords) / n
        cy = sum(y_coords) / n
        eccentricity = math.sqrt(cx ** 2 + cy ** 2)

        if cx >= 0 and cy >= 0:
            quadrant = "superior_temporal"
        elif cx < 0 and cy >= 0:
            quadrant = "superior_nasal"
        elif cx < 0 and cy < 0:
            quadrant = "inferior_nasal"
        else:
            quadrant = "inferior_temporal"

        return {
            "x": round(cx, 2),
            "y": round(cy, 2),
            "eccentricity_deg": round(eccentricity, 2),
            "quadrant": quadrant,
        }

    def evaluate_progress(
        self,
        session1_coords: Tuple[List[float], List[float]],
        session2_coords: Tuple[List[float], List[float]],
    ) -> dict:
        """
        مقارنة جلستين لتقييم تأثير تدريب الارتجاع البيولوجي.

        Args:
            session1_coords: (x_list, y_list) لجلسة سابقة
            session2_coords: (x_list, y_list) لجلسة لاحقة

        Returns:
            dict مع: status, bcea_before, bcea_after, improvement_pct, action
        """
        bcea_1 = self.calculate_bcea(*session1_coords)
        bcea_2 = self.calculate_bcea(*session2_coords)

        stability_1 = self.classify_stability(bcea_1)
        stability_2 = self.classify_stability(bcea_2)

        prl_before = self.estimate_prl_location(*session1_coords)
        prl_after = self.estimate_prl_location(*session2_coords)

        if bcea_1 == 0 or bcea_1 == float("inf"):
            improvement = 0.0
        else:
            improvement = ((bcea_1 - bcea_2) / bcea_1) * 100

        if improvement > 15:
            status = "significant_improvement"
            status_ar = "تحسن ملحوظ"
            action = "Continue current PRL training with biofeedback"
            action_ar = "استمرار التدريب الحالي على PRL مع الارتجاع البيولوجي"
        elif improvement > 0:
            status = "slight_improvement"
            status_ar = "تحسن طفيف"
            action = "Increase auditory biofeedback sensitivity; consider adjusting TRL location"
            action_ar = "زيادة حساسية الارتجاع السمعي؛ إعادة تقييم موقع TRL"
        else:
            status = "no_improvement"
            status_ar = "لا تحسن"
            action = "Re-evaluate chosen Retinal Locus (TRL). Consider alternative PRL location."
            action_ar = "إعادة تقييم منطقة الشبكية المختارة (TRL). تجربة موقع PRL بديل."

        return {
            "status": status,
            "status_ar": status_ar,
            "bcea_before": bcea_1,
            "bcea_after": bcea_2,
            "stability_before": stability_1,
            "stability_after": stability_2,
            "improvement_pct": round(improvement, 1),
            "prl_before": prl_before,
            "prl_after": prl_after,
            "action": action,
            "action_ar": action_ar,
        }


def run_fixation_assessment(params: dict) -> dict:
    """
    واجهة الأداة لمحلل ثبات التثبيت.

    Args:
        params: dict مع:
          - action: "calculate_bcea" | "evaluate_progress" | "full_assessment"
          - x_coords / y_coords: list
          - session1_x, session1_y, session2_x, session2_y: lists (لـ evaluate_progress)
          - probability_level: float (default 0.68)
    """
    prob = params.get("probability_level", 0.68)
    analyzer = FixationStabilityAnalyzer(prob)
    action = params.get("action", "full_assessment")

    if action == "calculate_bcea":
        x = params.get("x_coords", [])
        y = params.get("y_coords", [])
        bcea = analyzer.calculate_bcea(x, y)
        stability = analyzer.classify_stability(bcea)
        prl = analyzer.estimate_prl_location(x, y)
        return {"bcea": bcea, "stability": stability, "prl_location": prl}

    elif action == "evaluate_progress":
        s1 = (params.get("session1_x", []), params.get("session1_y", []))
        s2 = (params.get("session2_x", []), params.get("session2_y", []))
        return analyzer.evaluate_progress(s1, s2)

    elif action == "full_assessment":
        x = params.get("x_coords", [])
        y = params.get("y_coords", [])
        bcea = analyzer.calculate_bcea(x, y)
        return {
            "bcea_deg2": bcea,
            "bcea_log": round(math.log10(bcea), 2) if bcea > 0 and bcea != float("inf") else None,
            "stability": analyzer.classify_stability(bcea),
            "prl_location": analyzer.estimate_prl_location(x, y),
            "probability_level": prob,
            "n_fixation_points": len(x),
        }

    return {"error": f"Unknown action: {action}"}
