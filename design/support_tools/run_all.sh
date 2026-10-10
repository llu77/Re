#!/usr/bin/env bash
# Reproduces every check cited in support_spec.md §4.6 on a scratch database, then drops it.
set -uo pipefail
R=design
S=$R/support_sql; C=$S/checks; T=$R/support_tools/db.sh; O=$S/dumps
export PGPASSWORD=eyework_dev_owner
OWN="psql -qX -v ON_ERROR_STOP=1 -h localhost -U eyework_owner -d support_spec_check"
APP() { PGPASSWORD=eyework_dev_app psql -qX -h localhost -U eyework_app -d support_spec_check "$@"; }
echo "== cycle"; bash $T fresh >/dev/null; bash $T dump $O/A_base.sql >/dev/null; bash $T up >/dev/null; bash $T dump $O/B_up1.sql >/dev/null
bash $T down >/dev/null; bash $T dump $O/C_down.sql >/dev/null; bash $T up >/dev/null; bash $T dump $O/D_up2.sql >/dev/null
diff -q $O/A_base.sql $O/C_down.sql >/dev/null && echo "down restores base exactly" || echo "FAIL down"
diff -q $O/B_up1.sql $O/D_up2.sql >/dev/null && echo "second up identical to first" || echo "FAIL up2"
bash $T down >/dev/null; bash $T basedown >/dev/null; bash $T baseup >/dev/null; bash $T up >/dev/null; bash $T dump $O/F_full.sql >/dev/null
diff -q $O/B_up1.sql $O/F_full.sql >/dev/null && echo "rebuild from empty identical" || echo "FAIL rebuild"
echo "== functional (eyework_app)"
$OWN -f $C/00_owner_setup.sql -c "GRANT TEMPORARY ON DATABASE support_spec_check TO eyework_app"
APP -At -f $C/10_app_checks.sql 2>&1 | grep -E '^\|?[0-9]+\|(PASS|FAIL)' | cut -d'|' -f2 | sort | uniq -c
APP -At -f $C/15_app_more.sql 2>&1 | grep -E '^[0-9]+\|(PASS|FAIL)' | cut -d'|' -f2 | sort | uniq -c
echo "== close, follow-up, purge-at-once, cap, delete"
$OWN -f $C/20_owner_checks.sql; APP -At -f $C/25_app_close.sql 2>&1 | grep -o "PASS.*\|FAIL.*\|^CLOSED.*\|^[0-9]|.*\|^t$"
$OWN -At -f $C/30_owner_purge.sql; APP -f $C/35_app_cap.sql 2>&1 | grep -o 'PASS.*\|FAIL.*'
$OWN -f $C/40_owner_delete.sql; APP -At -f $C/45_app_delete.sql >/dev/null; $OWN -At -f $C/50_owner_after_delete.sql
echo "== set-profession away from SUPPORT"
$OWN -At -f $C/80_owner_set_profession.sql; APP -f $C/81_app_after_profession.sql 2>&1 | grep -o "PASS.*\|FAIL.*"
echo "== purge.sql in three passes (fresh data)"
bash $T fresh >/dev/null; bash $T up >/dev/null
$OWN -f $C/00_owner_setup.sql -c "GRANT TEMPORARY ON DATABASE support_spec_check TO eyework_app"
APP -At -f $C/10_app_checks.sql >/dev/null 2>&1; APP -At -f $C/15_app_more.sql >/dev/null 2>&1
echo "tickets|closed|purged|msgs|drafts|replies|live|events|calls|kb"; $OWN -At -f $C/73_owner_counts.sql
$OWN -f $C/70_owner_backdate.sql; $OWN -1 -f $S/purge.sql; $OWN -At -f $C/73_owner_counts.sql
$OWN -f $C/71_owner_backdate2.sql; $OWN -1 -f $S/purge.sql; $OWN -At -f $C/73_owner_counts.sql
$OWN -f $C/72_owner_backdate3.sql; $OWN -1 -f $S/purge.sql; $OWN -At -f $C/73_owner_counts.sql
echo "== down with data"
$OWN -c "REVOKE TEMPORARY ON DATABASE support_spec_check FROM eyework_app"
bash $T down >/dev/null; bash $T dump $O/G_down_with_data.sql >/dev/null
diff -q $O/A_base.sql $O/G_down_with_data.sql >/dev/null && echo "down with live data restores base exactly" || echo "FAIL down with data"
echo "== race"
bash $T fresh >/dev/null; bash $T up >/dev/null; $OWN -f $C/00_owner_setup.sql
APP -At -f $C/60_race_setup.sql >/dev/null
(APP -At -f $C/61_race_a.sql 2>&1 | grep -E '^t$' | sed 's/^/A opened: /' &)
APP -At -f $C/62_race_b.sql 2>&1 | grep -o 'ERROR:  busy' | sed 's/^/B: /'
sleep 3; $OWN -At -c "SELECT 'open calls after race: ' || count(*) FROM support_ai_calls"
bash $T drop
