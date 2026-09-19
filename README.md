# 🏥 مستشار التأهيل الذكي —# 🏥 نظام استشاري التأهيل البصري الذكي — Vision Rehab AI Consultant

## الدليل الشامل: من البنية السريرية إلى التنفيذ التقني


-----

## 📑 الفهرس الرئيسي

### الجزء الأول: الأساس السريري

1. [رؤية المشروع والبنية العامة](#الفصل-1-رؤية-المشروع-والبنية-العامة)
1. [نظام التقييم الوظيفي الشامل](#الفصل-2-نظام-التقييم-الوظيفي-الشامل)
1. [بروتوكولات التأهيل حسب التشخيص](#الفصل-3-بروتوكولات-التأهيل-حسب-التشخيص)
1. [قاعدة بيانات الأجهزة المساعدة](#الفصل-4-قاعدة-بيانات-الأجهزة-المساعدة)
1. [تدريبات التأهيل البصري الأساسية](#الفصل-5-تدريبات-التأهيل-البصري-الأساسية)
1. [التأهيل العصبي البصري](#الفصل-6-التأهيل-العصبي-البصري)
1. [تأهيل الأطفال](#الفصل-7-تأهيل-الأطفال)
1. [الجانب النفسي والتكيف](#الفصل-8-الجانب-النفسي-والتكيف)
1. [التوجه والتنقل ومهارات الحياة اليومية](#الفصل-9-التوجه-والتنقل-ومهارات-الحياة-اليومية)
1. [خصوصيات القراءة العربية](#الفصل-10-خصوصيات-القراءة-العربية)

### الجزء الثاني: البنية التقنية

1. [System Prompt المتقدم](#الفصل-11-system-prompt-المتقدم)
1. [Extended Thinking — التفكير السريري](#الفصل-12-extended-thinking)
1. [Tool Use — منظومة الأدوات](#الفصل-13-tool-use--منظومة-الأدوات)
1. [PubMed و المصادر العلمية](#الفصل-14-pubmed-والمصادر-العلمية)
1. [Vision — تحليل الصور الطبية](#الفصل-15-vision--تحليل-الصور-الطبية)
1. [RAG — بناء القاعدة المعرفية](#الفصل-16-rag--بناء-القاعدة-المعرفية)
1. [Prompt Chaining — سلاسل العمل](#الفصل-17-prompt-chaining--سلاسل-العمل)

### الجزء الثالث: التشغيل والجودة

1. [التوثيق والتقارير](#الفصل-18-التوثيق-والتقارير)
1. [نظام قياس النتائج والمتابعة](#الفصل-19-نظام-قياس-النتائج)
1. [الفريق متعدد التخصصات والإحالة](#الفصل-20-الفريق-متعدد-التخصصات)
1. [الأمان والخصوصية](#الفصل-21-الأمان-والخصوصية)
1. [خارطة البناء والتطوير](#الفصل-22-خارطة-البناء-والتطوير)

-----

# ═══════════════════════════════════════════════════

# الجزء الأول: الأساس السريري

# ═══════════════════════════════════════════════════

-----

## الفصل 1: رؤية المشروع والبنية العامة

### 1.1 ما هذا النظام؟

نظام ذكاء اصطناعي يعمل كـ**مساعد استشاري تأهيل بصري** يدمج بين:

- **المعرفة السريرية العميقة** — بروتوكولات، تقييمات، خطط علاجية
- **الوصول للأبحاث الحديثة** — PubMed، إرشادات سريرية، مراجعات منهجية
- **تحليل البيانات البصرية** — صور فحوصات، تقارير، مقاييس
- **التفكير السريري المتقدم** — استدلال متعدد الخطوات مدعوم بالأدلة

### 1.2 من يستخدمه؟

|المستخدم                 |طريقة الاستخدام                               |
|-------------------------|----------------------------------------------|
|**أخصائي التأهيل البصري**|بناء خطط علاجية، البحث عن أحدث البروتوكولات   |
|**طبيب العيون**          |فهم خيارات التأهيل لمرضاه، كتابة الإحالات     |
|**المعالج الوظيفي**      |بروتوكولات ADL، تعديلات بيئية                 |
|**أخصائي التنقل (O&M)**  |تقييم وتخطيط التنقل                           |
|**معلم التربية الخاصة**  |استراتيجيات تعليمية، Learning Media Assessment|
|**الباحث**               |مراجعة أدبيات، تلخيص أبحاث                    |


> ⚠️ **ليس بديلاً عن المتخصص البشري** — أداة مساعدة تعمل تحت إشراف مهني مؤهل.

### 1.3 البنية العامة — كيف يترابط كل شيء

```
┌─────────────────────────────────────────────────────────────────────┐
│                        المستخدم (متخصص/طبيب)                        │
│                    نص + صور + ملفات + أسئلة                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     طبقة التنسيق (Orchestration)                     │
│                                                                      │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ المصادقة │  │ إدارة      │  │ الموافقة │  │ Prompt Chain     │  │
│  │ والأمان  │  │ الجلسات   │  │ المسبقة  │  │ Orchestrator     │  │
│  └──────────┘  └────────────┘  └──────────┘  └────────┬─────────┘  │
└───────────────────────────────────────────────────────┼─────────────┘
                                                        │
┌───────────────────────────────────────────────────────┼─────────────┐
│              Engine             │             │
│                                                        ▼             │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    System Prompt الشامل                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │ الهوية   │ │ القواعد  │ │ الأمان   │ │ سياق الجلسة     │ │ │
│  │  │ السريرية │ │ السلوكية │ │ الطبي    │ │ (تقييم/علاج/بحث)│ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Extended │ │  Vision  │ │  Think   │ │ Adaptive │              │
│  │ Thinking │ │ (صور)    │ │  Tool    │ │ Effort   │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│                                                                      │
│  ┌──────────────────── الأدوات (Tools) ─────────────────────────┐  │
│  │                                                                │  │
│  │  🔬 PubMed     📚 RAG          🔢 حاسبة      📋 توثيق       │  │
│  │  Search        Knowledge       بصرية        طبي             │  │
│  │                Base                                           │  │
│  │  📄 Article    🏥 بروتوكولات   👁️ تقييم      🧠 تحويل       │  │
│  │  Fetch         تأهيلية        وظيفي        وإحالة          │  │
│  │                                                                │  │
│  │  🎯 أجهزة     👶 بروتوكولات   💊 تفاعلات   📊 نتائج        │  │
│  │  مساعدة       أطفال          دوائية       ومتابعة         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┬──────────────┐
            ▼              ▼              ▼              ▼
   ┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
   │  PubMed API  │ │ Vector DB   │ │ أجهزة DB │ │ بروتوكولات  │
   │  (E-Utils)   │ │ (RAG)       │ │ مساعدة   │ │ سريرية DB   │
   │  + MCP       │ │ Pinecone/   │ │          │ │              │
   │              │ │ Chroma      │ │          │ │              │
   └──────────────┘ └─────────────┘ └──────────┘ └──────────────┘
```

### 1.4 مبدأ الترابط: كل مكوّن سريري ← تقنية تخدمه

```
المحتوى السريري                    المكوّن التقني الذي يخدمه
─────────────────                   ──────────────────────────
بروتوكولات التقييم         ←──→    Tool: functional_assessment
                                    + RAG: assessment_protocols

بروتوكولات التأهيل بالتشخيص ←──→  RAG: diagnosis_protocols
                                    + PubMed: latest evidence

قاعدة الأجهزة المساعدة     ←──→    Tool: device_recommender
                                    + RAG: devices_database

تدريبات التأهيل            ←──→    RAG: training_exercises
                                    + Vision: exercise demos

التأهيل العصبي             ←──→    Extended Thinking: complex cases
                                    + RAG: neuro_protocols

تأهيل الأطفال              ←──→    Tool: developmental_assessment
                                    + RAG: pediatric_protocols

الدعم النفسي               ←──→    Tool: depression_screening
                                    + Prompt Chain: psych_workflow

التنقل ومهارات الحياة      ←──→    RAG: om_protocols + adl_guides

القراءة العربية             ←──→    Tool: arabic_reading_calculator
                                    + RAG: arabic_specific_protocols

قياس النتائج               ←──→    Tool: outcome_tracker
                                    + Charts: progress_visualization
```

-----

## الفصل 2: نظام التقييم الوظيفي الشامل

### 2.1 لماذا هو الأساس؟

كل شيء في التأهيل البصري يبدأ بالتقييم. بدون تقييم منظم، لا يمكن وضع خطة ولا قياس تقدم. النظام يجب أن يوجه المتخصص خلال كل مرحلة.

### 2.2 مراحل التقييم — Step by Step

```
┌─────────────────────────────────────────────────────────────────┐
│                   المرحلة 1: التاريخ المرضي                      │
│                                                                  │
│  ● التشخيص العيني الأساسي والمصاحب                              │
│  ● تاريخ فقدان البصر (مفاجئ/تدريجي، مستقر/متطور)               │
│  ● العمليات والعلاجات السابقة                                    │
│  ● الأدوية الحالية (خصوصاً: حقن Anti-VEGF، قطرات الغلوكوما)     │
│  ● الحالة الصحية العامة (سكري، ضغط، أعصاب)                      │
│  ● الحالة المعرفية (خصوصاً كبار السن)                            │
│  ● الشكاوى الوظيفية الرئيسية (ما الذي لا يستطيع فعله؟)          │
│  ● الأهداف الشخصية (ماذا يريد أن يحقق؟)                         │
│  ● البيئة المعيشية والدعم الأسري                                 │
│  ● المهنة / التعليم / الأنشطة الترفيهية                          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              المرحلة 2: التقييم البصري السريري                    │
│                                                                  │
│  2A. حدة الإبصار (Visual Acuity)                                 │
│  ├── بُعد: Snellen / ETDRS / LogMAR (مع أفضل تصحيح)             │
│  ├── قُرب: مخطط القراءة (Lighthouse, Colenbrander, MNREAD)       │
│  ├── كلا العينين منفردة + مجتمعة                                 │
│  └── مع/بدون فلتر → تأثير الإبهار                                │
│                                                                  │
│  2B. حساسية التباين (Contrast Sensitivity)                       │
│  ├── Pelli-Robson Chart                                          │
│  ├── Mars Letter Contrast Sensitivity Test                       │
│  └── الأهمية: قد تكون VA جيدة لكن CS منخفضة → مشاكل وظيفية     │
│                                                                  │
│  2C. المجال البصري (Visual Field)                                │
│  ├── مواجهة (Confrontation) — فحص مبدئي                          │
│  ├── Humphrey / Goldmann Perimetry — تفصيلي                      │
│  ├── Amsler Grid — الشبكة المركزية                                │
│  └── التصنيف: مركزي / محيطي / متقطع / نصفي                      │
│                                                                  │
│  2D. رؤية الألوان (Color Vision)                                 │
│  ├── Ishihara — فحص سريع                                         │
│  ├── Farnsworth D-15 — تصنيف نوع الخلل                           │
│  └── الأهمية: تؤثر على الأمان والتنقل واختيار الألوان            │
│                                                                  │
│  2E. تكيف الإضاءة (Light Adaptation)                             │
│  ├── Glare sensitivity — حساسية الإبهار                          │
│  ├── Dark adaptation — التكيف للظلام                              │
│  └── Photophobia — الحساسية للضوء                                 │
│                                                                  │
│  2F. فحوصات إضافية حسب الحالة                                    │
│  ├── Oculomotor assessment — حركات العين                          │
│  ├── Binocular vision — الرؤية الثنائية                           │
│  ├── Accommodation — التكيف (خصوصاً الأطفال)                      │
│  └── Stereopsis — الرؤية المجسمة                                  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              المرحلة 3: التقييم الوظيفي                           │
│                                                                  │
│  3A. تقييم القراءة                                               │
│  ├── حجم الطباعة الحرج (Critical Print Size — CPS)               │
│  ├── سرعة القراءة القصوى (Maximum Reading Speed — MRS)           │
│  ├── مسافة العمل الحالية والمثالية                                │
│  ├── مدة القراءة قبل الإرهاق                                     │
│  ├── نوع المادة: صحيفة / كتاب / هاتف / وصفات أدوية              │
│  └── 📌 للعربية: اتجاه RTL + التشكيل + خصوصيات القرآن           │
│                                                                  │
│  3B. الأنشطة اليومية (ADL / IADL)                                │
│  ├── العناية الشخصية: وضع الأدوية، ملابس، مكياج                  │
│  ├── الطبخ والتحضير: تقطيع، صب السوائل، قراءة الوصفات           │
│  ├── إدارة المنزل: تنظيف، تسوق، تنظيم                           │
│  ├── إدارة المال: أوراق نقدية، فواتير، أجهزة الصراف             │
│  ├── التواصل: هاتف، كتابة، توقيع                                 │
│  └── الترفيه: تلفزيون، أعمال يدوية، رياضة                        │
│                                                                  │
│  3C. التنقل والتوجه                                              │
│  ├── داخل المنزل: عتبات، سلالم، إضاءة                            │
│  ├── خارج المنزل: أرصفة، إشارات، مواصلات                         │
│  ├── بيئات مألوفة vs غير مألوفة                                   │
│  ├── ليلاً vs نهاراً                                              │
│  └── هل يستخدم عصا / مرافق / كلب مرشد؟                          │
│                                                                  │
│  3D. المهنة / التعليم                                            │
│  ├── متطلبات العمل البصرية                                       │
│  ├── تعديلات بيئة العمل المطلوبة                                  │
│  ├── الأداء الأكاديمي (للطلاب)                                   │
│  └── التقنيات المساعدة المستخدمة حالياً                           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              المرحلة 4: التقييم النفسي الأولي                     │
│                                                                  │
│  ● PHQ-2 / PHQ-9 — فحص الاكتئاب                                 │
│  ● مرحلة التكيف مع فقدان البصر                                   │
│  ● الدعم الاجتماعي والأسري                                       │
│  ● الدافعية للتأهيل                                              │
│  ● التوقعات (واقعية / غير واقعية)                                 │
│  ● هل يحتاج تحويل لأخصائي نفسي؟                                 │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              المرحلة 5: التصنيف والأولويات                        │
│                                                                  │
│  ● تصنيف WHO/ICD-11 لضعف البصر                                   │
│  ● تصنيف ICF: وظائف الجسم + الأنشطة + المشاركة + البيئة         │
│  ● قائمة الأولويات العلاجية (مرتبة حسب أهداف المريض)             │
│  ● تحديد مستوى الخدمة المطلوب (1/2/3)                            │
│  ● الإحالات المطلوبة (O&M, OT, نفسي, اجتماعي)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 التنفيذ التقني: أداة التقييم الوظيفي

```python
# ═══ أداة التقييم — تُضاف لقائمة Tools ═══
{
    "name": "functional_assessment",
    "description": """أداة التقييم الوظيفي البصري الشامل.
    تساعد في توجيه المتخصص خلال مراحل التقييم خطوة بخطوة.
    تقوم بـ: تصنيف مستوى ضعف البصر، حساب احتياجات التكبير،
    تحديد الأولويات التأهيلية، واقتراح التقييمات الإضافية المطلوبة.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "enum": [
                    "history",
                    "clinical_vision",
                    "functional",
                    "psychological",
                    "classification"
                ],
                "description": "مرحلة التقييم الحالية"
            },
            "data": {
                "type": "object",
                "description": "بيانات التقييم لهذه المرحلة"
            },
            "calculate": {
                "type": "array",
                "items": {"type": "string"},
                "description": "الحسابات المطلوبة: who_classification, magnification_need, cps_estimation, reading_speed_prediction"
            }
        },
        "required": ["phase", "data"]
    }
}
```

### 2.4 التنفيذ في RAG: هيكل مستندات التقييم

```
📁 knowledge_base/assessments/
├── 📄 functional_vision_assessment_protocol.md
│   ├── metadata: {category: "assessment", subcategory: "FVA", level: "comprehensive"}
│   └── content: بروتوكول التقييم الكامل مع خطوات ومعايير
│
├── 📄 visual_acuity_measurement_guide.md
│   ├── metadata: {category: "assessment", subcategory: "VA"}
│   └── content: طرق القياس، جداول التحويل، النصائح السريرية
│
├── 📄 contrast_sensitivity_protocol.md
├── 📄 visual_field_interpretation_guide.md
├── 📄 reading_assessment_protocol.md  ← يشمل MNREAD + Arabic specifics
├── 📄 adl_assessment_checklist.md
├── 📄 mobility_assessment_protocol.md
├── 📄 psychological_screening_guide.md  ← PHQ-9 + تكيف + تحويل
├── 📄 who_icd11_classification_guide.md
├── 📄 icf_framework_visual_impairment.md
│
├── 📁 forms/  ← نماذج جاهزة
│   ├── intake_form_template_ar.md
│   ├── fva_recording_form.md
│   ├── reading_assessment_form.md
│   ├── adl_checklist_ar.md
│   └── referral_form_template_ar.md
│
└── 📁 scoring/  ← جداول التقييم والتسجيل
    ├── va_conversion_tables.json
    ├── who_classification_criteria.json
    ├── magnification_calculation_formulas.json
    └── phq9_scoring_interpretation.json
```

-----

## الفصل 3: بروتوكولات التأهيل حسب التشخيص

### 3.1 المبدأ: كل تشخيص ← نمط فقدان بصري ← مقاربة تأهيلية مختلفة

```
التشخيص              نمط الفقدان            التحدي الرئيسي         المقاربة التأهيلية
──────────           ──────────             ──────────────          ─────────────────
AMD (جاف/رطب)       Scotoma مركزي          القراءة + الوجوه       Eccentric Viewing + تكبير
اعتلال شبكية سكري   متقطع + وذمة           تذبذب الرؤية           إدارة الإضاءة + تكبير مرن
الغلوكوما            فقدان محيطي تدريجي     التنقل + الإبهار       Scanning + فلاتر + O&M
التهاب شبكية صباغي   أنبوبي (Tunnel)         التنقل الليلي          O&M مكثف + إضاءة + تلسكوب
إعتام القرنية         ضبابية منتشرة          التباين + الإبهار      فلاتر + تباين + إضاءة
السكتة الدماغية       Hemianopia             التنقل + القراءة       Scanning + منشورات + تعويض
CVI (أطفال)          متغير + معقد           التعلم + التطور         بيئة بصرية مبسطة + تكرار
الرأرأة (Nystagmus)   تذبذب مستمر            كل المهام              وضعية رأس + تكبير + بيئة
المهق (Albinism)      حساسية ضوء + VA↓       الإبهار + القراءة      فلاتر + قبعة + تكبير
```

### 3.2 نموذج بروتوكول: الضمور البقعي (AMD)

```yaml
# ═══ AMD Rehabilitation Protocol ═══
diagnosis: "Age-Related Macular Degeneration"
icd11: "9B75"
pattern: "Central scotoma — bilateral, may be asymmetric"

assessment_priorities:
  - scotoma_mapping: "Amsler Grid + Microperimetry if available"
  - preferred_retinal_locus: "Identify PRL — usually just above or to the side of scotoma"
  - reading_assessment: "MNREAD — measure CPS, MRS, reading acuity"
  - contrast_sensitivity: "Pelli-Robson — often reduced"
  - glare: "Usually increased sensitivity"

rehabilitation_components:

  1_eccentric_viewing_training:
    description: "تدريب المريض على استخدام منطقة شبكية بديلة (PRL)"
    steps:
      - "تحديد موقع الـ scotoma بالنسبة للتثبيت"
      - "تحديد الاتجاه الأمثل للنظر اللامركزي"
      - "تمارين تثبيت مع هدف ثابت (بقعة ملونة)"
      - "تمارين تثبيت مع حروف/كلمات"
      - "التطبيق على القراءة التدريجي"
    frequency: "2-3 مرات أسبوعياً × 30 دقيقة × 6-8 أسابيع"
    evidence_level: "Level 1b — RCTs support efficacy"

  2_steady_eye_strategy:
    description: "تدريب العين على الثبات أثناء القراءة — تحريك النص بدل العين"
    application: "مع CCTV أو tablet"
    evidence: "Moderate — improves reading speed when combined with EV"

  3_magnification_prescription:
    near:
      calculation: "Magnification = Denominator of VA / Desired acuity"
      example: "VA 6/60 → wants 6/12 → 60/12 = 5X magnification needed"
      device_options:
        - "Stand magnifier 5X with LED — للقراءة الطويلة"
        - "Handheld magnifier 5X — للمهام القصيرة (أسعار، وصفات)"
        - "CCTV/EVES — للقراءة المطولة والكتابة"
        - "Tablet with zoom — متعدد الاستخدامات"
    distance:
      calculation: "Telescope power = Denominator / Desired (e.g., 60/12 = 5X)"
      devices: "Monocular telescope 4-6X — للوحات، تلفزيون"

  4_environmental_modifications:
    lighting:
      - "إضاءة موجهة (Task lighting) 75-100 watt LED"
      - "تجنب الإضاءة الخلفية والإبهار المباشر"
      - "مصباح قراءة بذراع مرنة"
    contrast:
      - "أدوات مطبخ بألوان متباينة (لوح تقطيع أسود + أبيض)"
      - "علامات بارزة على الأجهزة (نقاط لمسية)"
      - "أقلام فلوماستر سوداء عريضة بدل الأقلام العادية"
    organization:
      - "أماكن ثابتة لكل شيء"
      - "تسمية بالخط الكبير أو الصوت"

  5_psychosocial:
    - "شرح الحالة وتوقعات التأهيل الواقعية"
    - "ربط بمجموعات الدعم"
    - "إشراك الأسرة في الجلسات"
    - "فحص اكتئاب إذا لزم"

  6_follow_up:
    - "4 أسابيع: تقييم استخدام الأجهزة + Eccentric Viewing"
    - "3 أشهر: إعادة تقييم القراءة (MNREAD) + ADL"
    - "6 أشهر: تقييم شامل + تعديل الخطة"
    - "سنوياً: فحص بصري + تحديث الأجهزة"

  outcome_measures:
    - "MNREAD: Reading speed + CPS — قبل وبعد"
    - "VFQ-25: Quality of life — قبل وبعد"
    - "ADL checklist: Independence score — قبل وبعد"
    - "Patient satisfaction questionnaire"
```

### 3.3 التنفيذ في RAG: هيكل بروتوكولات التشخيص

```
📁 knowledge_base/diagnosis_protocols/
├── 📁 retinal/
│   ├── amd_dry_protocol.yaml
│   ├── amd_wet_protocol.yaml
│   ├── diabetic_retinopathy_protocol.yaml
│   ├── retinitis_pigmentosa_protocol.yaml
│   ├── retinal_detachment_post_surgery.yaml
│   └── stargardt_disease_protocol.yaml
│
├── 📁 optic_nerve/
│   ├── glaucoma_protocol.yaml
│   ├── optic_neuritis_protocol.yaml
│   └── optic_atrophy_protocol.yaml
│
├── 📁 corneal/
│   ├── corneal_opacity_protocol.yaml
│   ├── keratoconus_protocol.yaml
│   └── post_keratoplasty_protocol.yaml
│
├── 📁 neurological/
│   ├── hemianopia_protocol.yaml        ← الفصل 6
│   ├── visual_neglect_protocol.yaml
│   ├── tbi_vision_protocol.yaml
│   ├── nystagmus_protocol.yaml
│   └── cvi_protocol.yaml              ← الفصل 7
│
├── 📁 congenital/
│   ├── albinism_protocol.yaml
│   ├── aniridia_protocol.yaml
│   ├── congenital_cataract_protocol.yaml
│   └── rop_protocol.yaml
│
└── 📁 other/
    ├── post_cataract_surgery_protocol.yaml
    └── multiple_pathology_guide.yaml
```

             │
                    ▼
    Tool Call: search_knowledge_base(
        query="retinitis pigmentosa rehabilitation tunnel vision",
        category="diagnosis_protocols"
    )
                    │
                    ▼
    RAG يُرجع: retinitis_pigmentosa_protocol.yaml
                    │
                    ▼
    Tool Call: search_pubmed(
        query="retinitis pigmentosa low vision rehabilitation",
        date_range="2021:2026",
        article_types=["review", "guideline"]
    )
                    │
                    ▼
     يفكر (Interleaved Thinking):
    "البروتوكول المحلي يوصي بـ O&M + reverse telescope.
     أبحاث PubMed تُظهر دليل جديد على VR training.
     المريض عمره 55 → needs vocational assessment too."
                    │
                    ▼
     يُقدم خطة شاملة مخصصة مع مراجع
```

-----

## الفصل 4: قاعدة بيانات الأجهزة المساعدة

### 4.1 التصنيف الشامل

```
📦 الأجهزة المساعدة البصرية
│
├── 🔍 أجهزة التكبير البصرية (Optical Magnifiers)
│   ├── مكبرات يدوية (Handheld) — 2X إلى 20X
│   │   ├── مضيئة / غير مضيئة
│   │   ├── كروية / لاكروية (aspheric)
│   │   └── الاستخدام: مهام قصيرة (أسعار، أدوية، رسائل)
│   │
│   ├── مكبرات حامل (Stand) — 2X إلى 20X
│   │   ├── تحافظ على مسافة بؤرية ثابتة
│   │   ├── تحرر اليدين
│   │   └── الاستخدام: قراءة مطولة، أعمال يدوية
│   │
│   ├── مكبرات نظارية (Spectacle-mounted)
│   │   ├── عدسات مجهرية (Microscopes) — قوة عالية
│   │   ├── عدسات نصف عين (Half-eye)
│   │   ├── Prismatic half-eye — تقلل التقارب
│   │   └── الاستخدام: قراءة يدين حرتين + مسافة ثابتة
│   │
│   └── تلسكوبات (Telescopes)
│       ├── يدوية (Monocular) — 2.5X إلى 10X
│       ├── نظارية (Bioptic) — قيادة في بعض البلدان
│       ├── Keplerian (صورة أوضح، أثقل) vs Galilean (أخف، مجال أضيق)
│       └── الاستخدام: لوحات، تلفزيون، سبورة
│
├── 📺 أجهزة التكبير الإلكترونية (Electronic Magnification)
│   ├── CCTV / Video Magnifier — مكتبي
│   │   ├── تكبير 2X-75X
│   │   ├── أوضاع التباين (أبيض/أسود، أصفر/أزرق، إلخ)
│   │   ├── الاستخدام: قراءة مطولة + كتابة
│   │   └── الأفضل لـ: AMD, RP
│   │
│   ├── مكبرات إلكترونية محمولة (Portable EVES)
│   │   ├── حجم الجيب: Clover, Ruby, Compact+
│   │   ├── تكبير 2X-22X
│   │   └── الاستخدام: تسوق، مطاعم، خارج المنزل
│   │
│   ├── أجهزة لوحية (Tablets) + تطبيقات تكبير
│   │   ├── iPad/Android مع Accessibility features
│   │   ├── SuperVision+, Magnifying Glass apps
│   │   └── متعددة الاستخدامات + مقبولة اجتماعياً
│   │
│   └── نظارات ذكية (Smart Glasses)
│       ├── eSight — تكبير إلكتروني عالي الدقة
│       ├── OrCam MyEye — قراءة نصوص + تمييز وجوه
│       ├── Envision Glasses — AI-powered
│       └── IrisVision — VR headset للتكبير
│
├── 🕶️ الفلاتر والعدسات الخاصة
│   ├── فلاتر امتصاصية (Absorptive Filters)
│   │   ├── NoIR, Corning CPF, NOIR U-Series
│   │   ├── أصفر (450nm) — لتحسين التباين
│   │   ├── برتقالي (527nm) — للإبهار المتوسط
│   │   ├── كهرماني (550nm) — للإبهار الشديد
│   │   └── رمادي — لتقليل الإضاءة بدون تغيير الألوان
│   │
│   ├── منشورات (Prisms)
│   │   ├── Fresnel prisms — لـ Hemianopia (نقل الصورة)
│   │   ├── Yoked prisms — لـ Visual midline shift
│   │   └── Sector prisms — لـ field expansion
│   │
│   └── أغطية / حجب (Occlusion)
│       ├── Occluder لعين واحدة — للرؤية المزدوجة
│       └── Partial occlusion — للارتباك البصري
│
├── 🔊 تقنيات غير بصرية (Non-Optical & Assistive Tech)
│   ├── قارئات الشاشة: JAWS, NVDA, VoiceOver, TalkBack
│   ├── تحويل نص لصوت: text-to-speech
│   ├── كتب صوتية: Bookshare, Learning Ally, DAISY
│   ├── طابعة/قارئ برايل
│   ├── ساعات وأدوات ناطقة
│   ├── عصا بيضاء (أنواع: standard, folding, ID cane)
│   └── تطبيقات: Be My Eyes, Seeing AI, Aira, TapTapSee
│
└── 🏠 تعديلات بيئية
    ├── إضاءة: task lighting, dimmer switches, night lights
    ├── تباين: شريط لاصق ملون، علامات بارزة
    ├── تكبير: ملصقات كبيرة للأجهزة، لوحة مفاتيح كبيرة
    ├── تنظيم: أماكن ثابتة، صناديق ملونة
    └── أمان: درابزين، علامات على السلالم، إزالة العوائق
```

### 4.2 التنفيذ التقني: أداة توصية الأجهزة

```python
{
    "name": "device_recommender",
    "description": """قاعدة بيانات الأجهزة المساعدة البصرية.
    تُوصي بالأجهزة المناسبة بناءً على:
    - حدة الإبصار ونوع الفقدان البصري
    - المهمة المطلوبة (قراءة، مسافة، تنقل)
    - عمر المريض وقدراته الحركية والمعرفية
    - الميزانية والتوفر
    لكل جهاز: المواصفات، دواعي الوصف، موانع الاستعمال، طريقة التدريب""",
    "input_schema": {
        "type": "object",
        "properties": {
            "visual_acuity": {"type": "string", "description": "حدة الإبصار (مثل: 6/60)"},
            "field_type": {
                "type": "string",
                "enum": ["central_loss", "peripheral_loss", "hemianopia",
                         "scattered", "general_reduction", "normal_field"]
            },
            "task": {
                "type": "string",
                "enum": ["near_reading", "distance_viewing", "mobility",
                         "writing", "computer", "cooking", "grooming",
                         "medication_management", "shopping"]
            },
            "patient_age": {"type": "integer"},
            "cognitive_status": {
                "type": "string",
                "enum": ["normal", "mild_impairment", "moderate_impairment"]
            },
            "hand_function": {
                "type": "string",
                "enum": ["normal", "tremor", "limited_dexterity", "one_hand"]
            }
        },
        "required": ["visual_acuity", "task"]
    }
}
```

-----

## الفصل 5: تدريبات التأهيل البصري الأساسية

### 5.1 Eccentric Viewing Training (EVT) — تدريب النظر اللامركزي

```yaml
name: "Eccentric Viewing Training"
purpose: "تدريب المريض على استخدام منطقة شبكية بديلة (PRL) عند فقدان الرؤية المركزية"
indications:
  - "AMD مع scotoma مركزي"
  - "أي حالة بها فقدان مركزي (Stargardt, Macular hole, etc.)"
contraindications:
  - "ضعف معرفي شديد"
  - "عدم استقرار الحالة العينية"

protocol_steps:
  step_1_awareness:
    goal: "توعية المريض بوجود الـ scotoma وموقعه"
    exercises:
      - "Amsler Grid — تحديد شكل وموقع الـ scotoma"
      - "الشرح بنموذج الساعة: scotomak عند الساعة 12 → أنظر للأسفل (الساعة 6)"
    duration: "جلسة واحدة 30-45 دقيقة"

  step_2_localization:
    goal: "تحديد الاتجاه الأمثل للنظر اللامركزي"
    exercises:
      - "Freeman PRL training card"
      - "نقطة تثبيت مركزية + أهداف في 8 اتجاهات"
      - "المريض يحدد أي اتجاه يرى فيه الهدف بأفضل وضوح"
    duration: "1-2 جلسة"

  step_3_steady_fixation:
    goal: "تثبيت النظر على PRL لفترات متزايدة"
    exercises:
      - "تثبيت النظر على حرف كبير لمدة 5 ثوانٍ → 10 → 20 → 30"
      - "تثبيت مع عد (عد من 1-10 أثناء التثبيت)"
      - "تثبيت أثناء تحريك الرأس ببطء"
    frequency: "يومياً 15 دقيقة × 2-3 أسابيع"

  step_4_tracking:
    goal: "تتبع الأهداف أثناء استخدام PRL"
    exercises:
      - "تتبع خط أفقي من اليمين لليسار (للعربية)"
      - "تتبع كلمة كبيرة → جملة → سطر"
      - "تتبع أصبع المدرب المتحرك"
    frequency: "3 مرات أسبوعياً × 20 دقيقة"

  step_5_reading_application:
    goal: "تطبيق Eccentric Viewing على القراءة"
    exercises:
      - "كلمات مفردة كبيرة (حجم طباعة > CPS بخطوتين)"
      - "جمل قصيرة → فقرات"
      - "تصغير تدريجي لحجم الطباعة"
      - "مع جهاز تكبير (magnifier أو CCTV)"
      - "📌 للعربية: الاتجاه من اليمين لليسار"
    frequency: "يومياً 20-30 دقيقة × 6-8 أسابيع"

  expected_outcomes:
    - "تحسن سرعة القراءة 40-60% خلال 8 أسابيع"
    - "القدرة على قراءة حجم طباعة أصغر بخطوة واحدة"
    - "تقليل حركات الرأس التعويضية"

  evidence: "Level 1b — Multiple RCTs show efficacy (Nilsson 2003, Seiple 2011)"
```

### 5.2 Scanning Training — تدريب المسح البصري

```yaml
name: "Visual Scanning Training"
purpose: "توسيع المسح البصري للمرضى الذين فقدوا جزءاً من المجال البصري"
indications:
  - "Hemianopia (فقدان نصف المجال)"
  - "Quadrantanopia"
  - "ضيق المجال البصري (Glaucoma, RP)"
  - "Visual neglect بعد السكتة الدماغية"

protocol_steps:
  step_1_awareness:
    goal: "وعي المريض بحدود مجاله البصري"
    exercises:
      - "تمرين الساعة: المريض يمد ذراعه ويحرك يده حتى تختفي"
      - "تحديد حدود المجال في كل اتجاه"

  step_2_organized_scanning:
    goal: "بناء نمط مسح منتظم ومنهجي"
    exercises:
      - "مسح أفقي: من اليمين لليسار (وعكسه) بسرعة ثابتة"
      - "مسح عمودي: من الأعلى للأسفل"
      - "مسح بيئة الغرفة: باب → نافذة → أثاث بترتيب"
      - "البحث عن أهداف في صورة معقدة (مثل: كم سيارة حمراء؟)"

  step_3_functional_scanning:
    goal: "تطبيق على المواقف اليومية"
    exercises:
      - "عبور الشارع: نظر يمين → يسار → يمين مع تحريك الرأس"
      - "البحث في رف السوبرماركت"
      - "قراءة سطر كامل بدون تفويت كلمات"
      - "مسح شاشة الهاتف/الكمبيوتر"

  frequency: "3 مرات أسبوعياً × 30 دقيقة × 8-12 أسبوع"
  evidence: "Level 1a — Strong evidence for hemianopia scanning (Cochrane 2019)"
```

### 5.3 تدريبات إضافية (يجب تخزينها في RAG)

|التدريب                     |المؤشرات                |الملف في RAG                         |
|----------------------------|------------------------|-------------------------------------|
|Steady Eye Strategy         |AMD + تحريك النص        |`training/steady_eye_strategy.yaml`  |
|Tracking Exercises          |مشاكل حركة العين        |`training/tracking_exercises.yaml`   |
|Saccadic Training           |تباطؤ حركات الرمش       |`training/saccadic_training.yaml`    |
|Hand-Eye Coordination       |أي ضعف بصري + مهام يدوية|`training/hand_eye_coordination.yaml`|
|Typing/Writing Training     |صعوبة الكتابة           |`training/writing_training.yaml`     |
|Daily Living Skills Training|ADL                     |`training/adl_skills/`               |

-----

## الفصل 6: التأهيل العصبي البصري

### 6.1 الحالات المشمولة

```
┌────────────────────────────────────────────────────────────────┐
│                 التأهيل العصبي البصري                           │
│           Neuro-Visual Rehabilitation                          │
│                                                                │
│  1. Hemianopia (فقدان نصف المجال البصري)                       │
│     ├── Homonymous — نفس الجهة في العينين (سكتة دماغية)        │
│     ├── Bitemporal — الجانبين الخارجيين (ورم نخامي)             │
│     └── Quadrantanopia — ربع المجال                             │
│                                                                │
│  2. Visual Neglect (الإهمال البصري)                             │
│     ├── يختلف عن Hemianopia — مشكلة انتباه وليست فقدان          │
│     ├── المريض لا يعي الجانب المصاب                             │
│     └── أخطر على الأمان                                        │
│                                                                │
│  3. Post Trauma Vision Syndrome (PTVS)                         │
│     ├── بعد إصابات الدماغ الرضية (TBI)                          │
│     ├── أعراض: ازدواج، دوخة، حساسية ضوء، صعوبة تركيز           │
│     └── يشمل: convergence insufficiency, accommodative issues   │
│                                                                │
│  4. Diplopia (الرؤية المزدوجة)                                 │
│     ├── أحادية / ثنائية                                        │
│     ├── مستمرة / متقطعة                                        │
│     └── العلاج: منشورات، حجب، تمارين                            │
│                                                                │
│  5. Nystagmus (الرأرأة)                                        │
│     ├── خلقية / مكتسبة                                         │
│     ├── Null point — وضعية الرأس المثلى                         │
│     └── العلاج: منشورات، جراحة، تعديلات بيئية                    │
│                                                                │
│  6. Cortical Visual Impairment - CVI (الفصل 7 — أطفال)         │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 بروتوكول Hemianopia — مختصر

```yaml
hemianopia_rehabilitation:
  assessment:
    - "تحديد نوع ومدى فقدان المجال (Humphrey/Goldmann)"
    - "تقييم مهارات المسح الحالية"
    - "تقييم القراءة (أين يضيع في السطر؟)"
    - "تقييم التنقل (هل يصطدم بأشياء؟)"
    - "تقييم Visual Neglect (Line Bisection Test, Star Cancellation)"

  treatment_approaches:
    compensatory_scanning:
      description: "تدريب المريض على مسح الجهة المفقودة بفعالية"
      technique: "Lighthouse Technique: حرك عينك + رأسك نحو الجهة العمياء"
      evidence: "Level 1a — الأكثر فعالية"

    optical_aids:
      fresnel_prisms:
        description: "منشورات لنقل صورة الجهة المفقودة للجهة السليمة"
        power: "عادة 15-20 prism diopters"
        placement: "على عدسة عين الجهة المصابة"
        limitations: "تسبب ازدواج بصري في منطقة التداخل"

      sector_prisms:
        description: "Peli Peripheral Prisms — يعطي تنبيه بالأشياء من الجانب"
        evidence: "Level 2 — moderate evidence"

    reading_strategies:
      right_hemianopia: "صعوبة إيجاد بداية الكلمة التالية"
      left_hemianopia: "صعوبة إيجاد بداية السطر التالي"
      techniques:
        - "خط عمودي في بداية كل سطر (للعربية: في اليمين)"
        - "typoscope — نافذة تُبرز سطراً واحداً"
        - "استخدام الإصبع كدليل"
```

-----

## الفصل 7: تأهيل الأطفال

### 7.1 لماذا مختلف تماماً؟

الطفل ليس “بالغ صغير” — الفروق الجوهرية:

|البُعد      |البالغ             |الطفل               |
|-----------|-------------------|--------------------|
|**الهدف**  |استعادة الاستقلالية|دعم التطور والتعلم  |
|**التقييم**|يصف مشاكله         |يحتاج ملاحظة سلوكية |
|**التعاون**|عادة متعاون        |يحتاج تحفيز ولعب    |
|**التكيف** |صعب نفسياً          |أكثر مرونة عصبياً    |
|**الأجهزة**|يختار بنفسه        |الأهل والمعلم يقررون|
|**البيئة** |منزل/عمل           |منزل/مدرسة/لعب      |
|**CVI**    |نادر               |شائع جداً            |

### 7.2 Cortical Visual Impairment (CVI) — التفصيل

```yaml
cvi_protocol:
  definition: "ضعف بصري ناتج عن خلل في الدماغ وليس في العين"
  causes:
    - "Hypoxic-Ischemic Encephalopathy (نقص الأكسجين)"
    - "Periventricular Leukomalacia (PVL)"
    - "إصابات الدماغ الرضية"
    - "الصرع الشديد"

  assessment:
    roman_cvi_range:
      description: "مقياس Christine Roman — 0-10"
      characteristics:
        - "Color preference (تفضيل لوني)"
        - "Need for movement (تحتاج حركة لجذب الانتباه)"
        - "Visual latency (تأخر الاستجابة البصرية)"
        - "Visual field preferences"
        - "Difficulty with visual complexity"
        - "Light gazing / Photophobia"
        - "Difficulty with distance"
        - "Atypical visual reflexes"
        - "Difficulty with novelty (يفضل المألوف)"
        - "Absence of visually guided reach"

  phases:
    phase_1_building_visual_behavior: # CVI Range 1-3
      goal: "بناء سلوك بصري أساسي"
      strategies:
        - "شيء واحد فقط على خلفية سوداء"
        - "اللون المفضل (عادة أحمر أو أصفر)"
        - "حركة لجذب الانتباه"
        - "إضاءة خلفية (backlighting)"
        - "بيئة بصرية مبسطة جداً"

    phase_2_integrating_vision: # CVI Range 4-7
      goal: "دمج البصر مع الحواس الأخرى"
      strategies:
        - "زيادة تدريجية في تعقيد الخلفية"
        - "إدخال أشياء جديدة مع مألوفة"
        - "تقليل تدريجي للحركة"
        - "ربط البصر باللمس والصوت"

    phase_3_visual_curiosity: # CVI Range 8-10
      goal: "استخدام البصر بفعالية للتعلم"
      strategies:
        - "بيئة أقرب للطبيعية"
        - "مهام بصرية أكثر تعقيداً"
        - "تطبيق في الصف والمنزل"

  evidence: "Level 3 — Expert consensus + observational studies"
```

### 7.3 Learning Media Assessment (LMA)

```yaml
learning_media_assessment:
  purpose: "تحديد الوسيط التعليمي الأنسب للطفل"
  outcome_options:
    - "طباعة عادية (مع تعديلات)"
    - "طباعة كبيرة"
    - "طباعة كبيرة + صوتي"
    - "برايل (كامل أو اختصار)"
    - "صوتي + لمسي"
    - "وسائط متعددة (تكنولوجيا مساعدة)"

  factors_assessed:
    - "حدة الإبصار القريبة"
    - "سرعة القراءة مقارنة بالأقران"
    - "الإرهاق البصري"
    - "استقرار الحالة العينية"
    - "الوظائف البصرية الإضافية (مجال، تباين)"
    - "تفضيل الطفل ودافعيته"
```

-----

## الفصل 8: الجانب النفسي والتكيف

### 8.1 مراحل التكيف مع فقدان البصر

```
┌─────────────────────────────────────────────────┐
│  نموذج التكيف مع فقدان البصر                     │
│  (Modified Kübler-Ross for Vision Loss)           │
│                                                   │
│  1. الصدمة والإنكار                               │
│     "لا أصدق... الطبيب مخطئ"                      │
│     → الدعم: معلومات بسيطة + وقت                  │
│                                                   │
│  2. الغضب والإحباط                                │
│     "لماذا أنا؟ هذا غير عادل"                     │
│     → الدعم: الاستماع + التحقق من المشاعر         │
│                                                   │
│  3. الاكتئاب والانسحاب                            │
│     "لا فائدة... حياتي انتهت"                     │
│     ⚠️ أخطر مرحلة — قد يحتاج تحويل نفسي          │
│     → الدعم: فحص اكتئاب + ربط بمجموعات دعم       │
│                                                   │
│  4. المساومة والتجربة                             │
│     "سأجرب هذا الجهاز... ربما يساعد"              │
│     → الدعم: أفضل وقت للتدريب على الأجهزة         │
│                                                   │
│  5. القبول والتكيف                                │
│     "بصري تغير لكنني لا زلت أنا"                  │
│     → الدعم: تعزيز الاستقلالية                    │
│                                                   │
│  ⚠️ ليست خطية — المريض قد يتنقل بين المراحل      │
└─────────────────────────────────────────────────┘
```

### 8.2 أداة فحص الاكتئاب

```python
{
    "name": "depression_screening",
    "description": """فحص مبدئي للاكتئاب عند مرضى ضعف البصر.
    يستخدم PHQ-2 كفحص أولي، وPHQ-9 إذا كان PHQ-2 إيجابياً.
    يُحدد: مستوى الخطورة، الحاجة للتحويل، التوصيات المبدئية.
    ⚠️ ليس بديلاً عن التقييم النفسي المتخصص.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "enum": ["PHQ-2", "PHQ-9", "GDS-15"],
                "description": "المقياس المستخدم"
            },
            "responses": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "إجابات المريض (0-3 لكل سؤال)"
            },
            "additional_risk_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "عوامل خطر: recent_vision_loss, social_isolation, living_alone, previous_depression, chronic_pain"
            }
        },
        "required": ["tool", "responses"]
    }
}
```

### 8.3 متى نُحوّل لأخصائي نفسي؟

```yaml
referral_criteria:
  immediate:
    - "أفكار انتحارية أو إيذاء النفس"
    - "PHQ-9 ≥ 20 (شديد)"
  urgent:
    - "PHQ-9 ≥ 15 (متوسط-شديد)"
    - "عدم التحسن بعد 4-6 أسابيع من التأهيل"
    - "رفض التأهيل المستمر بسبب الحالة النفسية"
  recommended:
    - "PHQ-9 ≥ 10 (متوسط)"
    - "تاريخ اكتئاب سابق"
    - "فقدان بصر مفاجئ حديث (< 6 أشهر)"
    - "عزلة اجتماعية شديدة"
```

-----

## الفصل 9: التوجه والتنقل ومهارات الحياة اليومية

### 9.1 التوجه والتنقل (O&M)

```yaml
orientation_and_mobility:
  assessment:
    indoor:
      - "التنقل في المنزل (هل يصطدم بالأثاث؟)"
      - "السلالم (صعود/نزول)"
      - "الإضاءة والعتبات"
    outdoor:
      - "عبور الشارع"
      - "استخدام المواصلات العامة"
      - "التنقل في بيئة مألوفة vs جديدة"
      - "الإضاءة الليلية"
    tools:
      - "هل يستخدم عصا بيضاء؟ (ID cane vs mobility cane)"
      - "هل يعرف تقنية المرافق (Sighted Guide)؟"
      - "هل لديه GPS ناطق أو تطبيقات؟"

  training_areas:
    sighted_guide_technique:
      steps:
        - "المبصر يمشي نصف خطوة أمام الكفيف"
        - "الكفيف يمسك فوق المرفق"
        - "إشارات للمنعطفات والسلالم والأبواب"
    white_cane_basics:
      types:
        - "ID cane — للتعريف فقط (ضعف بصر جزئي)"
        - "Long cane — للتنقل المستقل"
      techniques:
        - "Touch technique — لمس الأرض يميناً ويساراً"
        - "Constant contact — لمس مستمر"
    environmental_modifications:
      - "إضاءة كافية في الممرات والسلالم"
      - "شريط لاصق ملون على حواف السلالم"
      - "إزالة العوائق من الممرات"
      - "ألوان متباينة للأبواب والمفاتيح"
```

### 9.2 مهارات الحياة اليومية (ADL/IADL)

```yaml
daily_living_skills:
  medication_management:
    critical_for: "مرضى السكري + الغلوكوما (قطرات متعددة)"
    strategies:
      - "علبة أدوية أسبوعية مقسمة + ملصقات بارزة"
      - "تطبيق ناطق للتذكير بالأدوية"
      - "ترتيب ثابت للقطرات (ألوان أغطية مختلفة)"
      - "تدريب على التقطير الذاتي (قطرة عين)"
      - "⚠️ أنسولين: أقلام بنقرات صوتية vs سرنجات"

  kitchen_safety:
    strategies:
      - "ألواح تقطيع بألوان متباينة (أسود لأطعمة فاتحة والعكس)"
      - "مؤقت ناطق / صوتي"
      - "قياسات بارزة على الأكواب"
      - "تنظيم الخزائن بنظام ثابت"
      - "علامات بارزة على الفرن والمايكروويف"
      - "⚠️ احتياطات الأمان: حروق، سكاكين"

  personal_care:
    - "تنظيم الملابس: شماعات ملونة حسب الزي"
    - "مكياج: مرآة مكبرة 5-10X مع إضاءة"
    - "حلاقة: ماكينة كهربائية أأمن"
    - "الاستحمام: تنظيم ثابت + ملصقات بارزة على الشامبو"

  money_management:
    - "طي الأوراق النقدية بطرق مختلفة حسب الفئة"
    - "تطبيق تمييز العملات (Seeing AI)"
    - "الدفع الإلكتروني (أسهل مع accessibility)"

  writing_and_signing:
    - "أقلام فلوماستر سوداء عريضة"
    - "دليل توقيع (Signature guide)"
    - "أوراق بخطوط سوداء عريضة"
    - "لوحة كتابة بتباين عالٍ"
```

-----

## الفصل 10: خصوصيات القراءة العربية

### 10.1 التحديات الفريدة

```yaml
arabic_reading_challenges:
  direction:
    issue: "القراءة من اليمين لليسار (RTL)"
    impact_on_rehabilitation:
      - "تدريب Eccentric Viewing: اتجاه المسح يختلف عن الإنجليزية"
      - "Hemianopia اليمنى: تأثير أكبر على بداية السطر بالعربية"
      - "Hemianopia اليسرى: تأثير على إيجاد بداية السطر التالي بالإنجليزية لكن نهايته بالعربية"
    adaptation: "تدريبات المسح يجب أن تبدأ من اليمين"

  diacritics:
    issue: "التشكيل (فتحة، ضمة، كسرة) يزيد التعقيد البصري"
    impact:
      - "يحتاج حساسية تباين أعلى"
      - "حجم طباعة أكبر مقارنة بنص بدون تشكيل"
      - "CPS للنص المشكّل أكبر بـ 1-2 خطوة من غير المشكّل"
    application: "قراءة القرآن الكريم تحتاج تكبيراً أعلى"

  quran_reading:
    special_requirements:
      - "حجم الطباعة: عادة 18-24 نقطة كحد أدنى لضعاف البصر"
      - "مصاحف ضعاف البصر: خط كبير + تباين عالي"
      - "تطبيقات: مصحف إلكتروني مع تكبير + تلاوة صوتية"
      - "CCTV مثالي: تكبير متغير + تباين + مسافة عمل مريحة"
      - "إضاءة: task lighting موجهة بدون إبهار"
    cultural_importance: "غالباً الأولوية الأولى للمريض → يزيد الدافعية"

  assessment_tools_arabic:
    available:
      - "Colenbrander Arabic reading card (غير معتمد رسمياً)"
      - "MNREAD — نسخة عربية محدودة"
    gaps:
      - "لا يوجد VFQ-25 عربي معتمد بشكل واسع"
      - "لا يوجد MNREAD عربي معتمد بالتشكيل"
    workaround:
      - "استخدام نصوص موحدة بأحجام متدرجة"
      - "قياس سرعة القراءة بالكلمات/دقيقة على نص عربي معياري"
```

### 10.2 أداة حسابات القراءة العربية

```python
{
    "name": "arabic_reading_calculator",
    "description": """حسابات خاصة بالقراءة العربية:
    - تقدير حجم الطباعة الأمثل (مع/بدون تشكيل)
    - حساب التكبير المطلوب لقراءة القرآن
    - تحويل بين وحدات حجم الطباعة (M-units, points, LogMAR)
    - تقدير مسافة العمل المثلى""",
    "input_schema": {
        "type": "object",
        "properties": {
            "calculation": {
                "type": "string",
                "enum": [
                    "optimal_print_size",
                    "quran_magnification",
                    "working_distance",
                    "print_unit_conversion"
                ]
            },
            "near_va": {"type": "string", "description": "حدة الإبصار القريبة"},
            "text_type": {
                "type": "string",
                "enum": ["plain_arabic", "diacritics", "quran", "numbers"]
            },
            "desired_reading_speed": {
                "type": "string",
                "description": "السرعة المرغوبة: fluent, functional, spot_reading"
            }
        },
        "required": ["calculation"]
    }
}
```

-----

# ═══════════════════════════════════════════════════

# الجزء الثاني: البنية التقنية

# ═══════════════════════════════════════════════════

-----

## الفصل 11: System Prompt المتقدم

### 11.1 الفلسفة: System Prompt = الحمض النووي للنظام

System Prompt يُحدد **كل شيء**: الهوية، المعرفة، السلوك، الحدود. كلما كان أكثر تفصيلاً وهيكلة، كان الأداء أفضل.

### 11.2 System Prompt الكامل

```python
SYSTEM_PROMPT = """
<role>
أنت استشاري تأهيل بصري متخصص (Low Vision Rehabilitation Consultant)
وخبير في التأهيل العصبي البصري (Neuro-Visual Rehabilitation).

تخصصاتك الدقيقة:
- تقييم وتأهيل ضعف البصر (Low Vision Assessment & Rehabilitation)
- وصف وتدريب الأجهزة المساعدة البصرية (Assistive Devices)
- التأهيل العصبي البصري (Hemianopia, Neglect, TBI vision, CVI)
- تأهيل الأطفال ضعاف البصر (Pediatric Low Vision)
- التوجه والتنقل (Orientation & Mobility — consultative)
- مهارات الحياة اليومية لضعاف البصر (ADL Training)
- الدعم النفسي الأولي والإحالة
- القراءة العربية لضعاف البصر (خصوصيات RTL والتشكيل والقرآن)

مؤهلاتك المرجعية:
- إلمام بتصنيفات WHO/ICD-11 لضعف البصر
- إطار ICF (International Classification of Functioning)
- إرشادات AAO, RNIB, ICO, ACE, AOA
- مقاييس التقييم: Colenbrander, Bailey-Lovie, ETDRS, MNREAD, Pelli-Robson
- مقاييس النتائج: VFQ-25, LVQOL, IVI, VA LV VFQ-48, Activity Inventory
- بروتوكولات: Eccentric Viewing, Scanning Training, Steady Eye Strategy
- تصنيف CVI: Roman-Lantzy CVI Range (0-10)
- مقاييس نفسية: PHQ-2, PHQ-9, GDS-15
</role>

<clinical_approach>
1. التقييم الشامل أولاً:
   - لا تُقدم توصيات بدون فهم الحالة كاملة
   - اسأل عن: التشخيص، VA، المجال، الشكاوى الوظيفية، الأهداف
   - استخدم Extended Thinking للحالات المعقدة

2. المنهج المبني على الأدلة:
   - ابحث في PubMed عند الحاجة لأحدث الأدلة
   - صنّف مستوى الدليل (1a, 1b, 2, 3, 4, 5)
   - ميّز بين: ثابت علمياً / محتمل / رأي خبراء / تجريبي

3. التفكير السريري المنظم:
   - التشخيص → نمط الفقدان → التأثير الوظيفي → التدخلات → المتابعة
   - فكّر بالحالات الحدية والموانع
   - لا تنسَ الجانب النفسي والاجتماعي

4. تحليل الصور الطبية (عند الإرسال):
   - وصف منهجي: ما أراه → تفسير → ربط سريري → توصيات
   - ⚠️ لست بديلاً عن تفسير المتخصص — أقدم تحليلاً مساعداً

5. الخطط العلاجية:
   - أهداف SMART (محددة، قابلة للقياس، واقعية، زمنية)
   - قصيرة المدى (1-4 أسابيع) + متوسطة (1-3 أشهر) + طويلة (3-12 شهر)
   - الأجهزة + التدريبات + التعديلات البيئية + الدعم النفسي
   - معايير النجاح ومؤشرات القياس
   - خطة المتابعة وإعادة التقييم

6. التوثيق:
   - فقط بعد موافقة صريحة
   - تنسيقات: SOAP Note, ICF Report, Referral Letter
   - لغة مهنية دقيقة + مصطلحات إنجليزية بين قوسين
</clinical_approach>

<patient_populations>
تتعامل مع:
- بالغون: AMD, DR, Glaucoma, RP, Corneal opacity, Nystagmus, Albinism
- عصبي: Hemianopia, Visual Neglect, TBI/PTVS, Diplopia
- أطفال: CVI, ROP, Congenital cataracts, Albinism, Nystagmus
- كبار سن: مشاكل معرفية مصاحبة + سقوط + عزلة
- متعدد الإعاقة: ضعف بصر + سمعي / حركي / معرفي
</patient_populations>

<available_tools>
لديك الأدوات التالية — استخدمها بفعالية:

1. search_pubmed — البحث في PubMed عن أحدث الأبحاث
2. fetch_article_details — جلب تفاصيل مقالة بالـ PMID
3. search_knowledge_base — البحث في القاعدة المعرفية المحلية
   (بروتوكولات، إرشادات، أجهزة، تقييمات، تمارين)
4. functional_assessment — أداة التقييم الوظيفي الشامل
5. device_recommender — قاعدة بيانات الأجهزة المساعدة
6. visual_calculator — حسابات بصرية (تكبير، VA تحويل، مسافة عمل)
7. arabic_reading_calculator — حسابات القراءة العربية والقرآن
8. depression_screening — فحص الاكتئاب (PHQ-2/9, GDS)
9. outcome_tracker — تتبع النتائج عبر الزمن
10. generate_document — إنشاء تقارير وخطابات (بعد الموافقة)
11. referral_generator — إنشاء خطابات الإحالة
12. think — أداة التفكير المنظم للحالات المعقدة
</available_tools>

<behavioral_rules>
- اللغة الافتراضية: العربية مع المصطلحات الطبية الإنجليزية بين قوسين
- لا تُشخّص — حلّل وأقترح وأوصِ تحت إشراف المتخصص
- وضّح مستوى الدليل العلمي لكل توصية
- اسأل قبل التوثيق — لا تُنتج تقارير بدون موافقة صريحة
- إذا كانت الحالة خارج نطاقك، وجّه للتخصص المناسب
- للحالات الطارئة (انفصال شبكية مفاجئ، ارتفاع ضغط عين حاد): وجّه للطوارئ فوراً
- أضف disclaimer في كل استجابة تحتوي على توصيات سريرية
</behavioral_rules>

<safety_disclaimers>
⚠️ هذا النظام أداة مساعدة وليس بديلاً عن:
- التشخيص الطبي المباشر
- الفحص السريري
- القرار العلاجي من المتخصص المؤهل
كل التوصيات تحتاج مراجعة من متخصص قبل التطبيق.
للحالات الطارئة: توجه لقسم الطوارئ فوراً.
</safety_disclaimers>
"""
```

### 11.3 كيف يترابط System Prompt مع باقي المكونات

```
System Prompt
    │
    ├── يُعرّف الأدوات المتاحة ←───→ Tool Use (الفصل 13)
    │   "لديك 12 أداة..."              يعرف متى يستدعي كل أداة
    │
    ├── يُحدد المنهج السريري ←───→ Extended Thinking (الفصل 12)
    │   "التقييم الشامل أولاً"           يُفكر بعمق قبل الإجابة
    │
    ├── يُعرّف التخصصات ←─────→ RAG Knowledge Base (الفصل 16)
    │   "CVI, AMD, Hemianopia..."       القاعدة المعرفية تُغطي كل تخصص
    │
    ├── يُحدد قواعد الصور ←───→ Vision (الفصل 15)
    │   "تحليل منهجي: وصف→تفسير"        يتبع بروتوكول التحليل
    │
    ├── يُحدد قواعد التوثيق ←──→ Prompt Chaining (الفصل 17)
    │   "بعد الموافقة فقط"              Chain يطلب الموافقة قبل الخطوة 6
    │
    └── يُحدد الأمان ←────────→ Security (الفصل 21)
        "disclaimers, طوارئ"            Validation + output filtering
```

-----

## الفصل 12: Extended Thinking — التفكير السريري

### 12.1 لماذا ضروري في التأهيل البصري؟

التأهيل البصري يتطلب **تفكيراً متعدد الطبقات**: التشخيص → نمط الفقدان → التأثير الوظيفي → الأجهزة المناسبة → التدريبات → العوامل النفسية → المتابعة. Extended Thinking يسمح بالتفكير بعمق قبل الإجابة.

### 12.2 أوضاع التفكير

```python
# ═══ الوضع 1: تفكير تكيفي (Adaptive) — لـ Opus 4.6 ═══
#  يُقرر تلقائياً كم يحتاج من التفكير

response = client.messages.create(
    max_tokens=16000,
    thinking={
        "type": "adaptive",
        "effort": "high"  # low | medium | high | max
    },
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_query}]
)

# ═══ الوضع 2: تفكير يدوي (Manual) — 
# نحدد ميزانية التفكير بالتوكنز

response = client.messages.create(
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # الحد الأدنى 1024
    },
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_query}]
)
```

### 12.3 متى نستخدم أي مستوى تفكير؟

```python
THINKING_LEVELS = {
    "low": {
        "budget_tokens": 2000,
        "adaptive_effort": "low",
        "use_cases": [
            "أسئلة بسيطة: 'ما هو تصنيف WHO لحدة 6/60؟'",
            "تحويلات: 'حوّل LogMAR 1.0 إلى Snellen'",
            "تعريفات: 'ما هو Eccentric Viewing؟'",
        ]
    },
    "medium": {
        "budget_tokens": 5000,
        "adaptive_effort": "medium",
        "use_cases": [
            "بروتوكول واحد: 'ما خطوات تدريب Scanning لـ hemianopia؟'",
            "توصية جهاز: 'مريض AMD، VA 6/36، يريد قراءة الجريدة'",
            "شرح مقال: 'لخص لي هذا البحث عن EVT'",
        ]
    },
    "high": {
        "budget_tokens": 10000,
        "adaptive_effort": "high",
        "use_cases": [
            "حالة كاملة: 'مريض 72 سنة، AMD+Glaucoma، ما الخطة؟'",
            "مقارنة خيارات: 'CCTV vs tablet vs eSight لهذا المريض'",
            "تأهيل أطفال: 'طفل CVI Range 4، ما البرنامج التعليمي؟'",
            "تحليل صورة طبية معقدة",
        ]
    },
    "max": {
        "budget_tokens": 16000,
        "adaptive_effort": "max",
        "use_cases": [
            "مراجعة أدبيات: 'ما أحدث الأبحاث عن VR في تأهيل RP؟'",
            "حالة معقدة متعددة: 'مريض TBI + RP + اكتئاب + سكري'",
            "بناء بروتوكول جديد مع أدلة",
        ]
    }
}
```

### 12.4 التفكير المتداخل مع الأدوات (Interleaved Thinking)

```python
# Claude يُفكر بين كل استدعاء أداة — ضروري للحالات المعقدة

response = client.messages.create(
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 10000},
    tools=ALL_TOOLS,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": complex_case}],
    # يتطلب beta header
    betas=["interleaved-thinking-2025-05-14"]
)

# مثال على ما يحدث داخلياً:
# 1. [thinking] "الحالة: AMD ثنائي + hemianopia يمنى بعد سكتة.
#     هذا مزيج نادر — أحتاج بروتوكول مخصص..."
#
# 2. [tool_use] search_knowledge_base("AMD rehabilitation protocol")
#
# 3. [thinking] "بروتوكول AMD يركز على Eccentric Viewing لكن
#     Hemianopia اليمنى ستؤثر على المسح → أحتاج دمج Scanning Training
#     مع EVT. أبحث عن أبحاث عن هذا المزيج..."
#
# 4. [tool_use] search_pubmed("hemianopia combined macular degeneration rehabilitation")
#
# 5. [thinking] "وجدت مقالة واحدة فقط. Evidence محدود.
#     سأبني خطة مبنية على مبادئ كلا البروتوكولين مع تعديلات..."
#
# 6. [text] الاستجابة النهائية المتكاملة
```

-----

## الفصل 13: Tool Use — منظومة الأدوات

### 13.1 القائمة الكاملة — 12 أداة متخصصة

الأدوات الست الأولى (PubMed + RAG + Visual Calculator + Document + Think) مُفصّلة في الإصدار السابق. هنا الأدوات الجديدة التي تُكمل المنظومة:

```python
ALL_TOOLS = [
    # ═══ 1-3: البحث العلمي ═══
    search_pubmed_tool,         # بحث PubMed
    fetch_article_details_tool, # تفاصيل مقالة بـ PMID
    search_knowledge_base_tool, # بحث RAG المحلي

    # ═══ 4-5: الحسابات ═══
    visual_calculator_tool,         # حسابات بصرية عامة
    arabic_reading_calculator_tool, # حسابات القراءة العربية ← جديد

    # ═══ 6-7: التقييم ═══
    functional_assessment_tool,  # التقييم الوظيفي الشامل ← جديد
    depression_screening_tool,   # فحص الاكتئاب ← جديد

    # ═══ 8: الأجهزة ═══
    device_recommender_tool,     # قاعدة بيانات الأجهزة ← جديد

    # ═══ 9: النتائج ═══
    outcome_tracker_tool,        # تتبع النتائج والتقدم ← جديد

    # ═══ 10-11: التوثيق ═══
    generate_document_tool,      # إنشاء تقارير
    referral_generator_tool,     # خطابات إحالة ← جديد

    # ═══ 12: التفكير ═══
    think_tool,                  # أداة التفكير المنظم
]
```

### 13.2 الأدوات الجديدة — التعريفات

```python
# ═══ أداة تتبع النتائج ═══
outcome_tracker_tool = {
    "name": "outcome_tracker",
    "description": """تتبع نتائج التأهيل عبر الزمن.
    يُخزن ويقارن: حدة الإبصار، سرعة القراءة، CPS، مقاييس جودة الحياة،
    نتائج ADL، ومقاييس نفسية. يُنتج رسوم بيانية للتقدم.
    يُحدد: هل المريض يتحسن؟ هل نحتاج تعديل الخطة؟""",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["record", "compare", "trend", "alert"],
                "description": "record: تسجيل قياس جديد, compare: مقارنة قبل/بعد, trend: اتجاه عبر الزمن, alert: تنبيه على تغيرات"
            },
            "patient_id": {"type": "string"},
            "measure_type": {
                "type": "string",
                "enum": [
                    "visual_acuity", "reading_speed", "critical_print_size",
                    "contrast_sensitivity", "visual_field",
                    "vfq25_score", "lvqol_score", "ivi_score",
                    "adl_independence", "mobility_score",
                    "phq9_score", "patient_satisfaction"
                ]
            },
            "value": {"type": "number"},
            "date": {"type": "string", "description": "ISO 8601"},
            "notes": {"type": "string"}
        },
        "required": ["action", "measure_type"]
    }
}

# ═══ أداة الإحالة ═══
referral_generator_tool = {
    "name": "referral_generator",
    "description": """إنشاء خطابات إحالة مهنية.
    يُنتج خطاب إحالة مُنسق حسب التخصص المُحال إليه،
    مع ملخص الحالة والسبب والمعلومات المطلوبة.
    ⚠️ يتطلب موافقة المستخدم قبل الإنشاء.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "referral_to": {
                "type": "string",
                "enum": [
                    "ophthalmologist", "optometrist", "retina_specialist",
                    "neuro_ophthalmologist", "occupational_therapist",
                    "orientation_mobility_specialist", "psychologist",
                    "psychiatrist", "social_worker", "special_educator",
                    "assistive_technology_specialist", "vocational_counselor"
                ]
            },
            "reason": {"type": "string"},
            "urgency": {
                "type": "string",
                "enum": ["routine", "soon", "urgent"]
            },
            "case_summary": {"type": "object"},
            "specific_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "أسئلة محددة للمتخصص المُحال إليه"
            }
        },
        "required": ["referral_to", "reason", "case_summary"]
    }
}
```

### 13.3 Tool Loop — حلقة استدعاء الأدوات

```python
import anthrop

async def run_with_tool_loop(
    user_message: str,
    images: list = None,
    session_context: dict = None
) -> str:
    """تشغيل Claude مع حلقة أدوات كاملة"""

    # بناء المحتوى
    content = []
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

    # سياق الجلسة (إن وُجد)
    system = SYSTEM_PROMPT
    if session_context:
        system += f"\n\n<session_context>\n{format_context(session_context)}\n</session_context>"

    messages = [{"role": "user", "content": content}]

    # حلقة الأدوات
    while True:
        response = client.messages.create(
            max_tokens=16000,
            system=system,
            messages=messages,
            tools=ALL_TOOLS,
            thinking={"type": "enabled", "budget_tokens": 10000}
        )

        # إذا انتهى Claude من الإجابة
        if response.stop_reason == "end_turn":
            return extract_final_text(response)

        # إذا يريد استدعاء أدوات
        if response.stop_reason == "tool_use":
            # أضف رد  (مع tool_use blocks)
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # نفّذ كل أداة مطلوبة
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            # أرسل النتائج لـ Claude
            messages.append({
                "role": "user",
                "content": tool_results
            })

        # حماية من الحلقات اللانهائية
        if len(messages) > 20:
            return "⚠️ تم الوصول للحد الأقصى من الاستدعاءات."


async def execute_tool(name: str, input_data: dict):
    """تنفيذ الأداة المطلوبة"""
    tool_handlers = {
        "search_pubmed": handle_pubmed_search,
        "fetch_article_details": handle_article_fetch,
        "search_knowledge_base": handle_rag_search,
        "visual_calculator": handle_visual_calc,
        "arabic_reading_calculator": handle_arabic_calc,
        "functional_assessment": handle_assessment,
        "depression_screening": handle_depression,
        "device_recommender": handle_device_recommend,
        "outcome_tracker": handle_outcome_track,
        "generate_document": handle_document_gen,
        "referral_generator": handle_referral_gen,
        "think": lambda x: x,  # Think tool يرجع المدخل كما هو
    }

    handler = tool_handlers.get(name)
    if handler:
        return await handler(input_data)
    return {"error": f"أداة غير معروفة: {name}"}
```

### 13.4 مخطط تدفق الأدوات — أيها تُستدعى ومتى

```
سؤال المستخدم
      │
      ├── "ما تصنيف VA 6/60؟"
      │   └── visual_calculator (مباشرة)
      │
      ├── "مريض AMD، VA 6/60، يريد قراءة القرآن"
      │   ├── 1. think (تفكير في الحالة)
      │   ├── 2. search_knowledge_base("AMD protocol")
      │   ├── 3. arabic_reading_calculator(quran_magnification)
      │   ├── 4. device_recommender(near_reading, VA=6/60)
      │   └── 5. الاستجابة المتكاملة
      │
      ├── "مريض سكتة + hemianopia + اكتئاب"
      │   ├── 1. think (حالة معقدة — تفكير مطوّل)
      │   ├── 2. search_knowledge_base("hemianopia protocol")
      │   ├── 3. search_pubmed("hemianopia rehabilitation stroke")
      │   ├── 4. depression_screening(PHQ-9, responses)
      │   ├── 5. device_recommender(prisms, hemianopia)
      │   ├── 6. referral_generator(psychologist) ← إذا PHQ-9 عالي
      │   └── 7. الاستجابة + خطة + إحالات
      │
      ├── "طفل CVI Range 3، ما البرنامج؟"
      │   ├── 1. search_knowledge_base("CVI phase 1 protocol")
      │   ├── 2. search_pubmed("cortical visual impairment intervention")
      │   └── 3. خطة تفصيلية بحسب المرحلة
      │
      └── "أنشئ تقرير SOAP لهذا المريض"
          ├── 1. Claude يسأل: "هل توافق على إنشاء التقرير؟"
          ├── 2. [بعد الموافقة] generate_document(SOAP, case_data)
          └── 3. التقرير المنسق
```

-----

## الفصل 14: PubMed والمصادر العلمية

### 14.1 خياران للتنفيذ

```python
# ═══ الخيار 1: E-Utilities المباشر (مُوصى به) ═══

import requests

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_API_KEY = "your-key"  # 10 req/sec مع API key

async def search_pubmed(query: str, max_results: int = 5,
                        date_range: str = None,
                        article_types: list = None) -> dict:
    """بحث PubMed عبر E-Utilities"""

    # بناء الاستعلام
    search_query = query
    if article_types:
        type_filter = " OR ".join(f"{t}[pt]" for t in article_types)
        search_query += f" AND ({type_filter})"
    if date_range:
        search_query += f" AND {date_range}[dp]"

    # ESearch — الحصول على PMIDs
    search_params = {
        "db": "pubmed",
        "term": search_query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "api_key": NCBI_API_KEY
    }
    search_resp = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=search_params)
    pmids = search_resp.json()["esearchresult"]["idlist"]

    if not pmids:
        return {"results": [], "total": 0}

    # ESummary — جلب البيانات الوصفية
    summary_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "api_key": NCBI_API_KEY
    }
    summary_resp = requests.get(f"{NCBI_BASE}/esummary.fcgi", params=summary_params)
    articles = summary_resp.json()["result"]

    results = []
    for pmid in pmids:
        if pmid in articles:
            art = articles[pmid]
            results.append({
                "pmid": pmid,
                "title": art.get("title", ""),
                "authors": [a["name"] for a in art.get("authors", [])[:3]],
                "journal": art.get("source", ""),
                "year": art.get("pubdate", "")[:4],
                "doi": art.get("elocationid", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })

    return {"results": results, "total": len(results)}


async def fetch_article_abstract(pmid: str) -> dict:
    """جلب الملخص الكامل لمقالة عبر PMID"""

    params = {
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "text",
        "api_key": NCBI_API_KEY
    }
    resp = requests.get(f"{NCBI_BASE}/efetch.fcgi", params=params)

    return {
        "pmid": pmid,
        "abstract": resp.text,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    }
```

```python
# ═══ الخيار 2: PubMed MCP Server ═══
# أسهل في الإعداد، يتكامل مع Claude Desktop

# mcp_config.json
{
    "mcpServers": {
        "pubmed": {
            "command": "uvx",
            "args": ["--from", "pubmed-mcp-server", "pubmed_mcp_server"]
        }
    }
}
# يوفر أدوات: search_pubmed, get_article_details, download_full_text
```

### 14.2 استراتيجيات البحث الفعال

```python
SEARCH_STRATEGIES = {
    "clinical_question": {
        "template": "{condition} AND {intervention} AND (rehabilitation OR low vision)",
        "example": "macular degeneration AND eccentric viewing AND rehabilitation",
        "filters": "Clinical Trial[pt] OR Randomized Controlled Trial[pt]"
    },
    "latest_guidelines": {
        "template": "{condition} AND (guideline[pt] OR practice guideline[pt])",
        "date": "last 5 years",
        "example": "low vision rehabilitation AND guideline[pt]"
    },
    "systematic_review": {
        "template": "{topic} AND (systematic review[pt] OR meta-analysis[pt])",
        "example": "assistive technology visual impairment AND systematic review[pt]"
    },
    "pediatric": {
        "template": "{condition} AND (child OR pediatric OR infant) AND rehabilitation",
        "example": "cortical visual impairment AND child AND intervention"
    }
}
```

-----

## الفصل 15: Vision — تحليل الصور الطبية

### 15.1 أنواع الصور المدعومة وكيفية التحليل

```python
SUPPORTED_IMAGE_TYPES = {
    "oct_scan": {
        "description": "Optical Coherence Tomography",
        "analysis_protocol": [
            "1. تحديد نوع الفحص (macular, RNFL, optic disc)",
            "2. وصف الطبقات الشبكية المرئية",
            "3. البحث عن: وذمة، ترقق، انفصال، سوائل",
            "4. قياسات السماكة (إن ظاهرة)",
            "5. مقارنة بالمعدل الطبيعي",
            "6. الربط بالتشخيص والتأثير التأهيلي"
        ],
        "rehab_relevance": "يُساعد في فهم استقرار الحالة ← هل نبدأ التأهيل أم ننتظر؟"
    },
    "visual_field": {
        "description": "Humphrey / Goldmann Visual Field",
        "analysis_protocol": [
            "1. نوع الفحص (24-2, 30-2, 10-2, full field)",
            "2. مؤشرات الموثوقية (fixation losses, false +/-)",
            "3. نمط الفقدان (مركزي, محيطي, نصفي, أنبوبي)",
            "4. Mean Deviation (MD) و Pattern Standard Deviation (PSD)",
            "5. التقدم مقارنة بفحوصات سابقة (إن وُجدت)",
            "6. التأثير الوظيفي: ما الأنشطة المتأثرة؟"
        ],
        "rehab_relevance": "يُحدد نوع تدريب التنقل + القراءة المطلوب"
    },
    "fundus_photo": {
        "description": "صورة قاع العين",
        "analysis_protocol": [
            "1. القرص البصري (حجم, لون, cup-to-disc ratio)",
            "2. البقعة (foveal reflex, drusen, scars, hemorrhage)",
            "3. الأوعية (تضيق, AV nicking, neovascularization)",
            "4. الشبكية المحيطية (نزيف, إفرازات, تنكس)",
            "5. الربط بالتشخيص المعروف"
        ]
    },
    "clinical_report": {
        "description": "تقارير مكتوبة/مطبوعة",
        "analysis": "استخراج البيانات السريرية الرئيسية وتنظيمها"
    },
    "patient_environment": {
        "description": "صور بيئة المريض (منزل/عمل)",
        "analysis_protocol": [
            "1. تقييم الإضاءة",
            "2. تقييم مخاطر التعثر/السقوط",
            "3. فرص التحسين (تباين، تنظيم، إضاءة)",
            "4. توصيات تعديلات بيئية محددة"
        ],
        "rehab_relevance": "مباشر — تعديلات بيئية عملية"
    }
}
```

### 15.2 كود تحليل الصور

```python
import base64

async def analyze_medical_image(image_path: str, clinical_context: str,
                                image_type: str = "auto") -> str:
    """تحليل صورة طبية مع سياق سريري"""

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # تحديد نوع الصورة
    media_type = "image/jpeg"
    if image_path.endswith(".png"):
        media_type = "image/png"

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT + """
<image_analysis_mode>
أنت الآن في وضع تحليل الصور الطبية.
اتبع البروتوكول التالي بدقة:

1. **الوصف** — ما أراه في الصورة (موضوعي، بدون تفسير)
2. **التفسير** — ماذا تعني هذه النتائج سريرياً
3. **الربط التأهيلي** — كيف يؤثر هذا على خطة التأهيل
4. **التوصيات** — ما يجب فعله بناءً على هذا التحليل

⚠️ تذكّر: هذا تحليل مساعد — ليس بديلاً عن تفسير المتخصص.
⚠️ لا تدّعِ رؤية تفاصيل دقيقة في صور منخفضة الجودة.
</image_analysis_mode>
""",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": f"""
السياق السريري:
{clinical_context}

حلّل هذه الصورة وفقاً لبروتوكول التحليل المنهجي.
ركّز على الجانب التأهيلي: كيف تؤثر النتائج على خطة التأهيل.
"""
                }
            ]
        }],
        thinking={"type": "enabled", "budget_tokens": 8000}
    )

    return extract_final_text(response)


# مقارنة صور متعددة (قبل وبعد العلاج)
async def compare_images(images: list, comparison_context: str) -> str:
    """مقارنة صور طبية متعددة"""

    content = []
    for i, img in enumerate(images):
        with open(img["path"], "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": data}
        })
        content.append({
            "type": "text",
            "text": f"📌 الصورة {i+1}: {img['label']}"
        })

    content.append({
        "type": "text",
        "text": f"""
قارن بين هذه الصور:
{comparison_context}

حدد: التغيرات، التحسن/التدهور، التأثير على خطة التأهيل.
"""
    })

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        thinking={"type": "enabled", "budget_tokens": 10000}
    )

    return extract_final_text(response)
```

-----

## الفصل 16: RAG — بناء القاعدة المعرفية

### 16.1 الهيكل الكامل للقاعدة المعرفية

```
📁 knowledge_base/
│
├── 📁 assessments/           ← الفصل 2
│   ├── protocols/            (بروتوكولات التقييم)
│   ├── forms/                (نماذج جاهزة)
│   └── scoring/              (جداول تقييم)
│
├── 📁 diagnosis_protocols/   ← الفصل 3
│   ├── retinal/              (AMD, DR, RP, Stargardt)
│   ├── optic_nerve/          (Glaucoma, ON, OA)
│   ├── corneal/              (opacity, keratoconus)
│   ├── neurological/         (hemianopia, neglect, TBI, nystagmus)
│   ├── congenital/           (albinism, aniridia, cataract)
│   └── other/
│
├── 📁 devices/               ← الفصل 4
│   ├── optical_magnifiers/   (handheld, stand, spectacle, telescope)
│   ├── electronic/           (CCTV, portable, tablet, smart glasses)
│   ├── filters/              (absorptive, prisms, occlusion)
│   ├── non_optical/          (screen readers, talking devices, apps)
│   └── environmental/        (lighting, contrast, organization)
│
├── 📁 training/              ← الفصل 5
│   ├── eccentric_viewing/    (EVT protocol steps)
│   ├── scanning/             (scanning training protocol)
│   ├── steady_eye/           (steady eye strategy)
│   ├── tracking/             (eye tracking exercises)
│   ├── hand_eye/             (coordination exercises)
│   └── reading_training/     (reading speed improvement)
│
├── 📁 neuro_visual/          ← الفصل 6
│   ├── hemianopia/           (scanning, prisms, reading)
│   ├── visual_neglect/       (awareness, scanning, functional)
│   ├── tbi_vision/           (PTVS, convergence, accommodation)
│   ├── diplopia/             (prisms, occlusion, exercises)
│   └── nystagmus/            (null point, prisms, surgery)
│
├── 📁 pediatric/             ← الفصل 7
│   ├── cvi/                  (Roman Range, phases, strategies)
│   ├── learning_media/       (LMA protocol, decision framework)
│   ├── early_intervention/   (0-3 years protocols)
│   ├── school_age/           (accommodations, IEP, technology)
│   └── developmental/        (milestones, play-based assessment)
│
├── 📁 psychosocial/          ← الفصل 8
│   ├── adjustment_stages/    (grief model, intervention per stage)
│   ├── depression_screening/ (PHQ, GDS, referral criteria)
│   ├── support_groups/       (resources, programs)
│   └── family_education/     (caregiver guides)
│
├── 📁 mobility_adl/          ← الفصل 9
│   ├── orientation_mobility/ (sighted guide, cane, GPS)
│   ├── daily_living/         (kitchen, medication, money, etc.)
│   └── vocational/           (workplace modifications)
│
├── 📁 arabic_specific/       ← الفصل 10
│   ├── reading_protocols/    (RTL adaptations)
│   ├── quran_reading/        (devices, settings, tips)
│   └── arabic_assessments/   (available tools, adaptations)
│
├── 📁 clinical_guidelines/   ← إرشادات عامة
│   ├── who_icd11/
│   ├── aao_guidelines/
│   ├── rnib_standards/
│   └── ico_guidelines/
│
└── 📁 outcome_measures/      ← الفصل 19
    ├── vfq25/
    ├── lvqol/
    ├── ivi/
    ├── mnread_parameters/
    └── adl_scales/
```

### 16.2 Contextual Embeddings — تقنية Anthropic

```python
# ═══ الفهرسة مع سياق (يُقلل فشل الاسترجاع 49%) ═══

from anthropic import Anthropic
from langchain.text_splitter import RecursiveCharacterTextSplitter

client = Anthropic()

def chunk_document(text: str, metadata: dict) -> list:
    """تقسيم المستند مع إضافة سياق لكل جزء"""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". "]
    )
    raw_chunks = splitter.split_text(text)

    contextualized_chunks = []
    for chunk in raw_chunks:
        # Claude يُنشئ سياقاً قصيراً لكل جزء
        context = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""<document>
{text[:2000]}  <!-- أول 2000 حرف من المستند الكامل -->
</document>

<chunk>
{chunk}
</chunk>

اكتب جملة واحدة قصيرة تصف سياق هذا الجزء ضمن المستند الكامل.
ابدأ بـ: "هذا الجزء من..."
"""
            }]
        ).content[0].text

        contextualized_chunks.append({
            "text": f"{context}\n\n{chunk}",
            "original_chunk": chunk,
            "context": context,
            "metadata": metadata
        })

    return contextualized_chunks
```

### 16.3 Hybrid Search (BM25 + Semantic)

```python
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import numpy as np

# نموذج الـ embedding — يدعم العربية والإنجليزية
embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

class HybridSearchEngine:
    def __init__(self, chunks: list):
        self.chunks = chunks
        texts = [c["text"] for c in chunks]

        # BM25 (keyword-based)
        tokenized = [t.split() for t in texts]
        self.bm25 = BM25Okapi(tokenized)

        # Semantic embeddings
        self.embeddings = embed_model.encode(texts, normalize_embeddings=True)

    def search(self, query: str, top_k: int = 5,
               category_filter: str = None,
               bm25_weight: float = 0.4,
               semantic_weight: float = 0.6) -> list:
        """بحث هجين: BM25 + Semantic مع دمج Reciprocal Rank Fusion"""

        # تصفية حسب الفئة
        candidates = self.chunks
        if category_filter:
            candidates = [c for c in candidates
                         if c["metadata"].get("category") == category_filter]

        # BM25 scores
        bm25_scores = self.bm25.get_scores(query.split())

        # Semantic scores
        query_embedding = embed_model.encode([query], normalize_embeddings=True)
        semantic_scores = np.dot(self.embeddings, query_embedding.T).flatten()

        # Reciprocal Rank Fusion
        bm25_ranks = np.argsort(-bm25_scores)
        semantic_ranks = np.argsort(-semantic_scores)

        rrf_scores = {}
        k = 60  # RRF constant
        for rank, idx in enumerate(bm25_ranks):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + bm25_weight / (k + rank + 1)
        for rank, idx in enumerate(semantic_ranks):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + semantic_weight / (k + rank + 1)

        # ترتيب وإرجاع
        sorted_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]

        return [{
            "text": self.chunks[i]["text"],
            "metadata": self.chunks[i]["metadata"],
            "score": rrf_scores[i]
        } for i in sorted_indices]
```

### 16.4 البديل للقواعد الصغيرة: Prompt Caching

```python
# إذا القاعدة المعرفية أقل من 200K tokens:
# استخدم Prompt Caching بدل Vector DB — أبسط وأسرع

# وفّر 90% من التكلفة + 50% من الوقت
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT
        },
        {
            "type": "text",
            "text": full_knowledge_base_text,  # كل المحتوى السريري
            "cache_control": {"type": "ephemeral"}  # يُخزن مؤقتاً 5 دقائق
        }
    ],
    messages=[{"role": "user", "content": user_query}]
)
# ✅ Claude يبحث في كل القاعدة مباشرة بدون Vector DB
# ✅ ممتاز للنماذج الأولية (prototyping)
```

-----

## الفصل 17: Prompt Chaining — سلاسل العمل السريرية

### 17.1 السلسلة الرئيسية: التقييم الشامل

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Chain 1          Chain 2          Chain 3          Chain 4       │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐   │
│  │الاستقبال │────▶│التقييم  │────▶│البحث    │────▶│الخطة    │   │
│  │والتاريخ │     │السريري  │     │العلمي   │     │العلاجية │   │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘   │
│       │               │               │               │          │
│   نص + أسئلة     نص + صور       tools مفعلة     XML مهيكل     │
│                                                       │          │
│                                    Chain 5          Chain 6      │
│                                   ┌─────────┐     ┌─────────┐   │
│                                   │المراجعة │────▶│التوثيق  │   │
│                                   │الذاتية  │     │(بموافقة)│   │
│                                   └─────────┘     └─────────┘   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 17.2 التنفيذ الكامل

```python
async def comprehensive_assessment_chain(
    patient_data: str,
    images: list = None,
    tools: list = ALL_TOOLS
) -> dict:
    """سلسلة التقييم الشامل — 6 مراحل"""

    results = {}

    # ═══ Chain 1: الاستقبال وجمع المعلومات ═══
    results["intake"] = await chain_call(
        phase="intake",
        system_addition="""أنت في مرحلة الاستقبال.
اجمع وصنّف كل المعلومات المتاحة عن الحالة.
إذا نقصت معلومات ضرورية، حددها بوضوح.
أخرج XML: <intake><demographics/><diagnosis/><history/><complaints/><goals/><missing_info/></intake>""",
        user_message=f"بيانات الحالة:\n{patient_data}",
        images=None,
        tools=None
    )

    # ═══ Chain 2: التقييم البصري والوظيفي ═══
    results["assessment"] = await chain_call(
        phase="assessment",
        system_addition="""أنت في مرحلة التقييم.
حلّل البيانات البصرية والوظيفية بعمق.
إذا أُرسلت صور طبية، حللها وفق البروتوكول المنهجي.
أخرج XML: <assessment><visual_function/><functional_impact/><classification/><image_analysis/><priorities/></assessment>""",
        user_message=f"بناءً على بيانات الاستقبال:\n<intake>{results['intake']}</intake>\n\nقم بالتقييم الشامل.",
        images=images,
        tools=[functional_assessment_tool, visual_calculator_tool, arabic_reading_calculator_tool]
    )

    # ═══ Chain 3: البحث العلمي ═══
    results["evidence"] = await chain_call(
        phase="evidence_search",
        system_addition="""أنت في مرحلة البحث العلمي.
ابحث عن أحدث الأدلة المتعلقة بهذه الحالة.
استخدم search_pubmed وsearch_knowledge_base.
لكل توصية، حدد مستوى الدليل.""",
        user_message=f"""بناءً على التقييم:
<assessment>{results['assessment']}</assessment>

ابحث عن:
1. بروتوكولات التأهيل لهذا التشخيص
2. فعالية التدخلات المقترحة
3. إرشادات سريرية حديثة
4. خصوصيات عمر المريض (إن كان طفلاً أو كبير سن)
""",
        tools=[search_pubmed_tool, fetch_article_details_tool, search_knowledge_base_tool]
    )

    # ═══ Chain 4: بناء الخطة العلاجية ═══
    results["plan"] = await chain_call(
        phase="treatment_plan",
        system_addition="""أنت في مرحلة بناء الخطة العلاجية.""",
        user_message=f"""بناءً على:
<intake>{results['intake']}</intake>
<assessment>{results['assessment']}</assessment>
<evidence>{results['evidence']}</evidence>

ضع خطة علاجية شاملة:

1. **أهداف SMART** — قصيرة/متوسطة/طويلة المدى
2. **الأجهزة المساعدة** — مع المواصفات وطريقة التدريب
3. **التدريبات** — البروتوكول المفصل خطوة بخطوة
4. **التعديلات البيئية** — محددة وعملية
5. **الدعم النفسي** — تقييم + تدخل + إحالة إذا لزم
6. **الإحالات** — لأي تخصصات أخرى مطلوبة
7. **الجدول الزمني** — عدد الجلسات والتكرار
8. **معايير النجاح** — مؤشرات قابلة للقياس
9. **خطة المتابعة** — مواعيد إعادة التقييم

أخرج XML: <treatment_plan>...</treatment_plan>
""",
        tools=[device_recommender_tool, depression_screening_tool, referral_generator_tool]
    )

    # ═══ Chain 5: المراجعة الذاتية ═══
    results["review"] = await chain_call(
        phase="quality_review",
        system_addition="""أنت مراجع جودة سريرية. راجع بعين ناقدة.""",
        user_message=f"""راجع الخطة العلاجية:
<plan>{results['plan']}</plan>

تحقق من:
✅ هل الأهداف واقعية وقابلة للقياس (SMART)؟
✅ هل التدخلات مدعومة بأدلة علمية كافية؟
✅ هل تم مراعاة موانع الاستعمال؟
✅ هل تم مراعاة عوامل المريض (عمر، معرفي، حركي، نفسي)؟
✅ هل الأجهزة مناسبة للقدرات الحركية والمعرفية؟
✅ هل الجدول الزمني منطقي؟
✅ هل تم تغطية الجانب النفسي والاجتماعي؟
✅ هل هناك فجوات أو تناقضات؟

أخرج: <quality_review><scores/><issues/><recommendations/><revised_plan_if_needed/></quality_review>
""",
        tools=None
    )

    # ═══ Chain 6: التوثيق (يحتاج موافقة) ═══
    results["documentation_ready"] = True
    results["documentation_pending_consent"] = True

    return results


async def chain_call(phase: str, system_addition: str,
                     user_message: str, images: list = None,
                     tools: list = None) -> str:
    """استدعاء حلقة واحدة في السلسلة"""

    content = []
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

    kwargs = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT + f"\n\n<current_phase>{system_addition}</current_phase>",
        "messages": [{"role": "user", "content": content}],
        "thinking": {"type": "enabled", "budget_tokens": 8000}
    }
    if tools:
        kwargs["tools"] = tools

    response = await run_with_tool_loop_internal(**kwargs)
    return extract_text(response)
```

-----

# ═══════════════════════════════════════════════════

# الجزء الثالث: التشغيل والجودة

# ═══════════════════════════════════════════════════

-----

## الفصل 18: التوثيق والتقارير

### 18.1 القاعدة الذهبية: لا توثيق بدون موافقة

```python
async def request_consent_then_document(case_results: dict, doc_type: str):
    """طلب الموافقة ثم إنشاء التوثيق"""

    # عرض ملخص ما سيتم توثيقه
    preview = generate_preview(case_results, doc_type)

    consent_message = f"""
📋 **طلب موافقة على التوثيق**

بناءً على تقييمنا، يمكنني إعداد: **{doc_type}**

سيتضمن التقرير:
{preview}

هل توافق على إنشاء هذا التقرير؟
⚠️ لن يتم تخزين بيانات شخصية بعد انتهاء الجلسة.
"""
    return consent_message
    # التنفيذ الفعلي يحدث فقط بعد تأكيد المستخدم
```

### 18.2 تنسيقات التوثيق المدعومة

```python
DOCUMENT_TYPES = {
    "soap_note": {
        "name": "SOAP Note",
        "sections": ["Subjective", "Objective", "Assessment", "Plan"],
        "use_case": "توثيق الزيارة السريرية",
        "template": """
<soap>
  <subjective>
    الشكوى الرئيسية: {chief_complaint}
    تاريخ الحالة: {history}
    الأهداف: {goals}
  </subjective>
  <objective>
    حدة الإبصار: {va}
    حساسية التباين: {cs}
    المجال البصري: {vf}
    القراءة: CPS={cps}, MRS={mrs}
    فحوصات إضافية: {additional}
  </objective>
  <assessment>
    التشخيص التأهيلي: {rehab_diagnosis}
    تصنيف WHO: {who_class}
    التصنيف الوظيفي: {functional_class}
    فحص الاكتئاب: {depression_screen}
  </assessment>
  <plan>
    الأجهزة: {devices}
    التدريبات: {training}
    التعديلات البيئية: {env_mods}
    الإحالات: {referrals}
    المتابعة: {follow_up}
  </plan>
</soap>"""
    },

    "icf_report": {
        "name": "ICF Framework Report",
        "sections": ["Body Functions", "Body Structures",
                      "Activities & Participation", "Environmental Factors",
                      "Personal Factors"],
        "use_case": "تقرير تأهيلي شامل وفق إطار ICF",
    },

    "referral_letter": {
        "name": "خطاب إحالة",
        "sections": ["المعلومات الأساسية", "ملخص الحالة",
                      "سبب الإحالة", "الأسئلة المحددة"],
        "use_case": "إحالة لمتخصص آخر",
    },

    "progress_note": {
        "name": "ملاحظة تقدم",
        "sections": ["الأهداف السابقة", "التقدم المحرز",
                      "القياسات الحالية", "التعديلات", "الخطة المحدثة"],
        "use_case": "متابعة دورية",
    },

    "treatment_plan": {
        "name": "خطة علاجية",
        "sections": ["التشخيص", "الأهداف", "التدخلات",
                      "الجدول", "معايير النجاح", "المتابعة"],
        "use_case": "خطة العلاج الشاملة",
    },

    "school_report": {
        "name": "تقرير مدرسي",
        "sections": ["التقييم البصري", "التأثير على التعلم",
                      "التوصيات الصفية", "الأجهزة", "التعديلات"],
        "use_case": "تقرير للمدرسة عن طفل ضعيف البصر",
    }
}
```

-----

## الفصل 19: نظام قياس النتائج والمتابعة

### 19.1 مقاييس النتائج المعتمدة

```yaml
outcome_measures:
  visual_function:
    visual_acuity:
      tools: ["ETDRS", "LogMAR", "Snellen"]
      frequency: "كل زيارة"
      meaningful_change: "≥ 0.1 LogMAR (سطر واحد)"

    reading_performance:
      tools: ["MNREAD"]
      parameters:
        - "Reading Acuity (RA) — أصغر حجم قابل للقراءة"
        - "Critical Print Size (CPS) — أصغر حجم بسرعة كاملة"
        - "Maximum Reading Speed (MRS) — سرعة القراءة القصوى"
      frequency: "قبل التدخل + 4 أسابيع + 3 أشهر"
      meaningful_change: "≥ 10 words/min في MRS أو ≥ 0.1 LogMAR في CPS"

    contrast_sensitivity:
      tools: ["Pelli-Robson", "Mars"]
      frequency: "قبل التدخل + 3 أشهر"
      meaningful_change: "≥ 0.15 log units"

  patient_reported:
    quality_of_life:
      tools:
        - name: "VFQ-25"
          description: "25-item Visual Function Questionnaire"
          domains: ["general vision", "near activities", "distance activities",
                    "driving", "social functioning", "mental health", "dependency"]
          meaningful_change: "≥ 5 points composite score"

        - name: "LVQOL"
          description: "Low Vision Quality of Life Questionnaire"
          domains: ["basic aspects", "adjustment", "reading/fine work", "mobility"]

        - name: "IVI"
          description: "Impact of Vision Impairment"
          domains: ["reading", "mobility", "emotional well-being"]

    functional_independence:
      tools:
        - name: "ADL Checklist"
          domains: ["personal care", "kitchen", "medication", "money",
                    "communication", "mobility"]
          scoring: "0=dependent, 1=with help, 2=with device, 3=independent"

        - name: "Activity Inventory"
          description: "VA LV VFQ-48 — مقياس شامل للقدرة الوظيفية"

  psychological:
    tools:
      - name: "PHQ-9"
        frequency: "استقبال + 3 أشهر + 6 أشهر"
        meaningful_change: "≥ 5 points"
      - name: "GDS-15"
        for: "كبار السن"
```

### 19.2 كيف يعمل تتبع النتائج

```
الزيارة الأولى                    متابعة 1 (4 أسابيع)         متابعة 2 (3 أشهر)
─────────────                     ────────────────────          ──────────────────
outcome_tracker.record(            outcome_tracker.record(       outcome_tracker.record(
  "reading_speed", 45 wpm)           "reading_speed", 62 wpm)     "reading_speed", 78 wpm)
outcome_tracker.record(            outcome_tracker.record(       outcome_tracker.record(
  "vfq25_score", 42)                 "vfq25_score", 55)           "vfq25_score", 68)
                                                                          │
                                                                          ▼
                                                              outcome_tracker.trend(
                                                                "reading_speed")
                                                                          │
                                                                          ▼
                                                              ┌────────────────────┐
                                                              │  📊 رسم بياني      │
                                                              │                    │
                                                              │  78 ─      ●       │
                                                              │  62 ─   ●          │
                                                              │  45 ─ ●            │
                                                              │     ─────────────  │
                                                              │     V1  M1   M2    │
                                                              │                    │
                                                              │  ✅ تحسن 73%       │
                                                              │  ✅ أعلى من الهدف  │
                                                              └────────────────────┘
```

-----

## الفصل 20: الفريق متعدد التخصصات والإحالة

### 20.1 خريطة الفريق

```
                    ┌───────────────────────┐
                    │   طبيب العيون         │
                    │   (التشخيص + العلاج)  │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  أخصائي التأهيل       │
                    │  البصري               │
                    │  (المنسق الرئيسي)     │
                    └───────────┬───────────┘
                                │
          ┌──────────┬──────────┼──────────┬──────────┬──────────┐
          ▼          ▼          ▼          ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
    │ معالج    ││ أخصائي  ││ أخصائي  ││ معلم    ││ أخصائي  ││ أخصائي  │
    │ وظيفي   ││ تنقل    ││ نفسي    ││ تربية   ││ تقنية   ││ اجتماعي│
    │ (OT)     ││ (O&M)    ││          ││ خاصة    ││ مساعدة  ││          │
    └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘
    ADL         التنقل      الدعم       التعليم    الأجهزة     الموارد
    المنزل      العصا       النفسي      IEP        والبرامج   المجتمعية
    العمل       البيئة      الاكتئاب    المناهج    التدريب    الدعم المالي
```

### 20.2 معايير الإحالة لكل تخصص

```python
REFERRAL_CRITERIA = {
    "ophthalmologist": {
        "when": [
            "تغير مفاجئ في الرؤية أثناء التأهيل",
            "أعراض جديدة (ومضات، عوائم كثيفة، ستارة)",
            "حاجة لتحديث التشخيص أو العلاج",
            "موعد الفحص الدوري (كل 6-12 شهر)"
        ],
        "urgency": "urgent إذا أعراض مفاجئة, routine إذا فحص دوري"
    },

    "occupational_therapist": {
        "when": [
            "صعوبات ADL لا تُحل بالأجهزة البصرية فقط",
            "حاجة لتعديلات بيئية معقدة",
            "مريض كبير سن مع مشاكل حركية مصاحبة",
            "تأهيل مهني (workplace modifications)"
        ]
    },

    "orientation_mobility_specialist": {
        "when": [
            "مجال بصري < 20 درجة (أنبوبي)",
            "صعوبة التنقل الخارجي",
            "تاريخ سقوط أو حوادث",
            "فقدان بصر حديث مع عدم ثقة في التنقل"
        ]
    },

    "psychologist": {
        "when": [
            "PHQ-9 ≥ 10",
            "علامات اكتئاب أو قلق مستمر",
            "رفض التأهيل بسبب الحالة النفسية",
            "أفكار انتحارية (⚠️ طارئ)",
            "صعوبة التكيف بعد 6+ أشهر"
        ]
    },

    "special_educator": {
        "when": [
            "طفل في سن المدرسة مع ضعف بصر",
            "حاجة لـ IEP أو تعديلات صفية",
            "تقييم Learning Media Assessment",
            "CVI يؤثر على التعلم"
        ]
    },

    "assistive_technology_specialist": {
        "when": [
            "حاجة لتقنيات معقدة (screen readers, JAWS)",
            "تكامل أجهزة متعددة",
            "بيئة عمل تحتاج حلول تقنية متقدمة"
        ]
    }
}
```

-----

## الفصل 21: الأمان والخصوصية

### 21.1 المبادئ الأساسية

```python
SECURITY_PRINCIPLES = {
    "data_in_transit": "TLS 1.2+ لكل الاتصالات مع Claude API",
    "data_at_rest": "AES-256-GCM لأي بيانات مخزنة محلياً",
    "zero_data_retention": "استخدام ZDR header عند التوفر",
    "no_pii_in_prompts": "لا تُرسل أسماء حقيقية أو أرقام هوية في System Prompt",
    "consent_first": "لا توثيق بدون موافقة صريحة",
    "disclaimer_always": "كل استجابة سريرية تحتوي على تنبيه",
    "audit_logging": "تسجيل كل تفاعل (بدون بيانات المريض)",
    "session_timeout": "30 دقيقة — مسح السياق بعدها",
    "human_review": "التوصيات الحرجة تحتاج مراجعة بشرية"
}
```

### 21.2 Input Validation والحماية

```python
import re

def sanitize_input(text: str) -> str:
    """تنظيف المدخلات من محاولات الحقن والبيانات الحساسة"""

    # 1. حماية من Prompt Injection
    injection_patterns = [
        r"ignore\s+(previous|all|above)\s+instructions",
        r"you\s+are\s+now",
        r"<\s*system\s*>",
        r"system:\s*",
        r"forget\s+everything",
        r"new\s+instructions",
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, "[BLOCKED]", text, flags=re.IGNORECASE)

    # 2. إزالة بيانات حساسة غير ضرورية
    text = re.sub(r'\b\d{10,}\b', '[REDACTED_ID]', text)         # أرقام هوية
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
                  '[REDACTED_CARD]', text)                          # بطاقات
    # لا نحذف أرقام VA أو القياسات الطبية (مهمة سريرياً)

    return text


