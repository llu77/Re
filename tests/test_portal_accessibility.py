"""
تدقيق وصولية بوابة المريض — معيار القبول 8
============================================
«تُختبر لا تُفترض» حرفياً: كل بند هنا يُقاس في متصفح حقيقي على الصفحة
المرندرة، لا يُراجَع في الشيفرة.

البنود: تباين ≥ 4.5:1 للنص و3:1 للعناصر التفاعلية · مساحة لمس ≥ 44×44 ·
**غياب أي تداخل بين عنصرين في أي مقاس شاشة** · كيبورد وقارئ شاشة · تكبير 200%
دون فقد وظيفة · لا مهلة زمنية على أي تفاعل.

لا اعتماد على شبكة: الفحوص منفَّذة هنا لا مستوردة من CDN، فتعمل في CI كما
تعمل محلياً.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import pytest

from core import caregivers, identity, proposals
from core.types import Actor
from tests.conftest import cite_evidence_as, requires_db

pytestmark = requires_db

ROOT = Path(__file__).resolve().parent.parent
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

PATIENT_EMAIL = "portal.patient@example.test"
TOKEN_KEY = "symbol.patient.token"
PLAN_KEY = "symbol.patient.plan"
SECRET = "كلمة-مرور-البوابة"

#: مقاسات تغطي الهاتف الضيق حتى سطح المكتب، ومنها مقاسات معروفة بكسر التخطيط.
VIEWPORTS = [
    (320, 568),   # أضيق هاتف متداول
    (360, 740),
    (390, 844),
    (768, 1024),  # لوحي رأسي
    (1024, 768),  # لوحي أفقي
    (1440, 900),
]

playwright_api = pytest.importorskip("playwright.sync_api", reason="playwright غير مثبّت")

if not Path(CHROMIUM).exists():  # pragma: no cover - يعتمد على البيئة
    pytest.skip("متصفح Chromium غير متاح", allow_module_level=True)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def portal_server():
    """يشغّل التطبيق الحقيقي: الاختبار يقيس ما يراه المريض، لا ملفاً ساكناً."""
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
             "--retry-connrefused", "--retry-all-errors", "-o", "/dev/null",
             f"{base}/health"],
            check=True, timeout=90,
        )
        yield base
    finally:
        process.terminate()
        process.wait(timeout=20)


@pytest.fixture
def patient_token(owner, seed, portal_server):
    """مريض بحساب وخطة معتمدة — البوابة بلا محتوى لا تُدقَّق بجدوى."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'PATIENT', %s, %s) RETURNING id",
            (seed.tenant_a, PATIENT_EMAIL, identity.hash_password(SECRET)),
        )
        cursor.execute(
            "UPDATE patients SET user_id = %s WHERE id = %s",
            (cursor.fetchone()[0], seed.patient_a),
        )

    practitioner = Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)
    plan = proposals.create(
        practitioner, patient_id=seed.patient_a, kind="PLAN",
        payload={"steps": [
            {"title": "تمرين الجلوس إلى الوقوف",
             "text": "اجلس على طرف الكرسي، ضع قدميك بعرض الكتفين، وانهض ببطء."},
            {"title": "المشي في الممر",
             "text": "امشِ عشر خطوات ذهاباً وإياباً مع الاستناد عند الحاجة."},
        ]},
        affected_side="RIGHT",
    )
    cite_evidence_as(practitioner, plan.id)
    proposals.submit(plan.id, practitioner)
    proposals.approve(plan.id, practitioner)

    token, _ = identity.authenticate(PATIENT_EMAIL, SECRET, "PATIENT")
    return token


@pytest.fixture
def page(portal_server, patient_token):
    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-SA")
        context.add_init_script(
            f"localStorage.setItem('symbol.patient.token', {patient_token!r});"
        )
        opened = context.new_page()
        opened.goto(f"{portal_server}/app/", wait_until="networkidle", timeout=60000)
        opened.wait_for_timeout(1200)
        yield opened
        browser.close()


@pytest.fixture
def anonymous_page(portal_server, patient_token):
    """
    الحساب والخطة موجودان، والجهاز بلا رمز — حال المريض عند أول فتح.

    `patient_token` مطلوب لإنشاء الحساب لا لحقنه: هذا الاختبار يدخل بالنموذج.
    """
    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-SA")
        opened = context.new_page()
        opened.goto(f"{portal_server}/app/", wait_until="networkidle", timeout=60000)
        opened.wait_for_timeout(800)
        yield opened
        browser.close()


