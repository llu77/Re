"""
التحقق من الصور — القاعدة 4
=============================
«كل صورة أو رسم يصل المريض يجب أن يجتاز تحققاً آلياً من الجانب المصاب، ثم
اعتماد ممارس. الصورة الفاشلة تُحجب ولا يوجد مسار تسليم بديل.»

**ما يُفحص هو المخرَج لا المولِّد.** لو اكتفينا بأن المولِّد استلم
`side="right"` لما أثبتنا شيئاً: ثلاثة من مولّدات هذا المستودع كانت تستقبل
الجانب وتتجاهله تماماً، فتُنتج لكل جانب الصورةَ نفسها حرفياً. التحقق هنا
يقيس أين يقع «حبر» الصورة فعلاً بالنسبة لخط المنتصف، ويحكم على ما رآه.

اصطلاح الجانب: يسار الصورة هو يسار المريض (لا انعكاس كما في الأشعة). هذا هو
الاصطلاح الذي تتبعه `tools/visual_exercises.py` أصلاً.

الفحص الثاني هو السلامة: البوابة تعرض هذا الـSVG كترميم لا كنصّ، فأي
`<script>` أو معالج حدث أو مرجع خارجي فيه ثغرةُ تنفيذ على جهاز المريض.
القائمة بيضاء: ما ليس مسموحاً صراحةً مرفوض.
"""

from __future__ import annotations

import hashlib
import math
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

__all__ = [
    "BILATERAL_TOLERANCE",
    "IllustrationRejected",
    "LATERAL_THRESHOLD",
    "SIDE_BEARING_TYPES",
    "SIDE_NEUTRAL_TYPES",
    "Verdict",
    "payload_digest",
    "verify",
]

_SVG_NS = "http://www.w3.org/2000/svg"

#: أنواع يحمل رسمها جانباً سريرياً: اتجاه المسح والقراءة والتتبّع يتغيّر
#: بتغيّر الجانب المصاب (العمى الشقي مثالاً).
SIDE_BEARING_TYPES: frozenset[str] = frozenset(
    {"scanning_grid", "tracking_exercise", "reading_ruler"}
)

#: أنواع لا جانب لها: لوحة التباين وتثبيت النظر متماثلتان بطبيعتهما. طلب
#: LEFT أو RIGHT عليهما يُرفض بدل أن يُسلَّم رسمٌ لا يحمل ما وُعد به.
SIDE_NEUTRAL_TYPES: frozenset[str] = frozenset({"contrast_chart", "fixation_cross"})

#: العتبتان مقيستان لا مختارتان.
#:
#: قياس كل مولّد عند كل صعوبة (1-5) أعطى: أضعف إشارة جانبية 0.167، وأقصى
#: ضجيج في رسمٍ للجانبين 0.075. فالعتبتان تقعان داخل تلك الفجوة بهامش على
#: الطرفين، ولا تتداخلان: رسمٌ بانحياز بين 0.10 و0.14 يفشل في الحالتين —
#: وهو الصواب، لأن جانباً غامضاً هو بالضبط ما يجب حجبه.
#:
#: `test_every_generator_stays_outside_the_thresholds` يعيد القياس في كل
#: بناء، فتعديلٌ يُضعف العلامة يُسقط البناء بدل أن يمرّ صامتاً.
LATERAL_THRESHOLD = 0.14

#: أقصى انحياز مسموح لصورة تدّعي أنها للجانبين.
BILATERAL_TOLERANCE = 0.10

#: مستطيل يغطي هذه النسبة من اللوحة خلفيةٌ لا محتوى. إدخاله في الحساب
#: يُخفّف كل انحياز إلى الصفر مهما كان الرسم منحازاً.
_BACKGROUND_COVERAGE = 0.55

#: عناصر SVG المسموح بها. ما ليس هنا مرفوض — لا استثناء ولا تنقية جزئية.
_ALLOWED_TAGS = frozenset({
    "svg", "g", "defs", "title", "desc",
    "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text",
    "tspan", "animate", "animateTransform", "linearGradient", "radialGradient",
    "stop", "clipPath", "mask",
})

#: سمات مسموح بها. `on*` غائبة عمداً، وكذلك كل ما يحمل مرجعاً خارجياً.
_ALLOWED_ATTRS = frozenset({
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "d", "points", "transform", "viewBox", "xmlns",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-dasharray",
    "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity",
    "font-size", "font-family", "font-weight", "text-anchor", "dominant-baseline",
    "class", "id", "style", "offset", "stop-color", "stop-opacity",
    "attributeName", "values", "dur", "repeatCount", "begin", "from", "to", "type",
    "gradientUnits", "clip-path", "mask", "preserveAspectRatio",
})

#: ما لا يجوز أن يظهر في `style` مهما كان السياق.
_FORBIDDEN_STYLE = re.compile(r"(url\s*\(|expression\s*\(|javascript:|@import)", re.I)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

AffectedSideValue = Literal["LEFT", "RIGHT", "BILATERAL"]


