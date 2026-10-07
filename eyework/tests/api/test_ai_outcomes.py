"""
نتائج الكاتب عبر الواجهة البرمجية
=================================
كل استدعاءٍ للنموذج محاولةٌ تُفتح في القاعدة قبله وتُغلق بنتيجتها بعده — نجح،
أو رفض، أو أخطأ، أو رفع الكاتب استثناءً لم يتوقّعه أحد. محاولةٌ تبقى مفتوحة
تحجز صاحبها عن غيرها دقائق بلا سبب يراه، فلا تُترك واحدةٌ مفتوحة.

ولكل نتيجةٍ جوابٌ ثابت: حالةٌ تفهمها الواجهة، ورسالةٌ عربية تقول ما يفعله
المستخدم بعدها، و`Retry-After` حين يكون للانتظار معنى. والصورة التي لا تصلح
ليست خطأً: الحملة تبقى مسودةً تنتظر صورةً أخرى.

وما يُعرض على المستخدم من رصيده اليومي هو ما تفرضه القاعدة نفسها: ما لم يصل
المزوّد أو ردّه مزدحماً لا يُحسب عليه، وما ربما فُوتر يُحسب. وسقف المعدّل
(ستّ محاولاتٍ في عشر دقائق) يرفض السابعة قبل أن يُستدعى النموذج.

وأخيراً: النموذج يرى ما يراه المستخدم بالضبط — الصورة المخزّنة نفسها بايتاً
ببايت — ولا شيء عن صاحب الطلب.
"""

from __future__ import annotations

import dataclasses

import pytest

from eyework.copy_rules import EditPreset
from eyework.copywriter import CopyOutcome
from eyework.prompt import UNUSABLE_REASONS, CopyRequest, PreviousCopy
from eyework.tests.api.conftest import (
    JPEG,
    SELLER,
    attempts,
    current,
    edit,
    expect,
    generate,
    noise_jpeg,
    open_attempts,
    path,
    signed_in,
    upload,
)
from eyework.tests.fakes import ok

DAILY = 40
NOTE = "اذكر أن الحزام قابل للتعديل"

#: (النتيجة، الحالة، الرمز) لكل محاولةٍ لم تُكتب فيها نسخة.
FAILURES = [
    ("REFUSED", 422, "AI_REFUSED"),
    ("OUTPUT_INVALID", 502, "AI_OUTPUT_INVALID"),
    ("UPSTREAM_BUSY", 503, "AI_BUSY"),
    ("UPSTREAM_TIMEOUT", 504, "AI_TIMEOUT"),
    ("UPSTREAM_ERROR", 503, "AI_UNAVAILABLE"),
    ("UPSTREAM_UNREACHABLE", 503, "AI_UNAVAILABLE"),
]

UNUSABLE_MESSAGES = {
    "NO_PRODUCT": "لا يظهر منتجٌ واضح في الصورة. اختر صورةً أخرى.",
    "UNCLEAR_PHOTO": "الصورة غير واضحة. اختر صورةً أوضح للمنتج.",
    "MULTIPLE_PRODUCTS": "في الصورة أكثر من منتج. اختر صورةً لمنتجٍ واحد.",
    "NOT_ALLOWED": "لا يمكن كتابة إعلانٍ لهذا المنتج.",
}


def _copy(client, view: dict):
    return client.post(path(view, "/copy"), json={"expected_row_version": view["row_version"]})


def _left(client) -> int:
    return expect(client.get("/api/me"))["generations_left"]


class _Exploding:
    """كاتبٌ يرفع ما لا يرفعه الكاتب الحقيقي في مساره المعتاد."""

    def write(self, request: CopyRequest) -> CopyOutcome:
        raise RuntimeError("connection reset while reading the model's reply")


# ── الجواب لكل نتيجة ───────────────────────────────────────────────────
def test_a_refusal_is_answered_with_its_arabic_message(seller, writer):
    """رفضٌ بلا سببٍ مفهوم يجعل المستخدم يعيد المحاولة بالصورة نفسها بلا نهاية."""
    view = upload(seller)
    writer.queue(CopyOutcome("REFUSED"))
    response = _copy(seller, view)
    assert response.status_code == 422
    assert response.json() == {
        "code": "AI_REFUSED",
        "detail": "لا يستطيع المساعد الكتابة عن هذه الصورة. جرّب صورةً أخرى للمنتج.",
    }


@pytest.mark.parametrize(("outcome", "status", "code"), FAILURES, ids=[f[0] for f in FAILURES])
def test_a_failed_attempt_is_answered_closed_and_does_not_block_the_next(seller, writer, owner,
                                                                         outcome, status, code):
    """فشلٌ يترك المحاولة مفتوحة يحجز صاحبه دقائق؛ وفشلٌ يغيّر الحملة يضيّع مسودته."""
    view = upload(seller)
    writer.queue(CopyOutcome(outcome))

    response = _copy(seller, view)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert attempts(owner) == [(outcome, True)]
    assert current(seller, view) == view

    assert generate(seller, view)["status"] == "COPY_PROPOSED"
    assert open_attempts(owner) == 0


@pytest.mark.parametrize(("given", "header"), [(12, "12"), (None, "30")])
def test_busy_tells_the_client_when_to_retry(seller, writer, given, header):
    """ازدحامٌ بلا موعدٍ يدفع الواجهة إلى إعادةٍ فورية تزيد الازدحام."""
    view = upload(seller)
    writer.queue(CopyOutcome("UPSTREAM_BUSY", retry_after_seconds=given))
    response = _copy(seller, view)
    assert response.status_code == 503
    assert response.headers["retry-after"] == header


