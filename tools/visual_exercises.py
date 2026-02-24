"""
Visual Exercise Generator — مولّد التمارين البصرية بـ SVG
==========================================================
يولّد تمارين علاجية بصرية كصور SVG تفاعلية مضمّنة في المحادثة.

أنواع التمارين:
  1. scanning_grid       — شبكة مسح بصري (Hemianopia / Tunnel Vision)
  2. fixation_cross      — صليب تثبيت + دوائر PRL (AMD / Central Scotoma)
  3. contrast_chart      — لوحة حساسية التباين المتدرجة
  4. reading_ruler       — مسطرة قراءة (Typoscope)
  5. tracking_exercise   — مسار تتبع بصري منحنى
"""

import math


def generate_visual_exercise(params: dict) -> dict:
    """
    مدخل موحّد لتوليد التمارين البصرية.

    Args:
        params: {
            exercise_type: نوع التمرين
            difficulty: 1-5 (الصعوبة)
            side: "left" | "right" | "both" (الجانب المتأثر)
            title: عنوان التمرين (اختياري)
            instructions: التعليمات (اختيارية)
        }

    Returns:
        {exercise_type, title, instructions, svg, duration_minutes,
         repetitions, evidence_level}
    """
    etype = params.get("exercise_type", "fixation_cross")
    difficulty = max(1, min(5, int(params.get("difficulty", 3))))
    side = params.get("side", "both")
    title = params.get("title", _default_titles.get(etype, "تمرين بصري"))
    instructions = params.get("instructions", _default_instructions.get(etype, "اتبع التعليمات"))

    generators = {
        "scanning_grid": _scanning_grid,
        "fixation_cross": _fixation_cross,
        "contrast_chart": _contrast_chart,
        "reading_ruler": _reading_ruler,
        "tracking_exercise": _tracking_exercise,
    }

    fn = generators.get(etype, _fixation_cross)
    svg = fn(difficulty, side)

    return {
        "exercise_type": etype,
        "title": title,
        "instructions": instructions,
        "svg": svg,
        "duration_minutes": 5 + difficulty * 2,
        "repetitions": max(1, 6 - difficulty),
        "evidence_level": _evidence_levels.get(etype, "B"),
    }


# ─────────────────────────────────────────────────────────────
# SVG Helpers
# ─────────────────────────────────────────────────────────────

def _svg_wrap(content: str, w: int = 500, h: int = 380, bg: str = "#0D1B2A") -> str:
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{bg};border-radius:12px;font-family:Cairo,sans-serif">'
        f'{content}'
        f'</svg>'
    )


# ─────────────────────────────────────────────────────────────
# 1. Scanning Grid — شبكة مسح بصري
# ─────────────────────────────────────────────────────────────

def _scanning_grid(difficulty: int, side: str) -> str:
    """
    شبكة نقاط مرقّمة للمسح البصري.
    - الصعوبة تحدد حجم الشبكة (4×4 → 8×8)
    - للـ Hemianopia: النقاط تتركز في الجانب المتأثر
    """
    grid_size = 3 + difficulty  # 4→8
    W, H = 500, 380
    pad = 50
    cell_w = (W - 2 * pad) / (grid_size - 1)
    cell_h = (H - 2 * pad - 40) / (grid_size - 1)

    # ألوان النقاط
    colors = ["#2E8BC0", "#10A567", "#E8A020", "#C0392B", "#9B59B6"]

    elements = []

    # خط الوسط إذا كان hemianopia
    if side in ("left", "right"):
        elements.append(
            f'<line x1="{W//2}" y1="30" x2="{W//2}" y2="{H-10}" '
            f'stroke="rgba(255,255,255,0.15)" stroke-width="1" stroke-dasharray="6 4"/>'
        )
        label_x = W // 4 if side == "left" else 3 * W // 4
        elements.append(
            f'<text x="{label_x}" y="20" fill="rgba(255,255,255,0.4)" '
            f'font-size="10" text-anchor="middle">الجانب المتأثر</text>'
        )

    # توليد النقاط
    num = 1
    order = []
    for row in range(grid_size):
        for col in range(grid_size):
            x = pad + col * cell_w
            y = pad + 20 + row * cell_h

            # للـ Hemianopia: إزاحة إضافية للجانب المتأثر
            if side == "left" and col < grid_size // 2:
                density_boost = True
            elif side == "right" and col >= grid_size // 2:
                density_boost = True
            else:
                density_boost = False

            order.append((x, y, density_boost, num))
            num += 1

    # رسم النقاط + أرقام
    for x, y, boost, n in order:
        r = 14 if boost else 10
        color = colors[(n - 1) % len(colors)]
        opacity = "1" if boost else "0.6"

        elements.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" '
            f'fill="{color}" opacity="{opacity}" stroke="white" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{x:.0f}" y="{y + 4:.0f}" fill="white" '
            f'font-size="9" font-weight="700" text-anchor="middle">{n}</text>'
        )

    # عنوان
    elements.append(
        f'<text x="{W//2}" y="{H-8}" fill="rgba(255,255,255,0.5)" '
        f'font-size="11" text-anchor="middle">'
        f'المستوى {difficulty} — انتقل من 1 → {num-1} بالترتيب'
        f'</text>'
    )

    return _svg_wrap("".join(elements))


