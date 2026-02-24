"""
Perceptual Learning Engine — محرك التعلم الإدراكي
================================================
يولد محفزات Gabor Patch رياضية + يتحكم في عتبة التباين
لتدريب القشرة البصرية V1 على تحسين حساسية التباين.

الأساس العلمي:
  Polat et al. (2004). Improving vision in adult amblyopia by perceptual learning.
  PNAS, 101(17), 6692-6697.

  Maniglia et al. (2011). Perceptual learning in patients with macular degeneration.
  Restorative Neurology and Neuroscience, 29(3), 143-156.
"""

import math
import numpy as np
from typing import Tuple, Optional


class GaborPatchGenerator:
    """
    مولد محفزات Gabor رياضية بدقة بكسلية.

    المعادلة الرياضية:
      G(x,y) = exp(-(x'² + y'²) / (2σ²)) × cos(2πf·x')

    حيث:
      x' = x·cos(θ) + y·sin(θ)  (تدوير)
      y' = -x·sin(θ) + y·cos(θ)
      σ = انتشار الغلاف الغاوسي
      f = التردد المكاني (cycles/degree)
      θ = زاوية الاتجاه
    """

    def generate(
        self,
        size: int = 256,
        spatial_freq: float = 0.05,
        theta_deg: float = 45.0,
        contrast: float = 1.0,
        sigma: float = 50.0,
        phase: float = 0.0,
    ) -> np.ndarray:
        """
        توليد Gabor Patch كمصفوفة numpy.

        Args:
            size: حجم الصورة (بكسل مربع)
            spatial_freq: التردد المكاني (cycles/pixel)
            theta_deg: زاوية الاتجاه (درجات)
            contrast: مستوى التباين (0.0 – 1.0)
            sigma: انتشار الغاوسي (بكسل)
            phase: الطور (radians)

        Returns:
            np.ndarray بالأبعاد (size, size) وقيم 0–255 (uint8)
        """
        half = size / 2
        x_range = np.linspace(-half, half, size)
        y_range = np.linspace(-half, half, size)
        x, y = np.meshgrid(x_range, y_range)

        theta = np.deg2rad(theta_deg)
        x_theta = x * np.cos(theta) + y * np.sin(theta)
        y_theta = -x * np.sin(theta) + y * np.cos(theta)

        # الغلاف الغاوسي
        gaussian = np.exp(-(x_theta ** 2 + y_theta ** 2) / (2 * sigma ** 2))

        # الموجة الجيبية
        sinusoid = np.cos(2 * np.pi * spatial_freq * x_theta + phase)

        # الدمج مع التباين
        gabor = gaussian * sinusoid * contrast

        # التطبيع إلى 0–255
        normalized = ((gabor + 1) / 2.0 * 255).astype(np.uint8)
        return normalized

    def generate_pair(
        self,
        size: int = 256,
        spatial_freq: float = 0.05,
        contrast: float = 0.5,
        sigma: float = 50.0,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        توليد زوج Gabor بزاويتين (للاختيار بين الاتجاهين).

        Returns:
            (patch_45, patch_135, correct_orientation)
        """
        target_theta = 45.0 if np.random.random() > 0.5 else 135.0
        patch_target = self.generate(size, spatial_freq, target_theta, contrast, sigma)

        return patch_target, target_theta


class PerceptualLearningController:
    """
    متحكم جلسات التعلم الإدراكي.

    يدير مستوى التباين بخوارزمية تكيّفية:
    - إجابة صحيحة → تقليل التباين 10% (أصعب)
    - إجابة خاطئة → زيادة التباين 15% (أسهل)

    يسجل التقدم عبر الجلسات.
    """

    def __init__(
        self,
        starting_contrast: float = 1.0,
        spatial_frequency: float = 3.0,
        step_down: float = 0.90,
        step_up: float = 1.15,
        min_contrast: float = 0.01,
        max_contrast: float = 1.0,
    ):
        self.current_contrast = starting_contrast
        self.spatial_frequency = spatial_frequency  # cpd
        self.step_down = step_down  # نسبة التقليل عند النجاح
        self.step_up = step_up      # نسبة الزيادة عند الفشل
        self.min_contrast = min_contrast
        self.max_contrast = max_contrast
        self.trial_history = []
        self.reversals = []
        self.last_direction = None

    def get_stimulus_parameters(self) -> dict:
        """إرجاع بارامترات المحفز الحالي"""
        return {
            "type": "gabor_patch",
            "contrast_level": round(self.current_contrast, 4),
            "contrast_pct": round(self.current_contrast * 100, 2),
            "spatial_freq_cpd": self.spatial_frequency,
            "orientation_options": [45, 135],
            "trial_number": len(self.trial_history) + 1,
        }

    def update_threshold(self, is_correct: bool) -> dict:
        """
        تحديث عتبة التباين بناءً على استجابة المريض.

        Args:
            is_correct: هل تعرف المريض على اتجاه الخطوط؟

        Returns:
            dict مع: new_contrast, direction, was_reversal
        """
        old_contrast = self.current_contrast

        if is_correct:
            self.current_contrast = max(
                self.min_contrast, self.current_contrast * self.step_down
            )
            direction = "harder"
        else:
            self.current_contrast = min(
                self.max_contrast, self.current_contrast * self.step_up
            )
            direction = "easier"

        # كشف الانعكاس
        was_reversal = False
        if self.last_direction and direction != self.last_direction:
            was_reversal = True
            self.reversals.append(self.current_contrast)
        self.last_direction = direction

        self.trial_history.append({
            "contrast": old_contrast,
            "is_correct": is_correct,
            "direction": direction,
            "was_reversal": was_reversal,
        })

        return {
            "new_contrast": round(self.current_contrast, 4),
            "new_contrast_pct": round(self.current_contrast * 100, 2),
            "direction": direction,
            "was_reversal": was_reversal,
            "total_reversals": len(self.reversals),
            "trial_number": len(self.trial_history),
        }

    def get_threshold_estimate(self) -> dict:
        """تقدير عتبة التباين من الانعكاسات"""
        if len(self.reversals) < 4:
            return {
                "estimated": False,
                "message": f"Need at least 4 reversals, have {len(self.reversals)}",
            }

        # متوسط آخر 6 انعكاسات (أو كل المتوفرة)
        last_revs = self.reversals[-6:]
        threshold = sum(last_revs) / len(last_revs)
        log_cs = -math.log10(threshold) if threshold > 0 else 0

        return {
            "estimated": True,
            "threshold_contrast": round(threshold, 4),
            "threshold_pct": round(threshold * 100, 2),
            "threshold_logcs": round(log_cs, 2),
            "reversals_used": len(last_revs),
            "total_reversals": len(self.reversals),
        }

    def get_session_summary(self) -> dict:
        """ملخص جلسة التعلم الإدراكي"""
        if not self.trial_history:
            return {"total_trials": 0}

        correct = sum(1 for t in self.trial_history if t["is_correct"])
        contrasts = [t["contrast"] for t in self.trial_history]

        threshold = self.get_threshold_estimate()

        return {
            "total_trials": len(self.trial_history),
            "correct_trials": correct,
            "accuracy_pct": round(correct / len(self.trial_history) * 100, 1),
            "starting_contrast": contrasts[0] if contrasts else None,
            "ending_contrast": round(self.current_contrast, 4),
            "min_contrast_reached": round(min(contrasts), 4) if contrasts else None,
            "spatial_frequency_cpd": self.spatial_frequency,
            "threshold_estimate": threshold,
            "total_reversals": len(self.reversals),
        }


def run_perceptual_learning(params: dict) -> dict:
    """
    واجهة الأداة لمحرك التعلم الإدراكي.

    Args:
        params: dict مع:
          - action: "get_params" | "update" | "summary" | "simulate_session" | "generate_gabor"
          - starting_contrast: float
          - spatial_frequency: float
          - is_correct: bool (لـ update)
          - num_trials: int (لـ simulate_session)
          - size, theta, contrast, sigma (لـ generate_gabor)
    """
    action = params.get("action", "simulate_session")
    sc = params.get("starting_contrast", 1.0)
    sf = params.get("spatial_frequency", 3.0)

    if action == "generate_gabor":
        gen = GaborPatchGenerator()
        patch = gen.generate(
            size=params.get("size", 256),
            spatial_freq=params.get("spatial_freq", 0.05),
            theta_deg=params.get("theta", 45),
            contrast=params.get("contrast", 0.5),
            sigma=params.get("sigma", 50),
        )
        return {
            "shape": list(patch.shape),
            "min_val": int(patch.min()),
            "max_val": int(patch.max()),
            "mean_val": round(float(patch.mean()), 1),
            "generated": True,
        }

    controller = PerceptualLearningController(sc, sf)

    if action == "get_params":
        return controller.get_stimulus_parameters()

    elif action == "simulate_session":
        import random
        num_trials = params.get("num_trials", 50)
        trials = []

        for i in range(num_trials):
            stim = controller.get_stimulus_parameters()

            # محاكاة: المريض يجيب صح 75% من الوقت عند تباين > عتبة
            simulated_threshold = 0.15
            p_correct = 0.95 if controller.current_contrast > simulated_threshold else 0.5
            is_correct = random.random() < p_correct

            result = controller.update_threshold(is_correct)
            trials.append({
                "trial": i + 1,
                "contrast": stim["contrast_level"],
                "correct": is_correct,
                "new_contrast": result["new_contrast"],
            })

        summary = controller.get_session_summary()
        return {"trials": trials, "session_summary": summary}

    return {"error": f"Unknown action: {action}"}
