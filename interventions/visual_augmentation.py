"""
Visual Augmentation Engine — محرك التعزيز البصري
================================================
معالجة صور حية أو ثابتة لتعويض النقص البصري:
  1. Glaucoma Assist — CLAHE + Edge Enhancement (أصفر)
  2. AMD Magnifier — Central Bubble Magnification + Inversion
  3. Scotoma Simulator — محاكاة ما يراه المريض (للأسرة)

يعمل مع: كاميرا تابلت، نظارات AR، أو صور ثابتة.

المكتبات: numpy, cv2 (OpenCV)
"""

import numpy as np
import cv2
from typing import Tuple, Optional


class VisualAugmentationEngine:
    """
    محرك التعزيز البصري بالزمن شبه-الفعلي.

    يأخذ صورة (numpy array BGR) ويعيدها بعد المعالجة المناسبة
    لنوع الإعاقة البصرية.
    """

    def __init__(self, display_resolution: Tuple[int, int] = (1920, 1080)):
        self.width, self.height = display_resolution

    # ═══════════════════════════════════════════════════════════════
    # 1. تعزيز التباين والحواف — مرضى الجلوكوما
    # ═══════════════════════════════════════════════════════════════

    def glaucoma_assist(
        self,
        frame: np.ndarray,
        clahe_clip: float = 3.0,
        clahe_grid: int = 8,
        edge_color: Tuple[int, int, int] = (0, 255, 255),
        canny_low: int = 30,
        canny_high: int = 100,
    ) -> np.ndarray:
        """
        تعزيز التباين + تلوين الحواف لمرضى الجلوكوما.

        المنطق:
        1. فصل الإضاءة (L) عبر LAB color space
        2. CLAHE على قناة L فقط (لمنع تشوه الألوان)
        3. استخراج الحواف (Canny) وتلوينها بالأصفر
           (الأصفر أسهل لون تراه العين المصابة بضعف التباين)

        Args:
            frame: صورة BGR
            clahe_clip: حد القص لـ CLAHE
            clahe_grid: حجم الشبكة
            edge_color: لون الحواف (BGR)
            canny_low, canny_high: عتبات Canny

        Returns:
            صورة BGR معالجة
        """
        # تحويل إلى LAB
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # CLAHE على قناة الإضاءة
        clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(clahe_grid, clahe_grid))
        cl = clahe.apply(l_channel)

        # إعادة الدمج
        enhanced_lab = cv2.merge((cl, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # استخراج الحواف
        blurred = cv2.GaussianBlur(l_channel, (5, 5), 0)
        edges = cv2.Canny(blurred, threshold1=canny_low, threshold2=canny_high)

        # تكثيف الحواف
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # تلوين الحواف
        edge_mask = edges == 255
        enhanced_bgr[edge_mask] = edge_color

        return enhanced_bgr

    # ═══════════════════════════════════════════════════════════════
    # 2. التكبير المركزي + عكس الألوان — مرضى AMD
    # ═══════════════════════════════════════════════════════════════

    def amd_magnifier(
        self,
        frame: np.ndarray,
        magnification: float = 2.0,
        invert_colors: bool = True,
        bubble_radius_ratio: float = 0.3,
    ) -> np.ndarray:
        """
        تكبير مركزي (Bubble Magnifier) مع عكس اختياري للألوان.

        المنطق:
        - مرضى AMD لديهم عتمة مركزية (Central Scotoma)
        - التكبير المركزي ينقل التفاصيل للشبكية المحيطة
        - عكس الألوان (أبيض على أسود) يقلل الوهج

        Args:
            frame: صورة BGR
            magnification: عامل التكبير
            invert_colors: عكس الألوان؟
            bubble_radius_ratio: نسبة نصف قطر الفقاعة إلى حجم الصورة
        """
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        radius = int(min(h, w) * bubble_radius_ratio)

        # قص المنطقة المركزية
        src_radius = int(radius / magnification)
        y1 = max(0, cy - src_radius)
        y2 = min(h, cy + src_radius)
        x1 = max(0, cx - src_radius)
        x2 = min(w, cx + src_radius)

        center_crop = frame[y1:y2, x1:x2]

        if center_crop.size == 0:
            return frame

        # تكبير
        magnified = cv2.resize(center_crop, (radius * 2, radius * 2), interpolation=cv2.INTER_CUBIC)

        # إنشاء قناع دائري
        mask = np.zeros((radius * 2, radius * 2), dtype=np.uint8)
        cv2.circle(mask, (radius, radius), radius, 255, -1)

        # عكس الألوان إذا مطلوب
        result = frame.copy()
        if invert_colors:
            magnified = cv2.bitwise_not(magnified)

        # لصق الفقاعة المكبرة
        py1 = max(0, cy - radius)
        py2 = min(h, cy + radius)
        px1 = max(0, cx - radius)
        px2 = min(w, cx + radius)

        # ضبط الأبعاد
        mh = py2 - py1
        mw = px2 - px1
        magnified_resized = cv2.resize(magnified, (mw, mh))
        mask_resized = cv2.resize(mask, (mw, mh))

        mask_3ch = cv2.merge([mask_resized, mask_resized, mask_resized])
        region = result[py1:py2, px1:px2]

        # الدمج
        result[py1:py2, px1:px2] = np.where(mask_3ch > 0, magnified_resized, region)

        return result

    # ═══════════════════════════════════════════════════════════════
    # 3. محاكاة العتمة — Scotoma Simulator
    # ═══════════════════════════════════════════════════════════════

    def scotoma_simulator(
        self,
        frame: np.ndarray,
        scotoma_type: str = "central",
        scotoma_size_deg: float = 10.0,
        scotoma_position: Tuple[float, float] = (0.5, 0.5),
        blur_sigma: float = 20.0,
    ) -> np.ndarray:
        """
        محاكاة ما يراه المريض (للأسرة + التعاطف البيئي).

        Args:
            frame: صورة BGR
            scotoma_type: "central" | "hemianopia_right" | "hemianopia_left" | "tunnel"
            scotoma_size_deg: حجم العتمة (درجات بصرية تقريبية)
            scotoma_position: موقع مركز العتمة (0–1 نسبي)
            blur_sigma: شدة التمويه

        Returns:
            صورة BGR تحاكي رؤية المريض
        """
        h, w = frame.shape[:2]
        result = frame.copy()

        if scotoma_type == "central":
            # عتمة مركزية (AMD)
            cx = int(w * scotoma_position[0])
            cy = int(h * scotoma_position[1])
            radius = int(min(h, w) * scotoma_size_deg / 60)  # تحويل تقريبي

            # تمويه شديد للمنطقة المركزية
            blurred = cv2.GaussianBlur(result, (0, 0), blur_sigma)
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), radius, 255, -1)

            # تنعيم حواف القناع
            mask = cv2.GaussianBlur(mask, (51, 51), 15)
            mask_3ch = cv2.merge([mask, mask, mask]).astype(np.float32) / 255.0

            result = (blurred * mask_3ch + result * (1 - mask_3ch)).astype(np.uint8)

            # إضافة بقعة رمادية داكنة في المركز
            dark_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(dark_mask, (cx, cy), radius // 2, 255, -1)
            dark_mask = cv2.GaussianBlur(dark_mask, (31, 31), 10)
            dark_3ch = cv2.merge([dark_mask, dark_mask, dark_mask]).astype(np.float32) / 255.0

            gray_overlay = np.full_like(result, 80)
            result = (gray_overlay * dark_3ch * 0.7 + result * (1 - dark_3ch * 0.7)).astype(np.uint8)

        elif scotoma_type.startswith("hemianopia"):
            # عمى شقي (نصف المجال)
            side = "right" if "right" in scotoma_type else "left"
            blurred = cv2.GaussianBlur(result, (0, 0), blur_sigma)

            # تدرج سلس عبر خط المنتصف
            gradient = np.zeros((h, w), dtype=np.float32)
            mid = w // 2
            transition = w // 10  # 10% من العرض للانتقال

            if side == "right":
                for x in range(w):
                    if x > mid + transition:
                        gradient[:, x] = 1.0
                    elif x > mid - transition:
                        gradient[:, x] = (x - mid + transition) / (2 * transition)
            else:
                for x in range(w):
                    if x < mid - transition:
                        gradient[:, x] = 1.0
                    elif x < mid + transition:
                        gradient[:, x] = (mid + transition - x) / (2 * transition)

            grad_3ch = cv2.merge([gradient, gradient, gradient])

            # مزج: تمويه + تعتيم
            dark = np.full_like(result, 40)
            affected = (blurred * 0.3 + dark * 0.7).astype(np.uint8)
            result = (affected * grad_3ch + result * (1 - grad_3ch)).astype(np.uint8)

        elif scotoma_type == "tunnel":
            # رؤية نفقية (RP / الجلوكوما المتقدم)
            cx, cy = w // 2, h // 2
            remaining_field = int(min(h, w) * scotoma_size_deg / 120)

            # كل شيء خارج الدائرة يُظلَم
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.circle(mask, (cx, cy), remaining_field, 1.0, -1)
            mask = cv2.GaussianBlur(mask, (51, 51), 20)

            mask_3ch = cv2.merge([mask, mask, mask])
            dark = np.full_like(result, 20)

            result = (result * mask_3ch + dark * (1 - mask_3ch)).astype(np.uint8)

        return result

    # ═══════════════════════════════════════════════════════════════
    # 4. تحليل بيئي (Environmental Assessment)
    # ═══════════════════════════════════════════════════════════════

    def analyze_environment(self, frame: np.ndarray) -> dict:
        """
        تحليل صورة بيئة المريض لعوامل الخطر البصرية.

        Returns:
            dict مع: estimated_lux, glare_sources, contrast_quality, fall_risk_areas
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 1. تقدير الإضاءة
        mean_brightness = float(gray.mean())
        estimated_lux = self._brightness_to_lux(mean_brightness)

        # 2. كشف مصادر الوهج (Glare)
        _, bright_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        bright_pixels = np.count_nonzero(bright_mask)
        glare_ratio = bright_pixels / (h * w)

        # 3. جودة التباين
        local_std = cv2.blur(gray.astype(np.float32), (50, 50))
        local_mean = cv2.blur(gray.astype(np.float32), (50, 50))
        with np.errstate(divide="ignore", invalid="ignore"):
            rms_contrast = np.where(local_mean > 0, local_std / local_mean, 0)
        avg_contrast = float(np.mean(rms_contrast))

        # 4. كشف حواف حادة (عقبات محتملة)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / (h * w)

        # تصنيفات
        lux_class = self._classify_lux(estimated_lux)
        glare_risk = "high" if glare_ratio > 0.05 else "moderate" if glare_ratio > 0.01 else "low"
        contrast_quality = "good" if avg_contrast > 0.3 else "moderate" if avg_contrast > 0.15 else "poor"

        recommendations = []
        if estimated_lux < 300:
            recommendations.append({
                "issue": "Low lighting",
                "issue_ar": "إضاءة منخفضة",
                "action": f"Increase ambient lighting from ~{estimated_lux:.0f} to 500+ lux",
                "action_ar": f"زيادة الإضاءة المحيطة من ~{estimated_lux:.0f} إلى 500+ لوكس",
            })
        if glare_risk != "low":
            recommendations.append({
                "issue": "Glare sources detected",
                "issue_ar": "مصادر وهج مكتشفة",
                "action": "Add anti-glare filters or reposition light sources",
                "action_ar": "إضافة فلاتر مضادة للوهج أو إعادة توجيه مصادر الإضاءة",
            })
        if contrast_quality == "poor":
            recommendations.append({
                "issue": "Low contrast environment",
                "issue_ar": "بيئة منخفضة التباين",
                "action": "Add contrast markers on stairs, door frames, and switches",
                "action_ar": "إضافة علامات تباين على الدرج وإطارات الأبواب والمفاتيح",
            })

        return {
            "estimated_lux": round(estimated_lux, 0),
            "lux_classification": lux_class,
            "glare_ratio": round(glare_ratio, 4),
            "glare_risk": glare_risk,
            "average_contrast": round(avg_contrast, 3),
            "contrast_quality": contrast_quality,
            "edge_density": round(edge_density, 4),
            "recommendations": recommendations,
        }

    def _brightness_to_lux(self, brightness_0_255: float) -> float:
        """تحويل تقريبي من متوسط سطوع البكسل إلى لوكس"""
        # هذا تقدير خشن — في الإنتاج يحتاج معايرة الكاميرا
        return (brightness_0_255 / 255.0) ** 2.2 * 1000

    def _classify_lux(self, lux: float) -> dict:
        """تصنيف مستوى الإضاءة"""
        if lux >= 500:
            return {"level": "adequate", "label": "Adequate", "label_ar": "كافية"}
        elif lux >= 300:
            return {"level": "borderline", "label": "Borderline", "label_ar": "حدية"}
        elif lux >= 100:
            return {"level": "low", "label": "Low", "label_ar": "منخفضة"}
        else:
            return {"level": "very_low", "label": "Very Low", "label_ar": "منخفضة جداً"}


def run_visual_augmentation(params: dict) -> dict:
    """
    واجهة الأداة لمحرك التعزيز البصري.

    Args:
        params: dict مع:
          - action: "glaucoma_assist" | "amd_magnifier" | "scotoma_simulator" | "analyze_environment" | "demo"
          - image_width, image_height: int (لتوليد صورة اختبارية)
          - scotoma_type, magnification, etc: بارامترات التدخل
    """
    engine = VisualAugmentationEngine()
    action = params.get("action", "demo")

    # توليد صورة اختبارية إذا لم تُقدَّم
    img_w = params.get("image_width", 640)
    img_h = params.get("image_height", 480)

    if action == "demo":
        # عرض توضيحي لجميع الوظائف
        test_frame = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)

        results = {}
        for mode in ["glaucoma_assist", "amd_magnifier"]:
            if mode == "glaucoma_assist":
                out = engine.glaucoma_assist(test_frame)
            else:
                out = engine.amd_magnifier(test_frame)
            results[mode] = {"shape": list(out.shape), "processed": True}

        for stype in ["central", "hemianopia_right", "tunnel"]:
            out = engine.scotoma_simulator(test_frame, scotoma_type=stype)
            results[f"scotoma_{stype}"] = {"shape": list(out.shape), "processed": True}

        env = engine.analyze_environment(test_frame)
        results["environment_analysis"] = env

        return {"demo_results": results}

    elif action == "analyze_environment":
        test_frame = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
        return engine.analyze_environment(test_frame)

    elif action == "scotoma_simulator":
        test_frame = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
        stype = params.get("scotoma_type", "central")
        size = params.get("scotoma_size_deg", 10.0)
        out = engine.scotoma_simulator(test_frame, scotoma_type=stype, scotoma_size_deg=size)
        return {"processed": True, "shape": list(out.shape), "scotoma_type": stype}

    return {"error": f"Unknown action: {action}"}
