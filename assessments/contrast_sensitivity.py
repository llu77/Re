"""
Contrast Sensitivity Assessment — تقييم حساسية التباين
=====================================================
محاكاة اختبار Pelli-Robson رقمي مع خوارزمية عتبة تكيّفية.
يحسب عتبة حساسية التباين (LogCS) للمريض.

المرجع العلمي:
  Pelli DG, Robson JG, Wilkins AJ (1988). The design of a new letter chart
  for measuring contrast sensitivity. Clinical Vision Sciences, 2(3), 187-199.
"""

import math
from typing import List, Optional


# ── Pelli-Robson Triplets ──
# كل مجموعة ثلاثية (Triplet) لها نفس مستوى التباين
# اللوحة تبدأ من 0.00 LogCS (تباين 100%) وتنتهي عند 2.25 LogCS (0.56%)
PELLI_ROBSON_LEVELS = [
    0.00, 0.15, 0.30, 0.45, 0.60, 0.75,
    0.90, 1.05, 1.20, 1.35, 1.50, 1.65,
    1.80, 1.95, 2.10, 2.25,
]


class ContrastSensitivityAssessment:
    """
    تقييم حساسية التباين بأسلوب Pelli-Robson الرقمي.

    LogCS = -log10(contrast_threshold)
    contrast = 10^(-LogCS)

    قيم مرجعية (Normative):
      - طبيعي: LogCS ≥ 1.65
      - خفيف: 1.35–1.65
      - متوسط: 1.05–1.35
      - شديد: < 1.05
    """

    def __init__(self):
        self.levels = PELLI_ROBSON_LEVELS

    def run_adaptive_test(self, responses: List[dict]) -> dict:
        """
        اختبار تكيّفي: يعرض حروف بتباين متناقص.

        Args:
            responses: list of dicts:
                - log_cs_level: float (مستوى LogCS المعروض)
                - letters_correct: int (0–3 حروف صحيحة من 3)

        Returns:
            dict مع: threshold_logcs, contrast_pct, classification, recommendations
        """
        if not responses:
            return {"error": "No responses provided"}

        # ترتيب من الأعلى تبايناً (أسهل) للأقل
        responses_sorted = sorted(responses, key=lambda r: r["log_cs_level"])

        # Pelli-Robson scoring: آخر مستوى رأى فيه المريض ≥2 من 3 حروف
        threshold = 0.0
        for r in responses_sorted:
            if r["letters_correct"] >= 2:
                threshold = r["log_cs_level"]
            else:
                break  # توقف عند أول فشل

        contrast_pct = round(10 ** (-threshold) * 100, 2)
        classification = self._classify_cs(threshold)
        recommendations = self._generate_recommendations(threshold)

        return {
            "threshold_logcs": threshold,
            "contrast_threshold_pct": contrast_pct,
            "classification": classification,
            "test_levels_presented": len(responses),
            "recommendations": recommendations,
        }

    def run_staircase_test(self, responses: List[dict]) -> dict:
        """
        اختبار سلم تكيّفي (2-down, 1-up) لتقدير العتبة بدقة أعلى.

        Args:
            responses: list of dicts بترتيب زمني:
                - contrast: float (0.0–1.0)
                - is_correct: bool

        Returns:
            dict مع: threshold, reversals, classification
        """
        if not responses:
            return {"error": "No responses provided"}

        consecutive_correct = 0
        reversals = []
        last_direction = None  # "up" or "down"
        contrasts_at_reversal = []

        for i, r in enumerate(responses):
            if r["is_correct"]:
                consecutive_correct += 1
                if consecutive_correct >= 2:
                    direction = "down"  # تقليل التباين (أصعب)
                    consecutive_correct = 0
                else:
                    continue
            else:
                consecutive_correct = 0
                direction = "up"  # زيادة التباين (أسهل)

            # تسجيل الانعكاس
            if last_direction is not None and direction != last_direction:
                contrasts_at_reversal.append(r["contrast"])
                reversals.append({
                    "trial": i + 1,
                    "contrast": r["contrast"],
                    "direction": direction,
                })
            last_direction = direction

        # العتبة = متوسط آخر 6 انعكاسات (أو كل المتوفرة)
        if contrasts_at_reversal:
            last_reversals = contrasts_at_reversal[-6:]
            threshold_contrast = sum(last_reversals) / len(last_reversals)
        else:
            # لا انعكاسات — نستخدم آخر تباين
            threshold_contrast = responses[-1]["contrast"]

        threshold_logcs = -math.log10(threshold_contrast) if threshold_contrast > 0 else 0
        threshold_logcs = round(threshold_logcs, 2)

        return {
            "threshold_logcs": threshold_logcs,
            "threshold_contrast": round(threshold_contrast, 4),
            "threshold_contrast_pct": round(threshold_contrast * 100, 2),
            "total_reversals": len(reversals),
            "reversals_used": min(6, len(contrasts_at_reversal)),
            "classification": self._classify_cs(threshold_logcs),
            "total_trials": len(responses),
        }

    def _classify_cs(self, log_cs: float) -> dict:
        """تصنيف حساسية التباين"""
        if log_cs >= 1.65:
            return {
                "level": "normal",
                "label": "Normal Contrast Sensitivity",
                "label_ar": "حساسية تباين طبيعية",
            }
        elif log_cs >= 1.35:
            return {
                "level": "mild_loss",
                "label": "Mild CS Loss",
                "label_ar": "فقد خفيف في حساسية التباين",
            }
        elif log_cs >= 1.05:
            return {
                "level": "moderate_loss",
                "label": "Moderate CS Loss",
                "label_ar": "فقد متوسط في حساسية التباين",
            }
        elif log_cs >= 0.60:
            return {
                "level": "severe_loss",
                "label": "Severe CS Loss",
                "label_ar": "فقد شديد في حساسية التباين",
            }
        else:
            return {
                "level": "profound_loss",
                "label": "Profound CS Loss",
                "label_ar": "فقد عميق في حساسية التباين",
            }

    def _generate_recommendations(self, log_cs: float) -> list:
        """توليد توصيات بناءً على نتائج CS"""
        recs = []

        if log_cs < 1.05:
            recs.append({
                "action": "Environmental modification: increase task lighting to 1000+ lux",
                "action_ar": "تعديل بيئي: زيادة إضاءة المهام لأكثر من 1000 لوكس",
                "priority": 1,
            })
            recs.append({
                "action": "High-contrast materials: black text on yellow/white background",
                "action_ar": "مواد عالية التباين: نص أسود على خلفية صفراء/بيضاء",
                "priority": 1,
            })
        if log_cs < 1.35:
            recs.append({
                "action": "Consider tinted lenses (yellow/amber) to enhance contrast",
                "action_ar": "النظر في عدسات ملونة (أصفر/كهرماني) لتعزيز التباين",
                "priority": 2,
            })
            recs.append({
                "action": "Perceptual Learning therapy (Gabor patch training) to improve cortical CS",
                "action_ar": "علاج التعلم الإدراكي (تدريب Gabor) لتحسين حساسية التباين القشرية",
                "priority": 2,
            })
        if log_cs < 0.60:
            recs.append({
                "action": "CLAHE-enhanced AR wearable (eSight/IrisVision) for real-time contrast boost",
                "action_ar": "نظارة واقع معزز مع تعزيز تباين CLAHE (eSight/IrisVision)",
                "priority": 1,
            })

        return recs


def run_contrast_assessment(params: dict) -> dict:
    """
    واجهة الأداة لتقييم حساسية التباين.

    Args:
        params: dict مع:
          - method: "pelli_robson" | "staircase"
          - responses: list of response dicts
    """
    assessment = ContrastSensitivityAssessment()
    method = params.get("method", "pelli_robson")

    if method == "pelli_robson":
        return assessment.run_adaptive_test(params.get("responses", []))
    elif method == "staircase":
        return assessment.run_staircase_test(params.get("responses", []))
    else:
        return {"error": f"Unknown method: {method}"}
