"""
Perceptual Learning Planner — مخطط جلسات التعلم الإدراكي
=======================================================
يولد بروتوكولات مخصصة لتدريب:
- Gabor patches (حساسية التباين)
- Lateral masking (التفاعلات المثبطة/المنشطة)
- Crowding reduction (تقليل الازدحام البصري)
- Motion perception (إدراك الحركة)

مبني على: Polat 2004, Levi 2009, Huang 2008
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# بارامترات التدريب الأساسية
# ═══════════════════════════════════════════════════════════════

TRAINING_PROTOCOLS = {
    "contrast_detection": {
        "name": "تدريب كشف التباين (Gabor Patches)",
        "name_en": "Contrast Detection Training",
        "description": "تدريب على كشف أنماط Gabor بتباين متناقص لتحسين حساسية التباين",
        "target_function": "حساسية التباين (Contrast Sensitivity)",
        "mechanism": "اللدونة العصبية في V1 — تحسين tuning curves لخلايا الكشف",
        "stimuli": {
            "type": "Gabor patches",
            "spatial_frequencies": [1, 2, 4, 6, 8, 12],  # cycles per degree
            "orientations": [0, 45, 90, 135],  # degrees
            "initial_contrast": 0.5,
            "staircase": "3-down-1-up adaptive (79.4% threshold)",
            "display_duration_ms": 200,
            "inter_trial_interval_ms": 1000
        },
        "protocol": {
            "total_sessions": 40,
            "session_duration_min": 30,
            "frequency": "يومياً أو 5×/أسبوع",
            "total_weeks": "6-8 أسابيع",
            "trials_per_session": 200,
            "reassessment_interval": 10
        },
        "expected_outcomes": {
            "cs_improvement": "1-2 سطر في Pelli-Robson",
            "va_improvement": "0.5-1 سطر في بعض الحالات",
            "timeline": "تحسن ملحوظ بعد 20-30 جلسة"
        },
        "evidence": {
            "level": "1b",
            "refs": ["Polat 2004 RCT", "Levi 2009"],
            "recommendation": "A"
        },
        "suitable_conditions": ["AMD", "amblyopia", "myopia", "post_refractive", "general_low_vision"],
        "va_range": (0.05, 0.5)
    },
    "lateral_masking": {
        "name": "تدريب التقنيع الجانبي (Lateral Masking)",
        "name_en": "Lateral Masking Training",
        "description": "تدريب على كشف هدف مركزي محاط بمثيرات جانبية (flankers) لتحسين التفاعلات في V1",
        "target_function": "حساسية التباين + القراءة في الازدحام",
        "mechanism": "تعديل lateral interactions في V1 — تقوية facilitation وتقليل suppression",
        "stimuli": {
            "type": "Gabor target + collinear flankers",
            "target_sf": 6,  # cpd
            "flanker_distances": [2, 3, 4, 6, 8],  # wavelengths
            "flanker_contrast": 0.4,
            "staircase": "2-AFC adaptive",
            "display_duration_ms": 200,
            "inter_trial_interval_ms": 800
        },
        "protocol": {
            "total_sessions": 30,
            "session_duration_min": 30,
            "frequency": "يومياً أو 5×/أسبوع",
            "total_weeks": "4-6 أسابيع",
            "trials_per_session": 160,
            "reassessment_interval": 10
        },
        "expected_outcomes": {
            "cs_improvement": "تحسن CS بمسافات flanker القريبة",
            "va_improvement": "1-2 سطر (خاصة في amblyopia)",
            "reading": "تحسن سرعة القراءة في النصوص المزدحمة"
        },
        "evidence": {
            "level": "1b",
            "refs": ["Huang 2008", "Polat 2009"],
            "recommendation": "A"
        },
        "suitable_conditions": ["amblyopia", "AMD", "general_low_vision"],
        "va_range": (0.05, 0.5)
    },
    "crowding_reduction": {
        "name": "تدريب تقليل الازدحام البصري (Crowding Reduction)",
        "name_en": "Crowding Reduction Training",
        "description": "تدريب على التعرف على حروف/أهداف محاطة بمشتتات قريبة",
        "target_function": "تقليل crowding zone + تحسين القراءة مع scotoma",
        "mechanism": "تقليل crowding zone في المحيط — مفيد جداً لمستخدمي EVT",
        "stimuli": {
            "type": "Tumbling E أو حروف + flanker letters",
            "target_sizes": "scaled to VA",
            "flanker_distances": "0.5x to 3x target size",
            "staircase": "Adaptive — تقليل المسافة تدريجياً",
            "display_duration_ms": 500,
            "inter_trial_interval_ms": 1000
        },
        "protocol": {
            "total_sessions": 30,
            "session_duration_min": 25,
            "frequency": "5×/أسبوع",
            "total_weeks": "6 أسابيع",
            "trials_per_session": 150,
            "reassessment_interval": 10
        },
        "expected_outcomes": {
            "crowding_zone": "تقليل 20-40% في critical spacing",
            "reading": "تحسن سرعة القراءة باستخدام PRL",
            "va_improvement": "تحسن crowded VA أكثر من uncrowded"
        },
        "evidence": {
            "level": "2b",
            "refs": ["Chung 2007", "Huckauf 2006"],
            "recommendation": "B"
        },
        "suitable_conditions": ["AMD", "Stargardt", "any_central_scotoma"],
        "va_range": (0.02, 0.3)
    },
    "motion_perception": {
        "name": "تدريب إدراك الحركة (Motion Perception)",
        "name_en": "Motion Perception Training",
        "description": "تدريب على اكتشاف اتجاه الحركة باستخدام random dot kinematograms",
        "target_function": "إدراك الحركة في المحيط — مهم للتنقل والأمان",
        "mechanism": "تحسين معالجة MT/V5 لإشارات الحركة",
        "stimuli": {
            "type": "Random Dot Kinematograms (RDK)",
            "coherence_levels": "5%-100% (adaptive)",
            "dot_speed": "5 deg/s",
            "dot_density": "5 dots/deg²",
            "staircase": "2-AFC direction discrimination",
            "display_duration_ms": 400,
            "inter_trial_interval_ms": 1000
        },
        "protocol": {
            "total_sessions": 20,
            "session_duration_min": 25,
            "frequency": "5×/أسبوع",
            "total_weeks": "4 أسابيع",
            "trials_per_session": 120,
            "reassessment_interval": 5
        },
        "expected_outcomes": {
            "motion_threshold": "تقليل coherence threshold 30-50%",
            "navigation": "تحسن في التنقل واكتشاف العوائق المتحركة",
            "driving": "قد يحسن أداء القيادة المحاكاة"
        },
        "evidence": {
            "level": "2b",
            "refs": ["Ball 2002", "Richards 2006"],
            "recommendation": "B"
        },
        "suitable_conditions": ["glaucoma", "RP", "peripheral_loss", "hemianopia"],
        "va_range": (0.05, 0.8)
    },
}

# مستويات الصعوبة التدريجية
DIFFICULTY_LEVELS = {
    "beginner": {
        "name": "مبتدئ",
        "contrast_multiplier": 1.5,
        "trials_multiplier": 0.6,
        "session_duration_multiplier": 0.7,
        "rest_breaks": "كل 5 دقائق"
    },
    "intermediate": {
        "name": "متوسط",
        "contrast_multiplier": 1.0,
        "trials_multiplier": 1.0,
        "session_duration_multiplier": 1.0,
        "rest_breaks": "كل 10 دقائق"
    },
    "advanced": {
        "name": "متقدم",
        "contrast_multiplier": 0.7,
        "trials_multiplier": 1.3,
        "session_duration_multiplier": 1.2,
        "rest_breaks": "كل 15 دقيقة"
    },
}


# ═══════════════════════════════════════════════════════════════
# توليد البروتوكول المخصص
# ═══════════════════════════════════════════════════════════════

def _parse_va(va_str: str) -> float:
    if not va_str:
        return 0.1
    va = str(va_str).strip().upper()
    special = {"NLP": 0.0, "LP": 0.005, "HM": 0.005, "CF": 0.01}
    if va in special:
        return special[va]
    if "/" in va:
        parts = va.split("/")
        try:
            return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            return 0.1
    try:
        val = float(va)
        return val if val <= 2.0 else 0.1
    except ValueError:
        return 0.1


def _determine_difficulty(va: float, age: int, sessions_completed: int = 0) -> str:
    """تحديد مستوى الصعوبة بناءً على VA والعمر"""
    if sessions_completed > 20:
        return "advanced"
    if va < 0.1 or age > 70:
        return "beginner"
    if va < 0.3 or age > 55:
        return "intermediate"
    return "intermediate"


def _generate_protocol(params: dict) -> dict:
    """توليد بروتوكول تعلم إدراكي مخصص"""
    task_type = params.get("task_type", "contrast_detection")
    protocol_template = TRAINING_PROTOCOLS.get(task_type)

    if not protocol_template:
        return {
            "error": f"نوع مهمة غير معروف: {task_type}",
            "available_types": list(TRAINING_PROTOCOLS.keys())
        }

    va = _parse_va(params.get("visual_acuity", ""))
    age = int(params.get("patient_age", 50))
    diagnosis = params.get("diagnosis", "")
    sessions_done = int(params.get("sessions_completed", 0))

    # Check VA range
    va_min, va_max = protocol_template["va_range"]
    va_warning = None
    if va < va_min:
        va_warning = f"⚠️ حدة الإبصار ({va}) أقل من الحد الأدنى ({va_min}) — قد تكون النتائج محدودة"
    elif va > va_max:
        va_warning = f"حدة الإبصار ({va}) أعلى من النطاق — قد لا يحتاج المريض هذا التدريب"

    # Determine difficulty
    difficulty = _determine_difficulty(va, age, sessions_done)
    diff_params = DIFFICULTY_LEVELS[difficulty]

    # Customize protocol
    base_protocol = protocol_template["protocol"]
    adjusted_trials = int(base_protocol["trials_per_session"] * diff_params["trials_multiplier"])
    adjusted_duration = int(base_protocol["session_duration_min"] * diff_params["session_duration_multiplier"])

    # Generate session plan
    remaining_sessions = max(0, base_protocol["total_sessions"] - sessions_done)
    next_reassessment = base_protocol["reassessment_interval"] - (sessions_done % base_protocol["reassessment_interval"])

    return {
        "protocol_name": protocol_template["name"],
        "protocol_name_en": protocol_template["name_en"],
        "description": protocol_template["description"],
        "target_function": protocol_template["target_function"],
        "mechanism": protocol_template["mechanism"],
        "patient_profile": {
            "visual_acuity": va,
            "age": age,
            "diagnosis": diagnosis,
            "sessions_completed": sessions_done
        },
        "difficulty_level": {
            "level": difficulty,
            "name": diff_params["name"],
            "rest_breaks": diff_params["rest_breaks"]
        },
        "session_parameters": {
            "stimuli": protocol_template["stimuli"],
            "trials_per_session": adjusted_trials,
            "session_duration_min": adjusted_duration,
            "frequency": base_protocol["frequency"],
            "initial_contrast_multiplier": diff_params["contrast_multiplier"]
        },
        "schedule": {
            "total_sessions": base_protocol["total_sessions"],
            "sessions_completed": sessions_done,
            "sessions_remaining": remaining_sessions,
            "total_weeks": base_protocol["total_weeks"],
            "next_reassessment_in": f"{next_reassessment} جلسات",
            "reassessment_measures": ["VA (LogMAR)", "CS (Pelli-Robson)", "task-specific threshold"]
        },
        "expected_outcomes": protocol_template["expected_outcomes"],
        "evidence": protocol_template["evidence"],
        "va_warning": va_warning,
        "clinical_notes": [
            "التحسن خاص بالمهمة المدربة — النقل محدود",
            "الدافعية والمواظبة ضرورية — قد يملّ المريض",
            "قياس CS + VA قبل البدء وكل 10 جلسات",
            f"استراحة {diff_params['rest_breaks']} لتجنب الإرهاق البصري"
        ],
        "timestamp": datetime.now().isoformat()
    }


def _list_protocols() -> dict:
    """قائمة بجميع بروتوكولات التعلم الإدراكي"""
    protocols = []
    for tid, proto in TRAINING_PROTOCOLS.items():
        protocols.append({
            "id": tid,
            "name": proto["name"],
            "name_en": proto["name_en"],
            "target": proto["target_function"],
            "sessions": proto["protocol"]["total_sessions"],
            "duration_weeks": proto["protocol"]["total_weeks"],
            "evidence_level": proto["evidence"]["level"],
            "suitable_for": proto["suitable_conditions"]
        })
    return {
        "total_protocols": len(protocols),
        "protocols": protocols
    }


def _track_progress(params: dict) -> dict:
    """تتبع تقدم التدريب"""
    task_type = params.get("task_type", "contrast_detection")
    sessions_done = int(params.get("sessions_completed", 0))
    baseline_cs = float(params.get("baseline_cs", 0))
    current_cs = float(params.get("current_cs", 0))
    baseline_va = _parse_va(params.get("baseline_va", ""))
    current_va = _parse_va(params.get("current_va", ""))

    protocol_template = TRAINING_PROTOCOLS.get(task_type, {})
    total = protocol_template.get("protocol", {}).get("total_sessions", 40)

    cs_change = current_cs - baseline_cs if baseline_cs and current_cs else None
    va_change = current_va - baseline_va if baseline_va and current_va else None

    progress_pct = round((sessions_done / total) * 100, 1) if total else 0

    status = "قيد التدريب"
    if progress_pct >= 100:
        status = "مكتمل"
    elif progress_pct >= 75:
        status = "مرحلة متقدمة"
    elif progress_pct >= 50:
        status = "منتصف البرنامج"
    elif progress_pct >= 25:
        status = "مرحلة مبكرة"

    return {
        "task_type": task_type,
        "progress": {
            "sessions_completed": sessions_done,
            "total_sessions": total,
            "percentage": progress_pct,
            "status": status
        },
        "outcomes": {
            "cs_change": cs_change,
            "cs_interpretation": "تحسن" if cs_change and cs_change > 0 else "لا تحسن ملحوظ" if cs_change else "لم يُقاس",
            "va_change": va_change,
            "va_interpretation": "تحسن" if va_change and va_change > 0 else "لا تحسن" if va_change else "لم يُقاس"
        },
        "recommendation": _get_progress_recommendation(progress_pct, cs_change)
    }


def _get_progress_recommendation(progress_pct: float, cs_change: float = None) -> str:
    if progress_pct < 25:
        return "استمر بالتدريب — النتائج تظهر عادةً بعد 20-30 جلسة"
    if progress_pct < 50:
        if cs_change and cs_change > 0:
            return "تحسن مبكر واعد — استمر بنفس الوتيرة"
        return "لا تحسن بعد — طبيعي في هذه المرحلة، استمر"
    if progress_pct < 75:
        if cs_change and cs_change > 0.1:
            return "تحسن جيد — يمكن زيادة الصعوبة"
        return "تقدم بطيء — قيّم الالتزام والدافعية"
    if cs_change and cs_change > 0:
        return "تحسن ملحوظ — يمكن الانتقال لمهمة تدريب مختلفة للتعميم"
    return "اكتمل البرنامج — قيّم الفائدة الوظيفية الشاملة"


# ═══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def plan_perceptual_learning(params: dict) -> dict:
    """
    مخطط جلسات التعلم الإدراكي

    Args:
        params: dict containing:
            - action: "generate" | "list" | "track_progress"
            - task_type: "contrast_detection" | "lateral_masking" | "crowding_reduction" | "motion_perception"
            - visual_acuity: حدة الإبصار
            - patient_age: العمر
            - diagnosis: التشخيص
            - sessions_completed: عدد الجلسات المكتملة
            - baseline_cs/current_cs: حساسية التباين
            - baseline_va/current_va: حدة الإبصار

    Returns:
        dict with protocol/list/progress
    """
    action = params.get("action", "generate")

    try:
        if action == "generate":
            return _generate_protocol(params)
        elif action == "list":
            return _list_protocols()
        elif action == "track_progress":
            return _track_progress(params)
        else:
            return {
                "error": f"إجراء غير معروف: {action}",
                "available_actions": ["generate", "list", "track_progress"]
            }
    except Exception as e:
        return {"error": f"خطأ في مخطط التعلم الإدراكي: {str(e)}"}
