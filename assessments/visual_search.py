"""
Visual Search Assessment — تقييم المسح البصري
=============================================
اختبار شطب رقمي (Digital Cancellation Test) لتقييم الإهمال البصري
وقدرة المسح في مرضى العمى الشقي (Hemianopia) وإهمال نصف المجال.

المرجع العلمي:
  Weintraub & Mesulam (1985). Mental State Assessment of Young and Elderly Adults
  in Behavioral Neurology. In Principles of Behavioral Neurology.
"""

import math
import random
from typing import List, Optional


class VisualSearchAssessment:
    """
    اختبار شطب رقمي (Cancellation Test) تكيّفي.

    يولد مصفوفة أهداف + مشتتات على مستوى صعوبة متزايد
    ويحلل أداء المريض من حيث السرعة والدقة والتوزيع المكاني.
    """

    def __init__(self, grid_width: int = 20, grid_height: int = 10):
        self.grid_width = grid_width
        self.grid_height = grid_height

    def generate_trial(self, difficulty: int = 1, target_count: int = 20) -> dict:
        """
        توليد مصفوفة أهداف ومشتتات لمحاولة واحدة.

        Args:
            difficulty: مستوى الصعوبة 1–5 (يزيد المشتتات ويقلل حجم الهدف)
            target_count: عدد الأهداف في كل نصف

        Returns:
            dict مع: targets, distractors, grid_size, parameters
        """
        half_targets = target_count // 2
        distractor_count = target_count * (difficulty + 1)

        targets = []
        distractors = []

        # توزيع الأهداف بالتساوي على اليمين واليسار
        for i in range(half_targets):
            # أهداف الجانب الأيسر (x: 0 to grid_width/2)
            targets.append({
                "id": f"T_L{i}",
                "x": random.uniform(0, self.grid_width / 2),
                "y": random.uniform(0, self.grid_height),
                "side": "left",
                "size": max(0.5, 2.0 - difficulty * 0.3),
            })
            # أهداف الجانب الأيمن (x: grid_width/2 to grid_width)
            targets.append({
                "id": f"T_R{i}",
                "x": random.uniform(self.grid_width / 2, self.grid_width),
                "y": random.uniform(0, self.grid_height),
                "side": "right",
                "size": max(0.5, 2.0 - difficulty * 0.3),
            })

        # المشتتات
        for i in range(distractor_count):
            distractors.append({
                "id": f"D{i}",
                "x": random.uniform(0, self.grid_width),
                "y": random.uniform(0, self.grid_height),
                "size": max(0.5, 2.0 - difficulty * 0.3),
            })

        return {
            "targets": targets,
            "distractors": distractors,
            "total_targets": len(targets),
            "total_distractors": len(distractors),
            "difficulty": difficulty,
            "grid_size": {"width": self.grid_width, "height": self.grid_height},
        }

    def analyze_responses(self, trial: dict, responses: List[dict]) -> dict:
        """
        تحليل استجابات المريض لمحاولة واحدة.

        Args:
            trial: dict من generate_trial()
            responses: list of dicts:
                - target_id: str (ID الهدف الذي شطبه المريض)
                - reaction_time_ms: int
                - x_tap, y_tap: float (موقع اللمس)

        Returns:
            تحليل شامل: omissions, commissions, reaction_times, laterality_index
        """
        targets = {t["id"]: t for t in trial["targets"]}
        total_targets = len(targets)

        # الأهداف المكتشفة
        found_ids = set()
        reaction_times = {"left": [], "right": [], "all": []}
        false_alarms = 0

        for resp in responses:
            tid = resp.get("target_id", "")
            rt = resp.get("reaction_time_ms", 0)

            if tid in targets:
                found_ids.add(tid)
                side = targets[tid]["side"]
                reaction_times[side].append(rt)
                reaction_times["all"].append(rt)
            else:
                false_alarms += 1

        # الأهداف المفقودة (Omissions)
        missed = {tid: t for tid, t in targets.items() if tid not in found_ids}
        left_missed = sum(1 for t in missed.values() if t["side"] == "left")
        right_missed = sum(1 for t in missed.values() if t["side"] == "right")

        left_targets = sum(1 for t in targets.values() if t["side"] == "left")
        right_targets = sum(1 for t in targets.values() if t["side"] == "right")

        left_found = left_targets - left_missed
        right_found = right_targets - right_missed

        # Laterality Index: (Right - Left) / (Right + Left)
        # إيجابي = إهمال يساري، سلبي = إهمال يميني
        total_found = left_found + right_found
        if total_found > 0:
            laterality_index = (right_found - left_found) / total_found
        else:
            laterality_index = 0.0

        # متوسط زمن الاستجابة
        def mean_rt(rts):
            return round(sum(rts) / len(rts), 1) if rts else None

        # تصنيف الإهمال
        neglect = self._classify_neglect(
            left_missed, right_missed, left_targets, right_targets, laterality_index
        )

        return {
            "total_targets": total_targets,
            "targets_found": len(found_ids),
            "omission_errors": len(missed),
            "commission_errors": false_alarms,
            "left_side": {
                "targets": left_targets,
                "found": left_found,
                "missed": left_missed,
                "accuracy_pct": round(left_found / left_targets * 100, 1) if left_targets else 0,
                "mean_rt_ms": mean_rt(reaction_times["left"]),
            },
            "right_side": {
                "targets": right_targets,
                "found": right_found,
                "missed": right_missed,
                "accuracy_pct": round(right_found / right_targets * 100, 1) if right_targets else 0,
                "mean_rt_ms": mean_rt(reaction_times["right"]),
            },
            "overall_accuracy_pct": round(len(found_ids) / total_targets * 100, 1) if total_targets else 0,
            "overall_mean_rt_ms": mean_rt(reaction_times["all"]),
            "laterality_index": round(laterality_index, 3),
            "search_asymmetry": neglect,
            "difficulty": trial.get("difficulty", 1),
        }

    def _classify_neglect(
        self, left_miss, right_miss, left_total, right_total, laterality
    ) -> dict:
        """تصنيف الإهمال البصري"""
        left_miss_rate = left_miss / left_total if left_total else 0
        right_miss_rate = right_miss / right_total if right_total else 0

        if abs(laterality) < 0.1 and left_miss_rate < 0.2 and right_miss_rate < 0.2:
            return {
                "type": "no_neglect",
                "label": "No significant neglect",
                "label_ar": "لا إهمال بصري ملحوظ",
                "severity": "none",
            }
        elif laterality > 0.3:
            severity = "severe" if laterality > 0.6 else "moderate"
            return {
                "type": "left_neglect",
                "label": f"Left visual neglect ({severity})",
                "label_ar": f"إهمال بصري أيسر ({'شديد' if severity == 'severe' else 'متوسط'})",
                "severity": severity,
            }
        elif laterality < -0.3:
            severity = "severe" if laterality < -0.6 else "moderate"
            return {
                "type": "right_neglect",
                "label": f"Right visual neglect ({severity})",
                "label_ar": f"إهمال بصري أيمن ({'شديد' if severity == 'severe' else 'متوسط'})",
                "severity": severity,
            }
        else:
            return {
                "type": "bilateral_impairment",
                "label": "Bilateral search impairment",
                "label_ar": "ضعف مسح بصري ثنائي الجانب",
                "severity": "moderate",
            }

    def compare_sessions(self, session1: dict, session2: dict) -> dict:
        """مقارنة جلستين لتتبع التقدم"""
        omit_change = session1["omission_errors"] - session2["omission_errors"]
        rt_before = session1.get("overall_mean_rt_ms") or 0
        rt_after = session2.get("overall_mean_rt_ms") or 0
        rt_improvement = rt_before - rt_after if rt_before and rt_after else 0

        lat_before = abs(session1.get("laterality_index", 0))
        lat_after = abs(session2.get("laterality_index", 0))
        symmetry_improvement = lat_before - lat_after

        improved = omit_change > 0 or symmetry_improvement > 0.1

        return {
            "omission_change": omit_change,
            "rt_improvement_ms": round(rt_improvement, 1),
            "symmetry_improvement": round(symmetry_improvement, 3),
            "overall_improved": improved,
            "summary_ar": (
                f"تحسن: {'نعم' if improved else 'لا'}. "
                f"الأهداف المفقودة: {session1['omission_errors']}→{session2['omission_errors']}. "
                f"التماثل: {lat_before:.2f}→{lat_after:.2f}."
            ),
        }


def run_visual_search_assessment(params: dict) -> dict:
    """
    واجهة الأداة لتقييم المسح البصري.

    Args:
        params: dict مع:
          - action: "generate_trial" | "analyze" | "compare_sessions"
          - difficulty: int (1-5)
          - target_count: int
          - trial: dict (لـ analyze)
          - responses: list (لـ analyze)
          - session1, session2: dict (لـ compare_sessions)
    """
    assessment = VisualSearchAssessment()
    action = params.get("action", "generate_trial")

    if action == "generate_trial":
        return assessment.generate_trial(
            difficulty=params.get("difficulty", 1),
            target_count=params.get("target_count", 20),
        )

    elif action == "analyze":
        trial = params.get("trial", {})
        responses = params.get("responses", [])
        return assessment.analyze_responses(trial, responses)

    elif action == "compare_sessions":
        return assessment.compare_sessions(
            params.get("session1", {}),
            params.get("session2", {}),
        )

    return {"error": f"Unknown action: {action}"}
