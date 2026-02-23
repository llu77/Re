"""
أمثلة تطبيقية — Rehabilitation AI Consultant
=============================================
أمثلة عملية لاستخدام النظام في حالات مختلفة

⚠️ متطلبات التشغيل:
    export ANTHROPIC_API_KEY="sk-ant-..."
    export NCBI_API_KEY="your-ncbi-key"  (اختياري لـ PubMed)
    pip install -r requirements.txt
"""

import os
import sys


def check_api_key():
    """التحقق من توفر API Key"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ خطأ: ANTHROPIC_API_KEY غير مُعيَّن")
        print("قم بتعيينه: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    print("✅ ANTHROPIC_API_KEY متوفر")

    if not os.environ.get("NCBI_API_KEY"):
        print("⚠️ تحذير: NCBI_API_KEY غير مُعيَّن — البحث في PubMed سيعمل بحد 3 طلبات/ثانية")
    else:
        print("✅ NCBI_API_KEY متوفر")


# ═══════════════════════════════════════════════════════════════
# مثال 1: سؤال بسيط عن حالة
# ═══════════════════════════════════════════════════════════════

def example_simple_consultation():
    """استشارة بسيطة عن حالة AMD"""
    print("\n" + "=" * 60)
    print("مثال 1: استشارة حالة ضمور بقعي")
    print("=" * 60)

    from rehab_consultant import run_rehab_consultant

    user_query = """
لدي مريضة عمرها 72 سنة مصابة بالضمور البقعي الجاف (Dry AMD) في كلتا العينين.

العين اليمنى: 6/60 (LogMAR 1.0)
العين اليسرى: 6/36 (LogMAR 0.78)
المجال البصري: سليم محيطياً مع scotoma مركزي ثنائي

الشكوى الرئيسية: صعوبة القراءة وتمييز الوجوه
الأهداف: الاستمرار في قراءة القرآن والطبخ والتنقل المستقل