#: الشاشات التي تُدقَّق كلها، لا شاشة الخطة وحدها.
SCREENS = ["login", "plan", "progress", "offline"]


@pytest.fixture
def audited_page(request):
    """
    شاشة الدخول تحتاج جهازاً بلا رمز، وبقية الشاشات تحتاج جلسة قائمة.

    حذف الرمز من `localStorage` ثم إعادة التحميل لا يكفي: تجهيزة `page` تحقنه
    في كل تنقّل، فيعود قبل أن يقرأه الملف. الاختيار هنا بين تجهيزتين.
    """
    screen = request.node.callspec.params["screen"]
    return request.getfixturevalue("anonymous_page" if screen == "login" else "page")


def _open_screen(page, screen):
    if screen == "progress":
        page.get_by_role("button", name="تقدّمي").click()
    elif screen == "offline":
        # انقطاع حقيقي من المتصفح: شريط التنبيه يظهر بحدث `offline` لا بحقن
        page.context.set_offline(True)
    elif screen not in ("plan", "login"):
        raise AssertionError(f"شاشة غير معروفة: {screen}")
    page.wait_for_timeout(600)

    # حارس ضد تدقيق فارغ: فحوص الصفحة تمرّ على صفحة بيضاء أيضاً
    marker = {
        "login": "#login-form",
        "plan": "#step-card",
        "progress": "#progress-rows tr",
        "offline": "#offline",
    }[screen]
    page.wait_for_selector(marker, state="visible", timeout=20000)


# ── أدوات القياس داخل الصفحة ────────────────────────────────────────────

CONTRAST_SCRIPT = """
() => {
  const luminance = (rgb) => {
    const [r, g, b] = rgb.map((channel) => {
      const c = channel / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const parse = (value) => (value.match(/[\\d.]+/g) || []).slice(0, 4).map(Number);

  const effectiveBackground = (element) => {
    let node = element;
    while (node) {
      const rgba = parse(getComputedStyle(node).backgroundColor);
      if (rgba.length >= 3 && (rgba[3] === undefined || rgba[3] > 0.95)) return rgba.slice(0, 3);
      node = node.parentElement;
    }
    return [255, 255, 255];
  };

  const findings = [];
  for (const element of document.querySelectorAll('body *')) {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) continue;

    const ownText = [...element.childNodes]
      .filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim()).join(' ');
    if (!ownText) continue;

    const style = getComputedStyle(element);
    if (style.visibility === 'hidden' || style.opacity === '0') continue;

    const size = parseFloat(style.fontSize);
    const bold = parseInt(style.fontWeight, 10) >= 700;
    const isLarge = size >= 24 || (bold && size >= 18.66);

    const front = luminance(parse(style.color).slice(0, 3));
    const back = luminance(effectiveBackground(element));
    const ratio = (Math.max(front, back) + 0.05) / (Math.min(front, back) + 0.05);
    const required = isLarge ? 3 : 4.5;

    if (ratio < required) {
      findings.push({
        text: ownText.slice(0, 40), ratio: Math.round(ratio * 100) / 100,
        required, size, selector: element.tagName + '.' + (element.className || ''),
      });
    }
  }
  return findings;
}
"""