# ─────────────────────────────────────────────────────────────
# 2. Fixation Cross + PRL Rings — تمرين الإبصار اللامركزي
# ─────────────────────────────────────────────────────────────

def _fixation_cross(difficulty: int, side: str) -> str:
    """
    صليب تثبيت مركزي + دوائر PRL لتدريب الإبصار اللامركزي.
    الصعوبة تحدد حجم الصليب (كبير→صغير) وعدد الدوائر.
    """
    W, H = 500, 380
    cx, cy = W // 2, H // 2

    cross_size = 60 - difficulty * 8  # 52 → 20
    prl_rings = difficulty + 1        # 2 → 6 حلقات

    elements = []

    # دوائر PRL المتدرجة
    ring_colors = ["#2E8BC0", "#10A567", "#E8A020", "#9B59B6", "#C0392B", "#E8E820"]
    for i in range(prl_rings, 0, -1):
        r = i * 35
        color = ring_colors[(i - 1) % len(ring_colors)]
        elements.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="none" stroke="{color}" stroke-width="1.5" '
            f'stroke-dasharray="6 4" opacity="0.5"/>'
        )
        # تسمية المسافة الزاوية
        if i <= 3:
            angle_deg = i * 2
            elements.append(
                f'<text x="{cx + r + 4}" y="{cy}" fill="{color}" '
                f'font-size="9" opacity="0.7">{angle_deg}°</text>'
            )

    # صليب التثبيت المركزي
    arm = cross_size
    thickness = max(2, 6 - difficulty)
    elements.append(
        f'<line x1="{cx-arm}" y1="{cy}" x2="{cx+arm}" y2="{cy}" '
        f'stroke="white" stroke-width="{thickness}" stroke-linecap="round"/>'
    )
    elements.append(
        f'<line x1="{cx}" y1="{cy-arm}" x2="{cx}" y2="{cy+arm}" '
        f'stroke="white" stroke-width="{thickness}" stroke-linecap="round"/>'
    )

    # دائرة المركز (الورم)
    elements.append(
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="#C0392B">'
        f'<animate attributeName="opacity" values="1;0.3;1" dur="2s" repeatCount="indefinite"/>'
        f'</circle>'
    )

    # نقطة PRL المقترحة (أسفل يسار للـ AMD)
    prl_offset = 30 + difficulty * 10
    prl_x = cx + prl_offset if side != "right" else cx - prl_offset
    prl_y = cy + prl_offset
    elements.append(
        f'<circle cx="{prl_x}" cy="{prl_y}" r="8" '
        f'fill="none" stroke="#10A567" stroke-width="2">'
        f'<animate attributeName="r" values="8;12;8" dur="2s" repeatCount="indefinite"/>'
        f'</circle>'
    )
    elements.append(
        f'<text x="{prl_x}" y="{prl_y + 22}" fill="#10A567" '
        f'font-size="9" text-anchor="middle">PRL المقترح</text>'
    )

    # تعليمة
    elements.append(
        f'<text x="{W//2}" y="{H-10}" fill="rgba(255,255,255,0.4)" '
        f'font-size="10" text-anchor="middle">'
        f'ثبّت نظرك على الدائرة الخضراء — تجاهل المركز الأحمر'
        f'</text>'
    )

    return _svg_wrap("".join(elements), bg="#0A1628")


# ─────────────────────────────────────────────────────────────
# 3. Contrast Chart — لوحة حساسية التباين
# ─────────────────────────────────────────────────────────────

