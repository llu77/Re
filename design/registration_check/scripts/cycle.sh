#!/usr/bin/env bash
# up 0001..0006 from the repo, then 0007 up/down/up from the scratch dir; compare pg_dump snapshots.
set -euo pipefail
W="$1"; REPO=/home/user/Re/eyework/migrations; DB=regspec0007_check
DSN="postgresql://eyework_owner:eyework_dev_owner@localhost:5432/$DB"
su postgres -c "psql -qtAX -c \"DROP DATABASE IF EXISTS $DB WITH (FORCE)\""
su postgres -c "psql -qtAX -c \"CREATE DATABASE $DB OWNER eyework_owner\""
apply() { psql "$DSN" -qX -v ON_ERROR_STOP=1 --single-transaction -f "$1" >/dev/null; }
snap() { pg_dump --schema-only --create --dbname "$DSN" | grep -v '^\\\(un\)\?restrict ' > "$1"; }
for f in 0001_identity 0002_campaigns 0003_persona 0004_image_activity 0005_registration 0006_passkeys; do
  apply "$REPO/$f.up.sql"
done
snap "$W/s6.sql"
apply "$W/migrations/0007_open_registration.up.sql"; snap "$W/s7.sql"
apply "$W/migrations/0007_open_registration.down.sql"; snap "$W/s6b.sql"
apply "$W/migrations/0007_open_registration.up.sql"; snap "$W/s7b.sql"
echo "down restores 0006: $(diff -q "$W/s6.sql" "$W/s6b.sql" >/dev/null && echo identical || echo DIFFERENT)"
echo "up again matches:   $(diff -q "$W/s7.sql" "$W/s7b.sql" >/dev/null && echo identical || echo DIFFERENT)"
echo "0007 changes schema: $(diff -q "$W/s6.sql" "$W/s7.sql" >/dev/null && echo no || echo yes)"
