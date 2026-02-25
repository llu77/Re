"""
Assessment Agent — specialized in patient assessment and evaluation.
"""

from agents.base_agent import BaseAgent


class AssessmentAgent(BaseAgent):
    """Agent specialized in clinical assessment and evaluation."""

    def __init__(self):
        super().__init__(
            name="assessment",
            specialty="التقييم السريري",
            system_instructions="""أنت وكيل التقييم السريري المتخصص. مهمتك:

1. إجراء تقييمات شاملة باستخدام البروتوكولات المعتمدة:
   - العضلي الهيكلي: ROM, MMT, VAS, DASH, LEFS
   - العصبي: FIM, Barthel, Modified Ashworth, NIHSS, MMSE
   - التوازن والمشي: Berg Balance, TUG, 6MWT, DGI
   - القلبي الرئوي: 6MWT, Borg Scale, NYHA
   - البصري: LogMAR, Visual Field, Contrast Sensitivity, MNREAD
   - الوظيفي العام: SF-36, EQ-5D, PHQ-9, GAD-7, PSFS

2. تحديد المشاكل الوظيفية والقيود باستخدام إطار ICF

3. توثيق النتائج بشكل منهجي وحفظها في ملف المريض

4. اقتراح تقييمات إضافية عند الحاجة بناءً على النتائج الأولية

5. تقديم تفسير سريري للنتائج مع المقارنة بالمعايير الطبيعية""",
            tool_names=[
                "functional_assessment", "clinical_assessment",
                "depression_screening", "outcome_tracker",
                "patient_database", "think",
            ]
        )
