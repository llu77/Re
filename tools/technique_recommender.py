"""
Technique Recommender — محرك التوصية بتقنيات التأهيل البصري المتقدمة
===================================================================
محرك قرار سريري يوصي بالتقنيات المناسبة بناءً على:
- نمط الفقد البصري (central, hemianopia, tunnel, etc.)
- التشخيص الأساسي + حدة الإبصار + المجال البصري
- الأهداف الوظيفية + العمر + الحالة الإدراكية
- المعدات المتوفرة + بيئة التأهيل

يغطي 25+ تقنية مصنفة: تعويضية، بديلة، ترميمية
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# تصنيف مستويات الأدلة العلمية
# ═══════════════════════════════════════════════════════════════

EVIDENCE_CLASSIFICATION = {
    # ─── تقنيات تعويضية (Compensatory) ───
    "evt_traditional": {
        "level": "2b",
        "description": "Cohort studies showing PRL development",
        "refs": ["Crossland 2014", "Nilsson 2003"],
        "recommendation": "B"
    },
    "evt_biofeedback_maia": {
        "level": "1b",
        "description": "RCT showing superior fixation stability with MAIA biofeedback",
        "refs": ["Vingolo 2018 RCT", "Morales 2020"],
        "recommendation": "A"
    },
    "evt_biofeedback_mp3": {
        "level": "1b",
        "description": "RCT with MP-3 microperimetry biofeedback",
        "refs": ["Tarita-Nistor 2019"],
        "recommendation": "A"
    },
    "scanning_training_zihl": {
        "level": "1a",
        "description": "Cochrane systematic review confirms efficacy for hemianopia",
        "refs": ["Pollock 2019 Cochrane", "Zihl 1995 original"],
        "recommendation": "A"
    },
    "scanning_neuroeyecoach": {
        "level": "1b",
        "description": "RCT: NEC comparable to in-office with better compliance",
        "refs": ["Aimola 2014 RCT", "Rowe 2017"],
        "recommendation": "A"
    },
    "scanning_search_trial": {
        "level": "1b",
        "description": "SEARCH multicenter RCT for stroke hemianopia",
        "refs": ["SEARCH Trial 2021"],
        "recommendation": "A"
    },
    "avist": {
        "level": "1b",
        "description": "RCT showing advantage over visual-only scanning",
        "refs": ["Keller 2010 RCT", "Keller 2014"],
        "recommendation": "A"
    },
    "oculomotor_convergence": {
        "level": "1b",
        "description": "CITT RCT: office-based therapy superior to home-based",
        "refs": ["CITT 2008 RCT", "Scheiman 2005"],
        "recommendation": "A"
    },
    "oculomotor_accommodation": {
        "level": "2b",
        "description": "Case series for post-TBI accommodative dysfunction",
        "refs": ["Ciuffreda 2007", "Green 2010"],
        "recommendation": "B"
    },
    "oculomotor_saccades": {
        "level": "2a",
        "description": "Systematic review of saccadic training post-TBI",
        "refs": ["Thiagarajan 2014", "Kapoor 2004"],
        "recommendation": "B"
    },
    "prism_adaptation": {
        "level": "1a",
        "description": "Multiple RCTs and meta-analysis for visual neglect",
        "refs": ["Rossetti 1998 landmark", "Frassinetti 2002", "Jacquin-Courtois 2013 Cochrane"],
        "recommendation": "A"
    },
    # ─── تقنيات بديلة (Substitutive) ───
    "peripheral_prisms_fresnel": {
        "level": "2b",
        "description": "Case series, field expansion confirmed",
        "refs": ["Bowers 2008", "Rossi 1990"],
        "recommendation": "B"
    },
    "peripheral_prisms_peli": {
        "level": "1b",
        "description": "Peli RCT: 40PD oblique prisms expand functional field",
        "refs": ["Peli 2000 original", "Bowers 2014 PMCT RCT"],
        "recommendation": "A"
    },
    "peripheral_prisms_mpp": {
        "level": "3",
        "description": "Case reports, emerging periscopic design",
        "refs": ["Jung 2020", "Houston 2018"],
        "recommendation": "C"
    },
    "smart_glasses_esight": {
        "level": "2b",
        "description": "Prospective cohort: significant VA improvement",
        "refs": ["Wittich 2018", "eSight clinical data 2023"],
        "recommendation": "B"
    },
    "smart_glasses_irisvision": {
        "level": "2b",
        "description": "Pilot studies showing improved reading and ADL",
        "refs": ["Deemer 2018", "IrisVision clinical 2022"],
        "recommendation": "B"
    },
    "smart_glasses_orcam": {
        "level": "2b",
        "description": "User satisfaction studies, OCR accuracy validated",
        "refs": ["Moisseiev 2019", "OrCam clinical 2023"],
        "recommendation": "B"
    },
    "ai_apps_bemyeyes": {
        "level": "4",
        "description": "User reports, no formal clinical trials yet",
        "refs": ["Be My Eyes + GPT-4V 2024"],
        "recommendation": "C"
    },
    # ─── تقنيات ترميمية (Restorative) ───
    "vrt_novavision": {
        "level": "2b",
        "description": "Controversial: Kasten 1998 positive, Reinhard 2005 negative",
        "refs": ["Kasten 1998", "Reinhard 2005 refutation", "Cochrane 2020"],
        "recommendation": "C",
        "controversy": "Eye movement confounds question validity of results"
    },
    "tdcs_occipital": {
        "level": "2b",
        "description": "Pilot studies showing transient VF improvements",
        "refs": ["Plow 2011", "Sabel 2020"],
        "recommendation": "C",
        "controversy": "Experimental, no large RCTs yet"
    },
    "trns_visual": {
        "level": "3",
        "description": "Early phase trials only",
        "refs": ["Herpich 2019"],
        "recommendation": "D"
    },
    "gene_therapy_luxturna": {
        "level": "1b",
        "description": "Phase III RCT: FDA/EMA approved for RPE65 mutations",
        "refs": ["Russell 2017 Phase III", "Maguire 2019 durability"],
        "recommendation": "A",
        "note": "Only for confirmed biallelic RPE65 mutations"
    },
    "retinal_prosthesis_argus": {
        "level": "2b",
        "description": "Argus II: largest implanted series but DISCONTINUED",
        "refs": ["da Cruz 2016", "Second Sight bankruptcy 2020"],
        "recommendation": "N/A",
        "note": "Manufacturer ceased operations"
    },
    "retinal_prosthesis_prima": {
        "level": "3",
        "description": "Phase I/II trials ongoing for dry AMD",
        "refs": ["Palanker 2020", "PRIMA feasibility 2023"],
        "recommendation": "D"
    },
    # ─── تقنيات إضافية ───
    "perceptual_learning": {
        "level": "1b",
        "description": "RCTs showing contrast sensitivity improvement",
        "refs": ["Polat 2004 RCT", "Levi 2009", "Huang 2008"],
        "recommendation": "A"
    },
    "telerehab_lvr": {
        "level": "1b",
        "description": "Bittner 2024 RCT: non-inferior to in-office LVR",
        "refs": ["Bittner 2024 RCT", "Goldstein 2015"],
        "recommendation": "A"
    },
    "environmental_modifications": {
        "level": "1b",
        "description": "Campbell 2005 RCT: home safety reduces falls in VI",
        "refs": ["Campbell 2005 RCT", "La Grow 2006"],
        "recommendation": "A"
    },
}


# ═══════════════════════════════════════════════════════════════
# قاعدة بيانات التقنيات
# ═══════════════════════════════════════════════════════════════

TECHNIQUE_DATABASE = {
    # ─── 1. تدريب الرؤية اللامركزية (EVT) ───
    "evt_traditional": {
        "name": "تدريب الرؤية اللامركزية التقليدي (Traditional EVT)",
        "name_en": "Traditional Eccentric Viewing Training",
        "category": "compensatory",
        "vision_loss_patterns": ["central_scotoma"],
        "diagnoses": ["AMD", "Stargardt", "macular_hole", "macular_dystrophy", "cone_dystrophy"],
        "va_range": (0.02, 0.3),
        "prerequisites": ["some_peripheral_vision", "adequate_cognition"],
        "contraindications": ["total_blindness", "severe_cognitive_impairment", "unstable_retinal_condition"],
        "equipment_needed": ["reading_materials", "training_cards"],
        "setting": ["clinic", "home", "hybrid"],
        "protocol": {
            "phases": [
                {"name": "PRL تحديد موقع", "duration": "1-2 جلسات", "description": "تحديد النقطة الشبكية المفضلة باستخدام Amsler Grid أو Microperimetry"},
                {"name": "تثبيت PRL", "duration": "4-6 جلسات", "description": "تمارين تثبيت النظر على PRL المختار باستخدام أهداف بصرية"},
                {"name": "القراءة باستخدام PRL", "duration": "6-8 جلسات", "description": "تدريب على القراءة مع استخدام التقنية اللامركزية + تكبير مناسب"},
                {"name": "التعميم", "duration": "2-4 جلسات", "description": "نقل المهارة للمهام اليومية: التعرف على الوجوه، التلفزيون، إلخ"}
            ],
            "total_sessions": "12-20 جلسة",
            "session_duration": "30-45 دقيقة",
            "frequency": "2-3 مرات أسبوعياً"
        },
        "expected_outcomes": {
            "reading_speed": "تحسن 30-60% في سرعة القراءة",
            "fixation": "تحسن استقرار التثبيت",
            "quality_of_life": "تحسن VFQ-25 بمعدل 5-10 نقاط"
        },
        "evidence_key": "evt_traditional"
    },
    "evt_biofeedback": {
        "name": "تدريب EVT مع Biofeedback بالـ Microperimetry",
        "name_en": "Microperimetry Biofeedback Training (MBFT)",
        "category": "compensatory",
        "vision_loss_patterns": ["central_scotoma"],
        "diagnoses": ["AMD", "Stargardt", "macular_hole", "macular_dystrophy"],
        "va_range": (0.02, 0.3),
        "prerequisites": ["some_peripheral_vision", "adequate_cognition", "microperimetry_available"],
        "contraindications": ["total_blindness", "severe_cognitive_impairment", "nystagmus"],
        "equipment_needed": ["MAIA_or_MP3"],
        "setting": ["clinic"],
        "protocol": {
            "phases": [
                {"name": "خريطة الحساسية", "duration": "جلسة 1", "description": "فحص microperimetry لتحديد أفضل PRL بناءً على الحساسية الفعلية"},
                {"name": "Biofeedback Training", "duration": "8-12 جلسة", "description": "تدريب مع تغذية راجعة صوتية/بصرية من MAIA أو MP-3 لتوجيه التثبيت إلى PRL الأمثل"},
                {"name": "التعزيز", "duration": "4-6 جلسات", "description": "جلسات تعزيز شهرية لمدة 6 أشهر"}
            ],
            "total_sessions": "12-18 جلسة + 6 جلسات تعزيز",
            "session_duration": "15-20 دقيقة (أقصر من التقليدي)",
            "frequency": "مرة أسبوعياً"
        },
        "expected_outcomes": {
            "reading_speed": "تحسن 40-80% (أفضل من التقليدي)",
            "fixation": "تحسن BCEA بنسبة 50-70%",
            "quality_of_life": "تحسن VFQ-25 بمعدل 8-15 نقطة"
        },
        "evidence_key": "evt_biofeedback_maia"
    },

    # ─── 2. تدريب المسح البصري (Scanning Training) ───
    "scanning_zihl": {
        "name": "تدريب المسح البصري — طريقة Zihl",
        "name_en": "Compensatory Scanning Training (Zihl Method)",
        "category": "compensatory",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left", "quadrantanopia"],
        "diagnoses": ["stroke", "TBI", "tumor_resection", "ABI"],
        "va_range": (0.05, 1.0),
        "prerequisites": ["adequate_cognition", "stable_field_defect"],
        "contraindications": ["severe_cognitive_impairment", "active_neglect_without_treatment", "unstable_neurological"],
        "equipment_needed": ["computer_with_software", "large_display"],
        "setting": ["clinic", "home"],
        "protocol": {
            "phases": [
                {"name": "التوعية", "duration": "1-2 جلسات", "description": "شرح العمى الشقي وآلية التعويض بحركات العين"},
                {"name": "مسح ثابت", "duration": "6-8 جلسات", "description": "تدريب على مسح منظم نحو الجانب المصاب مع أهداف ثابتة"},
                {"name": "مسح ديناميكي", "duration": "6-8 جلسات", "description": "أهداف متحركة + بيئات معقدة"},
                {"name": "التطبيق الوظيفي", "duration": "4-6 جلسات", "description": "القراءة، عبور الطريق، التسوق"}
            ],
            "total_sessions": "20-30 جلسة",
            "session_duration": "40-60 دقيقة",
            "frequency": "3-5 مرات أسبوعياً"
        },
        "expected_outcomes": {
            "visual_field": "لا توسيع فعلي للمجال — تحسين استراتيجيات التعويض",
            "search_time": "تقليل زمن البحث البصري 30-50%",
            "functional": "تحسن في القراءة والتنقل والأنشطة اليومية",
            "quality_of_life": "تحسن VFQ-25 بمعدل 10-15 نقطة"
        },
        "evidence_key": "scanning_training_zihl"
    },
    "scanning_neuroeyecoach": {
        "name": "NeuroEyeCoach — تدريب منزلي محوسب",
        "name_en": "NeuroEyeCoach (NEC) Home-based Training",
        "category": "compensatory",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left", "quadrantanopia"],
        "diagnoses": ["stroke", "TBI", "tumor_resection"],
        "va_range": (0.1, 1.0),
        "prerequisites": ["adequate_cognition", "computer_access", "basic_computer_skills"],
        "contraindications": ["severe_cognitive_impairment", "inability_to_use_computer"],
        "equipment_needed": ["computer", "internet"],
        "setting": ["home", "hybrid"],
        "protocol": {
            "phases": [
                {"name": "إعداد وتدريب", "duration": "جلسة 1", "description": "إعداد البرنامج + تدريب المريض على الاستخدام"},
                {"name": "تدريب يومي", "duration": "8-12 أسبوع", "description": "20-30 دقيقة يومياً على منصة NEC مع تكيف تلقائي للصعوبة"},
                {"name": "متابعة", "duration": "شهرية", "description": "مراجعة التقدم عبر لوحة المتابعة الإلكترونية"}
            ],
            "total_sessions": "56-84 جلسة منزلية",
            "session_duration": "20-30 دقيقة",
            "frequency": "يومياً"
        },
        "expected_outcomes": {
            "search_time": "تحسن مماثل لـ Zihl في العيادة",
            "compliance": "التزام أعلى (بيئة منزلية مريحة)",
            "functional": "تحسن في القراءة والتنقل"
        },
        "evidence_key": "scanning_neuroeyecoach"
    },

    # ─── 3. تدريب المسح السمعي-البصري (AViST) ───
    "avist": {
        "name": "تدريب المسح السمعي-البصري (AViST)",
        "name_en": "Audio-Visual Scanning Training",
        "category": "compensatory",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left", "hemianopia_with_neglect"],
        "diagnoses": ["stroke", "TBI"],
        "va_range": (0.05, 1.0),
        "prerequisites": ["adequate_hearing", "adequate_cognition"],
        "contraindications": ["bilateral_hearing_loss", "severe_cognitive_impairment"],
        "equipment_needed": ["avist_system_or_equivalent", "speakers"],
        "setting": ["clinic"],
        "protocol": {
            "phases": [
                {"name": "تنبيه سمعي", "duration": "4-6 جلسات", "description": "تنبيه صوتي من الجانب المصاب يسبق الهدف البصري"},
                {"name": "تقليل الدعم", "duration": "6-8 جلسات", "description": "تقليل تدريجي للتنبيه السمعي مع الحفاظ على المسح"},
                {"name": "بصري فقط", "duration": "4-6 جلسات", "description": "مسح بصري مستقل بدون تنبيه سمعي"}
            ],
            "total_sessions": "14-20 جلسة",
            "session_duration": "45 دقيقة",
            "frequency": "3 مرات أسبوعياً"
        },
        "expected_outcomes": {
            "detection": "تحسن اكتشاف الأهداف 40-60% في الجانب المصاب",
            "reaction_time": "تقليل زمن الاستجابة مقارنة بالمسح البصري وحده",
            "functional": "أفضل من scanning وحده عند وجود neglect خفيف"
        },
        "evidence_key": "avist"
    },

    # ─── 4. تأهيل حركات العين (Oculomotor) ───
    "oculomotor_convergence": {
        "name": "تأهيل التقارب البصري (Convergence Insufficiency)",
        "name_en": "Convergence Insufficiency Treatment",
        "category": "compensatory",
        "vision_loss_patterns": ["oculomotor_dysfunction"],
        "diagnoses": ["TBI", "concussion", "convergence_insufficiency"],
        "va_range": (0.3, 1.0),
        "prerequisites": ["measurable_convergence_deficit", "NPC_receded"],
        "contraindications": ["CN3_palsy", "decompensated_strabismus"],
        "equipment_needed": ["Hart_chart", "Brock_string", "vectograms"],
        "setting": ["clinic", "hybrid"],
        "protocol": {
            "phases": [
                {"name": "CITT Protocol — عيادي", "duration": "12 أسبوع", "description": "جلسات أسبوعية 60 دقيقة: vergence therapy مع Hart chart + Brock string + vectograms"},
                {"name": "تمارين منزلية", "duration": "يومياً", "description": "Pencil push-ups + Brock string 15 دقيقة يومياً"},
                {"name": "إعادة تقييم", "duration": "كل 4 أسابيع", "description": "قياس NPC + vergence ranges + أعراض CISS"}
            ],
            "total_sessions": "12 جلسة عيادية + يومياً منزلي",
            "session_duration": "60 دقيقة عيادي / 15 دقيقة منزلي",
            "frequency": "أسبوعياً عيادي + يومياً منزلي"
        },
        "expected_outcomes": {
            "npc": "تحسن NPC من >10cm إلى <6cm",
            "vergence": "توسيع vergence ranges",
            "symptoms": "تقليل CISS score بنسبة >50%"
        },
        "evidence_key": "oculomotor_convergence"
    },
    "oculomotor_saccades": {
        "name": "تأهيل حركات العين السريعة (Saccadic Training)",
        "name_en": "Saccadic Training Post-TBI",
        "category": "compensatory",
        "vision_loss_patterns": ["oculomotor_dysfunction"],
        "diagnoses": ["TBI", "concussion", "stroke", "MS"],
        "va_range": (0.1, 1.0),
        "prerequisites": ["measurable_saccadic_dysfunction"],
        "contraindications": ["acute_intracranial_pathology"],
        "equipment_needed": ["saccadic_targets", "computer_with_tracking"],
        "setting": ["clinic", "home"],
        "protocol": {
            "phases": [
                {"name": "تقييم أساسي", "duration": "جلسة 1", "description": "قياس latency, accuracy, velocity للسكيدات"},
                {"name": "تدريب منظم", "duration": "8-12 أسبوع", "description": "تمارين سكيدات مع أهداف متدرجة الصعوبة (سعة، سرعة، دقة)"},
                {"name": "مهام وظيفية", "duration": "4 أسابيع", "description": "قراءة + بحث بصري + أنشطة يومية"}
            ],
            "total_sessions": "24-36 جلسة",
            "session_duration": "30 دقيقة",
            "frequency": "3 مرات أسبوعياً"
        },
        "expected_outcomes": {
            "saccade_accuracy": "تحسن دقة السكيدات 20-40%",
            "reading": "تحسن سرعة القراءة",
            "functional": "تقليل الأعراض البصرية"
        },
        "evidence_key": "oculomotor_saccades"
    },

    # ─── 5. علاج التكيف المنشوري (Prism Adaptation) ───
    "prism_adaptation": {
        "name": "علاج التكيف المنشوري للإهمال البصري",
        "name_en": "Prism Adaptation Therapy for Visual Neglect",
        "category": "compensatory",
        "vision_loss_patterns": ["visual_neglect", "hemianopia_with_neglect"],
        "diagnoses": ["right_hemisphere_stroke", "TBI_with_neglect"],
        "va_range": (0.05, 1.0),
        "prerequisites": ["confirmed_visual_neglect", "ability_to_point"],
        "contraindications": ["bilateral_neglect", "severe_apraxia", "unable_to_wear_prisms"],
        "equipment_needed": ["prism_goggles_10PD", "pointing_board"],
        "setting": ["clinic"],
        "protocol": {
            "phases": [
                {"name": "تقييم الإهمال", "duration": "جلسة 1", "description": "Line bisection + cancellation + BIT battery"},
                {"name": "Prism Adaptation", "duration": "10-14 جلسة", "description": "ارتداء نظارات منشورية 10° يمين + 90 حركة إشارة لأهداف (50 مع + 40 بدون رؤية اليد)"},
                {"name": "بعد التكيف", "duration": "قياس مباشر", "description": "تقييم الـ aftereffect: انحراف الإشارة نحو اليسار = نجاح التكيف"},
                {"name": "التعزيز", "duration": "أسابيع-أشهر", "description": "جلسات تعزيز 2-3 مرات أسبوعياً لمدة 2-4 أسابيع"}
            ],
            "total_sessions": "14-20 جلسة",
            "session_duration": "20-30 دقيقة",
            "frequency": "يومياً أثناء التنويم / 3× أسبوعياً خارجي"
        },
        "expected_outcomes": {
            "neglect_improvement": "تحسن 40-60% في اختبارات الإهمال",
            "duration": "تأثير يستمر ساعات-أيام بعد الجلسة الواحدة",
            "cumulative": "التأثير التراكمي يستمر أسابيع-أشهر",
            "adl": "تحسن في الأنشطة اليومية والتنقل"
        },
        "evidence_key": "prism_adaptation"
    },

    # ─── 6. المناشير المحيطية ───
    "peripheral_prisms_peli": {
        "name": "منشور Peli المحيطي (40PD)",
        "name_en": "Peli Peripheral Prism (40PD Oblique)",
        "category": "substitutive",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left"],
        "diagnoses": ["stroke", "TBI", "tumor_resection"],
        "va_range": (0.1, 1.0),
        "prerequisites": ["stable_hemianopia", "adequate_central_vision"],
        "contraindications": ["bilateral_hemianopia", "complete_blindness"],
        "equipment_needed": ["peli_prism_segments"],
        "setting": ["clinic", "home"],
        "protocol": {
            "phases": [
                {"name": "تركيب", "duration": "جلسة 1", "description": "تركيب شرائح منشورية 40PD على نظارة المريض في الجانب المصاب (علوي + سفلي)"},
                {"name": "تدريب", "duration": "2-4 جلسات", "description": "تدريب على تفسير الازدواجية المحيطية كتنبيه + توجيه النظر"},
                {"name": "تكيف", "duration": "2-4 أسابيع", "description": "ارتداء يومي مع زيادة تدريجية للمدة"},
                {"name": "متابعة", "duration": "شهري", "description": "تقييم الفائدة والتكيف"}
            ],
            "total_sessions": "3-5 جلسات + متابعة",
            "session_duration": "30-45 دقيقة",
            "frequency": "أسبوعياً ثم شهرياً"
        },
        "expected_outcomes": {
            "field_expansion": "توسيع المجال الوظيفي ~20° في الجانب المصاب",
            "mobility": "تحسن التنقل وتجنب العوائق",
            "satisfaction": "~60-70% من المرضى يستمرون بالاستخدام"
        },
        "evidence_key": "peripheral_prisms_peli"
    },

    # ─── 7. النظارات الذكية ───
    "smart_glasses_esight": {
        "name": "نظارات eSight Go الذكية",
        "name_en": "eSight Go Smart Glasses",
        "category": "substitutive",
        "vision_loss_patterns": ["central_scotoma", "general_reduction"],
        "diagnoses": ["AMD", "Stargardt", "diabetic_retinopathy", "albinism", "optic_atrophy"],
        "va_range": (0.01, 0.3),
        "prerequisites": ["some_residual_vision", "CF_or_better"],
        "contraindications": ["total_blindness_NLP", "severe_photophobia"],
        "equipment_needed": ["eSight_Go"],
        "setting": ["home", "clinic"],
        "protocol": {
            "phases": [
                {"name": "تجربة", "duration": "1-2 جلسات", "description": "تجربة الجهاز في العيادة مع ضبط الإعدادات"},
                {"name": "تدريب", "duration": "3-5 جلسات", "description": "تدريب على الاستخدام: قراءة، مسافة، كمبيوتر"},
                {"name": "استخدام يومي", "duration": "مستمر", "description": "استخدام يومي مع متابعة شهرية"}
            ],
            "total_sessions": "4-7 جلسات تدريب",
            "session_duration": "60 دقيقة",
            "frequency": "أسبوعياً"
        },
        "expected_outcomes": {
            "va_improvement": "تحسن VA إلى 20/20-20/40 أثناء الارتداء",
            "reading": "تحسن كبير في القراءة والكتابة",
            "distance": "تحسن رؤية المسافة (TV، وجوه)"
        },
        "evidence_key": "smart_glasses_esight"
    },
    "smart_glasses_orcam": {
        "name": "OrCam MyEye 3 — مساعد AI",
        "name_en": "OrCam MyEye 3 AI Assistant",
        "category": "substitutive",
        "vision_loss_patterns": ["central_scotoma", "general_reduction", "tunnel_vision", "total_blindness"],
        "diagnoses": ["any_visual_impairment"],
        "va_range": (0.0, 0.3),
        "prerequisites": ["ability_to_learn_gestures", "adequate_cognition"],
        "contraindications": ["severe_cognitive_impairment"],
        "equipment_needed": ["OrCam_MyEye_3"],
        "setting": ["home", "clinic"],
        "protocol": {
            "phases": [
                {"name": "إعداد", "duration": "جلسة 1", "description": "تركيب على النظارة + إعداد أولي + تسجيل الوجوه"},
                {"name": "تدريب أساسي", "duration": "2-3 جلسات", "description": "قراءة نصوص، التعرف على المنتجات، الأوراق النقدية"},
                {"name": "تدريب متقدم", "duration": "2-3 جلسات", "description": "التعرف على الوجوه، Smart Reading، الإيماءات"}
            ],
            "total_sessions": "5-7 جلسات",
            "session_duration": "45 دقيقة",
            "frequency": "أسبوعياً"
        },
        "expected_outcomes": {
            "reading": "قراءة أي نص مطبوع بصوت فوري",
            "face_recognition": "التعرف على الوجوه المسجلة",
            "independence": "زيادة الاستقلالية في المهام اليومية"
        },
        "evidence_key": "smart_glasses_orcam"
    },

    # ─── 8. علاج استعادة البصر (VRT) — مثير للجدل ───
    "vrt_novavision": {
        "name": "علاج استعادة البصر (VRT) — ⚠️ مثير للجدل",
        "name_en": "Vision Restoration Therapy (NovaVision) — CONTROVERSIAL",
        "category": "restorative",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left", "quadrantanopia"],
        "diagnoses": ["stroke", "TBI"],
        "va_range": (0.1, 1.0),
        "prerequisites": ["stable_field_defect_6months", "residual_vision_in_border"],
        "contraindications": ["complete_homonymous_hemianopia_no_residual", "active_disease"],
        "equipment_needed": ["VRT_software"],
        "setting": ["home"],
        "protocol": {
            "phases": [
                {"name": "قياس أساسي", "duration": "جلسة 1", "description": "تخطيط مجال بصري دقيق بـ HRP (High Resolution Perimetry)"},
                {"name": "تدريب يومي", "duration": "6 أشهر", "description": "30 دقيقة مرتين يومياً على حدود المنطقة الانتقالية (transition zone)"},
                {"name": "إعادة تقييم", "duration": "كل 3 أشهر", "description": "HRP لقياس أي توسع في المجال"}
            ],
            "total_sessions": "~360 جلسة منزلية",
            "session_duration": "30 دقيقة × 2 يومياً",
            "frequency": "يومياً"
        },
        "expected_outcomes": {
            "field_expansion": "ادعاء: 5° توسع — مشكوك فيه بسبب eye movement confounds",
            "controversy": "Reinhard 2005 لم يجد فرقاً عند ضبط حركات العين",
            "practical": "قد يحسن الانتباه البصري أكثر من المجال الفعلي"
        },
        "evidence_key": "vrt_novavision",
        "warnings": [
            "⚠️ نتائج مثيرة للجدل — يجب إبلاغ المريض",
            "⚠️ مكلف وطويل المدة — 6 أشهر",
            "⚠️ Scanning Training أكثر فعالية من حيث التكلفة والدليل"
        ]
    },

    # ─── 9. التحفيز عبر الجمجمة ───
    "tdcs_occipital": {
        "name": "التحفيز عبر الجمجمة بالتيار المستمر (tDCS) — ⚠️ تجريبي",
        "name_en": "Transcranial Direct Current Stimulation (tDCS) — EXPERIMENTAL",
        "category": "restorative",
        "vision_loss_patterns": ["hemianopia_right", "hemianopia_left", "general_reduction"],
        "diagnoses": ["stroke", "optic_neuritis"],
        "va_range": (0.05, 0.5),
        "prerequisites": ["no_metallic_implants", "no_seizure_history", "research_setting"],
        "contraindications": ["pacemaker", "seizure_disorder", "metallic_cranial_implants", "pregnancy"],
        "equipment_needed": ["tDCS_device", "trained_operator"],
        "setting": ["clinic"],
        "protocol": {
            "phases": [
                {"name": "تقييم", "duration": "جلسة 1", "description": "تأهل + خط أساس مجال بصري + VA"},
                {"name": "تحفيز", "duration": "10-20 جلسة", "description": "2mA, 20 دقيقة, القطب السالب على V1 المقابل + القطب الموجب على Cz"},
                {"name": "متابعة", "duration": "شهرياً", "description": "قياس المجال البصري + الوظائف"}
            ],
            "total_sessions": "10-20 جلسة",
            "session_duration": "20-30 دقيقة",
            "frequency": "5× أسبوعياً"
        },
        "expected_outcomes": {
            "field": "تحسن 2-5° عابر في بعض الدراسات",
            "contrast": "تحسن حساسية التباين",
            "limitation": "النتائج غير مستقرة — حاجة لـ RCTs كبيرة"
        },
        "evidence_key": "tdcs_occipital",
        "warnings": [
            "⚠️ تقنية تجريبية — ليست معتمدة للاستخدام السريري الروتيني",
            "⚠️ يجب أن تُجرى فقط في سياق بحثي مع موافقة أخلاقية",
            "⚠️ لا يوجد إثبات قاطع للفعالية طويلة المدى"
        ]
    },

    # ─── 10. العلاج الجيني ───
    "gene_therapy_luxturna": {
        "name": "العلاج الجيني Luxturna (Voretigene neparvovec)",
        "name_en": "Luxturna Gene Therapy for RPE65 Mutations",
        "category": "restorative",
        "vision_loss_patterns": ["general_reduction", "tunnel_vision"],
        "diagnoses": ["LCA_RPE65", "RP_RPE65"],
        "va_range": (0.0, 0.3),
        "prerequisites": ["confirmed_biallelic_RPE65_mutation", "viable_retinal_cells", "age_12months_plus"],
        "contraindications": ["no_viable_retinal_cells", "active_ocular_infection", "advanced_atrophy"],
        "equipment_needed": ["vitreoretinal_surgery_setup", "approved_center"],
        "setting": ["clinic"],
        "protocol": {
            "phases": [
                {"name": "التأهل الجيني", "duration": "أسابيع", "description": "تأكيد طفرة RPE65 ثنائية الأليل + تقييم OCT لسماكة الشبكية"},
                {"name": "الجراحة", "duration": "يوم واحد لكل عين", "description": "حقن تحت الشبكية بفاصل ≥6 أيام بين العينين"},
                {"name": "متابعة", "duration": "سنوات", "description": "مراقبة VA + VF + OCT + multiluminance mobility test (MLMT)"}
            ],
            "total_sessions": "2 عمليات + متابعة طويلة",
            "session_duration": "جراحة",
            "frequency": "جرعة واحدة لكل عين"
        },
        "expected_outcomes": {
            "mlmt": "تحسن MLMT بمعدل 1.6 مستوى إضاءة",
            "visual_field": "توسع المجال البصري",
            "night_vision": "تحسن كبير في الرؤية الليلية",
            "durability": "تحسن مستمر لمدة 3+ سنوات (Maguire 2019)"
        },
        "evidence_key": "gene_therapy_luxturna",
        "warnings": [
            "⚠️ فقط لطفرات RPE65 — يجب تأكيد الطفرة جينياً",
            "⚠️ مكلف جداً (~$425,000 لكل عين)",
            "⚠️ يتطلب مركزاً معتمداً لإجراء العلاج"
        ]
    },

    # ─── 11. التعلم الإدراكي ───
    "perceptual_learning": {
        "name": "التعلم الإدراكي (Perceptual Learning)",
        "name_en": "Perceptual Learning Training",
        "category": "compensatory",
        "vision_loss_patterns": ["central_scotoma", "general_reduction"],
        "diagnoses": ["amblyopia", "AMD", "myopia", "post_refractive"],
        "va_range": (0.05, 0.5),
        "prerequisites": ["adequate_cognition", "motivation", "computer_access"],
        "contraindications": ["severe_cognitive_impairment"],
        "equipment_needed": ["computer_with_calibrated_display"],
        "setting": ["home", "clinic", "hybrid"],
        "protocol": {
            "phases": [
                {"name": "تقييم أساسي", "duration": "جلسة 1", "description": "قياس CS + VA + crowding threshold"},
                {"name": "تدريب Gabor", "duration": "30-40 جلسة", "description": "كشف Gabor patches مع adaptive staircase (تزيد الصعوبة تلقائياً)"},
                {"name": "Lateral Masking", "duration": "20-30 جلسة", "description": "كشف أهداف مع flankers بمسافات متغيرة"},
                {"name": "إعادة تقييم", "duration": "كل 10 جلسات", "description": "قياس التحسن في CS + VA"}
            ],
            "total_sessions": "40-60 جلسة",
            "session_duration": "30 دقيقة",
            "frequency": "يومياً أو 5× أسبوعياً"
        },
        "expected_outcomes": {
            "contrast_sensitivity": "تحسن 1-2 سطر في CS",
            "visual_acuity": "تحسن 1-2 سطر في VA (خاصة amblyopia)",
            "transfer": "نقل محدود — خاص بالمهمة المدربة"
        },
        "evidence_key": "perceptual_learning"
    },

    # ─── 12. التأهيل عن بعد ───
    "telerehab_lvr": {
        "name": "التأهيل البصري عن بعد (Tele-LVR)",
        "name_en": "Telerehabilitation for Low Vision",
        "category": "compensatory",
        "vision_loss_patterns": ["central_scotoma", "general_reduction", "hemianopia_right", "hemianopia_left"],
        "diagnoses": ["any_visual_impairment"],
        "va_range": (0.02, 0.5),
        "prerequisites": ["internet_access", "video_capable_device", "caregiver_for_setup_if_needed"],
        "contraindications": ["no_internet", "severe_cognitive_impairment_without_caregiver"],
        "equipment_needed": ["tablet_or_computer", "internet", "webcam"],
        "setting": ["telerehab"],
        "protocol": {
            "phases": [
                {"name": "تقييم تقني", "duration": "جلسة 1", "description": "التحقق من الاتصال + المعدات + ضبط الإضاءة والكاميرا"},
                {"name": "تقييم بصري عن بعد", "duration": "جلسة 2", "description": "VA عن بعد + تقييم وظيفي + تحديد الأهداف"},
                {"name": "جلسات التأهيل", "duration": "6-12 جلسة", "description": "تدريب على الأجهزة + EVT + استراتيجيات يومية عبر الفيديو"},
                {"name": "متابعة", "duration": "شهرية", "description": "مراجعة التقدم + تعديل الخطة"}
            ],
            "total_sessions": "8-14 جلسة",
            "session_duration": "45-60 دقيقة",
            "frequency": "أسبوعياً أو كل أسبوعين"
        },
        "expected_outcomes": {
            "equivalence": "Bittner 2024 RCT: نتائج مكافئة للتأهيل الحضوري",
            "access": "إتاحة الخدمة للمناطق النائية",
            "satisfaction": "رضا مرضى عالٍ (>85%)"
        },
        "evidence_key": "telerehab_lvr"
    },

    # ─── 13. التعديلات البيئية ───
    "environmental_modifications": {
        "name": "التعديلات البيئية والوقاية من السقوط",
        "name_en": "Environmental Modifications & Fall Prevention",
        "category": "compensatory",
        "vision_loss_patterns": ["central_scotoma", "peripheral_loss", "tunnel_vision", "general_reduction"],
        "diagnoses": ["any_visual_impairment"],
        "va_range": (0.0, 0.5),
        "prerequisites": [],
        "contraindications": [],
        "equipment_needed": ["assessment_checklist"],
        "setting": ["home"],
        "protocol": {
            "phases": [
                {"name": "تقييم منزلي", "duration": "جلسة 1", "description": "تقييم شامل: إضاءة، تباين، عوائق، سلالم، حمام، مطبخ"},
                {"name": "التعديلات", "duration": "1-2 أسبوع", "description": "تنفيذ التعديلات: إضاءة 300+ لوكس، علامات تباين، إزالة عوائق، مقابض"},
                {"name": "تدريب", "duration": "2-3 جلسات", "description": "تدريب على استخدام التعديلات + تقنيات الأمان"},
                {"name": "متابعة", "duration": "3 أشهر", "description": "إعادة تقييم + قياس السقوط"}
            ],
            "total_sessions": "4-6 جلسات",
            "session_duration": "60-90 دقيقة",
            "frequency": "أسبوعياً ثم شهرياً"
        },
        "expected_outcomes": {
            "falls": "تقليل السقوط 41% (Campbell 2005 RCT)",
            "independence": "زيادة الاستقلالية في المنزل",
            "safety": "تقليل مخاطر الحوادث المنزلية"
        },
        "evidence_key": "environmental_modifications"
    },
}


# ═══════════════════════════════════════════════════════════════
# خريطة التدفق السريرية (Clinical Decision Flowchart)
# ═══════════════════════════════════════════════════════════════

CLINICAL_DECISION_FLOWCHART = {
    "central_scotoma": {
        "description": "فقد مركزي (scotoma) — AMD, Stargardt, etc.",
        "primary": ["evt_biofeedback", "evt_traditional", "perceptual_learning"],
        "secondary": ["smart_glasses_esight", "smart_glasses_orcam", "telerehab_lvr"],
        "adjunct": ["environmental_modifications"],
        "experimental": ["vrt_novavision"],
        "decision_notes": "MBFT أولاً إذا توفر microperimetry، وإلا EVT تقليدي. النظارات الذكية للحالات المتقدمة (VA < 0.1)"
    },
    "hemianopia_right": {
        "description": "عمى شقي أيمن — stroke, TBI",
        "primary": ["scanning_zihl", "scanning_neuroeyecoach"],
        "secondary": ["peripheral_prisms_peli", "avist"],
        "adjunct": ["environmental_modifications", "telerehab_lvr"],
        "experimental": ["vrt_novavision", "tdcs_occipital"],
        "decision_notes": "Scanning أولاً (أقوى دليل). Peli prisms للتنقل. NEC إذا لم يتوفر عيادة."
    },
    "hemianopia_left": {
        "description": "عمى شقي أيسر — stroke, TBI",
        "primary": ["scanning_zihl", "scanning_neuroeyecoach"],
        "secondary": ["peripheral_prisms_peli", "avist"],
        "adjunct": ["environmental_modifications", "telerehab_lvr"],
        "experimental": ["vrt_novavision", "tdcs_occipital"],
        "decision_notes": "نفس بروتوكول الأيمن مع عكس الاتجاه. تحقق من الإهمال (أكثر شيوعاً مع اليسر بسبب إصابة نصف الكرة الأيمن)."
    },
    "hemianopia_with_neglect": {
        "description": "عمى شقي مع إهمال بصري",
        "primary": ["prism_adaptation"],
        "secondary": ["avist", "scanning_zihl"],
        "adjunct": ["environmental_modifications"],
        "experimental": ["tdcs_occipital"],
        "decision_notes": "⚠️ يجب علاج الإهمال أولاً بـ Prism Adaptation قبل بدء Scanning. الإهمال يعيق فعالية scanning."
    },
    "quadrantanopia": {
        "description": "فقد ربعي في المجال البصري",
        "primary": ["scanning_zihl", "scanning_neuroeyecoach"],
        "secondary": ["peripheral_prisms_peli"],
        "adjunct": ["environmental_modifications"],
        "experimental": [],
        "decision_notes": "نفس بروتوكول hemianopia مع شدة أقل. المريض قد يعوض بسهولة أكبر."
    },
    "tunnel_vision": {
        "description": "رؤية نفقية — RP, Glaucoma المتقدم",
        "primary": ["environmental_modifications", "smart_glasses_orcam"],
        "secondary": ["scanning_zihl", "telerehab_lvr"],
        "adjunct": [],
        "experimental": ["gene_therapy_luxturna"],
        "decision_notes": "التعديلات البيئية + O&M أساسية. Luxturna فقط إذا RPE65+. OrCam للقراءة والتعرف."
    },
    "general_reduction": {
        "description": "انخفاض عام في الرؤية — diabetic retinopathy, cataract, optic atrophy",
        "primary": ["smart_glasses_esight", "perceptual_learning"],
        "secondary": ["smart_glasses_orcam", "telerehab_lvr"],
        "adjunct": ["environmental_modifications"],
        "experimental": ["tdcs_occipital"],
        "decision_notes": "النظارات الذكية للتكبير. التعلم الإدراكي لتحسين CS. التعديلات البيئية دائماً."
    },
    "visual_neglect": {
        "description": "إهمال بصري بدون عمى شقي",
        "primary": ["prism_adaptation"],
        "secondary": ["avist"],
        "adjunct": ["environmental_modifications"],
        "experimental": ["tdcs_occipital"],
        "decision_notes": "Prism Adaptation هو العلاج الأول. AViST كمكمل."
    },
    "oculomotor_dysfunction": {
        "description": "اضطراب حركات العين — Post-TBI, CI",
        "primary": ["oculomotor_convergence", "oculomotor_saccades"],
        "secondary": ["perceptual_learning"],
        "adjunct": [],
        "experimental": [],
        "decision_notes": "CITT protocol للتقارب. Saccadic training حسب التقييم. قد يتداخل مع scanning."
    },
    "cvi": {
        "description": "ضعف البصر القشري (CVI) — أطفال",
        "primary": ["environmental_modifications", "perceptual_learning"],
        "secondary": ["smart_glasses_orcam"],
        "adjunct": ["telerehab_lvr"],
        "experimental": [],
        "decision_notes": "CVI يحتاج بيئة مبسطة + تحفيز تدريجي. Roman-Lantzy Phase I-III approach."
    },
    "nystagmus": {
        "description": "رأرأة — خلقية أو مكتسبة",
        "primary": ["smart_glasses_esight", "perceptual_learning"],
        "secondary": ["smart_glasses_orcam"],
        "adjunct": ["environmental_modifications"],
        "experimental": [],
        "decision_notes": "eSight يمكن أن يعوض عدم استقرار الصورة. التعلم الإدراكي لتحسين CS. تجنب EVT biofeedback (التثبيت غير مستقر)."
    },
    "total_blindness": {
        "description": "عمى كامل (NLP أو LP فقط)",
        "primary": ["smart_glasses_orcam", "environmental_modifications"],
        "secondary": ["telerehab_lvr"],
        "adjunct": [],
        "experimental": ["gene_therapy_luxturna"],
        "decision_notes": "OrCam + AI apps للقراءة والتعرف. O&M أساسي. Luxturna فقط إذا RPE65+ مع خلايا شبكية باقية."
    },
    "mixed": {
        "description": "نمط مختلط (مثل: central + peripheral)",
        "primary": ["smart_glasses_esight", "environmental_modifications"],
        "secondary": ["telerehab_lvr", "perceptual_learning"],
        "adjunct": [],
        "experimental": [],
        "decision_notes": "يتطلب تقييم فردي دقيق. اختر التقنيات بناءً على الشكوى الأساسية والأهداف الوظيفية."
    },
}


# ═══════════════════════════════════════════════════════════════
# محرك التوصية
# ═══════════════════════════════════════════════════════════════

def _parse_va_decimal(va_str: str) -> float:
    """تحويل حدة الإبصار إلى decimal"""
    if not va_str:
        return 0.1
    va = str(va_str).strip().upper()

    # Special values
    special = {"NLP": 0.0, "LP": 0.005, "HM": 0.005, "CF": 0.01}
    if va in special:
        return special[va]

    # Snellen (e.g. 6/60, 20/200)
    if "/" in va:
        parts = va.split("/")
        try:
            return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            return 0.1

    # Decimal
    try:
        val = float(va)
        if val > 2.0:
            return 0.1
        return val
    except ValueError:
        return 0.1


def _get_evidence_info(evidence_key: str) -> dict:
    """استرجاع معلومات الدليل العلمي"""
    ev = EVIDENCE_CLASSIFICATION.get(evidence_key, {})
    return {
        "level": ev.get("level", "N/A"),
        "recommendation": ev.get("recommendation", "N/A"),
        "description": ev.get("description", ""),
        "refs": ev.get("refs", []),
        "controversy": ev.get("controversy", None)
    }


def _filter_technique(tech: dict, params: dict) -> dict:
    """تقييم مدى ملاءمة تقنية لحالة معينة. يرجع score + reasons"""
    score = 0
    reasons_for = []
    reasons_against = []

    # 1. VA range check
    va = _parse_va_decimal(params.get("visual_acuity", ""))
    va_min, va_max = tech.get("va_range", (0, 1))
    if va_min <= va <= va_max:
        score += 20
        reasons_for.append("حدة الإبصار ضمن النطاق المناسب")
    elif va < va_min:
        score -= 10
        reasons_against.append(f"حدة الإبصار ({va}) أقل من الحد الأدنى ({va_min})")
    elif va > va_max:
        score -= 5
        reasons_against.append(f"حدة الإبصار ({va}) أعلى من الحد الأقصى ({va_max}) — قد لا يحتاج هذه التقنية")

    # 2. Diagnosis match
    diagnosis = params.get("primary_diagnosis", "").lower().replace(" ", "_")
    if diagnosis:
        tech_diagnoses = [d.lower() for d in tech.get("diagnoses", [])]
        if diagnosis in tech_diagnoses or "any_visual_impairment" in tech_diagnoses:
            score += 15
            reasons_for.append("التشخيص متوافق مع التقنية")

    # 3. Age considerations
    age = params.get("patient_age")
    if age is not None:
        try:
            age = int(age)
            if tech.get("category") == "restorative" and age > 75:
                score -= 10
                reasons_against.append("العمر >75 — التقنيات الترميمية أقل فعالية")
            if "oculomotor" in tech.get("evidence_key", "") and age < 18:
                score += 5
                reasons_for.append("الأطفال/المراهقون يستجيبون جيداً لتأهيل حركات العين")
        except (ValueError, TypeError):
            pass

    # 4. Cognitive status
    cognitive = params.get("cognitive_status", "normal")
    if cognitive in ["moderate_impairment", "severe_impairment"]:
        prereqs = tech.get("prerequisites", [])
        if "adequate_cognition" in prereqs:
            score -= 20
            reasons_against.append("التقنية تتطلب قدرات إدراكية كافية")

    # 5. Equipment availability
    available_equipment = params.get("available_equipment", [])
    if available_equipment:
        needed = tech.get("equipment_needed", [])
        for eq in needed:
            if eq in available_equipment:
                score += 10
                reasons_for.append(f"المعدات المطلوبة متوفرة: {eq}")

    # 6. Setting match
    setting = params.get("setting", "clinic")
    tech_settings = tech.get("setting", [])
    if setting in tech_settings:
        score += 10
        reasons_for.append(f"بيئة التأهيل ({setting}) مناسبة")
    elif "hybrid" in tech_settings or "telerehab" in tech_settings:
        score += 5
    else:
        score -= 5
        reasons_against.append(f"بيئة التأهيل ({setting}) غير مدعومة مباشرة")

    # 7. Evidence level bonus
    ev_key = tech.get("evidence_key", "")
    ev = EVIDENCE_CLASSIFICATION.get(ev_key, {})
    level = ev.get("level", "5")
    level_scores = {"1a": 20, "1b": 18, "2a": 14, "2b": 12, "3": 8, "4": 5, "5": 2}
    level_num = level_scores.get(level, 2)
    score += level_num
    if level in ["1a", "1b"]:
        reasons_for.append(f"مستوى دليل قوي ({level})")

    # 8. Contraindication check
    contras = tech.get("contraindications", [])
    patient_conditions = params.get("conditions", [])
    for contra in contras:
        if contra in patient_conditions:
            score -= 50
            reasons_against.append(f"⚠️ موانع استخدام: {contra}")

    # 9. Prior rehabilitation check — تجنب تكرار تقنية فشلت سابقاً
    prior_rehab = params.get("prior_rehabilitation", [])
    if prior_rehab:
        tech_id = tech.get("evidence_key", "")
        tech_name_en = tech.get("name_en", "").lower()
        for prev in prior_rehab:
            prev_lower = prev.lower()
            if prev_lower in tech_id.lower() or prev_lower in tech_name_en:
                score -= 15
                reasons_against.append(f"تقنية مجربة سابقاً: {prev} — قد تكون الفعالية محدودة عند التكرار")
                break

    # 10. Cognitive-specific technology warnings
    if cognitive == "mild_impairment":
        if tech.get("category") == "substitutive" and "smart_glasses" in tech.get("evidence_key", ""):
            score -= 5
            reasons_against.append("النظارات الذكية تحتاج قدرة تقنية — ضعف إدراكي خفيف قد يصعب الاستخدام")
    if cognitive in ["moderate_impairment", "severe_impairment"]:
        if tech.get("category") == "substitutive" and "smart_glasses" in tech.get("evidence_key", ""):
            score -= 15
            reasons_against.append("⚠️ النظارات الذكية غير مناسبة مع ضعف إدراكي متوسط/شديد")

    return {
        "score": score,
        "reasons_for": reasons_for,
        "reasons_against": reasons_against
    }


def _recommend_techniques(params: dict) -> dict:
    """التوصية بالتقنيات المناسبة"""
    vision_loss = params.get("vision_loss_pattern", "mixed")
    flowchart = CLINICAL_DECISION_FLOWCHART.get(vision_loss, CLINICAL_DECISION_FLOWCHART["mixed"])

    results = {
        "vision_loss_pattern": vision_loss,
        "pattern_description": flowchart["description"],
        "clinical_notes": flowchart["decision_notes"],
        "primary_recommendations": [],
        "secondary_recommendations": [],
        "adjunct_recommendations": [],
        "experimental_options": [],
        "contraindicated": [],
        "timestamp": datetime.now().isoformat()
    }

    # Process each priority level
    priority_to_key = {
        "primary": "primary_recommendations",
        "secondary": "secondary_recommendations",
        "adjunct": "adjunct_recommendations",
        "experimental": "experimental_options"
    }
    for priority, result_key in priority_to_key.items():
        tech_ids = flowchart.get(priority, [])
        for tech_id in tech_ids:
            tech = TECHNIQUE_DATABASE.get(tech_id)
            if not tech:
                continue

            evaluation = _filter_technique(tech, params)
            evidence = _get_evidence_info(tech.get("evidence_key", ""))

            entry = {
                "technique_id": tech_id,
                "name": tech["name"],
                "name_en": tech.get("name_en", ""),
                "category": tech["category"],
                "suitability_score": evaluation["score"],
                "evidence_level": evidence["level"],
                "recommendation_grade": evidence["recommendation"],
                "reasons_for": evaluation["reasons_for"],
                "reasons_against": evaluation["reasons_against"],
                "warnings": tech.get("warnings", [])
            }

            if evaluation["score"] < -20:
                results["contraindicated"].append(entry)
            else:
                results[result_key].append(entry)

    # Sort each list by suitability score
    for key in ["primary_recommendations", "secondary_recommendations",
                 "adjunct_recommendations", "experimental_options"]:
        results[key].sort(key=lambda x: x["suitability_score"], reverse=True)

    # Automatic psychological screening recommendation (always included)
    age = params.get("patient_age")
    cognitive = params.get("cognitive_status", "normal")
    if cognitive in ["moderate_impairment", "severe_impairment"]:
        psych_tool = "إحالة لتقييم نفسي متخصص (المقاييس الذاتية كـ PHQ-9 قد لا تكون دقيقة مع الضعف الإدراكي)"
    elif age and int(age) >= 65:
        psych_tool = "GDS-15 (مخصص لكبار السن) + تقييم مرحلة التكيف مع فقدان البصر"
    else:
        psych_tool = "PHQ-2/PHQ-9 + تقييم مرحلة التكيف (نسبة انتشار الاكتئاب ~30% في ضعف البصر)"

    results["psychological_screening"] = {
        "recommendation": "فحص نفسي إلزامي لكل مريض ضعف بصر",
        "tool": psych_tool,
        "evidence": "Standard of Care — الاكتئاب يؤثر سلباً على نتائج التأهيل",
        "priority": "دائماً"
    }

    return results


def _get_technique_detail(params: dict) -> dict:
    """الحصول على تفاصيل كاملة لتقنية محددة"""
    tech_id = params.get("technique_id", "")
    tech = TECHNIQUE_DATABASE.get(tech_id)

    if not tech:
        available = list(TECHNIQUE_DATABASE.keys())
        return {
            "error": f"تقنية غير موجودة: {tech_id}",
            "available_techniques": available
        }

    evidence = _get_evidence_info(tech.get("evidence_key", ""))

    return {
        "technique_id": tech_id,
        "name": tech["name"],
        "name_en": tech.get("name_en", ""),
        "category": tech["category"],
        "applicable_patterns": tech.get("vision_loss_patterns", []),
        "applicable_diagnoses": tech.get("diagnoses", []),
        "va_range": {"min": tech["va_range"][0], "max": tech["va_range"][1]},
        "prerequisites": tech.get("prerequisites", []),
        "contraindications": tech.get("contraindications", []),
        "equipment_needed": tech.get("equipment_needed", []),
        "available_settings": tech.get("setting", []),
        "protocol": tech.get("protocol", {}),
        "expected_outcomes": tech.get("expected_outcomes", {}),
        "evidence": evidence,
        "warnings": tech.get("warnings", [])
    }


def _compare_techniques(params: dict) -> dict:
    """مقارنة بين تقنيتين أو أكثر"""
    tech_ids = params.get("technique_ids", [])
    if len(tech_ids) < 2:
        return {"error": "يجب تحديد تقنيتين على الأقل للمقارنة"}

    comparison = []
    for tid in tech_ids:
        tech = TECHNIQUE_DATABASE.get(tid)
        if not tech:
            comparison.append({"technique_id": tid, "error": "غير موجودة"})
            continue

        evidence = _get_evidence_info(tech.get("evidence_key", ""))
        evaluation = _filter_technique(tech, params)

        comparison.append({
            "technique_id": tid,
            "name": tech["name"],
            "category": tech["category"],
            "evidence_level": evidence["level"],
            "recommendation_grade": evidence["recommendation"],
            "suitability_score": evaluation["score"],
            "protocol_duration": tech.get("protocol", {}).get("total_sessions", "N/A"),
            "session_frequency": tech.get("protocol", {}).get("frequency", "N/A"),
            "setting": tech.get("setting", []),
            "equipment_needed": tech.get("equipment_needed", []),
            "expected_outcomes": tech.get("expected_outcomes", {}),
            "warnings": tech.get("warnings", []),
            "pros": evaluation["reasons_for"],
            "cons": evaluation["reasons_against"]
        })

    comparison.sort(key=lambda x: x.get("suitability_score", 0), reverse=True)

    return {
        "comparison": comparison,
        "best_match": comparison[0]["technique_id"] if comparison and "error" not in comparison[0] else None,
        "patient_context": {
            "visual_acuity": params.get("visual_acuity"),
            "diagnosis": params.get("primary_diagnosis"),
            "vision_loss_pattern": params.get("vision_loss_pattern")
        }
    }


def _get_protocol(params: dict) -> dict:
    """الحصول على بروتوكول تقنية معينة مفصل"""
    tech_id = params.get("technique_id", "")
    tech = TECHNIQUE_DATABASE.get(tech_id)

    if not tech:
        return {"error": f"تقنية غير موجودة: {tech_id}"}

    protocol = tech.get("protocol", {})
    evidence = _get_evidence_info(tech.get("evidence_key", ""))

    return {
        "technique_id": tech_id,
        "name": tech["name"],
        "protocol": {
            "phases": protocol.get("phases", []),
            "total_sessions": protocol.get("total_sessions", "N/A"),
            "session_duration": protocol.get("session_duration", "N/A"),
            "frequency": protocol.get("frequency", "N/A")
        },
        "prerequisites": tech.get("prerequisites", []),
        "equipment_needed": tech.get("equipment_needed", []),
        "expected_outcomes": tech.get("expected_outcomes", {}),
        "evidence_level": evidence["level"],
        "references": evidence.get("refs", []),
        "warnings": tech.get("warnings", []),
        "contraindications": tech.get("contraindications", [])
    }


def _list_all_techniques() -> dict:
    """قائمة بجميع التقنيات المتاحة"""
    techniques = []
    for tid, tech in TECHNIQUE_DATABASE.items():
        ev = _get_evidence_info(tech.get("evidence_key", ""))
        techniques.append({
            "id": tid,
            "name": tech["name"],
            "category": tech["category"],
            "patterns": tech.get("vision_loss_patterns", []),
            "evidence_level": ev["level"],
            "recommendation": ev["recommendation"]
        })

    # Group by category
    categories = {}
    for t in techniques:
        cat = t["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(t)

    return {
        "total_techniques": len(techniques),
        "by_category": categories,
        "available_patterns": list(CLINICAL_DECISION_FLOWCHART.keys())
    }


# ═══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def recommend_techniques(params: dict) -> dict:
    """
    محرك التوصية بتقنيات التأهيل البصري المتقدمة

    Args:
        params: dict containing:
            - action: "recommend" | "detail" | "compare" | "protocol" | "list"
            - vision_loss_pattern: نمط الفقد البصري
            - primary_diagnosis: التشخيص
            - visual_acuity: حدة الإبصار
            - patient_age: العمر
            - cognitive_status: الحالة الإدراكية
            - available_equipment: المعدات المتوفرة
            - setting: بيئة التأهيل
            - technique_id: معرف التقنية (لـ detail/protocol)
            - technique_ids: قائمة معرفات (لـ compare)

    Returns:
        dict with recommendations/details/comparison/protocol
    """
    action = params.get("action", "recommend")

    try:
        if action == "recommend":
            return _recommend_techniques(params)
        elif action == "detail":
            return _get_technique_detail(params)
        elif action == "compare":
            return _compare_techniques(params)
        elif action == "protocol":
            return _get_protocol(params)
        elif action == "list":
            return _list_all_techniques()
        else:
            return {
                "error": f"إجراء غير معروف: {action}",
                "available_actions": ["recommend", "detail", "compare", "protocol", "list"]
            }
    except Exception as e:
        return {"error": f"خطأ في محرك التوصية: {str(e)}"}
