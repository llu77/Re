"""
وجهات سيمبول تطابق أزرار الرئيسية في العميل: المعرّف الذي يكتبه النموذج في `open` يفتح في العميل بند
`WORKSPACES[…].home` بالمعرّف نفسه (`client/src/lib/workspace.ts`)، والاسم الذي يراه الموظف على زرّ
الوجهة اسم البند نفسه. وجهةٌ بلا بندٍ لا تُفتح، وبندٌ تغيّر اسمه يُقترح باسمٍ لا يجده الموظف.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from eyework import assistant, inventory, support  # noqa: F401 — تسجّلان وجهات مهنتيهما عند الاستيراد
from eyework.professions import Profession

TS = (Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "workspace.ts").read_text(encoding="utf-8")


def home_entries(profession: str) -> list[tuple[str, str]]:
    """(المعرّف، الاسم) لبنود `home` في مساحة المهنة، بترتيبها."""
    block = re.search(rf"\n  {profession}: \{{(.*?)\n  \}},?\n", TS, re.DOTALL)
    assert block, profession
    home = re.search(r"home: \[(.*?)\n    \]", block.group(1), re.DOTALL)
    assert home, profession
    return re.findall(r'\{ id: "([a-z]+)", label: "([^"]+)"', home.group(1))


@pytest.mark.parametrize("profession", list(Profession))
def test_every_destination_is_a_home_entry_with_the_same_name(profession):
    destinations = [(place.id, place.label) for place in assistant.DESTINATIONS.get(profession, ())]
    assert destinations == home_entries(profession.value)
