#!/usr/bin/env bash
# Scratch verification for the support-desk migration. Usage: db.sh fresh|up|down|dump <file>|psql
set -euo pipefail
DB=support_spec_check
DIR=design/support_sql
export PGPASSWORD=eyework_dev_owner
OWN="psql -qX -v ON_ERROR_STOP=1 -h localhost -U eyework_owner -d $DB"
case "$1" in
  fresh)
    su postgres -c "psql -qX -c 'DROP DATABASE IF EXISTS $DB'" >/dev/null
    su postgres -c "psql -qX -c 'CREATE DATABASE $DB OWNER eyework_owner'" >/dev/null
    for m in 0001_identity 0002_campaigns 0003_persona 0004_image_activity 0005_registration 0006_passkeys 0007_open_registration; do
      $OWN -1 -f "$DIR/base/$m.up.sql" >/dev/null
    done
    echo "base 0001-0007 applied";;
  up)   $OWN -1 -f "$DIR/NEXT_support_desk.up.sql" >/dev/null && echo "NEXT up";;
  down) $OWN -1 -f "$DIR/NEXT_support_desk.down.sql" >/dev/null && echo "NEXT down";;
  basedown)
    for m in 0007_open_registration 0006_passkeys 0005_registration 0004_image_activity 0003_persona 0002_campaigns 0001_identity; do
      $OWN -1 -f "$DIR/base/$m.down.sql" >/dev/null
    done; echo "base down";;
  baseup)
    for m in 0001_identity 0002_campaigns 0003_persona 0004_image_activity 0005_registration 0006_passkeys 0007_open_registration; do
      $OWN -1 -f "$DIR/base/$m.up.sql" >/dev/null
    done; echo "base up";;
  dump) su postgres -c "pg_dump --schema-only -d $DB" | grep -v '^--' | grep -v '^$' | grep -v '^.\(un\)\{0,1\}restrict ' > "$2"; echo "dumped $2";;
  drop) su postgres -c "psql -qX -c 'DROP DATABASE IF EXISTS $DB'" >/dev/null; echo dropped;;
esac
