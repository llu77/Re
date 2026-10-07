"""
الفصل عن المنصّة — في الاتجاهين
================================
قائمة مستخدمي هذا التطبيق معلومةٌ صحّية: من فيها يعمل بعينيه. فالفصل هنا
ضمانةُ خصوصية لا ترتيبُ ملفات: لا يستورد التطبيق شيئاً من المنصّة السريرية،
ولا تستورد منه، ولا يذكر أحدهما متغيّرات الآخر ولا قاعدته ولا مساراته.

قائمة وحدات المنصّة تُحسب من جذر المستودع عند كل تشغيل — كل ملف `*.py` في
الجذر وكل مجلدٍ في أعلاه عدا `eyework` — فحزمةٌ جديدة في المنصّة مشمولةٌ
تلقائياً، ولا تحتاج تحديث قائمة.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "eyework"
_SKIP = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


def _files(base: Path, suffixes: tuple[str, ...]):
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix in suffixes and not any(part in _SKIP for part in path.parts):
            yield path


def _platform_modules() -> set[str]:
    modules = {path.stem for path in ROOT.glob("*.py")}
    modules |= {path.name for path in ROOT.iterdir()
                if path.is_dir() and path.name != "eyework" and not path.name.startswith(".")
                and path.name not in _SKIP}
    return modules


def _imports(tree: ast.AST) -> list[tuple[str, int, int]]:
    """(الوحدة، السطر، مستوى الاستيراد النسبي)."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.lineno, 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.lineno, node.level))
    return found


def test_eyework_imports_nothing_from_the_platform():
    platform = _platform_modules()
    assert {"core", "api", "portal", "migrations", "tools"} <= platform  # حارس: القائمة ليست فارغة
    offenders = []
    for path in _files(APP, (".py",)):
        for module, line, level in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            top = module.split(".")[0]
            if level == 0 and top in platform:
                offenders.append(f"{path.relative_to(ROOT)}:{line} → {module}")
            # استيرادٌ نسبي يصعد خارج الحزمة
            depth = len(path.relative_to(APP).parts) - 1
            if level > depth + 1:
                offenders.append(f"{path.relative_to(ROOT)}:{line} → استيرادٌ نسبي خارج eyework")
    assert not offenders, f"التطبيق يستورد من المنصّة: {offenders}"


def test_the_platform_never_imports_or_mentions_eyework():
    offenders = []
    targets = [*ROOT.glob("*.py"), *ROOT.glob("requirements*.txt"), ROOT / ".github" / "workflows" / "ci.yml"]
    for name in _platform_modules():
        base = ROOT / name
        if base.is_dir():
            targets += list(_files(base, (".py", ".js", ".html", ".css", ".sql", ".sh", ".toml", ".yml")))
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            for module, line, _ in _imports(ast.parse(text)):
                if module.split(".")[0] == "eyework":
                    offenders.append(f"{path.relative_to(ROOT)}:{line} يستورد eyework")
        if re.search(r"\beyework\b|EYEWORK_", text):
            offenders.append(f"{path.relative_to(ROOT)} يذكر eyework")
    assert not offenders, f"المنصّة تعرف التطبيق: {offenders}"


_BANNED = re.compile(
    r"SYMBOL_|symbol_rehab|app_patient|app_practitioner|/patient/|/practitioner/|\.\./portal"
    r"|^ANTHROPIC_API_KEY$"
)


def _code_strings(tree: ast.Module) -> list[tuple[str, int]]:
    """السلاسل الحرفية في الشيفرة، بلا سلاسل التوثيق: الشرح يذكر ما يُمنع، والشيفرة لا."""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [(node.value, node.lineno) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings]


def test_eyework_never_names_the_platform_database_or_paths():
    """
    لا متغيّرات المنصّة ولا قاعدتها ولا أدوارها ولا مساراتها، ولا مفتاح
    `ANTHROPIC_API_KEY` العام — في شيفرة الإنتاج. الاختبارات تسمّي أدوار
    المنصّة لتثبت أنها لا تتصل، فهي خارج هذا الفحص.
    """
    offenders = []
    for path in _files(APP, (".py",)):
        if "tests" in path.relative_to(APP).parts:
            continue
        for value, line in _code_strings(ast.parse(path.read_text(encoding="utf-8"))):
            if _BANNED.search(value):
                offenders.append(f"{path.relative_to(ROOT)}:{line} {value[:40]}")
    for path in _files(APP / "static", (".js", ".html", ".css", ".webmanifest")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"SYMBOL_|symbol_rehab|/patient/|/practitioner/|\.\./portal|ANTHROPIC", text):
            offenders.append(f"{path.relative_to(ROOT)} {match.group(0)}")
    for path in _files(APP / "migrations", (".sql",)):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"SYMBOL_|symbol_rehab|app_patient|app_practitioner", text):
            offenders.append(f"{path.relative_to(ROOT)} {match.group(0)}")
    assert not offenders, f"التطبيق يذكر المنصّة: {offenders}"


def test_no_symlink_leaves_the_app():
    escaping = [str(p.relative_to(ROOT)) for p in APP.rglob("*")
                if p.is_symlink() and APP not in p.resolve().parents]
    assert not escaping, f"وصلاتٌ رمزية تخرج من التطبيق: {escaping}"


def test_no_asset_is_the_platform_brand():
    """أيقونات المنصّة وشعارها لا تظهر هنا: الشاشة الرئيسية لا تربط التطبيقين."""
    platform_assets = {p.read_bytes() for p in (ROOT / "portal").glob("*") if p.suffix in (".png", ".svg")}
    shared = [str(p.relative_to(ROOT)) for p in _files(APP / "static", (".png", ".svg"))
              if p.read_bytes() in platform_assets]
    assert not shared, f"أصولٌ من علامة المنصّة: {shared}"


def test_user_visible_names_reveal_nothing():
    """الاسم والعنوان والأيقونة لا تذكر النظر ولا العين ولا الإعاقة ولا التأهيل."""
    revealing = re.compile(r"عين|نظر|إعاقة|اعاقة|تأهيل|مريض|eye|gaze|rehab|disab", re.IGNORECASE)
    import json

    for manifest in (APP / "static" / "manifest.webmanifest", APP / "static" / "probe" / "manifest.webmanifest"):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for key in ("name", "short_name"):
            assert not revealing.search(data[key]), f"{manifest.name}:{key} = {data[key]}"
    for page in (APP / "static" / "index.html", APP / "static" / "probe" / "index.html"):
        title = re.search(r"<title>(.*?)</title>", page.read_text(encoding="utf-8")).group(1)
        assert not revealing.search(title), f"{page.name}: {title}"
