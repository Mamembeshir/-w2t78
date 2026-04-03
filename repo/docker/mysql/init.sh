#!/bin/bash
# docker/mysql/init.sh
# Runs after MySQL creates the primary database and user via env vars.
# Creates the test database and grants the application user access to it.
set -e

# Fail fast if required env vars are missing — prevents silent SQL errors
[ -z "$MYSQL_ROOT_PASSWORD" ] && echo "ERROR: MYSQL_ROOT_PASSWORD is not set" && exit 1
[ -z "$MYSQL_DATABASE" ]      && echo "ERROR: MYSQL_DATABASE is not set"      && exit 1
[ -z "$MYSQL_USER" ]          && echo "ERROR: MYSQL_USER is not set"           && exit 1

echo "[init.sh] Creating test database: ${MYSQL_DATABASE}_test"

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS \`${MYSQL_DATABASE}_test\`
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci;

    GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}_test\`.* TO '${MYSQL_USER}'@'%';

    -- Ensure primary database has correct charset
    ALTER DATABASE \`${MYSQL_DATABASE}\`
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci;

    FLUSH PRIVILEGES;
EOSQL

echo "[init.sh] Done. Databases ready: ${MYSQL_DATABASE}, ${MYSQL_DATABASE}_test"
