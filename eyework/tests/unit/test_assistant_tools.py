"""
أدوات سيمبول بلا قاعدة: تعريف كل أداةٍ كما يرشد إليه توثيق Anthropic لتعريف الأدوات، وما تكتبه من صفوفٍ
معطاة، وخطأ المدخل الذي يعود بـ`is_error`، وما لا تقرؤه أصلاً. الأدوات تعمل بهوية الجلسة وتحت العزل (اختبار
الواجهة البرمجية)؛ وهنا شكل تعريفها وأسطرها وحدودها.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from eyework import assistant, inventory, support
from eyework.assistant_prompt import ToolError
from eyework.professions import Profession


class Rows:
    """مؤشّرٌ يعيد صفوفاً معطاة ويحفظ ما نُفّذ به."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, statement: str, params: tuple = ()) -> None:
        self.executed.append((statement, params))

    def fetchall(self) -> list[dict]:
        return self.rows

    def fetchone(self) -> dict | None:
        return self.rows[0] if self.rows else None


def test_every_tool_is_registered_once_for_its_profession():
    names = {name: tool.profession for name, tool in assistant.TOOLS.items()}
    assert names == {
        "calculate_vat": None, "list_campaigns": Profession.MARKETING,
        "search_items": Profession.STOREKEEPER, "list_low_stock_items": Profession.STOREKEEPER,
        "list_recent_purchases": Profession.STOREKEEPER,
        "search_knowledge_base": Profession.SUPPORT, "get_desk_counts": Profession.SUPPORT,
    }
    assert [tool.name for tool in assistant.tools_for(Profession.SUPPORT)] == [
        "calculate_vat", "search_knowledge_base", "get_desk_counts"]


