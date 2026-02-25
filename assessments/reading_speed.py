"""
Digital MNREAD — محلل سرعة القراءة الرقمي
==========================================
يحسب المؤشرات الثلاثة الأساسية لسرعة القراءة:
  1. MRS — Maximum Reading Speed (أقصى سرعة قراءة بالكلمة/دقيقة)
  2. CPS — Critical Print Size (أصغر حجم خط بأقصى سرعة)
  3. RA  — Reading Acuity (أصغر خط مقروء بـ LogMAR)

المرجع العلمي:
  Mansfield et al. (1993). A new reading-acuity chart for normal and low vision.
  Ophthalmic & Physiological Optics, 13, 232–235.
"""

import math
from typing import List, Optional


# أحجام خطوط MNREAD القياسية (LogMAR)
MNREAD_SIZES = [1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.1, -0.2, -0.3]
WORDS_PER_SENTENCE = 10  # MNREAD standard: 60 characters ≈ 10 words


class DigitalMNREAD:
    """
    محلل سرعة القراءة الرقمي المعتمد على بروتوكول MNREAD.

    يقبل سلسلة من القياسات: (حجم الخط LogMAR, زمن القراءة بالثانية, أخطاء الكلمات).
    """

    def __init__(self, viewing_distance_cm: float = 40.0):
        self.viewing_distance_cm = viewing_distance_cm

    def analyze_session(self, readings: List[dict]) -> dict:
        """
        تحليل جلسة قراءة كاملة.

        Args:
            readings: list of dicts:
                - print_size_logmar: float
                - reading_time_seconds: float
                - word_errors: int (0–10)

        Returns:
            dict مع: mrs, cps, reading_acuity, speed_curve, recommendations
        """
        if not readings:
            return {"error": "No readings provided"}

        # ترتيب من الأكبر للأصغر (سهل → صعب)
        readings_sorted = sorted(readings, key=lambda r: r["print_size_logmar"], reverse=True)

        # حساب سرعة القراءة لكل حجم
        speed_curve = []
        for r in readings_sorted:
            size = r["print_size_logmar"]
            time_s = r["reading_time_seconds"]
            errors = r.get("word_errors", 0)
            correct_words = max(0, WORDS_PER_SENTENCE - errors)

            if time_s > 0:
                wpm = (correct_words / time_s) * 60
            else:
                wpm = 0

            speed_curve.append({
                "print_size_logmar": size,
                "reading_speed_wpm": round(wpm, 1),
                "word_errors": errors,
                "time_seconds": time_s,
            })

        # 1. MRS — أقصى سرعة (أعلى WPM في الأحجام الكبيرة)
        valid_speeds = [p["reading_speed_wpm"] for p in speed_curve if p["word_errors"] < 5]
        mrs = max(valid_speeds) if valid_speeds else 0

        # 2. Reading Acuity — أصغر حجم مقروء (≥ 1 كلمة صحيحة)
        readable = [p for p in speed_curve if p["word_errors"] < WORDS_PER_SENTENCE]
        reading_acuity = readable[-1]["print_size_logmar"] if readable else None

        # 3. CPS — أصغر حجم بسرعة ≥ MRS × threshold
        # المعيار: السرعة لا تقل عن 80% من MRS
        threshold = mrs * 0.80
        cps = None
        for p in speed_curve:
            if p["reading_speed_wpm"] >= threshold and p["word_errors"] < 5:
                cps = p["print_size_logmar"]

        # تصنيف السرعة
        speed_class = self._classify_reading_speed(mrs)

        # توصيات
        recommendations = self._generate_recommendations(mrs, cps, reading_acuity)

        return {
            "mrs_wpm": round(mrs, 1),
            "cps_logmar": cps,
            "reading_acuity_logmar": reading_acuity,
            "speed_classification": speed_class,
            "speed_curve": speed_curve,
            "recommendations": recommendations,
            "viewing_distance_cm": self.viewing_distance_cm,
            "total_sentences_read": len(readings),
        }

    def _classify_reading_speed(self, mrs: float) -> dict:
        """تصنيف سرعة القراءة"""
        if mrs >= 200:
            return {"level": "normal", "label": "Normal", "label_ar": "طبيعي"}
        elif mrs >= 120:
            return {"level": "functional", "label": "Functional", "label_ar": "وظيفي"}
        elif mrs >= 60:
            return {"level": "impaired", "label": "Impaired", "label_ar": "ضعيف"}
        elif mrs >= 20:
            return {"level": "severely_impaired", "label": "Severely Impaired", "label_ar": "ضعيف جداً"}
        else:
            return {"level": "non_functional", "label": "Non-functional", "label_ar": "غير وظيفي"}

    def _generate_recommendations(
        self, mrs: float, cps: Optional[float], ra: Optional[float]
    ) -> list:
        """توليد توصيات بناءً على نتائج MNREAD"""
        recs = []

        if mrs < 60:
            recs.append({
                "action": "Consider audio alternatives (screen reader, audiobooks)",
                "action_ar": "النظر في البدائل الصوتية (قارئ شاشة، كتب مسموعة)",
                "priority": 1,
            })
        elif mrs < 120:
            recs.append({
                "action": "Prescribe optical/electronic magnification to increase print size above CPS",
                "action_ar": "وصف تكبير بصري/إلكتروني لزيادة حجم الخط فوق CPS",
                "priority": 2,
            })

        if cps is not None and cps > 0.4:
            # CPS أكبر من 0.4 LogMAR = يحتاج خط كبير
            magnification_needed = 10 ** cps
            recs.append({
                "action": f"Minimum magnification needed: {magnification_needed:.1f}x for fluent reading",
                "action_ar": f"الحد الأدنى من التكبير المطلوب: {magnification_needed:.1f}× للقراءة بطلاقة",
                "magnification": round(magnification_needed, 1),
                "priority": 2,
            })

        if ra is not None and ra > 1.0:
            recs.append({
                "action": "Severe reading impairment — evaluate for eccentric viewing training (EVT)",
                "action_ar": "ضعف قراءة شديد — تقييم لتدريب النظر اللامركزي (EVT)",
                "priority": 1,
            })

        return recs

    def calculate_magnification_need(self, cps_logmar: float, target_size_logmar: float = 0.0) -> float:
        """حساب التكبير المطلوب لقراءة مريحة"""
        # M = 10^(CPS - target)
        return round(10 ** (cps_logmar - target_size_logmar), 1)


def run_reading_assessment(params: dict) -> dict:
    """
    واجهة الأداة لمحلل سرعة القراءة.

    Args:
        params: dict مع:
          - readings: list of {print_size_logmar, reading_time_seconds, word_errors}
          - viewing_distance_cm: float (default 40)
    """
    distance = params.get("viewing_distance_cm", 40.0)
    analyzer = DigitalMNREAD(distance)
    readings = params.get("readings", [])
    return analyzer.analyze_session(readings)
