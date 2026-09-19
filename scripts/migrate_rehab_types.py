#!/usr/bin/env python3
"""
ترحيل مفردات rehabilitation_type في ملفات المرضى القائمة.
=========================================================
تدقيق المرحلة 0 — ح-2: كانت قائمة الواجهة تنتج مفاتيح طويلة
(`musculoskeletal`/`neurological`/`cardiopulmonary`) بينما يقارن كل
المستهلكين بمفاتيح قصيرة (`orthopedic`/`neuro`/`cardiac`). النتيجة أن حقل
«الجانب المصاب» وتصنيف NYHA ودرجة الألم لم تكن تظهر أو تدخل سياق النموذج.

يعمل في الاتجاهين. الاستخدام:
    python3 scripts/migrate_rehab_types.py up   [--dry-run]
    python3 scripts/migrate_rehab_types.py down [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

PATIENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "patients"

UP = {
    "musculoskeletal": "orthopedic",
    "neurological": "neuro",
    "cardiopulmonary": "cardiac",
}
DOWN = {v: k for k, v in UP.items()}


def _iter_patient_files(directory: Path):
    if not directory.exists():
        return
    yield from sorted(directory.glob("*.json"))


def migrate(direction: str, directory: Path, dry_run: bool) -> int:
    mapping = UP if direction == "up" else DOWN
    changed = 0

    for path in _iter_patient_files(directory):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[تخطٍّ] {path.name}: {type(exc).__name__}", file=sys.stderr)
            continue

        edits = []

        current = record.get("rehabilitation_type")
        if current in mapping:
            record["rehabilitation_type"] = mapping[current]
            edits.append(f"rehabilitation_type: {current} → {mapping[current]}")

        # الخطط المضمّنة تحمل نسختها الخاصة من الحقل
        for index, plan in enumerate(record.get("treatment_plans", [])):
            if isinstance(plan, dict) and plan.get("rehabilitation_type") in mapping:
                before = plan["rehabilitation_type"]
                plan["rehabilitation_type"] = mapping[before]
                edits.append(f"treatment_plans[{index}]: {before} → {mapping[before]}")

        if not edits:
            continue

        changed += 1
        print(f"{'[معاينة] ' if dry_run else ''}{path.name}")
        for edit in edits:
            print(f"    {edit}")
        if not dry_run:
            path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("up", "down"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dir", type=Path, default=PATIENTS_DIR)
    args = parser.parse_args()

    changed = migrate(args.direction, args.dir, args.dry_run)
    verb = "ستتغير" if args.dry_run else "تغيّرت"
    print(f"\n{verb} {changed} ملف/ملفات في {args.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
