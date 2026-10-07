"""
مسار الحملة عبر الواجهة البرمجية
================================
من صورةٍ بموقع التقاطها إلى حملةٍ جاهزة ثم مسحوبة، بالطلبات نفسها التي
ترسلها الواجهة. ما يثبته هذا الملف:

  • الصورة المخزّنة بلا EXIF — موقع الالتقاط قد يكون بيت صاحبها — ولا تُخبّأ
    في متصفّحٍ ولا وسيط.
  • كل كتابةٍ مشروطةٌ برقم الصفّ الذي رآه صاحبها: ضغطةٌ مكرّرة، أو تبويبٌ
    قديم، تُرفض بـ409 ولا تغيّر شيئاً — في كل مسارٍ يكتب، بلا استثناء.
  • التأكيد يعتمد ما عُرض بالضبط: النسخة والمبلغ والمدّة. أيّ اختلاف ⇒ 409.
  • حملة غيرك غير موجودة (404 لا 403) في كل مسار: لا يُكشف أنها موجودة.
  • ما لا يُقبل يُرفض بـ422 قبل أن يمسّ شيئاً، ولا يُصحَّح بصمت.

المال هنا قرارٌ لا يُرجع عنه بعد التأكيد؛ ولذلك كل رفضٍ يُتبع بفحص أن الحملة
لم تتغيّر، وكل اختبار رفضٍ لقيمةٍ قديمة يُتبع بالطلب نفسه بالقيمة الحالية
فينجح — فلا يمرّ الاختبار لسببٍ غير الذي يسمّيه.
"""

from __future__ import annotations

import hashlib

import pytest

from eyework.copy_rules import EditPreset
from eyework.prompt import PreviousCopy
from eyework.tests.api.conftest import (
    JPEG,
    approve,
    attempts,
    current,
    edit,
    expect,
    generate,
    noise_jpeg,
    open_attempts,
    path,
    set_budget,
    set_days,
    upload,
)
from eyework.tests.fakes import DESCRIPTION, ok

NOT_FOUND = {"code": "NOT_FOUND", "detail": "الحملة غير موجودة."}

SHORTER_TITLE = "حقيبة جلدية بنية"
SHORTER_DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط، تتّسع للأغراض اليومية ولها حزام كتف."
NEW_TITLE = "حقيبة يد جلدية بلون بني دافئ"
OTHER_DESCRIPTION = "حقيبة كتف واسعة من الجلد الطبيعي، بجيبٍ داخلي وسحّاب متين، تناسب العمل والسفر."
NOTE = "اذكر أن الحزام قابل للتعديل"

MUTATIONS = ["copy", "edit", "restore", "approve", "unapprove", "budget", "days", "confirm", "cancel", "image"]


def _restore(client, view: dict, target: str) -> dict:
    return expect(client.post(path(view, "/copy/restore"), json={
        "expected_row_version": view["row_version"],
        "expected_version_id": view["copy"]["version_id"],
        "target": target,
    }))


def _prepare(client, name: str) -> dict:
    """الحملة في الحالة التي ينجح فيها `name` بقيمٍ صحيحة."""
    view = upload(client)
    if name in ("copy", "image"):
        return view
    view = generate(client, view)
    if name == "restore":
        view = edit(client, view)
    if name in ("edit", "restore", "approve", "cancel"):
        return view
    view = approve(client, view)
    if name == "confirm":
        view = set_days(client, set_budget(client, view, 500), 7)
    return view


def _send(client, name: str, view: dict, row_version: int):
    """الطلب الذي ترسله الواجهة لـ`name`، برقم الصفّ المعطى وبقيمٍ صحيحة غيره."""
    version_id = view["copy"]["version_id"] if view["copy"] else None
    rv = {"expected_row_version": row_version}
    if name == "copy":
        return client.post(path(view, "/copy"), json=rv)
    if name == "edit":
        return client.post(path(view, "/copy/edit"),
                           json={**rv, "expected_version_id": version_id, "presets": ["SHORTER"]})
    if name == "restore":
        return client.post(path(view, "/copy/restore"),
                           json={**rv, "expected_version_id": version_id, "target": "previous"})
    if name == "approve":
        return client.post(path(view, "/copy/approve"), json={**rv, "version_id": version_id})
    if name == "unapprove":
        return client.post(path(view, "/copy/unapprove"), json=rv)
    if name == "budget":
        return client.put(path(view, "/budget"), json={**rv, "budget_sar": 1000})
    if name == "days":
        return client.put(path(view, "/days"), json={**rv, "days": 3})
    if name == "confirm":
        return client.post(path(view, "/confirm"),
                           json={**rv, "version_id": version_id, "budget_sar": 500, "days": 7})
    if name == "cancel":
        return client.post(path(view, "/cancel"), json=rv)
    if name == "image":
        return client.put(path(view, "/image"), params=rv, content=noise_jpeg(), headers=JPEG)
    raise AssertionError(name)


