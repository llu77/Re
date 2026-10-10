"""
قواعد الشيفرة
=============
كل قاعدةٍ هنا تجعل سؤالاً واحداً يُجاب بقراءة ملفٍّ واحد:

  • ما الذي يغادر النظام؟ — `model_gateway.py` وحده يستورد `anthropic`، ولا
    مكتبة شبكةٍ أخرى في شيفرة الإنتاج.
  • من أين يأتي الوقت؟ — لا ساعة حائطٍ في بايثون إطلاقاً؛ `clock.py` وحده
    يقرأ الساعة الرتيبة.
  • من أين يأتي SQL؟ — نصٌّ ثابت يُمرَّر حرفياً، لا يُركَّب بدمج.
  • ماذا تعرف الواجهة؟ — موضعٌ واحد يتصل بالشبكة، ولا مؤقّت ولا تخزين ولا
    مرور مؤشر.
  • ماذا يعرف النموذج؟ — `CopyRequest` بحقوله الخمسة، ولا حقل هوية.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "eyework"
STATIC = APP / "static"


def _production_python():
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(APP)
        if "tests" in relative.parts or "__pycache__" in relative.parts:
            continue
        yield path


def _rel(path: Path) -> str:
    return path.relative_to(APP).as_posix()


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            # `from eyework import db` يستورد الوحدة eyework.db لا اسماً فيها.
            modules |= {f"{node.module}.{alias.name}" for alias in node.names}
    return modules


def test_the_import_scanner_sees_modules_imported_from_a_package(tmp_path):
    source = tmp_path / "m.py"
    source.write_text("from eyework import db\nfrom eyework.tests import fakes\nimport psycopg.rows\n",
                      encoding="utf-8")
    assert {"eyework.db", "eyework.tests.fakes", "psycopg.rows"} <= _imports(source)


def _tops(path: Path) -> set[str]:
    return {module.split(".")[0] for module in _imports(path)}


# ── الحدود الخارجية ─────────────────────────────────────────────────────
NETWORK = {"requests", "urllib", "urllib3", "httpx", "aiohttp", "socket", "http", "ftplib", "smtplib"}


def test_only_the_model_gateway_speaks_to_the_model():
    """كاتب النصّ يستورد العميل وتصنيف الأخطاء من البوّابة، ولا يستورد المكتبة بنفسه."""
    importers = sorted(_rel(p) for p in _production_python() if "anthropic" in _tops(p))
    assert importers == ["model_gateway.py"]


def test_no_other_network_library_in_production_code():
    offenders = {_rel(p): sorted(_tops(p) & NETWORK) for p in _production_python() if _tops(p) & NETWORK}
    assert not offenders, f"اتصالٌ خارجي خارج كاتب النصّ: {offenders}"


def test_only_the_passkey_module_verifies_passkeys():
    """
    التحقّق من مفاتيح المرور في مكتبةٍ واحدة مثبّتة وفي وحدةٍ واحدة: لا تحليلٌ
    ثانٍ لـCBOR أو COSE يقبل ما ترفضه المكتبة.
    """
    importers = sorted(_rel(p) for p in _production_python() if _tops(p) & {"webauthn", "cbor2"})
    assert importers == ["passkeys.py"]


def test_only_the_image_module_decodes_images():
    """`scripts/make_icons.py` يرسم الأيقونات وقت البناء ولا يفكّ صورة مستخدم."""
    importers = sorted(_rel(p) for p in _production_python() if "PIL" in _tops(p))
    assert importers == ["images.py", "scripts/make_icons.py"]


#: من يستورد psycopg مباشرةً، بالضبط: `db.py` يفتح الجلسات، و`admin.py` و`migrations/run.py`
#: بدور المالك، و`campaigns.py` و`reviewer.py` و`inventory.py` و`support.py` يترجمون أخطاء القيود، و`web/app.py` يُنشئ
#: التجمّع ويترجم أخطاءه. سائر الخدمات (`auth` و`passkeys` والمساعد) تصل القاعدة عبر
#: `eyework.db` وحده؛ وقاعدة المسارات في `test_web_routes_never_touch_the_database_directly`.
DATABASE_ALLOWED = {"db.py", "admin.py", "migrations/run.py", "campaigns.py", "web/app.py", "reviewer.py", "inventory.py",
                    "support.py"}


def test_database_access_is_confined():
    importers = {_rel(p) for p in _production_python() if "psycopg" in _tops(p) or "psycopg_pool" in _tops(p)}
    assert importers == DATABASE_ALLOWED, f"مستوردو psycopg تغيّروا: {importers ^ DATABASE_ALLOWED}"


def test_web_routes_never_touch_the_database_directly():
    for path in (APP / "web").glob("*.py"):
        if path.name == "app.py":
            continue
        modules = _imports(path)
        assert "eyework.db" not in modules and not any(m.startswith("psycopg") for m in modules), path.name


PURE = ("states.py", "money.py", "arabic_numbers.py", "copy_rules.py", "prompt.py", "passwords.py",
        "clock.py", "rate_limit.py", "professions.py", "terms.py", "ui_size.py", "service_errors.py",
        "prompt_kit.py", "ai_limits.py", "ai_text.py", "redact.py", "grounding.py", "reviewer_prompt.py",
        "assistant_prompt.py", "ai_log.py", "inventory_rules.py", "inventory_flags.py", "inventory_prompt.py")
IMPURE = {"fastapi", "starlette", "psycopg", "psycopg_pool", "anthropic", "PIL"}


@pytest.mark.parametrize("name", PURE)
def test_pure_modules_stay_pure(name):
    path = APP / name
    assert not (_tops(path) & IMPURE), f"{name}: {_tops(path) & IMPURE}"
    assert not {m for m in _imports(path) if m.startswith(("eyework.db", "eyework.web"))}


# ── الوقت ───────────────────────────────────────────────────────────────
_WALL_CLOCK = {("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"), ("date", "today"),
               ("time", "time"), ("time", "time_ns"), ("time", "localtime"), ("time", "gmtime")}


def _clock_calls(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", None)
            if (name, node.func.attr) in _WALL_CLOCK or (name, node.func.attr) == ("time", "monotonic"):
                found.append(f"{name}.{node.func.attr} [{node.lineno}]")
    return found


def test_python_never_reads_the_wall_clock():
    """كل وقتٍ يُحفظ تكتبه القاعدة؛ والساعة الرتيبة في clock.py وحده."""
    offenders = {}
    for path in _production_python():
        calls = _clock_calls(ast.parse(path.read_text(encoding="utf-8")))
        if _rel(path) == "clock.py":
            calls = [c for c in calls if not c.startswith("time.monotonic")]
        if calls:
            offenders[_rel(path)] = calls
    assert not offenders, f"قراءةٌ للساعة: {offenders}"


# ── SQL ─────────────────────────────────────────────────────────────────
def _built_sql(tree: ast.AST) -> list[str]:
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in {"execute", "executemany"} and node.args:
            query = node.args[0]
            if not isinstance(query, (ast.Constant, ast.Name, ast.Attribute)):
                offenders.append(f"{type(query).__name__} في السطر {node.lineno}")
            elif isinstance(query, ast.Constant) and not isinstance(query.value, str):
                offenders.append(f"ثابتٌ غير نصّي في السطر {node.lineno}")
    return offenders


def test_sql_is_never_built_by_string_concatenation():
    offenders = {}
    for path in _production_python():
        found = _built_sql(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            offenders[_rel(path)] = found
    assert not offenders, f"SQL مُركَّب: {offenders}"


def test_sql_constants_are_never_formatted():
    """الثوابت نفسها لا تُبنى بـf-string ولا بـformat ولا بدمج."""
    offenders = []
    for path in _production_python():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id.startswith("_") and t.id.isupper() for t in node.targets
            ):
                if isinstance(node.value, (ast.JoinedStr, ast.BinOp)) or (
                    isinstance(node.value, ast.Call) and getattr(node.value.func, "attr", "") == "format"
                ):
                    text = ast.unparse(node.value)
                    if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", text):
                        offenders.append(f"{_rel(path)}:{node.lineno}")
    assert not offenders, f"ثابت SQL مُركَّب: {offenders}"


# ── ما يعرفه النموذج ───────────────────────────────────────────────────
def test_the_model_request_has_no_identity_fields():
    from eyework.prompt import CopyRequest

    fields = {field.name for field in dataclasses.fields(CopyRequest)}
    assert fields == {"jpeg", "seller_note", "previous", "presets", "edit_note"}


# ── ما لم يكتمل ─────────────────────────────────────────────────────────
_UNFINISHED = re.compile(r"\b(TODO|FIXME|XXX|HACK|lorem)\b|\bplaceholder\s*=", re.IGNORECASE)


def test_nothing_unfinished_in_the_production_path():
    offenders = []
    for path in [*_production_python(), *STATIC.rglob("*.js"), *STATIC.rglob("*.html"),
                 *STATIC.rglob("*.css"), *(APP / "migrations").glob("*.sql")]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _UNFINISHED.search(line):
                offenders.append(f"{_rel(path)}:{number}")
    assert not offenders, f"علاماتُ عملٍ لم يكتمل: {offenders}"


def test_fakes_are_only_imported_by_tests():
    importers = [_rel(p) for p in _production_python() if any("fakes" in m for m in _imports(p))]
    assert not importers, f"الكاتب المصطنع في مسار الإنتاج: {importers}"


def test_production_imports_nothing_from_the_tests():
    """الجهاز المصطنع يوقّع بأيّ أصلٍ وأيّ عدّاد: في مسار الإنتاج يصير مفتاحاً لكل حساب."""
    importers = [_rel(p) for p in _production_python()
                 if any(m == "eyework.tests" or m.startswith("eyework.tests.") for m in _imports(p))]
    assert not importers, f"شيفرة الاختبار في مسار الإنتاج: {importers}"


# ── الواجهة ─────────────────────────────────────────────────────────────
def _js(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _code(js: str) -> str:
    """الشيفرة بلا تعليقات: التعليق يشرح ما يُمنع ولا يفعله."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", js)