class IllustrationRejected(Exception):
    """الصورة لا تُسلَّم. لا مسار بديل، ولا نسخة «مقبولة جزئياً»."""


@dataclass(frozen=True, slots=True)
class Verdict:
    """
    نتيجة التحقق.

    `svg_sha256` بصمة هذه الصورة وحدها. بصمة حمولة المقترح تحسبها قاعدة
    البيانات لا هذا الملف: تمثيل `jsonb` النصّي مُطبَّع بقواعدها، وتطبيقُ
    تطبيع ثانٍ في بايثون يفترق عنه يوماً ما بصمت.

    `bias` موجب نحو يمين الصورة وسالب نحو يسارها، منسوبٌ إلى نصف العرض:
    القيمة 1.0 تعني أن كل الحبر عند الحافة. تُخزَّن مع الحكم ليُقرأ لاحقاً
    لماذا قُبلت صورة أو رُفضت، بدل «نجح/فشل» بلا سبب.
    """

    exercise_type: str
    side: AffectedSideValue
    bias: float
    element_count: int
    svg_sha256: str

    @property
    def is_side_bearing(self) -> bool:
        return self.exercise_type in SIDE_BEARING_TYPES


def payload_digest(payload: str) -> str:
    """
    بصمة المحتوى الذي جرى التحقق منه.

    التحقق مرتبط بالبصمة لا بالمقترح: تعديل الحمولة بعد التحقق يُبطله
    تلقائياً، فلا تُعتمد صورةٌ غير التي فُحصت.
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── السلامة ─────────────────────────────────────────────────────────────
def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _assert_safe(root: ElementTree.Element) -> None:
    for element in root.iter():
        name = _local_name(element.tag)
        if name not in _ALLOWED_TAGS:
            raise IllustrationRejected(f"عنصر غير مسموح في الرسم: <{name}>")

        for attribute, value in element.attrib.items():
            attribute_name = _local_name(attribute)
            if attribute_name.lower().startswith("on"):
                raise IllustrationRejected(f"معالج حدث في الرسم: {attribute_name}")
            if attribute_name in {"href", "xlink:href"}:
                raise IllustrationRejected("مرجع خارجي في الرسم")
            if attribute_name not in _ALLOWED_ATTRS:
                raise IllustrationRejected(f"سمة غير مسموحة في الرسم: {attribute_name}")
            if attribute_name == "style" and _FORBIDDEN_STYLE.search(value):
                raise IllustrationRejected("نمط يحمل مرجعاً أو تنفيذاً")


# ── القياس ──────────────────────────────────────────────────────────────
def _numbers(value: str | None) -> list[float]:
    return [float(found) for found in _NUMBER.findall(value or "")]


def _float(element, name: str, default: float = 0.0) -> float:
    try:
        return float(element.get(name, default))
    except (TypeError, ValueError):
        return default


def _ink(element, canvas_area: float) -> tuple[float, float] | None:
    """(مركز أفقي، وزن) لعنصر واحد، أو `None` إن لم يكن حبراً يُحسب."""
    name = _local_name(element.tag)

    if name == "rect":
        width, height = _float(element, "width"), _float(element, "height")
        if width <= 0 or height <= 0:
            return None
        if canvas_area and (width * height) / canvas_area >= _BACKGROUND_COVERAGE:
            return None            # خلفية، لا محتوى
        return _float(element, "x") + width / 2, width * height

    if name in {"circle", "ellipse"}:
        radius_x = _float(element, "r") or _float(element, "rx")
        radius_y = _float(element, "r") or _float(element, "ry") or radius_x
        if radius_x <= 0:
            return None
        return _float(element, "cx"), math.pi * radius_x * radius_y

    if name == "line":
        x1, x2 = _float(element, "x1"), _float(element, "x2")
        y1, y2 = _float(element, "y1"), _float(element, "y2")
        length = math.hypot(x2 - x1, y2 - y1)
        thickness = _float(element, "stroke-width", 1.0)
        return (x1 + x2) / 2, max(length * thickness, 1.0)

    if name == "text":
        body = "".join(element.itertext()).strip()
        if not body:
            return None
        size = _float(element, "font-size", 12.0)
        # النصّ العربي يمتدّ يساراً من نقطة الإرساء، والإنجليزي يميناً؛
        # نكتفي بنقطة الإرساء: تقدير الامتداد يضيف خطأً أكبر مما يزيل.
        return _float(element, "x"), max(len(body) * size * 0.5, 1.0)

    if name in {"polyline", "polygon"}:
        coordinates = _numbers(element.get("points"))
        xs, ys = coordinates[0::2], coordinates[1::2]
        if not xs:
            return None
        if name == "polygon" and len(xs) >= 3:
            # مساحة ومركز المضلّع بصيغة رباط الحذاء. تقدير الوزن بعدد
            # النقاط كان يُسقط سهماً كبيراً إلى وزن ثلاث نقاط، فيختفي من
            # القياس رغم أنه أبرز ما في الصورة.
            area2 = 0.0
            centroid = 0.0
            for i in range(len(xs)):
                j = (i + 1) % len(xs)
                cross = xs[i] * ys[j] - xs[j] * ys[i]
                area2 += cross
                centroid += (xs[i] + xs[j]) * cross
            if abs(area2) > 1e-9:
                return centroid / (3 * area2), abs(area2) / 2
        return sum(xs) / len(xs), max(len(xs) * 10.0, 1.0)

    if name == "path":
        coordinates = _numbers(element.get("d"))
        xs = coordinates[0::2]
        if not xs:
            return None
        thickness = _float(element, "stroke-width", 1.0)
        return sum(xs) / len(xs), max(len(xs) * thickness * 4.0, 1.0)

    return None


def _lateral_bias(root: ElementTree.Element) -> tuple[float, int]:
    """
    انحياز الحبر أفقياً، من -1 (كله يسار) إلى +1 (كله يمين).

    الوزن بالمساحة: هدفٌ كبير يزن أكثر من خطّ رفيع، وهو ما تراه العين.
    """
    viewbox = _numbers(root.get("viewBox")) or [
        0.0, 0.0, _float(root, "width", 0.0), _float(root, "height", 0.0)
    ]
    width = viewbox[2] if len(viewbox) >= 4 and viewbox[2] > 0 else _float(root, "width", 0.0)
    height = viewbox[3] if len(viewbox) >= 4 and viewbox[3] > 0 else _float(root, "height", 0.0)
    if width <= 0:
        raise IllustrationRejected("الرسم بلا عرض معروف، فلا يمكن قياس جانبه")

    midline = width / 2
    canvas_area = width * height

    moment = 0.0
    total = 0.0
    counted = 0
    for element in root.iter():
        measured = _ink(element, canvas_area)
        if measured is None:
            continue
        centre, weight = measured
        moment += weight * (centre - midline)
        total += weight
        counted += 1

    if total <= 0:
        raise IllustrationRejected("لا حبر في الرسم يُقاس")
    return moment / (total * midline), counted


# ── الحكم ───────────────────────────────────────────────────────────────
def verify(svg: str, *, exercise_type: str, side: AffectedSideValue) -> Verdict:
    """
    يتحقق من صورة واحدة، أو يرفع `IllustrationRejected`.

    الرفض هو المخرج الوحيد عند الفشل: لا قيمة إرجاع تقول «مشكوك فيها»، لأن
    قيمةً كهذه تحتاج من يقرّر بشأنها، والقاعدة 4 تقول إن الصورة الفاشلة
    تُحجب.
    """
    if side not in ("LEFT", "RIGHT", "BILATERAL"):
        raise IllustrationRejected(f"جانب غير معروف: {side}")

    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise IllustrationRejected(f"رسم غير صالح: {exc}") from exc

    if _local_name(root.tag) != "svg":
        raise IllustrationRejected("الجذر ليس <svg>")

    _assert_safe(root)
    bias, counted = _lateral_bias(root)

    known = SIDE_BEARING_TYPES | SIDE_NEUTRAL_TYPES
    if exercise_type not in known:
        raise IllustrationRejected(
            f"نوع تمرين غير مصنَّف: {exercise_type}. التصنيف شرط للتحقق."
        )

    if exercise_type in SIDE_NEUTRAL_TYPES:
        if side != "BILATERAL":
            raise IllustrationRejected(
                f"النوع {exercise_type} لا يحمل جانباً، فلا يُطلب له {side}"
            )
        if abs(bias) > BILATERAL_TOLERANCE:
            raise IllustrationRejected(
                f"رسمٌ يُفترض تماثله منحازٌ بمقدار {bias:+.3f}"
            )
    elif side == "BILATERAL":
        if abs(bias) > BILATERAL_TOLERANCE:
            raise IllustrationRejected(
                f"طُلب رسم للجانبين وجاء منحازاً بمقدار {bias:+.3f}"
            )
    else:
        wanted = -1 if side == "LEFT" else 1
        if bias * wanted < LATERAL_THRESHOLD:
            raise IllustrationRejected(
                f"الرسم لا يمثّل الجانب {side}: الانحياز {bias:+.3f}"
            )

    return Verdict(
        exercise_type=exercise_type,
        side=side,
        bias=round(bias, 4),
        element_count=counted,
        svg_sha256=payload_digest(svg),
    )


def verify_set(
    illustrations: Sequence[Mapping[str, str]], *, side: AffectedSideValue
) -> list[Verdict]:
    """
    يتحقق من مجموعة صور. **الرفض جماعي:** صورة واحدة تفشل تُسقط المجموعة.

    التسليم الجزئي هو بالضبط «مسار التسليم البديل» الذي تمنعه القاعدة 4.
    """
    if not illustrations:
        raise IllustrationRejected("مجموعة صور فارغة")

    return [
        verify(item["svg"], exercise_type=item["exercise_type"], side=side)
        for item in illustrations
    ]
