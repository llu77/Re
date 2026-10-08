"""
الواجهة القديمة تُرسَم فعلاً
=============================
`AppTest` يشغّل سكربت Streamlit ويفحص شجرة عناصره، ولا يُحمّل CSS ولا يرسم
شيئاً. فالفحص الوظيفي وحده يمرّ على صفحة بيضاء تماماً.

وهذا ما حدث: سطران في `app.py` جعلا `.stApp` صندوقاً قاصّاً بارتفاع صفر،
فابتلع الواجهة كلها. بقي الاختبار الوظيفي أخضر، والصفحة في المتصفح لا تحمل
حرفاً واحداً ولا زرّاً قابلاً للنقر.

الاختبار هنا يقيس ما يراه المستخدم: ارتفاعٌ مرسوم، ونصّ مرئي، وزرٌّ يقبل
النقر فعلاً — والنقر هو اختبار إصابة المؤشر نفسه.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

playwright_api = pytest.importorskip("playwright.sync_api", reason="playwright غير مثبّت")
pytest.importorskip("streamlit", reason="streamlit غير مثبّت")

if not Path(CHROMIUM).exists():  # pragma: no cover - يعتمد على البيئة
    pytest.skip("متصفح Chromium غير متاح", allow_module_level=True)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def streamlit_server():
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env={**os.environ},
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        subprocess.run(
            ["curl", "-sf", "--retry", "60", "--retry-delay", "1",
             "--retry-connrefused", "--retry-all-errors", "-o", "/dev/null", f"{base}/"],
            check=True, timeout=120,
        )
        yield base
    finally:
        process.terminate()
        process.wait(timeout=20)


@pytest.fixture
def page(streamlit_server):
    with playwright_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ar-SA")
        opened = context.new_page()
        opened.goto(streamlit_server, wait_until="networkidle", timeout=90000)
        opened.wait_for_timeout(3500)
        yield opened
        browser.close()


def test_the_app_shell_has_a_painted_height(page):
    """`.stApp` بارتفاع صفر يعني أن كل ما تحته مقصوص — وصفحة بيضاء."""
    measured = page.evaluate("""
    () => {
      const app = document.querySelector('.stApp');
      const style = getComputedStyle(app);
      return {
        height: app.getBoundingClientRect().height,
        position: style.position,
      };
    }
    """)
    assert measured["height"] > 100, measured
    # Streamlit يضع `.stApp` مُطلَقاً بـ`inset: 0`؛ تغييره يُسقط الارتفاع
    assert measured["position"] == "absolute", measured


def test_the_page_shows_its_content(page):
    """
    حارس للنصّ لا للرسم.

    `inner_text` يُعيد نصّ عنصر مقصوص أيضاً، فهذا الفحص وحده كان يمرّ على
    الصفحة البيضاء. الرسم يثبته الاختباران الآخران: الارتفاع، وإصابة المؤشر.
    """
    body = page.inner_text("body")
    assert "سجل المرضى" in body
    assert "إنشاء ملف مريض جديد" in body


def test_the_primary_button_actually_receives_the_pointer(page):
    """
    النقر هو الاختبار: Playwright يرفض النقر إن لم يصل المؤشر إلى العنصر.

    قبل الإصلاح كان `document.elementFromPoint` عند مركز الزرّ يُعيد `HTML`،
    لأن الصندوق القاصّ بارتفاع صفر أخرج كل شيء من اختبار الإصابة.
    """
    button = page.get_by_role("button", name="إنشاء ملف مريض جديد")
    box = button.bounding_box()
    assert box, "الزرّ بلا صندوق"

    hit = page.evaluate(
        "([x, y]) => { const e = document.elementFromPoint(x, y);"
        " return e ? e.tagName : null; }",
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
    )
    assert hit != "HTML", "لا شيء قابل للإصابة عند مركز الزرّ"

    button.click(timeout=10000)
    page.wait_for_timeout(2500)
    assert "اسم المريض" in page.inner_text("body")


def test_the_page_does_not_scroll_sideways(page):
    """الطبقتان الزخرفيتان `fixed` ولا تُنشئان فيضاً أفقياً."""
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"تمرير أفقي: {overflow}px"


def _open_the_new_patient_form(page):
    """النموذج داخل `st.expander`، ورأسه يحمل أيقونة السهم."""
    page.get_by_role("button", name="إنشاء ملف مريض جديد").click(timeout=10000)
    page.wait_for_selector('[data-testid="stExpander"] summary', timeout=20000)
    page.evaluate("document.fonts.ready")


#: Streamlit يرسم أيقوناته نصّاً (`keyboard_arrow_down`) يحوّله خطّ
#: Material Symbols إلى رمز واحد بالربط. عرض النصّ المرسوم هو الشاهد: رمزٌ
#: واحد عرضه نحو 1em، والنصّ نفسه بخطّ آخر عرضه أضعاف ذلك.
ICON_SCRIPT = """
() => [...document.querySelectorAll('[data-testid="stIconMaterial"]')].map(icon => {
  const style = getComputedStyle(icon);
  const range = document.createRange();
  range.selectNodeContents(icon);
  return {
    name: icon.textContent,
    family: style.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
    fontSize: parseFloat(style.fontSize),
    inkWidth: range.getBoundingClientRect().width,
    inExpander: !!icon.closest('[data-testid="stExpander"] summary'),
    inSidebar: !!icon.closest('[data-testid="stSidebar"]'),
  };
})
"""


def test_material_icons_render_as_icons_not_as_their_names(page):
    """
    `font-family: Amiri !important` على كل صنف `st-emotion-cache-…` أصاب
    أيقونات Streamlit أيضاً: رأس كل `st.expander` كتب «keyboard_ar…» فوق
    تسميته، وزرّ طيّ الشريط كتب «keyboard_double_arrow_left».
    """
    _open_the_new_patient_form(page)
    icons = page.evaluate(ICON_SCRIPT)

    # فحصٌ بلا أيقونات يمرّ على كل شيء: سهم المُوسِّع وزرّ الشريط شاهدان لازمان
    assert any(i["inExpander"] for i in icons), icons
    assert any(i["inSidebar"] for i in icons), icons

    for icon in icons:
        assert icon["family"].startswith("Material Symbols"), icon
        assert icon["inkWidth"] <= icon["fontSize"] * 1.5, f"رُسم اسماً لا رمزاً: {icon}"


def test_the_sidebar_content_stays_inside_the_sidebar(page):
    """
    اسم الأيقونة المرسوم نصّاً عريضٌ، فدفع محتوى الشريط كله 10px خارج حافة
    الشاشة. كل عنصر مرئي في محتوى الشريط يجب أن يقع بين حافتيه.

    مقبض تغيير العرض (`stSidebarResizeHandle`) شقيقٌ للمحتوى لا جزءٌ منه،
    ويقع على الحدّ عمداً — فلا يُقاس هنا.
    """
    escaped = page.evaluate("""
    () => {
      const sidebar = document.querySelector('[data-testid="stSidebar"]');
      const content = sidebar.querySelector('[data-testid="stSidebarContent"]');
      const edge = sidebar.getBoundingClientRect();
      const right = Math.min(edge.right, window.innerWidth);
      const out = [];
      for (const element of [content, ...content.querySelectorAll('*')]) {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) continue;
        if (rect.left < edge.left - 1 || rect.right > right + 1) {
          out.push({
            testid: element.dataset.testid || '', cls: String(element.className).slice(0, 40),
            left: Math.round(rect.left), right: Math.round(rect.right),
          });
        }
      }
      return out;
    }
    """)
    assert not escaped, f"عناصر خارج الشريط: {escaped[:5]}"


def test_arabic_text_is_set_in_amiri(page):
    """
    الخطّ من سمة Streamlit (`.streamlit/config.toml`) لا من قاعدة تفرضه على
    كل صنف: كل نصّ عربي مرئي يُرسَم بـAmiri، وملفّه حُمِّل فعلاً لا سقط
    إلى بديل النظام.
    """
    _open_the_new_patient_form(page)
    measured = page.evaluate("""
    () => {
      const arabic = /[\\u0600-\\u06FF]/;
      const walker = document.createTreeWalker(document.querySelector('.stApp'),
                                               NodeFilter.SHOW_TEXT);
      const elsewhere = [];
      let checked = 0;
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!arabic.test(node.textContent)) continue;
        const parent = node.parentElement;
        if (!parent || parent.closest('style, script')) continue;
        const rect = parent.getBoundingClientRect();
        if (!rect.width || !rect.height) continue;
        checked += 1;
        const first = getComputedStyle(parent).fontFamily.split(',')[0]
          .replace(/["']/g, '').trim();
        if (first !== 'Amiri') {
          elsewhere.push({ text: node.textContent.trim().slice(0, 30), font: first });
        }
      }
      const loaded = [...document.fonts].some(
        face => face.family.replace(/["']/g, '') === 'Amiri' && face.status === 'loaded');
      return { checked, elsewhere, loaded };
    }
    """)
    assert measured["checked"] > 20, measured
    assert not measured["elsewhere"], measured["elsewhere"][:5]
    assert measured["loaded"], "ملفّ Amiri لم يُحمَّل"