def _contrast_chart(difficulty: int, side: str) -> str:
    """
    حروف عربية بدرجات تباين متدرجة (100% → 5%).
    تستخدم لقياس وتدريب حساسية التباين.
    """
    W, H = 500, 380
    letters = ["ب", "س", "ع", "ر", "و", "ن", "ه", "م", "ل", "ك"]

    # صفوف: كل صف درجة تباين
    contrasts = [100, 80, 60, 40, 25, 15, 10, 5]
    num_rows = min(4 + difficulty, len(contrasts))
    font_sizes = [36, 30, 26, 22, 18, 16, 14, 12]

    elements = []

    row_h = (H - 60) / num_rows
    for i in range(num_rows):
        ct = contrasts[i]
        brightness = int(255 * ct / 100)
        color = f"rgb({brightness},{brightness},{brightness})"
        fs = font_sizes[i]
        y = 40 + i * row_h + row_h * 0.6

        # عدد الحروف في الصف
        num_letters = min(5 + difficulty - i, len(letters))
        letter_set = letters[i:i + num_letters]
        spacing = (W - 80) / max(len(letter_set), 1)

        for j, letter in enumerate(letter_set):
            x = 40 + j * spacing + spacing / 2
            elements.append(
                f'<text x="{x:.0f}" y="{y:.0f}" fill="{color}" '
                f'font-size="{fs}" font-weight="700" text-anchor="middle"'
                f' font-family="Cairo,Arial">{letter}</text>'
            )

        # تسمية التباين
        elements.append(
            f'<text x="8" y="{y:.0f}" fill="rgba(255,255,255,0.3)" '
            f'font-size="9" text-anchor="start">{ct}%</text>'
        )

    # عنوان
    elements.append(
        f'<text x="{W//2}" y="20" fill="rgba(255,255,255,0.6)" '
        f'font-size="12" font-weight="700" text-anchor="middle">'
        f'تدرّج حساسية التباين — اقرأ أدنى صف ممكن'
        f'</text>'
    )

    return _svg_wrap("".join(elements), bg="#1A1A1A")


# ─────────────────────────────────────────────────────────────
# 4. Reading Ruler — مسطرة القراءة (Typoscope)
# ─────────────────────────────────────────────────────────────

def _reading_ruler(difficulty: int, side: str) -> str:
    """
    مسطرة قراءة (Typoscope) مع نافذة تُبرز سطراً واحداً.
    نص عربي تدريبي بأحجام مختلفة.
    """
    W, H = 500, 380
    font_sizes = [28, 22, 18, 14, 12]
    fs = font_sizes[min(difficulty - 1, 4)]

    lines = [
        "التأهيل البصري يُعيد الاستقلالية",
        "كل يوم تدريب هو خطوة للأمام",
        "القراءة ممكنة بالإبصار اللامركزي",
        "النظارات المكبّرة أداة قوية",
        "الصبر والممارسة مفتاح النجاح",
        "عيناك تتكيّفان مع الوقت",
        "اسأل أخصائيك عن أجهزة القراءة",
        "التدريب اليومي يُفرق كثيراً",
    ]

    line_h = fs + 10
    total_text_h = len(lines) * line_h
    start_y = (H - total_text_h) // 2

    # الصف المُبرز (وسط الشاشة)
    highlight_row = len(lines) // 2
    highlight_y = start_y + highlight_row * line_h

    elements = []

    # خلفية مُعتِمة لكل الصفحة
    elements.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#1A1A2E"/>')

    # الأسطر
    for i, line in enumerate(lines):
        y = start_y + i * line_h + line_h * 0.75
        if i == highlight_row:
            # تأطير الصف المُبرز
            elements.append(
                f'<rect x="10" y="{start_y + i * line_h}" '
                f'width="{W - 20}" height="{line_h}" '
                f'fill="rgba(46,139,192,0.25)" rx="4"/>'
            )
            color = "white"
        else:
            color = "rgba(255,255,255,0.25)"

        elements.append(
            f'<text x="{W//2}" y="{y:.0f}" fill="{color}" '
            f'font-size="{fs}" text-anchor="middle" '
            f'font-family="Cairo,Arial" font-weight="{"700" if i == highlight_row else "400"}">'
            f'{line}</text>'
        )

    # إطار النافذة
    elements.append(
        f'<rect x="10" y="{start_y + highlight_row * line_h}" '
        f'width="{W - 20}" height="{line_h}" '
        f'fill="none" stroke="#2E8BC0" stroke-width="2" rx="4"/>'
    )

    # تسمية الحجم
    elements.append(
        f'<text x="{W//2}" y="{H - 6}" fill="rgba(255,255,255,0.3)" '
        f'font-size="10" text-anchor="middle">'
        f'حجم الخط: {fs}pt — اقرأ السطر الأزرق بوضوح'
        f'</text>'
    )

    return _svg_wrap("".join(elements), bg="#1A1A2E")


# ─────────────────────────────────────────────────────────────
# 5. Tracking Exercise — تمرين التتبع البصري
# ─────────────────────────────────────────────────────────────

