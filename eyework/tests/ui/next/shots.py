"""
لقطات الواجهة الجديدة للمالك
============================
يشغّل الخادم بالبديل الوهمي للنموذج ويمشي في الشاشات الرئيسة (ما قبل الدخول، والتسجيل، والبوابة،
وأداة الحملة، و«حسابي») على كل إطارٍ بالحجمين، ويحفظ لقطةً لكل شاشة ويطبع تدقيق عقد النظر لها.

    EYEWORK_TEST_DATABASE_URL=… EYEWORK_SHOTS=/tmp/shots python -m eyework.tests.ui.next.shots [size:WxH …]

بلا وسائط: كل الإطارات (`FRAMES`) × الحجمين. يحتاج العميل مبنيّاً (`npm run build`) وقاعدةً مهاجَرةً
ينتهي اسمها بـ`_test` (تُمحى حساباتها؛ غيرها يُرفض كما في الاختبارات). ليس اختباراً: لا يجمعه pytest،
وما يطبعه يُقرأ بالعين.
"""

from __future__ import annotations

import io
import os
import socket
import sys
import threading
import time
import traceback

import psycopg
import uvicorn
from PIL import Image
from playwright.sync_api import sync_playwright

from eyework import config
from eyework.db import Database
from eyework.tests.conftest import app_url_for
from eyework.tests.fakes import FakeCopywriter, FakeGateway
from eyework.tests.ui.conftest import LOCAL_CHROMIUM, PASSWORD
from eyework.tests.ui.next.conftest import FRAMES, INSTRUMENT, LOGIN, frame_ids, member
from eyework.tests.ui.next.flow import Flow
from eyework.web.app import create_app
from eyework.web.deps import Limiters


def start_server(owner_url: str):
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    settings = config.Settings(
        app_database_url=app_url_for(owner_url), login_key=b"k" * 32, anthropic_api_key=None,
        public_origin=f"http://localhost:{port}", support_contact="help@example.sa", registration="open",
    )
    app = create_app(settings, copywriter=FakeCopywriter(), gateway=FakeGateway(), database=Database(settings.app_database_url))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < deadline, "لم يبدأ الخادم"
        time.sleep(0.05)
    return app, server, f"http://localhost:{port}"


def sample_photo() -> dict:
    buffer = io.BytesIO()
    Image.effect_noise((1200, 900), 40).convert("RGB").save(buffer, "JPEG")
    return {"name": "p.jpg", "mimeType": "image/jpeg", "buffer": buffer.getvalue()}


def before_login(page, flow, base: str, size: str, shot) -> None:
    page.goto(base + "/next/" + ("?size=large" if size == "gaze" else "") + "#/")
    flow.screen("#welcome-login"); flow.audit("welcome"); shot("01-welcome")
    flow.press("#welcome-login", lambda: flow.screen("input[name='username']"), "ادخل"); flow.audit("login"); shot("02-login")
    flow.press("#login-signup", lambda: flow.screen("#notice-next"), "أنشئ حساباً"); flow.audit("notice-kept"); shot("03-notice-kept")
    flow.press("#notice-next", lambda: flow.screen("#signup-agree"), "التالي"); flow.audit("notice-sent"); shot("04-notice-sent")
    flow.press("#signup-agree", lambda: flow.screen("#signup-use-next"), "أوافق وأتابع"); flow.audit("signup-use"); shot("05-signup-use")
    flow.press("#signup-use-" + ("GAZE" if size == "gaze" else "COMPACT"), lambda: None, "طريقة الاستخدام")
    flow.press("#signup-use-next", lambda: flow.screen("#signup-name-input"), "التالي"); flow.audit("signup-name"); shot("06-signup-name")
    page.fill("#signup-name-input", "سارة")
    flow.press("#signup-name-next", lambda: flow.screen("#signup-year-presets"), "التالي"); flow.audit("signup-year"); shot("07-signup-year")
    flow.press("#signup-year-presets button >> nth=1", lambda: flow.until("!document.querySelector('#signup-year-next').disabled"), "سنة")
    flow.press("#signup-year-next", lambda: flow.screen("#signup-month-presets"), "التالي")
    flow.press("#signup-month-presets button >> nth=2", lambda: flow.until("!document.querySelector('#signup-month-next').disabled"), "شهر")
    flow.press("#signup-month-next", lambda: flow.screen("#signup-day-presets"), "التالي")
    flow.press("#signup-day-presets button >> nth=1", lambda: flow.until("!document.querySelector('#signup-day-next').disabled"), "يوم")
    flow.press("#signup-day-next", lambda: flow.screen("#signup-profession-MARKETING"), "التالي"); flow.audit("signup-profession"); shot("08-signup-profession")
    flow.press("#signup-profession-MARKETING", lambda: flow.until("!document.querySelector('#signup-profession-next').disabled"), "المهنة")
    flow.press("#signup-profession-next", lambda: flow.screen("#signup-email-input"), "التالي")
    page.fill("#signup-email-input", "sara@example.com")
    flow.press("#signup-email-next", lambda: flow.screen("#signup-review-next"), "التالي"); flow.audit("signup-review"); shot("09-signup-review")
    flow.press("#signup-review-next", lambda: flow.screen("#signup-password-input"), "التالي"); flow.audit("signup-password"); shot("10-signup-password")


