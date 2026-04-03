#!/bin/bash
# docker/mysql/init.sh
# Runs after MySQL creates the primary database and user via env vars.
# Creates the test database and grants the application user access to it.
set -e

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
