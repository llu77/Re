"""
لوحة الممارس — من المتصفّح إلى القاعدة
=======================================
اللوحة (`console/`) تُبنى بـVite وتُخدم من التطبيق نفسه تحت `/console`. هذه
الاختبارات تشغّل التطبيق الحقيقي وتقود اللوحة في Chromium، ثم تقرأ النتيجة من
القاعدة: قرارٌ ظهر نجاحه على الشاشة ولم يُكتب لا يُعدّ قراراً.

وتُقاس اللوحة بمقاييس البوابة نفسها (تباين، تداخل، مساحة لمس ≥ 44، لا فيض
أفقي) — المقاييس مستوردة لا منسوخة، فلا تختلف المسطرة بين الواجهتين.

بلا بناءٍ (`npm ci && npm run build` في console/) أو بلا Chromium تُتجاوز هذه
الاختبارات بسببٍ صريح — وفي CI يُفشلها الغياب (`tests/browsers.py`). ترويسات
الخادم لا تحتاج متصفّحاً، فتُختبر في `test_console_headers.py`.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

from core import escalation, identity, proposals
from core.adl import gate as adl_gate
from core.types import Actor
from tests import browsers
from tests.conftest import cite_evidence_as, requires_db

pytestmark = requires_db

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "console" / "dist" / "index.html"

PRACTITIONER_EMAIL = "practitioner.A@example.test"
SECRET = "كلمة-مرور-اللوحة"
SESSION_KEY = "symbol.practitioner.session"

CHROMIUM = browsers.chromium_executable()
if not DIST.exists():  # pragma: no cover - يعتمد على البناء
    browsers.unavailable("لوحة الممارس لم تُبنَ: npm ci && npm run build في console/")

import playwright.sync_api as playwright_api  # noqa: E402 — بعد شرط التجاوز

from tests.test_portal_accessibility import (  # noqa: E402 — بعد شرط التجاوز
    CONTRAST_SCRIPT,
    HORIZONTAL_OVERFLOW_SCRIPT,
    OVERLAP_SCRIPT,
    TOUCH_TARGET_SCRIPT,
)

DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}

DOCUMENTATION_TEXT = "ملخّص الجلسة الثالثة: تحسّن مدى حركة الكتف إلى 120 درجة."
FIRST_STEP_TITLE = "أدخِل الذراع المصابة في الكمّ"
RED_FLAG_TEXT = "ألم شديد مفاجئ في الكتف منذ الصباح مع تنميل في الأصابع."
SECOND_FLAG_TEXT = "دوخة عند الوقوف وسقطتُ مرةً في الحمّام."


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    process = subprocess.Popen(
        ["python3", "-m", "uvicorn", "api.app:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env={**os.environ},
    )
    base = f"http://127.0.0.1:{port}"
    try:
        subprocess.run(
            ["curl", "-sf", "--retry", "40", "--retry-delay", "1",
             "--retry-connrefused", "--retry-all-errors", "-o", "/dev/null", f"{base}/health"],
            check=True, timeout=90,
        )
        yield base
    finally:
        process.terminate()
        process.wait(timeout=20)


class Clinic:
    """ممارسٌ بكلمة مرور، ومقترحان في الطابور (أحدهما علامة حمراء)، وبلاغ مفتوح."""

    def __init__(self, practitioner: Actor, plan, note, flag):
        self.practitioner = practitioner
        self.plan = plan
        self.note = note
        self.flag = flag


@pytest.fixture
def clinic(owner, seed, server) -> Clinic:
    practitioner = Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)
    with owner.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (identity.hash_password(SECRET), seed.practitioner_a),
        )
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'PATIENT', 'console.patient@example.test', 'x') RETURNING id",
            (seed.tenant_a,),
        )
        patient_user = cursor.fetchone()[0]
        cursor.execute("UPDATE patients SET user_id = %s WHERE id = %s", (patient_user, seed.patient_a))

    # خطة لبس حقيقية كالتي تدقّقها البوابة: تمرّ ببوابات الدليل والتحقّق كلها.
    plan = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="PLAN", priority=1, is_red_flag=True,
        payload={
            "module": "DRESSING",
            "steps": [
                {"action": "DON", "side": "AFFECTED", "garment": "القميص",
                 "title": FIRST_STEP_TITLE,
                 "text": "اجلس على طرف الكرسي، وأدخِل الذراع المصابة أولاً والكمّ واسع."},
                {"action": "DON", "side": "SOUND", "garment": "القميص",
                 "title": "ثم الذراع السليمة",
                 "text": "مرّر القميص خلف ظهرك، ثم أدخِل الذراع السليمة."},
            ],
        },
        affected_side="RIGHT",
    )
    cite_evidence_as(practitioner, plan.id)
    adl_gate.verify_proposal(practitioner, plan.id)
    proposals.submit(plan.id, practitioner)

    note = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="DOCUMENTATION", priority=5,
        payload={"summary": DOCUMENTATION_TEXT},
    )
    cite_evidence_as(practitioner, note.id)
    proposals.submit(note.id, practitioner)

    flag, _ = escalation.report(
        tenant_id=seed.tenant_a, patient_id=seed.patient_a, body=RED_FLAG_TEXT,
        reported_by=patient_user,
    )
    return Clinic(practitioner, plan, note, flag)


class Browser:
    """متصفّح لكل اختبار، يجمع أخطاء الصفحة ومخالفات سياسة المحتوى."""

    def __init__(self, server: str):
        self.server = server
        self.problems: list[str] = []
        self._pw = playwright_api.sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])

    def open(self, *, viewport=DESKTOP, token: str | None = None, path: str = "/console/"):
        context = self._browser.new_context(viewport=viewport, locale="ar-SA")
        if token:
            session = json.dumps({"token": token, "role": "PRACTITIONER"})
            context.add_init_script(
                f"sessionStorage.setItem({SESSION_KEY!r}, {session!r});"
                f"sessionStorage.setItem('symbol.practitioner.email', {PRACTITIONER_EMAIL!r});"
            )
        page = context.new_page()
        page.on("pageerror", lambda error: self.problems.append(f"pageerror: {error}"))
        page.on("console", lambda message: self.problems.append(f"console: {message.text}")
                if message.type == "error" else None)
        page.goto(f"{self.server}{path}", wait_until="networkidle", timeout=60000)
        return page

    def close(self):
        self._browser.close()
        self._pw.stop()


@pytest.fixture
def browser(server):
    opened = Browser(server)
    yield opened
    opened.close()


def _token() -> str:
    token, _ = identity.authenticate(PRACTITIONER_EMAIL, SECRET, "PRACTITIONER")
    return token


def _status(owner, proposal_id) -> tuple[str, str | None]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT status, rejection_reason FROM proposals WHERE id = %s", (proposal_id,))
        return cursor.fetchone()


def _nav(page):
    return page.get_by_role("navigation", name="أقسام اللوحة")


# ── الدخول والطابور ─────────────────────────────────────────────────────


def test_signing_in_shows_the_queue_in_server_order(browser, clinic):
    page = browser.open()
    page.get_by_label("البريد الإلكتروني").fill(PRACTITIONER_EMAIL)
    page.get_by_label("كلمة المرور").fill(SECRET)
    page.get_by_role("button", name="تسجيل الدخول").click()

    queue = page.get_by_role("list", name="المقترحات بانتظار المراجعة")
    queue.wait_for()
    items = queue.get_by_role("listitem")
    assert items.count() == 2
    # العلامة الحمراء أولاً، كما يرتّبها الخادم.
    assert "علامة حمراء" in items.nth(0).inner_text()
    assert "خطة علاج" in items.nth(0).inner_text()
    assert "توثيق" in items.nth(1).inner_text()

    nav = _nav(page)
    assert nav.get_by_role("link", name="طابور المراجعة، 2").get_attribute("aria-current") == "page"
    assert nav.get_by_role("link", name="البلاغات العاجلة، 1").is_visible()
    assert page.evaluate(f"() => sessionStorage.getItem({SESSION_KEY!r})")
    assert not browser.problems, browser.problems


def test_a_wrong_password_stores_nothing(browser, clinic):
    page = browser.open()
    page.get_by_label("البريد الإلكتروني").fill(PRACTITIONER_EMAIL)
    page.get_by_label("كلمة المرور").fill("خطأ")
    page.get_by_role("button", name="تسجيل الدخول").click()
    assert "بيانات اعتماد غير صحيحة" in page.get_by_role("alert").inner_text()
    assert page.evaluate(f"() => sessionStorage.getItem({SESSION_KEY!r})") is None


def test_an_expired_session_returns_to_the_login_screen(browser, clinic):
    page = browser.open(token="not-a-real-token")
    page.get_by_role("button", name="تسجيل الدخول").wait_for()
    assert page.evaluate(f"() => sessionStorage.getItem({SESSION_KEY!r})") is None


# ── القرار ──────────────────────────────────────────────────────────────


def test_approving_takes_two_steps_and_reaches_the_database(browser, clinic, owner):
    page = browser.open(token=_token(), path=f"/console/#/queue/{clinic.plan.id}")
    page.get_by_text(FIRST_STEP_TITLE).wait_for()
    citations = page.get_by_role("complementary", name="الأدلّة (1)")
    assert citations.get_by_role("link").count() == 1

    page.get_by_role("button", name="اعتماد", exact=True).click()
    assert _status(owner, clinic.plan.id)[0] == "PENDING"
    page.get_by_role("button", name="تأكيد الاعتماد").click()

    page.get_by_role("status").get_by_text("اعتُمد المقترح.").wait_for()
    assert _status(owner, clinic.plan.id)[0] == "APPROVED"
    assert page.evaluate("() => location.hash") == "#/queue"
    page.get_by_role("link", name="طابور المراجعة، 1").wait_for()
    assert not browser.problems, browser.problems


def test_rejecting_needs_a_reason_and_stores_it(browser, clinic, owner):
    page = browser.open(token=_token(), path=f"/console/#/queue/{clinic.note.id}")
    page.get_by_text(DOCUMENTATION_TEXT).wait_for()
    page.get_by_role("button", name="رفض", exact=True).click()
    confirm = page.get_by_role("button", name="تأكيد الرفض")
    assert confirm.is_disabled()

    page.get_by_label("سبب الرفض (إلزامي)").fill("القياس غير موثّق بأداة معيارية.")
    confirm.click()
    page.get_by_role("status").get_by_text("رُفض المقترح وحُفظ السبب.").wait_for()
    assert _status(owner, clinic.note.id) == ("REJECTED", "القياس غير موثّق بأداة معيارية.")


def test_a_decision_already_taken_elsewhere_is_reported_not_repeated(browser, clinic, owner):
    page = browser.open(token=_token(), path=f"/console/#/queue/{clinic.note.id}")
    page.get_by_text(DOCUMENTATION_TEXT).wait_for()
    proposals.approve(clinic.note.id, clinic.practitioner)   # ممارسٌ آخر سبق
    page.get_by_role("button", name="اعتماد", exact=True).click()
    page.get_by_role("button", name="تأكيد الاعتماد").click()
    assert "حالة المقترح لا تسمح بذلك" in page.get_by_role("alert").inner_text()
    assert _status(owner, clinic.note.id)[0] == "APPROVED"


def test_acknowledging_a_red_flag_records_it_once(browser, clinic, owner):
    page = browser.open(token=_token(), path="/console/#/red-flags")
    page.get_by_text(RED_FLAG_TEXT).wait_for()
    page.get_by_role("button", name="استلام البلاغ").click()
    page.get_by_label("ملاحظة (اختيارية)").fill("اتصلتُ بالمريض.")
    page.get_by_role("button", name="تأكيد الاستلام").click()

    page.get_by_text("لا بلاغات عاجلة غير مستلَمة.").wait_for()
    with owner.cursor() as cursor:
        cursor.execute("SELECT acknowledged_at IS NOT NULL FROM red_flag_reports WHERE id = %s",
                       (clinic.flag.id,))
        assert cursor.fetchone()[0] is True
    page.get_by_role("link", name="البلاغات العاجلة، 0").wait_for()


# ── الشريط الجانبي ──────────────────────────────────────────────────────


def test_the_sidebar_sits_on_the_right_and_collapses_to_48px_icons(browser, clinic):
    page = browser.open(token=_token())
    page.get_by_role("list", name="المقترحات بانتظار المراجعة").wait_for()
    sidebar = page.locator("[data-sidebar='sidebar']").first
    box = sidebar.bounding_box()
    assert box["x"] + box["width"] >= DESKTOP["width"] - 1, "الشريط ليس في بداية السطر العربي"

    page.get_by_role("button", name="إظهار الشريط الجانبي أو طيّه").first.click()
    page.locator("[data-state='collapsed'][data-side='right']").wait_for()
    page.wait_for_timeout(400)   # انتقال العرض
    for name in ("طابور المراجعة، 2", "البلاغات العاجلة، 1"):
        link = _nav(page).get_by_role("link", name=name).bounding_box()
        assert link["width"] >= 48 and link["height"] >= 48, (name, link)

    link = _nav(page).get_by_role("link", name="البلاغات العاجلة، 1")
    link.hover()
    tooltip = page.get_by_role("tooltip")
    tooltip.wait_for()
    assert tooltip.inner_text().strip() == "البلاغات العاجلة، 1"
    assert tooltip.bounding_box()["x"] + tooltip.bounding_box()["width"] <= link.bounding_box()["x"] + 1

    # العاجل ظاهرٌ مطويّاً، بلا مرور: العدد على الأيقونة نفسها.
    page.mouse.move(10, 10)
    urgent = _nav(page).locator("[data-urgent-count]")
    assert urgent.is_visible() and urgent.inner_text() == "1"

    # الحالة للجلسة المفتوحة وحدها: لا ملفّ ارتباط على الأصل، والتحميل يبدأ ظاهراً.
    assert not [c for c in page.context.cookies() if c["name"] == "sidebar_state"]
    page.reload(wait_until="networkidle")
    page.locator("[data-state='expanded'][data-side='right']").wait_for()
    assert not browser.problems, browser.problems


def test_on_a_phone_the_sidebar_is_a_named_sheet_that_closes_on_navigation(browser, clinic):
    page = browser.open(viewport=PHONE, token=_token())
    page.get_by_role("list", name="المقترحات بانتظار المراجعة").wait_for()
    assert _nav(page).count() == 0

    page.get_by_role("button", name="إظهار الشريط الجانبي أو طيّه").click()
    sheet = page.get_by_role("dialog", name="القائمة الجانبية")
    sheet.wait_for()
    box = sheet.bounding_box()
    assert box["x"] + box["width"] >= PHONE["width"] - 1, "النافذة لا تنزلق من اليمين"

    sheet.get_by_role("link", name="البلاغات العاجلة، 1").click()
    sheet.wait_for(state="detached")
    page.get_by_text(RED_FLAG_TEXT).wait_for()
    assert not browser.problems, browser.problems


def _focused(page) -> str:
    return page.evaluate(
        "() => { const e = document.activeElement;"
        " return `${e.tagName}:${e.getAttribute('aria-label') || e.textContent.trim().slice(0, 40)}` }")


def test_the_phone_sheet_is_reachable_and_leaves_by_keyboard(browser, clinic):
    page = browser.open(viewport=PHONE, token=_token())
    page.get_by_role("list", name="المقترحات بانتظار المراجعة").wait_for()
    # بموقع العنصر لا بدوره: النافذة المفتوحة تُخفي ما خارجها عن شجرة الوصول.
    trigger = page.locator("[data-sidebar='trigger']")
    assert trigger.get_attribute("aria-label") == "إظهار الشريط الجانبي أو طيّه"
    assert trigger.get_attribute("aria-expanded") == "false"
    trigger.focus()
    page.keyboard.press("Enter")
    sheet = page.get_by_role("dialog", name="القائمة الجانبية")
    sheet.wait_for()
    assert trigger.get_attribute("aria-expanded") == "true"
    page.wait_for_timeout(300)

    # يبدأ على رابط الصفحة الحالية، لا على «تسجيل الخروج».
    assert _focused(page) == "A:طابور المراجعة، 2"
    page.keyboard.press("Tab")
    assert _focused(page) == "A:البلاغات العاجلة، 1"

    # Escape واحدة تغلق، ويعود التركيز إلى الزرّ الذي فتح.
    page.keyboard.press("Escape")
    sheet.wait_for(state="detached")
    assert _focused(page) == "BUTTON:إظهار الشريط الجانبي أو طيّه"

    # زرّ إغلاقٍ ظاهر، ورابط الصفحة الحالية يغلقها أيضاً.
    trigger.click()
    sheet.wait_for()
    sheet.get_by_role("button", name="إغلاق القائمة").click()
    sheet.wait_for(state="detached")
    trigger.click()
    sheet.wait_for()
    sheet.get_by_role("link", name="طابور المراجعة، 2").click()
    sheet.wait_for(state="detached")

    # الانتقال من النافذة يضع التركيز على عنوان الصفحة الجديدة.
    trigger.click()
    sheet.wait_for()
    sheet.get_by_role("link", name="البلاغات العاجلة، 1").click()
    sheet.wait_for(state="detached")
    page.get_by_text(RED_FLAG_TEXT).wait_for()
    page.wait_for_timeout(300)
    assert _focused(page) == "H1:البلاغات العاجلة"
    assert not browser.problems, browser.problems


def test_focus_follows_each_decision_step(browser, clinic):
    page = browser.open(token=_token(), path=f"/console/#/queue/{clinic.note.id}")
    page.get_by_text(DOCUMENTATION_TEXT).wait_for()
    assert page.title() == "مراجعة مقترح — لوحة الممارس — Symbol AI"

    page.get_by_role("button", name="رفض", exact=True).click()
    assert page.evaluate("() => document.activeElement.id") == "reject-reason"
    page.get_by_role("button", name="تراجع").click()
    assert _focused(page) == "BUTTON:رفض"

    page.get_by_role("button", name="اعتماد", exact=True).click()
    # يُقرأ ما سيحدث أولاً؛ Enter هنا لا تعتمد شيئاً.
    assert _focused(page).startswith("P:بعد الاعتماد")
    page.keyboard.press("Enter")
    assert page.get_by_role("button", name="تأكيد الاعتماد").is_visible()
    page.get_by_role("button", name="تراجع").click()
    assert _focused(page) == "BUTTON:اعتماد"


def test_after_a_decision_the_queue_opens_at_the_top(browser, clinic, owner):
    page = browser.open(viewport={"width": 390, "height": 600}, token=_token(),
                        path=f"/console/#/queue/{clinic.plan.id}")
    page.get_by_text(FIRST_STEP_TITLE).wait_for()
    page.get_by_role("button", name="اعتماد", exact=True).click()
    page.get_by_role("button", name="تأكيد الاعتماد").scroll_into_view_if_needed()
    assert page.evaluate("() => scrollY") > 0
    page.get_by_role("button", name="تأكيد الاعتماد").click()
    notice = page.get_by_role("status").get_by_text("اعتُمد المقترح.")
    notice.wait_for()
    assert page.evaluate("() => scrollY") == 0
    assert notice.bounding_box()["y"] >= 0
    assert page.title() == "طابور المراجعة — لوحة الممارس — Symbol AI"


def test_acknowledging_is_announced_and_focus_returns_to_the_heading(browser, clinic):
    page = browser.open(token=_token(), path="/console/#/red-flags")
    page.get_by_text(RED_FLAG_TEXT).wait_for()
    # المنطقة الحيّة موجودةٌ قبل الرسالة، فتُعلَن حين تتغيّر.
    assert page.get_by_role("status").count() >= 1
    page.get_by_role("button", name="استلام البلاغ").click()
    assert page.evaluate("() => document.activeElement.tagName") == "TEXTAREA"
    page.get_by_role("button", name="تأكيد الاستلام").click()
    page.get_by_role("status").get_by_text("سُجّل استلام البلاغ.").wait_for()
    assert _focused(page) == "H1:البلاغات العاجلة"


def test_a_second_acknowledgment_is_announced_too(browser, clinic, seed):
    """
    استلامان متتاليان والرسالة نفسها. لو بقيت فقرتها كما هي لما تغيّر في
    المنطقة الحيّة شيء، ولما سمع مستخدم قارئ الشاشة أن الثاني سُجّل.
    """
    escalation.report(tenant_id=seed.tenant_a, patient_id=seed.patient_a,
                      body=SECOND_FLAG_TEXT, reported_by=clinic.flag.reported_by)
    page = browser.open(token=_token(), path="/console/#/red-flags")
    page.get_by_text(SECOND_FLAG_TEXT).wait_for()

    def acknowledge_the_oldest():
        page.get_by_role("button", name="استلام البلاغ").first.click()
        page.get_by_role("button", name="تأكيد الاستلام").click()

    acknowledge_the_oldest()
    page.get_by_role("status").get_by_text("سُجّل استلام البلاغ.").wait_for()
    page.get_by_text(RED_FLAG_TEXT).wait_for(state="detached")
    page.evaluate("""() => {
        window.__announced = []
        new MutationObserver((records) => {
            for (const record of records)
                for (const node of record.addedNodes) window.__announced.push(node.textContent)
        }).observe(document.querySelector('[role=status][aria-live=polite]'),
                   { childList: true, subtree: true, characterData: true })
    }""")

    acknowledge_the_oldest()
    page.get_by_text("لا بلاغات عاجلة غير مستلَمة.").wait_for()
    announced = page.evaluate("() => window.__announced")
    assert any("سُجّل استلام البلاغ." in (text or "") for text in announced), announced
    assert not browser.problems, browser.problems


def test_an_expired_session_says_so_and_keeps_the_unsent_reason(browser, clinic, owner):
    page = browser.open(token=_token(), path=f"/console/#/queue/{clinic.note.id}")
    page.get_by_text(DOCUMENTATION_TEXT).wait_for()
    page.get_by_role("button", name="رفض", exact=True).click()
    reason = "القياس غير موثّق بأداة معيارية، ويُعاد بعد الجلسة القادمة."
    page.get_by_label("سبب الرفض (إلزامي)").fill(reason)

    identity.revoke_user_sessions(clinic.practitioner.id)
    page.get_by_role("button", name="تأكيد الرفض").click()
    assert "انتهت الجلسة" in page.get_by_role("alert").inner_text()

    page.get_by_label("البريد الإلكتروني").fill(PRACTITIONER_EMAIL)
    page.get_by_label("كلمة المرور").fill(SECRET)
    page.get_by_role("button", name="تسجيل الدخول").click()
    page.get_by_text(DOCUMENTATION_TEXT).wait_for()
    assert page.get_by_label("سبب الرفض (إلزامي)").input_value() == reason
    assert _status(owner, clinic.note.id) == ("PENDING", None)


@pytest.mark.parametrize("viewport", [PHONE, {"width": 768, "height": 1024}], ids=["390", "768"])
def test_doubled_text_never_scrolls_sideways(browser, clinic, viewport):
    for path, marker in (("/console/#/queue", "علامة حمراء"),
                         (f"/console/#/queue/{clinic.plan.id}", FIRST_STEP_TITLE),
                         ("/console/#/red-flags", RED_FLAG_TEXT)):
        page = browser.open(viewport=viewport, token=_token(), path=path)
        page.get_by_text(marker).first.wait_for()
        page.evaluate("() => { document.documentElement.style.fontSize = '200%' }")
        page.wait_for_timeout(300)
        assert page.evaluate("() => document.scrollingElement.scrollWidth - innerWidth") <= 1, path
    page.get_by_role("button", name="إظهار الشريط الجانبي أو طيّه").click()
    if viewport is PHONE:
        sheet = page.get_by_role("dialog", name="القائمة الجانبية")
        sheet.wait_for()
        sheet.evaluate("(e) => Promise.all(e.getAnimations().map((a) => a.finished))")
        box = sheet.bounding_box()
        assert box["x"] >= -1 and box["x"] + box["width"] <= viewport["width"] + 1


# ── المقاييس ─────────────────────────────────────────────────────────────

#: شارة العدد في المكوّن مرسومةٌ فوق زرّ القائمة عمداً (`SidebarMenuBadge`
#: أخٌ مطلق الموضع لا ابن، ولا يلتقط النقر). تداخلها مع زرّها وحده تصميم لا
#: عيب؛ ما يهمّ ألّا يمرّ الاسم تحتها، ويقيسه اختبارٌ مستقلّ أدناه.
OVERLAP_EXCEPT_BADGE = OVERLAP_SCRIPT.replace(
    "if (a.contains(b) || b.contains(a)) continue;",
    "if (a.contains(b) || b.contains(a)) continue;\n"
    "      const badge = (x, y) => x.dataset.sidebar === 'menu-badge'"
    " && y.dataset.sidebar === 'menu-button' && x.parentElement === y.parentElement;\n"
    "      if (badge(a, b) || badge(b, a)) continue;",
)
assert OVERLAP_EXCEPT_BADGE != OVERLAP_SCRIPT

#: زرّ الحافة (`SidebarRail`) خطٌّ بعرض 16px للفأرة؛ وظيفته نفسها في زرّ
#: الإظهار (48px) فيُستثنى بنصّ WCAG 2.5.8 (الهدف المكافئ).
TARGETS_EXCEPT_RAIL = TOUCH_TARGET_SCRIPT.replace(
    "if (style.visibility === 'hidden'",
    "if (element.dataset.sidebar === 'rail') continue;\n    if (style.visibility === 'hidden'",
)


@pytest.mark.parametrize("viewport", [DESKTOP, {"width": 1024, "height": 768}, PHONE],
                         ids=["1440", "1024", "390"])
@pytest.mark.parametrize("screen", ["queue", "proposal", "red-flags"])
def test_every_screen_passes_the_portal_audit(browser, clinic, viewport, screen):
    path = {
        "queue": "/console/#/queue",
        "proposal": f"/console/#/queue/{clinic.plan.id}",
        "red-flags": "/console/#/red-flags",
    }[screen]
    page = browser.open(viewport=viewport, token=_token(), path=path)
    marker = {"queue": "علامة حمراء", "proposal": FIRST_STEP_TITLE, "red-flags": RED_FLAG_TEXT}[screen]
    page.get_by_text(marker).first.wait_for()
    page.wait_for_timeout(300)

    assert not page.evaluate(CONTRAST_SCRIPT), f"تباين في {screen}"
    assert not page.evaluate(OVERLAP_EXCEPT_BADGE), f"تداخل في {screen}"
    assert not page.evaluate(TARGETS_EXCEPT_RAIL, 44), f"مساحة لمس في {screen}"
    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT), f"فيض أفقي في {screen}"


def test_a_long_label_never_runs_under_its_count_badge(browser, clinic):
    page = browser.open(token=_token())
    page.get_by_role("list", name="المقترحات بانتظار المراجعة").wait_for()
    # أطول اسمٍ ممكن في عرض الشريط: يُقصّ بنقاط، ولا يبلغ الشارة.
    page.evaluate("""() => {
        for (const link of document.querySelectorAll('[data-sidebar=menu-button] > span:last-child'))
            link.textContent = 'طابور المراجعة والمقترحات المعلّقة لدى الممارس المناوب'
    }""")
    overlaps = page.evaluate("""() => [...document.querySelectorAll('[data-sidebar=menu-badge]')].map((badge) => {
        const label = badge.parentElement.querySelector('[data-sidebar=menu-button] > span:last-child')
        const a = label.getBoundingClientRect(), b = badge.getBoundingClientRect()
        return Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0
            && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0
    })""")
    assert overlaps == [False, False]


def test_the_login_screen_passes_the_portal_audit(browser, clinic):
    page = browser.open(viewport=PHONE)
    page.get_by_role("button", name="تسجيل الدخول").wait_for()
    assert not page.evaluate(CONTRAST_SCRIPT)
    assert not page.evaluate(OVERLAP_SCRIPT)
    assert not page.evaluate(TOUCH_TARGET_SCRIPT, 44)
    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT)


def test_the_document_is_arabic_and_right_to_left(browser, clinic):
    page = browser.open()
    assert page.evaluate("() => [document.documentElement.lang, document.documentElement.dir]") == ["ar", "rtl"]
