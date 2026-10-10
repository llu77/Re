"""
صورة الحملة في القاعدة
======================
صورة الهاتف قد تحمل في EXIF أو XMP موقع التقاطها — بيت صاحبها أحياناً.
التطبيق يعيد ترميز كل صورةٍ فلا يبقى منها إلا البكسلات؛ وقيود
`campaign_images` حاجزٌ ثانٍ يصمد لو أخطأ ذلك المسار، ولو كتب المالك نفسه.

والصورة تُثبَّت بعد أوّل نصٍّ كُتب عنها — ومنذ أن يقرأها النموذج ليكتبه —
فلا يتغيّر المنتج تحت نصٍّ وصفه؛ وتُحذف مع الإلغاء في المعاملة نفسها، فلا
تبقى صورةُ حملةٍ ملغاة ولا يضيع الحذف إن تراجعت المعاملة. ودور الويب لا يحذف
شيئاً بنفسه. والحدود نظيرُ `eyework/images.py`: القاعدة تقبل كل ما يُخرجه.
"""

from __future__ import annotations

import functools
import hashlib
import io
from contextlib import contextmanager
from uuid import UUID

import psycopg
import pytest
from PIL import Image
from psycopg import errors

from eyework import campaigns
from eyework.images import LONG_EDGE, MAX_OUTPUT_BYTES, MIN_SHORT_EDGE, process
from eyework.states import Status
from eyework.tests.conftest import DESCRIPTION, TITLE, add_version, create_campaign, make_user, row_version

EXIF_SIGNATURE = b"Exif\x00\x00"
XMP_NAMESPACE = b"http://ns.adobe.com/xap/"
XMP_PACKET = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>'
XMP_INLINE = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
    b' xmp:CreatorTool="Camera"/></x:xmpmeta>'
)

_COUNT = "SELECT count(*) FROM campaign_images WHERE campaign_id = %s"
_DIGEST = "SELECT sha256 FROM campaign_images WHERE campaign_id = %s"


#: قيود الصورة تُفحص بترتيب أسمائها، فقد يسبق فحصُ «لا بيانات وصفية» (أيّ مقطع
#: APPn أو COM في أيّ موضع) الفحصَ الأضيق. كلاهما رفضٌ صحيح للسبب نفسه.
_ALSO = {"image_has_no_xmp": {"image_has_no_metadata"}, "image_has_no_exif": {"image_has_no_metadata"},
         "image_is_jpeg": {"image_has_no_metadata"}}


@contextmanager
def rejected(error: type[Exception], constraint: str | None = None):
    with pytest.raises(error) as caught:
        yield
    if constraint is not None:
        assert caught.value.diag.constraint_name in {constraint, *_ALSO.get(constraint, ())}


def encode(fmt: str = "JPEG", **options) -> bytes:
    buffer = io.BytesIO()
    Image.effect_noise((400, 400), 40).convert("RGB").save(buffer, fmt, **options)
    return buffer.getvalue()


@functools.cache
def clean_image() -> tuple[bytes, int, int]:
    buffer = io.BytesIO()
    Image.effect_noise((640, 480), 40).convert("RGB").save(buffer, "JPEG")
    image = process(buffer.getvalue())
    return image.jpeg, image.width, image.height


def sample_jpeg() -> bytes:
    """صورةٌ نظيفة كما يُخرجها `images.process`، بأبعادٍ فوق حدّه الأدنى."""
    return clean_image()[0]


def new_campaign(app, user: UUID, *, with_image: bool = True) -> UUID:
    """مسودةٌ بدور الويب، وصورتها بعبارة الإدراج الإنتاجية متى طُلبت."""
    campaign = create_campaign(app, user, with_image=False)
    if with_image:
        jpeg, width, height = clean_image()
        insert_image(app, campaign, user, jpeg, width, height)
    return campaign


