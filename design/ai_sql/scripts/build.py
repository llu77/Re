"""Assemble NEXT_ai_layer.up.sql and .down.sql.

The one function both files carry, ew_begin_generation, is taken from the open-registration
migration verbatim: the up replaces exactly its two cap conditions with ew_ai_spend, the down
restores the original text byte for byte. Nothing in it is retyped.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "src"
ORIGINAL = (SRC / "begin_generation_registration.sql").read_text(encoding="utf-8")

GLOBAL_OLD = """    IF (SELECT count(*) FROM generation_attempts
         WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN"""
GLOBAL_NEW = """    -- ai_layer: السقف العام يعدّ استدعاءات الأدوات الأخرى (ai_requests) مع المحاولات وآثارها.
    IF ew_ai_spend(false) >= 2000 THEN"""
NEW_OLD = """    IF fresh AND (SELECT count(*) FROM generation_attempts
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN"""
NEW_NEW = """    -- ai_layer: وكذلك استدعاءات الأدوات الأخرى من حساباتٍ جديدة.
    IF fresh AND ew_ai_spend(true) >= 400 THEN"""

assert ORIGINAL.count(GLOBAL_OLD) == 1 and ORIGINAL.count(NEW_OLD) == 1
replaced = ORIGINAL.replace(GLOBAL_OLD, GLOBAL_NEW).replace(NEW_OLD, NEW_NEW)

up = (SRC / "up.template.sql").read_text(encoding="utf-8")
assert up.count("--@@BEGIN_GENERATION@@") == 1
(HERE / "NEXT_ai_layer.up.sql").write_text(up.replace("--@@BEGIN_GENERATION@@", replaced.rstrip("\n")),
                                            encoding="utf-8")

down = (SRC / "down.template.sql").read_text(encoding="utf-8")
assert down.count("--@@BEGIN_GENERATION@@") == 1
(HERE / "NEXT_ai_layer.down.sql").write_text(down.replace("--@@BEGIN_GENERATION@@", ORIGINAL.rstrip("\n")),
                                              encoding="utf-8")
print("built", HERE / "NEXT_ai_layer.up.sql", HERE / "NEXT_ai_layer.down.sql")
