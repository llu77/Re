"""
أيقونات التطبيق
===============
تُولَّد هنا وتُحفظ في `eyework/static/`. صندوق منتجٍ هندسي محايد: لا عين ولا
نظر ولا إشارة إلى إعاقة، ولا شيء من علامة المنصّة — الأيقونة على الشاشة
الرئيسية لا تكشف شيئاً عن صاحب الجهاز.

    python eyework/scripts/make_icons.py

حتمية: الأبعاد والألوان ثابتة، فإعادة التوليد تُنتج الملفات نفسها.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "static"
NAVY = (6, 24, 64)
WHITE = (255, 255, 255)
BLUE = (48, 107, 245)
SUPERSAMPLE = 4


def icon(size: int, path: Path, *, inset: float = 0.0) -> None:
    """`inset` يصغّر الرسم داخل المنطقة الآمنة للأيقونة القابلة للقصّ."""
    canvas = size * SUPERSAMPLE
    image = Image.new("RGB", (canvas, canvas), NAVY)
    draw = ImageDraw.Draw(image)
    margin = canvas * (0.24 + inset)
    stroke = max(1, int(canvas * 0.05))
    top, bottom = margin * 1.05, canvas - margin * 0.95
    draw.rounded_rectangle([margin, top, canvas - margin, bottom], radius=canvas * 0.04,
                           outline=WHITE, width=stroke)
    lid = top + (canvas - 2 * margin) * 0.30
    draw.line([margin, lid, canvas - margin, lid], fill=WHITE, width=stroke)
    label_w, label_h = (canvas - 2 * margin) * 0.34, (canvas - 2 * margin) * 0.16
    centre, label_top = canvas / 2, lid + (bottom - lid) * 0.38
    draw.rounded_rectangle([centre - label_w / 2, label_top, centre + label_w / 2, label_top + label_h],
                           radius=canvas * 0.015, fill=BLUE)
    image.resize((size, size), Image.Resampling.LANCZOS).save(path, optimize=True)


def main() -> None:
    icon(192, STATIC / "icon-192.png")
    icon(512, STATIC / "icon-512.png")
    icon(512, STATIC / "icon-maskable-512.png", inset=0.06)
    icon(180, STATIC / "apple-touch-icon.png")


if __name__ == "__main__":
    main()
