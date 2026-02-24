"""
Outcome Store — تخزين واسترجاع نتائج المرضى
==============================================
يتتبع نجاح/فشل التقنيات لكل مريض لتحسين التوصيات المستقبلية.
"""

import os
import json
from datetime import datetime


class OutcomeStore:
    """تخزين JSON-based لنتائج التأهيل"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base, "data", "outcomes")

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _patient_file(self, patient_id: str) -> str:
        safe_id = "".join(c for c in patient_id if c.isalnum() or c in "-_")
        return os.path.join(self.data_dir, f"{safe_id}.json")

    def _load_patient(self, patient_id: str) -> dict:
        filepath = self._patient_file(patient_id)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"patient_id": patient_id, "outcomes": [], "created": datetime.now().isoformat()}

    def _save_patient(self, patient_id: str, data: dict):
        filepath = self._patient_file(patient_id)
        data["last_updated"] = datetime.now().isoformat()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────

    def log_outcome(self, patient_id: str, technique_id: str, outcome: dict):
        """
        تسجيل نتيجة استخدام تقنية لمريض.

        Args:
            patient_id: معرف المريض
            technique_id: معرف التقنية (rule_id)
            outcome: dict مع:
                - success: bool
                - va_before: float (LogMAR)
                - va_after: float (LogMAR)
                - reading_speed_before: int (WPM)
                - reading_speed_after: int (WPM)
                - sessions_completed: int
                - adherence_percentage: float
                - patient_satisfaction: int (1-5)
                - clinician_notes: str
                - outcome_date: str
        """
        data = self._load_patient(patient_id)

        entry = {
            "technique_id": technique_id,
            "outcome_date": outcome.get("outcome_date", datetime.now().isoformat()),
            "success": outcome.get("success", None),
            "measurements": {
                "va_before": outcome.get("va_before"),
                "va_after": outcome.get("va_after"),
                "va_improvement": None,
                "reading_speed_before": outcome.get("reading_speed_before"),
                "reading_speed_after": outcome.get("reading_speed_after"),
            },
            "adherence": {
                "sessions_completed": outcome.get("sessions_completed"),
                "adherence_percentage": outcome.get("adherence_percentage"),
            },
            "patient_satisfaction": outcome.get("patient_satisfaction"),
            "clinician_notes": outcome.get("clinician_notes", ""),
        }

        # حساب التحسن
        if entry["measurements"]["va_before"] is not None and entry["measurements"]["va_after"] is not None:
            improvement = entry["measurements"]["va_before"] - entry["measurements"]["va_after"]
            entry["measurements"]["va_improvement"] = round(improvement, 2)
            # تحسن ≥ 0.1 LogMAR يعتبر معنوياً
            if entry["success"] is None:
                entry["success"] = improvement >= 0.1

        data["outcomes"].append(entry)
        self._save_patient(patient_id, data)

    def get_history(self, patient_id: str) -> list:
        """استرجاع تاريخ نتائج المريض"""
        data = self._load_patient(patient_id)
        return data.get("outcomes", [])

    def get_technique_outcomes(self, patient_id: str, technique_id: str) -> list:
        """استرجاع نتائج تقنية محددة لمريض"""
        history = self.get_history(patient_id)
        return [o for o in history if o.get("technique_id") == technique_id]

    def get_technique_success_rate(self, patient_id: str, technique_id: str) -> float | None:
        """حساب نسبة نجاح تقنية لمريض"""
        outcomes = self.get_technique_outcomes(patient_id, technique_id)
        if not outcomes:
            return None
        successes = sum(1 for o in outcomes if o.get("success") is True)
        return round(successes / len(outcomes), 2)

    def adjust_priorities(self, recommendations: list, patient_id: str) -> list:
        """
        تعديل أولويات التوصيات بناءً على تاريخ المريض.

        - تقنيات فشلت سابقاً → تنخفض أولويتها
        - تقنيات نجحت → تبقى كما هي أو ترتفع
        - تقنيات لم تُجرب → لا تتغير
        """
        history = self.get_history(patient_id)
        if not history:
            return recommendations

        # بناء ملخص النتائج السابقة
        outcome_summary = {}
        for outcome in history:
            tid = outcome.get("technique_id", "")
            if tid not in outcome_summary:
                outcome_summary[tid] = {"successes": 0, "failures": 0, "total": 0}
            outcome_summary[tid]["total"] += 1
            if outcome.get("success") is True:
                outcome_summary[tid]["successes"] += 1
            elif outcome.get("success") is False:
                outcome_summary[tid]["failures"] += 1

        # تعديل التوصيات
        adjusted = []
        for rec in recommendations:
            rule_id = rec.get("rule_id", "")
            rec_copy = dict(rec)

            if rule_id in outcome_summary:
                summary = outcome_summary[rule_id]
                if summary["failures"] > 0 and summary["successes"] == 0:
                    # فشل سابق بدون نجاح → خفض الأولوية
                    rec_copy["priority"] = rec_copy.get("priority", 5) + 5
                    rec_copy["suitability_score"] = max(0, rec_copy.get("suitability_score", 0) - 10)
                    rec_copy["outcome_note"] = (
                        f"⚠️ هذه التقنية فشلت سابقاً لهذا المريض "
                        f"({summary['failures']} مرة). تم خفض الأولوية."
                    )
                    rec_copy["outcome_note_en"] = (
                        f"This technique previously failed for this patient "
                        f"({summary['failures']} time(s)). Priority reduced."
                    )
                elif summary["successes"] > 0:
                    # نجاح سابق
                    rec_copy["outcome_note"] = (
                        f"✅ تقنية ناجحة سابقاً لهذا المريض "
                        f"({summary['successes']}/{summary['total']} مرة)."
                    )

            adjusted.append(rec_copy)

        # إعادة الترتيب
        adjusted.sort(key=lambda r: (r.get("priority", 10), -r.get("suitability_score", 0)))
        return adjusted

    def get_patient_summary(self, patient_id: str) -> dict:
        """ملخص شامل لنتائج المريض"""
        history = self.get_history(patient_id)
        if not history:
            return {"patient_id": patient_id, "total_outcomes": 0}

        total = len(history)
        successes = sum(1 for o in history if o.get("success") is True)
        failures = sum(1 for o in history if o.get("success") is False)

        # أفضل تحسن VA
        va_improvements = [
            o["measurements"]["va_improvement"]
            for o in history
            if o.get("measurements", {}).get("va_improvement") is not None
        ]

        techniques_tried = list(set(o.get("technique_id", "") for o in history))

        return {
            "patient_id": patient_id,
            "total_outcomes": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total, 2) if total > 0 else 0,
            "techniques_tried": techniques_tried,
            "best_va_improvement": max(va_improvements) if va_improvements else None,
            "avg_va_improvement": round(sum(va_improvements) / len(va_improvements), 2) if va_improvements else None,
        }