def _tracking_exercise(difficulty: int, side: str) -> str:
    """
    مسار منحنى للتتبع البصري مع نقاط تحكم.
    الصعوبة تحدد تعقيد المسار وعدد الأهداف.
    """
    W, H = 500, 380
    cx, cy = W // 2, H // 2

    # توليد نقاط المسار بالتريج
    num_points = 6 + difficulty * 2
    radius_x = 180 - difficulty * 15
    radius_y = 130 - difficulty * 10
    rotation_offset = difficulty * 15

    path_points = []
    for i in range(num_points + 1):
        angle = (2 * math.pi * i / num_points) + math.radians(rotation_offset)
        # إضافة تموج للصعوبة الأعلى
        wobble = 1 + (difficulty - 1) * 0.15 * math.sin(angle * difficulty)
        x = cx + radius_x * wobble * math.cos(angle)
        y = cy + radius_y * wobble * math.sin(angle)
        path_points.append((x, y))

    elements = []

    # رسم المسار
    path_d = f"M {path_points[0][0]:.1f} {path_points[0][1]:.1f}"
    for i in range(1, len(path_points)):
        x0, y0 = path_points[i - 1]
        x1, y1 = path_points[i]
        # منحنى بيزييه
        cp_x = (x0 + x1) / 2 + (y1 - y0) * 0.2
        cp_y = (y0 + y1) / 2 + (x0 - x1) * 0.2
        path_d += f" Q {cp_x:.1f} {cp_y:.1f} {x1:.1f} {y1:.1f}"

    elements.append(
        f'<path d="{path_d}" fill="none" stroke="#2E8BC0" '
        f'stroke-width="2.5" stroke-linecap="round" opacity="0.7"/>'
    )

    # نقاط الهدف على المسار
    target_colors = ["#10A567", "#E8A020", "#C0392B", "#9B59B6"]
    num_targets = min(difficulty + 2, len(path_points) - 1)
    step = len(path_points) // num_targets
    for i in range(num_targets):
        idx = (i * step) % (len(path_points) - 1)
        px, py = path_points[idx]
        color = target_colors[i % len(target_colors)]
        elements.append(
            f'<circle cx="{px:.0f}" cy="{py:.0f}" r="10" '
            f'fill="{color}" stroke="white" stroke-width="1.5">'
        )
        if i == 0:
            elements.append(
                f'<animate attributeName="r" values="10;14;10" '
                f'dur="1.5s" repeatCount="indefinite"/>'
            )
        elements.append('</circle>')
        elements.append(
            f'<text x="{px:.0f}" y="{py + 4:.0f}" fill="white" '
            f'font-size="9" font-weight="700" text-anchor="middle">{i+1}</text>'
        )

    # نقطة البداية (نجمة)
    sx, sy = path_points[0]
    elements.append(
        f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="5" fill="#FFD700"/>'
    )
    elements.append(
        f'<text x="{sx:.0f}" y="{sy - 12:.0f}" fill="#FFD700" '
        f'font-size="9" text-anchor="middle">ابدأ هنا</text>'
    )

    # تعليمة
    elements.append(
        f'<text x="{W//2}" y="{H - 8}" fill="rgba(255,255,255,0.4)" '
        f'font-size="10" text-anchor="middle">'
        f'تتبع المسار بعينيك بدون تحريك رأسك — المستوى {difficulty}'
        f'</text>'
    )

    return _svg_wrap("".join(elements), bg="#0D1B2A")


# ─────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────

_default_titles = {
    "scanning_grid": "تمرين مسح الشبكة البصرية",
    "fixation_cross": "تمرين الإبصار اللامركزي (PRL)",
    "contrast_chart": "تدريب حساسية التباين",
    "reading_ruler": "تمرين القراءة بالمسطرة",
    "tracking_exercise": "تمرين تتبع المسار البصري",
}

_default_instructions = {
    "scanning_grid": "انظر إلى النقاط بالترتيب من 1 حتى النهاية. حرّك رأسك ببطء مع كل رقم.",
    "fixation_cross": "ثبّت نظرك على الدائرة الخضراء (PRL) وليس على المركز. استمر 30 ثانية.",
    "contrast_chart": "اقرأ الصفوف من الأعلى (أوضح) نزولاً حتى أدنى صف تستطيع قراءته.",
    "reading_ruler": "ضع إصبعك أسفل السطر الأزرق واقرأه بصوت عالٍ. انتقل لسطر آخر عند الانتهاء.",
    "tracking_exercise": "ابدأ من النجمة الذهبية وتتبع الخط بعينيك حتى النقطة 1 ثم 2 ثم 3…",
}

_evidence_levels = {
    "scanning_grid": "1b",      # Zihl, NeuroEyeCoach RCTs
    "fixation_cross": "1b",     # EVT + MBFT meta-analysis
    "contrast_chart": "2a",     # Pelli-Robson derivatives
    "reading_ruler": "3",       # Clinical practice guideline
    "tracking_exercise": "2b",  # Oculomotor rehab studies
}
