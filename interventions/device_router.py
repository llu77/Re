"""
Smart Device Router — التوجيه الذكي للمعدات المساعدة
===================================================
حواجز أمان صارمة تُقيّم حدة الإبصار ومجال الرؤية والإدراك
قبل الموافقة على وصف جهاز مساعد.

يمنع إهدار المال والوقت بتوجيه المريض للجهاز الصحيح:
  - VR Magnifier (eSight) vs Audio AI (OrCam) vs Simple Optical

المبدأ:
  VA LogMAR → Residual Vision Assessment → Device Category → Specific Device
"""

from typing import Optional


# ── قاعدة بيانات الأجهزة ──
DEVICE_DATABASE = {
    "orcam_myeye3": {
        "name": "OrCam MyEye 3 Pro",
        "name_ar": "أوركام ماي آي 3 برو",
        "category": "audio_ai",
        "va_range": {"min_logmar": 1.3},
        "requires_cognition": "normal",
        "price_usd": 4500,
        "modality": "auditory",
        "features": ["text_reading", "face_recognition", "product_identification"],
    },
    "esight_go": {
        "name": "eSight Go",
        "name_ar": "إي سايت غو",
        "category": "vr_magnifier",
        "va_range": {"min_logmar": 0.5, "max_logmar": 1.3},
        "requires_cognition": "normal",
        "price_usd": 5950,
        "modality": "visual",
        "features": ["autofocus", "contrast_enhancement", "zoom"],
    },
    "irisvision_inspire": {
        "name": "IrisVision Inspire",
        "name_ar": "آيريس فيجن إنسباير",
        "category": "vr_magnifier",
        "va_range": {"min_logmar": 0.5, "max_logmar": 1.5},
        "requires_cognition": "normal",
        "price_usd": 2500,
        "modality": "visual",
        "features": ["scene_camera", "bubble_view", "edge_mode"],
    },
    "envision_glasses": {
        "name": "Envision Glasses",
        "name_ar": "إنفيجن جلاسيز",
        "category": "audio_ai",
        "va_range": {"min_logmar": 1.0},
        "requires_cognition": "normal",
        "price_usd": 3500,
        "modality": "auditory",
        "features": ["scene_description", "text_reading", "video_call"],
    },
    "optical_magnifier": {
        "name": "Optical Hand/Stand Magnifier",
        "name_ar": "مكبر بصري يدوي/مكتبي",
        "category": "optical",
        "va_range": {"min_logmar": 0.3, "max_logmar": 1.0},
        "requires_cognition": "any",
        "price_usd": 50,
        "modality": "visual",
        "features": ["portable", "no_charging", "simple"],
    },
    "cctv_desktop": {
        "name": "Desktop CCTV (Merlin/DaVinci)",
        "name_ar": "تلفزيون دائرة مغلقة مكتبي",
        "category": "electronic_magnifier",
        "va_range": {"min_logmar": 0.5, "max_logmar": 1.5},
        "requires_cognition": "any",
        "price_usd": 2000,
        "modality": "visual",
        "features": ["high_magnification", "contrast_modes", "reading_line"],
    },
    "white_cane": {
        "name": "Standard White Cane + Audio Labels",
        "name_ar": "عصا بيضاء + ملصقات صوتية",
        "category": "mobility",
        "va_range": {"min_logmar": 2.0},
        "requires_cognition": "any",
        "price_usd": 30,
        "modality": "tactile",
        "features": ["mobility", "low_cost", "no_tech"],
    },
    "tablet_accessibility": {
        "name": "Tablet with Accessibility Features",
        "name_ar": "جهاز لوحي مع ميزات إمكانية الوصول",
        "category": "consumer_tech",
        "va_range": {"min_logmar": 0.3, "max_logmar": 0.8},
        "requires_cognition": "any",
        "price_usd": 400,
        "modality": "visual",
        "features": ["zoom", "voiceover", "display_settings", "magnifier_app"],
    },
}


