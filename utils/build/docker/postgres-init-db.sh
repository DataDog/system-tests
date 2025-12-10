#!/bin/bash

# NOTE: if you are getting a permission error when starting postgres instance try doing chmod 777 on this file

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE USER system_tests_user WITH PASSWORD 'system_tests';
	CREATE DATABASE system_tests_dbname;
	GRANT ALL PRIVILEGES ON DATABASE system_tests_dbname TO system_tests_user;
	GRANT pg_monitor TO system_tests_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "system_tests_dbname" <<-EOSQL
        GRANT ALL PRIVILEGES ON SCHEMA public TO system_tests_user;
        CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
        ALTER SYSTEM SET track_io_timing = on;
        ALTER SYSTEM SET track_functions = 'all';
EOSQL

# Reload configuration to apply settings
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        SELECT pg_reload_conf();
EOSQL