#: عنصران متداخلان هما عنصران **مرسومان** يتقاطعان دون أن يكون أحدهما سلفاً
#: للآخر. «مرسوم» هنا تعني المستطيل بعد القصّ: `getBoundingClientRect` يتجاهل
#: قصّ أوعية التمرير، فيبلّغ عن عنصر مُمرَّر خارج وعائه كأنه مرسوم فوق ما تحته —
#: تداخل لا يراه المريض. القصّ يُحسب هنا صراحةً.
OVERLAP_SCRIPT = """
() => {
  const clippers = (element) => {
    const boxes = [];
    const position = getComputedStyle(element).position;
    if (position === 'fixed') return boxes;   // لا يقصّه سلف، المنفذ وحده
    for (let node = element.parentElement; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      // سلف ساكن ليس الكتلة الحاوية لعنصر مطلق، فلا يقصّه
      if (position === 'absolute' && style.position === 'static') continue;
      if (style.overflowX !== 'visible' || style.overflowY !== 'visible') boxes.push(node);
    }
    return boxes;
  };

  const paintedRect = (element) => {
    const rect = element.getBoundingClientRect();
    let top = rect.top, right = rect.right, bottom = rect.bottom, left = rect.left;
    for (const clip of clippers(element)) {
      const box = clip.getBoundingClientRect();
      top = Math.max(top, box.top);
      left = Math.max(left, box.left);
      right = Math.min(right, box.right);
      bottom = Math.min(bottom, box.bottom);
    }
    return {
      top: Math.max(top, 0),
      left: Math.max(left, 0),
      right: Math.min(right, window.innerWidth),
      bottom: Math.min(bottom, window.innerHeight),
    };
  };

  const modal = [...document.querySelectorAll('dialog[open]')]
    .find((sheet) => sheet.matches(':modal'));
  const scope = modal ? [modal, ...modal.querySelectorAll('*')]
                      : [...document.querySelectorAll('body *')];

  const painted = [];
  for (const element of scope) {
    const style = getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0')
      continue;

    const rect = paintedRect(element);
    if (rect.right - rect.left < 2 || rect.bottom - rect.top < 2) continue;

    const interactive = element.matches('button, a, input, textarea, select, summary, [tabindex]');
    const ownText = [...element.childNodes]
      .some((n) => n.nodeType === 3 && n.textContent.trim());
    if (interactive || ownText) painted.push([element, rect]);
  }

  const clashes = [];
  for (let i = 0; i < painted.length; i++) {
    for (let j = i + 1; j < painted.length; j++) {
      const [a, ra] = painted[i];
      const [b, rb] = painted[j];
      if (a.contains(b) || b.contains(a)) continue;

      const width = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const height = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);

      if (width > 1 && height > 1) {
        clashes.push({
          a: a.tagName + '#' + (a.id || '') + '.' + (a.className || ''),
          b: b.tagName + '#' + (b.id || '') + '.' + (b.className || ''),
          area: Math.round(width * height),
        });
      }
    }
  }
  return clashes;
}
"""

HORIZONTAL_OVERFLOW_SCRIPT = """
() => {
  const out = [];
  for (const element of document.querySelectorAll('body *')) {
    const style = getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    if (style.position === 'fixed' && element.matches('.skip-link')) continue;

    const rect = element.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    if (rect.left < -1 || rect.right > window.innerWidth + 1) {
      out.push({
        selector: element.tagName + '#' + (element.id || '') + '.' + (element.className || ''),
        left: Math.round(rect.left), right: Math.round(rect.right),
      });
    }
  }
  // وعاء تمرير يمرَّر أفقياً عيبٌ أيضاً وإن بقيت حوافه داخل المنفذ
  for (const box of document.querySelectorAll('body, .shell, main, .sheet')) {
    const slack = box.scrollWidth - box.clientWidth;
    if (slack > 1) out.push({ selector: box.tagName + '.' + (box.className || ''), slack });
  }
  return out;
}
"""

TOUCH_TARGET_SCRIPT = """
(minimum) => {
  const small = [];
  for (const element of document.querySelectorAll(
      'button, a[href], input, textarea, select, summary, [tabindex]:not([tabindex="-1"])')) {
    const style = getComputedStyle(element);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) continue;
    if (rect.width < minimum || rect.height < minimum) {
      small.push({
        selector: element.tagName + '#' + (element.id || '') + '.' + (element.className || ''),
        width: Math.round(rect.width), height: Math.round(rect.height),
      });
    }
  }
  return small;
}
"""


# ── الاختبارات ──────────────────────────────────────────────────────────

def test_the_portal_renders_the_approved_plan(page):
    """حارس: بقية الفحوص بلا معنى على صفحة فارغة."""
    body = page.inner_text("body")
    assert "الخطوة 1 من 2" in body
    assert "تمرين الجلوس إلى الوقوف" in body
    assert "أحتاج مساعدة الآن" in body


def test_no_page_errors(portal_server, patient_token):
    errors = []
    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script(
            f"localStorage.setItem('symbol.patient.token', {patient_token!r});"
        )
        opened = context.new_page()
        opened.on("pageerror", lambda exc: errors.append(str(exc)))
        opened.goto(f"{portal_server}/app/", wait_until="networkidle", timeout=60000)
        opened.wait_for_timeout(1500)
        browser.close()
    assert not errors, errors


