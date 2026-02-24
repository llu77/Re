"""
CDSS Orchestrator — منسق نظام دعم القرار السريري
==================================================
يجمع جميع مكونات CDSS في واجهة موحدة:
  FHIR Bundle / Manual Input
       ↓
  ClinicalGuardrails (تحقق)
       ↓
  ClinicalRuleEngine (تقييم)
       ↓
  OutcomeStore (تعديل بناءً على التاريخ)
       ↓
  ExplainabilityBuilder (مبررات)
       ↓
  نتائج كاملة: توصيات + تحذيرات + مسار تدقيق
"""

import os

from .fhir_parser import FHIRParser
from .engine import ClinicalRuleEngine
from .guardrails import ClinicalGuardrails
from .explainability import ExplainabilityBuilder
from .outcome_store import OutcomeStore


class CDSSOrchestrator:
    """المنسق الرئيسي لنظام CDSS"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        rules_dir = os.path.join(base_dir, "rules")

        self.parser = FHIRParser(
            os.path.join(rules_dir, "fhir_mappings", "code_mappings.yaml")
        )
        self.guardrails = ClinicalGuardrails(
            os.path.join(rules_dir, "guardrails", "contradictions.yaml")
        )
        self.engine = ClinicalRuleEngine(rules_dir)
        self.explainer = ExplainabilityBuilder()
        self.outcomes = OutcomeStore(os.path.join(base_dir, "data", "outcomes"))

    # ─────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────

    def evaluate_fhir(self, fhir_bundle: dict, patient_id: str = None,
                      language: str = "ar") -> dict:
        """
        المسار الكامل: FHIR Bundle → توصيات سريرية

        Args:
            fhir_bundle: HL7 FHIR R4 Bundle dict
            patient_id: معرف المريض (اختياري، لتتبع النتائج)
            language: لغة التقرير ("ar" | "en")

        Returns:
            dict مع:
              - is_valid: bool
              - errors: list (تناقضات حرجة)
              - warnings: list (تحذيرات)
              - recommendations: list (مرتبة حسب الأولوية)
              - clinical_report: str (تقرير Markdown)
              - audit_trail: dict
              - patient_context: dict
        """
        ctx = self.parser.parse_bundle(fhir_bundle)
        return self._run_pipeline(ctx, patient_id, language)

    def evaluate_manual(self, patient_data: dict, patient_id: str = None,
                        language: str = "ar") -> dict:
        """
        مسار يدوي: dict بسيط → توصيات سريرية

        Args:
            patient_data: dict مع مفاتيح:
                - diagnosis: str (أو icd10_codes: list)
                - vision_pattern: str
                - va_logmar: float (أو va_decimal: float)
                - phq9_score: int
                - age: int
                - cognitive_status: str
                - functional_goals: list
                - equipment_available: list
                - setting: str
            patient_id: معرف المريض (اختياري)
            language: "ar" | "en"
        """
        ctx = self.parser.parse_manual(patient_data)
        return self._run_pipeline(ctx, patient_id, language)

    def log_outcome(self, patient_id: str, technique_id: str, outcome: dict):
        """تسجيل نتيجة تقنية لمريض"""
        self.outcomes.log_outcome(patient_id, technique_id, outcome)

    def get_patient_history(self, patient_id: str) -> list:
        """تاريخ نتائج المريض"""
        return self.outcomes.get_history(patient_id)

    # ─────────────────────────────────────────────────────
    # Pipeline
    # ─────────────────────────────────────────────────────

    def _run_pipeline(self, ctx: dict, patient_id: str,
                      language: str) -> dict:
        """خط الأنابيب الداخلي المشترك"""

        # 1. فحص حواجز الأمان
        validation = self.guardrails.validate(ctx)

        # إذا وجدت أخطاء حرجة → أوقف (لكن ابلّغ بالتحذيرات)
        if not validation.is_valid:
            return {
                "is_valid": False,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "recommendations": [],
                "clinical_report": self._error_report(validation, language),
                "audit_trail": {},
                "patient_context": ctx,
            }

        # 2. تقييم القواعد
        eval_result = self.engine.evaluate(ctx)

        # 3. تعديل الأولويات بناءً على تاريخ المريض
        recommendations = eval_result.get("recommendations", [])
        if patient_id:
            recommendations = self.outcomes.adjust_priorities(
                recommendations, patient_id
            )
            eval_result["recommendations"] = recommendations

        # 4. إضافة المبررات لكل توصية
        for rec in recommendations:
            rec["justification"] = self.explainer.build_justification(rec, ctx)

        # 5. توليد التقرير السريري
        clinical_report = self.explainer.format_for_clinician(
            eval_result, ctx, validation, language
        )

        # 6. بناء مسار التدقيق
        audit_trail = self.explainer.build_audit_trail(
            eval_result, ctx, validation
        )

        return {
            "is_valid": True,
            "errors": [],
            "warnings": validation.warnings,
            "recommendations": recommendations,
            "clinical_report": clinical_report,
            "audit_trail": audit_trail,
            "patient_context": ctx,
            "total_rules_evaluated": eval_result.get("total_rules_evaluated", 0),
            "total_matched": eval_result.get("total_matched", 0),
        }

    def _error_report(self, validation, language: str) -> str:
        """تقرير خطأ عند وجود تناقضات حرجة"""
        if language == "ar":
            lines = ["# ⛔ تعذّر إجراء التقييم\n"]
            lines.append("## الأخطاء الحرجة\n")
            for err in validation.errors:
                lines.append(f"- {err['message_ar']}")
            if validation.warnings:
                lines.append("\n## التحذيرات\n")
                for w in validation.warnings:
                    lines.append(f"- {w['message_ar']}")
            lines.append("\n---")
            lines.append("*يرجى مراجعة البيانات المُدخلة وتصحيح الأخطاء قبل المتابعة.*")
            return "\n".join(lines)
        else:
            lines = ["# ⛔ Evaluation Failed\n"]
            for err in validation.errors:
                lines.append(f"- {err['message_en']}")
            return "\n".join(lines)


# ─────────────────────────────────────────────────────
# دالة مساعدة للاستخدام المباشر من rehab_consultant.py
# ─────────────────────────────────────────────────────

def run_cdss_evaluation(params: dict) -> dict:
    """
    دالة المدخل الرئيسية لأداة Claude (cdss_evaluate).

    Args:
        params: dict مع:
          - input_type: "fhir" | "manual"
          - fhir_bundle: dict (إذا input_type == "fhir")
          - patient_data: dict (إذا input_type == "manual")
          - patient_id: str (اختياري)
          - language: "ar" | "en"

    Returns:
        نتائج CDSS كاملة
    """
    orchestrator = CDSSOrchestrator()

    input_type = params.get("input_type", "manual")
    patient_id = params.get("patient_id")
    language = params.get("language", "ar")

    if input_type == "fhir":
        fhir_bundle = params.get("fhir_bundle", {})
        if not fhir_bundle:
            return {"error": "fhir_bundle مطلوب عند input_type='fhir'"}
        return orchestrator.evaluate_fhir(fhir_bundle, patient_id, language)

    elif input_type == "manual":
        patient_data = params.get("patient_data", {})
        if not patient_data:
            return {"error": "patient_data مطلوب عند input_type='manual'"}
        return orchestrator.evaluate_manual(patient_data, patient_id, language)

    elif input_type == "log_outcome":
        if not patient_id:
            return {"error": "patient_id مطلوب لتسجيل النتائج"}
        technique_id = params.get("technique_id", "")
        outcome = params.get("outcome", {})
        orchestrator.log_outcome(patient_id, technique_id, outcome)
        return {"status": "تم تسجيل النتيجة بنجاح", "patient_id": patient_id}

    elif input_type == "get_history":
        if not patient_id:
            return {"error": "patient_id مطلوب"}
        return {"history": orchestrator.get_patient_history(patient_id)}

    return {"error": f"input_type غير معروف: {input_type}"}
