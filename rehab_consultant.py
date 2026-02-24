"""
مستشار التأهيل الذكي — Rehabilitation AI Consultant
====================================================
النظام الرئيسي: يجمع بين System Prompt + Tool Use + Extended Thinking
"""

import os
import json
import base64
import anthropic
from typing import Optional

from tools.pubmed import search_pubmed_api, fetch_pubmed_article
from tools.calculator import calculate_visual_params
from tools.knowledge_base import search_vector_db
from tools.documents import generate_medical_document
from tools.functional_assessment import run_functional_assessment
from tools.device_recommender import recommend_devices
from tools.arabic_reading_calculator import calculate_arabic_reading_params
from tools.depression_screening import run_depression_screening
from tools.outcome_tracker import track_rehabilitation_outcomes
from tools.referral_generator import generate_referral
from tools.technique_recommender import recommend_techniques
from tools.perceptual_learning_planner import plan_perceptual_learning
from tools.environmental_assessment import assess_environment
from tools.telerehab_session_manager import manage_telerehab_session
from utils.security import sanitize_patient_input, validate_medical_output
from cdss import run_cdss_evaluation
from assessments import run_assessment
from interventions import run_intervention


# ═══════════════════════════════════════════════════════════════
# System Prompt — شخصية المستشار المتخصص
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
<role>
أنت استشاري تأهيل طبي متخصص وخبير في التأهيل البصري (Vision Rehabilitation Specialist).
تتمتع بخبرة سريرية عميقة في:

- التأهيل البصري (Low Vision Rehabilitation)
- التأهيل الوظيفي (Occupational Therapy for Visual Impairment)
- تقييم الوظائف البصرية (Visual Function Assessment)
- الأجهزة المساعدة البصرية (Assistive Devices & Optical Aids)
- التأهيل العصبي البصري (Neuro-Visual Rehabilitation)
- التوجه والتنقل (Orientation & Mobility - O&M)
- التدخل المبكر لضعف البصر عند الأطفال
- تأهيل ما بعد الجراحات البصرية (إزالة المياه البيضاء، زراعة القرنية، إلخ)
- التقنيات المساعدة والبرامج التكيفية

لديك معرفة شاملة بـ:
- التصنيف الدولي للأمراض (ICD-11) المتعلق بالبصر
- تصنيفات WHO لضعف البصر والعمى
- أحدث إرشادات الممارسة السريرية (Clinical Practice Guidelines)
- بروتوكولات التقييم: Colenbrander, Bailey-Lovie, MNREAD, Pepper VSRT
- مقاييس جودة الحياة: VFQ-25, LVQOL, IVI
</role>

<advanced_techniques>
لديك خبرة متقدمة في التقنيات التالية:

أ. التقنيات التعويضية (Compensatory):
   1. تدريب الرؤية اللامركزية (EVT) + Biofeedback مع MAIA/MP-3
   2. تدريب المسح البصري (Scanning Training) — Zihl, NeuroEyeCoach
   3. تدريب المسح السمعي-البصري (AViST)
   4. تأهيل حركات العين (Oculomotor) — Post-TBI
   5. علاج التكيف المنشوري (Prism Adaptation) — للإهمال البصري

ب. التقنيات البديلة (Substitutive):
   6. المناشير المحيطية (Fresnel, Peli 40PD, MPP)
   7. النظارات الذكية (eSight Go, IrisVision, OrCam MyEye 3)
   8. تطبيقات AI (Be My Eyes+GPT-4, Seeing AI)

ج. التقنيات الترميمية (Restorative — بحذر):
   9. علاج استعادة البصر (VRT) — مثير للجدل، مستوى دليل C
   10. التحفيز عبر الجمجمة (tDCS/tRNS) — تجريبي
   11. العلاج الجيني (Luxturna) — RPE65 فقط، مستوى دليل A
   12. الشبكية الاصطناعية — PRIMA/Orion (قيد التطوير)

د. تقنيات إضافية:
   13. التعلم الإدراكي (Perceptual Learning)
   14. التأهيل عن بعد (Telerehabilitation) — Bittner 2024 RCT
   15. تعديلات بيئية + وقاية من السقوط — Campbell 2005 RCT
   16. التوجه والتنقل المتقدم (O&M)

قواعد اختيار التقنية:
- المركزي (scotoma) → EVT/MBFT أولاً → تكبير → نظارات ذكية
- الشقي (hemianopia) مع إهمال → Prism Adaptation أولاً → scanning
- الشقي بدون إهمال → Scanning Training → Peli Prisms
- النفقي (tunnel vision) → scanning + O&M + تعديلات بيئية
- الترميمية: تُذكر كخيارات تجريبية فقط مع تصنيف الدليل
- دائماً: صنف مستوى الدليل (1a-5) لكل توصية
</advanced_techniques>

<behavioral_guidelines>
1. **المنهج السريري:**
   - ابدأ دائماً بفهم الحالة الكاملة قبل إعطاء أي توصية
   - اسأل عن: التشخيص، حدة الإبصار، المجال البصري، حساسية التباين، الوظائف اليومية المتأثرة
   - استخدم التفكير العميق (Extended Thinking) للحالات المعقدة
   - قدم توصيات مبنية على أدلة علمية مع ذكر المراجع

2. **البحث العلمي:**
   - عند الحاجة لمعلومات حديثة، استخدم أداة البحث في PubMed
   - ركز على: Systematic Reviews, Meta-analyses, RCTs, Clinical Guidelines
   - صنف مستوى الدليل (Level of Evidence) لكل توصية
   - لا تقدم معلومات غير موثقة كحقائق

3. **تحليل الصور:**
   - عند استلام صور طبية (تقارير فحص، OCT، Visual Fields، صور قاع العين)
   - حلل بمنهجية: الوصف → التفسير → الربط السريري → التوصيات
   - انتبه: أنت لا تقدم تشخيصاً نهائياً بل تحليلاً مساعداً يتطلب مراجعة الطبيب

