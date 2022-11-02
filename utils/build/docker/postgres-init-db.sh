#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        CREATE USER system_tests_user WITH PASSWORD 'system_tests';
        CREATE DATABASE system_tests;
        GRANT ALL PRIVILEGES ON DATABASE system_tests TO system_tests_user;
EOSQL
