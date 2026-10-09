"""
تجهيزات الواجهة الجديدة (/next/)
================================
الخادم نفسه الذي تختبره واجهة «/» (`server` في tests/ui/conftest.py) يقدّم الواجهة
الجديدة مبنيةً تحت /next/؛ بلا بناءٍ لا اختبار هنا، وفي CI فشلٌ لا تجاوز. المراقبة
(INSTRUMENT) تعدّ ما تستدعيه قطعة التطبيق `assets/app-*.js` وحدها من المؤقّتات والمستمعين:
جدولة React وإطارات framer-motion في `vendor` مسموحةٌ حين تبدأ بضغطةٍ أو بردّ خادم.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from eyework import terms
from eyework.tests.api.conftest import add_user
from eyework.tests.ui.conftest import PASSWORD, REQUIRE_BROWSER
from eyework.web.app import CLIENT_DIST

LOGIN = "ali@example.sa"
NAME = "علي"

#: إطارات الواجهة الجديدة. قائمة الواجهة القائمة (tests/ui/conftest.py) لا تُمسّ: اختباراتها تفهرسها
#: بالموضع. الهواتف: Safari بشريطيه على iPhone 12 mini و12–14، و15/16 (393) و15/16 Plus (430)؛
#: وإطار إجهادٍ 320 (تكبير الشاشة)؛ والآيباد: mini عمودياً (744)، والعاشر (820)، وPro 12.9 (1024)،
#: وأفقياً (1180×820)؛ والحاسوب. لم تُقَس على جهاز (بوابة الإصدار 0 تطبع الإطار الحقيقي).
PHONES = [(375, 635), (390, 664), (393, 700), (430, 800)]
STRESS = (320, 635)
HANDHELD = [*PHONES, STRESS]
TABLETS = [(744, 1133), (820, 1180), (1024, 1366)]
LANDSCAPE = (1180, 820)
DESKTOP = (1280, 800)
#: ما يمشي عليه المسار الكامل: كل الهواتف، وأصغر الآيباد وأكبره، والأفقي، والحاسوب.
FRAMES = [*HANDHELD, TABLETS[0], TABLETS[2], LANDSCAPE, DESKTOP]
#: أضيق إطارين: لا يتّسع نصٌّ فيهما إلا اتّسع في كل إطارٍ أعرض وأطول.
TIGHTEST = [PHONES[0], STRESS]
#: ما يعرض الشريط الجانبي.
WIDE = [TABLETS[0], LANDSCAPE, DESKTOP]


def frame_ids(frames) -> list[str]:
    return [f"{w}x{h}" for w, h in frames]

INSTRUMENT = r"""
(() => {
    const log = { timers: [], listeners: [], csp: [] };
    Object.defineProperty(window, '__eyework', { value: log });
    // الإطار المباشر وحده: ما تستدعيه شيفرة التطبيق بنفسها، لا ما يستدعيه React بالنيابة عنها
    // (مستمعو الجذر عند createRoot، وجدولة التحديثات) وإن ظهر التطبيق أسفل المكدّس.
    const app = (stack) => /\/assets\/app-[^/]+\.js/.test(((stack || '').split('\n')[2]) || '');
    for (const name of ['setTimeout', 'setInterval', 'requestAnimationFrame', 'requestIdleCallback']) {
        const original = window[name];
        if (!original) continue;
        window[name] = function (...args) {
            if (app(new Error().stack)) log.timers.push(name);
            return original.apply(this, args);
        };
    }
    const add = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, ...rest) {
        if (app(new Error().stack)) log.listeners.push(type);
        return add.call(this, type, ...rest);
    };
    document.addEventListener('securitypolicyviolation', (e) => log.csp.push(e.violatedDirective + ' ' + e.blockedURI));
})();
"""


@pytest.fixture(scope="session", autouse=True)
def built_client() -> None:
    if (CLIENT_DIST / "index.html").exists():
        return
    message = "الواجهة الجديدة غير مبنية: cd eyework/client && npm ci && npm run build"
    if REQUIRE_BROWSER:
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def member(owner, username: str = LOGIN, *, profession: str = "MARKETING", size: str | None = "COMPACT",
           terms_version: str | None = terms.TERMS_VERSION, name: str | None = NAME) -> UUID:
    """حسابٌ مفعَّل بكلمة المرور المعروفة، بطريقة استخدامٍ (أو بدونها) وموافقةٍ (أو بدونها)."""
    user_id = add_user(owner, username, profession=profession, terms_version=terms_version)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET ui_size = %s, display_name = %s WHERE id = %s", (size, name, user_id))
    return user_id


@pytest.fixture
def next_page(browser, server):
    """صفحةٌ على الواجهة الجديدة: بجلسة حسابٍ إن طُلب (الدخول بالمسار الحقيقي)، وبالمراقبة."""
    from eyework.web.deps import Limiters

    # الحدود في الذاكرة تُصفَّر كما تُصفَّر القاعدة: كل اختبارٍ يدخل باسم الدخول نفسه.
    server["app"].state.limiters = Limiters.default()
    contexts = []

    def make(width: int = 390, height: int = 664, *, login: str | None = None, size: str | None = None):
        context = browser.new_context(viewport={"width": width, "height": height}, locale="ar-SA", has_touch=True)
        context.add_init_script(INSTRUMENT)
        if login:
            response = context.request.post(
                server["base"] + "/api/auth/login",
                data={"username": login, "password": PASSWORD},
                headers={"X-Eyework": "1", "Origin": server["base"]},
            )
            assert response.status == 204, response.status
        contexts.append(context)
        page = context.new_page()
        page.requests = []
        page.on("request", lambda request: page.requests.append((request.method, request.url)))
        page.errors = []
        page.on("pageerror", lambda error: page.errors.append(str(error)))
        page.next = f"{server['base']}/next/" + ("?size=large" if size == "gaze" else "")
        return page

    yield make
    for context in contexts:
        context.close()
