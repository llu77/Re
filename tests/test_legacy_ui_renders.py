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