4. **الخطط العلاجية:**
   - اتبع نموذج SMART Goals (Specific, Measurable, Achievable, Relevant, Time-bound)
   - قسم الخطة إلى: أهداف قصيرة/متوسطة/طويلة المدى
   - حدد: التقنيات، الأجهزة، التمارين، جدول المتابعة
   - اذكر معايير النجاح ومؤشرات التقدم

5. **التوثيق:**
   - لا تقم بتوثيق أو تلخيص أي معلومات إلا بعد موافقة صريحة من المستخدم
   - استخدم التنسيق الطبي المعياري (SOAP Notes, ICF Framework)
   - اذكر دائماً: "هذا ليس بديلاً عن الرأي الطبي المباشر"

6. **اللغة والتواصل:**
   - تحدث بالعربية بشكل افتراضي
   - استخدم المصطلحات الطبية مع شرحها بلغة بسيطة
   - كن دقيقاً ومهنياً مع الحفاظ على الدفء الإنساني
   - عند التواصل مع المريض: بسّط؛ مع المتخصص: استخدم المصطلحات الدقيقة
</behavioral_guidelines>

<proactive_intake>
عند تلقي أي رسالة تحتوي على __START_INTAKE__ :

ابدأ فوراً بمقابلة التقييم الاستهلالي. لا تشرح ولا تقدم نفسك بإسهاب.
اكتب تحية موجزة ودافئة (جملة واحدة) ثم اطرح السؤال الأول مباشرة.

تسلسل الأسئلة المحورية (اطرح سؤالاً واحداً في كل رسالة — انتظر الإجابة قبل السؤال التالي):

السؤال 1 — الشكوى الرئيسية:
"ما الذي يُضايقك أكثر في بصرك الآن؟ (مثال: صعوبة القراءة، التعرف على الوجوه، التنقل، استخدام الشاشة)"

السؤال 2 — القياسات الموضوعية (إذا لم تكن مسجّلة في ملف المريض):
"هل عندك قياس VA حديث؟ كم تُقدَّر بـ LogMAR أو كسر Snellen؟"

السؤال 3 — الأولوية الوظيفية:
"ما النشاط الذي تتمنى أن تستعيده أكثر من أي شيء؟"

السؤال 4 — الخبرة السابقة:
"هل جربت أجهزة مساعدة أو برامج تأهيل من قبل؟ كيف كانت التجربة؟"

بعد إجابة السؤال 4، انتقل فوراً إلى التحليل والتدخل (لا تسأل المزيد إلا إذا كانت هناك معلومة جوهرية ناقصة).

ملاحظة مهمة: إذا كانت بيانات المريض (VA، التشخيص، الأهداف) مسجّلة بالفعل في سياق المريض — تجاوز الأسئلة المتعلقة بها واستخدم ما هو مسجّل مباشرة.
</proactive_intake>

<intervention_delivery>
قاعدة ذهبية: لا تكتفِ بالتوصيات النظرية — قدّم دائماً نشاطاً قابلاً للتنفيذ الفوري.

بعد كل تحليل سريري، قدّم ثلاثة مستويات:

أ. 🎯 نشاط فوري (ابدأ الآن في هذه الجلسة):
   - استخدم أداة generate_visual_exercise لتوليد تمرين SVG مناسب للحالة
   - اختر النوع المناسب:
     * Hemianopia → scanning_grid (مع تحديد الجانب المتأثر)
     * AMD / Central Scotoma → fixation_cross
     * حساسية التباين → contrast_chart
     * القراءة → reading_ruler
     * حركات العين / Post-TBI → tracking_exercise
   - اشرح خطوات التمرين في 2-3 جمل
   - حدد المدة: 5-15 دقيقة

ب. 🏠 تمرين منزلي (كل يوم):
   - تمرين بسيط لا يحتاج أجهزة
   - حدد: كيف × كم مرة × كم أسبوع

ج. 📅 الخطوة التالية (الجلسة القادمة):
   - ما الذي يُقيَّم أو يُنفَّذ في الجلسة التالية

تذكير مهم: أداة generate_visual_exercise تنتج صورة SVG تفاعلية — استخدمها دائماً بدلاً من وصف التمرين نصياً فقط.
</intervention_delivery>

