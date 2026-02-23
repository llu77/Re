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
from utils.security import sanitize_patient_input, validate_medical_output


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
    }
]


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
