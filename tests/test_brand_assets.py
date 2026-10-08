"""
أصول العلامة — سلامتها لا مظهرها
==================================
المظهر يُدقَّق في المتصفح (`test_portal_accessibility`). ما هنا أضيق وأهمّ:
أن تبقى الملفات التي تقوم عليها الواجهتان موجودةً ومتطابقة ومحلّية.

كل اختبار هنا يقابل طريقةً صامتة للانهيار: ملفٌّ يُشار إليه ولا يوجد فيسقط
الخطّ إلى بديل النظام، أو نسختان تفترقان فيختلف الخطّ بين الواجهتين، أو
رابطٌ خارجي يعود فيتسرّب عنوان المريض ويغيب الخطّ دون اتصال.

لا قاعدة بيانات ولا متصفّح: قراءة ملفات فقط.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "portal"
STATIC = ROOT / "static"

#: أول إصدار من Streamlit يعرف `theme.headingFont` ويوثّق `[[theme.fontFaces]]`.
#: المصدر: ملاحظات الإصدار 1.44.0 (25 مارس 2025) — «Introducing advanced
#: theming options… Change the fonts, colors, and roundness of your app
#: without CSS». وفي حزمة 1.43.2 نفسها `fontFaces` خيارٌ مخفيّ ولا
#: `headingFont` أصلاً.
THEME_FONTS_SINCE = Version("1.44.0")

#: الأوزان التي يحتاجها برنامج الممارس، وهي المنسوخة مرتين.
SHARED_FONTS = ("amiri-arabic-400.woff2", "amiri-arabic-700.woff2")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── لا طرف ثالث ─────────────────────────────────────────────────────────
def test_no_font_is_fetched_from_a_third_party():
    """
    الخطّ محلّي في الواجهتين.

    رابطٌ خارجي يفعل شيئين: يُرسل عنوان جهاز المريض وبصمة متصفّحه إلى غيرنا
    في كل فتحة، ويُغيّب الخطّ حين ينقطع الاتصال — على الشاشة نفسها التي
    يقرأ منها تعليمات تمرينه.
    """
    offenders = []
    for path in [ROOT / "app.py", *PORTAL.rglob("*.css"), *PORTAL.rglob("*.html"),
                 *PORTAL.rglob("*.js"), *(ROOT / ".streamlit").rglob("*.toml")]:
        source = path.read_text(encoding="utf-8", errors="ignore")
        for line in source.splitlines():
            if "fonts.googleapis" in line or "fonts.gstatic" in line:
                # التعليقات تشرح ما حُذف؛ الشيفرة وحدها هي المقصودة
                if line.lstrip().startswith(("*", "#", "//", "/*")):
                    continue
                offenders.append(f"{path.relative_to(ROOT)}: {line.strip()[:60]}")
    assert not offenders, f"طلب خطّ خارجي: {offenders}"


# ── النسختان لا تفترقان ─────────────────────────────────────────────────
@pytest.mark.parametrize("name", SHARED_FONTS)
def test_the_two_font_copies_match(name):
    """
    `portal/fonts` و`static/fonts` نسختان من الملفّ نفسه.

    وصلةٌ رمزية كانت أنظف، لكن المعالج الساكن في Streamlit يحلّ المسار
    الحقيقي ويرفض ما يخرج عن جذره بـ400. فالنسخ ضرورة، وهذا الاختبار هو
    ما يمنع أن يُحدَّث أحدهما ويُنسى الآخر — فيقرأ المريض بخطٍّ ويقرأ
    الممارس بغيره.
    """
    portal_copy, static_copy = PORTAL / "fonts" / name, STATIC / "fonts" / name
    assert portal_copy.exists(), f"مفقود: {portal_copy.relative_to(ROOT)}"
    assert static_copy.exists(), f"مفقود: {static_copy.relative_to(ROOT)}"
    assert _digest(portal_copy) == _digest(static_copy), f"النسختان افترقتا: {name}"


# ── خطّ برنامج الممارس يحتاج إصداراً يفهم إعلانه ─────────────────────────
def test_the_streamlit_floor_understands_the_theme_font():
    """
    الخطّ في برنامج الممارس تعلنه السمة وحدها، ولا `@font-face` احتياطية في
    `CUSTOM_CSS`. إصدارٌ أقدم من 1.44 يتجاهل إعلانها بلا خطأ، فيُرسَم
    التطبيق بخطّ بديل — ولذلك لا يجوز أن تسمح المتطلبات بتثبيته.
    """
    theme = tomllib.loads(
        (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    assert "fontFaces" in theme and "headingFont" in theme, "السمة لم تعد تعلن الخطّ"

    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    requirement = next(Requirement(line) for line in lines
                       if re.match(r"streamlit\b", line.strip()))
    floors = [Version(spec.version) for spec in requirement.specifier
              if spec.operator in (">=", ">", "~=", "==")]
    assert floors, f"لا حدّ أدنى لـStreamlit: {requirement}"
    assert max(floors) >= THEME_FONTS_SINCE, (
        f"{requirement} يسمح بإصدار لا يفهم theme.fontFaces/headingFont")
    assert requirement.specifier.contains(THEME_FONTS_SINCE), requirement


def test_the_font_licence_travels_with_the_files():
    """Amiri تحت SIL OFL 1.1، وهي تشترط إرفاق نصّ الرخصة مع الملفات."""
    for folder in (PORTAL / "fonts", STATIC / "fonts"):
        licence = folder / "OFL.txt"
        assert licence.exists(), f"رخصة مفقودة في {folder.relative_to(ROOT)}"
        assert "SIL Open Font License" in licence.read_text(encoding="utf-8")


# ── كل ما يُشار إليه موجود ──────────────────────────────────────────────
def test_every_asset_the_portal_references_exists():
    """
    مرجعٌ مكسور لا يرفع خطأ — يسقط بصمت إلى بديل النظام.

    ولذلك لا يكشفه إلا فحصٌ كهذا أو عينٌ تنظر إلى الشاشة في اللحظة
    المناسبة.
    """
    missing = []
    for source in (PORTAL / "styles.css", PORTAL / "index.html"):
        text = source.read_text(encoding="utf-8")
        refs = re.findall(r"""url\(['"]([^'")]+)['"]\)""", text)
        refs += re.findall(r'(?:href|src)="([^"]+\.(?:svg|png|css|js|webmanifest))"', text)
        for ref in refs:
            if ref.startswith(("http", "data:", "#")):
                continue
            if not (PORTAL / ref).exists():
                missing.append(f"{source.name} → {ref}")
    assert not missing, f"مراجع مكسورة: {missing}"


def test_every_test_a_comment_cites_exists():
    """
    تعليقٌ يقول «يختبره `test_…`» وعدٌ بأن CI يحرس القرار. اسمٌ لا يوجد —
    كما كان `test_the_portal_survives_250_percent_text` في `styles.css` —
    وعدٌ لا يحرسه شيء.
    """
    defined = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        defined.update(re.findall(r"^\s*def (test_\w+)", path.read_text(encoding="utf-8"), re.M))

    missing = []
    for path in [ROOT / "app.py", *PORTAL.rglob("*.css"), *PORTAL.rglob("*.html"),
                 *PORTAL.rglob("*.js"), *(ROOT / ".streamlit").rglob("*.toml")]:
        for name in re.findall(r"`(test_\w+)`", path.read_text(encoding="utf-8")):
            if name not in defined:
                missing.append(f"{path.relative_to(ROOT)} → {name}")
    assert not missing, f"تعليقات تستشهد باختبار غير موجود: {missing}"


def test_the_manifest_icons_exist():
    manifest = json.loads((PORTAL / "manifest.webmanifest").read_text(encoding="utf-8"))
    missing = [i["src"] for i in manifest["icons"] if not (PORTAL / i["src"]).exists()]
    assert not missing, f"أيقونات معلنة ومفقودة: {missing}"


def test_the_service_worker_caches_the_font():
    """
    الخطّ ضمن قشرة عامل الخدمة.

    دونه تعمل البوابة دون اتصال بخطّ النظام لا بخطّها — وهو بالضبط ما
    اختير الاستضافة الذاتية لتفاديه، فيصير القرار كلّه بلا أثر.
    """
    worker = (PORTAL / "sw.js").read_text(encoding="utf-8")
    for name in (PORTAL / "fonts").glob("*.woff2"):
        assert f"fonts/{name.name}" in worker, f"خارج القشرة: {name.name}"