class SmartDeviceRouter:
    """
    نظام توجيه ذكي للأجهزة المساعدة مع حواجز أمان.

    المنطق:
    1. فحص الإدراك (Cognitive Guardrail)
    2. تقييم الرؤية المتبقية (Residual Vision)
    3. مطابقة الأجهزة المناسبة
    4. ترتيب حسب الأولوية السريرية
    """

    def __init__(self):
        self.devices = DEVICE_DATABASE

    def prescribe(
        self,
        va_logmar: float,
        visual_field_degrees: Optional[float] = None,
        has_cognitive_decline: bool = False,
        cognitive_level: str = "normal",
        functional_goals: list = None,
        budget_usd: Optional[float] = None,
        setting: str = "clinic",
    ) -> dict:
        """
        توصية بالجهاز الأنسب مع مبرر سريري.

        Args:
            va_logmar: حدة الإبصار LogMAR
            visual_field_degrees: مجال الرؤية (اختياري)
            has_cognitive_decline: هل يوجد تدهور إدراكي؟
            cognitive_level: "normal" | "mild_impairment" | "severe_impairment"
            functional_goals: قائمة الأهداف الوظيفية
            budget_usd: الميزانية المتاحة
            setting: "clinic" | "home" | "community"

        Returns:
            dict مع: primary_device, alternatives, guardrail_warnings, justification
        """
        goals = functional_goals or []
        warnings = []
        blocked_categories = []

        # ── 1. حاجز إدراكي ──
        if has_cognitive_decline or cognitive_level in ("moderate_impairment", "severe_impairment"):
            blocked_categories.extend(["audio_ai", "vr_magnifier"])
            warnings.append({
                "type": "cognitive_guardrail",
                "message": "Smart wearables require high cognitive load. Not recommended.",
                "message_ar": "النظارات الذكية تحتاج حمل إدراكي عالي. غير مُوصى بها.",
                "severity": "warning",
            })

        # ── 2. حاجز مجال الرؤية ──
        if visual_field_degrees is not None and visual_field_degrees < 5.0:
            # مجال رؤية ضيق جداً — أجهزة VR لن تفيد
            blocked_categories.append("vr_magnifier")
            warnings.append({
                "type": "field_guardrail",
                "message": f"Visual field ({visual_field_degrees}°) too narrow for VR magnification.",
                "message_ar": f"مجال الرؤية ({visual_field_degrees}°) ضيق جداً للتكبير VR.",
                "severity": "info",
            })

        # ── 3. مطابقة الأجهزة ──
        candidates = []
        for dev_id, dev in self.devices.items():
            # فحص الفئة المحظورة
            if dev["category"] in blocked_categories:
                continue

            # فحص نطاق VA
            va_range = dev["va_range"]
            if "min_logmar" in va_range and va_logmar < va_range["min_logmar"]:
                continue
            if "max_logmar" in va_range and va_logmar > va_range["max_logmar"]:
                continue

            # فحص الميزانية
            if budget_usd is not None and dev["price_usd"] > budget_usd:
                continue

            # حساب درجة الملاءمة
            score = self._score_device(dev, va_logmar, goals, setting)

            candidates.append({
                "device_id": dev_id,
                "device": dev,
                "score": score,
            })

        # ترتيب حسب الملاءمة
        candidates.sort(key=lambda c: c["score"], reverse=True)

        if not candidates:
            return {
                "primary_device": None,
                "alternatives": [],
                "guardrail_warnings": warnings,
                "justification": "No suitable device found for this VA/field/budget combination.",
                "justification_ar": "لم يُعثر على جهاز مناسب لهذا المزيج من VA/المجال/الميزانية.",
            }

        primary = candidates[0]
        alternatives = candidates[1:4]  # أفضل 3 بدائل

        justification = self._build_justification(
            primary["device"], va_logmar, visual_field_degrees, goals
        )

        return {
            "primary_device": {
                "id": primary["device_id"],
                "name": primary["device"]["name"],
                "name_ar": primary["device"]["name_ar"],
                "category": primary["device"]["category"],
                "price_usd": primary["device"]["price_usd"],
                "modality": primary["device"]["modality"],
                "features": primary["device"]["features"],
                "suitability_score": primary["score"],
            },
            "alternatives": [
                {
                    "id": c["device_id"],
                    "name": c["device"]["name"],
                    "name_ar": c["device"]["name_ar"],
                    "price_usd": c["device"]["price_usd"],
                    "score": c["score"],
                }
                for c in alternatives
            ],
            "guardrail_warnings": warnings,
            "justification": justification["en"],
            "justification_ar": justification["ar"],
            "patient_profile": {
                "va_logmar": va_logmar,
                "visual_field_deg": visual_field_degrees,
                "cognitive_decline": has_cognitive_decline,
                "goals": goals,
                "budget_usd": budget_usd,
            },
        }

    def _score_device(self, device: dict, va: float, goals: list, setting: str) -> int:
        """حساب درجة ملاءمة الجهاز"""
        score = 50

        # مكافأة إذا الجهاز يطابق الأهداف
        features = device.get("features", [])
        if "reading" in goals and "text_reading" in features:
            score += 20
        if "mobility" in goals and device["category"] == "mobility":
            score += 20
        if "face_recognition" in goals and "face_recognition" in features:
            score += 15

        # مكافأة للأجهزة البسيطة في البيئة المنزلية
        if setting == "home" and "portable" in features:
            score += 10
        if "simple" in features:
            score += 5

        # خصم للأجهزة الغالية
        price = device.get("price_usd", 0)
        if price > 3000:
            score -= 10
        elif price < 500:
            score += 10

        return score

    def _build_justification(self, device: dict, va: float, vf: Optional[float], goals: list) -> dict:
        """بناء المبرر السريري"""
        name = device["name"]
        modality = device["modality"]

        en = f"Recommended {name} (${device['price_usd']}) based on VA={va} LogMAR"
        ar = f"تم ترشيح {device['name_ar']} (${device['price_usd']}) بناءً على VA={va} LogMAR"

        if vf:
            en += f", VF={vf}°"
            ar += f"، مجال الرؤية={vf}°"

        if modality == "auditory":
            en += ". Auditory substitution is required due to limited residual vision."
            ar += ". الاستبدال السمعي مطلوب بسبب محدودية الرؤية المتبقية."
        elif modality == "visual":
            en += ". Sufficient residual vision for optical/electronic magnification."
            ar += ". رؤية متبقية كافية للتكبير البصري/الإلكتروني."

        return {"en": en, "ar": ar}


def run_device_routing(params: dict) -> dict:
    """
    واجهة الأداة للتوجيه الذكي للمعدات.

    Args:
        params: dict مع:
          - va_logmar: float
          - visual_field_degrees: float (اختياري)
          - has_cognitive_decline: bool
          - cognitive_level: str
          - functional_goals: list
          - budget_usd: float (اختياري)
          - setting: str
    """
    router = SmartDeviceRouter()
    return router.prescribe(
        va_logmar=params.get("va_logmar", 1.0),
        visual_field_degrees=params.get("visual_field_degrees"),
        has_cognitive_decline=params.get("has_cognitive_decline", False),
        cognitive_level=params.get("cognitive_level", "normal"),
        functional_goals=params.get("functional_goals", []),
        budget_usd=params.get("budget_usd"),
        setting=params.get("setting", "clinic"),
    )
