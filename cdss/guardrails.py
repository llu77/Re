"""
Clinical Guardrails — حواجز الأمان السريرية
============================================
فحص المدخلات للتناقضات والأخطاء المنطقية
قبل تمريرها لمحرك القواعد السريرية.
"""

import os
import yaml
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """نتيجة فحص حواجز الأمان"""
    is_valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add_error(self, guard_id: str, message_ar: str, message_en: str):
        self.is_valid = False
        self.errors.append({
            "id": guard_id,
            "message_ar": message_ar,
            "message_en": message_en,
            "severity": "error",
        })

    def add_warning(self, guard_id: str, message_ar: str, message_en: str):
        self.warnings.append({
            "id": guard_id,
            "message_ar": message_ar,
            "message_en": message_en,
            "severity": "warning",
        })


class ClinicalGuardrails:
    """فحص المدخلات السريرية لكشف التناقضات"""

    def __init__(self, rules_path: str = None):
        if rules_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_path = os.path.join(base, "rules", "guardrails", "contradictions.yaml")

        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.contradiction_rules = data.get("contradictions", [])

    def validate(self, patient_context: dict) -> ValidationResult:
        """
        فحص شامل لبيانات المريض.

        Args:
            patient_context: dict من FHIRParser

        Returns:
            ValidationResult مع الأخطاء والتحذيرات
        """
        result = ValidationResult()

        # فحص تكامل البيانات أولاً
        self._check_data_integrity(patient_context, result)

        # فحص التناقضات من YAML
        self._check_yaml_contradictions(patient_context, result)

        # فحوصات ديناميكية إضافية
        self._check_goal_vs_capability(patient_context, result)
        self._check_diagnosis_vs_pattern(patient_context, result)

        return result

    def _check_data_integrity(self, ctx: dict, result: ValidationResult):
        """فحص سلامة البيانات الأساسية"""
        # فحص العمر
        age = ctx.get("patient", {}).get("age")
        if age is not None:
            if not (0 <= age <= 150):
                result.add_error(
                    "DATA_AGE_INVALID",
                    f"⛔ عمر المريض ({age}) خارج النطاق المنطقي (0-150)",
                    f"Patient age ({age}) outside logical range (0-150)",
                )

        # فحص VA
        va = ctx.get("mapped_observations", {}).get("va_logmar")
        if va is not None and isinstance(va, (int, float)):
            if va < -0.3:
                result.add_error(
                    "DATA_VA_INVALID",
                    f"⛔ قيمة VA غير منطقية (LogMAR={va} < -0.3)",
                    f"VA value impossible (LogMAR={va} < -0.3)",
                )

        # فحص PHQ-9
        phq9 = ctx.get("mapped_observations", {}).get("phq9_score")
        if phq9 is not None and isinstance(phq9, (int, float)):
            if not (0 <= phq9 <= 27):
                result.add_warning(
                    "DATA_PHQ9_RANGE",
                    f"⚠️ قيمة PHQ-9 ({phq9}) خارج النطاق (0-27)",
                    f"PHQ-9 score ({phq9}) outside valid range (0-27)",
                )

        # فحص أن هناك بيانات كافية للتقييم
        if not ctx.get("vision_patterns") and not ctx.get("active_icd10"):
            result.add_warning(
                "DATA_INSUFFICIENT",
                "⚠️ لا يوجد تشخيص أو نمط فقد بصري — النتائج قد تكون محدودة",
                "No diagnosis or vision pattern provided — results may be limited",
            )

    def _check_yaml_contradictions(self, ctx: dict, result: ValidationResult):
        """فحص التناقضات المحددة في ملف YAML"""
        for rule in self.contradiction_rules:
            check_type = rule.get("check", "")
            condition = rule.get("condition", {})
            severity = rule.get("severity", "warning")
            msg_ar = rule.get("message_ar", "")
            msg_en = rule.get("message_en", "")
            guard_id = rule.get("id", "UNKNOWN")

            matched = False

            if check_type == "goal_vs_capability":
                matched = self._match_goal_capability(ctx, condition)
            elif check_type == "diagnosis_vs_pattern":
                matched = self._match_diagnosis_pattern(ctx, condition)
            elif check_type == "cognitive_vs_technique":
                matched = self._match_cognitive_technique(ctx, condition)
            elif check_type == "age_safety":
                matched = self._match_age_safety(ctx, condition)
            elif check_type == "data_integrity":
                matched = self._match_data_integrity(ctx, condition)
            elif check_type == "equipment_availability":
                # يُفحص لاحقاً عند تقييم القواعد
                continue

            if matched:
                if severity == "error":
                    result.add_error(guard_id, msg_ar, msg_en)
                else:
                    result.add_warning(guard_id, msg_ar, msg_en)

    def _match_goal_capability(self, ctx: dict, condition: dict) -> bool:
        """فحص تناقض الهدف مع القدرة"""
        # فحص بناءً على diagnosis_category
        diag_cat = condition.get("diagnosis_category")
        if diag_cat:
            patient_patterns = ctx.get("vision_patterns", [])
            if diag_cat not in patient_patterns:
                return False
            goal = condition.get("functional_goal", "")
            return goal in ctx.get("functional_goals", [])

        # فحص بناءً على va_logmar_min
        va_min = condition.get("va_logmar_min")
        if va_min is not None:
            va = ctx.get("mapped_observations", {}).get("va_logmar")
            if va is None or va < va_min:
                return False
            goal = condition.get("functional_goal", "")
            return goal in ctx.get("functional_goals", [])

        return False

    def _match_diagnosis_pattern(self, ctx: dict, condition: dict) -> bool:
        """فحص تناقض التشخيص مع نمط الفقد"""
        required_icd = condition.get("diagnosis_icd10", [])
        required_pattern = condition.get("vision_pattern", "")

        patient_icd = set(ctx.get("active_icd10", []))
        patient_patterns = ctx.get("vision_patterns", [])

        has_icd = bool(patient_icd.intersection(set(required_icd)))
        has_pattern = required_pattern in patient_patterns

        return has_icd and has_pattern

    def _match_cognitive_technique(self, ctx: dict, condition: dict) -> bool:
        """فحص تناقض الإدراك مع التقنية"""
        required_cog = condition.get("cognitive_status", [])
        patient_cog = ctx.get("cognitive_status", "normal")
        return patient_cog in required_cog

    def _match_age_safety(self, ctx: dict, condition: dict) -> bool:
        """فحص أمان العمر"""
        age = ctx.get("patient", {}).get("age")
        if age is None:
            return False

        age_max = condition.get("patient_age_max")
        age_min = condition.get("patient_age_min")

        if age_max is not None and age <= age_max:
            return True
        if age_min is not None and age >= age_min:
            return True

        return False

    def _match_data_integrity(self, ctx: dict, condition: dict) -> bool:
        """فحص سلامة البيانات"""
        va_max = condition.get("va_logmar_max")
        if va_max is not None:
            va = ctx.get("mapped_observations", {}).get("va_logmar")
            if va is not None and va < va_max:
                return True
        return False

    def _check_goal_vs_capability(self, ctx: dict, result: ValidationResult):
        """فحوصات ديناميكية إضافية للأهداف"""
        va = ctx.get("mapped_observations", {}).get("va_logmar")
        goals = ctx.get("functional_goals", [])

        if va is not None and va > 2.0:
            visual_goals = {"reading", "face_recognition", "tv_watching", "driving", "writing"}
            impossible_goals = set(goals).intersection(visual_goals)
            if impossible_goals:
                result.add_warning(
                    "DYNAMIC_SEVERE_VI_GOALS",
                    f"⚠️ أهداف بصرية ({', '.join(impossible_goals)}) مع ضعف بصر شديد جداً — يجب تقديم بدائل صوتية/لمسية",
                    f"Visual goals ({', '.join(impossible_goals)}) with very severe VI — audio/tactile alternatives needed",
                )

    def _check_diagnosis_vs_pattern(self, ctx: dict, result: ValidationResult):
        """فحوصات ديناميكية للتشخيص vs النمط"""
        diagnoses = ctx.get("diagnoses", [])
        patterns = ctx.get("vision_patterns", [])

        for diag in diagnoses:
            expected_pattern = diag.get("pattern")
            if expected_pattern and patterns:
                if expected_pattern not in patterns and expected_pattern != "any":
                    actual = ", ".join(patterns)
                    result.add_warning(
                        f"DYNAMIC_PATTERN_MISMATCH_{diag['code']}",
                        f"⚠️ التشخيص {diag['name_ar']} ({diag['code']}) يُتوقع منه نمط '{expected_pattern}' لكن الأنماط المُدخلة: {actual}",
                        f"Diagnosis {diag['name']} ({diag['code']}) expects pattern '{expected_pattern}' but input patterns: {actual}",
                    )
