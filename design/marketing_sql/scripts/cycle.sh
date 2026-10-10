#!/usr/bin/env bash
# NEXT_marketing on a scratch database with the repo's own runner, from an export of origin/main (not a worktree).
#   0001-0006 (main) + NEXT_open_registration as 0007 + NEXT_marketing as 0008.
#   up to 0007, snapshot; up, snapshot; down to 0007, snapshot; up, snapshot; down --all, snapshot; up, snapshot.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
RED=$(cd "$HERE/.." && pwd)
BASE="$HERE/base"
DB=mkt_spec_test
OUT="$HERE/evidence"
mkdir -p "$OUT"
export EYEWORK_OWNER_DATABASE_URL="postgresql://eyework_owner:eyework_dev_owner@localhost:5432/$DB"
export PYTHONPATH="$BASE"
run() { (cd "$BASE" && python3 -m eyework.migrations.run "$@"); }
snap() { pg_dump --schema-only --dbname "$EYEWORK_OWNER_DATABASE_URL" | grep -v '^\\\(un\)\?restrict ' > "$1"; }
same() { diff -q "$1" "$2" >/dev/null && echo identical || echo DIFFERENT; }

su postgres -c "psql -p 5432 -qtAX -c 'DROP DATABASE IF EXISTS $DB WITH (FORCE)'"
su postgres -c "psql -p 5432 -qtAX -c 'CREATE DATABASE $DB OWNER eyework_owner'"
cp "$RED/registration_sql/next/NEXT_open_registration.up.sql"   "$BASE/eyework/migrations/0007_open_registration.up.sql"
cp "$RED/registration_sql/next/NEXT_open_registration.down.sql" "$BASE/eyework/migrations/0007_open_registration.down.sql"
cp "$HERE/NEXT_marketing.up.sql"   "$BASE/eyework/migrations/0008_marketing.up.sql"
cp "$HERE/NEXT_marketing.down.sql" "$BASE/eyework/migrations/0008_marketing.down.sql"

run up --to 0007;          snap "$OUT/s7.sql"
run up;                    snap "$OUT/s8.sql"
run down --to 0007;        snap "$OUT/s7b.sql"
run up;                    snap "$OUT/s8b.sql"
run down --all;            snap "$OUT/s0.sql"
run up;                    snap "$OUT/s8c.sql"
run status | tail -3

echo "down to 0007 restores 0007:   $(same "$OUT/s7.sql" "$OUT/s7b.sql")"
echo "up again matches first up:    $(same "$OUT/s8.sql" "$OUT/s8b.sql")"
echo "from empty matches first up:  $(same "$OUT/s8.sql" "$OUT/s8c.sql")"
echo "NEXT changes the schema:      $( diff -q "$OUT/s7.sql" "$OUT/s8.sql" >/dev/null && echo yes-no-change || echo yes)"