def gps_exif() -> bytes:
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (24.0, 42.0, 0.0), 3: "E", 4: (46.0, 43.0, 0.0)}
    return exif.tobytes()


def insert_image(connection, campaign: UUID, user: UUID, jpeg: bytes, width: int = 400,
                 height: int = 400) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            campaigns._INSERT_IMAGE,
            (campaign, user, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )


def replace_image(connection, campaign: UUID, jpeg: bytes) -> int:
    with connection.cursor() as cursor:
        cursor.execute(campaigns._REPLACE_IMAGE, (jpeg, 400, 400, hashlib.sha256(jpeg).digest(), campaign))
        return cursor.rowcount


def stored_digest(owner, campaign: UUID) -> bytes | None:
    with owner.cursor() as cursor:
        cursor.execute(_DIGEST, (campaign,))
        row = cursor.fetchone()
    return None if row is None else bytes(row[0])


def image_count(connection, campaign: UUID) -> int:
    with connection.cursor() as cursor:
        cursor.execute(_COUNT, (campaign,))
        return cursor.fetchone()[0]


def campaign_status(connection, campaign: UUID) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT status FROM campaigns WHERE id = %s", (campaign,))
        return cursor.fetchone()[0]


def apply_one(connection, statement: str, params: tuple) -> None:
    """عبارةٌ إنتاجية مشروطة بما رآه صاحبها، يجب أن تصيب صفّها."""
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        assert cursor.rowcount == 1


def begin_first_copy(app, campaign: UUID) -> UUID:
    with app.cursor() as cursor:
        cursor.execute(campaigns._BEGIN, (campaign, "INITIAL", row_version(app, campaign), None))
        return cursor.fetchone()[0]


def write_first_copy(app, user: UUID, campaign: UUID, attempt: UUID) -> None:
    with app.transaction(), app.cursor() as cursor:
        cursor.execute(campaigns._INSERT_VERSION, (
            campaign, user, attempt, TITLE, DESCRIPTION, [], None, [], "claude-opus-5-5", "test", None, None,
        ))
        cursor.execute(campaigns._FINISH, (attempt, "OK", 0, 0))


def applied(action) -> bool:
    """يُطبَّق الفعل أو يُرفض بقيدٍ مسمّى؛ أيّ خطأٍ غير ذلك يُسقط الاختبار."""
    try:
        action()
    except errors.CheckViolation as exc:
        assert exc.diag.constraint_name
        return False
    return True


def drive(app, user: UUID, target: Status) -> UUID:
    """حملةٌ بصورتها في الحالة المطلوبة، بالمسار الإنتاجي."""
    campaign = new_campaign(app, user)
    if target is Status.DRAFT:
        return campaign
    if target is Status.CANCELLED:
        apply_one(app, campaigns._CANCEL, (campaign, row_version(app, campaign)))
        return campaign
    version = add_version(app, user, campaign)
    if target is Status.COPY_PROPOSED:
        return campaign
    apply_one(app, campaigns._APPROVE, (campaign, row_version(app, campaign), version))
    if target is Status.COPY_APPROVED:
        return campaign
    apply_one(app, campaigns._SET_BUDGET, (500, campaign, row_version(app, campaign)))
    apply_one(app, campaigns._SET_DAYS, (10, campaign, row_version(app, campaign)))
    apply_one(app, campaigns._CONFIRM, (campaign, row_version(app, campaign), version, 500, 10))
    return campaign


@pytest.fixture
def user(owner) -> UUID:
    return make_user(owner, login=b"image-owner")


@pytest.fixture
def connection_for(owner, app):
    return {"app": app, "owner": owner}.__getitem__


ROLES = ["app", "owner"]

WITH_EXIF = [
    pytest.param(lambda: encode(exif=gps_exif()), id="app1-segment"),
    pytest.param(lambda: sample_jpeg() + EXIF_SIGNATURE + b"MM\x00*\x00\x00\x00\x08", id="trailing-bytes"),
    pytest.param(lambda: sample_jpeg() + EXIF_SIGNATURE, id="bare-signature"),
]

