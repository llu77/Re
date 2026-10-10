#!/usr/bin/env bash
# The NEXT migration against a scratch database, with the repo's own runner from a worktree of main.
#   1. 0001-0006 up (runner), snapshot
#   2. NEXT up (as 0007), snapshot; down, snapshot; up again, snapshot
#   3. full rollback to empty and up again, snapshot
# Compares the pg_dump --schema-only snapshots. Leaves the database at NEXT for the checks.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
WT=reg_v2_main
DB=reg_v2_test
OUT="$HERE/evidence"
mkdir -p "$OUT"
export EYEWORK_OWNER_DATABASE_URL="postgresql://eyework_owner:eyework_dev_owner@localhost:5432/$DB"
export PYTHONPATH="$WT"
run() { (cd "$WT" && python3 -m eyework.migrations.run "$@"); }
snap() { pg_dump --schema-only --dbname "$EYEWORK_OWNER_DATABASE_URL" | grep -v '^\\\(un\)\?restrict ' > "$1"; }
same() { diff -q "$1" "$2" >/dev/null && echo identical || echo DIFFERENT; }

su postgres -c "psql -p 5432 -qtAX -c 'DROP DATABASE IF EXISTS $DB WITH (FORCE)'"
su postgres -c "psql -p 5432 -qtAX -c 'CREATE DATABASE $DB OWNER eyework_owner'"
cp "$HERE/next/NEXT_open_registration.up.sql"   "$WT/eyework/migrations/0007_open_registration.up.sql"
cp "$HERE/next/NEXT_open_registration.down.sql" "$WT/eyework/migrations/0007_open_registration.down.sql"

run up --to 0006;           snap "$OUT/s6.sql"
run up;                     snap "$OUT/s7.sql"
run down --to 0006;         snap "$OUT/s6b.sql"
run up;                     snap "$OUT/s7b.sql"
run down --all;             snap "$OUT/s0.sql"
run up;                     snap "$OUT/s7c.sql"
run status | tail -3

echo "down to 0006 restores 0006:   $(same "$OUT/s6.sql" "$OUT/s6b.sql")"
echo "up again matches first up:    $(same "$OUT/s7.sql" "$OUT/s7b.sql")"
echo "from empty matches first up:  $(same "$OUT/s7.sql" "$OUT/s7c.sql")"
echo "NEXT changes the schema:      $( diff -q "$OUT/s6.sql" "$OUT/s7.sql" >/dev/null && echo no || echo yes)"
