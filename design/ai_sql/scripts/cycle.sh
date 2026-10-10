#!/usr/bin/env bash
# NEXT_ai_layer (as 0008) on top of main 0001-0006 and NEXT_open_registration (as 0007), with the
# repo's own runner, in a scratch database. Compares pg_dump --schema-only snapshots:
#   0007 -> 0008 up -> down -> up again; full rollback to empty -> up.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
WT="$HERE/wt"
DB=ai_spec_check
OUT="$HERE/evidence"
mkdir -p "$OUT"
cp "$HERE/NEXT_ai_layer.up.sql"   "$WT/eyework/migrations/0008_ai_layer.up.sql"
cp "$HERE/NEXT_ai_layer.down.sql" "$WT/eyework/migrations/0008_ai_layer.down.sql"
export EYEWORK_OWNER_DATABASE_URL="postgresql://eyework_owner:eyework_dev_owner@localhost:5432/$DB"
export PYTHONPATH="$WT"
run() { (cd "$WT" && python3 -m eyework.migrations.run "$@"); }
snap() { pg_dump --schema-only --dbname "$EYEWORK_OWNER_DATABASE_URL" | grep -v '^\\\(un\)\?restrict ' > "$1"; }
same() { diff -q "$1" "$2" >/dev/null && echo identical || echo DIFFERENT; }

su postgres -c "psql -p 5432 -qtAX -c 'DROP DATABASE IF EXISTS $DB WITH (FORCE)'"
su postgres -c "psql -p 5432 -qtAX -c 'CREATE DATABASE $DB OWNER eyework_owner'"

run up --to 0007;           snap "$OUT/s7.sql"
run up;                     snap "$OUT/s8.sql"
run down --to 0007;         snap "$OUT/s7b.sql"
run up;                     snap "$OUT/s8b.sql"
run down --all;             snap "$OUT/s0.sql"
run up;                     snap "$OUT/s8c.sql"
run status | tail -3

echo "down to 0007 restores 0007:   $(same "$OUT/s7.sql" "$OUT/s7b.sql")"
echo "up again matches first up:    $(same "$OUT/s8.sql" "$OUT/s8b.sql")"
echo "from empty matches first up:  $(same "$OUT/s8.sql" "$OUT/s8c.sql")"
echo "0008 changes the schema:      $( diff -q "$OUT/s7.sql" "$OUT/s8.sql" >/dev/null && echo no || echo yes)"
