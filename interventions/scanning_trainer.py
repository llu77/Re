"""
Adaptive Scanning Trainer — مدرب المسح البصري التكيّفي
=====================================================
خوارزمية سلم تكيّفي (1-up, 2-down) لتدريب مرضى Hemianopia
على البحث في الجانب الأعمى مع زيادة تدريجية في الصعوبة.

المبدأ العلمي:
  Zihl (1995). Visual scanning training effect on reading performance.
  Pambakian et al. (2004). Scanning the visual world: a study of patients
  with homonymous hemianopia.
"""

import random
from typing import List, Optional


class AdaptiveScanningTask:
    """
    مدرب مسح بصري تكيّفي بخوارزمية (1-up, 2-down Staircase).

    - نجاحان متتاليان = زيادة الصعوبة (هدف أصغر + أبعد في الجانب الأعمى)
    - فشل واحد = تقليل الصعوبة (حماية من الإحباط)

    المستويات: 1 (سهل جداً) إلى 10 (خبير)
    """

    def __init__(self, blind_side: str = "right", initial_difficulty: int = 1):
        self.blind_side = blind_side  # "right" أو "left"
        self.current_difficulty = max(1, min(10, initial_difficulty))
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.trial_history = []
        self.reversal_count = 0
        self.last_direction = None  # "up" أو "down"

    def generate_stimulus(self) -> dict:
        """
        يولد معلمات المحفز البصري للمحاولة القادمة.

        Returns:
            dict مع: target_size, x_position, y_position, distractors_count,
            time_limit_ms, difficulty
        """
        d = self.current_difficulty

        # حجم الهدف: يبدأ كبير (5°) ويصغر مع الصعوبة
        target_size_deg = max(0.5, 5.0 - (d * 0.45))

        # المسافة في الجانب الأعمى: تبدأ قريبة (10°) وتبعد
        eccentricity_deg = min(30.0, 8.0 + (d * 2.2))

        # الموقع: في الجانب الأعمى
        x_position = eccentricity_deg if self.blind_side == "right" else -eccentricity_deg

        # ارتفاع عشوائي (لمنع التوقع)
        y_position = random.uniform(-8.0, 8.0)

        # عدد المشتتات: يزداد مع الصعوبة
        distractors_count = d * 3

        # حد الوقت: يقل مع الصعوبة
        time_limit_ms = max(800, 3000 - (d * 200))

        return {
            "target_size_deg": round(target_size_deg, 1),
            "x_position_deg": round(x_position, 1),
            "y_position_deg": round(y_position, 1),
            "distractors_count": distractors_count,
            "time_limit_ms": time_limit_ms,
            "difficulty": d,
            "blind_side": self.blind_side,
        }

    def process_response(self, reaction_time_ms: int, is_correct: bool) -> dict:
        """
        معالجة استجابة المريض وتحديث مستوى الصعوبة.

        Args:
            reaction_time_ms: زمن الاستجابة بالمللي ثانية
            is_correct: هل وجد المريض الهدف؟

        Returns:
            dict مع: new_difficulty, direction, was_reversal, feedback
        """
        old_difficulty = self.current_difficulty
        direction = None
        was_reversal = False

        if is_correct and reaction_time_ms < 1500:
            # استجابة صحيحة وسريعة
            self.consecutive_successes += 1
            self.consecutive_failures = 0

            if self.consecutive_successes >= 2:
                # 2-down: نجاحان = زيادة الصعوبة
                self.current_difficulty = min(10, self.current_difficulty + 1)
                self.consecutive_successes = 0
                direction = "up"
        else:
            # فشل أو بطء
            self.consecutive_failures += 1
            self.consecutive_successes = 0

            if self.consecutive_failures >= 1:
                # 1-up: فشل واحد = تقليل الصعوبة
                self.current_difficulty = max(1, self.current_difficulty - 1)
                self.consecutive_failures = 0
                direction = "down"

        # كشف الانعكاس (Reversal)
        if direction and self.last_direction and direction != self.last_direction:
            self.reversal_count += 1
            was_reversal = True
        if direction:
            self.last_direction = direction

        # تسجيل المحاولة
        trial = {
            "difficulty_before": old_difficulty,
            "difficulty_after": self.current_difficulty,
            "reaction_time_ms": reaction_time_ms,
            "is_correct": is_correct,
            "direction": direction,
            "was_reversal": was_reversal,
        }
        self.trial_history.append(trial)

        # توليد feedback
        if is_correct and reaction_time_ms < 1000:
            feedback = {"tone": "excellent", "message_ar": "ممتاز! سرعة رائعة", "message_en": "Excellent! Great speed"}
        elif is_correct:
            feedback = {"tone": "good", "message_ar": "أحسنت! حاول أسرع", "message_en": "Good! Try faster"}
        else:
            feedback = {"tone": "encourage", "message_ar": "لا بأس، حاول مجدداً", "message_en": "No problem, try again"}

        return {
            "new_difficulty": self.current_difficulty,
            "direction": direction,
            "was_reversal": was_reversal,
            "total_reversals": self.reversal_count,
            "feedback": feedback,
            "trial_number": len(self.trial_history),
        }

    def get_session_summary(self) -> dict:
        """ملخص الجلسة الحالية"""
        if not self.trial_history:
            return {"total_trials": 0}

        correct = sum(1 for t in self.trial_history if t["is_correct"])
        rts = [t["reaction_time_ms"] for t in self.trial_history if t["is_correct"]]
        difficulties = [t["difficulty_after"] for t in self.trial_history]

        return {
            "total_trials": len(self.trial_history),
            "correct_trials": correct,
            "accuracy_pct": round(correct / len(self.trial_history) * 100, 1),
            "mean_rt_ms": round(sum(rts) / len(rts), 1) if rts else None,
            "max_difficulty_reached": max(difficulties),
            "final_difficulty": self.current_difficulty,
            "total_reversals": self.reversal_count,
            "blind_side": self.blind_side,
            "threshold_difficulty": round(sum(difficulties[-10:]) / min(10, len(difficulties)), 1),
        }

    def reset(self, difficulty: int = 1):
        """إعادة تعيين الجلسة"""
        self.current_difficulty = max(1, min(10, difficulty))
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.trial_history = []
        self.reversal_count = 0
        self.last_direction = None