<safety_disclaimers>
- هذا النظام أداة مساعدة وليس بديلاً عن التشخيص أو العلاج الطبي المباشر
- جميع التوصيات تتطلب مراجعة من طبيب/أخصائي مؤهل
- في الحالات الطارئة، يجب التوجه فوراً لغرفة الطوارئ
- لا يتم تخزين بيانات المرضى الحساسة بدون تشفير وموافقة
</safety_disclaimers>
"""


# ═══════════════════════════════════════════════════════════════
# تعريف الأدوات (Tools)
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "search_pubmed",
        "description": """بحث في قاعدة بيانات PubMed للأبحاث الطبية.
        استخدم هذه الأداة عند الحاجة إلى:
        - أبحاث حديثة عن حالة أو علاج تأهيلي
        - إرشادات سريرية محدثة
        - مراجعات منهجية أو تحليلات تجميعية
        - بروتوكولات تأهيل بصري مبنية على أدلة
        ركز على: Systematic Reviews, RCTs, Clinical Guidelines""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "مصطلحات البحث بالإنجليزية (MeSH terms مفضلة)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "عدد النتائج المطلوبة (افتراضي: 10)",
                    "default": 10
                },
                "date_range": {
                    "type": "string",
                    "description": "نطاق التاريخ مثل: 2020:2026"
                },
                "article_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "أنواع المقالات: review, clinical-trial, meta-analysis, guideline"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_article_details",
        "description": """جلب التفاصيل الكاملة لمقال من PubMed عبر PMID.
        يشمل: العنوان، المؤلفون، الملخص، المجلة، DOI""",
        "input_schema": {
            "type": "object",
            "properties": {
                "pmid": {
                    "type": "string",
                    "description": "معرف PubMed للمقال (PMID)"
                }
            },
            "required": ["pmid"]
        }
    },
    {
        "name": "search_knowledge_base",
        "description": """بحث في القاعدة المعرفية المحلية للتأهيل البصري.
        تحتوي على: بروتوكولات، إرشادات سريرية، أدلة الأجهزة المساعدة،
        نماذج التقييم، خطط علاجية نموذجية""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "استعلام البحث"
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "protocols", "guidelines", "devices",
                        "assessments", "treatment_plans", "exercises"
                    ],
                    "description": "تصنيف المحتوى المطلوب"
                },
                "top_k": {
                    "type": "integer",
                    "description": "عدد النتائج الأكثر صلة",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "visual_calculator",
        "description": """حسابات بصرية متخصصة مثل:
        - تحويل حدة الإبصار بين المقاييس (Snellen, LogMAR, Decimal)
        - حساب قوة العدسة المكبرة المطلوبة
        - تقدير حجم الطباعة المناسب
        - حساب مسافة العمل المثالية""",
        "input_schema": {
            "type": "object",
            "properties": {
                "calculation_type": {
                    "type": "string",
                    "enum": [
                        "va_conversion",
                        "magnification_power",
                        "print_size",
                        "working_distance"
                    ]
                },
                "input_values": {
                    "type": "object",
                    "description": "القيم المدخلة حسب نوع الحساب"
                }
            },
            "required": ["calculation_type", "input_values"]
        }
    },
    {
        "name": "generate_document",
        "description": """إنشاء وثائق طبية منسقة. يتطلب موافقة مسبقة من المستخدم.
        الأنواع: تقرير تقييم، خطة علاجية، ملخص حالة، خطاب إحالة""",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "enum": [
                        "assessment_report",
                        "treatment_plan",
                        "case_summary",
                        "referral_letter",
                        "progress_note"
                    ]
                },
                "content": {
                    "type": "object",
                    "description": "محتوى الوثيقة المنظم"
                },
                "format": {
                    "type": "string",
                    "enum": ["markdown", "pdf", "docx"],
                    "default": "markdown"
                }
            },
            "required": ["document_type", "content"]
        }
    },
    {
        "name": "think",
        "description": """أداة للتوقف والتفكير المنظم أثناء تسلسل الاستدلال السريري.
        استخدم هذه الأداة عندما تحتاج:
        - مراجعة معلومات جديدة من أداة قبل اتخاذ القرار التالي
        - تقييم هل لديك معلومات كافية للتوصية
        - التحقق من اتساق البيانات مع التوصيات""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "تفكيرك واستدلالك السريري"
                }
            },
            "required": ["reasoning"]
        }
    },
    {
        "name": "functional_assessment",
        "description": """إجراء تقييم وظيفي شامل متعدد المراحل.
        يشمل: تاريخ المريض، حدة الإبصار، الوظائف اليومية، التقييم النفسي، التصنيف.
        المراحل: history, clinical_vision, functional, psychological, classification, full""",
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "enum": ["history", "clinical_vision", "functional", "psychological", "classification", "full"],
                    "description": "مرحلة التقييم المطلوبة"
                },
                "patient_data": {
                    "type": "object",
                    "description": "بيانات المريض (العمر، التشخيص، حدة الإبصار، إلخ)"
                }
            },
            "required": ["phase"]
        }
    },
    {
        "name": "device_recommender",
        "description": """التوصية بالأجهزة البصرية المساعدة المناسبة.
        يأخذ: حدة الإبصار، نوع فقدان المجال، المهام المطلوبة، العمر، الوضع الإدراكي.
        يعطي: توصيات رئيسية + ثانوية + تحذيرات + خطوات تالية""",
        "input_schema": {
            "type": "object",
            "properties": {
                "visual_acuity": {
                    "type": "string",
                    "description": "حدة الإبصار (مثل: 6/60, 0.1, CF)"
                },
                "field_type": {
                    "type": "string",
                    "enum": ["central_loss", "peripheral_loss", "full_field", "normal_field"],
                    "description": "نوع المجال البصري"
                },
                "task": {
                    "type": "string",
                    "description": "المهمة الرئيسية (reading, distance, daily_tasks, computer, mobility)"
                },
                "patient_age": {"type": "number"},
                "cognitive_status": {
                    "type": "string",
                    "enum": ["normal", "mild_impairment", "moderate_impairment"]
                },
                "hand_function": {
                    "type": "string",
                    "enum": ["normal", "limited", "severely_limited"]
                }
            },
            "required": ["visual_acuity"]
        }
    },
    {
        "name": "arabic_reading_calculator",
        "description": """حسابات القراءة العربية المتخصصة.
        يحسب: حجم الطباعة الأمثل، التكبير المطلوب، مسافة العمل، سرعة القراءة،
        ومتطلبات القرآن الكريم والنصوص المشكّلة.
        أنواع الحسابات: optimal_print_size, magnification_needed, working_distance,
        reading_speed_estimation, quran_requirements, full_arabic_assessment""",
        "input_schema": {
            "type": "object",
            "properties": {
                "calculation_type": {
                    "type": "string",
                    "enum": [
                        "optimal_print_size", "magnification_needed", "working_distance",
                        "reading_speed_estimation", "quran_requirements", "full_arabic_assessment"
                    ]
                },
                "visual_acuity": {
                    "type": "string",
                    "description": "حدة الإبصار"
                },
                "text_type": {
                    "type": "string",
                    "enum": ["plain", "diacritical", "quran", "mixed", "handwriting"],
                    "description": "نوع النص العربي"
                },
                "patient_age": {"type": ["string", "number"]}
            },
            "required": ["visual_acuity"]
        }
    },
    {
        "name": "depression_screening",
        "description": """فحص الاكتئاب والحالة النفسية لمرضى ضعف البصر.
        الأدوات: PHQ-2 (فحص سريع), PHQ-9 (تقييم كامل), GDS-15 (للمسنين +65),
        adjustment_assessment (مرحلة التكيف مع فقدان البصر), full_psychological (شامل).
        ⚠️ أي درجة في Q9 (أفكار انتحارية) تستوجب تنبيهاً فورياً""",
        "input_schema": {
            "type": "object",
            "properties": {
                "screening_type": {
                    "type": "string",
                    "enum": ["phq2", "phq9", "gds15", "adjustment_assessment", "full_psychological"]
                },
                "scores": {
                    "type": "object",
                    "description": "درجات الأسئلة (q1: 0-3, q2: 0-3, ...)"
                },
                "patient_age": {"type": ["string", "number"]},
                "months_since_diagnosis": {"type": "number"}
            },
            "required": ["screening_type"]
        }
    },
    {
        "name": "outcome_tracker",
        "description": """تتبع وقياس نتائج التأهيل البصري عبر الزمن.
        الإجراءات: record_assessment, compare_progress, calculate_gas (Goal Attainment Scale),
        calculate_vfq25, generate_report, set_smart_goals.
        يقيس: حدة الإبصار، سرعة القراءة، PHQ-9، VFQ-25، استقلالية الأنشطة اليومية""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "record_assessment", "compare_progress", "calculate_gas",
                        "calculate_vfq25", "generate_report", "set_smart_goals"
                    ]
                },
                "baseline": {
                    "type": "object",
                    "description": "بيانات التقييم الأولي"
                },
                "current": {
                    "type": "object",
                    "description": "بيانات التقييم الحالي"
                },
                "goals": {
                    "type": "array",
                    "description": "قائمة الأهداف لحساب GAS"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "referral_generator",
        "description": """توليد خطابات إحالة احترافية لـ 13 تخصصاً طبياً.
        التخصصات: ophthalmology, neurology, psychiatry, psychology, pediatrics,
        occupational_therapy, orientation_mobility, social_work, optometry,
        special_education, endocrinology, geriatrics, neurosurgery.
        الإجراءات: recommend_referrals, generate_letter, generate_all_needed""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["recommend_referrals", "generate_letter", "generate_all_needed"]
                },
                "specialty": {
                    "type": "string",
                    "description": "التخصص المُحال إليه (لـ generate_letter)"
                },
                "patient_name": {"type": "string"},
                "patient_age": {"type": ["string", "number"]},
                "diagnosis": {"type": "string"},
                "va_better_eye": {"type": "string"},
                "clinical_flags": {
                    "type": "object",
                    "description": "علامات سريرية لتحديد الإحالات المناسبة"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["emergency", "urgent", "routine", "elective"]
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "technique_recommender",
        "description": """محرك التوصية بتقنيات التأهيل البصري المتقدمة.
        يحلل نمط الفقد البصري والتشخيص وحدة الإبصار ويوصي بالتقنيات المناسبة.
        يغطي 25+ تقنية: EVT, Scanning, AViST, Oculomotor, Prism Adaptation,
        النظارات الذكية, المناشير, VRT, tDCS, العلاج الجيني, التعلم الإدراكي, التأهيل عن بعد.
        الإجراءات: recommend, detail, compare, protocol, list""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["recommend", "detail", "compare", "protocol", "list"]
                },
                "vision_loss_pattern": {
                    "type": "string",
                    "enum": [
                        "central_scotoma", "hemianopia_right", "hemianopia_left",
                        "hemianopia_with_neglect", "quadrantanopia", "tunnel_vision",
                        "general_reduction", "visual_neglect", "oculomotor_dysfunction",
                        "cvi", "nystagmus", "total_blindness", "mixed"
                    ],
                    "description": "نمط الفقد البصري"
                },
                "primary_diagnosis": {"type": "string"},
                "visual_acuity": {"type": "string"},
                "patient_age": {"type": "number"},
                "cognitive_status": {
                    "type": "string",
                    "enum": ["normal", "mild_impairment", "moderate_impairment", "severe_impairment"]
                },
                "available_equipment": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "setting": {
                    "type": "string",
                    "enum": ["clinic", "home", "hybrid", "telerehab"]
                },
                "technique_id": {"type": "string"},
                "technique_ids": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "prior_rehabilitation": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "تقنيات تأهيل سابقة جربها المريض (لتجنب التكرار)"
                },
                "conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "حالات/موانع طبية (مثل: seizure_disorder, nystagmus)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "perceptual_learning_planner",
        "description": """مخطط جلسات التعلم الإدراكي.
        يولد بروتوكولات مخصصة لـ: Gabor patches (حساسية التباين),
        Lateral masking, Crowding reduction, Motion perception.
        الإجراءات: generate, list, track_progress""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["generate", "list", "track_progress"]
                },
                "task_type": {
                    "type": "string",
                    "enum": ["contrast_detection", "lateral_masking", "crowding_reduction", "motion_perception"]
                },
                "visual_acuity": {"type": "string"},
                "patient_age": {"type": "number"},
                "diagnosis": {"type": "string"},
                "sessions_completed": {"type": "number"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "environmental_assessment",
        "description": """تقييم البيئة المنزلية/العمل/المدرسة لمرضى ضعف البصر.
        يشمل: تقييم الإضاءة، التباين، السلامة، الوقاية من السقوط.
        مبني على Campbell 2005 RCT (تقليل السقوط 41%).
        الإجراءات: assess_home, assess_workplace, assess_school, fall_prevention""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["assess_home", "assess_workplace", "assess_school", "fall_prevention"]
                },
                "visual_acuity": {"type": "string"},
                "field_type": {"type": "string"},
                "patient_age": {"type": "number"},
                "fall_count_12months": {"type": "number"},
                "mobility_level": {
                    "type": "string",
                    "enum": ["independent", "assisted", "wheelchair"]
                },
                "job_type": {"type": "string"},
                "grade_level": {"type": "string"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "telerehab_session_manager",
        "description": """إدارة جلسات التأهيل البصري عن بعد.
        تخطيط الجلسات + فحص الجاهزية التقنية + خطة علاج كاملة.
        مبني على Bittner 2024 RCT (التأهيل عن بعد مكافئ للحضوري).
        الإجراءات: plan_session, check_readiness, treatment_plan, list_types""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["plan_session", "check_readiness", "treatment_plan", "list_types"]
                },
                "session_type": {
                    "type": "string",
                    "enum": [
                        "initial_assessment", "device_training", "evt_remote",
                        "scanning_remote", "psychological_support", "follow_up"
                    ]
                },
                "patient_tech_literacy": {
                    "type": "string",
                    "enum": ["low", "moderate", "high"]
                },
                "patient_age": {"type": "number"},
                "caregiver_available": {"type": "boolean"},
                "total_sessions": {"type": "number"},
                "primary_goal": {"type": "string"},
                "diagnosis": {"type": "string"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "cdss_evaluate",
        "description": """محرك القرار السريري المتكامل (CDSS) — يقبل بيانات FHIR أو يدوية.
        يُجري تقييماً سريرياً شاملاً بناءً على قواعد YAML مع:
        - حواجز أمان (Guardrails): كشف التناقضات قبل التقييم
        - مبررات (XAI): سبب كل توصية بأرقام المريض الحقيقية
        - FHIR: يقبل حزم HL7 FHIR R4 مباشرةً من أنظمة المستشفيات
        - تتبع النتائج: يتعلم من نتائج المريض السابقة
        input_type: "fhir" | "manual" | "log_outcome" | "get_history"
        يعمل بالتوازي مع الأدوات الأخرى — استخدمه عند:
        1. استلام بيانات FHIR من نظام مستشفى
        2. طلب تقييم شامل مع مبررات تفصيلية
        3. تسجيل نتيجة تقنية لمريض""",
        "input_schema": {
            "type": "object",
            "properties": {
                "input_type": {
                    "type": "string",
                    "enum": ["fhir", "manual", "log_outcome", "get_history"],
                    "description": "نوع الإدخال"
                },
                "fhir_bundle": {
                    "type": "object",
                    "description": "حزمة FHIR R4 Bundle (عند input_type=fhir)"
                },
                "patient_data": {
                    "type": "object",
                    "description": "بيانات المريض اليدوية (عند input_type=manual)",
                    "properties": {
                        "diagnosis": {"type": "string"},
                        "icd10_codes": {"type": "array", "items": {"type": "string"}},
                        "vision_pattern": {"type": "string"},
                        "va_logmar": {"type": "number"},
                        "va_decimal": {"type": "number"},
                        "phq9_score": {"type": "number"},
                        "age": {"type": "number"},
                        "cognitive_status": {"type": "string"},
                        "functional_goals": {"type": "array", "items": {"type": "string"}},
                        "equipment_available": {"type": "array", "items": {"type": "string"}},
                        "setting": {"type": "string"}
                    }
                },
                "patient_id": {
                    "type": "string",
                    "description": "معرف المريض (اختياري، لتتبع النتائج)"
                },
                "language": {
                    "type": "string",
                    "enum": ["ar", "en"],
                    "description": "لغة التقرير"
                },
                "technique_id": {
                    "type": "string",
                    "description": "معرف التقنية (عند input_type=log_outcome)"
                },
                "outcome": {
                    "type": "object",
                    "description": "نتيجة التقنية (عند input_type=log_outcome)"
                }
            },
            "required": ["input_type"]
        }
    },
    {
        "name": "clinical_assessment",
        "description": "تقييمات سريرية رقمية — Digital Biomarkers: 1) fixation: تحليل ثبات التثبيت BCEA + PRL من إحداثيات تتبع العين. 2) reading: محلل سرعة القراءة الرقمي MNREAD (MRS, CPS, RA). 3) visual_search: اختبار شطب رقمي لتقييم الإهمال البصري وقدرة المسح. 4) contrast: تقييم حساسية التباين Pelli-Robson أو Staircase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assessment_type": {
                    "type": "string",
                    "enum": ["fixation", "reading", "visual_search", "contrast"],
                    "description": "نوع التقييم"
                },
                "action": {
                    "type": "string",
                    "description": "الإجراء المطلوب (يعتمد على نوع التقييم)"
                },
                "x_coords": {"type": "array", "items": {"type": "number"}, "description": "إحداثيات X لتتبع العين (fixation)"},
                "y_coords": {"type": "array", "items": {"type": "number"}, "description": "إحداثيات Y لتتبع العين (fixation)"},
                "session1_x": {"type": "array", "items": {"type": "number"}},
                "session1_y": {"type": "array", "items": {"type": "number"}},
                "session2_x": {"type": "array", "items": {"type": "number"}},
                "session2_y": {"type": "array", "items": {"type": "number"}},
                "readings": {"type": "array", "description": "قراءات MNREAD: [{print_size_logmar, reading_time_seconds, word_errors}]"},
                "responses": {"type": "array", "description": "استجابات اختبار التباين"},
                "method": {"type": "string", "description": "طريقة اختبار التباين: pelli_robson أو staircase"},
                "difficulty": {"type": "integer", "description": "مستوى صعوبة المسح البصري (1-5)"},
                "target_count": {"type": "integer", "description": "عدد الأهداف في المسح البصري"}
            },
            "required": ["assessment_type"]
        }
    },
    {
        "name": "clinical_intervention",
        "description": "تدخلات علاجية رقمية نشطة: 1) scanning: مدرب المسح البصري التكيّفي لمرضى Hemianopia (خوارزمية 1-up 2-down). 2) perceptual_learning: التعلم الإدراكي بمحفزات Gabor Patch لتحسين حساسية التباين. 3) visual_augmentation: تعزيز بصري AR (CLAHE + حواف لمرضى الجلوكوما، تكبير AMD، محاكاة العتمة). 4) device_routing: توجيه ذكي للمعدات المساعدة مع حواجز أمان.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intervention_type": {
                    "type": "string",
                    "enum": ["scanning", "perceptual_learning", "visual_augmentation", "device_routing"],
                    "description": "نوع التدخل"
                },
                "action": {"type": "string", "description": "الإجراء: generate_stimulus, process_response, simulate_session, demo, etc."},
                "blind_side": {"type": "string", "enum": ["right", "left"], "description": "الجانب الأعمى (scanning)"},
                "difficulty": {"type": "integer", "description": "مستوى الصعوبة (1-10)"},
                "num_trials": {"type": "integer", "description": "عدد المحاولات للمحاكاة"},
                "starting_contrast": {"type": "number", "description": "تباين البداية (perceptual_learning)"},
                "spatial_frequency": {"type": "number", "description": "التردد المكاني cpd"},
                "va_logmar": {"type": "number", "description": "حدة الإبصار LogMAR (device_routing)"},
                "visual_field_degrees": {"type": "number", "description": "مجال الرؤية بالدرجات"},
                "has_cognitive_decline": {"type": "boolean"},
                "functional_goals": {"type": "array", "items": {"type": "string"}},
                "budget_usd": {"type": "number"},
                "setting": {"type": "string"},
                "scotoma_type": {"type": "string", "enum": ["central", "hemianopia_right", "hemianopia_left", "tunnel"]}
            },
            "required": ["intervention_type"]
        }
    },
    {
        "name": "generate_visual_exercise",
        "description": """توليد تمرين بصري علاجي كصورة SVG تفاعلية مضمّنة في المحادثة.
        استخدم هذه الأداة دائماً عند الحاجة إلى تقديم نشاط بصري للمريض:
        - scanning_grid: شبكة مسح بصري لمرضى Hemianopia أو Tunnel Vision
        - fixation_cross: صليب تثبيت + دوائر PRL للإبصار اللامركزي (AMD / Central Scotoma)
        - contrast_chart: لوحة حساسية التباين المتدرجة (Contrast Sensitivity)
        - reading_ruler: مسطرة قراءة (Typoscope) بنص عربي تدريبي
        - tracking_exercise: مسار تتبع بصري منحنى (Post-TBI / Oculomotor Rehab)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "exercise_type": {
                    "type": "string",
                    "enum": ["scanning_grid", "fixation_cross", "contrast_chart",
                             "reading_ruler", "tracking_exercise"],
                    "description": "نوع التمرين"
                },
                "difficulty": {
                    "type": "integer", "minimum": 1, "maximum": 5,
                    "description": "مستوى الصعوبة 1-5 (1=أسهل، 5=أصعب)"
                },
                "side": {
                    "type": "string", "enum": ["left", "right", "both"],
                    "description": "الجانب المتأثر (للـ Hemianopia: left أو right)"
                },
                "title": {
                    "type": "string",
                    "description": "عنوان التمرين بالعربية (يُعرض للمريض)"
                },
                "instructions": {
                    "type": "string",
                    "description": "تعليمات التمرين بالعربية (1-2 جملة)"
                }
            },
            "required": ["exercise_type"]
        }
    },
    {
        "name": "patient_database",
        "description": """الوصول إلى قاعدة بيانات المرضى — البحث واسترجاع البيانات السريرية.
        استخدم هذه الأداة عند الحاجة إلى:
        - البحث عن مريض برقم الملف أو الاسم أو التشخيص
        - استرجاع بيانات مريض كاملة أو ملخصة
        - عرض قائمة جميع المرضى
        - مقارنة بيانات مريضين
        - استرجاع تاريخ التقييمات أو الجلسات لمريض

        الإجراءات المتاحة (action):
        - search: بحث بنص حر (اسم، تشخيص، ICD-10، رقم ملف)
        - get_by_file_number: استرجاع مريض برقم الملف
        - get_by_id: استرجاع مريض بالمعرف الفريد
        - list_all: قائمة ملخصة لجميع المرضى
        - get_assessments: استرجاع تقييمات مريض
        - get_interventions: استرجاع جلسات مريض
        - get_notes: استرجاع ملاحظات مريض""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "get_by_file_number", "get_by_id", "list_all",
                             "get_assessments", "get_interventions", "get_notes"],
                    "description": "نوع العملية"
                },
                "query": {
                    "type": "string",
                    "description": "نص البحث (للبحث بالاسم/التشخيص/ICD-10/رقم الملف)"
                },
                "file_number": {
                    "type": "integer",
                    "description": "رقم ملف المريض (مثال: 1, 2, 3...)"
                },
                "patient_id": {
                    "type": "string",
                    "description": "معرف المريض الفريد (مثال: VR-2026-0001)"
                }
            },
            "required": ["action"]
        }
    }
]


