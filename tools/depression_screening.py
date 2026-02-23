"""
Depression & Psychological Screening Tool
أداة الفحص النفسي وفحص الاكتئاب

Implements evidence-based screening tools for psychological assessment
in low vision rehabilitation:
- PHQ-2 (Primary screening, 2 questions)
- PHQ-9 (Full depression assessment, 9 questions)
- GDS-15 (Geriatric Depression Scale for elderly patients)
- Vision-specific psychological adjustment stages
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


# PHQ-9 Questions (Arabic + English)
PHQ9_QUESTIONS = [
    {
        "id": 1,
        "arabic": "فقدان الاهتمام أو المتعة في فعل الأشياء",
        "english": "Little interest or pleasure in doing things",
        "category": "anhedonia"
    },
    {
        "id": 2,
        "arabic": "الشعور بالاكتئاب أو اليأس أو انعدام الأمل",
        "english": "Feeling down, depressed, or hopeless",
        "category": "depressed_mood"
    },
    {
        "id": 3,
        "arabic": "صعوبة في النوم أو الاستمرار في النوم، أو النوم الزائد",
        "english": "Trouble falling/staying asleep, or sleeping too much",
        "category": "sleep"
    },
    {
        "id": 4,
        "arabic": "الشعور بالتعب أو نقص الطاقة",
        "english": "Feeling tired or having little energy",
        "category": "fatigue"
    },
    {
        "id": 5,
        "arabic": "سوء الشهية أو الإفراط في الأكل",
        "english": "Poor appetite or overeating",
        "category": "appetite"
    },
    {
        "id": 6,
        "arabic": "الشعور بالسوء تجاه نفسك، أو أنك فاشل أو خذلت نفسك أو عائلتك",
        "english": "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
        "category": "guilt"
    },
    {
        "id": 7,
        "arabic": "صعوبة في التركيز على الأشياء، كقراءة الجريدة أو مشاهدة التلفاز",
        "english": "Trouble concentrating on things, such as reading the newspaper or watching television",
        "category": "concentration"
    },
    {
        "id": 8,
        "arabic": "التحرك أو الكلام ببطء شديد لدرجة أن الآخرين قد لاحظوا ذلك؟ أو العكس - الانفعال أو الاضطراب بشكل متزايد",
        "english": "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless",
        "category": "psychomotor"
    },
    {
        "id": 9,
        "arabic": "أفكار بأنك أفضل لو كنت ميتاً أو إيذاء نفسك بطريقة ما",
        "english": "Thoughts that you would be better off dead or of hurting yourself in some way",
        "category": "suicidal_ideation"
    },
]

# PHQ-9 Scoring
PHQ9_RESPONSE_OPTIONS = {
    0: {"arabic": "إطلاقاً", "english": "Not at all"},
    1: {"arabic": "عدة أيام", "english": "Several days"},
    2: {"arabic": "أكثر من نصف الأيام", "english": "More than half the days"},
    3: {"arabic": "كل يوم تقريباً", "english": "Nearly every day"},
}

# PHQ-9 Severity Classification
PHQ9_SEVERITY = {
    (0, 4): {
        "level": "minimal",
        "arabic": "أعراض ضئيلة أو لا يوجد اكتئاب",
        "english": "Minimal or no depression",
        "action": "مراقبة - لا يحتاج تدخل فوري",
        "color": "green"
    },
    (5, 9): {
        "level": "mild",
        "arabic": "اكتئاب خفيف",
        "english": "Mild depression",
        "action": "تدعيم نفسي - متابعة خلال شهر",
        "color": "yellow"
    },
    (10, 14): {
        "level": "moderate",
        "arabic": "اكتئاب متوسط",
        "english": "Moderate depression",
        "action": "يُنصح بالتقييم من متخصص نفسي",
        "color": "orange"
    },
    (15, 19): {
        "level": "moderately_severe",
        "arabic": "اكتئاب متوسط إلى شديد",
        "english": "Moderately severe depression",
        "action": "إحالة عاجلة للطب النفسي",
        "color": "red"
    },
    (20, 27): {
        "level": "severe",
        "arabic": "اكتئاب شديد",
        "english": "Severe depression",
        "action": "إحالة فورية للطب النفسي",
        "color": "dark_red"
    },
}

# GDS-15 Questions (Geriatric Depression Scale)
GDS15_QUESTIONS = [
    {"id": 1, "arabic": "هل أنت راضٍ بشكل عام عن حياتك؟", "positive_answer": "لا", "weight": 1},
    {"id": 2, "arabic": "هل تخليت عن كثير من أنشطتك واهتماماتك؟", "positive_answer": "نعم", "weight": 1},
    {"id": 3, "arabic": "هل تشعر أن حياتك فارغة؟", "positive_answer": "نعم", "weight": 1},
    {"id": 4, "arabic": "هل تشعر بالملل في كثير من الأحيان؟", "positive_answer": "نعم", "weight": 1},
    {"id": 5, "arabic": "هل أنت في مزاج جيد في معظم الوقت؟", "positive_answer": "لا", "weight": 1},
    {"id": 6, "arabic": "هل تخشى أن يحدث لك شيء سيء؟", "positive_answer": "نعم", "weight": 1},
    {"id": 7, "arabic": "هل تشعر بالسعادة في معظم الوقت؟", "positive_answer": "لا", "weight": 1},
    {"id": 8, "arabic": "هل تشعر في كثير من الأحيان بأنك عاجز؟", "positive_answer": "نعم", "weight": 1},
    {"id": 9, "arabic": "هل تفضل البقاء في المنزل بدلاً من الخروج وفعل أشياء جديدة؟", "positive_answer": "نعم", "weight": 1},
    {"id": 10, "arabic": "هل تشعر أن لديك مشاكل أكثر في الذاكرة مقارنة بمعظم الناس؟", "positive_answer": "نعم", "weight": 1},
    {"id": 11, "arabic": "هل تعتقد أنه من الرائع أن تكون حياً الآن؟", "positive_answer": "لا", "weight": 1},
    {"id": 12, "arabic": "هل تشعر بعدم القيمة بالطريقة التي أنت عليها الآن؟", "positive_answer": "نعم", "weight": 1},
    {"id": 13, "arabic": "هل تشعر بالنشاط والحيوية؟", "positive_answer": "لا", "weight": 1},
    {"id": 14, "arabic": "هل تشعر أن وضعك ميؤوس منه؟", "positive_answer": "نعم", "weight": 1},
    {"id": 15, "arabic": "هل تعتقد أن معظم الناس في وضع أفضل منك؟", "positive_answer": "نعم", "weight": 1},
]

# GDS-15 Severity
GDS15_SEVERITY = {
    (0, 4): {"level": "normal", "arabic": "طبيعي", "action": "لا يحتاج تدخل"},
    (5, 8): {"level": "mild", "arabic": "اكتئاب خفيف محتمل", "action": "متابعة ودعم نفسي"},
    (9, 11): {"level": "moderate", "arabic": "اكتئاب متوسط محتمل", "action": "تقييم من متخصص"},
    (12, 15): {"level": "severe", "arabic": "اكتئاب شديد محتمل", "action": "إحالة عاجلة للطب النفسي"},
}

# Vision loss adjustment stages (Kübler-Ross adaptation for vision loss)
VISION_LOSS_ADJUSTMENT_STAGES = {
    1: {
        "name": "الإنكار",
        "arabic_desc": "رفض تصديق التشخيص، تأخير طلب المساعدة",
        "interventions": [
            "الاستماع الفعال بدون مواجهة",
            "تقديم معلومات واضحة عن التشخيص",
            "إتاحة الوقت للمعالجة",
        ]
    },
    2: {
        "name": "الغضب",
        "arabic_desc": "غضب من الوضع، من الطبيب، من العائلة",
        "interventions": [
            "قبول التعبير عن الغضب دون حكم",
            "توجيه الطاقة نحو التأهيل",
            "دعم الأسرة لفهم هذه المرحلة",
        ]
    },
    3: {
        "name": "المساومة",
        "arabic_desc": "البحث عن علاجات بديلة، الأمل في التعافي الكامل",
        "interventions": [
            "تقديم معلومات دقيقة عن التوقعات",
            "تعزيز الأهداف الواقعية",
            "الانفتاح على البدائل والمساعدات التقنية",
        ]
    },
    4: {
        "name": "الاكتئاب",
        "arabic_desc": "حزن عميق، انسحاب اجتماعي، فقدان الأمل",
        "interventions": [
            "فحص PHQ-9 / PHQ-2 رسمياً",
            "إحالة للدعم النفسي إذا لزم",
            "دعم مجموعي مع أشخاص بنفس الوضع",
        ]
    },
    5: {
        "name": "القبول",
        "arabic_desc": "تقبل الواقع، الانخراط في التأهيل، إيجاد معنى جديد",
        "interventions": [
            "تعزيز الاستقلالية",
            "تطوير مهارات تعويضية",
            "الانخراط في المجتمع والأنشطة",
        ]
    },
}


def run_depression_screening(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for depression screening tools.

    Supported screening_type values:
    - phq2: PHQ-2 quick screening
    - phq9: Full PHQ-9 assessment
    - gds15: Geriatric Depression Scale
    - adjustment_assessment: Vision loss adjustment stage assessment
    - full_psychological: Complete psychological screening

    Args:
        params: Dictionary with screening type and patient data

    Returns:
        Dictionary with screening results and recommendations
    """
    screening_type = params.get("screening_type", "phq2")

    screeners = {
        "phq2": _run_phq2,
        "phq9": _run_phq9,
        "gds15": _run_gds15,
        "adjustment_assessment": _assess_adjustment_stage,
        "full_psychological": _full_psychological_screening,
    }

    screener = screeners.get(screening_type)
    if not screener:
        return {
            "error": f"Unknown screening type: {screening_type}",
            "available_types": list(screeners.keys())
        }

    return screener(params)