def test_the_app_has_a_single_network_call_site():
    code = _code(_js("app.js"))
    assert len(re.findall(r"\bfetch\(", code)) == 1
    assert len(re.findall(r"\bfetch\(", _code(_js("ui.js")))) == 0
    for banned in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "import("):
        assert banned not in code, banned


def test_the_probe_cannot_transmit_or_store_anything():
    code = _code(_js("probe/probe.js"))
    for banned in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource",
                   "localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert banned not in code, banned


@pytest.mark.parametrize("name", ["app.js", "ui.js", "probe/probe.js"])
def test_no_timers(name):
    """النظام يملك زمن المكوث. لا تقدّم تلقائي ولا إغلاق تلقائي ولا عدّ تنازلي."""
    code = _code(_js(name))
    for banned in ("setTimeout", "setInterval", "requestAnimationFrame", "requestIdleCallback",
                   "AbortSignal.timeout", "scheduler.postTask"):
        assert banned not in code, f"{name}: {banned}"


@pytest.mark.parametrize("name", ["app.js", "ui.js"])
def test_no_storage_in_the_app(name):
    code = _code(_js(name))
    for banned in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert banned not in code, f"{name}: {banned}"


@pytest.mark.parametrize("name", ["app.js", "ui.js"])
def test_activation_is_by_click_alone(name):
    """
    لا pointerdown ولا ضغطٌ مطوّل ولا سحب ولا مرور: النظر لا يضغط ويسحب،
    ومؤشره يمرّ على كل شيء. صفحة الاختبار وحدها تستمع للمرور، لأنها تقيسه.
    """
    events = re.findall(r"addEventListener\(\s*['\"]([a-z]+)['\"]", _code(_js(name)))
    banned = {e for e in events if re.match(r"(pointer|mouse|touch|drag|wheel|contextmenu)", e)}
    assert not banned, f"{name}: {sorted(banned)}"


