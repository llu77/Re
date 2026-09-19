"""
اختبارات انحدار — القسم 0 (إيقاف النزيف)
=========================================
كل اختبار هنا يقابل عيباً مؤكَّداً في تدقيق المرحلة 0. فشل أيٍّ منها يعني
عودة العيب نفسه، لا مجرد تغيّر في الشكل.
"""

import json
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CONSULTANT = (ROOT / "rehab_consultant.py").read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    """الشريحة بين علامتين — يجب البحث عن النهاية بعد البداية لا من أول الملف."""
    begin = source.index(start)
    return source[begin:source.index(end, begin + len(start))]


# ── ح-8: ملفات المرضى خارج Git ──────────────────────────────────────
@pytest.mark.parametrize(
    "relative_path",
    ["data/patients/MR-2026-0001.json", "data/outcomes/MR-2026-0001.json",
     "data/patients/.counter"],
)
def test_patient_data_is_gitignored(relative_path):
    result = subprocess.run(
        ["git", "check-ignore", relative_path], cwd=ROOT, capture_output=True
    )
    assert result.returncode == 0, f"{relative_path} غير مستثنى من Git — PHI قابل للالتزام"


def test_gitkeep_stays_tracked():
    result = subprocess.run(
        ["git", "check-ignore", "data/patients/.gitkeep"], cwd=ROOT, capture_output=True
    )
    assert result.returncode != 0, "استثناء .gitkeep يُفقد بنية المجلد"


# ── ح-1: لا نتيجة محاكاة تدخل السجل الطبي ───────────────────────────
def test_no_simulated_result_is_persisted():
    body = _section(APP, "def render_interventions_tab", "def _render_simulation_notice")
    offenders = []
    for block in re.split(r"\n    (?:el)?if int_type ==", body)[1:]:
        name = re.match(r'\s*"(\w+)"', block).group(1)
        simulated = "simulate_session" in block or '"action": "demo"' in block
        persisted = "_save_intervention" in block
        if simulated and persisted:
            offenders.append(name)
    assert not offenders, f"مسارات محاكاة ما زالت تُحفظ في ملف المريض: {offenders}"


def test_fabricated_lux_is_not_displayed():
    body = _section(APP, "def render_interventions_tab", "def _render_simulation_notice")
    assert "estimated_lux" not in body, (
        "قراءة اللوكس مشتقة من إطار مولَّد — عرضها كقياس بيئي تلفيق سريري"
    )


# ── ح-2: كل مفتاح يُقارَن به قابل للإنتاج من القائمة ────────────────
def test_every_compared_rehab_type_is_selectable():
    literal = _section(APP, "REHAB_TYPES = {", "}")
    keys = {k for k in re.findall(r'"(\w*)":', literal) if k}

    compared = set()
    for source in (APP, CONSULTANT):
        for match in re.finditer(
            r'(?:rehab_type|rt)\s*(?:==\s*"(\w+)"|in\s*\(([^)]*)\))', source
        ):
            if match.group(1):
                compared.add(match.group(1))
            if match.group(2):
                compared |= set(re.findall(r'"(\w+)"', match.group(2)))

    unreachable = compared - keys
    assert not unreachable, (
        f"فروع لا يمكن بلوغها — القائمة لا تنتج هذه المفاتيح: {sorted(unreachable)}"
    )


def test_affected_side_input_is_reachable():
    guard = re.search(r'if rehab_type == "(\w+)":\s*\n\s*affected_side = ', APP)
    assert guard, "حقل الجانب المصاب غير موجود"
    literal = _section(APP, "REHAB_TYPES = {", "}")
    assert f'"{guard.group(1)}":' in literal, (
        "حقل الجانب المصاب محروس بنوع تأهيل لا تنتجه القائمة"
    )


def test_tool_enum_matches_selectable_types():
    literal = _section(APP, "REHAB_TYPES = {", "}")
    keys = {k for k in re.findall(r'"(\w*)":', literal) if k}
    enum = set(re.findall(
        r'"enum": \[([^\]]*)\],\s*\n\s*"description": "نوع التأهيل"', CONSULTANT
    )[0].replace('"', "").replace(" ", "").split(","))
    assert enum == keys, f"enum الأداة يخالف القائمة: {enum ^ keys}"


