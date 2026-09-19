#!/usr/bin/env bash
# قاعدة بيانات تطوير محلية
# ========================
# تُشغّل عنقود PostgreSQL محلياً وتُهيّئ قاعدة التطبيق وأدواره.
# بيئة التطوير هنا بلا Docker، ولهذا لا نستخدم testcontainers.
# في CI تأتي القاعدة جاهزة كخدمة، ويُتجاوز هذا السكربت.
#
#   scripts/dev_db.sh start | stop | reset | dsn
set -euo pipefail

PGVERSION="${PGVERSION:-16}"
CLUSTER="${PGCLUSTER:-main}"
DB_NAME="${SYMBOL_DB_NAME:-symbol_rehab}"
DB_USER="${SYMBOL_DB_USER:-symbol_owner}"
DB_PASSWORD="${SYMBOL_DB_PASSWORD:-symbol_dev}"
PORT="${SYMBOL_DB_PORT:-5432}"

as_postgres() { su postgres -c "$1"; }

dsn() { echo "postgresql://$DB_USER:$DB_PASSWORD@localhost:$PORT/$DB_NAME"; }

start_cluster() {
    if pg_isready -q -p "$PORT" 2>/dev/null; then
        echo "العنقود يعمل على المنفذ $PORT"
        return
    fi
    pg_ctlcluster "$PGVERSION" "$CLUSTER" start
    # pg_isready يتراجع تلقائياً؛ لا حاجة لحلقة انتظار
    pg_isready -q -t 30 -p "$PORT"
    echo "بدأ العنقود $PGVERSION/$CLUSTER على المنفذ $PORT"
}

ensure_database() {
    as_postgres "psql -qtAX -p $PORT -c \"SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'\"" \
        | grep -q 1 || as_postgres \
        "psql -qX -p $PORT -c \"CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' CREATEROLE\""

    as_postgres "psql -qtAX -p $PORT -c \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
        | grep -q 1 || as_postgres \
        "psql -qX -p $PORT -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER\""

    echo "القاعدة $DB_NAME جاهزة بمالك $DB_USER"
}

case "${1:-start}" in
    start)
        start_cluster
        ensure_database
        echo "DSN: $(dsn)"
        ;;
    stop)
        pg_ctlcluster "$PGVERSION" "$CLUSTER" stop || true
        ;;
    reset)
        start_cluster
        as_postgres "psql -qX -p $PORT -c \"DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)\""
        ensure_database
        ;;
    dsn) dsn ;;
    *)
        echo "الاستخدام: $0 {start|stop|reset|dsn}" >&2
        exit 2
        ;;
esac

exit 0