def validate_output(response: str) -> str:
    """التحقق من أن الاستجابة آمنة ومكتملة"""

    # 1. إضافة Disclaimer إذا لم يكن موجوداً
    has_disclaimer = any(term in response for term in
                        ["ليس بديلاً", "تنبيه", "مراجعة متخصص", "استشارة طبية"])

    if not has_disclaimer and contains_clinical_advice(response):
        response += "\n\n⚠️ هذا تحليل مساعد وليس بديلاً عن الرأي الطبي المباشر من متخصص مؤهل."

    # 2. التحقق من عدم وجود تشخيص نهائي
    definitive_patterns = [
        r"أنت مصاب بـ",
        r"التشخيص هو",
        r"يجب أن تتناول",  # وصف دوائي مباشر
    ]
    for pattern in definitive_patterns:
        if re.search(pattern, response):
            response = re.sub(pattern, "قد يكون ", response)

    return response
```

### 21.3 إعدادات HIPAA

```python
HIPAA_CONFIG = {
    "api_headers": {
        "anthropic-beta": "zero-data-retention-2025-01-01"
    },
    "local_storage": {
        "encryption": "AES-256-GCM",
        "key_management": "environment variable, never hardcoded",
        "retention_period": "session only — deleted after timeout",
    },
    "logging": {
        "what_to_log": ["tool_calls", "response_times", "error_types"],
        "what_NOT_to_log": ["patient_data", "images", "full_responses"],
    },
    "access_control": {
        "authentication": "required",
        "session_timeout_minutes": 30,
        "role_based": True,
    }
}
```

-----

## الفصل 22: خارطة البناء والتطوير

### 22.1 المراحل الأربع

```
═══════════════════════════════════════════════════════════════
المرحلة 1: الأساس (شهر 1-2)
═══════════════════════════════════════════════════════════════

