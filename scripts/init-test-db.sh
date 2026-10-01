#!/bin/bash
set -e

# Create test database alongside dev database in postgres container
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE employee_task_test_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'employee_task_test_db')\gexec
    GRANT ALL PRIVILEGES ON DATABASE employee_task_test_db TO "$POSTGRES_USER";
EOSQL
