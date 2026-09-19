"""
حدود الطبقات — ما يمنع تآكل الضمانات مع الوقت
===============================================
ضمانة تحرسها المراجعة البشرية وحدها تتآكل. كل اختبار هنا يفشل البناء عند أول
انحراف، لا عند اكتشافه في الإنتاج.

لا تحتاج هذه الاختبارات قاعدة بيانات: تقرأ الشيفرة نفسها.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

#: الطبقة الجديدة التي تُفرض عليها القواعد كاملةً.
NEW_LAYER = ("core", "api", "migrations")

#: كود سابق للقسم 1. دَين معروف يُسدَّد في الأقسام اللاحقة، لا استثناء دائم.
#: `test_legacy_debt_only_shrinks` يمنع بقاء اسم هنا بعد إصلاحه.
LEGACY_TIME_DEBT = {
    "app.py",
    "rehab_consultant.py",
    "utils/security.py",
    "cdss/engine.py",
    "cdss/explainability.py",
    "cdss/fhir_parser.py",
    "cdss/outcome_store.py",
    "tools/depression_screening.py",
    "tools/documents.py",
    "tools/environmental_assessment.py",
    "tools/outcome_tracker.py",
    "tools/perceptual_learning_planner.py",
    "tools/referral_generator.py",
    "tools/technique_recommender.py",
    "tools/telerehab_session_manager.py",
}

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def _python_files(*roots: str):
    for root in roots:
        base = ROOT / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if not any(part in _SKIP_DIRS for part in path.parts):
                yield path


def _all_project_files():
    yield from (path for path in sorted(ROOT.glob("*.py")))
    yield from _python_files("core", "api", "migrations", "tools", "cdss", "assessments",
                             "interventions", "chains", "utils", "agents", "scripts")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


# ── معيار القبول 2: لا مسار التفافي حول نقطة العبور ─────────────────────
FORBIDDEN_IN_PATIENT_GATE = {"core.db", "core.proposals"}


def test_patient_gate_reads_only_through_the_delivery_gateway():
    """
    بوابة المريض لا تصل إلى جداول المحتوى إلا عبر `core.delivery`.

    هذا الاختبار هو نصف الضمانة؛ نصفها الآخر أن دور `app_patient` لا يملك أي
    صلاحية على تلك الجداول أصلاً (`test_patient_role_cannot_touch_content_tables`).
    """
    offenders = {}
    for path in _python_files("api/patient"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        banned = {
            module
            for module in _imported_modules(tree)
            if any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN_IN_PATIENT_GATE)
        }
        if banned:
            offenders[_relative(path)] = sorted(banned)

    assert not offenders, (
        "مسار المريض يستورد وصولاً مباشراً إلى المحتوى — القراءة عبر "
        f"core.delivery حصراً: {offenders}"
    )


def test_delivery_gateway_is_the_only_patient_role_reader():
    """لا وحدة أخرى تفتح جلسة بدور `patient`."""
    offenders = []
    for path in _python_files("core", "api"):
        if _relative(path) == "core/delivery.py":
            continue
        source = path.read_text(encoding="utf-8")
        if '"patient"' in source and "db.session" in source:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "session"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "patient"
                ):
                    offenders.append(_relative(path))
    assert not offenders, f"وحدات تقرأ بدور المريض خارج نقطة العبور: {sorted(set(offenders))}"


# ── معيار القبول 14: مصدر زمن واحد ──────────────────────────────────────
#: الدوال التي تُنتج لحظة محلية ساذجة، لكل نوع من المصدر.
_CLASS_CALLS = {"datetime": {"now", "utcnow", "today"}, "date": {"today"}}


def _time_class_aliases(tree: ast.AST) -> dict[str, str]:
    """
    يربط الأسماء المحلية بأصلها في `datetime`.

    الاسم المستعار (`from datetime import datetime as _dt`) كان يفلت من فحص
    يقارن الأسماء حرفياً — وهو تحديداً ما يفعله `rehab_consultant.py:1302`.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for item in node.names:
                if item.name in _CLASS_CALLS:
                    aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name == "datetime":
                    # `import datetime as d` ⇒ d.datetime.now() و d.date.today()
                    aliases[f"{item.asname or item.name}.datetime"] = "datetime"
                    aliases[f"{item.asname or item.name}.date"] = "date"
    return aliases


def _call_owner(node: ast.Attribute) -> str | None:
    """`_dt` من `_dt.now()`، و`d.datetime` من `d.datetime.now()`."""
    owner = node.value
    if isinstance(owner, ast.Name):
        return owner.id
    if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name):
        return f"{owner.value.id}.{owner.attr}"
    return None


def _naive_time_calls(tree: ast.AST) -> list[str]:
    aliases = _time_class_aliases(tree)
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        owner = _call_owner(node.func)
        origin = aliases.get(owner) if owner else None
        if origin and node.func.attr in _CLASS_CALLS[origin]:
            found.append(f"{owner}.{node.func.attr}() [{node.lineno}]")
    return found


def test_new_layer_uses_only_the_single_clock():
    """
    `core.clock` هو المصدر الوحيد للوقت في الطبقة الجديدة.

    تدقيق المرحلة 0 وجد 38 طابعاً زمنياً محلياً ساذجاً وصفر تعريف لحدود اليوم.
    بناء حساب التزام فوق ذلك يعطي إجابات مختلفة من مسارات مختلفة.
    """
    offenders = {}
    for path in _python_files(*NEW_LAYER):
        if _relative(path) == "core/clock.py":
            continue
        calls = _naive_time_calls(ast.parse(path.read_text(encoding="utf-8")))
        if calls:
            offenders[_relative(path)] = calls

    assert not offenders, (
        f"وقت محلي ساذج في الطبقة الجديدة — استخدم core.clock.now(): {offenders}"
    )