def run_scanning_trainer(params: dict) -> dict:
    """
    واجهة الأداة لمدرب المسح البصري.

    Args:
        params: dict مع:
          - action: "generate_stimulus" | "process_response" | "session_summary" | "simulate_session"
          - blind_side: "right" | "left"
          - difficulty: int (1-10)
          - reaction_time_ms, is_correct (لـ process_response)
          - num_trials (لـ simulate_session)
    """
    action = params.get("action", "generate_stimulus")
    blind_side = params.get("blind_side", "right")
    difficulty = params.get("difficulty", 1)

    trainer = AdaptiveScanningTask(blind_side, difficulty)

    if action == "generate_stimulus":
        return trainer.generate_stimulus()

    elif action == "simulate_session":
        # محاكاة جلسة كاملة لعرض كيفية عمل الخوارزمية
        num_trials = params.get("num_trials", 20)
        trials = []

        for i in range(num_trials):
            stimulus = trainer.generate_stimulus()

            # محاكاة أداء المريض (احتمال النجاح يعتمد على الصعوبة)
            success_prob = max(0.3, 1.0 - (trainer.current_difficulty * 0.07))
            is_correct = random.random() < success_prob
            rt = random.randint(600, 2500) if is_correct else random.randint(1500, 3000)

            response = trainer.process_response(rt, is_correct)
            trials.append({
                "trial": i + 1,
                "stimulus": stimulus,
                "rt_ms": rt,
                "correct": is_correct,
                "new_difficulty": response["new_difficulty"],
                "feedback": response["feedback"]["message_en"],
            })

        summary = trainer.get_session_summary()
        return {
            "trials": trials,
            "session_summary": summary,
        }

    return {"error": f"Unknown action: {action}"}