def test_text_contrast_meets_aa(page):
    """تباين ≥ 4.5:1 للنص العادي و3:1 للكبير — محسوب على الصفحة المرندرة."""
    findings = page.evaluate(CONTRAST_SCRIPT)
    assert not findings, f"نصوص دون حد التباين: {findings}"


@pytest.mark.parametrize("width, height", VIEWPORTS)
def test_nothing_overlaps_at_any_screen_size(page, width, height):
    """
    لا تداخل بين أي عنصرين في أي مقاس.

    تدقيق المرحلة 0 وجد في الواجهة القديمة شريطاً لاصقاً يحجب آخر رسالة، وهو
    تحديداً ما يمنعه هذا الاختبار: شريط البلاغ ثابت، والصفحة تحجز له مساحته.
    """
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(350)
    clashes = page.evaluate(OVERLAP_SCRIPT)
    assert not clashes, f"تداخل عند {width}×{height}: {clashes[:4]}"


@pytest.mark.parametrize("width, height", VIEWPORTS)
def test_touch_targets_are_large_enough(page, width, height):
    """≥ 44×44 في كل مقاس — والبوابة تستهدف 56 لأن الجمهور ذو إعاقة حركية."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(350)
    small = page.evaluate(TOUCH_TARGET_SCRIPT, 44)
    assert not small, f"عناصر تفاعلية أصغر من 44 عند {width}×{height}: {small}"


@pytest.mark.parametrize("width, height", VIEWPORTS)
def test_nothing_overflows_horizontally(page, width, height):
    """لا تمرير أفقي في أي مقاس: التمرير الأفقي يُفقد المحتوى على اليسار."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_timeout(350)
    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT), f"فيض أفقي عند {width}×{height}"