WITH_XMP = [
    pytest.param(lambda: encode(xmp=XMP_PACKET), id="app1-segment"),
    pytest.param(lambda: sample_jpeg() + XMP_INLINE, id="trailing-bytes"),
    pytest.param(lambda: sample_jpeg() + XMP_NAMESPACE + b"mm/", id="bare-namespace"),
]


# ── ما يُخزَّن بكسلاتٌ وحدها ───────────────────────────────────────────
@pytest.mark.parametrize("role", ROLES)
def test_clean_image_is_stored(owner, app, user, connection_for, role):
    """قيدٌ يرفض صورةً نظيفة كما يُخرجها التطبيق يوقف إنشاء كل حملة."""
    campaign = create_campaign(app, user, with_image=False)
    jpeg, width, height = clean_image()
    insert_image(connection_for(role), campaign, user, jpeg, width, height)
    assert stored_digest(owner, campaign) == hashlib.sha256(jpeg).digest()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("make", WITH_EXIF)
def test_exif_is_rejected_even_for_the_owner(app, user, connection_for, role, make):
    """توقيع EXIF في صورةٍ مخزّنة قد يحمل موقع بيت صاحبها إلى كل من يراها."""
    jpeg = make()
    assert jpeg.startswith(b"\xff\xd8\xff") and EXIF_SIGNATURE in jpeg and XMP_NAMESPACE not in jpeg
    campaign = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "image_has_no_exif"):
        insert_image(connection_for(role), campaign, user, jpeg)
    assert image_count(app, campaign) == 0


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("make", WITH_XMP)
def test_xmp_is_rejected_even_for_the_owner(app, user, connection_for, role, make):
    """حزمة XMP تحمل ما فات التنظيف من EXIF: الجهاز والتاريخ والموقع أحياناً."""
    jpeg = make()
    assert jpeg.startswith(b"\xff\xd8\xff") and XMP_NAMESPACE in jpeg and EXIF_SIGNATURE not in jpeg
    campaign = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "image_has_no_xmp"):
        insert_image(connection_for(role), campaign, user, jpeg)
    assert image_count(app, campaign) == 0


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(("make", "constraint"), [
    pytest.param(lambda: encode(exif=gps_exif()), "image_has_no_exif", id="exif"),
    pytest.param(lambda: encode(xmp=XMP_PACKET), "image_has_no_xmp", id="xmp"),
])
def test_metadata_cannot_arrive_by_replacement(owner, app, user, connection_for, role, make, constraint):
    """استبدالٌ يتجاوز ما يفحصه الإدراج يُدخل البيانات الوصفية من الباب الثاني — ولو بيد المالك."""
    campaign = new_campaign(app, user)
    before = stored_digest(owner, campaign)
    with rejected(errors.CheckViolation, constraint):
        replace_image(connection_for(role), campaign, make())
    assert stored_digest(owner, campaign) == before


@pytest.mark.parametrize("make", [
    pytest.param(lambda: encode("PNG"), id="png"),
    pytest.param(lambda: encode("WEBP"), id="webp"),
    pytest.param(lambda: encode("GIF"), id="gif"),
    pytest.param(lambda: b"\xff\xd8" + bytes(1024), id="truncated-marker"),
    pytest.param(lambda: b"<svg xmlns='http://www.w3.org/2000/svg'/>", id="svg"),
])
def test_non_jpeg_is_rejected(app, user, make):
    """ملفٌّ غير JPEG لم يمرّ بإعادة الترميز، فقد يحمل كل ما كان فيه."""
    campaign = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "image_is_jpeg"):
        insert_image(app, campaign, user, make())


