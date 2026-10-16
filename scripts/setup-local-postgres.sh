#!/bin/bash
# Separate project-local PostgreSQL cluster. Never changes Homebrew's existing cluster.
set -euo pipefail
cd "$(dirname "$0")/.."
pg_bin="${CANDOR_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
db_root="$PWD/.local/postgres"
db_user="$(id -un)"
mkdir -p "$db_root/socket"
if [ ! -f "$db_root/data/PG_VERSION" ]; then
  "$pg_bin/initdb" -D "$db_root/data" -U "$db_user" --auth=trust --no-locale -E UTF8
fi
if [ "$(cat "$db_root/data/PG_VERSION")" != "17" ]; then
  echo 'This script requires a PostgreSQL 17 cluster; existing data was preserved.' >&2
  exit 1
fi
if ! "$pg_bin/pg_ctl" -D "$db_root/data" status >/dev/null 2>&1; then
  "$pg_bin/pg_ctl" -D "$db_root/data" -l "$db_root/server.log" \
    -o "-p 5433 -h 127.0.0.1 -k '$db_root/socket'" -w start
fi
# Check this server is our cluster, not an unrelated process on the same port.
actual_dir="$($pg_bin/psql -h 127.0.0.1 -p 5433 -U "$db_user" -d postgres -Atc 'SHOW data_directory')"
if [ "$actual_dir" != "$db_root/data" ]; then
  echo 'Port 5433 belongs to another cluster; no database changes made.' >&2
  exit 1
fi
if [ "$($pg_bin/psql -h 127.0.0.1 -p 5433 -U "$db_user" -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = 'candor'")" != '1' ]; then
  "$pg_bin/createdb" -h 127.0.0.1 -p 5433 -U "$db_user" candor
fi
"$pg_bin/psql" -h 127.0.0.1 -p 5433 -U "$db_user" -d candor -v ON_ERROR_STOP=1 \
  -c 'CREATE EXTENSION IF NOT EXISTS vector;' \
  -c 'SELECT current_database(), current_user, version();'
if [ ! -f config/pipeline.local.yaml ]; then
  cat > config/pipeline.local.yaml <<EOF
# Separate local instance; ignored by Git.
postgres:
  database: candor
  host: 127.0.0.1
  port: 5433
  user: "$db_user"
  password: ""
EOF
fi
echo 'Separate database is ready on 127.0.0.1:5433.'