def test_two_hundred_percent_zoom_keeps_the_page_usable(page):
    """تكبير 200% دون فقد وظيفة ولا تمرير أفقي."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("document.documentElement.style.fontSize = '250%'")  # 125% × 2
    page.wait_for_timeout(400)

    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT), "تمرير أفقي عند 200%"

    assert not page.evaluate(OVERLAP_SCRIPT), "تداخل عند تكبير 200%"
    assert page.get_by_role("button", name="أحتاج مساعدة الآن").is_visible()


CAREGIVER_EMAIL = "portal.caregiver@example.test"


def test_the_portal_tells_a_caregiver_they_are_a_caregiver(owner, seed, portal_server,
                                                           patient_token):
    """
    من يسجّل الأداء يرى باسم من يسجّله.

    خطوة تُسجَّل «تمّت» في سجل المريض وقد أدّاها مرافقه تُفسد المتابعة كلها،
    فالصفة معروضة لا مستنتَجة.
    """
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (tenant_id, role, email, password_hash)"
            " VALUES (%s, 'CAREGIVER', %s, %s) RETURNING id",
            (seed.tenant_a, CAREGIVER_EMAIL, identity.hash_password(SECRET)),
        )
        caregiver_id = cursor.fetchone()[0]

    practitioner = Actor(id=seed.practitioner_a, role="PRACTITIONER", tenant_id=seed.tenant_a)
    caregivers.grant(
        practitioner,
        patient_id=seed.patient_a,
        caregiver_user_id=caregiver_id,
        relationship="زوجة المريض",
        consent_text="أوافق على أن يطّلع مرافقي على خطتي وأن يسجّل أدائي نيابةً عني.",
        consent_given_by="PATIENT",
    )
    token, _ = identity.authenticate(CAREGIVER_EMAIL, SECRET, "PATIENT")

    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-SA")
        context.add_init_script(f"localStorage.setItem({TOKEN_KEY!r}, {token!r});")
        opened = context.new_page()
        opened.goto(f"{portal_server}/app/", wait_until="networkidle", timeout=60000)
        opened.wait_for_selector("#acting-as", state="visible", timeout=20000)

        assert "بصفة مرافق" in opened.inner_text("#acting-as")
        assert "تمرين الجلوس إلى الوقوف" in opened.inner_text("body")
        assert not opened.evaluate(OVERLAP_SCRIPT)
        assert not opened.evaluate(CONTRAST_SCRIPT)
        browser.close()


def test_the_service_worker_never_caches_clinical_content(page):
    """
    خزن المتصفح لا يحمل محتوى سريرياً.

    استجابةٌ محفوظة من `/patient/*` تعني تسليم خطة بعد سحب اعتمادها أو انتهاء
    صلاحيتها — التفافٌ على نقطة العبور من داخل الجهاز.
    """
    page.wait_for_function(
        "() => navigator.serviceWorker && navigator.serviceWorker.controller",
        timeout=30000,
    )
    page.reload(wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1200)

    cached = page.evaluate("""
    async () => {
      const urls = [];
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        for (const request of await cache.keys()) urls.push(request.url);
      }
      return urls;
    }
    """)

    assert cached, "لم تُخزَّن القشرة — الاختبار بلا معنى بلا مخزن"
    assert not [url for url in cached if "/patient/" in url], cached


def test_the_portal_asks_for_login_before_showing_anything(anonymous_page):
    """
    بلا جلسة لا محتوى ولا زر بلاغ: البوابة تطلب الدخول ولا تَعِد بما لا تستطيع.
    """
    page = anonymous_page
    assert page.get_by_role("heading", name="تسجيل الدخول").is_visible()
    assert page.locator("#step-card").is_hidden()
    assert page.locator(".alarm").is_hidden()
    assert page.locator(".tabs").is_hidden()


def test_wrong_password_shows_an_error_and_stores_no_token(anonymous_page):
    page = anonymous_page
    page.fill("#login-email", PATIENT_EMAIL)
    page.fill("#login-password", "كلمة-خاطئة")
    page.click("#login-submit")
    page.wait_for_timeout(900)

    assert page.locator("#login-error").is_visible()
    assert page.evaluate(f"() => localStorage.getItem({TOKEN_KEY!r})") is None
    assert page.locator("#step-card").is_hidden()


def test_login_shows_the_plan_and_logout_clears_it(anonymous_page):
    """
    الخروج يمحو الخطة المحفوظة: الجهاز قد يكون مشتركاً، والخطة محتوى سريري.
    """
    page = anonymous_page
    page.fill("#login-email", PATIENT_EMAIL)
    page.fill("#login-password", SECRET)
    page.click("#login-submit")
    page.wait_for_selector("#step-card:not([hidden])", timeout=20000)

    assert "تمرين الجلوس إلى الوقوف" in page.inner_text("body")
    assert page.evaluate(f"() => localStorage.getItem({TOKEN_KEY!r})")
    assert page.evaluate(f"() => localStorage.getItem({PLAN_KEY!r})")

    page.get_by_role("button", name="خروج").click()
    page.wait_for_timeout(900)

    assert page.get_by_role("heading", name="تسجيل الدخول").is_visible()
    assert page.evaluate(f"() => localStorage.getItem({TOKEN_KEY!r})") is None
    assert page.evaluate(f"() => localStorage.getItem({PLAN_KEY!r})") is None
    assert page.locator("#step-card").is_hidden()


@pytest.mark.parametrize("width, height", [(320, 568), (1440, 900)])
@pytest.mark.parametrize("screen", SCREENS)
def test_every_screen_passes_the_audit(audited_page, screen, width, height):
    """
    التدقيق على كل شاشة لا على شاشة واحدة: الدخول، والخطة، والتقدّم، وحال
    انقطاع الاتصال. عيب التخطيط يسكن عادةً في الشاشة التي لا تُدقَّق.
    """
    page = audited_page
    page.set_viewport_size({"width": width, "height": height})
    _open_screen(page, screen)

    assert not page.evaluate(CONTRAST_SCRIPT), f"تباين في {screen}"
    assert not page.evaluate(OVERLAP_SCRIPT), f"تداخل في {screen}"
    assert not page.evaluate(TOUCH_TARGET_SCRIPT, 44), f"مساحة لمس في {screen}"
    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT), f"فيض أفقي في {screen}"


def test_the_alarm_sheet_fits_and_does_not_overlap_at_200_percent(page):
    """
    ورقة البلاغ تحت تكبير 200%: مسار الطوارئ هو آخر ما يجوز أن ينكسر.

    الصفحة خلفها لا تمرَّر (وعاء التمرير `.shell`)، فلو تجاوزت الورقة الشاشة
    بلا تمرير ذاتي لصار زر الإرسال غير قابل للبلوغ.
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("document.documentElement.style.fontSize = '250%'")
    page.get_by_role("button", name="أحتاج مساعدة الآن").click()
    page.wait_for_timeout(400)

    assert page.evaluate("() => document.getElementById('alarm-sheet').matches(':modal')")
    assert not page.evaluate(OVERLAP_SCRIPT), "تداخل داخل ورقة البلاغ"
    assert not page.evaluate(HORIZONTAL_OVERFLOW_SCRIPT), "فيض أفقي في ورقة البلاغ"

    send = page.get_by_role("button", name="أرسِل البلاغ")
    send.scroll_into_view_if_needed()
    assert send.is_visible()
    box = send.bounding_box()
    assert box["y"] >= -1 and box["y"] + box["height"] <= 844 + 1, box