# ── المسار كاملاً ──────────────────────────────────────────────────────
def test_a_campaign_from_photo_to_ready_and_withdrawn(seller, writer):
    """كل خطوةٍ كما تراها الواجهة، من الرفع إلى السحب، بلا اختصار."""
    original = noise_jpeg(gps=True)
    assert b"Exif" in original

    # الرفع: الصورة المخزّنة أُعيد ترميزها بلا موقع، ولا تُخبّأ.
    view = upload(seller, original)
    assert (view["status"], view["row_version"], view["copy"]) == ("DRAFT", 1, None)
    stored = seller.get(path(view, "/image"))
    assert stored.status_code == 200
    assert stored.headers["content-type"] == "image/jpeg"
    assert stored.headers["cache-control"] == "private, no-store"
    assert stored.content.startswith(b"\xff\xd8\xff")
    assert b"Exif" not in stored.content
    assert hashlib.sha256(stored.content).hexdigest()[:16] == view["image"]["tag"]

    # النسخة الأولى.
    view = generate(seller, view)
    first = view["copy"]
    assert view["status"] == "COPY_PROPOSED"
    assert first["version"] == 1
    assert not first["can_restore_previous"] and not first["can_restore_newest"]

    # تعديلٌ بخيارٍ وملاحظة: النموذج يرى النسخة المعروضة وطلبَ صاحبها.
    writer.queue(ok(SHORTER_TITLE, SHORTER_DESCRIPTION))
    view = edit(seller, view, ("SHORTER",), NOTE)
    second = view["copy"]
    assert (second["version"], second["title"], second["description"]) == (2, SHORTER_TITLE, SHORTER_DESCRIPTION)
    sent = writer.requests[-1]
    assert sent.presets == (EditPreset.SHORTER,)
    assert sent.edit_note == NOTE
    assert sent.previous == PreviousCopy(first["title"], first["description"])

    # «عنوانٌ آخر فقط»: الوصف يبقى بايتاً ببايت.
    writer.queue(ok(NEW_TITLE, SHORTER_DESCRIPTION))
    view = edit(seller, view, ("NEW_TITLE",))
    third = view["copy"]
    assert third["version"] == 3
    assert third["title"] == NEW_TITLE
    assert third["description"].encode("utf-8") == second["description"].encode("utf-8")

    # الاستعادة ذهاباً وإياباً، بلا استدعاءٍ للنموذج.
    calls = len(writer.requests)
    view = _restore(seller, view, "previous")
    assert view["copy"]["version_id"] == second["version_id"]
    assert view["copy"]["can_restore_newest"]
    view = _restore(seller, view, "newest")
    assert view["copy"]["version_id"] == third["version_id"]
    assert len(writer.requests) == calls

    # الموافقة تسجّل النسخة المعروضة نفسها.
    view = approve(seller, view)
    assert view["status"] == "COPY_APPROVED"
    assert view["approved_version_id"] == third["version_id"]

    # المبلغ من الخيارات الجاهزة، والمدّة.
    choices = seller.get("/api/choices").json()
    preset = 500
    assert preset in choices["budget"]["presets"]
    view = set_budget(seller, view, preset)
    view = set_days(seller, view, 7)
    assert view["budget"]["sar"] == preset
    assert view["days"]["n"] == 7

    # التراجع عن الموافقة لا يمسّ المال.
    view = expect(seller.post(path(view, "/copy/unapprove"), json={"expected_row_version": view["row_version"]}))
    assert view["status"] == "COPY_PROPOSED"
    assert view["approved_version_id"] is None
    assert (view["budget"]["sar"], view["days"]["n"]) == (preset, 7)

    # موافقةٌ ثانية، ثم خطوةٌ واحدة من الخيار الجاهز إلى جاره في المجال.
    view = approve(seller, view)
    values = [value["sar"] for value in choices["budget"]["values"]]
    stepped = values[values.index(preset) + 1]
    view = set_budget(seller, view, stepped)
    view = set_days(seller, view, 10)
    assert view["budget"]["sar"] == stepped == 550
    assert view["daily"] == {"amount": "55.00", "exact": True}

    # التأكيد بما عُرض.
    view = expect(seller.post(path(view, "/confirm"), json={
        "expected_row_version": view["row_version"], "version_id": third["version_id"],
        "budget_sar": stepped, "days": 10}))
    assert view["status"] == "READY"
    assert view["ready_at"] is not None
    assert view["approved_version_id"] == third["version_id"]

    # السحب: الإلغاء نهائي، والصورة تُحذف معه.
    view = expect(seller.post(path(view, "/cancel"), json={"expected_row_version": view["row_version"]}))
    assert view["status"] == "CANCELLED"
    assert view["image"] is None
    gone = seller.get(path(view, "/image"))
    assert gone.status_code == 404
    assert gone.json() == NOT_FOUND
    assert view["id"] not in {item["id"] for item in seller.get("/api/campaigns").json()["items"]}


