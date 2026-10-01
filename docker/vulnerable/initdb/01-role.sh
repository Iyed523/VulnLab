#!/bin/sh
(
set -eu
: "${APP_DB_PASSWORD:?Missing fictitious application password}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE vulnlab_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE vulnlab FROM PUBLIC;
GRANT CONNECT ON DATABASE vulnlab TO vulnlab_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO vulnlab_app;
SQL
)
