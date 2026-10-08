"""
تجهيزات اختبارات المتصفّح
=========================
التطبيق الحقيقي — المصنع نفسه والقاعدة نفسها والملفات الساكنة نفسها — في
خيطٍ داخل pytest، والكاتب المصطنع محقونٌ بدل النموذج. والمتصفّح Chromium عبر
Playwright.

`EYEWORK_REQUIRE_BROWSER=1` يجعل غياب المتصفّح فشلاً لا تجاوزاً.

نصٌّ مُهيّأ يُحقن قبل أيّ شيفرةٍ في الصفحة ويسجّل: كل مؤقّت، وكل طلب كاميرا،
وكل مستمعٍ يُضاف. الاختبارات تقرأ السجلّ.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

from eyework import auth, config
from eyework.db import Database
from eyework.tests.conftest import app_url_for
from eyework.tests.fakes import FakeCopywriter

REQUIRE_BROWSER = os.environ.get("EYEWORK_REQUIRE_BROWSER") == "1"
#: المتصفّح المثبَّت في بيئة التطوير، حين لا يطابق إصدار Playwright متصفّحه.
LOCAL_CHROMIUM = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
LOGIN_KEY = b"k" * 32
LOGIN = "ali@example.sa"
PASSWORD = "Strong-Password-2026-x"

#: مقاسات الهاتف — مؤقّتة: Safari بشريطيه على iPhone 12 mini وعلى 12/13/14،
#: والشاشة الرئيسية. لم تُقَس على جهاز، ولم يُتحقَّق منها في Safari على iOS 26
#: و27 ولا في تخطيطات الألسنة (Tabs) فيه. وiPhone SE (الجيل الثالث) غائب: لا
#: مصدر لإطاره في Safari، ولا يُكتب هنا رقمٌ مخمَّن. تُستبدل كلّها بما يطبعه «فحص
#: الإدخال» (حجم النافذة) على الأجهزة في بوابة الإصدار 0.
PHONES = [(375, 635), (390, 664), (390, 763)]
#: إطار إجهاد، لا جهاز: أضيق من كل مقاسٍ أعلاه، بارتفاع أقصرها. «تكبير الشاشة»
#: (Display Zoom) يكبّر النصّ والعناصر، وأرجح — استنتاجاً لا قياساً — أنه يضيّق
#: عرض الصفحة؛ فعقد النظر يُفرض هنا أيضاً.
STRESS = (320, 635)
#: كل إطارٍ يُمسك فيه الهاتف: المؤقّتة وإطار الإجهاد.
HANDHELD = [*PHONES, STRESS]
DESKTOP = (1280, 800)
VIEWPORTS = [*HANDHELD, DESKTOP]

INSTRUMENT = r"""
(() => {
    const log = { timers: [], camera: 0, listeners: [] };
    Object.defineProperty(window, '__eyework', { value: log });
    for (const name of ['setTimeout', 'setInterval', 'requestAnimationFrame', 'requestIdleCallback']) {
        const original = window[name];
        if (!original) continue;
        // يُحسب ما تستدعيه شيفرة التطبيق وحدها؛ أدوات الاختبار نفسها تستعمل
        // requestAnimationFrame في انتظارها.
        window[name] = function (...args) {
            if (/\/(app|ui|portal|probe)\.js/.test(new Error().stack || '')) log.timers.push(name);
            return original.apply(this, args);
        };
    }
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        navigator.mediaDevices.getUserMedia = (...args) => { log.camera += 1; return original(...args); };
    }
    const add = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, ...rest) {
        if (/\/(app|ui|portal)\.js/.test(new Error().stack || '')) log.listeners.push(type);
        return add.call(this, type, ...rest);
    };
})();
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def playwright_api():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if REQUIRE_BROWSER:
            pytest.fail("playwright غير مثبّت", pytrace=False)
        pytest.skip("playwright غير مثبّت")
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_api):
    try:
        instance = playwright_api.chromium.launch()
    except Exception:
        if not LOCAL_CHROMIUM.exists():
            if REQUIRE_BROWSER:
                pytest.fail("لا متصفّح Chromium", pytrace=False)
            pytest.skip("لا متصفّح Chromium")
        instance = playwright_api.chromium.launch(executable_path=str(LOCAL_CHROMIUM), args=["--no-sandbox"])
    yield instance
    instance.close()


@pytest.fixture(scope="session")
def server(owner_url):
    """uvicorn في خيط، على منفذٍ حرّ، بالكاتب المصطنع."""
    import uvicorn

    from eyework.web.app import create_app

    port = _free_port()
    settings = config.Settings(
        app_database_url=app_url_for(owner_url), login_key=LOGIN_KEY,
        anthropic_api_key=None, public_origin=f"http://localhost:{port}",
    )
    writer = FakeCopywriter()
    database = Database(settings.app_database_url)
    app = create_app(settings, copywriter=writer, database=database)
    instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not instance.started:
        if time.monotonic() > deadline:
            raise RuntimeError("الخادم لم يبدأ")
        time.sleep(0.05)
    yield {"base": f"http://localhost:{port}", "writer": writer, "app": app}
    instance.should_exit = True
    thread.join(timeout=10)
    database.close()


@pytest.fixture
def signed_in(owner, server):
    """مستخدمٌ مفعَّل بكلمة مرورٍ معروفة؛ كل سياقٍ يدخل به عبر نقطة الدخول."""
    from eyework.passwords import hash_password

    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac, password_hash, activated_at, profession)"
            " VALUES (%s, %s, now(), 'MARKETING')",
            (auth.login_hmac(LOGIN_KEY, LOGIN), hash_password(PASSWORD)),
        )
    server["writer"].outcomes.clear()
    server["writer"].requests.clear()
    # الحدود في الذاكرة تُصفَّر كما تُصفَّر القاعدة: كل اختبارٍ يدخل باسم الدخول
    # نفسه، وخمسة دخولٍ في الدقيقة حدُّ الإنتاج لا حدُّ المجموعة.
    from eyework.web.deps import Limiters

    server["app"].state.limiters = Limiters.default()


@pytest.fixture
def page_factory(browser, server, signed_in):
    contexts = []

    def make(width: int = 390, height: int = 664, *, session: bool = True):
        context = browser.new_context(viewport={"width": width, "height": height}, locale="ar-SA", has_touch=True)
        context.add_init_script(INSTRUMENT)
        if session:
            # الدخول بالمسار الحقيقي: ملفّ `__Host-` لا يُزرع من خارج المتصفّح.
            response = context.request.post(
                server["base"] + "/api/auth/login",
                data={"username": LOGIN, "password": PASSWORD},
                headers={"X-Eyework": "1", "Origin": server["base"]},
            )
            assert response.status == 204, response.status
        contexts.append(context)
        page = context.new_page()
        page.requests = []
        page.on("request", lambda request: page.requests.append((request.method, request.url)))
        page.errors = []
        page.on("pageerror", lambda error: page.errors.append(str(error)))
        return page

    yield make
    for context in contexts:
        context.close()
