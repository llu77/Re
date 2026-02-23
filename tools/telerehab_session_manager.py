"""
Telerehab Session Manager — إدارة جلسات التأهيل عن بعد
======================================================
تخطيط وإدارة جلسات التأهيل البصري عبر الفيديو:
- تقييم الجاهزية التقنية
- تخطيط الجلسات
- بروتوكولات المتابعة
- تقييم النتائج

مبني على: Bittner 2024 RCT (non-inferior to in-office LVR)
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# أنواع الجلسات المتاحة
# ═══════════════════════════════════════════════════════════════

SESSION_TYPES = {
    "initial_assessment": {
        "name": "التقييم الأولي عن بعد",
        "name_en": "Remote Initial Assessment",
        "duration_min": 60,
        "components": [
            {"step": "التحقق التقني", "duration": 10, "description": "فحص الاتصال + الكاميرا + الإضاءة + الصوت"},
            {"step": "التعارف والتاريخ", "duration": 15, "description": "التاريخ البصري + الأهداف + الحالة الصحية"},
            {"step": "تقييم VA عن بعد", "duration": 10, "description": "استخدام Peek Acuity أو لوحة منزلية مُرسلة مسبقاً"},
            {"step": "تقييم وظيفي", "duration": 15, "description": "مهام القراءة + الكتابة + التعرف + التنقل المنزلي"},
            {"step": "وضع الأهداف", "duration": 10, "description": "SMART Goals بالتشاور مع المريض"}
        ],
        "prerequisites": ["video_capable_device", "stable_internet", "adequate_lighting"],
        "materials_to_send": [
            "لوحة حدة إبصار مطبوعة (Tumbling E — معيارية المقاس)",
            "بطاقة قراءة عربية (أحجام 0.4M - 2.0M)",
            "استبيان VFQ-25 مطبوع",
            "كتيب تعليمات التحضير للجلسة"
        ]
    },
    "device_training": {
        "name": "تدريب على الأجهزة المساعدة",
        "name_en": "Assistive Device Training Session",
        "duration_min": 45,
        "components": [
            {"step": "مراجعة الجلسة السابقة", "duration": 5, "description": "أسئلة + تحديات + تقدم"},
            {"step": "عرض وشرح", "duration": 10, "description": "المختص يوضح استخدام الجهاز أمام الكاميرا"},
            {"step": "تطبيق عملي", "duration": 20, "description": "المريض يمارس + المختص يوجه عبر الفيديو"},
            {"step": "تمارين منزلية", "duration": 5, "description": "تحديد تمارين يومية محددة"},
            {"step": "جدولة المتابعة", "duration": 5, "description": "تحديد موعد الجلسة التالية"}
        ],
        "prerequisites": ["device_received", "caregiver_if_needed"],
        "materials_to_send": ["الجهاز المساعد (مكبر/نظارة/CCTV)", "دليل الاستخدام المبسط"]
    },
    "evt_remote": {
        "name": "تدريب EVT عن بعد",
        "name_en": "Remote Eccentric Viewing Training",
        "duration_min": 45,
        "components": [
            {"step": "تحقق من الوضعية", "duration": 5, "description": "إضاءة + مسافة + وضع الجسم"},
            {"step": "تمارين تثبيت PRL", "duration": 15, "description": "أهداف على الشاشة المشتركة + توجيه صوتي"},
            {"step": "تدريب قراءة", "duration": 15, "description": "نصوص متدرجة الحجم + توقيت"},
            {"step": "واجب منزلي", "duration": 5, "description": "تمارين يومية 15 دقيقة + سجل"},
            {"step": "تقييم مختصر", "duration": 5, "description": "قياس سرعة القراءة المقارنة"}
        ],
        "prerequisites": ["prl_identified", "initial_evt_training_in_clinic"],
        "materials_to_send": ["بطاقات تدريب EVT", "نصوص تدريب متدرجة"]
    },
    "scanning_remote": {
        "name": "تدريب Scanning عن بعد",
        "name_en": "Remote Visual Scanning Training",
        "duration_min": 45,
        "components": [
            {"step": "مراجعة التقدم", "duration": 5, "description": "نتائج NEC أو تمارين منزلية"},
            {"step": "تمارين مسح", "duration": 20, "description": "عرض أهداف على شاشة مشتركة + توقيت"},
            {"step": "مهام وظيفية", "duration": 10, "description": "قراءة + بحث بصري + وصف مشهد"},
            {"step": "تخطيط", "duration": 5, "description": "تمارين الأسبوع القادم"},
            {"step": "تقييم", "duration": 5, "description": "مقارنة أوقات البحث مع الأسبوع السابق"}
        ],
        "prerequisites": ["stable_hemianopia", "computer_access"],
        "materials_to_send": ["رابط NeuroEyeCoach (إذا متوفر)", "تمارين ورقية للمسح"]
    },
    "psychological_support": {
        "name": "دعم نفسي وتكيف",
        "name_en": "Psychological Support & Adjustment Session",
        "duration_min": 50,
        "components": [
            {"step": "تسجيل وصول", "duration": 5, "description": "كيف كان الأسبوع؟ أي تحديات؟"},
            {"step": "PHQ-2 سريع", "duration": 5, "description": "فحص اكتئاب سريع"},
            {"step": "مناقشة التكيف", "duration": 20, "description": "مرحلة التكيف الحالية + استراتيجيات التأقلم"},
            {"step": "حل المشكلات", "duration": 10, "description": "تحديات محددة + حلول عملية"},
            {"step": "خطة الأسبوع", "duration": 10, "description": "أهداف صغيرة قابلة للتحقيق"}
        ],
        "prerequisites": ["private_environment"],
        "materials_to_send": ["دليل التكيف مع فقدان البصر", "معلومات مجموعات الدعم"]
    },
    "follow_up": {
        "name": "متابعة دورية",
        "name_en": "Follow-up Review Session",
        "duration_min": 30,
        "components": [
            {"step": "مراجعة الأهداف", "duration": 10, "description": "تقييم تقدم SMART Goals"},
            {"step": "قياسات", "duration": 10, "description": "VA + سرعة قراءة + VFQ-25 مختصر"},
            {"step": "تعديل الخطة", "duration": 10, "description": "تعديل التدخلات بناءً على التقدم"}
        ],
        "prerequisites": ["previous_sessions_completed"],
        "materials_to_send": ["استبيان متابعة VFQ-25"]
    },
}


# ═══════════════════════════════════════════════════════════════
# متطلبات تقنية
# ═══════════════════════════════════════════════════════════════

TECH_REQUIREMENTS = {
    "minimum": {
        "internet": "5 Mbps download / 2 Mbps upload",
        "device": "Tablet أو Computer مع كاميرا",
        "platform": "Zoom, Teams, أو أي منصة HIPAA-compliant",
        "camera": "720p على الأقل",
        "audio": "ميكروفون مدمج أو خارجي",
        "lighting": "إضاءة أمامية كافية (300+ لوكس)"
    },
    "recommended": {
        "internet": "10+ Mbps",
        "device": "iPad أو Computer بشاشة كبيرة",
        "camera": "1080p + زاوية واسعة",
        "audio": "سماعات خارجية (أوضح للمريض ضعيف السمع)",
        "screen_sharing": "قدرة مشاركة الشاشة (للتمارين المحوسبة)"
    },
}


# ═══════════════════════════════════════════════════════════════
# منطق إدارة الجلسات
# ═══════════════════════════════════════════════════════════════

def _plan_session(params: dict) -> dict:
    """تخطيط جلسة تأهيل عن بعد"""
    session_type = params.get("session_type", "initial_assessment")
    template = SESSION_TYPES.get(session_type)

    if not template:
        return {
            "error": f"نوع جلسة غير معروف: {session_type}",
            "available_types": list(SESSION_TYPES.keys())
        }

    tech_literacy = params.get("patient_tech_literacy", "moderate")
    caregiver_available = params.get("caregiver_available", False)
    patient_age = int(params.get("patient_age", 65))

    # Adjust duration based on tech literacy
    duration_adjust = 1.0
    if tech_literacy == "low":
        duration_adjust = 1.3
    elif tech_literacy == "high":
        duration_adjust = 0.9

    adjusted_duration = int(template["duration_min"] * duration_adjust)

    # Pre-session checklist
    pre_session = {
        "technical_setup": [
            "اختبار الاتصال بالإنترنت (speedtest.net)",
            "تجربة الكاميرا والميكروفون",
            "إعداد الإضاءة: مصباح أمامي + تجنب الظل",
            "تحضير بيئة هادئة خالية من المشتتات",
            f"تحميل تطبيق المحادثة المرئية وتسجيل الدخول مسبقاً"
        ],
        "materials": template.get("materials_to_send", []),
        "patient_prep": [
            "ارتداء النظارة المعتادة",
            "تحضير الأجهزة المساعدة (إن وجدت)",
            "وجود ورقة وقلم",
            "شرب ماء + راحة قبل الجلسة"
        ]
    }

    if caregiver_available:
        pre_session["caregiver_role"] = [
            "المساعدة في الإعداد التقني",
            "توجيه الكاميرا إذا لزم الأمر",
            "المساعدة في تطبيق التمارين",
            "تدوين الملاحظات والتعليمات"
        ]

    if tech_literacy == "low":
        pre_session["technical_setup"].insert(0, "⚠️ جلسة تدريب تقنية أولية 15 دقيقة قبل الجلسة الأولى")

    return {
        "session_plan": {
            "type": session_type,
            "name": template["name"],
            "name_en": template["name_en"],
            "duration_minutes": adjusted_duration,
            "components": template["components"],
            "prerequisites": template["prerequisites"]
        },
        "patient_profile": {
            "tech_literacy": tech_literacy,
            "age": patient_age,
            "caregiver_available": caregiver_available
        },
        "pre_session_checklist": pre_session,
        "tech_requirements": TECH_REQUIREMENTS,
        "tips": _get_session_tips(session_type, tech_literacy, patient_age),
        "timestamp": datetime.now().isoformat()
    }


def _get_session_tips(session_type: str, tech_literacy: str, age: int) -> list:
    """نصائح للمختص حسب نوع الجلسة"""
    tips = [
        "تحدث بوضوح وببطء — الصوت قد يتأخر قليلاً عبر الفيديو",
        "اطلب من المريض تأكيد الفهم بعد كل تعليمة",
        "استخدم مشاركة الشاشة لعرض التمارين والمواد"
    ]
    if tech_literacy == "low":
        tips.extend([
            "كن صبوراً مع المشاكل التقنية — قد تأخذ وقتاً",
            "استخدم لغة بسيطة لوصف الخطوات التقنية",
            "أرسل فيديو تعليمي قصير قبل الجلسة"
        ])
    if age > 70:
        tips.extend([
            "زِد حجم الخط عند مشاركة الشاشة",
            "خذ استراحات أكثر تكراراً",
            "تأكد من سماع المريض بوضوح (قد يحتاج سماعة)"
        ])
    if session_type == "evt_remote":
        tips.append("تأكد من أن المريض يستخدم PRL المحدد سابقاً — لا تغيره عن بعد")
    if session_type == "psychological_support":
        tips.append("انتبه لعلامات الضيق الشديد — لديك خطة إحالة طوارئ جاهزة")

    return tips


def _check_readiness(params: dict) -> dict:
    """فحص جاهزية المريض للتأهيل عن بعد"""
    has_internet = params.get("has_internet", True)
    has_device = params.get("has_video_device", True)
    tech_literacy = params.get("patient_tech_literacy", "moderate")
    caregiver = params.get("caregiver_available", False)
    hearing_status = params.get("hearing_status", "normal")

    score = 0
    barriers = []
    facilitators = []

    if has_internet:
        score += 3
        facilitators.append("اتصال إنترنت متوفر")
    else:
        barriers.append("⚠️ لا يوجد إنترنت — عائق رئيسي")

    if has_device:
        score += 3
        facilitators.append("جهاز بكاميرا متوفر")
    else:
        barriers.append("⚠️ لا يوجد جهاز بكاميرا — عائق رئيسي")

    if tech_literacy in ["moderate", "high"]:
        score += 2
        facilitators.append("محو أمية تقنية كافٍ")
    elif caregiver:
        score += 1
        facilitators.append("مرافق متوفر للمساعدة التقنية")
    else:
        barriers.append("محو أمية تقنية منخفض بدون مرافق — يحتاج تدريب إضافي")

    if hearing_status == "normal":
        score += 1
        facilitators.append("سمع طبيعي")
    elif hearing_status in ["mild_loss", "aided"]:
        score += 0.5
        facilitators.append("سمع مساعد — تأكد من وضوح الصوت")
    else:
        barriers.append("ضعف سمع — قد يحتاج ترجمة نصية مباشرة")

    if caregiver:
        score += 1
        facilitators.append("مرافق/داعم متوفر")

    ready = score >= 6
    readiness = "جاهز" if ready else "يحتاج تحضير" if score >= 4 else "غير مناسب حالياً"

    recommendations = []
    if not has_internet:
        recommendations.append("استكشاف إمكانية توفير إنترنت (SIM بيانات مؤقت)")
    if not has_device:
        recommendations.append("توفير جهاز tablet (برنامج إعارة أجهزة إن وجد)")
    if tech_literacy == "low" and not caregiver:
        recommendations.append("جلسة تدريب تقنية أولية + تجنيد مرافق")
    if not recommendations:
        recommendations.append("المريض جاهز — يمكن البدء بالجلسة الأولى")

    return {
        "readiness": {
            "score": score,
            "max_score": 10,
            "status": readiness,
            "ready_for_telerehab": ready
        },
        "barriers": barriers,
        "facilitators": facilitators,
        "recommendations": recommendations,
        "evidence": "Bittner 2024 RCT: التأهيل عن بعد مكافئ للحضوري في النتائج"
    }


def _generate_treatment_plan(params: dict) -> dict:
    """توليد خطة تأهيل عن بعد كاملة"""
    sessions_count = int(params.get("total_sessions", 8))
    primary_goal = params.get("primary_goal", "reading")
    diagnosis = params.get("diagnosis", "AMD")

    # Build session schedule
    schedule = []

    # Session 1: Always initial assessment
    schedule.append({
        "session": 1,
        "type": "initial_assessment",
        "focus": "تقييم شامل + وضع الأهداف",
        "week": 1
    })

    # Sessions 2-N-1: Training
    training_sessions = sessions_count - 2  # minus assessment and final follow-up
    week = 2

    if primary_goal == "reading" and diagnosis in ["AMD", "Stargardt"]:
        for i in range(training_sessions):
            if i < training_sessions // 2:
                schedule.append({
                    "session": i + 2,
                    "type": "evt_remote",
                    "focus": "تدريب EVT + تمارين قراءة",
                    "week": week
                })
            else:
                schedule.append({
                    "session": i + 2,
                    "type": "device_training",
                    "focus": "تدريب على المكبر/النظارة الذكية",
                    "week": week
                })
            week += 1
    elif primary_goal == "reading" and diagnosis in ["stroke", "TBI"]:
        for i in range(training_sessions):
            schedule.append({
                "session": i + 2,
                "type": "scanning_remote",
                "focus": "تدريب scanning + قراءة",
                "week": week
            })
            week += 1
    else:
        for i in range(training_sessions):
            schedule.append({
                "session": i + 2,
                "type": "device_training",
                "focus": "تدريب أجهزة + استراتيجيات يومية",
                "week": week
            })
            week += 1

    # Add psychological support (mid-way)
    if sessions_count >= 6:
        mid = sessions_count // 2
        schedule.insert(mid, {
            "session": "إضافي",
            "type": "psychological_support",
            "focus": "دعم نفسي + تقييم التكيف",
            "week": mid + 1
        })

    # Final session: Follow-up
    schedule.append({
        "session": sessions_count,
        "type": "follow_up",
        "focus": "تقييم نهائي + خطة متابعة طويلة المدى",
        "week": week
    })

    return {
        "treatment_plan": {
            "total_sessions": sessions_count,
            "total_weeks": week,
            "primary_goal": primary_goal,
            "diagnosis": diagnosis,
            "schedule": schedule
        },
        "outcome_measures": {
            "baseline": ["VA (LogMAR)", "سرعة القراءة (wpm)", "VFQ-25", "PHQ-2"],
            "mid_point": ["VA", "سرعة القراءة", "رضا المريض"],
            "final": ["VA", "سرعة القراءة", "VFQ-25", "PHQ-2", "رضا", "GAS"]
        },
        "success_criteria": [
            "تحسن VA بـ ≥0.1 LogMAR أو",
            "تحسن سرعة القراءة ≥30% أو",
            "تحسن VFQ-25 ≥5 نقاط أو",
            "تحقيق ≥80% من SMART Goals"
        ],
        "evidence": "Bittner 2024 RCT: نتائج مكافئة للتأهيل الحضوري",
        "timestamp": datetime.now().isoformat()
    }


def _list_session_types() -> dict:
    """قائمة بأنواع الجلسات المتاحة"""
    types = []
    for sid, session in SESSION_TYPES.items():
        types.append({
            "id": sid,
            "name": session["name"],
            "name_en": session["name_en"],
            "duration": session["duration_min"],
            "components_count": len(session["components"]),
            "prerequisites": session.get("prerequisites", [])
        })
    return {
        "total_types": len(types),
        "session_types": types,
        "tech_requirements": TECH_REQUIREMENTS
    }


# ═══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def manage_telerehab_session(params: dict) -> dict:
    """
    إدارة جلسات التأهيل عن بعد

    Args:
        params: dict containing:
            - action: "plan_session" | "check_readiness" | "treatment_plan" | "list_types"
            - session_type: نوع الجلسة
            - patient_tech_literacy: "low" | "moderate" | "high"
            - patient_age: العمر
            - caregiver_available: bool
            - has_internet / has_video_device: bool
            - total_sessions: عدد الجلسات الكلي
            - primary_goal: الهدف الأساسي
            - diagnosis: التشخيص

    Returns:
        dict with session plan/readiness/treatment plan
    """
    action = params.get("action", "plan_session")

    try:
        if action == "plan_session":
            return _plan_session(params)
        elif action == "check_readiness":
            return _check_readiness(params)
        elif action == "treatment_plan":
            return _generate_treatment_plan(params)
        elif action == "list_types":
            return _list_session_types()
        else:
            return {
                "error": f"إجراء غير معروف: {action}",
                "available_actions": ["plan_session", "check_readiness", "treatment_plan", "list_types"]
            }
    except Exception as e:
        return {"error": f"خطأ في إدارة الجلسات: {str(e)}"}
