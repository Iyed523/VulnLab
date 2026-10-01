#!/bin/sh
(
set -eu
: "${APP_DB_PASSWORD:?Missing fictitious application password}"
: "${MIGRATION_DB_PASSWORD:?Missing fictitious migration password}"
# The same explicit operation supports existing volumes without deleting data.
PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_password="$APP_DB_PASSWORD" --set=migration_password="$MIGRATION_DB_PASSWORD" <<'SQL'
BEGIN;
SELECT format('CREATE ROLE vulnlab_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vulnlab_app')
\gexec
SELECT format('CREATE ROLE vulnlab_migrate LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'migration_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vulnlab_migrate')
\gexec
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('vulnlab_app', 'vulnlab_migrate')
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT FROM pg_auth_members WHERE member IN
                  (SELECT oid FROM pg_roles WHERE rolname IN ('vulnlab_app', 'vulnlab_migrate'))) THEN
        RAISE EXCEPTION 'Unexpected existing laboratory role privileges; operator review required';
    END IF;
END $$;
REVOKE ALL ON DATABASE vulnlab FROM PUBLIC;
GRANT CONNECT ON DATABASE vulnlab TO vulnlab_app, vulnlab_migrate;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM vulnlab_app;
GRANT USAGE ON SCHEMA public TO vulnlab_app;
GRANT USAGE, CREATE ON SCHEMA public TO vulnlab_migrate;
ALTER DEFAULT PRIVILEGES FOR ROLE vulnlab_migrate IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vulnlab_app;
ALTER DEFAULT PRIVILEGES FOR ROLE vulnlab_migrate IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO vulnlab_app;
COMMIT;
SQL
)