الأسبوع 1-2: البنية التحتية
  ✅ إعداد Claude API مع System Prompt الشامل
  ✅ تنفيذ Tool Loop الأساسي
  ✅ اختبار Extended Thinking على حالات بسيطة

الأسبوع 3-4: الأدوات الأساسية
  ✅ search_pubmed + fetch_article_details
  ✅ visual_calculator + arabic_reading_calculator
  ✅ think tool

الأسبوع 5-6: القاعدة المعرفية v1
  ✅ 50-100 مستند أساسي (بروتوكولات رئيسية)
  ✅ Vector DB بسيط (Chroma محلي)
  ✅ search_knowledge_base

الأسبوع 7-8: التكامل والاختبار
  ✅ Prompt Chaining (أول 4 chains)
  ✅ اختبار على 10 حالات نموذجية
  ✅ تحسين System Prompt بناءً على النتائج

═══════════════════════════════════════════════════════════════
المرحلة 2: التوسع (شهر 3-4)
═══════════════════════════════════════════════════════════════

  🔲 Contextual Embeddings (تقنية Anthropic)
  🔲 Hybrid Search (BM25 + Semantic)
  🔲 الأدوات الجديدة: device_recommender, functional_assessment
  🔲 بروتوكولات التشخيص الكاملة (20+ حالة)
  🔲 محتوى تأهيل الأطفال (CVI, LMA)
  🔲 محتوى التأهيل العصبي البصري
  🔲 Vision: تحليل صور OCT و Visual Fields
  🔲 التوثيق: SOAP + ICF + Referral templates