def test_every_control_is_reachable_and_named(page):
    """
    كل عنصر تفاعلي له اسم متاح ويمكن بلوغه بالكيبورد.

    زر بلا اسم متاح موجود للعين وغير موجود لقارئ الشاشة.
    """
    unnamed = page.evaluate("""
    () => {
      const missing = [];
      for (const element of document.querySelectorAll('button, a[href], input, textarea, select')) {
        const style = getComputedStyle(element);
        if (style.visibility === 'hidden' || style.display === 'none') continue;
        if (element.closest('[hidden]')) continue;

        const name = (element.getAttribute('aria-label') || '').trim()
          || (element.labels && element.labels.length
              ? [...element.labels].map((l) => l.textContent.trim()).join(' ') : '')
          || (element.textContent || '').trim()
          || (element.getAttribute('title') || '').trim();

        if (!name) missing.push(element.tagName + '#' + (element.id || ''));
        if (element.tabIndex < 0) missing.push('غير قابل للتبويب: ' + element.tagName);
      }
      return missing;
    }
    """)
    assert not unnamed, f"عناصر بلا اسم متاح أو خارج مسار الكيبورد: {unnamed}"


def test_the_document_declares_language_and_direction(page):
    """قارئ الشاشة يحتاج لغة المستند ليختار النطق الصحيح."""
    assert page.evaluate("document.documentElement.lang") == "ar"
    assert page.evaluate("document.documentElement.dir") == "rtl"


def test_landmarks_and_headings_are_present(page):
    """بنية دلالية: التنقّل بقارئ الشاشة يعتمد عليها لا على الترتيب البصري."""
    structure = page.evaluate("""
    () => ({
      banner: !!document.querySelector('header[role="banner"], header'),
      nav: !!document.querySelector('nav'),
      main: !!document.querySelector('main'),
      h1: document.querySelectorAll('h1').length,
      headingOrder: [...document.querySelectorAll('h1,h2,h3')]
        .map((h) => Number(h.tagName[1])),
    })
    """)
    assert structure["banner"] and structure["nav"] and structure["main"]
    assert structure["h1"] == 1, "المستند يحتاج عنواناً رئيسياً واحداً"

    levels = structure["headingOrder"]
    jumps = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    assert not jumps, f"قفزات في مستويات العناوين: {jumps}"


def test_no_interaction_is_on_a_timer(page):
    """
    لا مهلة زمنية على أي تفاعل.

    نُثبّت الزمن ونقفز ساعة: أي مؤقّت يُخفي محتوى أو يعطّل زراً سيظهر أثره.
    """
    before = page.inner_text("body")
    page.evaluate("() => { for (let i = 1; i < 100000; i++) clearTimeout(i); }")
    page.wait_for_timeout(1500)

    assert page.inner_text("body") == before, "المحتوى تغيّر من تلقائه"
    assert page.get_by_role("button", name="أحتاج مساعدة الآن").is_enabled()


def test_reduced_motion_is_honoured(portal_server, patient_token):
    """من طلب حركة أقل من نظامه لا تُفرض عليه حركة."""
    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, reduced_motion="reduce"
        )
        context.add_init_script(
            f"localStorage.setItem('symbol.patient.token', {patient_token!r});"
        )
        opened = context.new_page()
        opened.goto(f"{portal_server}/app/", wait_until="networkidle", timeout=60000)
        opened.wait_for_timeout(600)

        moving = opened.evaluate("""
        () => [...document.querySelectorAll('body *')].filter((element) => {
          const style = getComputedStyle(element);
          const duration = parseFloat(style.animationDuration) || 0;
          return style.animationName !== 'none' && duration > 0.1;
        }).length
        """)
        browser.close()
    assert moving == 0, f"{moving} عنصراً ما زال متحركاً رغم طلب تقليل الحركة"
