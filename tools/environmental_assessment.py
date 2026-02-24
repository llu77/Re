"""
Environmental Assessment — تقييم البيئة المنزلية/العمل
=====================================================
تقييم شامل مع توصيات لـ:
- الإضاءة والتباين
- السلامة والوقاية من السقوط
- التعديلات البيئية
- التقنيات المساعدة

مبني على: Campbell 2005 RCT, La Grow 2006, Otago Programme
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# معايير التقييم البيئي
# ═══════════════════════════════════════════════════════════════

LIGHTING_STANDARDS = {
    "living_room": {"min_lux": 300, "recommended_lux": 500, "label": "غرفة المعيشة"},
    "reading_area": {"min_lux": 500, "recommended_lux": 1000, "label": "منطقة القراءة"},
    "kitchen": {"min_lux": 500, "recommended_lux": 750, "label": "المطبخ"},
    "bathroom": {"min_lux": 300, "recommended_lux": 500, "label": "الحمام"},
    "bedroom": {"min_lux": 200, "recommended_lux": 300, "label": "غرفة النوم"},
    "stairs": {"min_lux": 300, "recommended_lux": 500, "label": "السلالم"},
    "hallway": {"min_lux": 200, "recommended_lux": 300, "label": "الممرات"},
    "entrance": {"min_lux": 300, "recommended_lux": 500, "label": "المدخل"},
}

ROOM_HAZARDS = {
    "living_room": [
        {"hazard": "سجاد مفكك / حواف مرتفعة", "risk_level": "high", "fix": "تثبيت أو إزالة السجاد"},
        {"hazard": "أسلاك وكابلات على الأرض", "risk_level": "high", "fix": "تنظيم وتثبيت على الجدار"},
        {"hazard": "أثاث بزوايا حادة", "risk_level": "medium", "fix": "واقيات زوايا سيليكون"},
        {"hazard": "طاولات زجاجية شفافة", "risk_level": "medium", "fix": "ملصقات تباين على الحواف"},
        {"hazard": "إضاءة غير كافية", "risk_level": "medium", "fix": "إضافة مصباح أرضي 300+ لوكس"},
    ],
    "kitchen": [
        {"hazard": "أرضية زلقة عند البلل", "risk_level": "high", "fix": "سجادة مانعة للانزلاق"},
        {"hazard": "أدوات حادة بدون تمييز", "risk_level": "medium", "fix": "تنظيم + ملصقات ملونة"},
        {"hazard": "موقد بدون علامات تباين", "risk_level": "high", "fix": "ملصقات حرارية + علامات بارزة على المقابض"},
        {"hazard": "أدوية/مواد تنظيف متشابهة", "risk_level": "high", "fix": "فصل + ملصقات كبيرة ملونة"},
    ],
    "bathroom": [
        {"hazard": "أرضية زلقة", "risk_level": "high", "fix": "سجادة مانعة للانزلاق في الحوض والأرضية"},
        {"hazard": "لا مقابض", "risk_level": "high", "fix": "تركيب مقابض ثابتة بجانب المرحاض والحوض"},
        {"hazard": "تباين ضعيف (كل شيء أبيض)", "risk_level": "medium", "fix": "إضافة مناشف ملونة + غطاء مرحاض ملون"},
        {"hazard": "لا كرسي استحمام", "risk_level": "medium", "fix": "كرسي استحمام + رأس دش يدوي"},
    ],
    "bedroom": [
        {"hazard": "عتبة باب غير مرئية", "risk_level": "medium", "fix": "شريط تباين لاصق على العتبة"},
        {"hazard": "طريق من السرير للحمام في الظلام", "risk_level": "high", "fix": "إضاءة ليلية تلقائية (motion sensor)"},
        {"hazard": "أشياء على الأرض بجانب السرير", "risk_level": "medium", "fix": "تنظيم + طاولة جانبية"},
    ],
    "stairs": [
        {"hazard": "حواف درج غير مميزة", "risk_level": "high", "fix": "شريط تباين (أصفر/أبيض) على كل حافة"},
        {"hazard": "لا درابزين أو درابزين واحد", "risk_level": "high", "fix": "تركيب درابزين على الجانبين"},
        {"hazard": "إضاءة غير موحدة", "risk_level": "high", "fix": "إضاءة أعلى وأسفل السلم + مفتاح ثنائي"},
        {"hazard": "أشياء على الدرج", "risk_level": "high", "fix": "سياسة: لا شيء على الدرج أبداً"},
    ],
    "entrance": [
        {"hazard": "عتبة باب مرتفعة", "risk_level": "medium", "fix": "منحدر تدريجي أو إزالة"},
        {"hazard": "إضاءة خارجية ضعيفة", "risk_level": "medium", "fix": "مصباح حساس للحركة"},
        {"hazard": "درج خارجي بدون درابزين", "risk_level": "high", "fix": "درابزين + إضاءة + شريط تباين"},
    ],
}

FALL_RISK_FACTORS = {
    "vision": {
        "low_va": {"condition": "VA < 6/18", "risk_increase": "1.7x", "intervention": "تصحيح بصري + أجهزة مساعدة"},
        "field_loss": {"condition": "فقد مجال بصري", "risk_increase": "2.0x", "intervention": "O&M + تعديلات بيئية"},
        "contrast_loss": {"condition": "CS < 1.5 log", "risk_increase": "1.5x", "intervention": "تحسين إضاءة + تباين بيئي"},
        "depth_perception": {"condition": "ضعف إدراك العمق", "risk_increase": "1.8x", "intervention": "تجنب نظارات progressive عند المشي"},
    },
    "physical": {
        "balance": {"condition": "ضعف التوازن", "risk_increase": "2.5x", "intervention": "Otago Exercise Programme"},
        "muscle_weakness": {"condition": "ضعف عضلي", "risk_increase": "2.0x", "intervention": "تمارين تقوية + physio"},
        "foot_problems": {"condition": "مشاكل القدم", "risk_increase": "1.5x", "intervention": "فحص القدم + أحذية مناسبة"},
    },
    "medication": {
        "sedatives": {"condition": "مهدئات/منومات", "risk_increase": "1.7x", "intervention": "مراجعة مع الطبيب لتقليل أو إيقاف"},
        "antihypertensives": {"condition": "خافضات ضغط", "risk_increase": "1.3x", "intervention": "مراقبة orthostatic hypotension"},
        "polypharmacy": {"condition": "≥4 أدوية", "risk_increase": "1.5x", "intervention": "مراجعة صيدلانية شاملة"},
    },
    "environmental": {
        "poor_lighting": {"condition": "إضاءة < 300 لوكس", "risk_increase": "1.5x", "intervention": "ترقية الإضاءة"},
        "tripping_hazards": {"condition": "عوائق أرضية", "risk_increase": "2.0x", "intervention": "إزالة + تنظيم"},
        "no_handrails": {"condition": "لا مقابض/درابزين", "risk_increase": "1.8x", "intervention": "تركيب مقابض"},
    },
}


# ═══════════════════════════════════════════════════════════════
# منطق التقييم
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


def _assess_home(params: dict) -> dict:
    """تقييم البيئة المنزلية الشامل"""
    va = _parse_va(params.get("visual_acuity", ""))
    field = params.get("field_type", "general_reduction")
    age = int(params.get("patient_age", 65))
    fall_history = int(params.get("fall_count_12months", 0))
    mobility = params.get("mobility_level", "independent")
    rooms = params.get("rooms_to_assess", list(ROOM_HAZARDS.keys()))

    # Fall risk assessment
    risk_score = 0
    risk_factors = []

    if va < 0.3:
        risk_score += 2
        risk_factors.append(FALL_RISK_FACTORS["vision"]["low_va"])
    if field in ["peripheral_loss", "hemianopia", "tunnel_vision"]:
        risk_score += 2
        risk_factors.append(FALL_RISK_FACTORS["vision"]["field_loss"])
    if age > 65:
        risk_score += 1
    if age > 80:
        risk_score += 1
    if fall_history >= 2:
        risk_score += 3
        risk_factors.append({"condition": f"تاريخ {fall_history} سقطات في آخر 12 شهر", "risk_increase": "3.0x", "intervention": "تدخل عاجل متعدد العوامل"})
    elif fall_history == 1:
        risk_score += 1
    if mobility in ["assisted", "wheelchair"]:
        risk_score += 1

    risk_level = "منخفض"
    if risk_score >= 5:
        risk_level = "عالٍ جداً"
    elif risk_score >= 3:
        risk_level = "عالٍ"
    elif risk_score >= 2:
        risk_level = "متوسط"

    # Room-by-room assessment
    room_assessments = {}
    total_hazards = 0
    high_priority_fixes = []

    for room in rooms:
        if room not in ROOM_HAZARDS:
            continue
        hazards = ROOM_HAZARDS[room]
        lighting = LIGHTING_STANDARDS.get(room, {})

        room_result = {
            "room_name": lighting.get("label", room),
            "lighting": {
                "minimum_lux": lighting.get("min_lux", 300),
                "recommended_lux": lighting.get("recommended_lux", 500),
                "recommendation": f"تأكد من ≥{lighting.get('recommended_lux', 500)} لوكس"
            },
            "hazards": [],
            "high_priority_count": 0
        }

        for h in hazards:
            room_result["hazards"].append(h)
            total_hazards += 1
            if h["risk_level"] == "high":
                room_result["high_priority_count"] += 1
                high_priority_fixes.append({
                    "room": lighting.get("label", room),
                    "hazard": h["hazard"],
                    "fix": h["fix"]
                })

        room_assessments[room] = room_result

    # Generate priority action plan
    action_plan = {
        "immediate": [f for f in high_priority_fixes],
        "short_term": [
            "تركيب إضاءة ليلية تلقائية في الممرات والحمام",
            "شراء سجادات مانعة للانزلاق",
            "إزالة الأسلاك والعوائق من الممرات"
        ],
        "medium_term": [
            "ترقية الإضاءة العامة إلى LED عالي اللومن",
            "تركيب مقابض في الحمام وعند السلالم",
            "تنظيم المنزل بنظام الأماكن الثابتة"
        ],
        "long_term": [
            "تقييم الحاجة لنظام إنذار شخصي",
            "برنامج Otago للتوازن والتقوية",
            "مراجعة دورية كل 6 أشهر"
        ]
    }

    return {
        "assessment_type": "home",
        "patient_profile": {
            "visual_acuity": va,
            "field_type": field,
            "age": age,
            "fall_history": fall_history,
            "mobility_level": mobility
        },
        "fall_risk": {
            "score": risk_score,
            "level": risk_level,
            "factors": risk_factors
        },
        "room_assessments": room_assessments,
        "summary": {
            "total_hazards": total_hazards,
            "high_priority": len(high_priority_fixes),
            "rooms_assessed": len(room_assessments)
        },
        "action_plan": action_plan,
        "evidence": {
            "primary": "Campbell 2005 RCT: تعديلات منزلية تقلل السقوط 41%",
            "level": "1b",
            "recommendation": "A"
        },
        "timestamp": datetime.now().isoformat()
    }


def _assess_workplace(params: dict) -> dict:
    """تقييم بيئة العمل"""
    va = _parse_va(params.get("visual_acuity", ""))
    field = params.get("field_type", "general_reduction")
    job_type = params.get("job_type", "office")

    recommendations = {
        "workstation": [],
        "lighting": [],
        "technology": [],
        "ergonomics": []
    }

    # General recommendations
    recommendations["lighting"].extend([
        "إضاءة مكتب ≥500 لوكس + مصباح مهام موجه",
        "تجنب الوهج: شاشة مضادة للانعكاس + ستائر",
        "إضاءة موحدة بدون ظلال حادة"
    ])

    # VA-specific
    if va < 0.3:
        recommendations["technology"].extend([
            "شاشة كبيرة (27\"+) مع تكبير نظام التشغيل",
            "برنامج تكبير شاشة (ZoomText, Magnifier)",
            "لوحة مفاتيح بحروف كبيرة أو high-contrast"
        ])
    if va < 0.1:
        recommendations["technology"].extend([
            "قارئ شاشة (JAWS, NVDA, VoiceOver)",
            "OCR للمستندات الورقية",
            "هاتف مكتب بأرقام كبيرة"
        ])

    # Field-specific
    if field in ["hemianopia", "peripheral_loss"]:
        recommendations["workstation"].extend([
            "وضع الزملاء/الباب في الجانب المبصر",
            "مرآة على المكتب لرؤية الجانب المفقود",
            "تنظيم المكتب بحيث الأهم في الجانب المبصر"
        ])

    # Job-specific
    if job_type == "office":
        recommendations["ergonomics"].extend([
            "مسافة شاشة 40-60 سم (قد تقل مع التكبير)",
            "زاوية شاشة: مركز الشاشة عند مستوى العين أو أقل",
            "استراحة بصرية: قاعدة 20-20-20 (كل 20 دقيقة، انظر 20 قدم، 20 ثانية)"
        ])
    elif job_type == "manual":
        recommendations["workstation"].extend([
            "إضاءة مهام مكثفة (1000+ لوكس) على منطقة العمل",
            "مكبر مثبت (mounted magnifier) إذا لزم",
            "تباين عالٍ في أدوات العمل والقياسات"
        ])

    return {
        "assessment_type": "workplace",
        "patient_profile": {
            "visual_acuity": va,
            "field_type": field,
            "job_type": job_type
        },
        "recommendations": recommendations,
        "assistive_technology": {
            "screen_readers": ["JAWS", "NVDA", "VoiceOver"] if va < 0.1 else [],
            "magnification": ["ZoomText", "Windows Magnifier", "macOS Zoom"] if va < 0.3 else [],
            "hardware": ["شاشة 27+\"", "لوحة مفاتيح high-contrast"] if va < 0.3 else []
        },
        "employer_guidance": [
            "تعديلات معقولة (Reasonable Accommodations) حق قانوني",
            "تقييم مهني مع OT متخصص في ضعف البصر",
            "مراجعة دورية للاحتياجات كل 6-12 شهر"
        ],
        "timestamp": datetime.now().isoformat()
    }


def _assess_school(params: dict) -> dict:
    """تقييم البيئة المدرسية"""
    va = _parse_va(params.get("visual_acuity", ""))
    field = params.get("field_type", "general_reduction")
    grade_level = params.get("grade_level", "elementary")

    recommendations = {
        "seating": [],
        "materials": [],
        "technology": [],
        "teacher_guidance": []
    }

    # Seating
    recommendations["seating"].extend([
        "المقعد الأمامي — الصف الأول أو الثاني",
        "بعيد عن النوافذ (تجنب الوهج)",
        "قرب السبورة + في الوسط"
    ])
    if field in ["hemianopia_right"]:
        recommendations["seating"].append("الجلوس بحيث السبورة على يمين الطالب")
    elif field in ["hemianopia_left"]:
        recommendations["seating"].append("الجلوس بحيث السبورة على يسار الطالب")

    # Materials
    if va < 0.3:
        recommendations["materials"].extend([
            "طباعة مكبرة (18-24 نقطة على الأقل)",
            "نسخ محسنة التباين (أسود على أبيض أو أصفر)",
            "أوراق اختبار مكبرة + وقت إضافي (50-100%)",
            "كتب مكبرة أو نسخ رقمية مكبرة"
        ])
    if va < 0.1:
        recommendations["materials"].extend([
            "مواد بطريقة Braille حسب الحاجة",
            "تسجيلات صوتية للمحتوى",
            "مساعد بصري/قارئ في الاختبارات"
        ])

    # Technology
    recommendations["technology"].extend([
        "iPad/Tablet مع إعدادات إمكانية الوصول",
        "تطبيقات تكبير + OCR للمستندات"
    ])
    if va < 0.3:
        recommendations["technology"].extend([
            "CCTV محمول في الصف",
            "كاميرا توثيق للسبورة (تعرض على شاشة شخصية)"
        ])

    # Teacher guidance
    recommendations["teacher_guidance"].extend([
        "التحدث أثناء الكتابة على السبورة (لا تعتمد على البصر فقط)",
        "توزيع نسخ مطبوعة من محتوى السبورة",
        "السماح بالتصوير بالهاتف للسبورة",
        "عدم المعاقبة على بطء القراءة/الكتابة",
        "توفير وقت إضافي في الاختبارات والواجبات"
    ])

    return {
        "assessment_type": "school",
        "student_profile": {
            "visual_acuity": va,
            "field_type": field,
            "grade_level": grade_level
        },
        "recommendations": recommendations,
        "iep_recommendations": [
            "خطة تعليمية فردية (IEP) مع أهداف بصرية",
            "تقييم TVI (Teacher of Visually Impaired) دوري",
            "تقييم O&M إذا VA < 6/60 أو فقد مجال",
            "تكنولوجيا مساعدة حسب التقييم"
        ],
        "timestamp": datetime.now().isoformat()
    }


def _generate_fall_prevention_plan(params: dict) -> dict:
    """خطة وقاية من السقوط متعددة العوامل"""
    va = _parse_va(params.get("visual_acuity", ""))
    age = int(params.get("patient_age", 70))
    fall_history = int(params.get("fall_count_12months", 0))
    medications = params.get("medications", [])
    balance_status = params.get("balance_status", "fair")

    plan = {
        "environmental": {
            "priority": "عالية",
            "actions": [
                "تقييم منزلي شامل (استخدم assess_home)",
                "تعديلات إضاءة + تباين + إزالة عوائق",
                "مقابض في الحمام + درابزين على السلالم"
            ],
            "evidence": "Campbell 2005: تقليل السقوط 41%"
        },
        "exercise": {
            "priority": "عالية",
            "program": "Otago Exercise Programme",
            "actions": [
                "تمارين تقوية: 30 دقيقة × 3/أسبوع",
                "تمارين توازن: ضمن نفس البرنامج",
                "مشي: 30 دقيقة × 2/أسبوع (بيئة آمنة)",
                "إشراف physio/OT في الأسابيع الأولى"
            ],
            "evidence": "Gillespie 2012 Cochrane: تقليل السقوط 35%"
        },
        "vision": {
            "priority": "عالية",
            "actions": [
                "تحديث تصحيح النظارة",
                "نظارة واحدة للمشي (ليست progressive)",
                "تقييم أجهزة مساعدة بصرية",
                "تقييم O&M إذا VA < 6/60"
            ]
        },
        "medication_review": {
            "priority": "متوسطة",
            "actions": [
                "مراجعة صيدلانية شاملة",
                "تقليل/إيقاف المهدئات إن أمكن",
                "مراقبة ضغط الدم الانتصابي"
            ]
        },
        "monitoring": {
            "actions": [
                "سجل يومي للسقوط/شبه السقوط",
                "FES-I (Falls Efficacy Scale) كل 3 أشهر",
                "TUG (Timed Up and Go) كل 3 أشهر",
                "إعادة تقييم منزلي كل 6 أشهر"
            ]
        }
    }

    # Risk stratification
    risk_level = "standard"
    if fall_history >= 2 or (fall_history >= 1 and (va < 0.1 or age > 80)):
        risk_level = "high"
        plan["referrals"] = [
            "إحالة لطب المسنين (Geriatrics) — تقييم شامل",
            "إحالة لعلاج طبيعي — برنامج Otago",
            "إحالة لـ O&M إذا فقد بصري + مشاكل تنقل"
        ]

    return {
        "fall_prevention_plan": plan,
        "risk_level": risk_level,
        "patient_profile": {
            "age": age,
            "visual_acuity": va,
            "fall_history": fall_history,
            "balance": balance_status
        },
        "evidence_summary": {
            "Campbell_2005": "تعديلات منزلية → -41% سقوط",
            "Gillespie_2012": "تمارين توازن → -35% سقوط",
            "combined": "التدخل المتعدد أكثر فعالية من أي تدخل منفرد"
        },
        "timestamp": datetime.now().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def assess_environment(params: dict) -> dict:
    """
    تقييم البيئة المنزلية/العمل/المدرسة

    Args:
        params: dict containing:
            - action: "assess_home" | "assess_workplace" | "assess_school" | "fall_prevention"
            - visual_acuity: حدة الإبصار
            - field_type: نوع الفقد البصري
            - patient_age: العمر
            - fall_count_12months: عدد السقطات
            - mobility_level: مستوى التنقل
            - job_type: نوع العمل (لـ workplace)
            - grade_level: المرحلة الدراسية (لـ school)

    Returns:
        dict with assessment results and recommendations
    """
    action = params.get("action", "assess_home")

    try:
        if action == "assess_home":
            return _assess_home(params)
        elif action == "assess_workplace":
            return _assess_workplace(params)
        elif action == "assess_school":
            return _assess_school(params)
        elif action == "fall_prevention":
            return _generate_fall_prevention_plan(params)
        else:
            return {
                "error": f"إجراء غير معروف: {action}",
                "available_actions": ["assess_home", "assess_workplace", "assess_school", "fall_prevention"]
            }
    except Exception as e:
        return {"error": f"خطأ في تقييم البيئة: {str(e)}"}
