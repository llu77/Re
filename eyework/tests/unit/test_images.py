"""
صورة المنتج
===========
صورة iPhone تحمل موقع التقاطها. هذه الاختبارات تثبت أن ما يُخزَّن ويُرسل
بكسلاتٌ وحدها، وأن ما يُرهق الذاكرة يُرفض قبل أن يُفكّ.
"""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from PIL import Image, ImageCms

from eyework.images import LONG_EDGE, MAX_UPLOAD_BYTES, ImageRejected, process


def _noise(size, mode="RGB"):
    return Image.effect_noise(size, 60).convert(mode)


def _encode(image, fmt, **options):
    buffer = io.BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def _png_header_only(width, height):
    """ترويسة PNG تعلن أبعاداً هائلة، بلا بيانات — قنبلة فكّ الضغط النموذجية."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    end = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    return b"\x89PNG\r\n\x1a\n" + chunk + end


def test_gps_exif_never_survives():
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (24.0, 42.0, 0.0), 3: "E", 4: (46.0, 43.0, 0.0)}
    data = _encode(_noise((1200, 900)), "JPEG", exif=exif.tobytes())
    assert b"Exif\x00\x00" in data

    result = process(data)
    assert b"Exif" not in result.jpeg
    assert result.jpeg.startswith(b"\xff\xd8\xff")


def test_orientation_is_applied_before_metadata_is_dropped():
    exif = Image.Exif()
    exif[0x0112] = 6  # مُدار ٩٠°
    result = process(_encode(_noise((4032, 3024)), "JPEG", exif=exif.tobytes()))
    assert (result.width, result.height) == (1176, LONG_EDGE)


def test_xmp_and_icc_never_survive():
    xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://ns.adobe.com/xap/1.0/"/></x:xmpmeta>'
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    result = process(_encode(_noise((600, 600)), "JPEG", xmp=xmp, icc_profile=icc))
    assert b"ns.adobe.com/xap" not in result.jpeg
    assert b"ICC_PROFILE" not in result.jpeg


def test_large_photo_is_downscaled_to_the_long_edge():
    result = process(_encode(_noise((4032, 3024)), "JPEG"))
    assert max(result.width, result.height) == LONG_EDGE


def test_transparency_is_flattened():
    image = _noise((800, 600)).convert("RGBA")
    image.putalpha(0)
    result = process(_encode(image, "PNG"))
    decoded = Image.open(io.BytesIO(result.jpeg))
    assert decoded.mode == "RGB"
    assert decoded.getpixel((400, 300))[0] > 240  # شفافٌ تماماً ⇒ أبيض


def test_cmyk_is_converted():
    result = process(_encode(_noise((1000, 800), "CMYK"), "JPEG"))
    assert Image.open(io.BytesIO(result.jpeg)).mode == "RGB"


def test_appended_payload_does_not_survive():
    """ملفّ JPEG ذيّله HTML: لا يبقى إلا ما أُعيد رسمه."""
    data = _encode(_noise((600, 600)), "JPEG") + b"<script>steal()</script>"
    assert b"script" not in process(data).jpeg


@pytest.mark.parametrize(("data", "code"), [
    pytest.param(b"", "EMPTY", id="empty"),
    pytest.param(b"<html><body>not an image</body></html>" * 4, "UNSUPPORTED_TYPE", id="html"),
    pytest.param(_encode(_noise((400, 400)), "GIF"), "UNSUPPORTED_TYPE", id="gif"),
    pytest.param(_encode(_noise((400, 400)), "BMP"), "UNSUPPORTED_TYPE", id="bmp"),
    pytest.param(_encode(_noise((300, 400)), "JPEG"), "TOO_SMALL", id="short-side-300"),
    pytest.param(_encode(_noise((2000, 400)), "JPEG"), "BAD_ASPECT", id="aspect-5"),
    pytest.param(_encode(_noise((1000, 1000)), "JPEG")[:4000], "CORRUPT", id="truncated"),
    pytest.param(_png_header_only(60_000, 60_000), "TOO_MANY_PIXELS", id="bomb-60k"),
    pytest.param(_png_header_only(5_000, 5_000), "TOO_MANY_PIXELS", id="png-25mp"),
    pytest.param(_png_header_only(13_000, 400), "TOO_MANY_PIXELS", id="long-side-13k"),
])
def test_rejections_carry_a_fixed_code(data, code):
    with pytest.raises(ImageRejected) as caught:
        process(data)
    assert caught.value.code == code


def test_animation_is_rejected():
    frames = [_noise((400, 400)) for _ in range(2)]
    data = _encode(frames[0], "WEBP", save_all=True, append_images=frames[1:])
    with pytest.raises(ImageRejected) as caught:
        process(data)
    assert caught.value.code == "ANIMATED"


def test_oversized_upload_is_rejected_before_decoding():
    with pytest.raises(ImageRejected) as caught:
        process(b"\xff\xd8\xff" + b"\x00" * MAX_UPLOAD_BYTES)
    assert caught.value.code == "TOO_LARGE"


def _markers(jpeg: bytes) -> set[int]:
    """مقاطع JPEG حتى بداية البيانات المضغوطة (SOS)، ثم EOI."""
    found, i = set(), 2
    assert jpeg[:2] == b"\xff\xd8"
    found.add(0xD8)
    while i < len(jpeg):
        assert jpeg[i] == 0xFF, f"بايتٌ غير متوقَّع عند {i}"
        marker = jpeg[i + 1]
        found.add(marker)
        if marker == 0xDA:  # SOS: ما بعده بيانات مضغوطة حتى EOI
            break
        length = int.from_bytes(jpeg[i + 2:i + 4], "big")
        i += 2 + length
    assert jpeg.endswith(b"\xff\xd9")
    found.add(0xD9)
    return found


def test_only_the_markers_a_clean_baseline_jpeg_needs():
    """
    SOI وJFIF وجداول الكمية وهوفمان والإطار والمسح والنهاية — ولا غيرها.

    أيّ APPn غير JFIF (EXIF، ICC، XMP، Photoshop) أو COM (تعليق قد يحمل اسماً)
    يفشل هنا مهما كان مصدره.
    """
    exif = Image.Exif()
    exif[0x010E] = "صورة بيت فلان"
    exif[0x8825] = {1: "N", 2: (24.0, 42.0, 0.0)}
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = _encode(_noise((900, 700)), "JPEG", exif=exif.tobytes(), icc_profile=icc,
                   comment=b"owner: Ahmad", xmp=b"<x:xmpmeta/>")
    assert _markers(process(data).jpeg) == {0xD8, 0xE0, 0xDB, 0xC0, 0xC4, 0xDA, 0xD9}


def test_iphone_multi_picture_jpeg_is_one_photo_not_an_animation():
    """
    صورة iPhone بخريطة HDR تُفتح «MPO» بإطارين. تُقبل بإطارها الأول، ولا يبقى
    من الإطار الثاني ولا من امتداد MPF شيء.
    """
    first, gain_map = _noise((1200, 900)), _noise((600, 450))
    data = _encode(first, "MPO", save_all=True, append_images=[gain_map])
    assert Image.open(io.BytesIO(data)).format == "MPO"
    result = process(data)
    assert (result.width, result.height) == (1200, 900)
    assert result.jpeg.count(b"\xff\xd8") == 1
    assert b"MPF" not in result.jpeg


def test_animated_png_is_rejected():
    frames = [_noise((400, 400)) for _ in range(2)]
    data = _encode(frames[0], "PNG", save_all=True, append_images=frames[1:])
    with pytest.raises(ImageRejected) as caught:
        process(data)
    assert caught.value.code == "ANIMATED"


def test_a_bomb_is_rejected_before_any_pixel_is_decoded(monkeypatch):
    """
    يثبت الترتيب لا الذاكرة: لو وصل الرفض بعد الفكّ لرفع `load` المعطوب هنا
    خطأً آخر. Pillow يخصّص الذاكرة في C فلا يراها tracemalloc، والترتيب هو
    ما يمكن إثباته.
    """
    from PIL import ImageFile

    def refuse(self):
        raise AssertionError("فُكّ ضغط صورةٍ كان يجب رفضها من ترويستها")

    monkeypatch.setattr(ImageFile.ImageFile, "load", refuse)
    with pytest.raises(ImageRejected) as caught:
        process(_png_header_only(9_000, 9_000))
    assert caught.value.code == "TOO_MANY_PIXELS"