def test_a_new_title_never_rewrites_the_description(seller, writer, owner):
    """كاتبٌ يتجاهل «عنواناً آخر فقط» لا يغيّر وصفاً وافق عليه صاحبه ضمناً."""
    view = generate(seller, upload(seller))
    writer.queue(ok(NEW_TITLE, OTHER_DESCRIPTION))
    response = seller.post(path(view, "/copy/edit"), json={
        "expected_row_version": view["row_version"], "expected_version_id": view["copy"]["version_id"],
        "presets": ["NEW_TITLE"]})
    assert response.status_code == 409
    after = current(seller, view)
    assert after["copy"] == view["copy"]
    assert after["copy"]["description"] == DESCRIPTION
    assert attempts(owner)[-1] == ("DISCARDED", True)


def test_pressing_approve_twice_applies_once(seller):
    """الضغطة المكرّرة بالعين تُرفض بدل أن تُطبَّق مرتين."""
    view = generate(seller, upload(seller))
    body = {"expected_row_version": view["row_version"], "version_id": view["copy"]["version_id"]}
    assert seller.post(path(view, "/copy/approve"), json=body).status_code == 200
    again = seller.post(path(view, "/copy/approve"), json=body)
    assert again.status_code == 409
    assert again.json()["code"] == "STALE"


# ── رقم الصفّ ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", MUTATIONS)
def test_every_mutation_refuses_a_row_version_other_than_the_current(seller, writer, owner, name):
    """
    مسارٌ واحد يكتب دون شرط رقم الصفّ يطبّق ما في تبويبٍ قديم فوق ما رآه
    صاحبه بعده. ومسودةٌ رقمها 1 دائماً، فيُرسل لها رقمٌ آخر غير الحالي.
    """
    view = _prepare(seller, name)
    before = current(seller, view)
    calls = len(writer.requests)
    stale = view["row_version"] - 1 if view["row_version"] > 1 else view["row_version"] + 1

    refused = _send(seller, name, view, stale)
    assert refused.status_code == 409, refused.text
    assert current(seller, view) == before
    assert len(writer.requests) == calls
    assert open_attempts(owner) == 0

    # الطلب نفسه برقم الصفّ الحالي ينجح: لم يُرفض لسببٍ آخر.
    assert _send(seller, name, view, view["row_version"]).status_code == 200


@pytest.mark.parametrize("change", ["version_id", "budget_sar", "days"])
def test_confirm_refuses_anything_but_what_was_shown(seller, change):
    """تأكيدٌ بمبلغٍ أو مدّةٍ أو نسخةٍ غير المعروضة يعتمد ما لم يره صاحبه."""
    view = generate(seller, upload(seller))
    older = view["copy"]["version_id"]
    view = set_days(seller, set_budget(seller, approve(seller, edit(seller, view)), 500), 7)
    shown = {"expected_row_version": view["row_version"], "version_id": view["copy"]["version_id"],
             "budget_sar": 500, "days": 7}
    other = {"version_id": older, "budget_sar": 550, "days": 8}[change]
    before = current(seller, view)

    refused = seller.post(path(view, "/confirm"), json={**shown, change: other})
    assert refused.status_code == 409
    assert current(seller, view) == before

    assert expect(seller.post(path(view, "/confirm"), json=shown))["status"] == "READY"