@pytest.mark.parametrize("reason", UNUSABLE_REASONS)
def test_an_unusable_photo_keeps_the_draft_open_for_another_photo(seller, writer, owner, reason):
    """صورةٌ لا تصلح ليست خطأً: حملةٌ تُغلق بها تُضيّع على صاحبها خطواته."""
    view = upload(seller)
    writer.queue(CopyOutcome("UNUSABLE_PHOTO", reason=reason))

    body = expect(_copy(seller, view))
    assert body["result"] == "UNUSABLE_PHOTO"
    assert body["reason"] == reason
    assert body["message"] == UNUSABLE_MESSAGES[reason]
    assert body["campaign"]["status"] == "DRAFT"
    assert body["campaign"]["copy"] is None
    assert attempts(owner) == [("UNUSABLE_PHOTO", True)]

    replaced = expect(seller.put(path(view, "/image"), params={"expected_row_version": body["campaign"]["row_version"]},
                                 content=noise_jpeg(), headers=JPEG))
    assert replaced["status"] == "DRAFT"
    assert replaced["image"]["tag"] != view["image"]["tag"]


@pytest.mark.parametrize("outcome", [
    pytest.param(ok(), id="OK"),
    pytest.param(CopyOutcome("UNUSABLE_PHOTO", reason="NO_PRODUCT"), id="UNUSABLE_PHOTO"),
    *(pytest.param(CopyOutcome(name), id=name) for name, _, _ in FAILURES),
])
def test_no_outcome_leaves_an_attempt_open(seller, writer, owner, outcome):
    """محاولةٌ تبقى مفتوحة تمنع صاحبها من غيرها حتى تنقضي مهلتها."""
    view = upload(seller)
    writer.queue(outcome)
    _copy(seller, view)
    assert open_attempts(owner) == 0
    assert attempts(owner) == [(outcome.outcome, True)]


def test_a_writer_that_raises_still_closes_the_attempt(owner, server, browser, writer):
    """استثناءٌ من الكاتب يترك المحاولة مفتوحة فيُرفض كل توليدٍ بعده بـ«يكتب الآن»."""
    client = signed_in(owner, browser, SELLER, raise_server_exceptions=False)
    view = upload(client)

    server.state.copywriter = _Exploding()
    response = _copy(client, view)
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL", "detail": "حدث خطأ. حاول مرة أخرى."}
    assert "connection reset" not in response.text
    assert attempts(owner) == [("UPSTREAM_ERROR", True)]

    server.state.copywriter = writer
    assert generate(client, view)["status"] == "COPY_PROPOSED"


def test_the_seventh_generation_within_ten_minutes_is_refused_before_the_model(seller, writer, owner):
    """بلا سقفٍ للمعدّل تحرق حلقةٌ في الواجهة رصيد اليوم كلّه في دقيقة."""
    view = upload(seller)
    for _ in range(6):
        writer.queue(CopyOutcome("OUTPUT_INVALID"))
        assert _copy(seller, view).status_code == 502

    refused = _copy(seller, view)
    assert refused.status_code == 429
    assert refused.json() == {"code": "AI_RATE", "detail": "طلباتٌ كثيرة خلال وقتٍ قصير. حاول بعد دقائق."}
    assert refused.headers["retry-after"] == "600"
    assert len(writer.requests) == 6
    assert len(attempts(owner)) == 6


# ── الرصيد اليومي ──────────────────────────────────────────────────────
@pytest.mark.parametrize(("outcome", "counted"), [
    ("UPSTREAM_BUSY", False),
    ("UPSTREAM_UNREACHABLE", False),
    ("UPSTREAM_ERROR", False),
    ("REFUSED", True),
    ("OUTPUT_INVALID", True),
])
def test_generations_left_counts_only_what_may_have_been_billed(seller, writer, owner, outcome, counted):
    """
    انقطاع الخدمة لا يستهلك رصيد صاحبها؛ ورصيدٌ معروض يخالف ما تفرضه القاعدة
    يُري المستخدم «نفد» وهو لم ينفد، أو العكس.
    """
    view = upload(seller)
    assert _left(seller) == DAILY
    writer.queue(CopyOutcome(outcome))
    _copy(seller, view)

    assert _left(seller) == DAILY - int(counted)
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FILTER (WHERE ew_is_billable(outcome)) FROM generation_attempts")
        assert _left(seller) == DAILY - cursor.fetchone()[0]


# ── ما يراه النموذج ────────────────────────────────────────────────────
def test_the_model_sees_the_stored_image_and_nothing_about_the_user(owner, seller, writer):
    """
    صورةٌ أصلية تصل النموذج تحمل موقع التقاطها؛ ومعرّفٌ يصله يربط مستخدمي
    التطبيق بطلباتهم لدى طرفٍ ثالث.
    """
    view = upload(seller, noise_jpeg(gps=True))
    stored = seller.get(path(view, "/image")).content
    view = generate(seller, view)
    edit(seller, view, ("SIMPLER",), NOTE)

    assert len(writer.requests) == 2
    for request in writer.requests:
        assert type(request) is CopyRequest
        assert {field.name for field in dataclasses.fields(request)} == {
            "jpeg", "previous", "presets", "edit_note", "seller_note"}
        assert request.jpeg == stored
        assert request.seller_note is None

    initial, edited = writer.requests
    assert (initial.previous, initial.presets, initial.edit_note) == (None, (), None)
    assert edited.previous == PreviousCopy(view["copy"]["title"], view["copy"]["description"])
    assert edited.presets == (EditPreset.SIMPLER,)
    assert edited.edit_note == NOTE

    with owner.cursor() as cursor:
        cursor.execute("SELECT id::text FROM users")
        (user_id,) = cursor.fetchone()
    sent_text = repr([(r.previous, r.presets, r.edit_note, r.seller_note) for r in writer.requests])
    for identity in (user_id, view["id"], SELLER):
        assert identity not in sent_text
