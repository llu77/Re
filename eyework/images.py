"""
معالجة صورة المنتج
==================
بايتاتٌ تدخل، وصورة JPEG نظيفةٌ تخرج — أو رفضٌ برمزٍ ثابت. لا شبكة ولا
قاعدة هنا؛ دالّةٌ نقية تُختبر وحدها.

**لماذا إعادة الترميز لا الحذف الانتقائي.** صورة iPhone تحمل في EXIF موقع
التقاطها، وقد يكون بيت المستخدم. حذف الحقول واحداً واحداً يترك ما لم
يُعرف: XMP، وملفّ ICC، ونصوص PNG، وبيانات المصنّع. أمّا رسم البكسلات في
صورةٍ جديدة لا معلومات فيها ثم ترميزها فلا يُبقي إلا البكسلات. والقاعدة
ترفض بقيدٍ ثانٍ أيّ صورةٍ مخزّنة فيها توقيع EXIF أو XMP.

**ما يُرسل إلى النموذج هو ما يُخزَّن وهو ما يراه المستخدم.** النسخة الأصلية
لا تُكتب على قرص ولا في قاعدة، وتُترك لجامع الذاكرة عند نهاية الطلب.

**الدفاع عن الذاكرة.** الأبعاد تُقرأ من الترويسة قبل فكّ الضغط، فصورةٌ تعلن
ستين ألف بكسل في ستين ألفاً تُرفض قبل أن تُخصّص لها ذاكرة. وفكّ JPEG كبيرة
يكون بمقياسٍ مصغّر (`draft`) لا بالحجم الكامل. ولا تُفكّ أكثر من صورتين
معاً.
"""

from __future__ import annotations

import hashlib
import io
import threading
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps

__all__ = [
    "ACCEPTED_TYPES",
    "MAX_UPLOAD_BYTES",
    "ImageRejected",
    "ProcessedImage",
    "process",
]

#: أكبر ملفٍّ يُقبل. صورة iPhone بدقّة 48 ميغابكسل تقارب عشرة ميغابايت.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

#: الأنواع المقبولة، كما يعلنها حقل الملف. نوع الملف الفعلي يُقرأ من بايتاته.
#: HEIC ليس منها: Safari يحوّله إلى JPEG حين لا يقبله الحقل.
ACCEPTED_TYPES = ("image/jpeg", "image/png", "image/webp")
_FORMATS = ("JPEG", "PNG", "WEBP")

#: صورة iPhone بصيغة JPEG تحمل غالباً صورةً ثانية (خريطة HDR) في امتداد MPF،
#: فيفتحها Pillow بصيغة «MPO» بإطارين. هي صورةٌ واحدة لا متحرّكة: يُؤخذ
#: إطارها الأول وتُعامل معاملة JPEG. والحركة تُفحص في PNG وWebP وحدهما.
_JPEG_FAMILY = ("JPEG", "MPO")
_ANIMATABLE = ("PNG", "WEBP")

#: الحافّة الطويلة للناتج — ما يقبله النموذج دون تصغيرٍ إضافي من جهته.
LONG_EDGE = 1568
MIN_SHORT_EDGE = 320
MAX_LONG_EDGE = 12_000
MAX_ASPECT = 4.0

#: حدّ البكسلات قبل فكّ الضغط. JPEG تُفكّ مصغّرةً فتحتمل أكثر؛ PNG وWebP
#: تُفكّ كاملة.
_MAX_PIXELS = {"JPEG": 50_000_000, "MPO": 50_000_000, "PNG": 4096 * 4096, "WEBP": 4096 * 4096}

#: سقف الناتج، ونظيره قيد CHECK في `campaign_images`.
MAX_OUTPUT_BYTES = 3 * 1024 * 1024
_QUALITY = 85

_EXIF_SIGNATURE = b"Exif\x00\x00"
_XMP_NAMESPACE = b"http://ns.adobe.com/xap/"

_decoding = threading.BoundedSemaphore(2)


