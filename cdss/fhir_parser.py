"""
FHIR Bundle Parser — محلل حزم HL7 FHIR
========================================
يحوّل FHIR Bundle (JSON) إلى PatientContext dict موحد
يُستخدم كمدخل لمحرك القواعد السريرية.
"""

import os
import yaml


class FHIRParser:
    """محلل حزم FHIR R4 مع ربط أكواد ICD-10 و LOINC"""

    def __init__(self, mappings_path: str = None):
        if mappings_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            mappings_path = os.path.join(base, "rules", "fhir_mappings", "code_mappings.yaml")

        with open(mappings_path, "r", encoding="utf-8") as f:
            mappings = yaml.safe_load(f)

        self.icd10_map = mappings.get("icd10_to_diagnosis", {})
        self.loinc_map = mappings.get("loinc_to_observation", {})
        self.who_classification = mappings.get("who_classification", {})

    # ─────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────

    def parse_bundle(self, bundle: dict) -> dict:
        """
        تحويل FHIR Bundle → PatientContext

        Args:
            bundle: FHIR R4 Bundle (resourceType: Bundle)

        Returns:
            dict مع:
              - active_icd10: list of ICD-10 codes
              - diagnoses: list of {code, name, name_ar, pattern, category}
              - observations: dict of {loinc_code: value}
              - mapped_observations: dict of {field_name: value}
              - vision_patterns: list of detected patterns
              - patient: dict of demographics
              - who_category: WHO VI classification
        """
        ctx = {
            "active_icd10": [],
            "diagnoses": [],
            "observations": {},
            "mapped_observations": {},
            "vision_patterns": [],
            "patient": {},
            "who_category": None,
            "functional_goals": [],
            "cognitive_status": "normal",
            "equipment_available": [],
            "setting": "clinic",
            "source": "fhir",
        }

        entries = bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            rtype = resource.get("resourceType", "")

            if rtype == "Patient":
                ctx["patient"] = self._extract_patient(resource)
            elif rtype == "Condition":
                self._extract_condition(resource, ctx)
            elif rtype == "Observation":
                self._extract_observation(resource, ctx)
            elif rtype == "Goal":
                self._extract_goal(resource, ctx)
            elif rtype == "Device":
                self._extract_device(resource, ctx)

        # تصنيف WHO بناءً على VA
        va = ctx["mapped_observations"].get("va_logmar")
        if va is not None:
            ctx["who_category"] = self._classify_who(va)

        # استخراج أنماط الفقد البصري الفريدة
        ctx["vision_patterns"] = list(set(ctx["vision_patterns"]))

        return ctx

    def parse_manual(self, data: dict) -> dict:
        """
        تحويل dict يدوي (بدون FHIR) → نفس بنية PatientContext

        Args:
            data: dict مع مفاتيح مثل diagnosis, va_logmar, age, etc.

        Returns:
            PatientContext dict
        """
        ctx = {
            "active_icd10": [],
            "diagnoses": [],
            "observations": {},
            "mapped_observations": {},
            "vision_patterns": [],
            "patient": {},
            "who_category": None,
            "functional_goals": data.get("functional_goals", []),
            "cognitive_status": data.get("cognitive_status", "normal"),
            "equipment_available": data.get("equipment_available", []),
            "setting": data.get("setting", "clinic"),
            "source": "manual",
        }

        # Demographics
        if "age" in data:
            ctx["patient"]["age"] = data["age"]
        if "gender" in data:
            ctx["patient"]["gender"] = data["gender"]

        # ICD-10 codes (if provided directly)
        if "icd10_codes" in data:
            for code in data["icd10_codes"]:
                ctx["active_icd10"].append(code)
                if code in self.icd10_map:
                    info = self.icd10_map[code]
                    ctx["diagnoses"].append({
                        "code": code,
                        "name": info.get("name", ""),
                        "name_ar": info.get("name_ar", ""),
                        "pattern": info.get("pattern"),
                        "category": info.get("category", ""),
                    })
                    if info.get("pattern"):
                        ctx["vision_patterns"].append(info["pattern"])

        # Diagnosis name mapping (if no ICD-10)
        if "diagnosis" in data and not ctx["active_icd10"]:
            diag = data["diagnosis"].lower()
            for code, info in self.icd10_map.items():
                if (info.get("name", "").lower() in diag or
                        info.get("name_ar", "") in data.get("diagnosis", "")):
                    ctx["active_icd10"].append(code)
                    ctx["diagnoses"].append({
                        "code": code,
                        "name": info.get("name", ""),
                        "name_ar": info.get("name_ar", ""),
                        "pattern": info.get("pattern"),
                        "category": info.get("category", ""),
                    })
                    if info.get("pattern"):
                        ctx["vision_patterns"].append(info["pattern"])
                    break

        # Vision pattern (if provided directly)
        if "vision_pattern" in data:
            if data["vision_pattern"] not in ctx["vision_patterns"]:
                ctx["vision_patterns"].append(data["vision_pattern"])

        # Observations
        if "va_logmar" in data:
            ctx["observations"]["70770-3"] = data["va_logmar"]
            ctx["mapped_observations"]["va_logmar"] = data["va_logmar"]
        if "va_decimal" in data:
            from math import log10
            logmar = -log10(max(data["va_decimal"], 0.001))
            ctx["observations"]["70770-3"] = round(logmar, 2)
            ctx["mapped_observations"]["va_logmar"] = round(logmar, 2)
        if "phq9_score" in data:
            ctx["observations"]["44261-6"] = data["phq9_score"]
            ctx["mapped_observations"]["phq9_score"] = data["phq9_score"]
        if "contrast_sensitivity" in data:
            ctx["observations"]["29271-4"] = data["contrast_sensitivity"]
            ctx["mapped_observations"]["contrast_sensitivity"] = data["contrast_sensitivity"]

        # WHO classification
        va = ctx["mapped_observations"].get("va_logmar")
        if va is not None:
            ctx["who_category"] = self._classify_who(va)

        ctx["vision_patterns"] = list(set(ctx["vision_patterns"]))
        return ctx

    # ─────────────────────────────────────────────────────
    # Private extraction methods
    # ─────────────────────────────────────────────────────

    def _extract_patient(self, resource: dict) -> dict:
        """استخراج بيانات المريض الديموغرافية"""
        patient = {}
        if "birthDate" in resource:
            from datetime import date
            try:
                birth = date.fromisoformat(resource["birthDate"])
                patient["age"] = (date.today() - birth).days // 365
            except (ValueError, TypeError):
                pass

        if "gender" in resource:
            patient["gender"] = resource["gender"]

        names = resource.get("name", [])
        if names:
            name = names[0]
            parts = []
            if "given" in name:
                parts.extend(name["given"])
            if "family" in name:
                parts.append(name["family"])
            patient["name"] = " ".join(parts)

        if "id" in resource:
            patient["patient_id"] = resource["id"]

        return patient

    def _extract_condition(self, resource: dict, ctx: dict):
        """استخراج التشخيصات (Condition resources)"""
        # فحص الحالة السريرية (active فقط)
        clinical_status = "active"
        cs = resource.get("clinicalStatus", {})
        codings = cs.get("coding", [])
        if codings:
            clinical_status = codings[0].get("code", "active")
        if clinical_status != "active":
            return

        # استخراج الكود
        code_obj = resource.get("code", {})
        for coding in code_obj.get("coding", []):
            system = coding.get("system", "")
            code = coding.get("code", "")

            if "icd-10" in system.lower() or "icd10" in system.lower():
                ctx["active_icd10"].append(code)

                if code in self.icd10_map:
                    info = self.icd10_map[code]
                    ctx["diagnoses"].append({
                        "code": code,
                        "name": info.get("name", coding.get("display", "")),
                        "name_ar": info.get("name_ar", ""),
                        "pattern": info.get("pattern"),
                        "category": info.get("category", ""),
                    })
                    if info.get("pattern"):
                        ctx["vision_patterns"].append(info["pattern"])

    def _extract_observation(self, resource: dict, ctx: dict):
        """استخراج القياسات (Observation resources)"""
        code_obj = resource.get("code", {})
        for coding in code_obj.get("coding", []):
            loinc = coding.get("code", "")

            # استخراج القيمة
            value = None
            if "valueInteger" in resource:
                value = resource["valueInteger"]
            elif "valueQuantity" in resource:
                value = resource["valueQuantity"].get("value")
            elif "valueString" in resource:
                try:
                    value = float(resource["valueString"])
                except (ValueError, TypeError):
                    value = resource["valueString"]

            if loinc and value is not None:
                ctx["observations"][loinc] = value

                # ربط بالاسم الداخلي
                if loinc in self.loinc_map:
                    field = self.loinc_map[loinc].get("field", loinc)
                    ctx["mapped_observations"][field] = value

    def _extract_goal(self, resource: dict, ctx: dict):
        """استخراج الأهداف الوظيفية (Goal resources)"""
        desc = resource.get("description", {})
        text = desc.get("text", "")
        if text:
            ctx["functional_goals"].append(text.lower())

    def _extract_device(self, resource: dict, ctx: dict):
        """استخراج الأجهزة المتوفرة (Device resources)"""
        device_name = resource.get("deviceName", [])
        if device_name:
            ctx["equipment_available"].append(device_name[0].get("name", ""))
        elif "type" in resource:
            type_text = resource["type"].get("text", "")
            if type_text:
                ctx["equipment_available"].append(type_text)

    def _classify_who(self, va_logmar: float) -> dict:
        """تصنيف WHO لضعف البصر بناءً على LogMAR"""
        from math import pow
        try:
            va_decimal = pow(10, -va_logmar)
        except (ValueError, OverflowError):
            va_decimal = 0.0

        for cat_key, cat_info in self.who_classification.items():
            va_range = cat_info.get("va_range", {})
            if va_range.get("min", 0) <= va_decimal <= va_range.get("max", 2.0):
                return {
                    "category": cat_key,
                    "label": cat_info.get("label", ""),
                    "label_ar": cat_info.get("label_ar", ""),
                    "va_decimal": round(va_decimal, 4),
                    "va_logmar": round(va_logmar, 2),
                }

        return {
            "category": "category_5",
            "label": "Total blindness (NLP)",
            "label_ar": "عمى كامل",
            "va_decimal": round(va_decimal, 4),
            "va_logmar": round(va_logmar, 2),
        }