def portal(page, flow, base: str, size: str, shot, photo: dict) -> None:
    # بعد الدخول تُحمَّل الصفحة من جديد: تغيير الوسم وحده لا يعيد قراءة /api/me.
    page.goto("about:blank")
    page.goto(base + "/next/" + ("?size=large" if size == "gaze" else "") + "#/")
    flow.screen("#home-new"); flow.audit("home"); shot("11-home")
    if page.locator("#nav-sections").count():
        flow.press("#nav-sections", lambda: flow.screen("dialog[open]"), "الأقسام"); flow.audit("sections"); shot("12-sections")
        flow.press("dialog[open] >> text=إغلاق", lambda: page.wait_for_selector("dialog[open]", state="detached"), "إغلاق")
    if page.locator("#nav-tools").count():
        flow.press("#nav-tools", lambda: flow.screen("dialog[open]"), "الأدوات"); flow.audit("tools"); shot("13-tools")
        flow.press("dialog[open] >> text=اسأل سيمبول", lambda: flow.screen("dialog[open] textarea"), "اسأل سيمبول")
    else:
        flow.press("#nav-assistant", lambda: flow.screen("dialog[open] textarea"), "اسأل سيمبول")
    flow.audit("assistant"); shot("14-assistant")
    flow.press("dialog[open] >> text=إغلاق", lambda: page.wait_for_selector("dialog[open]", state="detached"), "إغلاق")
    flow.press("#home-new", lambda: flow.screen("#photo-input"), "حملة جديدة"); flow.audit("photo"); shot("15-photo")
    page.set_input_files("#photo-input", files=[photo])
    flow.until("!document.querySelector('#photo-generate').disabled"); flow.audit("photo-draft"); shot("16-photo-draft")
    flow.press("#photo-generate", lambda: flow.screen("#proposal-copy"), "اكتب لي العنوان والوصف"); flow.audit("proposal"); shot("17-proposal")
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    flow.press("#edit-chips button >> nth=0", lambda: None, "خيار تعديل"); flow.audit("edit"); shot("18-edit")
    flow.press("#edit-note", lambda: flow.screen("#note-text"), "ملاحظة نصية")
    page.fill("#note-text", "اذكر أنه مصنوعٌ من الجلد الطبيعي"); flow.audit("note"); shot("19-note")
    flow.press("#note-save", lambda: flow.screen("#edit-chips"), "احفظ الملاحظة")
    flow.press("#edit-back", lambda: flow.screen("#proposal-copy"), "رجوع")
    end = lambda word: lambda: flow.until(f"document.querySelector('#proposal-end').textContent.includes('{word}')")
    flow.press("#proposal-end", end("الميزانية"), "أوافق على النص"); flow.audit("approved"); shot("20-approved")
    flow.press("#proposal-end", lambda: flow.screen("#budget-presets"), "تابع إلى الميزانية")
    flow.press("#budget-presets button >> nth=1", lambda: flow.until("!document.querySelector('#budget-next').disabled"), "مبلغ جاهز"); flow.audit("budget"); shot("21-budget")
    flow.press("#budget-next", lambda: flow.screen("#days-presets"), "التالي: عدد الأيام")
    flow.press("#days-presets button >> nth=1", lambda: flow.until("!document.querySelector('#days-next').disabled"), "مدّة جاهزة"); flow.audit("days"); shot("22-days")
    flow.press("#days-next", lambda: flow.screen("#review-continue"), "التالي: المراجعة"); flow.audit("review"); shot("23-review")
    flow.press("#review-continue", lambda: flow.screen("#confirm-yes"), "متابعة للتأكيد"); flow.audit("confirm"); shot("24-confirm")
    flow.press("#confirm-yes", lambda: flow.screen("#ready-share"), "نعم، اعتمد الحملة"); flow.audit("ready"); shot("25-ready")
    flow.press("#ready-withdraw", lambda: flow.screen("#cancel-yes"), "اسحب الحملة"); flow.audit("withdraw"); shot("26-withdraw")
    flow.press("#cancel-back", lambda: flow.screen("#ready-share"), "رجوع دون إلغاء")
    flow.press("#ready-home", lambda: flow.screen("#home-new"), "الرئيسية")
    flow.press("#home-campaigns", lambda: flow.until("document.querySelectorAll('#campaigns-list li').length === 1"), "حملاتي"); flow.audit("campaigns"); shot("27-campaigns")
    flow.press("#campaigns-list li button", lambda: flow.screen("#ready-share"), "حملة من القائمة"); flow.audit("ready-again"); shot("28-ready-from-list")
    flow.press("#nav-account", lambda: flow.screen("#account-ui-size-apply"), "حسابي"); flow.audit("account"); shot("29-account")
    flow.press("#account-logout", lambda: flow.screen("#account-confirm-yes"), "تسجيل الخروج"); flow.audit("logout"); shot("30-logout")


