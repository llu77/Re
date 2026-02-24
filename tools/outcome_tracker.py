"""
Rehabilitation Outcome Tracker
متتبع نتائج التأهيل البصري

Tracks patient outcomes over time including:
- Visual Acuity progression
- Reading speed improvement
- VFQ-25 (Visual Function Questionnaire)
- PHQ-9 psychological outcomes
- Functional independence scores
- Goal attainment scaling (GAS)
"""

import json
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, date


# VFQ-25 Subscale Definitions
VFQ25_SUBSCALES = {
    "general_health": {
        "name": "الصحة العامة",
        "questions": [1],
        "weight": 1,
    },
    "general_vision": {
        "name": "الرؤية العامة",
        "questions": [2],
        "weight": 1,
    },
    "ocular_pain": {
        "name": "ألم العين",
        "questions": [4, 19],
        "weight": 1,
    },
    "near_activities": {
        "name": "الأنشطة القريبة",
        "questions": [5, 6, 7],
        "weight": 1,
    },
    "distance_activities": {
        "name": "الأنشطة البعيدة",
        "questions": [8, 9, 10],
        "weight": 1,
    },
    "vision_role": {
        "name": "دور الرؤية",
        "questions": [11, 13],
        "weight": 1,
    },
    "social_function": {
        "name": "الوظيفة الاجتماعية",
        "questions": [12, 14],
        "weight": 1,
    },
    "mental_health": {
        "name": "الصحة النفسية",
        "questions": [15, 16, 17, 18],
        "weight": 1,
    },
    "role_difficulties": {
        "name": "صعوبات الدور",
        "questions": [20, 21],
        "weight": 1,
    },
    "dependency": {
        "name": "الاعتماد على الآخرين",
        "questions": [22, 23],
        "weight": 1,
    },
    "driving": {
        "name": "القيادة",
        "questions": [],  # Optional subscale (15a, 15b, 15c)
        "weight": 0.5,
    },
    "color_vision": {
        "name": "رؤية الألوان",
        "questions": [24],
        "weight": 1,
    },
    "peripheral_vision": {
        "name": "الرؤية المحيطية",
        "questions": [25],
        "weight": 1,
    },
}

# Outcome measurement benchmarks
OUTCOME_BENCHMARKS = {
    "visual_acuity": {
        "improvement_significant": 0.1,   # LogMAR improvement considered significant
        "improvement_moderate": 0.2,
        "improvement_major": 0.3,
    },
    "reading_speed": {
        "improvement_significant": 10,    # WPM improvement threshold
        "functional_threshold": 60,       # WPM for functional reading
        "normal_threshold": 120,          # WPM for normal reading
    },
    "vfq25": {
        "improvement_significant": 5,     # Points improvement (0-100 scale)
        "improvement_moderate": 10,
        "minimal_clinically_important": 8,
    },
    "phq9": {
        "improvement_significant": 5,     # Points improvement
        "remission_threshold": 5,         # PHQ-9 ≤ 5 = remission
        "response_threshold": 50,         # 50% reduction = response
    },
}

# Goal Attainment Scale levels
GAS_LEVELS = {
    -2: "نتيجة أسوأ بكثير من المتوقع",
    -1: "نتيجة أسوأ قليلاً من المتوقع",
    0: "النتيجة المتوقعة (الهدف المحقق)",
    1: "نتيجة أفضل قليلاً من المتوقع",
    2: "نتيجة أفضل بكثير من المتوقع",
}