# ── ح-3: القارئ والكاتب يتفقان، والبرنامج المنزلي يُعرض ─────────────
def test_plan_reader_reads_only_written_keys():
    written = set(re.findall(r'"(\w+)":\s*params\.get', CONSULTANT)) | {"timestamp", "status"}
    body = _section(APP, "def render_treatment_plans_tab", "# Tab: Chat")
    read = set(re.findall(r'plan(?:\[|\.get\()"(\w+)"', body))
    orphans = read - written
    assert not orphans, f"القارئ يطلب مفاتيح لا يكتبها أحد: {sorted(orphans)}"


def test_home_program_reaches_the_screen():
    body = _section(APP, "def render_treatment_plans_tab", "# Tab: Chat")
    assert 'plan.get("home_program"' in body, "البرنامج المنزلي ما زال غير معروض"
    for key in ("goals_short_term", "goals_long_term"):
        assert key in body, f"{key} غير معروض"


# ── ح-4: فشل الحفظ لا يُبلَّغ كنجاح ─────────────────────────────────
@pytest.fixture
def fake_streamlit(monkeypatch):
    """حقن وحدة streamlit وهمية — record_treatment_plan يستوردها داخلياً."""
    def _install(session_state):
        module = types.ModuleType("streamlit")
        module.session_state = session_state
        monkeypatch.setitem(sys.modules, "streamlit", module)
    return _install


class _SessionState(dict):
    def __getattr__(self, item):
        return self[item]


def test_write_failure_is_reported_as_error(fake_streamlit, monkeypatch):
    from rehab_consultant import record_treatment_plan

    patient = {"id": "MR-2026-0001", "treatment_plans": []}
    fake_streamlit(_SessionState(
        current_patient_id="MR-2026-0001", patients={"MR-2026-0001": patient}
    ))

    def _explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _explode)
    result = record_treatment_plan({"plan_title": "خطة"})

    assert result["status"] == "error", "فشل الكتابة ما زال يُبلَّغ كنجاح"
    assert patient["treatment_plans"] == [], (
        "الذاكرة تحمل خطة لا وجود لها على القرص"
    )


def test_missing_patient_is_reported_as_not_saved(fake_streamlit):
    from rehab_consultant import record_treatment_plan

    fake_streamlit(_SessionState(current_patient_id=None, patients={}))
    result = record_treatment_plan({"plan_title": "خطة"})
    assert result["status"] == "not_saved"


def test_successful_write_persists_and_updates_memory(fake_streamlit, tmp_path, monkeypatch):
    import rehab_consultant
    from rehab_consultant import record_treatment_plan

    patient = {"id": "MR-2026-0001", "treatment_plans": []}
    fake_streamlit(_SessionState(
        current_patient_id="MR-2026-0001", patients={"MR-2026-0001": patient}
    ))
    monkeypatch.setattr(rehab_consultant, "__file__", str(tmp_path / "rehab_consultant.py"))
    (tmp_path / "data" / "patients").mkdir(parents=True)

    result = record_treatment_plan({"plan_title": "خطة", "home_program": "تمارين يومية"})
    assert result["status"] == "ok"
    assert len(patient["treatment_plans"]) == 1

    written = json.loads((tmp_path / "data" / "patients" / "MR-2026-0001.json").read_text(encoding="utf-8"))
    assert written["treatment_plans"][0]["home_program"] == "تمارين يومية"


# ── ح-16: التبعيات المعلنة تغطي كل ما يُستورَد ──────────────────────
def test_declared_requirements_cover_runtime_imports():
    declared = {
        re.split(r"[<>=]", line)[0].strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    distribution_of = {
        "streamlit": "streamlit", "numpy": "numpy", "cv2": "opencv-python-headless",
        "yaml": "pyyaml", "anthropic": "anthropic", "requests": "requests",
    }
    missing = {
        module: dist for module, dist in distribution_of.items()
        if dist not in declared
    }
    assert not missing, f"تبعيات مستورَدة وغير معلنة: {missing}"


# ── حذف غير قابل للتراجع يتطلب تأكيداً ──────────────────────────────
def test_delete_requires_confirmation():
    index = APP.index("delete_patient(pid)")
    guard = APP[index - 600:index]
    assert 'pending_delete == pid' in guard and "تأكيد الحذف" in guard, (
        "حذف ملف المريض ما زال بضغطة واحدة"
    )
