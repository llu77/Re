"""
Interventions Package — حزمة التدخلات العلاجية الرقمية
=====================================================
محركات تدخل نشطة (Active Interventions):
  1. AdaptiveScanningTask — تدريب المسح البصري (Hemianopia)
  2. PerceptualLearningController — تعلم إدراكي (Gabor Patches)
  3. VisualAugmentationEngine — تعزيز بصري AR (Glaucoma/AMD)
  4. SmartDeviceRouter — توجيه ذكي للمعدات المساعدة
"""

from .scanning_trainer import run_scanning_trainer, AdaptiveScanningTask
from .perceptual_learning import run_perceptual_learning, PerceptualLearningController, GaborPatchGenerator
from .visual_augmentation import run_visual_augmentation, VisualAugmentationEngine
from .device_router import run_device_routing, SmartDeviceRouter


def run_intervention(params: dict) -> dict:
    """
    واجهة موحدة لتشغيل أي تدخل علاجي.

    Args:
        params: dict مع:
          - intervention_type: "scanning" | "perceptual_learning" | "visual_augmentation" | "device_routing"
          - ... باقي البارامترات حسب النوع
    """
    itype = params.get("intervention_type", "")

    if itype == "scanning":
        return run_scanning_trainer(params)
    elif itype == "perceptual_learning":
        return run_perceptual_learning(params)
    elif itype == "visual_augmentation":
        return run_visual_augmentation(params)
    elif itype == "device_routing":
        return run_device_routing(params)
    else:
        return {
            "error": f"Unknown intervention_type: {itype}",
            "available_types": ["scanning", "perceptual_learning", "visual_augmentation", "device_routing"],
        }


__all__ = [
    "run_intervention",
    "run_scanning_trainer",
    "run_perceptual_learning",
    "run_visual_augmentation",
    "run_device_routing",
    "AdaptiveScanningTask",
    "PerceptualLearningController",
    "GaborPatchGenerator",
    "VisualAugmentationEngine",
    "SmartDeviceRouter",
]