# ═══════════════════════════════════════════════════════════════
# قاعدة بيانات المرضى — Patient Database Query Engine
# ═══════════════════════════════════════════════════════════════

def query_patient_database(params: dict) -> dict:
    """
    محرك استعلام قاعدة بيانات المرضى — يتيح للذكاء الاصطناعي
    البحث والوصول لملفات المرضى بأمان
    """
    # Import here to avoid circular imports
    import sys
    import os as _os
    _patients_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "patients")

    def _load_all():
        patients = {}
        if _os.path.exists(_patients_dir):
            for fname in sorted(_os.listdir(_patients_dir)):
                if fname.endswith(".json"):
                    path = _os.path.join(_patients_dir, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            p = json.load(f)
                            patients[p["id"]] = p
                    except (json.JSONDecodeError, KeyError):
                        pass
        return patients

    def _summary(p):
        """ملخص مريض بدون محادثات"""
        return {
            "id": p.get("id"), "file_number": p.get("file_number"),
            "name": p.get("name"), "age": p.get("age"), "gender": p.get("gender"),
            "diagnosis_text": p.get("diagnosis_text"),
            "diagnosis_icd10": p.get("diagnosis_icd10", []),
            "va_logmar": p.get("va_logmar"), "va_snellen": p.get("va_snellen"),
            "visual_field_degrees": p.get("visual_field_degrees"),
            "vision_pattern": p.get("vision_pattern"),
            "cognitive_status": p.get("cognitive_status"),
            "functional_goals": p.get("functional_goals", []),
            "phq9_score": p.get("phq9_score"),
            "num_assessments": len(p.get("assessment_results", [])),
            "num_interventions": len(p.get("intervention_sessions", [])),
            "num_notes": len(p.get("notes", [])),
            "num_cdss": len(p.get("cdss_evaluations", [])),
            "created_at": p.get("created_at"), "updated_at": p.get("updated_at"),
        }

    action = params.get("action", "")

    if action == "list_all":
        patients = _load_all()
        if not patients:
            return {"status": "empty", "message": "لا يوجد مرضى مسجلون", "patients": [], "count": 0}
        summaries = [_summary(p) for p in patients.values()]
        summaries.sort(key=lambda x: x.get("file_number") or 0)
        return {"status": "ok", "count": len(summaries), "patients": summaries}

    elif action == "search":
        query = params.get("query", "").strip()
        if not query:
            return {"error": "يرجى تحديد نص البحث (query)"}
        patients = _load_all()
        results = []
        q = query.lower()
        for pid, p in patients.items():
            match = False
            # بحث برقم الملف
            if q.isdigit() and p.get("file_number") == int(q):
                match = True
            # بحث بالمعرف
            elif q in pid.lower():
                match = True
            # بحث بالاسم
            elif q in p.get("name", "").lower() or q in p.get("name_en", "").lower():
                match = True
            # بحث بالتشخيص
            elif q in p.get("diagnosis_text", "").lower():
                match = True
            # بحث بـ ICD-10
            elif any(q in icd.lower() for icd in p.get("diagnosis_icd10", [])):
                match = True
            if match:
                results.append(_summary(p))
        return {"status": "ok", "query": query, "count": len(results), "results": results}

    elif action == "get_by_file_number":
        fnum = params.get("file_number")
        if fnum is None:
            return {"error": "يرجى تحديد رقم الملف (file_number)"}
        patients = _load_all()
        for p in patients.values():
            if p.get("file_number") == int(fnum):
                result = _summary(p)
                # إضافة آخر الملاحظات والتقييمات
                result["recent_notes"] = [
                    {"type": n.get("type"), "content": n.get("content", "")[:150], "timestamp": n.get("timestamp")}
                    for n in p.get("notes", [])[-5:]
                ]
                result["recent_assessments"] = [
                    {"type": a.get("type"), "timestamp": a.get("timestamp"),
                     "result_summary": {k: v for k, v in a.get("result", {}).items() if not isinstance(v, (list, dict))}
                    }
                    for a in p.get("assessment_results", [])[-5:]
                ]
                result["recent_interventions"] = [
                    {"type": s.get("type"), "timestamp": s.get("timestamp")}
                    for s in p.get("intervention_sessions", [])[-5:]
                ]
                return {"status": "ok", "patient": result}
        return {"status": "not_found", "message": f"لم يُعثر على مريض برقم ملف {fnum}"}

    elif action == "get_by_id":
        patient_id = params.get("patient_id", "").strip()
        if not patient_id:
            return {"error": "يرجى تحديد معرف المريض (patient_id)"}
        patients = _load_all()
        p = patients.get(patient_id)
        if not p:
            return {"status": "not_found", "message": f"لم يُعثر على مريض بمعرف {patient_id}"}
        result = _summary(p)
        result["recent_notes"] = [
            {"type": n.get("type"), "content": n.get("content", "")[:150], "timestamp": n.get("timestamp")}
            for n in p.get("notes", [])[-5:]
        ]
        return {"status": "ok", "patient": result}

    elif action == "get_assessments":
        fnum = params.get("file_number")
        patient_id = params.get("patient_id", "").strip()
        patients = _load_all()
        target = None
        if fnum is not None:
            for p in patients.values():
                if p.get("file_number") == int(fnum):
                    target = p
                    break
        elif patient_id:
            target = patients.get(patient_id)
        if not target:
            return {"status": "not_found", "message": "لم يُعثر على المريض"}
        assessments = target.get("assessment_results", [])
        return {
            "status": "ok",
            "patient_id": target["id"], "file_number": target.get("file_number"),
            "patient_name": target.get("name"),
            "total": len(assessments),
            "assessments": [
                {"type": a.get("type"), "timestamp": a.get("timestamp"), "result": a.get("result", {})}
                for a in assessments
            ]
        }

    elif action == "get_interventions":
        fnum = params.get("file_number")
        patient_id = params.get("patient_id", "").strip()
        patients = _load_all()
        target = None
        if fnum is not None:
            for p in patients.values():
                if p.get("file_number") == int(fnum):
                    target = p
                    break
        elif patient_id:
            target = patients.get(patient_id)
        if not target:
            return {"status": "not_found", "message": "لم يُعثر على المريض"}
        sessions = target.get("intervention_sessions", [])
        return {
            "status": "ok",
            "patient_id": target["id"], "file_number": target.get("file_number"),
            "patient_name": target.get("name"),
            "total": len(sessions),
            "interventions": [
                {"type": s.get("type"), "timestamp": s.get("timestamp"), "result": s.get("result", {})}
                for s in sessions
            ]
        }

    elif action == "get_notes":
        fnum = params.get("file_number")
        patient_id = params.get("patient_id", "").strip()
        patients = _load_all()
        target = None
        if fnum is not None:
            for p in patients.values():
                if p.get("file_number") == int(fnum):
                    target = p
                    break
        elif patient_id:
            target = patients.get(patient_id)
        if not target:
            return {"status": "not_found", "message": "لم يُعثر على المريض"}
        notes = target.get("notes", [])
        return {
            "status": "ok",
            "patient_id": target["id"], "file_number": target.get("file_number"),
            "patient_name": target.get("name"),
            "total": len(notes),
            "notes": notes
        }

    else:
        return {"error": f"إجراء غير معروف: {action}. الإجراءات المتاحة: search, get_by_file_number, get_by_id, list_all, get_assessments, get_interventions, get_notes"}


# ═══════════════════════════════════════════════════════════════
# منفذ الأدوات
# ═══════════════════════════════════════════════════════════════

def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """تنفيذ الأداة المطلوبة وإرجاع نتيجتها"""

    try:
        if tool_name == "search_pubmed":
            return search_pubmed_api(tool_input)

        elif tool_name == "fetch_article_details":
            return fetch_pubmed_article(tool_input["pmid"])

        elif tool_name == "search_knowledge_base":
            return search_vector_db(tool_input)

        elif tool_name == "visual_calculator":
            return calculate_visual_params(tool_input)

        elif tool_name == "generate_document":
            return generate_medical_document(tool_input)

        elif tool_name == "think":
            # أداة التفكير — لا تنفذ شيئاً، Claude يستخدمها داخلياً
            return {"status": "thinking_complete", "reasoning_logged": True}

        elif tool_name == "functional_assessment":
            return run_functional_assessment(tool_input)

        elif tool_name == "device_recommender":
            return recommend_devices(tool_input)

        elif tool_name == "arabic_reading_calculator":
            return calculate_arabic_reading_params(tool_input)

        elif tool_name == "depression_screening":
            return run_depression_screening(tool_input)

        elif tool_name == "outcome_tracker":
            return track_rehabilitation_outcomes(tool_input)

        elif tool_name == "referral_generator":
            return generate_referral(tool_input)

        elif tool_name == "technique_recommender":
            return recommend_techniques(tool_input)

        elif tool_name == "perceptual_learning_planner":
            return plan_perceptual_learning(tool_input)

        elif tool_name == "environmental_assessment":
            return assess_environment(tool_input)

        elif tool_name == "telerehab_session_manager":
            return manage_telerehab_session(tool_input)

        elif tool_name == "cdss_evaluate":
            return run_cdss_evaluation(tool_input)

        elif tool_name == "clinical_assessment":
            return run_assessment(tool_input)

        elif tool_name == "clinical_intervention":
            return run_intervention(tool_input)

        elif tool_name == "patient_database":
            return query_patient_database(tool_input)

        elif tool_name == "generate_visual_exercise":
            from tools.visual_exercises import generate_visual_exercise
            return generate_visual_exercise(tool_input)

        else:
            return {"error": f"أداة غير معروفة: {tool_name}"}

    except Exception as e:
        return {"error": f"خطأ في تنفيذ {tool_name}: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# استخراج النص من الاستجابة
# ═══════════════════════════════════════════════════════════════

def extract_text_response(response) -> str:
    """استخراج النص من استجابة Claude"""
    text_parts = []
    for block in response.content:
        if hasattr(block, "type"):
            if block.type == "text":
                text_parts.append(block.text)
    return "\n".join(text_parts)


# ═══════════════════════════════════════════════════════════════
# الحلقة الرئيسية مع Tool Use
# ═══════════════════════════════════════════════════════════════

def run_rehab_consultant(
    user_message: str,
    images: Optional[list] = None,
    use_extended_thinking: bool = True,
    thinking_budget: int = 10000
) -> str:
    """
    حلقة المحادثة الرئيسية مع دعم الأدوات والتفكير العميق

    Args:
        user_message: رسالة المستخدم
        images: قائمة الصور [{media_type, data}] (اختيارية)
        use_extended_thinking: تفعيل Extended Thinking
        thinking_budget: حد رموز التفكير (افتراضي: 10000)

    Returns:
        نص الاستجابة النهائية
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # تنظيف المدخلات
    user_message = sanitize_patient_input(user_message)

    # بناء المحتوى (نص + صور اختيارية)
    content = []

    # الصور أولاً (أداء أفضل)
    if images:
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["data"]
                }
            })

    content.append({"type": "text", "text": user_message})

    messages = [{"role": "user", "content": content}]

    # إعداد معاملات الـ API
    api_params = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 16384,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": messages
    }

    if use_extended_thinking:
        api_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget
        }

    # حلقة Tool Use
    while True:
        response = client.messages.create(**api_params)

        # توقف بدون طلب أداة → نُرجع الجواب
        if response.stop_reason == "end_turn":
            result = extract_text_response(response)
            return validate_medical_output(result)

        # طلب استخدام أداة
        if response.stop_reason == "tool_use":
            # أضف رد Claude الحالي للمحادثة
            messages.append({"role": "assistant", "content": response.content})

            # نفّذ كل أداة مطلوبة
            tool_results = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            # أرسل النتائج لـ Claude
            messages.append({"role": "user", "content": tool_results})
            api_params["messages"] = messages

        else:
            # stop_reason غير متوقع
            return extract_text_response(response)


# ═══════════════════════════════════════════════════════════════
# تحليل الصور الطبية
# ═══════════════════════════════════════════════════════════════

def analyze_medical_image(image_path: str, clinical_question: str) -> str:
    """
    تحليل صورة طبية مع سياق سريري

    Args:
        image_path: مسار ملف الصورة
        clinical_question: السؤال السريري المرتبط بالصورة

    Returns:
        التحليل السريري
    """
    # قراءة وترميز الصورة
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # تحديد نوع الملف
    if image_path.lower().endswith(".png"):
        media_type = "image/png"
    elif image_path.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif image_path.lower().endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"

    analysis_prompt = f"""
حلل هذه الصورة الطبية بمنهجية:

1. **الوصف:** ما الذي تراه في الصورة؟ (نوع الفحص، القراءات، الملاحظات)
2. **التفسير:** ما الدلالة السريرية للنتائج الظاهرة؟
3. **الربط السريري:** {clinical_question}
4. **التوصيات:** ما الخطوات التالية المقترحة؟

⚠️ تذكر: هذا تحليل مساعد وليس تشخيصاً نهائياً.
"""

    return run_rehab_consultant(
        user_message=analysis_prompt,
        images=[{"media_type": media_type, "data": image_data}],
        use_extended_thinking=True,
        thinking_budget=8000
    )


# ═══════════════════════════════════════════════════════════════
# واجهة المحادثة التفاعلية
# ═══════════════════════════════════════════════════════════════

def interactive_session():
    """جلسة محادثة تفاعلية مع المستشار"""
    print("=" * 60)
    print("🏥 مستشار التأهيل الذكي — Vision Rehabilitation AI")
    print("=" * 60)
    print("اكتب سؤالك أو وصف الحالة. اكتب 'خروج' للإنهاء.")
    print("-" * 60)

    while True:
        user_input = input("\n👤 أنت: ").strip()

        if user_input.lower() in ["خروج", "exit", "quit"]:
            print("👋 شكراً لاستخدام المستشار. مع السلامة.")
            break

        if not user_input:
            continue

        print("\n🤖 المستشار: (يفكر...)\n")
        try:
            response = run_rehab_consultant(user_input)
            print(f"🤖 المستشار:\n{response}")
        except Exception as e:
            print(f"❌ خطأ: {e}")


if __name__ == "__main__":
    interactive_session()
