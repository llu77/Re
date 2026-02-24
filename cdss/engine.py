"""
Clinical Rule Engine — محرك القواعد السريرية
=============================================
يقرأ قواعد YAML ويطابقها مع بيانات المريض (PatientContext).
يُرجع قائمة توصيات مرتبة حسب الأولوية ومستوى الدليل.
"""

import os
import yaml
from datetime import datetime


# درجات مستويات الأدلة (للترتيب)
EVIDENCE_SCORES = {
    "1a": 20,
    "1b": 18,
    "2a": 14,
    "2b": 12,
    "3": 8,
    "4": 5,
    "5": 2,
    "C": 3,
    "D": 1,
}


class ClinicalRuleEngine:
    """محرك تقييم القواعد السريرية"""

    def __init__(self, rules_dir: str = None):
        if rules_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rules_dir = os.path.join(base, "rules")

        self.rules_dir = rules_dir
        self.rules = []
        self._load_all_rules()

    def _load_all_rules(self):
        """تحميل جميع ملفات القواعد من مجلد rules/techniques/"""
        techniques_dir = os.path.join(self.rules_dir, "techniques")
        if not os.path.isdir(techniques_dir):
            return

        for filename in sorted(os.listdir(techniques_dir)):
            if filename.endswith((".yaml", ".yml")):
                filepath = os.path.join(techniques_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and "rules" in data:
                    for rule in data["rules"]:
                        rule["_source_file"] = filename
                    self.rules.extend(data["rules"])

    def evaluate(self, patient_context: dict) -> list:
        """
        تقييم جميع القواعد مقابل بيانات المريض.

        Args:
            patient_context: dict من FHIRParser.parse_bundle() أو parse_manual()

        Returns:
            list of recommendations مرتبة حسب الأولوية:
            [{
                rule_id, technique, technique_ar, category,
                action, protocol, evidence_level, priority,
                suitability_score, justification_template,
                evidence_refs, match_details
            }]
        """
        recommendations = []
        skipped_rules = []

        for rule in self.rules:
            match_result = self._check_conditions(rule, patient_context)
            if match_result["matched"]:
                rec = self._build_recommendation(rule, patient_context, match_result)
                recommendations.append(rec)
            else:
                skipped_rules.append({
                    "rule_id": rule.get("rule_id", ""),
                    "technique": rule.get("technique", ""),
                    "reason": match_result.get("fail_reason", "conditions not met"),
                })

        # ترتيب: priority أولاً (أقل = أعلى) ثم evidence score
        recommendations.sort(
            key=lambda r: (r["priority"], -r["suitability_score"])
        )

        # إضافة metadata
        return {
            "recommendations": recommendations,
            "skipped_rules": skipped_rules,
            "total_rules_evaluated": len(self.rules),
            "total_matched": len(recommendations),
            "timestamp": datetime.now().isoformat(),
        }

    def _check_conditions(self, rule: dict, ctx: dict) -> dict:
        """
        فحص شروط قاعدة واحدة مقابل بيانات المريض.

        Returns:
            {matched: bool, fail_reason: str, score_adjustments: list}
        """
        conditions = rule.get("conditions", {})
        result = {"matched": True, "fail_reason": None, "score_adjustments": []}

        # ── 1. فحص نمط الفقد البصري ──
        required_patterns = conditions.get("has_vision_pattern", [])
        if required_patterns and "any" not in required_patterns:
            patient_patterns = set(ctx.get("vision_patterns", []))
            if not patient_patterns.intersection(set(required_patterns)):
                result["matched"] = False
                result["fail_reason"] = f"vision pattern mismatch: need {required_patterns}, have {list(patient_patterns)}"
                return result

        # ── 2. فحص ICD-10 (وجود) ──
        required_icd = conditions.get("has_condition_icd10", [])
        if required_icd:
            patient_icd = set(ctx.get("active_icd10", []))
            if not patient_icd.intersection(set(required_icd)):
                result["matched"] = False
                result["fail_reason"] = f"ICD-10 mismatch: need any of {required_icd}"
                return result

        # ── 3. فحص ICD-10 (استبعاد) ──
        excluded_icd = conditions.get("exclude_condition_icd10", [])
        if excluded_icd:
            patient_icd = set(ctx.get("active_icd10", []))
            if patient_icd.intersection(set(excluded_icd)):
                result["matched"] = False
                result["fail_reason"] = f"excluded ICD-10 present: {list(patient_icd.intersection(set(excluded_icd)))}"
                return result

        # ── 4. فحص نطاقات القياسات (LOINC) ──
        loinc_ranges = conditions.get("observation_loinc_range", {})
        for loinc_code, range_vals in loinc_ranges.items():
            value = ctx.get("observations", {}).get(loinc_code)
            if value is None:
                # القياس غير متوفر — لا نرفض لكن نخصم نقاط
                result["score_adjustments"].append(("missing_observation", loinc_code, -3))
                continue
            if not isinstance(value, (int, float)):
                continue
            min_val = range_vals.get("min", float("-inf"))
            max_val = range_vals.get("max", float("inf"))
            if not (min_val <= value <= max_val):
                result["matched"] = False
                result["fail_reason"] = f"LOINC {loinc_code} value {value} outside range [{min_val}, {max_val}]"
                return result

        # ── 5. فحص الحالة الإدراكية ──
        cog_condition = conditions.get("cognitive_status", {})
        if cog_condition:
            excluded_cog = cog_condition.get("exclude", [])
            patient_cog = ctx.get("cognitive_status", "normal")
            if patient_cog in excluded_cog:
                result["matched"] = False
                result["fail_reason"] = f"cognitive status '{patient_cog}' is excluded"
                return result

        # ── 6. فحص المعدات ──
        equip_condition = conditions.get("equipment_available", [])
        if equip_condition:
            patient_equip = set(ctx.get("equipment_available", []))
            if not patient_equip.intersection(set(equip_condition)):
                # المعدات غير متوفرة — نخصم نقاط لكن لا نرفض (ما لم يكن ضرورياً)
                sys_caps = conditions.get("system_capabilities", {})
                if sys_caps.get("equipment_available"):
                    # معدات مطلوبة صراحة
                    result["matched"] = False
                    result["fail_reason"] = f"required equipment {equip_condition} not available"
                    return result
                result["score_adjustments"].append(("missing_equipment", equip_condition, -5))

        # ── 7. فحص العمر ──
        age_condition = conditions.get("patient_age", {})
        if age_condition:
            patient_age = ctx.get("patient", {}).get("age")
            if patient_age is not None:
                if "min" in age_condition and patient_age < age_condition["min"]:
                    result["matched"] = False
                    result["fail_reason"] = f"patient age {patient_age} below minimum {age_condition['min']}"
                    return result
                if "max" in age_condition and patient_age > age_condition["max"]:
                    result["score_adjustments"].append(("age_above_max", patient_age, -5))

        # ── 8. فحص بيئة التأهيل ──
        setting_condition = conditions.get("setting", [])
        if setting_condition:
            patient_setting = ctx.get("setting", "clinic")
            if patient_setting not in setting_condition:
                result["score_adjustments"].append(("setting_mismatch", patient_setting, -3))

        # ── 9. فحص الأهداف الوظيفية ──
        goal_condition = conditions.get("functional_goals", [])
        if goal_condition:
            patient_goals = set(ctx.get("functional_goals", []))
            if patient_goals.intersection(set(goal_condition)):
                result["score_adjustments"].append(("goal_match", list(goal_condition), +5))

        return result

    def _build_recommendation(self, rule: dict, ctx: dict, match_result: dict) -> dict:
        """بناء توصية من قاعدة مطابقة"""
        rec_data = rule.get("recommendation", {})
        evidence_level = rec_data.get("evidence_level", "5")
        priority = rec_data.get("priority", 10)

        # حساب نقاط الملاءمة
        base_score = EVIDENCE_SCORES.get(evidence_level, 2)
        adjustments = sum(adj[2] for adj in match_result.get("score_adjustments", []))
        suitability_score = max(0, base_score + adjustments)

        return {
            "rule_id": rule.get("rule_id", ""),
            "technique": rule.get("technique", ""),
            "technique_ar": rule.get("technique_ar", ""),
            "category": rule.get("category", ""),
            "action": rec_data.get("action", ""),
            "protocol": rec_data.get("protocol", ""),
            "evidence_level": evidence_level,
            "evidence_refs": rec_data.get("evidence_refs", []),
            "priority": priority,
            "suitability_score": suitability_score,
            "justification_template": rec_data.get("justification_template", ""),
            "experimental": rule.get("experimental", False),
            "controversy": rule.get("controversy", None),
            "hard_guardrails": rule.get("hard_guardrails", []),
            "price_range": rec_data.get("price_range", None),
            "match_details": {
                "score_adjustments": match_result.get("score_adjustments", []),
                "source_file": rule.get("_source_file", ""),
            },
        }
