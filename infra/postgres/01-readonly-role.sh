#!/bin/bash
# Creates the read-only login role used by the agent's text-to-SQL tool.
# SELECT grants are added by Alembic migrations, scoped to the curated `reporting` schema only.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
  CREATE ROLE ${POSTGRES_RO_USER} LOGIN PASSWORD '${POSTGRES_RO_PASSWORD}';
  ALTER ROLE ${POSTGRES_RO_USER} SET statement_timeout = '5s';
  ALTER ROLE ${POSTGRES_RO_USER} SET default_transaction_read_only = on;
SQL