def track_rehabilitation_outcomes(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for outcome tracking.

    Supported action values:
    - record_assessment: Record a new assessment
    - compare_progress: Compare two assessment points
    - calculate_gas: Calculate Goal Attainment Scale
    - calculate_vfq25: Calculate VFQ-25 score
    - generate_report: Generate progress report
    - set_smart_goals: Set SMART rehabilitation goals

    Args:
        params: Dictionary with action and assessment data

    Returns:
        Dictionary with outcome data and analysis
    """
    action = params.get("action", "compare_progress")

    actions = {
        "record_assessment": _record_assessment,
        "compare_progress": _compare_progress,
        "calculate_gas": _calculate_gas,
        "calculate_vfq25": _calculate_vfq25,
        "generate_report": _generate_progress_report,
        "set_smart_goals": _set_smart_goals,
    }

    handler = actions.get(action)
    if not handler:
        return {
            "error": f"Unknown action: {action}",
            "available_actions": list(actions.keys())
        }

    return handler(params)


def _record_assessment(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Record a new assessment snapshot.
    Returns structured assessment record.
    """
    assessment_date = params.get("assessment_date", datetime.now().strftime("%Y-%m-%d"))
    assessment_number = params.get("assessment_number", 1)

    # Visual Acuity
    va_data = params.get("visual_acuity", {})
    logmar_va = None
    if va_data:
        logmar_va = _decimal_to_logmar(va_data.get("decimal")) if va_data.get("decimal") else None

    # Reading speed
    reading_data = params.get("reading", {})

    # PHQ-9
    phq9_score = params.get("phq9_score")

    # VFQ-25
    vfq25_data = params.get("vfq25", {})
    vfq25_result = None
    if vfq25_data:
        vfq25_result = _calculate_vfq25({"scores": vfq25_data})

    # Functional ADL
    adl_data = params.get("adl", {})
    adl_score = _calculate_adl_percentage(adl_data) if adl_data else None

    # Magnification usage
    mag_data = params.get("magnification", {})

    assessment_record = {
        "assessment_date": assessment_date,
        "assessment_number": assessment_number,
        "visual_acuity": {
            "decimal": va_data.get("decimal"),
            "snellen": va_data.get("snellen"),
            "logmar": round(logmar_va, 2) if logmar_va is not None else None,
            "near_va": va_data.get("near_va"),
            "contrast_sensitivity": va_data.get("contrast_sensitivity"),
        },
        "reading": {
            "speed_wpm": reading_data.get("speed_wpm"),
            "print_size_pt": reading_data.get("print_size_pt"),
            "text_type": reading_data.get("text_type", "plain"),
            "with_aids": reading_data.get("with_aids", False),
            "reading_distance_cm": reading_data.get("distance_cm"),
        },
        "psychological": {
            "phq9_score": phq9_score,
            "phq9_severity": _classify_phq9(phq9_score) if phq9_score is not None else None,
            "adjustment_stage": params.get("adjustment_stage"),
        },
        "functional": {
            "adl_percentage": adl_score,
            "adl_details": adl_data,
            "independence_level": _classify_independence(adl_score) if adl_score else None,
        },
        "vfq25": vfq25_result,
        "magnification_used": mag_data.get("power"),
        "devices_used": params.get("devices_used", []),
        "clinician_notes": params.get("notes", ""),
        "recorded_at": datetime.now().isoformat(),
    }

    return {
        "action": "record_assessment",
        "status": "recorded",
        "assessment": assessment_record,
        "summary": _summarize_assessment(assessment_record),
    }


def _compare_progress(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two assessment time points and calculate progress.
    """
    baseline = params.get("baseline", {})
    current = params.get("current", {})

    if not baseline or not current:
        # If only current data provided, create a simple baseline from params
        baseline = params.get("initial_values", {})
        current = params.get("current_values", params)

    comparison = {}

    # Visual Acuity comparison
    va_baseline = baseline.get("visual_acuity", {}) or {}
    va_current = current.get("visual_acuity", {}) or {}

    baseline_decimal = va_baseline.get("decimal") or params.get("baseline_va")
    current_decimal = va_current.get("decimal") or params.get("current_va")

    if baseline_decimal and current_decimal:
        baseline_logmar = _decimal_to_logmar(float(baseline_decimal))
        current_logmar = _decimal_to_logmar(float(current_decimal))
        logmar_change = baseline_logmar - current_logmar  # Positive = improvement

        comparison["visual_acuity"] = {
            "baseline_decimal": baseline_decimal,
            "current_decimal": current_decimal,
            "baseline_logmar": round(baseline_logmar, 2),
            "current_logmar": round(current_logmar, 2),
            "logmar_change": round(logmar_change, 2),
            "improved": logmar_change > 0,
            "significance": _classify_va_change(logmar_change),
        }

    # Reading speed comparison
    baseline_reading = baseline.get("reading", {}) or {}
    current_reading = current.get("reading", {}) or {}

    baseline_wpm = baseline_reading.get("speed_wpm") or params.get("baseline_wpm")
    current_wpm = current_reading.get("speed_wpm") or params.get("current_wpm")

    if baseline_wpm and current_wpm:
        wpm_change = float(current_wpm) - float(baseline_wpm)
        wpm_pct_change = (wpm_change / float(baseline_wpm)) * 100 if baseline_wpm else 0

        comparison["reading_speed"] = {
            "baseline_wpm": baseline_wpm,
            "current_wpm": current_wpm,
            "change_wpm": round(wpm_change, 1),
            "percent_change": round(wpm_pct_change, 1),
            "improved": wpm_change > 0,
            "now_functional": float(current_wpm) >= 60,
            "significance": _classify_reading_change(wpm_change, float(baseline_wpm)),
        }

    # PHQ-9 comparison
    baseline_phq9 = baseline.get("psychological", {}).get("phq9_score") or params.get("baseline_phq9")
    current_phq9 = current.get("psychological", {}).get("phq9_score") or params.get("current_phq9")

    if baseline_phq9 is not None and current_phq9 is not None:
        phq9_change = float(baseline_phq9) - float(current_phq9)  # Positive = improvement
        phq9_response = phq9_change >= float(baseline_phq9) * 0.5

        comparison["psychological"] = {
            "baseline_phq9": baseline_phq9,
            "current_phq9": current_phq9,
            "change": round(phq9_change, 1),
            "improved": phq9_change > 0,
            "treatment_response": phq9_response,
            "in_remission": float(current_phq9) <= 5,
            "significance": _classify_phq9_change(phq9_change),
        }

    # ADL comparison
    baseline_adl = baseline.get("functional", {}).get("adl_percentage") or params.get("baseline_adl")
    current_adl = current.get("functional", {}).get("adl_percentage") or params.get("current_adl")

    if baseline_adl and current_adl:
        adl_change = float(current_adl) - float(baseline_adl)
        comparison["functional_independence"] = {
            "baseline_pct": baseline_adl,
            "current_pct": current_adl,
            "change_pct": round(adl_change, 1),
            "improved": adl_change > 0,
            "classification": _classify_independence(float(current_adl)),
        }

    # VFQ-25 comparison
    baseline_vfq = baseline.get("vfq25", {}) or {}
    current_vfq = current.get("vfq25", {}) or {}

    baseline_vfq_total = baseline_vfq.get("composite_score") or params.get("baseline_vfq25")
    current_vfq_total = current_vfq.get("composite_score") or params.get("current_vfq25")

    if baseline_vfq_total and current_vfq_total:
        vfq_change = float(current_vfq_total) - float(baseline_vfq_total)
        comparison["quality_of_life"] = {
            "baseline_vfq25": baseline_vfq_total,
            "current_vfq25": current_vfq_total,
            "change": round(vfq_change, 1),
            "improved": vfq_change > 0,
            "clinically_meaningful": abs(vfq_change) >= 8,
        }

    # Overall progress summary
    overall_progress = _calculate_overall_progress(comparison)

    return {
        "action": "compare_progress",
        "time_points": {
            "baseline_date": baseline.get("assessment_date", "غير محدد"),
            "current_date": current.get("assessment_date", datetime.now().strftime("%Y-%m-%d")),
        },
        "domain_comparisons": comparison,
        "overall_progress": overall_progress,
        "recommendations": _generate_progress_recommendations(overall_progress, comparison),
    }


def _calculate_gas(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Goal Attainment Scale (GAS) scores.
    """
    goals = params.get("goals", [])
    if not goals:
        return {
            "error": "يرجى تحديد الأهداف (goals)",
            "example_goal": {
                "name": "قراءة الصحيفة",
                "level_minus2": "لا يستطيع قراءة أي شيء",
                "level_minus1": "يقرأ العناوين فقط بمكبر",
                "level_0": "يقرأ الجريدة بمكبر ×4",
                "level_plus1": "يقرأ بمكبر ×2",
                "level_plus2": "يقرأ بدون مكبر",
                "achieved_level": 0,
                "weight": 1,
            }
        }

    gas_scores = []
    weighted_sum = 0
    total_weight = 0

    for goal in goals:
        level = goal.get("achieved_level", 0)
        weight = float(goal.get("weight", 1))

        gas_scores.append({
            "goal_name": goal.get("name", "هدف"),
            "achieved_level": level,
            "level_description": GAS_LEVELS.get(level, ""),
            "goal_description_at_level": goal.get(f"level_{'+' if level >= 0 else ''}{level}", ""),
            "weight": weight,
        })

        # GAS formula: T = 50 + 10 * Σ(wi * xi) / sqrt(0.7 * Σ(wi²) + 0.3 * (Σwi)²)
        weighted_sum += weight * level
        total_weight += weight

    # GAS T-score calculation
    sum_w_sq = sum(float(g.get("weight", 1))**2 for g in goals)
    denominator = math.sqrt(0.7 * sum_w_sq + 0.3 * (total_weight**2))

    if denominator > 0:
        gas_t_score = 50 + 10 * (weighted_sum / denominator)
    else:
        gas_t_score = 50

    # Interpretation
    if gas_t_score >= 60:
        gas_interpretation = "تجاوز الأهداف - نتائج ممتازة"
    elif gas_t_score >= 50:
        gas_interpretation = "تحقيق الأهداف - نتائج جيدة جداً"
    elif gas_t_score >= 40:
        gas_interpretation = "تحقيق جزئي للأهداف - نتائج جيدة"
    else:
        gas_interpretation = "دون الأهداف المتوقعة - يحتاج مراجعة خطة التأهيل"

    goals_achieved = sum(1 for g in gas_scores if g["achieved_level"] >= 0)
    goals_exceeded = sum(1 for g in gas_scores if g["achieved_level"] > 0)

    return {
        "action": "calculate_gas",
        "gas_t_score": round(gas_t_score, 1),
        "interpretation": gas_interpretation,
        "goals_total": len(goals),
        "goals_achieved": goals_achieved,
        "goals_exceeded": goals_exceeded,
        "goal_details": gas_scores,
        "benchmark": "T=50 = الهدف المتوقع محقق. T>50 = تجاوز الأهداف. T<50 = دون الأهداف",
    }


def _calculate_vfq25(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate VFQ-25 (Visual Function Questionnaire) composite score.
    25-item questionnaire, scores 0-100 per subscale, composite 0-100.
    """
    scores = params.get("scores", {})
    if not scores:
        return {
            "error": "يرجى توفير درجات الأسئلة (scores)",
            "note": "VFQ-25 يحتوي على 25 سؤالاً، كل سؤال يُسجَّل 0-100"
        }

    # Subscale calculation (simplified)
    subscale_scores = {}
    available_subscales = []

    for subscale_key, subscale_info in VFQ25_SUBSCALES.items():
        if not subscale_info["questions"]:
            continue

        subscale_q_scores = []
        for q_num in subscale_info["questions"]:
            q_key = f"q{q_num}"
            if q_key in scores:
                raw = float(scores[q_key])
                # Convert to 0-100 scale (assuming 1-5 Likert → 0-100)
                if 1 <= raw <= 5:
                    converted = (5 - raw) / 4 * 100
                elif 0 <= raw <= 100:
                    converted = raw
                else:
                    converted = raw
                subscale_q_scores.append(converted)

        if subscale_q_scores:
            avg = sum(subscale_q_scores) / len(subscale_q_scores)
            subscale_scores[subscale_key] = {
                "name": subscale_info["name"],
                "score": round(avg, 1),
                "questions_answered": len(subscale_q_scores),
            }
            available_subscales.append(avg)

    # Composite score (excluding general health subscale per standard VFQ-25 protocol)
    non_gh_subscales = [
        v["score"] for k, v in subscale_scores.items()
        if k != "general_health" and k != "driving"
    ]

    composite_score = sum(non_gh_subscales) / len(non_gh_subscales) if non_gh_subscales else None

    # Interpretation
    if composite_score is not None:
        if composite_score >= 80:
            interpretation = "وظيفة بصرية جيدة إلى ممتازة"
        elif composite_score >= 60:
            interpretation = "وظيفة بصرية متوسطة - تأثير محدود على الحياة اليومية"
        elif composite_score >= 40:
            interpretation = "وظيفة بصرية منخفضة - تأثير متوسط على الحياة اليومية"
        else:
            interpretation = "وظيفة بصرية ضعيفة جداً - تأثير كبير على الحياة اليومية"
    else:
        interpretation = "غير كافٍ للتفسير"

    return {
        "action": "calculate_vfq25",
        "composite_score": round(composite_score, 1) if composite_score else None,
        "interpretation": interpretation,
        "subscale_scores": subscale_scores,
        "questions_answered": len(scores),
        "note": (
            "VFQ-25: 0 = أسوأ نتيجة، 100 = أفضل نتيجة. "
            "الحد الأدنى للفرق المهم سريرياً (MCID) = 8 نقاط"
        ),
    }


def _generate_progress_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate comprehensive rehabilitation progress report.
    """
    patient_info = params.get("patient_info", {})
    assessments = params.get("assessments", [])
    goals = params.get("goals", [])

    if len(assessments) < 2:
        return {
            "error": "يحتاج التقرير على الأقل تقييمين (تقييم أولي وحالي)",
            "provided_assessments": len(assessments),
        }

    baseline = assessments[0]
    current = assessments[-1]

    # Calculate progress
    progress = _compare_progress({"baseline": baseline, "current": current})

    # Calculate GAS if goals provided
    gas_result = None
    if goals:
        gas_result = _calculate_gas({"goals": goals})

    # Build report
    report_date = datetime.now().strftime("%Y-%m-%d")

    # Calculate duration
    baseline_date = baseline.get("assessment_date", "")
    current_date = current.get("assessment_date", report_date)

    report = {
        "action": "generate_report",
        "report_date": report_date,
        "patient_name": patient_info.get("name", "المريض"),
        "patient_id": patient_info.get("id", ""),
        "program_duration": f"{baseline_date} → {current_date}",
        "total_assessments": len(assessments),
        "overall_progress_rating": progress["overall_progress"]["rating"],
        "progress_summary": progress["overall_progress"]["summary"],
        "domain_progress": progress["domain_comparisons"],
        "gas_results": gas_result,
        "key_achievements": _extract_key_achievements(progress["domain_comparisons"]),
        "areas_needing_attention": _identify_areas_needing_attention(progress["domain_comparisons"]),
        "recommendations": progress["recommendations"],
        "next_steps": _generate_next_steps(progress, goals),
        "assessment_timeline": [
            {
                "date": a.get("assessment_date"),
                "va_decimal": a.get("visual_acuity", {}).get("decimal"),
                "reading_wpm": a.get("reading", {}).get("speed_wpm"),
                "phq9": a.get("psychological", {}).get("phq9_score"),
            }
            for a in assessments
        ],
    }

    return report


def _set_smart_goals(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set SMART (Specific, Measurable, Achievable, Relevant, Time-bound) goals
    for vision rehabilitation.
    """
    current_va = params.get("current_visual_acuity")
    patient_priorities = params.get("patient_priorities", [])
    time_frame_weeks = params.get("time_frame_weeks", 12)
    current_reading_wpm = params.get("current_reading_wpm", 0)

    goals = []

    # Parse VA
    decimal_va = None
    if current_va:
        try:
            from tools.arabic_reading_calculator import _parse_va_to_decimal
            decimal_va = _parse_va_to_decimal(str(current_va))
        except Exception:
            pass

    # Goal 1: Reading improvement (most common priority)
    if not patient_priorities or "reading" in patient_priorities:
        target_wpm = min((current_reading_wpm or 20) * 2, 120)
        goals.append({
            "goal_id": "G1",
            "category": "reading",
            "smart_goal": (
                f"أن يتمكن المريض من قراءة النصوص العربية بسرعة {target_wpm} كلمة/دقيقة "
                f"باستخدام المساعدات البصرية المناسبة خلال {time_frame_weeks} أسبوعاً"
            ),
            "specific": f"قراءة نص عربي قياسي بخط {14 if decimal_va and decimal_va >= 0.2 else 20}pt",
            "measurable": f"قياس بـ MNREAD-A test، الهدف {target_wpm} كلمة/دقيقة",
            "achievable": "قابل للتحقيق مع 6-8 جلسات تدريبية",
            "relevant": "مهم للحياة اليومية والقرآن والصحف",
            "time_bound": f"{time_frame_weeks} أسبوعاً",
            "measurement_tool": "MNREAD-A Arabic",
            "baseline_wpm": current_reading_wpm,
            "target_wpm": target_wpm,
        })

    # Goal 2: Device mastery
    if not patient_priorities or "device" in patient_priorities:
        goals.append({
            "goal_id": "G2",
            "category": "assistive_technology",
            "smart_goal": (
                f"أن يستخدم المريض المكبر الموصى به باستقلالية كاملة خلال {time_frame_weeks // 2} أسبوعاً"
            ),
            "specific": "استخدام المكبر لمهام محددة: قراءة الوصفات، الفواتير، الرسائل",
            "measurable": "تقييم عملي: 3 مهام ناجحة متتالية بدون مساعدة",
            "achievable": "قابل للتحقيق مع 4-6 جلسات تدريبية",
            "relevant": "ضروري للاستقلالية اليومية",
            "time_bound": f"{time_frame_weeks // 2} أسبوعاً",
        })

    # Goal 3: ADL independence
    if not patient_priorities or "adl" in patient_priorities:
        goals.append({
            "goal_id": "G3",
            "category": "functional_independence",
            "smart_goal": (
                "أن يؤدي المريض 5 مهام حياة يومية بشكل مستقل بنسبة ≥80% خلال 8 أسابيع"
            ),
            "specific": "مهام: تناول الدواء، الطهي الأساسي، التنقل في المنزل، العناية الشخصية، استخدام الهاتف",
            "measurable": "مقياس الاستقلالية الوظيفية (ADL score) ≥80%",
            "achievable": "مع تدريب تعويضي وتعديل البيئة المنزلية",
            "relevant": "يحسن جودة الحياة والكرامة الشخصية",
            "time_bound": "8 أسابيع",
        })

    # Goal 4: Psychological
    if not patient_priorities or "psychological" in patient_priorities:
        goals.append({
            "goal_id": "G4",
            "category": "psychological_wellbeing",
            "smart_goal": (
                f"أن تتحسن نتيجة PHQ-9 بمقدار ≥5 نقاط خلال {time_frame_weeks} أسبوعاً"
            ),
            "specific": "تقليل أعراض الاكتئاب وزيادة التكيف مع ضعف البصر",
            "measurable": "PHQ-9 score بداية المرحلة مقارنة بنهايتها",
            "achievable": "مع دعم نفسي منتظم وجلسات تأهيل",
            "relevant": "الاكتئاب يعيق كل محاور التأهيل",
            "time_bound": f"{time_frame_weeks} أسبوعاً",
        })

    return {
        "action": "set_smart_goals",
        "time_frame_weeks": time_frame_weeks,
        "goals_count": len(goals),
        "goals": goals,
        "goal_attainment_scale_template": {
            "level_minus2": "لا تقدم أو تراجع",
            "level_minus1": "تقدم جزئي (أقل من المتوقع)",
            "level_0": "تحقيق الهدف بالكامل",
            "level_plus1": "تجاوز الهدف قليلاً",
            "level_plus2": "تجاوز الهدف بشكل ملحوظ",
        },
        "review_schedule": [
            {"week": time_frame_weeks // 4, "focus": "مراجعة مبكرة - تعديل الأهداف إذا لزم"},
            {"week": time_frame_weeks // 2, "focus": "مراجعة منتصف المرحلة"},
            {"week": time_frame_weeks, "focus": "تقييم نهائي وتحديد أهداف مرحلة قادمة"},
        ],
    }


# --- Helper Functions ---

def _decimal_to_logmar(decimal_va: float) -> float:
    """Convert decimal VA to LogMAR."""
    if decimal_va <= 0:
        return 3.0  # Maximum LogMAR for NLP
    return -math.log10(decimal_va)


def _classify_va_change(logmar_change: float) -> str:
    """Classify significance of VA change."""
    if logmar_change >= 0.3:
        return "تحسن كبير (≥3 أسطر)"
    elif logmar_change >= 0.2:
        return "تحسن متوسط (2 سطر)"
    elif logmar_change >= 0.1:
        return "تحسن طفيف (1 سطر)"
    elif logmar_change > -0.1:
        return "مستقر (بدون تغيير ذي أهمية)"
    elif logmar_change >= -0.2:
        return "تراجع طفيف"
    else:
        return "تراجع ملحوظ"


def _classify_reading_change(wpm_change: float, baseline: float) -> str:
    """Classify significance of reading speed change."""
    if baseline > 0:
        pct = (wpm_change / baseline) * 100
        if pct >= 50:
            return "تحسن كبير جداً (>50%)"
        elif pct >= 25:
            return "تحسن جيد (25-50%)"
        elif pct >= 10:
            return "تحسن طفيف (10-25%)"
        elif pct > -10:
            return "مستقر"
        else:
            return "تراجع"
    return "لا يمكن تصنيفه"


def _classify_phq9(score: Optional[int]) -> str:
    """Classify PHQ-9 severity."""
    if score is None:
        return "غير محدد"
    score = int(score)
    if score <= 4:
        return "ضئيل"
    elif score <= 9:
        return "خفيف"
    elif score <= 14:
        return "متوسط"
    elif score <= 19:
        return "متوسط-شديد"
    else:
        return "شديد"


def _classify_phq9_change(change: float) -> str:
    """Classify PHQ-9 improvement."""
    if change >= 10:
        return "تحسن نفسي كبير"
    elif change >= 5:
        return "استجابة للعلاج (≥50% تخفيض)"
    elif change >= 2:
        return "تحسن طفيف"
    elif change > -2:
        return "مستقر"
    else:
        return "تدهور - يحتاج مراجعة"


def _classify_independence(adl_pct: float) -> str:
    """Classify ADL independence level."""
    if adl_pct >= 90:
        return "مستقل تماماً"
    elif adl_pct >= 75:
        return "مستقل مع بعض التكيفات"
    elif adl_pct >= 50:
        return "يحتاج مساعدة جزئية"
    elif adl_pct >= 25:
        return "يحتاج مساعدة كبيرة"
    else:
        return "يعتمد اعتماداً كبيراً على الآخرين"


def _calculate_adl_percentage(adl_data: dict) -> float:
    """Calculate ADL independence percentage from activity scores."""
    if not adl_data:
        return 0
    scores = [v for v in adl_data.values() if isinstance(v, (int, float))]
    if not scores:
        return 0
    # Assume 0-3 scale, 3 = fully independent
    avg = sum(scores) / len(scores)
    return round((avg / 3) * 100, 1)


def _calculate_overall_progress(comparison: dict) -> dict:
    """Calculate overall progress across domains."""
    improved_domains = []
    stable_domains = []
    declined_domains = []

    for domain, data in comparison.items():
        if isinstance(data, dict) and "improved" in data:
            if data["improved"]:
                improved_domains.append(domain)
            elif data.get("change", 0) == 0:
                stable_domains.append(domain)
            else:
                declined_domains.append(domain)

    total = len(improved_domains) + len(stable_domains) + len(declined_domains)

    if total == 0:
        return {"rating": "غير كافٍ", "summary": "بيانات غير كافية للمقارنة"}

    improvement_pct = len(improved_domains) / total * 100

    if improvement_pct >= 75:
        rating = "ممتاز"
    elif improvement_pct >= 50:
        rating = "جيد"
    elif improvement_pct >= 25:
        rating = "متوسط"
    elif len(declined_domains) > len(improved_domains):
        rating = "يحتاج مراجعة"
    else:
        rating = "مستقر"

    return {
        "rating": rating,
        "improved_domains": improved_domains,
        "stable_domains": stable_domains,
        "declined_domains": declined_domains,
        "improvement_percentage": round(improvement_pct, 0),
        "summary": (
            f"تحسن في {len(improved_domains)} من {total} مجالات. "
            f"مستقر في {len(stable_domains)}. "
            f"تراجع في {len(declined_domains)}."
        )
    }


def _generate_progress_recommendations(overall: dict, comparison: dict) -> list:
    """Generate recommendations based on progress analysis."""
    recs = []

    if "visual_acuity" in comparison and not comparison["visual_acuity"].get("improved"):
        recs.append("مراجعة قوة العدسات أو أجهزة التكبير المستخدمة")

    if "reading_speed" in comparison:
        if not comparison["reading_speed"].get("now_functional"):
            recs.append("مواصلة التدريب على القراءة بضعف البصر (تكثيف الجلسات)")

    if "psychological" in comparison and not comparison["psychological"].get("improved"):
        recs.append("مراجعة الدعم النفسي وتكثيفه إذا لزم")

    if overall.get("rating") in ["يحتاج مراجعة"]:
        recs.append("مراجعة شاملة لخطة التأهيل مع المريض وعائلته")

    recs.append("متابعة التقييم الدوري كل 4-6 أسابيع")

    return recs


def _extract_key_achievements(comparison: dict) -> list:
    """Extract key achievements from comparison data."""
    achievements = []

    if "visual_acuity" in comparison and comparison["visual_acuity"].get("improved"):
        change = comparison["visual_acuity"].get("significance", "")
        achievements.append(f"تحسن في حدة البصر: {change}")

    if "reading_speed" in comparison and comparison["reading_speed"].get("improved"):
        change = comparison["reading_speed"].get("change_wpm", 0)
        achievements.append(f"تحسن سرعة القراءة بـ {change} كلمة/دقيقة")
        if comparison["reading_speed"].get("now_functional"):
            achievements.append("وصل المريض لمستوى القراءة الوظيفية (≥60 كلمة/دقيقة)")

    if "psychological" in comparison and comparison["psychological"].get("in_remission"):
        achievements.append("تحقيق هدأة الأعراض الاكتئابية (PHQ-9 ≤ 5)")

    if "functional_independence" in comparison and comparison["functional_independence"].get("improved"):
        achievements.append(f"تحسن الاستقلالية الوظيفية: {comparison['functional_independence'].get('change_pct', 0)}%")

    return achievements if achievements else ["لم تُسجَّل إنجازات محددة بعد"]


def _identify_areas_needing_attention(comparison: dict) -> list:
    """Identify areas that need more attention."""
    areas = []

    for domain, data in comparison.items():
        if isinstance(data, dict) and not data.get("improved") and data.get("change", 0) < 0:
            areas.append(domain)

    return areas if areas else []


def _generate_next_steps(progress: dict, goals: list) -> list:
    """Generate next steps based on progress."""
    steps = []

    overall = progress.get("overall_progress", {})
    if overall.get("rating") in ["ممتاز", "جيد"]:
        steps.append("تحديد أهداف مرحلة قادمة أكثر تحدياً")
    else:
        steps.append("مراجعة وتعديل الأهداف الحالية")

    steps.append("جدولة التقييم التالي بعد 4-6 أسابيع")

    declined = overall.get("declined_domains", [])
    for domain in declined:
        steps.append(f"تكثيف التدخل في: {domain}")

    return steps


def _summarize_assessment(assessment: dict) -> str:
    """Create a brief text summary of an assessment."""
    parts = []

    va = assessment.get("visual_acuity", {})
    if va.get("decimal"):
        parts.append(f"VA: {va['decimal']}")

    reading = assessment.get("reading", {})
    if reading.get("speed_wpm"):
        parts.append(f"قراءة: {reading['speed_wpm']} ك/د")

    psych = assessment.get("psychological", {})
    if psych.get("phq9_score") is not None:
        parts.append(f"PHQ-9: {psych['phq9_score']}")

    return " | ".join(parts) if parts else "تقييم مسجل"
