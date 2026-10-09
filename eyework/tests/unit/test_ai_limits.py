"""
حدود الأدوات نظير الترحيل
=========================
صفوف `ai_features` في الترحيل 0009 تُقرأ من ملفّ SQL وتُقارن بـ`FEATURES`؛
وإعدادات الاستدعاء كما في المواصفة §2.2.
"""

from __future__ import annotations

import re
from pathlib import Path

from eyework import ai_limits
from eyework.ai_limits import ASSISTANT, DRAFT, FEATURES, REVIEW

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0009_ai_layer.up.sql"
_ROW = re.compile(r"\('([A-Z_]+)',\s*(NULL|'[A-Z]+'),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)")


def _rows_in_the_migration() -> dict:
    text = MIGRATION.read_text(encoding="utf-8")
    insert = text[text.index("INSERT INTO ai_features"):]
    insert = insert[:insert.index(";")]
    rows = {}
    for code, profession, *numbers in _ROW.findall(insert):
        rows[code] = (None if profession == "NULL" else profession.strip("'"), *map(int, numbers))
    return rows


def test_the_feature_limits_mirror_the_migration_rows():
    rows = _rows_in_the_migration()
    assert set(rows) == set(FEATURES)
    for code, limits in FEATURES.items():
        assert rows[code] == (limits.profession, limits.per_user_10min, limits.per_user_day,
                              limits.per_new_user_day, limits.app_day, limits.lease_seconds), code


def test_the_call_settings_follow_the_spec():
    assert (REVIEW.effort, REVIEW.max_tokens, REVIEW.deadline_seconds, REVIEW.stream) == ("low", 3000, 30.0, False)
    assert (ASSISTANT.effort, ASSISTANT.max_tokens, ASSISTANT.deadline_seconds, ASSISTANT.stream) == (
        "low", 3000, 25.0, False)
    assert (DRAFT.effort, DRAFT.max_tokens, DRAFT.deadline_seconds, DRAFT.stream) == ("medium", 8000, 120.0, True)
    assert ai_limits.REVIEW_WAIT_SECONDS == 12.0 and REVIEW.deadline_seconds > ai_limits.REVIEW_WAIT_SECONDS
    assert ai_limits.STREAM_TIMEOUT_SECONDS == 20.0
    assert (ai_limits.BREAKER_FAILURES, ai_limits.BREAKER_WINDOW_SECONDS, ai_limits.BREAKER_OPEN_SECONDS) == (
        3, 120.0, 60.0)
    assert re.fullmatch(r"[a-z0-9.-]{1,32}", REVIEW.prompt_version)
    assert re.fullmatch(r"[a-z0-9.-]{1,32}", ASSISTANT.prompt_version)


def test_every_lease_covers_its_deadline():
    """الاستدعاء ينتهي قبل عقده في القاعدة، وإلا رُفضت نتيجته الناجحة."""
    assert FEATURES["STOCK_REVIEW"].lease_seconds > REVIEW.deadline_seconds
    assert FEATURES["ASSISTANT"].lease_seconds > ASSISTANT.deadline_seconds
    assert FEATURES["SUPPORT_DRAFT"].lease_seconds > DRAFT.deadline_seconds