def test_image_at_the_output_limit_is_accepted(app, user):
    """القاعدة تقبل كل ما قد يُخرجه `images.py`، حتى آخر بايت من حدّه."""
    jpeg = sample_jpeg()
    jpeg += bytes(MAX_OUTPUT_BYTES - len(jpeg))
    campaign = create_campaign(app, user, with_image=False)
    insert_image(app, campaign, user, jpeg)
    assert image_count(app, campaign) == 1


def test_image_over_three_mebibytes_is_rejected(app, user):
    """صورةٌ فوق الحدّ تُضخّم كلفة كل طلبٍ إلى النموذج وكل نسخةٍ احتياطية."""
    assert MAX_OUTPUT_BYTES == 3 * 1024 * 1024
    jpeg = sample_jpeg()
    jpeg += bytes(MAX_OUTPUT_BYTES + 1 - len(jpeg))
    campaign = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "image_size"):
        insert_image(app, campaign, user, jpeg)


@pytest.mark.parametrize(("width", "height", "constraint"), [
    (319, 400, "campaign_images_width_check"),
    (1569, 400, "campaign_images_width_check"),
    (400, 319, "campaign_images_height_check"),
    (400, 1569, "campaign_images_height_check"),
])
def test_dimensions_outside_bounds_are_rejected(app, user, width, height, constraint):
    """أبعادٌ خارج ما يُخرجه التطبيق تعني صورةً لم تمرّ به، أو وصفاً كاذباً لها."""
    campaign = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, constraint):
        insert_image(app, campaign, user, sample_jpeg(), width=width, height=height)


@pytest.mark.parametrize(("width", "height"), [
    (320, 320), (1568, 1568), (320, 1568), (MIN_SHORT_EDGE, LONG_EDGE), (LONG_EDGE, MIN_SHORT_EDGE),
])
def test_dimension_bounds_are_accepted(app, user, width, height):
    """حدٌّ أضيق في القاعدة يرفض صورةً قبلها التطبيق بعد أن دفع المستخدم ثمن رفعها."""
    campaign = create_campaign(app, user, with_image=False)
    insert_image(app, campaign, user, sample_jpeg(), width=width, height=height)
    assert image_count(app, campaign) == 1


# ── الصورة تُثبَّت بعد أوّل نصّ ────────────────────────────────────────
def test_image_can_be_replaced_while_draft(owner, app, user):
    """منعُ الاستبدال في المسودة يُلزم صاحبها بصورةٍ رفعها خطأً."""
    campaign = new_campaign(app, user)
    jpeg = encode()
    assert replace_image(app, campaign, jpeg) == 1
    assert stored_digest(owner, campaign) == hashlib.sha256(jpeg).digest()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("status", [Status.COPY_PROPOSED, Status.COPY_APPROVED, Status.READY])
def test_image_is_fixed_once_copy_exists(owner, app, user, connection_for, role, status):
    """صورةٌ تُستبدل تحت نصٍّ كُتب عنها تجعل الإعلان يصف منتجاً غير المعروض."""
    campaign = drive(app, user, status)
    before = stored_digest(owner, campaign)
    with rejected(errors.CheckViolation, "image_only_in_draft"):
        replace_image(connection_for(role), campaign, encode())
    assert stored_digest(owner, campaign) == before


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("status", [Status.COPY_PROPOSED, Status.COPY_APPROVED, Status.READY, Status.CANCELLED])
def test_image_cannot_be_added_outside_draft(owner, app, user, connection_for, role, status):
    """صورةٌ تُضاف بعد النصّ أو بعد الإلغاء تُعيد ما حُذف أو تُبدّل ما وُصف — ولو بيد المالك."""
    campaign = drive(app, user, status)
    before = stored_digest(owner, campaign)
    with rejected(errors.CheckViolation, "image_only_in_draft"):
        insert_image(connection_for(role), campaign, user, encode())
    assert stored_digest(owner, campaign) == before


