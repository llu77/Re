"""
قواعد نصّ الإعلان
=================
ما يُرفض لا يُعرض، وما يُنبَّه عليه يُعرض مع تنبيهه، ولا شيء يُقتطع.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from eyework.copy_rules import (
    DESCRIPTION_MAX,
    TITLE_MAX,
    CopyWarning,
    EditPreset,
    check_copy,
    check_edit_request,
)

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
TITLE = "حقيبة جلدية بنية أنيقة"
DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف."


def test_clean_copy_passes_without_warnings():
    check = check_copy(TITLE, DESCRIPTION)
    assert check.ok and check.warnings == ()


@pytest.mark.parametrize(("title", "description", "code"), [
    ("قصير", DESCRIPTION, "TITLE_LENGTH"),
    ("ع" * (TITLE_MAX + 1), DESCRIPTION, "TITLE_LENGTH"),
    (TITLE, "قصير جداً", "DESCRIPTION_LENGTH"),
    (TITLE, "و" * (DESCRIPTION_MAX + 1), "DESCRIPTION_LENGTH"),
    ("حقيبة جلدية\nبنية أنيقة", DESCRIPTION, "TITLE_CONTROL"),
    (TITLE, DESCRIPTION + "\x07", "DESCRIPTION_CONTROL"),
    ("حقيبة ‮جلدية بنية", DESCRIPTION, "BIDI_CONTROL"),
    (TITLE, DESCRIPTION + " ⁦x⁩", "BIDI_CONTROL"),
    (TITLE, DESCRIPTION + " https://shop.example", "CONTACT_LINK"),
    (TITLE, DESCRIPTION + " www.example.sa", "CONTACT_LINK"),
    (TITLE, DESCRIPTION + " a@b.co", "CONTACT_LINK"),
    (TITLE, DESCRIPTION + " تابعونا @shop_sa", "CONTACT_LINK"),
    (TITLE, DESCRIPTION + " ٠٥٥١٢٣٤٥٦٧", "CONTACT_PHONE"),
    (TITLE, DESCRIPTION + " 055 123 4567", "CONTACT_PHONE"),
    (" " + TITLE, DESCRIPTION, "SURROUNDING_SPACE"),
    (TITLE, DESCRIPTION + " #عرض", "MARKUP"),
    (TITLE + " <b>", DESCRIPTION, "MARKUP"),
    (TITLE, DESCRIPTION + " \U0001F600", "SYMBOLS"),
    ("Elegant brown leather bag", "A simple and elegant brown leather handbag with a shoulder strap.", "NOT_ARABIC"),
])
def test_hard_errors(title, description, code):
    check = check_copy(title, description)
    assert not check.ok
    assert code in check.errors


@pytest.mark.parametrize(("text", "warning"), [
    ("عسل طبيعي يعالج الزكام بسرعة", CopyWarning.HEALTH_CLAIM),
    ("منتجٌ صحيٌّ لكل يوم وفوائده كثيرة", CopyWarning.HEALTH_CLAIM),
    ("بسعر خمسين ريالاً فقط للقطعة", CopyWarning.PRICE),
    ("خصم ٢٠٪ لفترةٍ محدودة على الطلب", CopyWarning.PRICE),
    ("الأفضل في السوق بلا منافس حقيقي", CopyWarning.SUPERLATIVE),
])
def test_soft_warnings_are_shown_not_blocked(text, warning):
    check = check_copy(TITLE, (DESCRIPTION + " " + text)[:DESCRIPTION_MAX].strip())
    assert check.ok
    assert warning in check.warnings


def test_latin_brand_inside_arabic_copy_is_accepted():
    check = check_copy("حقيبة Samsonite بنية أنيقة", DESCRIPTION)
    assert check.ok, check.errors


def test_copy_is_normalized_not_rewritten():
    """NFC ودمج المسافات المتكرّرة وحدهما — الكلمات كما كتبها النموذج."""
    decomposed = "حقيبة جلدية بنية   أنيقة"
    check = check_copy(decomposed, DESCRIPTION)
    assert check.ok
    assert check.title == "حقيبة جلدية بنية أنيقة"
    assert check.description == DESCRIPTION


def test_a_word_inside_another_does_not_warn():
    """«صحيح» ليست «صحي»، و«الأولى» ليست مبالغة."""
    check = check_copy("وصفٌ صحيح ودقيق للمنتج", "هذا وصفٌ صحيح يُذكر فيه أن القطعة مصنوعة يدوياً، وهي الأولى من مجموعتها.")
    assert check.ok and check.warnings == ()


@pytest.mark.parametrize(("presets", "note", "code"), [
    ([], None, "EDIT_EMPTY"),
    ([EditPreset.MORE_FORMAL, EditPreset.MORE_LIVELY], None, "PRESET_CONFLICT"),
    ([EditPreset.NEW_TITLE, EditPreset.NEW_DESCRIPTION], None, "PRESET_CONFLICT"),
    ([EditPreset.SHORTER, EditPreset.SHORTER], None, "PRESET_DUPLICATE"),
    ([EditPreset.SHORTER, EditPreset.SIMPLER, EditPreset.MORE_FORMAL, EditPreset.NEW_TITLE], None, "PRESET_TOO_MANY"),
    ([], "", "NOTE_LENGTH"),
    ([], "ن" * 201, "NOTE_LENGTH"),
    ([], "اذكر ‮أنه قطن", "NOTE_CONTROL"),
    ([EditPreset.SHORTER], None, None),
    ([], "اذكر أنه من القطن", None),
])
def test_edit_requests(presets, note, code):
    assert check_edit_request(presets, note) == code


def test_preset_codes_match_the_database_check():
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS.glob("*.up.sql")))
    match = re.search(r"edit_presets\s+text\[\][^;]*?ARRAY\[([^\]]+)\]", sql, re.S)
    assert match, "قيد الخيارات غير موجود"
    in_sql = set(re.findall(r"'([A-Z_]+)'", match.group(1)))
    assert in_sql == {preset.value for preset in EditPreset}