def run(owner_url: str, app, base: str, out: str, label: str, size: str, width: int, height: int, photo: dict) -> None:
    with psycopg.connect(owner_url, autocommit=True) as connection:
        connection.execute("TRUNCATE users, attempt_tombstones, registration_ledger RESTART IDENTITY CASCADE")
        member(connection, LOGIN, size="GAZE" if size == "gaze" else "COMPACT")
    app.state.limiters = Limiters.default()
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
        except Exception:
            browser = playwright.chromium.launch(executable_path=str(LOCAL_CHROMIUM), args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": width, "height": height}, locale="ar-SA", has_touch=True)
        context.add_init_script(INSTRUMENT)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def shot(name: str) -> None:
            page.evaluate("() => document.fonts.ready.then(() => true)")
            page.screenshot(path=os.path.join(out, f"{label}-{name}.png"))

        flow = Flow(page)
        try:
            before_login(page, flow, base, size, shot)
            response = context.request.post(base + "/api/auth/login", data={"username": LOGIN, "password": PASSWORD},
                                            headers={"X-Eyework": "1", "Origin": base})
            assert response.status == 204, response.status
            portal(page, flow, base, size, shot, photo)
        except Exception:
            shot("99-failed")
            traceback.print_exc()
        print(f"=== {label}")
        for audit in flow.audits:
            print(f"  {audit['label']:<18} enabled={audit['enabled']:<3} vertical={audit['vertical']!s:<5} "
                  f"small={audit['small']} close={audit['close']} edge={audit['edge']} clipped={audit['clipped']}")
        print("  failures:", flow.failures())
        print("  landings:", flow.landings)
        print("  errors:", errors)
        browser.close()


def main(argv: list[str]) -> None:
    owner_url = os.environ["EYEWORK_TEST_DATABASE_URL"]
    name = psycopg.conninfo.conninfo_to_dict(owner_url).get("dbname") or ""
    if not name.endswith("_test"):
        raise SystemExit(f"قاعدة اللقطات يجب أن ينتهي اسمها بـ_test (لا {name!r}): حساباتها تُمحى.")
    out = os.environ["EYEWORK_SHOTS"]
    os.makedirs(out, exist_ok=True)
    runs = argv or [f"{size}:{frame}" for frame in frame_ids(FRAMES) for size in ("compact", "gaze")]
    app, server, base = start_server(owner_url)
    photo = sample_photo()
    try:
        for spec in runs:
            size, frame = spec.split(":")
            width, height = frame.split("x")
            run(owner_url, app, base, out, f"{size}-{frame}", size, int(width), int(height), photo)
    finally:
        server.should_exit = True


if __name__ == "__main__":
    main(sys.argv[1:])
