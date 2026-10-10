"""
أدوات سيمبول بلا قاعدة: ما تكتبه كل أداةٍ من صفوفٍ معطاة، وما لا تقرؤه أصلاً. الأدوات تعمل بهوية
الجلسة وتحت العزل (اختبار الواجهة البرمجية)؛ وهنا شكل أسطرها وحدودها.
"""

from __future__ import annotations

from datetime import date

import pytest

from eyework import assistant, inventory, support
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
        "VAT": None, "CAMPAIGNS": Profession.MARKETING,
        "ITEMS": Profession.STOREKEEPER, "LOW_STOCK": Profession.STOREKEEPER, "PURCHASES": Profession.STOREKEEPER,
        "KB": Profession.SUPPORT, "DESK": Profession.SUPPORT,
    }
    assert [tool.name for tool in assistant.tools_for(Profession.SUPPORT)] == ["VAT", "KB", "DESK"]


@pytest.mark.parametrize(("text", "lines"), [
    ("١١٥ ريال", ("115.00 ر.س قبل الضريبة: الضريبة 17.25 ر.س، والإجمالي 132.25 ر.س.",
                 "115.00 ر.س شاملةً الضريبة: قبلها 100.00 ر.س، والضريبة 15.00 ر.س.")),
    ("1,000.5", ("1,000.50 ر.س قبل الضريبة: الضريبة 150.08 ر.س، والإجمالي 1,150.58 ر.س.",
                 "1,000.50 ر.س شاملةً الضريبة: قبلها 870.00 ر.س، والضريبة 130.50 ر.س.")),
    ("مئة", ("لم يُفهم المبلغ: يُكتب رقماً بالريال، مثل 115.",)),
    ("0", ("المبلغ خارج ما تحسبه الأداة (من هللةٍ إلى مئة مليون ريال).",)),
])
def test_the_calculator_reads_the_amount_and_answers_both_ways(text, lines):
    assert assistant.TOOLS["VAT"].run(None, None, text) == lines


def test_the_purchases_tool_reads_no_supplier_name():
    """ما يُرسَل من المخزون بنود الفواتير وأسماء الأصناف؛ أسماء المورّدين لا تصل سيمبول (README)."""
    assert "supplier" not in inventory._TOOL_PURCHASES
    cursor = Rows([{"number": 7, "invoice_date": date(2026, 10, 9), "printed_total_halalas": 11500, "lines": 3}])
    (line,) = assistant.TOOLS["PURCHASES"].run(cursor, None, "")
    assert line.startswith("فاتورة ") and "بتاريخ 2026-10-09، 3 أسطر، إجماليها المطبوع 115.00 ر.س" in line
    assert assistant.TOOLS["PURCHASES"].run(Rows([]), None, "") == ("لا فاتورة شراءٍ مسجّلة بعد.",)


def test_the_knowledge_tool_needs_words_and_shortens_a_long_resolution():
    assert assistant.TOOLS["KB"].run(Rows([]), None, " ") == ("يُكتب ما يُبحث عنه بكلمتين على الأقل.",)
    long = "أعد تشغيل الطابعة " * 30
    cursor = Rows([{"number": 4, "title": "الطابعة", "issue": "تطبع\nصفحاتٍ فارغة", "resolution": long}])
    (line,) = assistant.TOOLS["KB"].run(cursor, None, "الطابعة")
    head, resolution = line.split(" — الحلّ: ")
    assert head == "KB-4 «الطابعة»: تطبع صفحاتٍ فارغة"
    assert resolution.endswith("…") and len(resolution) <= 221
    assert cursor.executed[0][1] == ("الطابعة", 3)


def test_the_desk_tool_reads_the_counts_only():
    cursor = Rows([{"decide": 2, "open": 5, "pending": 1, "escalated": 0, "kb_attention": 3}])
    assert assistant.TOOLS["DESK"].run(cursor, None, "أيّ شيء") == (
        "بانتظار قرارك: 2، والتذاكر المفتوحة: 5، وبانتظار العميل: 1، والمُصعَّدة: 0، ومقالاتٌ تحتاج مراجعة: 3",)
    assert [statement for statement, _ in cursor.executed] == [support._COUNTS]
