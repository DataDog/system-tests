#!/bin/bash

# NOTE: if you are getting a permission error when starting postgres instance try doing chmod 777 on this file

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        CREATE USER system_tests_user WITH PASSWORD 'system_tests';
        CREATE DATABASE system_tests;
        GRANT ALL PRIVILEGES ON DATABASE system_tests TO system_tests_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "system_tests" <<-EOSQL
        GRANT ALL PRIVILEGES ON SCHEMA public TO system_tests_user;
EOSQL