def test_legacy_time_debt_only_shrinks():
    """اسم يُصلَح يجب أن يُحذف من قائمة الدَّين، وإلا صارت القائمة استثناءً دائماً."""
    already_clean = sorted(
        name
        for name in LEGACY_TIME_DEBT
        if (ROOT / name).exists()
        and not _naive_time_calls(ast.parse((ROOT / name).read_text(encoding="utf-8")))
    )
    assert not already_clean, (
        f"هذه الملفات نظيفة الآن — احذفها من LEGACY_TIME_DEBT: {already_clean}"
    )


def test_no_new_file_joins_the_time_debt():
    """أي ملف خارج القائمة وخارج core/clock.py يجب أن يكون نظيفاً."""
    offenders = {}
    for path in _all_project_files():
        name = _relative(path)
        if name in LEGACY_TIME_DEBT or name == "core/clock.py" or name.startswith("tests/"):
            continue
        calls = _naive_time_calls(ast.parse(path.read_text(encoding="utf-8")))
        if calls:
            offenders[name] = calls
    assert not offenders, f"وقت محلي ساذج في ملف جديد: {offenders}"


# ── معيار القبول 15: لا دمج نصي في SQL ──────────────────────────────────
def _sql_built_by_concatenation(tree: ast.AST) -> list[str]:
    """
    يرصد نصّ SQL مُركَّباً عند نقطة الاستدعاء.

    القاعدة صارمة عمداً: وسيط `execute` الأول إما سلسلة حرفية أو اسم ثابت.
    الصرامة تجعل القاعدة قابلة للتدقيق بنظرة، بدل محلّل ذكي يخطئ.
    """
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"execute", "executemany"} or not node.args:
            continue

        query = node.args[0]
        if isinstance(query, ast.JoinedStr):
            offenders.append(f"f-string في السطر {node.lineno}")
        elif isinstance(query, ast.BinOp) and isinstance(query.op, (ast.Add, ast.Mod)):
            offenders.append(f"دمج/تنسيق في السطر {node.lineno}")
        elif isinstance(query, ast.Call) and getattr(query.func, "attr", None) == "format":
            offenders.append(f"format() في السطر {node.lineno}")
    return offenders


def test_sql_is_never_built_by_string_concatenation():
    """Prepared Statements حصراً: القيم معاملات، والنص ثابت."""
    offenders = {}
    for path in _python_files(*NEW_LAYER):
        found = _sql_built_by_concatenation(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            offenders[_relative(path)] = found
    assert not offenders, f"SQL مُركَّب نصياً: {offenders}"


# ── معيار القبول 12: لا إجراءات جماعية على المحتوى السريري ──────────────
DECISION_SEGMENTS = {"approve", "edit-and-approve", "reject", "submit"}


@pytest.fixture(scope="module")
def openapi_spec():
    import os

    os.environ.setdefault("SYMBOL_DATABASE_URL", "postgresql://unused/unused")
    os.environ.setdefault("SYMBOL_PRACTITIONER_PASSWORD", "unused")
    os.environ.setdefault("SYMBOL_PATIENT_PASSWORD", "unused")
    from api.app import create_app

    return create_app().openapi()


def _decision_paths(spec) -> list[str]:
    return [
        path
        for path in spec["paths"]
        if any(path.endswith("/" + segment) for segment in DECISION_SEGMENTS)
    ]


def test_decision_endpoints_exist(openapi_spec):
    """حارس للاختبار التالي: لو اختفت النقاط لصار الفحص فارغاً وهو يمر."""
    assert len(_decision_paths(openapi_spec)) >= 4


def test_no_decision_endpoint_accepts_a_list(openapi_spec):
    """
    قرار واحد لكل مقترح. الموافقة بالجملة تُفرغ المراجعة من معناها.

    يُفحص شكلان: معرّف مفرد في المسار، وجسم طلب لا يقبل مصفوفة.
    """
    schemas = openapi_spec.get("components", {}).get("schemas", {})
    offenders = []

    for path in _decision_paths(openapi_spec):
        if "{proposal_id}" not in path:
            offenders.append(f"{path}: لا يحمل معرّفاً مفرداً في المسار")

        for method, operation in openapi_spec["paths"][path].items():
            body = operation.get("requestBody", {})
            for media in body.get("content", {}).values():
                schema = media.get("schema", {})
                if ref := schema.get("$ref"):
                    schema = schemas.get(ref.rsplit("/", 1)[-1], {})
                if schema.get("type") == "array":
                    offenders.append(f"{method.upper()} {path}: جسم الطلب مصفوفة")

    assert not offenders, f"إجراءات جماعية على المحتوى السريري: {offenders}"


# ── طبقة المجال مستقلة عن الواجهة ───────────────────────────────────────
def test_core_does_not_depend_on_streamlit_or_the_model_client():
    """
    `core` قابلة للاستدعاء والاختبار بلا واجهة وبلا شبكة.

    الضمانات السريرية يجب أن تصمد خارج أي واجهة، وإلا صارت خاصية عرض.
    """
    offenders = {}
    for path in _python_files("core"):
        modules = _imported_modules(ast.parse(path.read_text(encoding="utf-8")))
        banned = {m for m in modules if m.split(".")[0] in {"streamlit", "anthropic", "fastapi"}}
        if banned:
            offenders[_relative(path)] = sorted(banned)
    assert not offenders, f"طبقة المجال تعتمد على الواجهة: {offenders}"
