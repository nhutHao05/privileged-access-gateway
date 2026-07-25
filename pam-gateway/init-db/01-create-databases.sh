#!/bin/bash
set -e

echo "Creating multiple databases: keycloak, guacamole, pam_control"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE keycloak;
    CREATE DATABASE guacamole;
    CREATE DATABASE pam_control;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE guacamole TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE pam_control TO $POSTGRES_USER;
EOSQL