@pytest.mark.parametrize("name", sorted(assistant.TOOLS))
def test_each_definition_follows_anthropics_guidance_for_tool_definitions(name):
    """
    «Define tools» في توثيق Anthropic: اسمٌ يقول ما تفعله الأداة، ووصفٌ مفصّل (ثلاث جملٍ أو أربع على الأقل) يقول
    ما تعيده ومتى تُستدعى ومتى لا وحدودها، ووصفٌ لكل مدخل، و`strict` بـ`additionalProperties: false`.
    """
    definition = assistant.TOOLS[name].definition()
    assert set(definition) == {"name", "description", "input_schema", "strict"} and definition["strict"] is True
    assert re.fullmatch(r"[a-z]+(_[a-z]+)+", definition["name"]) and len(definition["name"]) <= 64
    description = definition["description"]
    assert len(re.findall(r"[.؟!]", description)) >= 3, "ثلاث جملٍ على الأقل"
    assert "استدعِها حين" in description or "استدعِها كلما" in description, "متى تُستدعى"
    assert "لا " in description, "ما لا تعيده أو حدودها"
    schema = definition["input_schema"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema.get("required", []) == list(schema["properties"])
    for key, prop in schema["properties"].items():
        assert re.fullmatch(r"[a-z]+(_[a-z]+)*", key) and prop.get("description"), key
    if not schema["properties"]:
        assert "لا تحتاج مدخلاً" in description


@pytest.mark.parametrize(("tool_input", "lines", "shown"), [
    ({"amount_sar": 115, "basis": "both"},
     ("115.00 ر.س قبل الضريبة: الضريبة 17.25 ر.س، والإجمالي 132.25 ر.س.",
      "115.00 ر.س شاملةً الضريبة: قبلها 100.00 ر.س، والضريبة 15.00 ر.س."), "115 ريال"),
    ({"amount_sar": 1000.5, "basis": "before_vat"},
     ("1,000.50 ر.س قبل الضريبة: الضريبة 150.08 ر.س، والإجمالي 1,150.58 ر.س.",), "1000.5 ريال، قبل الضريبة"),
    ({"amount_sar": 115, "basis": "including_vat"},
     ("115.00 ر.س شاملةً الضريبة: قبلها 100.00 ر.س، والضريبة 15.00 ر.س.",), "115 ريال، شاملاً الضريبة"),
])
def test_the_calculator_answers_the_basis_it_is_asked(tool_input, lines, shown):
    tool = assistant.TOOLS["calculate_vat"]
    assert tool.run(None, None, tool_input) == lines and tool.shown(tool_input) == shown


@pytest.mark.parametrize("amount", [0, -5, 100000000.01])
def test_an_amount_the_calculator_cannot_take_is_an_instructive_error(amount):
    """خطأ المدخل يقول ما الخطأ وما يُجرَّب بعده («Handle tool calls»: رسائل خطأٍ تعليمية)، ويعود بـis_error."""
    with pytest.raises(ToolError, match="من 0.01 إلى مئة مليون ريال"):
        assistant.TOOLS["calculate_vat"].run(None, None, {"amount_sar": amount, "basis": "both"})


def test_the_campaigns_tool_says_when_older_campaigns_exist():
    row = {"status": "COPY_PROPOSED", "title": "حقيبة", "budget_sar": 500, "days": 7, "updated": date(2026, 10, 9)}
    cursor = Rows([row] * 9)
    lines = assistant.TOOLS["list_campaigns"].run(cursor, None, {})
    assert len(lines) == 9 and lines[-1] == "هذه أحدث 8 حملات؛ وفي «حملاتي» حملاتٌ أقدم."
    assert cursor.executed[0][1] == (9,)
    assert assistant.TOOLS["list_campaigns"].run(Rows([row]), None, {})[-1].endswith("(آخر تعديل 2026-10-09)")


def test_the_items_tool_asks_for_a_query_and_says_when_more_match():
    tool = assistant.TOOLS["search_items"]
    with pytest.raises(ToolError, match="اكتب اسم المنتج"):
        tool.run(Rows([]), None, {"query": "  "})
    item = {"name": "ماء 330 مل", "number": 3, "supplier_code": None, "kind": "STOCK", "on_hand_milli": 12000,
            "unit": "PCE", "reorder_level_milli": None, "last_price_halalas": None}
    cursor = Rows([item] * 6)
    lines = tool.run(cursor, None, {"query": "ماء"})
    assert len(lines) == 6 and lines[-1] == "تطابق «ماء» أكثر من 5 منتجات: ابحث بكلمةٍ أدقّ أو بالرمز."
    assert cursor.executed[0][1][-1] == 6
    assert tool.run(Rows([]), None, {"query": "ماء"}) == (
        "لا منتج نشطاً يطابق «ماء». جرّب كلمةً أقصر من الاسم، أو الرمز أو الباركود.",)
    assert tool.shown({"query": "ماء"}) == "ماء"


def test_the_low_stock_tool_says_when_more_are_under_their_level():
    row = {"name": "ماء", "unit": "PCE", "on_hand_milli": 1000, "reorder_level_milli": 5000, "target_level_milli": None}
    lines = assistant.TOOLS["list_low_stock_items"].run(Rows([row] * 9), None, {})
    assert len(lines) == 9 and lines[-1] == "هذه أبعد 8 منتجات تحت حدّها؛ وفي «المخزون» غيرها."


def test_the_purchases_tool_reads_no_supplier_name():
    """ما يُرسَل من المخزون بنود الفواتير وأسماء الأصناف؛ أسماء المورّدين لا تصل سيمبول (README)."""
    assert "supplier" not in inventory._TOOL_PURCHASES
    cursor = Rows([{"number": 7, "invoice_date": date(2026, 10, 9), "printed_total_halalas": 11500, "lines": 3}])
    (line,) = assistant.TOOLS["list_recent_purchases"].run(cursor, None, {})
    assert line.startswith("فاتورة ") and "بتاريخ 2026-10-09، 3 أسطر، إجماليها المطبوع 115.00 ر.س" in line
    assert assistant.TOOLS["list_recent_purchases"].run(Rows([]), None, {}) == ("لا فاتورة شراءٍ مسجّلة بعد.",)


def test_the_knowledge_tool_needs_words_and_shortens_a_long_resolution():
    tool = assistant.TOOLS["search_knowledge_base"]
    with pytest.raises(ToolError, match="بكلمتين على الأقل"):
        tool.run(Rows([]), None, {"query": " "})
    long = "أعد تشغيل الطابعة " * 30
    cursor = Rows([{"number": 4, "title": "الطابعة", "issue": "تطبع\nصفحاتٍ فارغة", "resolution": long}])
    (line,) = tool.run(cursor, None, {"query": "الطابعة"})
    head, resolution = line.split(" — الحلّ: ")
    assert head == "KB-4 «الطابعة»: تطبع صفحاتٍ فارغة"
    assert resolution.endswith("…") and len(resolution) <= 221
    assert cursor.executed[0][1] == ("الطابعة", 3)
    assert tool.run(Rows([]), None, {"query": "الطابعة"}) == (
        "لا مقالة منشورة تطابق «الطابعة». جرّب كلماتٍ أقلّ أو مرادفة مرةً واحدة.",)


def test_the_desk_tool_reads_the_counts_only():
    cursor = Rows([{"decide": 2, "open": 5, "pending": 1, "escalated": 0, "kb_attention": 3}])
    assert assistant.TOOLS["get_desk_counts"].run(cursor, None, {}) == (
        "بانتظار قرارك: 2، والتذاكر المفتوحة: 5، وبانتظار العميل: 1، والمُصعَّدة: 0، ومقالاتٌ تحتاج مراجعة: 3",)
    assert [statement for statement, _ in cursor.executed] == [support._COUNTS]
