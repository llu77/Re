"""
الفحص اليدوي يطبع كل ما في النتيجة
==================================
`copy_smoke` يُقرأ قبل الإطلاق ليُعرف ما سيقرؤه المستخدم؛ فلا يُخفي شيءٌ فيه
شيئاً آخر: التنبيهات تُطبع بلا ملاحظة، وسبب الصورة غير الصالحة يُطبع معها.
"""

from __future__ import annotations

import pytest

from eyework.copy_rules import CopyWarning
from eyework.copywriter import CopyOutcome
from eyework.scripts import copy_smoke


@pytest.fixture
def run(monkeypatch, tmp_path, capsys):
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8")
    monkeypatch.setenv("EYEWORK_ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(copy_smoke, "process", lambda data: type("Image", (), {"jpeg": data})())

    def go(outcome: CopyOutcome) -> str:
        monkeypatch.setattr(copy_smoke, "AnthropicCopywriter",
                            lambda key: type("Writer", (), {"write": lambda self, request: outcome})())
        copy_smoke.main([str(photo)])
        return capsys.readouterr().out
    return go


def test_warnings_are_printed_when_the_note_was_dropped(run):
    warning = next(iter(CopyWarning))
    out = run(CopyOutcome("OK", title="ع", description="و", warnings=(warning,), note=None))
    assert warning.value in out


def test_an_unusable_photo_prints_its_reason_and_its_note(run):
    out = run(CopyOutcome("UNUSABLE_PHOTO", reason="TOO_DARK", note="الصورة مظلمة؛ صوّرها في ضوء النهار."))
    assert "TOO_DARK" in out and "ضوء النهار" in out