def _run_phq2(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    PHQ-2: Two-question primary depression screen.
    Covers questions 1 and 2 of PHQ-9.
    Score ≥ 3 requires full PHQ-9 assessment.
    """
    scores = params.get("scores", {})
    q1_score = int(scores.get("q1", params.get("q1_score", 0)))
    q2_score = int(scores.get("q2", params.get("q2_score", 0)))

    total = q1_score + q2_score

    if total < 0 or total > 6:
        return {"error": "درجات PHQ-2 يجب أن تكون بين 0-6"}

    if total >= 3:
        result = "إيجابي - يحتاج تقييم PHQ-9 كامل"
        positive = True
        urgency = "متوسط"
        next_step = "إجراء PHQ-9 الكامل"
    else:
        result = "سلبي - خطر منخفض للاكتئاب"
        positive = False
        urgency = "منخفض"
        next_step = "مراقبة دورية"

    return {
        "screening_type": "PHQ-2",
        "scores": {
            "q1_anhedonia": q1_score,
            "q2_depressed_mood": q2_score,
            "total": total,
            "max_possible": 6,
        },
        "result": result,
        "is_positive": positive,
        "urgency": urgency,
        "next_step": next_step,
        "questions_asked": [
            f"Q1: {PHQ9_QUESTIONS[0]['arabic']} → {PHQ9_RESPONSE_OPTIONS[q1_score]['arabic']}",
            f"Q2: {PHQ9_QUESTIONS[1]['arabic']} → {PHQ9_RESPONSE_OPTIONS[q2_score]['arabic']}",
        ],
        "vision_rehab_note": (
            "في تأهيل ضعف البصر، يُنصح بإجراء PHQ-2 عند كل زيارة. "
            "الخسارة البصرية ترفع خطر الاكتئاب 3-5 أضعاف."
        ),
        "timestamp": datetime.now().isoformat(),
    }


def _run_phq9(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    PHQ-9: Full 9-question depression assessment.
    """
    scores_input = params.get("scores", {})
    patient_name = params.get("patient_name", "المريض")
    va_context = params.get("visual_acuity_context", "")
    vision_loss_duration = params.get("vision_loss_duration_months")

    # Validate and collect scores
    question_scores = []
    total_score = 0
    missing_questions = []

    for i, q in enumerate(PHQ9_QUESTIONS):
        key = f"q{q['id']}"
        alt_keys = [key, f"q{i+1}", str(i), str(i+1)]

        score = None
        for k in alt_keys:
            if k in scores_input:
                score = int(scores_input[k])
                break

        if score is None:
            missing_questions.append(q['id'])
            score = 0  # Default to 0 if missing

        if score < 0 or score > 3:
            return {"error": f"الدرجة للسؤال {q['id']} يجب أن تكون بين 0-3"}

        question_scores.append({
            "question_id": q['id'],
            "category": q['category'],
            "arabic": q['arabic'],
            "score": score,
            "response": PHQ9_RESPONSE_OPTIONS[score]['arabic'],
        })
        total_score += score

    # Safety check for question 9 (suicidal ideation)
    q9_score = question_scores[8]['score']
    suicidal_alert = q9_score > 0

    # Determine severity
    severity_info = None
    for (low, high), info in PHQ9_SEVERITY.items():
        if low <= total_score <= high:
            severity_info = info
            break

    # Functional impairment (from params or estimated from score)
    functional_score = params.get("functional_impairment", None)
    if functional_score is None:
        if total_score <= 4:
            functional_impairment = "لا اضطراب وظيفي"
        elif total_score <= 9:
            functional_impairment = "اضطراب وظيفي طفيف"
        elif total_score <= 14:
            functional_impairment = "اضطراب وظيفي متوسط"
        elif total_score <= 19:
            functional_impairment = "اضطراب وظيفي شديد"
        else:
            functional_impairment = "اضطراب وظيفي بالغ الشدة"
    else:
        functional_impairment = functional_score

    # Vision-specific risk factors
    vision_risk_factors = _assess_vision_depression_risk(va_context, vision_loss_duration)

    # Recommendations
    recommendations = _generate_phq9_recommendations(
        total_score, severity_info, suicidal_alert, vision_risk_factors
    )

    result = {
        "screening_type": "PHQ-9",
        "patient": patient_name,
        "scores": {
            "total": total_score,
            "max_possible": 27,
            "percentage": round(total_score / 27 * 100, 1),
        },
        "severity": {
            "level": severity_info["level"] if severity_info else "unknown",
            "arabic": severity_info["arabic"] if severity_info else "",
            "english": severity_info["english"] if severity_info else "",
            "color_indicator": severity_info["color"] if severity_info else "gray",
        },
        "functional_impairment": functional_impairment,
        "question_breakdown": question_scores,
        "safety_alert": {
            "suicidal_ideation": suicidal_alert,
            "q9_score": q9_score,
            "action_required": "إجراء تقييم خطر الانتحار فوراً" if suicidal_alert else None,
        },
        "missing_questions": missing_questions if missing_questions else None,
        "vision_risk_factors": vision_risk_factors,
        "recommendations": recommendations,
        "follow_up": {
            "minimal": "6 أشهر",
            "mild": "4 أسابيع",
            "moderate": "أسبوعان",
            "moderately_severe": "أسبوع",
            "severe": "فوري",
        }.get(severity_info["level"] if severity_info else "minimal", "شهر"),
        "timestamp": datetime.now().isoformat(),
    }

    # URGENT flag
    if suicidal_alert or (severity_info and severity_info["level"] in ["moderately_severe", "severe"]):
        result["URGENT"] = True
        result["urgent_action"] = (
            "⚠️ تنبيه عاجل: يحتاج هذا المريض تقييماً نفسياً فورياً. "
            "لا تترك المريض وحده. اتصل بالطب النفسي."
        )

    return result


def _run_gds15(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    GDS-15: Geriatric Depression Scale (short form, 15 items).
    Specific for patients 65+ years.
    """
    scores_input = params.get("answers", params.get("scores", {}))
    patient_age = params.get("patient_age", 70)

    # Age check
    age = int(patient_age) if str(patient_age).isdigit() else 70
    if age < 65:
        return {
            "warning": "GDS-15 مصمم للمرضى 65 سنة فأكثر. للمرضى الأصغر، استخدم PHQ-9.",
            "recommendation": "استخدم PHQ-9 للمرضى دون 65 سنة"
        }

    total_score = 0
    question_results = []
    missing = []

    for q in GDS15_QUESTIONS:
        key = f"q{q['id']}"
        answer = scores_input.get(key, scores_input.get(str(q['id'])))

        if answer is None:
            missing.append(q['id'])
            continue

        # Normalize answer
        answer_normalized = str(answer).strip()
        if answer_normalized in ["نعم", "yes", "1", "true", "True"]:
            answer_yn = "نعم"
        else:
            answer_yn = "لا"

        # Score based on expected positive answer
        if answer_yn == q['positive_answer']:
            score = 1
        else:
            score = 0

        total_score += score
        question_results.append({
            "id": q['id'],
            "question": q['arabic'],
            "answer": answer_yn,
            "scored": score,
        })

    # Get severity
    severity_info = None
    for (low, high), info in GDS15_SEVERITY.items():
        if low <= total_score <= high:
            severity_info = info
            break

    return {
        "screening_type": "GDS-15",
        "patient_age": age,
        "scores": {
            "total": total_score,
            "max_possible": 15,
            "answered_questions": len(question_results),
        },
        "severity": severity_info if severity_info else {"level": "unknown"},
        "question_results": question_results,
        "missing_questions": missing if missing else None,
        "recommendations": _generate_gds15_recommendations(total_score, severity_info),
        "elderly_vision_note": (
            "كبار السن مع ضعف البصر أكثر عرضة للعزلة الاجتماعية والاكتئاب. "
            "تقييم شبكة الدعم الاجتماعي ضروري."
        ),
        "timestamp": datetime.now().isoformat(),
    }


def _assess_adjustment_stage(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess patient's psychological adjustment stage to vision loss.
    """
    indicators = params.get("clinical_indicators", {})
    patient_description = params.get("description", "")
    months_since_diagnosis = params.get("months_since_diagnosis", 0)

    # Stage indicators
    stage_scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Stage 1: Denial
    if indicators.get("denies_diagnosis"):
        stage_scores[1] += 3
    if indicators.get("delays_seeking_help"):
        stage_scores[1] += 2
    if indicators.get("minimizes_visual_loss"):
        stage_scores[1] += 2
    if indicators.get("shops_for_second_opinions"):
        stage_scores[1] += 1

    # Stage 2: Anger
    if indicators.get("expresses_anger_frequently"):
        stage_scores[2] += 3
    if indicators.get("blames_medical_team"):
        stage_scores[2] += 2
    if indicators.get("family_conflict_increased"):
        stage_scores[2] += 2
    if indicators.get("refuses_help"):
        stage_scores[2] += 1

    # Stage 3: Bargaining
    if indicators.get("seeks_alternative_treatments"):
        stage_scores[3] += 3
    if indicators.get("unrealistic_recovery_expectations"):
        stage_scores[3] += 2
    if indicators.get("religious_bargaining_statements"):
        stage_scores[3] += 2

    # Stage 4: Depression
    if indicators.get("social_withdrawal"):
        stage_scores[4] += 3
    if indicators.get("phq9_score") and int(indicators.get("phq9_score", 0)) >= 10:
        stage_scores[4] += 4
    if indicators.get("appetite_changes"):
        stage_scores[4] += 1
    if indicators.get("sleep_disturbance"):
        stage_scores[4] += 1
    if indicators.get("loss_of_interest"):
        stage_scores[4] += 2

    # Stage 5: Acceptance
    if indicators.get("uses_assistive_devices"):
        stage_scores[5] += 3
    if indicators.get("engaged_in_rehabilitation"):
        stage_scores[5] += 3
    if indicators.get("realistic_goals"):
        stage_scores[5] += 2
    if indicators.get("reconnected_socially"):
        stage_scores[5] += 2
    if indicators.get("finds_new_meaning"):
        stage_scores[5] += 2

    # Determine primary and secondary stages
    max_score = max(stage_scores.values())
    if max_score == 0:
        primary_stage = 1  # Default to denial if no indicators
    else:
        primary_stage = max(stage_scores, key=stage_scores.get)

    # Secondary stage
    sorted_stages = sorted(stage_scores.items(), key=lambda x: x[1], reverse=True)
    secondary_stage = sorted_stages[1][0] if sorted_stages[1][1] > 0 else None

    # Time-based expectations
    expected_stage_by_time = {
        0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 6: 3,
        9: 4, 12: 4, 18: 5, 24: 5
    }
    expected_stage = 1
    for months, stage in sorted(expected_stage_by_time.items()):
        if months_since_diagnosis >= months:
            expected_stage = stage

    stuck_in_grief = primary_stage < expected_stage and months_since_diagnosis > 6

    return {
        "screening_type": "adjustment_assessment",
        "primary_adjustment_stage": primary_stage,
        "stage_name": VISION_LOSS_ADJUSTMENT_STAGES[primary_stage]["name"],
        "stage_description": VISION_LOSS_ADJUSTMENT_STAGES[primary_stage]["arabic_desc"],
        "secondary_stage": secondary_stage,
        "stage_scores": stage_scores,
        "months_since_diagnosis": months_since_diagnosis,
        "expected_stage_by_time": expected_stage,
        "stuck_in_grief": stuck_in_grief,
        "interventions": VISION_LOSS_ADJUSTMENT_STAGES[primary_stage]["interventions"],
        "all_stages_reference": {
            str(k): {"name": v["name"], "description": v["arabic_desc"]}
            for k, v in VISION_LOSS_ADJUSTMENT_STAGES.items()
        },
        "note": (
            "⚠️ يُنصح بالإحالة للدعم النفسي المتخصص إذا تجاوز وقت مرحلة الاكتئاب 3 أشهر"
            if stuck_in_grief and primary_stage == 4 else
            "التقدم في مراحل التكيف يختلف من شخص لآخر - لا يوجد وقت 'صحيح' للتعافي"
        ),
        "timestamp": datetime.now().isoformat(),
    }


def _full_psychological_screening(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete psychological screening combining PHQ-2/9, adjustment assessment,
    and vision-specific risk factors.
    """
    patient_age = params.get("patient_age", 50)
    age = int(patient_age) if str(patient_age).isdigit() else 50

    # Run PHQ-2 first
    phq2_scores = params.get("phq2_scores", {"q1": 0, "q2": 0})
    phq2_result = _run_phq2({"scores": phq2_scores})
    phq2_total = phq2_result["scores"]["total"]

    # If PHQ-2 positive or scores provided for PHQ-9, run full PHQ-9
    phq9_result = None
    if phq2_total >= 3 or params.get("phq9_scores"):
        phq9_scores = params.get("phq9_scores", {})
        # Fill Q1, Q2 from PHQ-2 if not in PHQ-9
        if "q1" not in phq9_scores:
            phq9_scores["q1"] = phq2_scores.get("q1", 0)
        if "q2" not in phq9_scores:
            phq9_scores["q2"] = phq2_scores.get("q2", 0)
        phq9_result = _run_phq9({
            "scores": phq9_scores,
            "patient_name": params.get("patient_name", "المريض"),
            "visual_acuity_context": params.get("visual_acuity"),
        })

    # GDS-15 for elderly
    gds15_result = None
    if age >= 65 and params.get("gds15_answers"):
        gds15_result = _run_gds15({
            "answers": params.get("gds15_answers", {}),
            "patient_age": age,
        })

    # Adjustment stage
    adjustment_result = None
    if params.get("adjustment_indicators") or params.get("months_since_diagnosis"):
        adjustment_result = _assess_adjustment_stage({
            "clinical_indicators": params.get("adjustment_indicators", {}),
            "months_since_diagnosis": params.get("months_since_diagnosis", 0),
        })

    # Determine overall risk level
    risk_level = _calculate_overall_psychological_risk(
        phq2_result, phq9_result, gds15_result, adjustment_result
    )

    # Summary recommendations
    summary_recommendations = _generate_summary_recommendations(
        risk_level, phq9_result, adjustment_result, age
    )

    return {
        "screening_type": "full_psychological",
        "patient_age": age,
        "overall_risk_level": risk_level,
        "phq2_result": phq2_result,
        "phq9_result": phq9_result,
        "gds15_result": gds15_result,
        "adjustment_stage_result": adjustment_result,
        "summary_recommendations": summary_recommendations,
        "urgent_action_needed": risk_level in ["high", "critical"],
        "timestamp": datetime.now().isoformat(),
    }


# --- Helper Functions ---

def _assess_vision_depression_risk(va_context: str, duration_months: Optional[int]) -> dict:
    """Assess vision-specific depression risk factors."""
    risk_factors = []
    risk_score = 0

    if va_context:
        # Parse VA to check severity
        from tools.arabic_reading_calculator import _parse_va_to_decimal
        decimal_va = _parse_va_to_decimal(va_context)
        if decimal_va is not None:
            if decimal_va < 0.1:
                risk_factors.append("فقدان بصري شديد (أقل من 6/60)")
                risk_score += 3
            elif decimal_va < 0.3:
                risk_factors.append("فقدان بصري متوسط")
                risk_score += 2

    if duration_months is not None:
        if duration_months < 3:
            risk_factors.append("فقدان بصري حديث (أقل من 3 أشهر)")
            risk_score += 2
        elif duration_months < 12:
            risk_factors.append("فقدان بصري خلال السنة الأولى")
            risk_score += 1

    if risk_score >= 4:
        risk_level = "مرتفع"
    elif risk_score >= 2:
        risk_level = "متوسط"
    else:
        risk_level = "منخفض"

    return {
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "risk_score": risk_score,
        "general_note": "خطر الاكتئاب مرتفع بشكل ملحوظ في ضعف البصر مقارنة بالسكان العاديين",
    }


def _generate_phq9_recommendations(
    score: int,
    severity: dict,
    suicidal_alert: bool,
    vision_risk: dict
) -> list:
    """Generate clinical recommendations based on PHQ-9 results."""
    recommendations = []

    if suicidal_alert:
        recommendations.append("🚨 URGENT: تقييم خطر الانتحار فوراً - لا تترك المريض")

    if severity:
        recommendations.append(severity.get("action", ""))

    if score >= 10:
        recommendations.append("إحالة للطب النفسي أو علم النفس الإكلينيكي")
        recommendations.append("النظر في العلاج النفسي (CBT مع ضعف البصر)")

    if score >= 5:
        recommendations.append("برنامج دعم نفسي ضمن فريق التأهيل البصري")
        recommendations.append("مجموعات دعم المرضى بضعف البصر")

    recommendations.append("إعادة تقييم PHQ-9 بعد 4-8 أسابيع من التدخل")

    if vision_risk["risk_level"] == "مرتفع":
        recommendations.append("تكثيف الدعم النفسي بسبب عوامل خطر خاصة بضعف البصر")

    return [r for r in recommendations if r]


def _generate_gds15_recommendations(score: int, severity: dict) -> list:
    """Generate recommendations for GDS-15 results."""
    recommendations = []

    if severity:
        recommendations.append(severity.get("action", ""))

    if score >= 9:
        recommendations.append("تقييم كامل من طبيب نفسي متخصص في كبار السن")

    recommendations.extend([
        "تقييم الشبكة الاجتماعية والعزلة",
        "فحص الأمراض المزمنة المصاحبة وعلاقتها بالاكتئاب",
        "مراجعة الأدوية لاحتمال التأثير على المزاج",
        "برامج نشاط اجتماعي مناسبة لكبار السن",
    ])

    return recommendations


def _calculate_overall_psychological_risk(
    phq2: dict, phq9: Optional[dict], gds15: Optional[dict], adjustment: Optional[dict]
) -> str:
    """Calculate overall psychological risk level."""
    risk_scores = []

    # PHQ-2
    phq2_total = phq2.get("scores", {}).get("total", 0)
    if phq2_total >= 4:
        risk_scores.append(4)
    elif phq2_total >= 3:
        risk_scores.append(3)
    elif phq2_total >= 1:
        risk_scores.append(1)
    else:
        risk_scores.append(0)

    # PHQ-9
    if phq9:
        phq9_total = phq9.get("scores", {}).get("total", 0)
        if phq9.get("safety_alert", {}).get("suicidal_ideation"):
            risk_scores.append(10)  # Critical
        elif phq9_total >= 20:
            risk_scores.append(5)
        elif phq9_total >= 15:
            risk_scores.append(4)
        elif phq9_total >= 10:
            risk_scores.append(3)
        elif phq9_total >= 5:
            risk_scores.append(2)

    # Adjustment
    if adjustment:
        if adjustment.get("stuck_in_grief") and adjustment.get("primary_adjustment_stage") == 4:
            risk_scores.append(3)

    max_risk = max(risk_scores) if risk_scores else 0

    if max_risk >= 10:
        return "critical"
    elif max_risk >= 4:
        return "high"
    elif max_risk >= 2:
        return "moderate"
    elif max_risk >= 1:
        return "low"
    else:
        return "minimal"


def _generate_summary_recommendations(
    risk_level: str,
    phq9: Optional[dict],
    adjustment: Optional[dict],
    age: int
) -> list:
    """Generate final summary recommendations."""
    recs = []

    if risk_level == "critical":
        recs.append("🚨 إحالة نفسية طارئة - لا يُترك المريض وحده")
        recs.append("التواصل مع الطب النفسي فوراً")
    elif risk_level == "high":
        recs.append("إحالة خلال أسبوع لمتخصص نفسي")
        recs.append("متابعة أسبوعية من الفريق")
    elif risk_level == "moderate":
        recs.append("دعم نفسي ضمن جلسات التأهيل")
        recs.append("إعادة تقييم بعد 4 أسابيع")
    else:
        recs.append("المراقبة الدورية كافية حالياً")

    if adjustment and adjustment.get("primary_adjustment_stage"):
        stage_name = adjustment.get("stage_name")
        recs.append(f"التعامل مع مرحلة: {stage_name} بالتدخلات المناسبة")

    recs.append("تفعيل دعم الأسرة في رحلة التأهيل")

    if age >= 65:
        recs.append("التحقق من أنشطة التواصل الاجتماعي لتجنب العزلة")

    return recs