ما الأجهزة المساعدة المناسبة لها؟
"""

    print("إرسال الاستفسار... (قد يستغرق دقيقة)")
    response = run_rehab_consultant(user_query, use_extended_thinking=True)
    print("\n📋 الاستجابة:")
    print(response)


# ═══════════════════════════════════════════════════════════════
# مثال 2: الحاسبة البصرية (لا يحتاج API)
# ═══════════════════════════════════════════════════════════════

def example_visual_calculator():
    """أمثلة على الحسابات البصرية"""
    print("\n" + "=" * 60)
    print("مثال 2: الحاسبة البصرية")
    print("=" * 60)

    from tools.calculator import calculate_visual_params

    # تحويل حدة الإبصار
    print("\n📊 تحويل حدة الإبصار 6/60:")
    result = calculate_visual_params({
        "calculation_type": "va_conversion",
        "input_values": {
            "from_format": "snellen_metric",
            "value": "6/60"
        }
    })
    _print_result(result)

    # حساب قوة المكبر
    print("\n🔍 حساب قوة المكبر للقراءة (VA = 0.1):")
    result = calculate_visual_params({
        "calculation_type": "magnification_power",
        "input_values": {
            "visual_acuity_decimal": 0.1,
            "target_print_size_N": 8,
            "reading_distance_cm": 40
        }
    })
    _print_result(result)

    # تقدير حجم الطباعة
    print("\n📄 تقدير حجم الطباعة المناسب (VA = 0.05):")
    result = calculate_visual_params({
        "calculation_type": "print_size",
        "input_values": {
            "visual_acuity_decimal": 0.05,
            "reading_distance_cm": 40
        }
    })
    _print_result(result)

    # مسافة العمل مع العدسة
    print("\n📏 مسافة العمل مع عدسة 10D:")
    result = calculate_visual_params({
        "calculation_type": "working_distance",
        "input_values": {"lens_power_diopter": 10}
    })
    _print_result(result)


# ═══════════════════════════════════════════════════════════════
# مثال 3: البحث في القاعدة المعرفية (لا يحتاج API)
# ═══════════════════════════════════════════════════════════════

def example_knowledge_base_search():
    """البحث في القاعدة المعرفية المحلية"""
    print("\n" + "=" * 60)
    print("مثال 3: البحث في القاعدة المعرفية")
    print("=" * 60)

    from tools.knowledge_base import search_vector_db

    # بحث عن بروتوكول AMD
    print("\n🔍 البحث عن بروتوكول تأهيل الضمور البقعي:")
    result = search_vector_db({
        "query": "AMD ضمور بقعي تأهيل PRL مكبرات",
        "top_k": 2
    })
    _print_result(result, truncate=True)

    # بحث في فئة الأجهزة
    print("\n🔧 البحث عن الأجهزة المساعدة:")
    result = search_vector_db({
        "query": "CCTV مكبر إلكتروني",
        "category": "devices",
        "top_k": 1
    })
    _print_result(result, truncate=True)


# ═══════════════════════════════════════════════════════════════
# مثال 4: إنشاء وثيقة طبية (لا يحتاج API)
# ═══════════════════════════════════════════════════════════════

def example_document_generation():
    """إنشاء وثائق طبية"""
    print("\n" + "=" * 60)
    print("مثال 4: إنشاء وثيقة SOAP Note")
    print("=" * 60)

    from tools.documents import generate_medical_document

    result = generate_medical_document({
        "document_type": "case_summary",
        "content": {
            "patient_name": "م.ع. (مجهّل للخصوصية)",
            "subjective": "مريضة 72 عاماً تشكو من صعوبة القراءة وتمييز الوجوه منذ سنتين. تريد الاستمرار في قراءة القرآن والطبخ.",
            "objective": "حدة الإبصار: YD 6/60، YS 6/36. مجال بصري محيطي سليم. Scotoma مركزي ثنائي. حساسية تباين منخفضة.",
            "assessment": "Dry AMD bilateral — Moderate-Severe VI. محدودية في القراءة القريبة والتمييز. المجال المحيطي كافٍ للتنقل.",
            "plan": "1) مكبر يدوي 4x للقراءة المؤقتة. 2) Stand magnifier 6x للقراءة المطولة. 3) تدريب PRL 3×/أسبوع. 4) تعديل الإضاءة المنزلية."
        },
        "format": "markdown"
    })

    print("\n📄 الوثيقة المُنشأة:")
    print(result.get("document", "خطأ في الإنشاء"))
    print(f"\n⚠️ {result.get('disclaimer', '')}")


# ═══════════════════════════════════════════════════════════════
# مثال 5: PubMed Search (يحتاج اتصال إنترنت)
# ═══════════════════════════════════════════════════════════════

def example_pubmed_search():
    """البحث في PubMed"""
    print("\n" + "=" * 60)
    print("مثال 5: البحث في PubMed")
    print("=" * 60)

    from tools.pubmed import search_pubmed_api

    print("\n🔬 البحث عن أبحاث تدريب PRL لمرضى AMD:")
    result = search_pubmed_api({
        "query": "eccentric viewing training AMD low vision rehabilitation",
        "max_results": 5,
        "date_range": "2020:2026",
        "article_types": ["review", "clinical-trial"]
    })

    if "error" in result:
        print(f"❌ خطأ: {result['error']}")
    else:
        print(f"✅ وُجد {result.get('total_count', 0)} مقالة إجمالاً، عُرض {result.get('returned_count', 0)}")
        for i, article in enumerate(result.get("results", [])[:3], 1):
            print(f"\n[{i}] {article.get('title', '')}")
            print(f"    المجلة: {article.get('journal', '')} | التاريخ: {article.get('pub_date', '')}")
            print(f"    رابط: {article.get('pubmed_url', '')}")


# ═══════════════════════════════════════════════════════════════
# مثال 6: سلسلة التقييم الكاملة (يحتاج API)
# ═══════════════════════════════════════════════════════════════

def example_full_assessment_chain():
    """سلسلة التقييم الكاملة للحالة"""
    print("\n" + "=" * 60)
    print("مثال 6: سلسلة التقييم الكاملة")
    print("=" * 60)

    from chains.case_assessment import full_case_assessment

    patient_data = {
        "age": 72,
        "diagnosis": "Dry AMD bilateral",
        "visual_acuity": {
            "right_eye": "6/60 (LogMAR 1.0)",
            "left_eye": "6/36 (LogMAR 0.78)"
        },
        "visual_field": "Central scotoma bilateral, peripheral intact",
        "contrast_sensitivity": "منخفضة",
        "chief_complaint": "صعوبة شديدة في القراءة وتمييز الوجوه",
        "patient_goals": "القراءة، الطبخ، الاستقلالية في المنزل",
        "medical_history": "لا يوجد أمراض مزمنة",
        "functional_limitations": "عدم قدرة على قراءة أدوية، صعوبة في الطبخ، عزلة اجتماعية"
    }

    print("بدء سلسلة التقييم (بدون بحث PubMed لتسريع المثال)...")
    results = full_case_assessment(
        patient_data,
        include_pubmed_search=False
    )

    # عرض ملخص النتائج
    print("\n" + "=" * 60)
    print("📊 ملخص نتائج التقييم:")
    print("=" * 60)

    for phase, content in results.items():
        if isinstance(content, str) and content:
            preview = content[:300] + "..." if len(content) > 300 else content
            print(f"\n### {phase.upper()} ###")
            print(preview)
        else:
            print(f"\n### {phase.upper()} ###")
            print(content)


# ═══════════════════════════════════════════════════════════════
# مساعد
# ═══════════════════════════════════════════════════════════════

def _print_result(result: dict, truncate: bool = False):
    """طباعة نتيجة منسقة"""
    import json
    if truncate:
        # طباعة مختصرة للنتائج الطويلة
        if "results" in result and result["results"]:
            print(f"  وُجدت {result.get('total_found', len(result['results']))} نتائج")
            first = result["results"][0]
            print(f"  الأولى: {first.get('title', '')}")
            text = first.get('text', '')
            if text:
                print(f"  معاينة: {text[:200]}...")
        else:
            print(f"  {result}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🏥 مستشار التأهيل الذكي — أمثلة تطبيقية")
    print("=" * 60)

    # الأمثلة التي لا تحتاج API Key
    print("\n📌 الأمثلة التي لا تحتاج API Key:")
    example_visual_calculator()
    example_knowledge_base_search()
    example_document_generation()

    print("\n" + "=" * 60)

    # الأمثلة التي تحتاج API Key
    print("\n📌 الأمثلة التي تحتاج API Key:")
    if os.environ.get("ANTHROPIC_API_KEY"):
        choice = input("\nهل تريد تشغيل الأمثلة الكاملة؟ (نعم/لا): ").strip()
        if choice.lower() in ["نعم", "yes", "y"]:
            example_pubmed_search()
            example_simple_consultation()
    else:
        print("💡 لتشغيل الأمثلة الكاملة:")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        print("   python example_usage.py")
