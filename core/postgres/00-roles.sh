#!/bin/sh
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

set -e

# 1. Khởi tạo các vai trò trong database chính
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
            CREATE ROLE authenticator NOINHERIT LOGIN;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dxos_svc') THEN
            CREATE ROLE dxos_svc NOINHERIT LOGIN NOSUPERUSER NOBYPASSRLS;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dxos_owner') THEN
            CREATE ROLE dxos_owner NOINHERIT LOGIN NOSUPERUSER NOBYPASSRLS;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
            CREATE ROLE keycloak LOGIN;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'flowable') THEN
            CREATE ROLE flowable LOGIN;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc') THEN
            CREATE ROLE svc NOLOGIN;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_user') THEN
            CREATE ROLE web_user NOLOGIN;
        END IF;
    END \$\$;
    ALTER ROLE authenticator WITH PASSWORD '${AUTHENTICATOR_PASSWORD}';
    ALTER ROLE dxos_svc WITH PASSWORD '${DB_PASSWORD}';
    ALTER ROLE dxos_owner WITH PASSWORD '${DXOS_OWNER_PASSWORD}';
    ALTER ROLE keycloak WITH PASSWORD '${KEYCLOAK_DB_PASSWORD}';
    ALTER ROLE flowable WITH PASSWORD '${FLOWABLE_DB_PASSWORD}';
    GRANT web_user, svc TO dxos_svc;
    GRANT CONNECT, CREATE ON DATABASE dxos TO dxos_owner;
    GRANT CONNECT ON DATABASE dxos TO dxos_svc;
    REVOKE ALL ON DATABASE dxos FROM dxos_svc;
    GRANT CONNECT ON DATABASE dxos TO dxos_svc;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    GRANT USAGE ON SCHEMA public TO dxos_svc, svc, web_user, dxos_owner;
EOSQL

# 2. Cấp quyền cơ sở dữ liệu riêng biệt cho Keycloak
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "keycloak" <<-EOSQL
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
    ALTER DATABASE keycloak OWNER TO keycloak;
    GRANT ALL ON SCHEMA public TO keycloak;
EOSQL

# 3. Cấp quyền cơ sở dữ liệu riêng biệt cho Flowable
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "flowable" <<-EOSQL
    GRANT ALL PRIVILEGES ON DATABASE flowable TO flowable;
    ALTER DATABASE flowable OWNER TO flowable;
    GRANT ALL ON SCHEMA public TO flowable;
EOSQL