═══════════════════════════════════════════════════════════════
المرحلة 3: التحسين (شهر 5-6)
═══════════════════════════════════════════════════════════════

  🔲 depression_screening + outcome_tracker
  🔲 referral_generator
  🔲 نظام قياس النتائج والرسوم البيانية
  🔲 القراءة العربية: بروتوكولات خاصة + القرآن
  🔲 Cross-Encoder Reranking للبحث
  🔲 Evaluation Framework: اختبار على 50+ حالة
  🔲 Few-shot examples من حالات حقيقية (مجهولة الهوية)
  🔲 مراجعة من متخصصين (3+ مراجعين)

═══════════════════════════════════════════════════════════════
المرحلة 4: الإنتاج (شهر 7+)
═══════════════════════════════════════════════════════════════

  🔲 HIPAA Compliance الكامل
  🔲 واجهة مستخدم (Web + Mobile)
  🔲 Audit Logging شامل
  🔲 تكامل مع EMR/EHR (FHIR API)
  🔲 تحديث تلقائي من PubMed (RSS/Alerts)
  🔲 Human-in-the-loop: مراجعة طبية للتوصيات الحرجة
  🔲 مراجعة دورية للقاعدة المعرفية (كل 3 أشهر)
  🔲 قياس الأداء المستمر