def test_image_cannot_change_while_its_first_copy_is_written(owner, app, user):
    """النموذج يقرأ الصورة ثم يكتب نحو دقيقة؛ صورةٌ تُستبدل بينهما تُخرج نصّاً يصف منتجاً غير الذي فوقه."""
    campaign = new_campaign(app, user)
    described = stored_digest(owner, campaign)
    attempt = begin_first_copy(app, campaign)
    replaced = applied(lambda: replace_image(app, campaign, encode()))
    written = applied(lambda: write_first_copy(app, user, campaign, attempt))
    assert (replaced, written) in {(False, True), (True, False)}
    if written:
        assert stored_digest(owner, campaign) == described


def test_owner_cannot_move_an_image_to_another_campaign(owner, app, user):
    """صورةٌ تنتقل بين الحملات تجعل نصّاً كُتب عن منتجٍ يظهر فوق منتجٍ آخر."""
    source = new_campaign(app, user)
    target = create_campaign(app, user, with_image=False)
    with rejected(errors.CheckViolation, "image_only_in_draft"):
        with owner.cursor() as cursor:
            cursor.execute("UPDATE campaign_images SET campaign_id = %s WHERE campaign_id = %s", (target, source))
    assert (image_count(owner, source), image_count(owner, target)) == (1, 0)


def test_app_cannot_move_an_image(app, user):
    """منحٌ على عمود الحملة أو المستخدم يفتح للخادم نقل صورةٍ إلى غير صاحبها."""
    campaign = new_campaign(app, user)
    for statement in (
        "UPDATE campaign_images SET campaign_id = campaign_id WHERE campaign_id = %s",
        "UPDATE campaign_images SET user_id = user_id WHERE campaign_id = %s",
        "UPDATE campaign_images SET created_at = now() WHERE campaign_id = %s",
    ):
        with rejected(errors.InsufficientPrivilege):
            with app.cursor() as cursor:
                cursor.execute(statement, (campaign,))


# ── الإلغاء يحذف الصورة ────────────────────────────────────────────────
@pytest.mark.parametrize("status", [Status.DRAFT, Status.COPY_PROPOSED, Status.COPY_APPROVED, Status.READY])
def test_cancel_deletes_the_image_in_the_same_transaction(owner, app, user, status):
    """صورةٌ تبقى بعد الإلغاء صورةُ منتجٍ لا عمل لها، محفوظةٌ بلا سبب."""
    campaign = drive(app, user, status)
    assert image_count(owner, campaign) == 1
    with app.transaction():
        apply_one(app, campaigns._CANCEL, (campaign, row_version(app, campaign)))
        assert image_count(app, campaign) == 0
    assert campaign_status(owner, campaign) == "CANCELLED"
    assert image_count(owner, campaign) == 0


def test_rolled_back_cancel_keeps_the_image(owner, app, user):
    """حذفٌ خارج معاملة الإلغاء يُفقد صورة حملةٍ لم تُلغَ حين تتراجع المعاملة."""
    campaign = new_campaign(app, user)
    before = stored_digest(owner, campaign)
    with app.transaction():
        apply_one(app, campaigns._CANCEL, (campaign, row_version(app, campaign)))
        assert image_count(app, campaign) == 0
        raise psycopg.Rollback
    assert campaign_status(owner, campaign) == "DRAFT"
    assert stored_digest(owner, campaign) == before


def test_app_cannot_delete_images(owner, app, user):
    """حذفٌ بيد الخادم يفصل الصورة عن حالة حملتها: مسودةٌ بلا صورة، أو حذفٌ لصورة غيره."""
    campaign = new_campaign(app, user)
    for statement, params in (
        ("DELETE FROM campaign_images WHERE campaign_id = %s", (campaign,)),
        ("DELETE FROM campaign_images", ()),
        ("TRUNCATE campaign_images", ()),
    ):
        with rejected(errors.InsufficientPrivilege):
            with app.cursor() as cursor:
                cursor.execute(statement, params)
    assert image_count(owner, campaign) == 1
