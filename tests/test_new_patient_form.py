"""
اختبار وظيفي للنموذج — القسم 0، ح-2
=====================================
يشغّل التطبيق فعلياً عبر AppTest ويتحقق أن الحقول التخصصية تظهر لنوع التأهيل
الذي تنتجه القائمة. قبل الإصلاح كانت القائمة تنتج `neurological` بينما الحارس
يقارن بـ`neuro`، فكان حقل «الجانب المصاب» كوداً ميتاً لا يُعرض أبداً.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

# المسار النسبي في AppTest يُحلّ مقابل ملف الاختبار لا مجلد العمل
APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture(scope="module")
def form():
    def _run(rehab_type=None):
        at = AppTest.from_file(str(APP), default_timeout=90)
        at.session_state["show_new_patient_form"] = True
        if rehab_type is not None:
            at.session_state["np_rehab_type"] = rehab_type
        at.run()
        return at
    return _run


def _widget_labels(at) -> list[str]:
    return (
        [w.label for w in at.selectbox]
        + [w.label for w in at.slider]
        + [w.label for w in at.number_input]
        + [w.label for w in at.text_input]
    )


def test_form_renders_without_exception(form):
    at = form()
    assert not at.exception, [str(e) for e in at.exception]


@pytest.mark.parametrize(
    "rehab_type, expected_label",
    [
        ("neuro", "الجانب المصاب"),
        ("cardiac", "تصنيف NYHA"),
        ("orthopedic", "مستوى الألم"),
        ("pain", "مستوى الألم"),
        ("vision", "حدة الإبصار"),
    ],
)
def test_specialty_field_appears_for_its_rehab_type(form, rehab_type, expected_label):
    at = form(rehab_type)
    assert not at.exception, [str(e) for e in at.exception]
    labels = _widget_labels(at)
    assert any(expected_label in label for label in labels), (
        f"«{expected_label}» لا يظهر عند اختيار «{rehab_type}» — الحقل غير قابل للتعبئة. "
        f"الحقول الظاهرة: {labels}"
    )


def test_affected_side_hidden_before_a_type_is_chosen(form):
    at = form("")
    assert not any("الجانب المصاب" in label for label in _widget_labels(at))


def test_every_selectable_type_renders_cleanly(form):
    """لا نوع تأهيل يكسر النموذج."""
    import app

    for key in app.REHAB_TYPES:
        at = form(key)
        assert not at.exception, f"«{key}» يرفع استثناءً: {[str(e) for e in at.exception]}"
