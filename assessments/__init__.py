"""
Assessments Package — حزمة التقييمات السريرية الرقمية
=====================================================
Digital Biomarkers لتقييم حالة المريض البصرية:
  1. FixationStabilityAnalyzer — BCEA + PRL location
  2. DigitalMNREAD — سرعة القراءة + CPS + RA
  3. VisualSearchAssessment — المسح البصري والإهمال
  4. ContrastSensitivityAssessment — حساسية التباين (LogCS)
"""

from .fixation_analyzer import run_fixation_assessment, FixationStabilityAnalyzer
from .reading_speed import run_reading_assessment, DigitalMNREAD
from .visual_search import run_visual_search_assessment, VisualSearchAssessment
from .contrast_sensitivity import run_contrast_assessment, ContrastSensitivityAssessment


def run_assessment(params: dict) -> dict:
    """
    واجهة موحدة لتشغيل أي تقييم.

    Args:
        params: dict مع:
          - assessment_type: "fixation" | "reading" | "visual_search" | "contrast"
          - ... باقي البارامترات حسب النوع
    """
    atype = params.get("assessment_type", "")

    if atype == "fixation":
        return run_fixation_assessment(params)
    elif atype == "reading":
        return run_reading_assessment(params)
    elif atype == "visual_search":
        return run_visual_search_assessment(params)
    elif atype == "contrast":
        return run_contrast_assessment(params)
    else:
        return {
            "error": f"Unknown assessment_type: {atype}",
            "available_types": ["fixation", "reading", "visual_search", "contrast"],
        }

__all__ = [
    "run_assessment",
    "run_fixation_assessment",
    "run_reading_assessment",
    "run_visual_search_assessment",
    "run_contrast_assessment",
    "FixationStabilityAnalyzer",
    "DigitalMNREAD",
    "VisualSearchAssessment",
    "ContrastSensitivityAssessment",
]
