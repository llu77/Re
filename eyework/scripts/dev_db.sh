#!/usr/bin/env bash
# قاعدة تطوير لتطبيق «صياغة»
# ===========================
# نسخةٌ من سكربت المنصّة بقيمٍ خاصة بهذا التطبيق: قاعدتان (للتطوير
# وللاختبار) ودوران، في العنقود المحلي نفسه لكن بلا أي منحٍ متبادل مع قاعدة
# المنصّة. في الإنتاج عنقودٌ مستقلّ، وفي CI خدمة postgres.
#
# الدوران يُنشآن هنا لا في الترحيل: ترحيلٌ يُنشئ دوراً بكلمة مرور مكتوبة
# فيه يترك في الإنتاج دوراً بكلمة مرورٍ منشورة إن نسي المشغّل إنشاءه أولاً.
# الترحيل هنا يشترط وجود `eyework_app` ويفشل بوضوح إن غاب.
#
#   bash eyework/scripts/dev_db.sh start | reset | dsn [db] | app-dsn [db]
set -euo pipefail

PGVERSION="${PGVERSION:-16}"
CLUSTER="${PGCLUSTER:-main}"
PORT="${EYEWORK_DB_PORT:-5432}"
OWNER="eyework_owner"
OWNER_PASSWORD="${EYEWORK_OWNER_PASSWORD:-eyework_dev_owner}"
APP="eyework_app"
APP_PASSWORD="${EYEWORK_APP_PASSWORD:-eyework_dev_app}"
DATABASES=("eyework" "eyework_test")

as_postgres() { su postgres -c "$1"; }
psql_q() { as_postgres "psql -qtAX -p $PORT -c \"$1\""; }

dsn() { echo "postgresql://$OWNER:$OWNER_PASSWORD@localhost:$PORT/${1:-eyework}"; }
app_dsn() { echo "postgresql://$APP:$APP_PASSWORD@localhost:$PORT/${1:-eyework}"; }

start_cluster() {
    if pg_isready -q -p "$PORT" 2>/dev/null; then
        return
    fi
    pg_ctlcluster "$PGVERSION" "$CLUSTER" start
    pg_isready -q -t 30 -p "$PORT"
}

ensure_role() {  # name password attributes
    psql_q "SELECT 1 FROM pg_roles WHERE rolname='$1'" | grep -q 1 \
        || psql_q "CREATE ROLE $1 LOGIN PASSWORD '$2' $3"
}

ensure_databases() {
    # المالك بلا CREATEROLE: لا يُنشئ أدواراً، يمنح ما يملكه فقط.
    ensure_role "$OWNER" "$OWNER_PASSWORD" "NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB"
    ensure_role "$APP" "$APP_PASSWORD" "NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB"
    for db in "${DATABASES[@]}"; do
        psql_q "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
            || psql_q "CREATE DATABASE $db OWNER $OWNER"
    done
}

case "${1:-start}" in
    start)
        start_cluster
        ensure_databases
        echo "DSN: $(dsn)"
        ;;
    reset)
        start_cluster
        for db in "${DATABASES[@]}"; do
            psql_q "DROP DATABASE IF EXISTS $db WITH (FORCE)"
        done
        ensure_databases
        ;;
    dsn) dsn "${2:-}" ;;
    app-dsn) app_dsn "${2:-}" ;;
    *)
        echo "الاستخدام: $0 {start|reset|dsn [db]|app-dsn [db]}" >&2
        exit 2
        ;;
esac