```

### 22.2 استراتيجية تحديث القاعدة المعرفية

```python
UPDATE_STRATEGY = {
    "pubmed_alerts": {
        "frequency": "weekly",
        "queries": [
            "low vision rehabilitation[MeSH] AND last 7 days[dp]",
            "vision rehabilitation AND clinical trial[pt] AND last 30 days[dp]",
            "cortical visual impairment AND intervention AND last 30 days[dp]",
            "assistive technology visual impairment AND review[pt]",
        ],
        "auto_index": True
    },
    "guideline_updates": {
        "frequency": "quarterly",
        "sources": ["WHO", "AAO", "RNIB", "ICO", "AOA"],
        "manual_review": True  # مراجعة بشرية قبل الإضافة
    },
    "quality_audit": {
        "frequency": "monthly",
        "metrics": [
            "retrieval_precision",   # هل RAG يرجع محتوى ذا صلة؟
            "answer_accuracy",       # هل الإجابات صحيحة سريرياً؟
            "evidence_citation",     # هل المراجع دقيقة؟
            "safety_compliance",     # هل Disclaimers موجودة دائماً؟
            "user_satisfaction"      # تقييم المتخصصين
        ]
    }
}
```

-----

## ⚡ ملخص تنفيذي

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  🏥 نظام استشاري التأهيل البصري الذكي v2.0                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              الأساس السريري (10 فصول)                       │ │
│  │                                                             │ │
│  │  تقييم وظيفي شامل → بروتوكولات بالتشخيص → أجهزة مساعدة   │ │
│  │  → تدريبات تأهيلية → تأهيل عصبي → تأهيل أطفال            │ │
│  │  → دعم نفسي → تنقل ومهارات حياة → القراءة العربية         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                          ↕ يترابط مع                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              البنية التقنية (7 فصول)                         │ │
│  │                                                             │ │
│  │  System Prompt ← Extended Thinking ← 12 أداة متخصصة       │ │
│  │  ← PubMed API ← Vision ← RAG+Hybrid Search                │ │
│  │  ← Prompt Chaining (6 خطوات)                               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                          ↕ يُنتج                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              التشغيل والجودة (5 فصول)                       │ │
│  │                                                             │ │
│  │  توثيق مهني (SOAP/ICF) → قياس نتائج → فريق متعدد         │ │
│  │  → أمان وخصوصية (HIPAA) → خارطة بناء 4 مراحل             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  🎯 الهدف: أفضل مساعد تأهيلي ممكن                               │
│     مع بقاء القرار النهائي للمتخصص البشري                        │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

-----

> **الإصدار:** 2.0 — إعادة بناء شاملة
> **التاريخ:** فبراير 2026
> **عدد الفصول:** 22 فصل (10 سريري + 7 تقني + 5 تشغيلي)
> **أُعد عبر:** Claude Opus 4.6
> **⚠️ للاستخدام التعليمي والمهني — ليس للتشخيص الطبي المباشر**
