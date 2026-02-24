"""
Explainability Builder — نظام المبررات وقابلية التفسير (XAI)
=============================================================
يولّد مبررات بشرية لكل توصية سريرية + مسار تدقيق قانوني.
"""

from datetime import datetime


class ExplainabilityBuilder:
    """توليد مبررات بشرية وتقارير شفافية"""

    def build_justification(self, recommendation: dict, patient_context: dict) -> str:
        """
        ملء قالب المبرر ببيانات المريض الفعلية.

        Args:
            recommendation: dict من ClinicalRuleEngine
            patient_context: dict من FHIRParser

        Returns:
            نص المبرر الكامل (عربي)
        """
        template = recommendation.get("justification_template", "")
        if not template:
            return self._generate_default_justification(recommendation, patient_context)

        # جمع المتغيرات لملء القالب
        variables = self._collect_template_variables(patient_context)

        try:
            return template.format(**variables)
        except (KeyError, IndexError):
            # إذا فشل الملء — نستخدم القالب كما هو مع استبدال ما نستطيع
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", str(value))
            return template

    def build_audit_trail(self, evaluation_result: dict, patient_context: dict,
                          validation_result=None) -> dict:
        """
        بناء مسار تدقيق كامل لجلسة التقييم.

        Returns:
            dict مع كل تفاصيل القرار:
            - metadata, input_summary, validation, fired_rules, skipped_rules, recommendations
        """
        trail = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "engine_version": "1.0.0",
                "total_rules_evaluated": evaluation_result.get("total_rules_evaluated", 0),
                "total_matched": evaluation_result.get("total_matched", 0),
                "source": patient_context.get("source", "unknown"),
            },
            "input_summary": {
                "active_icd10": patient_context.get("active_icd10", []),
                "vision_patterns": patient_context.get("vision_patterns", []),
                "who_category": patient_context.get("who_category", {}).get("category", ""),
                "va_logmar": patient_context.get("mapped_observations", {}).get("va_logmar"),
                "phq9_score": patient_context.get("mapped_observations", {}).get("phq9_score"),
                "cognitive_status": patient_context.get("cognitive_status", ""),
                "functional_goals": patient_context.get("functional_goals", []),
                "equipment_available": patient_context.get("equipment_available", []),
                "setting": patient_context.get("setting", ""),
                "patient_age": patient_context.get("patient", {}).get("age"),
            },
            "validation": None,
            "fired_rules": [],
            "skipped_rules": evaluation_result.get("skipped_rules", []),
        }

        # إضافة نتائج التحقق
        if validation_result:
            trail["validation"] = {
                "is_valid": validation_result.is_valid,
                "errors_count": len(validation_result.errors),
                "warnings_count": len(validation_result.warnings),
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
            }

        # تفاصيل القواعد المُفعَّلة
        for rec in evaluation_result.get("recommendations", []):
            trail["fired_rules"].append({
                "rule_id": rec.get("rule_id", ""),
                "technique": rec.get("technique", ""),
                "evidence_level": rec.get("evidence_level", ""),
                "priority": rec.get("priority", 0),
                "suitability_score": rec.get("suitability_score", 0),
                "score_adjustments": rec.get("match_details", {}).get("score_adjustments", []),
            })

        return trail

    def format_for_clinician(self, evaluation_result: dict, patient_context: dict,
                             validation_result=None, language: str = "ar") -> str:
        """
        تنسيق التقرير الكامل بصيغة Markdown للطبيب.

        Args:
            language: "ar" للعربية، "en" للإنجليزية

        Returns:
            نص Markdown كامل
        """
        if language == "ar":
            return self._format_arabic(evaluation_result, patient_context, validation_result)
        return self._format_english(evaluation_result, patient_context, validation_result)

    # ─────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────

    def _collect_template_variables(self, ctx: dict) -> dict:
        """جمع كل المتغيرات المتاحة لملء القوالب"""
        obs = ctx.get("mapped_observations", {})
        diagnoses = ctx.get("diagnoses", [])
        diag_name = diagnoses[0].get("name", "") if diagnoses else ""
        diag_name_ar = diagnoses[0].get("name_ar", "") if diagnoses else ""

        patterns = ctx.get("vision_patterns", [])
        pattern = patterns[0] if patterns else ""

        goals = ctx.get("functional_goals", [])
        goal = goals[0] if goals else ""

        equip = ctx.get("equipment_available", [])
        equipment = equip[0] if equip else "N/A"

        who = ctx.get("who_category", {})

        return {
            "va": obs.get("va_logmar", "N/A"),
            "va_logmar": obs.get("va_logmar", "N/A"),
            "va_decimal": who.get("va_decimal", "N/A"),
            "phq9": obs.get("phq9_score", "N/A"),
            "phq9_score": obs.get("phq9_score", "N/A"),
            "cs": obs.get("contrast_sensitivity", "N/A"),
            "oct": obs.get("oct_central_thickness", "N/A"),
            "diagnosis": diag_name,
            "diagnosis_ar": diag_name_ar,
            "pattern": pattern,
            "goal": goal,
            "equipment": equipment,
            "age": ctx.get("patient", {}).get("age", "N/A"),
            "setting": ctx.get("setting", "clinic"),
            "who_category": who.get("label_ar", ""),
            "severity": self._phq9_severity(obs.get("phq9_score")),
        }

    def _phq9_severity(self, score) -> str:
        if score is None:
            return "N/A"
        score = int(score)
        if score <= 4:
            return "طبيعي"
        elif score <= 9:
            return "خفيف"
        elif score <= 14:
            return "متوسط"
        elif score <= 19:
            return "متوسط-شديد"
        return "شديد"

    def _generate_default_justification(self, rec: dict, ctx: dict) -> str:
        """توليد مبرر افتراضي إذا لم يوجد قالب"""
        technique = rec.get("technique_ar", rec.get("technique", ""))
        evidence = rec.get("evidence_level", "N/A")
        refs = ", ".join(rec.get("evidence_refs", []))

        return (
            f"تم اختيار {technique} بناءً على تطابق الحالة السريرية مع شروط القاعدة. "
            f"مستوى الدليل: {evidence}. "
            f"المراجع: {refs}."
        )

    def _format_arabic(self, eval_result, ctx, validation) -> str:
        """تنسيق عربي Markdown"""
        lines = []
        lines.append("# 📋 تقرير التوصيات السريرية\n")
        lines.append(f"**التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        # ملخص المريض
        who = ctx.get("who_category", {})
        age = ctx.get("patient", {}).get("age", "—")
        lines.append("## 👤 ملخص المريض\n")
        lines.append(f"- **العمر:** {age} سنة")
        lines.append(f"- **التشخيص:** {', '.join(d.get('name_ar', d.get('name', '')) for d in ctx.get('diagnoses', []))}")
        lines.append(f"- **نمط الفقد:** {', '.join(ctx.get('vision_patterns', []))}")
        lines.append(f"- **تصنيف WHO:** {who.get('label_ar', 'N/A')} ({who.get('category', '')})")
        va = ctx.get("mapped_observations", {}).get("va_logmar")
        if va is not None:
            lines.append(f"- **حدة الإبصار:** {va} LogMAR (عشري: {who.get('va_decimal', 'N/A')})")
        lines.append("")

        # تحذيرات
        if validation and (validation.errors or validation.warnings):
            lines.append("## ⚠️ تنبيهات الأمان\n")
            for err in validation.errors:
                lines.append(f"- 🔴 {err['message_ar']}")
            for warn in validation.warnings:
                lines.append(f"- 🟡 {warn['message_ar']}")
            lines.append("")

        # التوصيات
        recs = eval_result.get("recommendations", [])
        if recs:
            lines.append(f"## 🎯 التوصيات ({len(recs)} تقنية مطابقة)\n")
            for i, rec in enumerate(recs, 1):
                experimental = " ⚠️ تجريبي" if rec.get("experimental") else ""
                lines.append(f"### {i}. {rec.get('technique_ar', rec.get('technique', ''))}{experimental}\n")
                lines.append(f"- **التصنيف:** {rec.get('category', '')}")
                lines.append(f"- **مستوى الدليل:** {rec.get('evidence_level', '')}")
                lines.append(f"- **الأولوية:** {rec.get('priority', '')}")
                lines.append(f"- **الإجراء:** {rec.get('action', '')}")
                lines.append(f"- **البروتوكول:** {rec.get('protocol', '')}")
                if rec.get("price_range"):
                    lines.append(f"- **التكلفة التقديرية:** {rec['price_range']}")
                refs = ", ".join(rec.get("evidence_refs", []))
                if refs:
                    lines.append(f"- **المراجع:** {refs}")

                justification = rec.get("justification", "")
                if justification:
                    lines.append(f"\n> **المبرر:** {justification}")

                if rec.get("controversy"):
                    lines.append(f"\n> ⚠️ **ملاحظة:** {rec['controversy']}")
                lines.append("")

        # إخلاء مسؤولية
        lines.append("---")
        lines.append("*⚠️ هذا التقرير مُولَّد آلياً وليس بديلاً عن التقييم السريري المباشر.*")

        return "\n".join(lines)

    def _format_english(self, eval_result, ctx, validation) -> str:
        """English Markdown formatting"""
        lines = []
        lines.append("# Clinical Recommendations Report\n")
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        recs = eval_result.get("recommendations", [])
        lines.append(f"## Recommendations ({len(recs)} matched)\n")
        for i, rec in enumerate(recs, 1):
            lines.append(f"### {i}. {rec.get('technique', '')}")
            lines.append(f"- Evidence: {rec.get('evidence_level', '')} | Priority: {rec.get('priority', '')}")
            lines.append(f"- Action: {rec.get('action', '')}")
            justification = rec.get("justification", "")
            if justification:
                lines.append(f"- Justification: {justification}")
            lines.append("")

        return "\n".join(lines)
