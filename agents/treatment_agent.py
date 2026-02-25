"""
Treatment Agent — specialized in treatment planning and intervention delivery.
"""

from agents.base_agent import BaseAgent


class TreatmentAgent(BaseAgent):
    """Agent specialized in treatment planning and delivery."""

    def __init__(self):
        super().__init__(
            name="treatment",
            specialty="التخطيط العلاجي",
            system_instructions="""أنت وكيل التخطيط العلاجي المتخصص. مهمتك:

1. إعداد خطط علاجية شاملة تتضمن:
   - أهداف SMART (قصيرة ومتوسطة وطويلة المدى)
   - تدخلات محددة بالجرعة (التكرار، الشدة، المدة)
   - تمارين علاجية مفصلة مع تعليمات واضحة
   - برنامج منزلي عملي
   - معايير التقدم وإعادة التقييم

2. تسجيل الخطط العلاجية في ملف المريض باستخدام أداة record_treatment_plan

3. تقديم تدخلات فورية قابلة للتنفيذ:
   - بصري: توليد تمارين SVG
   - عضلي هيكلي: وصف التمارين بالتفصيل
   - عصبي: تمارين التوازن والتنسيق
   - قلبي رئوي: برامج المشي والتنفس

4. مراعاة الاحتياطات والموانع لكل مريض

5. دمج التثقيف الصحي مع الخطة العلاجية""",
            tool_names=[
                "record_treatment_plan", "generate_visual_exercise",
                "clinical_intervention", "technique_recommender",
                "device_recommender", "outcome_tracker",
                "patient_database", "think",
                "search_pubmed", "search_knowledge_base",
            ]
        )