class ImageRejected(Exception):
    """صورةٌ لا تُقبل. `code` رمزٌ ثابت تترجمه طبقة الويب إلى رسالة عربية."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    jpeg: bytes
    width: int
    height: int
    sha256: bytes


def _open(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data), formats=_FORMATS)
    except Image.DecompressionBombError as exc:
        # Pillow يفحص الأبعاد عند الفتح بحدٍّ أعلى من حدّنا؛ ما تجاوز حدّه
        # تجاوز حدّنا من باب أولى.
        raise ImageRejected("TOO_MANY_PIXELS") from exc
    except Image.UnidentifiedImageError as exc:
        raise ImageRejected("UNSUPPORTED_TYPE") from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise ImageRejected("CORRUPT") from exc
    return image


def _check_header(image: Image.Image) -> None:
    width, height = image.size
    if image.format not in _MAX_PIXELS:
        raise ImageRejected("UNSUPPORTED_TYPE")
    if width * height > _MAX_PIXELS[image.format]:
        raise ImageRejected("TOO_MANY_PIXELS")
    if min(width, height) < MIN_SHORT_EDGE:
        raise ImageRejected("TOO_SMALL")
    if max(width, height) > MAX_LONG_EDGE:
        raise ImageRejected("TOO_MANY_PIXELS")
    if max(width, height) / min(width, height) > MAX_ASPECT:
        raise ImageRejected("BAD_ASPECT")
    if image.format in _ANIMATABLE and getattr(image, "n_frames", 1) > 1:
        raise ImageRejected("ANIMATED")


def _target_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, LONG_EDGE / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def _to_srgb(image: Image.Image) -> Image.Image:
    """
    ملفّ ألوانٍ مضمَّن (Display P3 في صور iPhone) يُحوَّل إلى sRGB قبل حذفه.

    حذفه دون تحويل يُبهت الألوان؛ والحذف لازمٌ لأن الملفّ نفسه بياناتٌ
    وصفية. ملفٌّ تالف لا يُسقط الصورة: يُتجاهل، والتحويل العادي يكفي.
    """
    profile = image.info.get("icc_profile")
    if profile and image.mode in ("RGB", "RGBA", "CMYK"):
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
            target = ImageCms.createProfile("sRGB")
            mode = "RGBA" if image.mode == "RGBA" else "RGB"
            converted = ImageCms.profileToProfile(image, source, target, outputMode=mode)
            if converted is not None:
                return converted
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    return image


def _flatten(image: Image.Image) -> Image.Image:
    """الشفافية تُركَّب على أبيض؛ الناتج RGB بلا قناة ألفا."""
    has_alpha = image.mode in ("RGBA", "LA", "PA") or (
        image.mode == "P" and "transparency" in image.info
    )
    if has_alpha:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _encode(image: Image.Image) -> bytes:
    """
    البكسلات وحدها في صورةٍ جديدة: `Image.new` لا تحمل `info`، فلا EXIF ولا
    ICC ولا XMP يمكن أن يتسرّب إلى الحفظ.
    """
    clean = Image.new("RGB", image.size)
    clean.paste(image)
    buffer = io.BytesIO()
    clean.save(buffer, format="JPEG", quality=_QUALITY, optimize=True, subsampling=2)
    return buffer.getvalue()


def process(data: bytes) -> ProcessedImage:
    """يقبل صورةً أو يرفضها برمزٍ ثابت. لا يكتب شيئاً ولا يرسل شيئاً."""
    if not data:
        raise ImageRejected("EMPTY")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageRejected("TOO_LARGE")

    with _decoding:
        image = _open(data)
        try:
            _check_header(image)
            if image.format in _JPEG_FAMILY:
                if image.format == "MPO":
                    image.seek(0)
                # فكٌّ بأصغر مقياسٍ لا ينزل عن حجم الناتج.
                image.draft("RGB", _target_size(*image.size))
            image.load()
        except ImageRejected:
            raise
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ImageRejected("CORRUPT") from exc

        # الاتجاه أولاً، لأنه يُقرأ من EXIF الذي سيُحذف.
        image = ImageOps.exif_transpose(image)
        image = _flatten(_to_srgb(image))
        image.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
        jpeg = _encode(image)

    width, height = image.size
    # حواجز على الناتج نفسه: إن أخطأ شيءٌ أعلاه فلا يُخزَّن.
    if not jpeg.startswith(b"\xff\xd8\xff"):
        raise ImageRejected("CORRUPT")
    if _EXIF_SIGNATURE in jpeg or _XMP_NAMESPACE in jpeg:
        raise ImageRejected("METADATA_SURVIVED")
    if len(jpeg) > MAX_OUTPUT_BYTES:
        raise ImageRejected("TOO_LARGE")
    if min(width, height) < MIN_SHORT_EDGE or max(width, height) > LONG_EDGE:
        raise ImageRejected("TOO_SMALL")

    return ProcessedImage(jpeg=jpeg, width=width, height=height, sha256=hashlib.sha256(jpeg).digest())