def test_no_hover_or_motion_in_css():
    for path in STATIC.rglob("*.css"):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        assert ":hover" not in css, path.name
        assert not re.search(r"@keyframes|animation\s*:(?!\s*none)|transition\s*:(?!\s*none)", css), path.name


@pytest.mark.parametrize("page", ["index.html", "probe/index.html"])
def test_html_carries_no_inline_code_or_gaze_hazards(page):
    html = (STATIC / page).read_text(encoding="utf-8")
    markup = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", markup), "سكربتٌ مضمَّن (CSP)"
    assert not re.search(r"\sstyle=", markup), "تنسيقٌ مضمَّن (CSP)"
    assert not re.search(r"\son[a-z]+=", markup), "معالجُ حدثٍ مضمَّن"
    assert not re.search(r"\stitle=", markup), "تلميحٌ لا يظهر إلا بالمرور"
    assert not re.search(r"\splaceholder=", markup), "نصٌّ نائب بدل عنوانٍ ظاهر"
    assert 'type="range"' not in markup and "draggable" not in markup
    assert not re.search(r"(?:src|href)=\"https?://", markup), "موردٌ من طرفٍ ثالث"


def test_fields_are_large_enough_not_to_trigger_ios_zoom():
    """iOS يكبّر الصفحة عند التركيز على حقلٍ خطّه دون 16px، والمستخدم بالنظر لا يستطيع إرجاعها."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    field = re.search(r"\.field\s*\{([^}]*)\}", css).group(1)
    assert "font-size: var(--fs-body)" in field
    assert re.search(r"--fs-body:\s*1\.125rem", css)


def test_ios_text_size_reaches_the_screen_text_and_never_the_root():
    """
    `font: -apple-system-body` يأخذ «حجم النصّ» من iOS، ويضبط معه العائلة وتباعد
    الأسطر؛ فهو على `.screen` وحدها، وبعده في القاعدة نفسها عائلة الخطّ وتباعد الأسطر.
    والجذر بحجم المتصفّح: لو تبعه الجذر لكبرت الأهداف (4.5rem) وفاضت كل شاشة.
    """
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "styles.css").read_text(encoding="utf-8"), flags=re.S)
    rules = [(selector.strip(), block) for selector, block in re.findall(r"([^{}]+)\{([^}]*)\}", css)
             if "-apple-system" in block]
    assert [selector for selector, _ in rules] == [".screen"], rules
    block = rules[0][1]
    order = [block.find(part) for part in
             ("font: -apple-system-body;", "font-family: var(--font);", "line-height: var(--line-height);")]
    assert -1 not in order and order == sorted(order), order
    assert re.search(r"(?m)^html\s*\{[^}]*font-size:\s*100%", css)


def test_the_users_name_never_reaches_the_model():
    """
    الاسم يُعرض في الواجهة من قاعدة التطبيق، ولا تعرفه الوحدات التي تبني طلب
    النموذج أو ترسله أو تنفّذ أداته: ما لا تذكره لا تستطيع إرساله.
    """
    import inspect

    from eyework import assistant_prompt, copywriter, model_gateway, prompt, prompt_kit, reviewer_prompt, self_check

    for module in (prompt, copywriter, self_check, prompt_kit, reviewer_prompt, assistant_prompt, model_gateway):
        source = inspect.getsource(module)
        assert "display_name" not in source, module.__name__
        assert "ew_my_display_name" not in source, module.__name__
    assert set(inspect.signature(prompt.CopyRequest).parameters) == {
        "jpeg", "seller_note", "previous", "presets", "edit_note",
    }


# ── طبقة الذكاء الاصطناعي ─────────────────────────────────────────────
AI_MODULES = ("model_gateway.py", "prompt_kit.py", "ai_limits.py", "ai_text.py", "redact.py", "grounding.py",
              "reviewer_prompt.py", "reviewer.py", "assistant_prompt.py", "assistant.py", "ai_log.py",
              "web/routes_ai.py", "scripts/ai_eval.py", "inventory_prompt.py")
PROMPT_MODULES = ("prompt_kit.py", "reviewer_prompt.py", "assistant_prompt.py", "inventory_prompt.py")
#: من يسجّل عبر `ai_log` وحده: لا `logging` ولا `print`، فلا يتسرّب نصٌّ إلى السجلّ.
AI_LOG_ONLY = ("model_gateway.py", "prompt_kit.py", "ai_text.py", "redact.py", "grounding.py", "reviewer_prompt.py",
               "reviewer.py", "assistant_prompt.py", "assistant.py", "web/routes_ai.py", "inventory_prompt.py",
               "inventory.py")
#: ما يعيد هذا النموذج 400 عليه، أو لا تحتاجه هذه الأدوات: لا يظهر حرفياً في وحداتها.
_FORBIDDEN_REQUEST_KEYS = {"thinking", "budget_tokens", "tool_choice"}
#: مفاتيح لا تدخل موضوعاً يُرسل (المواصفة §6.2).
IDENTITY_KEYS = {"name", "display_name", "email", "login", "birth", "ui_size", "user_id", "supplier", "vat_number",
                 "customer", "phone", "ticket_number"}


def _string_constants(path: Path) -> set[str]:
    return {node.value for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}


@pytest.mark.parametrize("name", AI_MODULES)
def test_ai_modules_never_name_thinking_a_budget_or_forced_tools(name):
    found = _string_constants(APP / name) & _FORBIDDEN_REQUEST_KEYS
    assert not found, f"{name}: {sorted(found)}"


@pytest.mark.parametrize("name", PROMPT_MODULES)
def test_prompt_modules_know_neither_the_database_nor_the_user(name):
    path = APP / name
    assert not {m for m in _imports(path) if m.startswith(("eyework.auth", "eyework.db", "eyework.web"))}, name
    source = path.read_text(encoding="utf-8")
    assert "display_name" not in source and "ew_my_display_name" not in source, name


@pytest.mark.parametrize("name", AI_LOG_ONLY)
def test_ai_modules_log_only_through_ai_log(name):
    path = APP / name
    assert "logging" not in _tops(path), name
    offenders = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "print":
            offenders.append(f"print [{node.lineno}]")
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id in ("logger", "logging", "log"):
            offenders.append(f"{func.value.id}.{func.attr} [{node.lineno}]")
    assert not offenders, f"{name}: {offenders}"


def test_only_ai_log_imports_logging_among_the_ai_modules():
    importers = [name for name in AI_MODULES if "logging" in _tops(APP / name)]
    assert importers == ["ai_log.py"]


def test_every_model_calling_route_depends_on_the_consent_gate():
    """ما يصل النموذج أو المراجِع من مسارات الذكاء الاصطناعي يعتمد `require_current_terms`."""
    tree = ast.parse((APP / "web" / "routes_ai.py").read_text(encoding="utf-8"))
    checked = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.decorator_list:
            continue
        body = "\n".join(ast.unparse(statement) for statement in node.body)
        if any(token in body for token in ("reviewer.review(", "assistant.ask(", "state.gateway", "state.copywriter")):
            assert "Depends(require_current_terms)" in ast.unparse(node.args), node.name
            checked.append(node.name)
    assert sorted(checked) == ["ask", "review"]


def _identity_key(key: str) -> bool:
    return any(key == word or key.startswith(word + "_") or key.endswith("_" + word) for word in IDENTITY_KEYS)


def test_registered_review_loaders_declare_no_identity_fields_and_carry_a_fixture():
    """
    المفاتيح المعلَنة تُفحص هنا (المسار السريع)؛ وما يحمّله المحمّل فعلاً يُقارن بها في
    `tests/api/test_ai_review.py::check_loader_keys` على موضوعٍ من `fixture` — فلا تُسجَّل
    أداةٌ بلا موضعٍ نموذجي يُشغَّل عليه محمّلها.
    """
    import eyework.inventory  # noqa: F401 — يسجّل STOCK_REVIEW للفاتورة وللمرتجع
    from eyework import reviewer

    assert "STOCK_REVIEW" in reviewer.FEATURES and ("STOCK_REVIEW", "RETURN") in reviewer.KIND_FEATURES
    every = {**reviewer.FEATURES, **{f"{code}/{kind}": feature for (code, kind), feature in reviewer.KIND_FEATURES.items()}}
    for code, feature in every.items():
        found = sorted(key for key in feature.payload_keys if _identity_key(key))
        assert not found, f"{code}: {found}"
        assert feature.fixture is not None, f"{code}: أداة مراجعةٍ بلا موضوعٍ نموذجي"


def test_screen_loader_sql_selects_no_identity_columns():
    """شاشات المساعد تُحمَّل بعباراتٍ ثابتة لا تذكر عموداً من أعمدة الهوية."""
    tree = ast.parse((APP / "assistant.py").read_text(encoding="utf-8"))
    statements = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
                  and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                  and re.search(r"\bSELECT\b", node.value.value)]
    assert statements, "لا عبارات في assistant.py"
    for statement in statements:
        for column in ("display_name", "login_hmac", "email", "birth_date", "ui_size", "user_id", "password",
                       "terms_version", "jpeg", "sha256"):
            assert column not in statement, column


def test_the_model_call_has_no_identity_fields():
    from eyework.prompt_kit import ModelCall

    assert {field.name for field in dataclasses.fields(ModelCall)} == {
        "feature", "system", "user", "schema", "effort", "max_tokens", "deadline_seconds", "stream", "prompt_version",
    }


# ── بوّابة الموافقة ─────────────────────────────────────────────────────
#: أسماء عملاء النموذج على حالة التطبيق (`request.app.state.<اسم>`): مسارٌ يذكر أحدها
#: يصل النموذج. مسار القرار على التنبيه (`/api/ai/flags/{id}/decision`) لا يذكر أحدها:
#: لا يُرسَل فيه شيء، فلا بوّابة عليه (ai_spec §8.2).
MODEL_CLIENTS = ("copywriter", "gateway", "review_runner", "reviewer", "assistant", "support_agent")
#: يُغلقان في حزمة التبديل مع تسلسل البدء (القرار D1): قبلها لا سبيل لمن وافق على
#: نسخةٍ أقدم إلى إعادة القبول من العميل الثابت، فحجبهم عن النصّ يوقف العمل.
UNGATED_UNTIL_THE_SWITCH = {"POST /api/campaigns/{campaign_id}/copy", "POST /api/campaigns/{campaign_id}/copy/edit"}


def _api_routes():
    """مسارات كل وحدة `web/routes_*` بموجّهها، كما يضمّها التطبيق: اعتماديات الموجّه فيها."""
    import importlib
    import pkgutil

    from eyework import web

    for info in pkgutil.iter_modules(web.__path__):
        if info.name.startswith("routes_"):
            yield from importlib.import_module(f"eyework.web.{info.name}").router.routes


def _depends_on(dependant, target) -> bool:
    return any(sub.call is target or _depends_on(sub, target) for sub in dependant.dependencies)


def _reaches_the_model(route) -> bool:
    import inspect

    source = inspect.getsource(route.endpoint)
    return any(f"state.{name}" in source for name in MODEL_CLIENTS)


def test_every_route_that_reaches_the_model_depends_on_the_consent_gate():
    """لا يُرسَل شيءٌ لحسابٍ إلى مزوّد النموذج قبل أن يوافق على النسخة الحالية من «قبل أن تبدأ»."""
    from eyework.web.deps import require_current_terms

    reaching, offenders = [], []
    for route in _api_routes():
        if not _reaches_the_model(route):
            continue
        for method in sorted(route.methods):
            name = f"{method} {route.path}"
            reaching.append(name)
            if name not in UNGATED_UNTIL_THE_SWITCH and not _depends_on(route.dependant, require_current_terms):
                offenders.append(name)
    assert not offenders, f"مسارٌ يصل النموذج بلا بوّابة الموافقة: {offenders}"
    # الاستثناء يسمّي مساراتٍ تصل النموذج فعلاً: لو أُغلقت أو حُذفت فليُحذف من هنا.
    assert UNGATED_UNTIL_THE_SWITCH <= set(reaching), set(reaching)


def test_the_consent_gate_builds_on_the_session_and_nothing_else():
    """البوّابة تعتمد `require_user` فتُحسب الجلسة مرةً للطلب، ولا تقرأ جسماً ولا استعلاماً."""
    import inspect

    from eyework.web.deps import require_current_terms, require_user

    parameters = inspect.signature(require_current_terms).parameters
    assert set(parameters) == {"request", "user_id"}
    assert parameters["user_id"].default.dependency is require_user