# ── حملة غيرك ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["read", "read_image", *MUTATIONS])
def test_another_users_campaign_does_not_exist_on_any_route(seller, intruder, writer, name):
    """403 يقول «موجودةٌ وليست لك»؛ ومسارٌ واحد ينسى العزل يكشف حملات غيرك."""
    view = _prepare(seller, name if name in MUTATIONS else "copy")
    before = current(seller, view)
    image = seller.get(path(view, "/image")).content
    calls = len(writer.requests)

    if name == "read":
        response = intruder.get(path(view))
    elif name == "read_image":
        response = intruder.get(path(view, "/image"))
    else:
        # برقم الصفّ الصحيح: معرفة الرقم لا تفتح حملة غيرك.
        response = _send(intruder, name, view, view["row_version"])

    assert response.status_code == 404, response.text
    assert response.json() == NOT_FOUND
    assert current(seller, view) == before
    assert seller.get(path(view, "/image")).content == image
    assert len(writer.requests) == calls
    assert intruder.get("/api/campaigns").json()["items"] == []


# ── ما لا يُقبل ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("budget", [1100, 75])
def test_a_budget_outside_the_domain_is_refused(seller, budget):
    """مبلغٌ لا تعرضه الواجهة لم يختره أحد؛ لا يُقرَّب إلى أقرب قيمة بصمت."""
    view = approve(seller, generate(seller, upload(seller)))
    response = seller.put(path(view, "/budget"), json={"expected_row_version": view["row_version"],
                                                       "budget_sar": budget})
    assert response.status_code == 422
    assert response.json()["code"] == "BUDGET_RANGE"
    assert current(seller, view)["budget"] is None


@pytest.mark.parametrize("body", [
    pytest.param({"budget_sar": "500"}, id="budget-as-string"),
    pytest.param({"budget_sar": 500.0}, id="budget-as-float"),
    pytest.param({"budget_sar": 500, "approved": True}, id="unknown-field"),
])
def test_a_loosely_typed_or_unknown_field_is_refused(seller, body):
    """«"500"» نصّاً ليست ميزانية، وحقلٌ لا نعرفه لا يُتجاهل بصمت."""
    view = approve(seller, generate(seller, upload(seller)))
    response = seller.put(path(view, "/budget"), json={"expected_row_version": view["row_version"], **body})
    assert response.status_code == 422
    assert response.json() == {"code": "INVALID", "detail": "قيمةٌ غير صالحة في الطلب."}
    assert current(seller, view)["budget"] is None


def test_opposite_presets_are_refused_before_the_model_is_called(seller, writer, owner):
    """«أكثر رسمية» و«أكثر حيوية» معاً طلبٌ يدفع ثمنه صاحبه ولا جواب صحيحاً له."""
    view = generate(seller, upload(seller))
    calls, tried = len(writer.requests), len(attempts(owner))
    response = seller.post(path(view, "/copy/edit"), json={
        "expected_row_version": view["row_version"], "expected_version_id": view["copy"]["version_id"],
        "presets": ["MORE_FORMAL", "MORE_LIVELY"]})
    assert response.status_code == 422
    assert response.json()["code"] == "EDIT_CONFLICT"
    assert len(writer.requests) == calls
    assert len(attempts(owner)) == tried
    assert current(seller, view) == view


def test_the_image_cannot_be_replaced_once_copy_describes_it(seller):
    """صورةٌ تتغيّر تحت نصٍّ كُتب عنها تجعل الإعلان يصف منتجاً غير المعروض."""
    view = generate(seller, upload(seller))
    image = seller.get(path(view, "/image")).content
    response = seller.put(path(view, "/image"), params={"expected_row_version": view["row_version"]},
                          content=noise_jpeg(), headers=JPEG)
    assert response.status_code == 409
    assert seller.get(path(view, "/image")).content == image
    assert current(seller, view) == view
