"""
سجلٌّ بلا محتوى
===============
حقولٌ معدودة، وقيمٌ رموزٌ أو أرقام: نصٌّ حرّ لا يصل السجلّ ولو مرّره مستدعٍ.
"""

from __future__ import annotations

import logging

import pytest

from eyework import ai_log

CANARY = "CANARY-نصّ سرّي 0551234567"


def test_only_known_fields_are_accepted():
    with pytest.raises(TypeError):
        ai_log.event("x", question=CANARY)


def test_free_text_is_masked_and_none_is_omitted(caplog):
    caplog.set_level(logging.DEBUG, logger="eyework.ai")
    ai_log.event("model_call", feature="STOCK_REVIEW", outcome="OK", api_request_id=CANARY, served_model=None,
                 input_tokens=1200, drop_codes="REASON_LENGTH,LINE", latency_ms=12.5, masks=True)
    (record,) = caplog.records
    message = record.getMessage()
    assert CANARY not in message and "api_request_id=?" in message
    assert "feature=STOCK_REVIEW" in message and "outcome=OK" in message and "input_tokens=1200" in message
    assert "served_model" not in message and "drop_codes=REASON_LENGTH,LINE" in message and "masks=1" in message
    assert record.levelno == logging.INFO


def test_levels_are_honoured_and_the_event_name_is_a_code(caplog):
    caplog.set_level(logging.DEBUG, logger="eyework.ai")
    ai_log.event("upstream_rejected", level="critical", status=400)
    ai_log.event(CANARY, level="warning")
    assert [record.levelno for record in caplog.records] == [logging.CRITICAL, logging.WARNING]
    assert caplog.records[1].getMessage().startswith("? ")
