"""
تسميات العميل لرموز مكتب الدعم تطابق رموز القاعدة (0011): رمزٌ يُضاف إلى القاعدة بلا تسميةٍ في
`client/src/lib/support.ts` يظهر للموظف فارغاً، ورمزٌ في العميل لا تعرفه القاعدة لا يُحفظ.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "migrations" / "0011_support_desk.up.sql").read_text(encoding="utf-8")
TS = (ROOT / "client" / "src" / "lib" / "support.ts").read_text(encoding="utf-8")


def sql_codes(constraint: str) -> set[str]:
    """القيم في أول «IN (…)» بعد اسم القيد."""
    match = re.search(rf"CONSTRAINT {constraint}\b.*?\bIN\s*\(([^)]*)\)", SQL, re.DOTALL)
    assert match, constraint
    return {quoted or number for quoted, number in re.findall(r"'([A-Z0-9_]+)'|\b(\d+)\b", match.group(1))}


def ts_keys(name: str) -> set[str]:
    """مفاتيح `export const NAME: Record<…> = { … }` (أو `{ ...OTHER, … }`)."""
    match = re.search(rf"export const {name}: Record<[^>]+> = \{{(.*?)\}}\n", TS, re.DOTALL)
    assert match, name
    body = re.sub(r'"[^"]*"', '""', match.group(1))
    keys = set(re.findall(r"\b([A-Z][A-Z0-9_]*|\d+)\s*:", body))
    for spread in re.findall(r"\.\.\.([A-Z_]+)", body):
        keys |= ts_keys(spread)
    return keys


@pytest.mark.parametrize(("labels", "constraint", "server_only"), [
    ("STATUS", "support_ticket_status", set()),
    ("PRIORITY", "support_ticket_priority", set()),
    ("CHANNEL", "support_ticket_channel", set()),
    ("CATEGORY", "support_draft_category", set()),
    ("REPLY_KIND", "support_reply_kind", set()),
    ("REJECT_REASON", "support_draft_reject_reason", set()),
    ("ESCALATION_TARGET", "support_escalation_to", set()),
    # «REPLIED» تكتبه «نعم، أرسلته»؛ المنتقي يعرض طرق الحلّ بلا ردٍّ وحدها.
    ("RESOLUTION", "support_resolution", {"REPLIED"}),
    ("DISMISSED_REASON", "support_flag_dismiss", set()),
    ("ARTICLE_STATE", "kb_article_state", set()),
    ("AUTHOR", "support_message_author", set()),
    ("REVIEW_REASON", "kb_review_reason", set()),
    ("SLA_FIRST", "support_sla_first", set()),
    ("SLA_RESOLVE", "support_sla_resolve", set()),
])
def test_every_database_code_has_a_client_label(labels, constraint, server_only):
    assert ts_keys(labels) == sql_codes(constraint) - server_only


def test_the_dismiss_picker_offers_only_what_the_employee_chooses():
    assert ts_keys("DISMISS_REASON") == sql_codes("support_flag_dismiss") - {"CONFIRMED"}
