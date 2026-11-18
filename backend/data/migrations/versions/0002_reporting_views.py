"""reporting schema: PII-free views + read-only grants for the agent's text-to-SQL tool

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

from common.settings import get_settings

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Each view is the ONLY surface the read-only role can see (DECISIONS.md D-011).
# Tenant email/phone and vendor phone are deliberately absent; tenant names are reduced
# to "First L." so query results can't leak full identities.
VIEWS: dict[str, str] = {
    "properties": "SELECT id, name, city, state, property_type, year_built, acquired_on "
    "FROM public.properties",
    "units": "SELECT id, property_id, unit_number, unit_type, bedrooms, bathrooms, sqft, "
    "market_rent FROM public.units",
    "tenants": "SELECT id, first_name || ' ' || left(last_name, 1) || '.' AS tenant_label, "
    "credit_score FROM public.tenants",
    "leases": "SELECT id, unit_id, tenant_id, start_date, end_date, move_out_date, "
    "monthly_rent, security_deposit, status, renewal_of_lease_id FROM public.leases",
    "rent_ledger": "SELECT id, lease_id, period, due_date, amount_due, amount_paid, paid_on "
    "FROM public.rent_ledger",
    "vendors": "SELECT id, name, trade, hourly_rate FROM public.vendors",
    "work_orders": "SELECT id, property_id, unit_id, vendor_id, category, priority, status, "
    "opened_at, completed_at, cost, description FROM public.work_orders",
    "operating_expenses": "SELECT id, property_id, period, category, amount "
    "FROM public.operating_expenses",
}


def upgrade() -> None:
    ro = get_settings().postgres_ro_user
    op.execute("CREATE SCHEMA IF NOT EXISTS reporting")
    for name, sql in VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW reporting.{name} AS {sql}")
    # The role normally exists already (infra/postgres init script, which sets its password).
    # Create a NOLOGIN placeholder otherwise so migrations also work in CI / test databases.
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ro}') "
        f"THEN CREATE ROLE {ro} NOLOGIN; END IF; END $$"
    )
    op.execute(f"REVOKE ALL ON SCHEMA public FROM {ro}")
    op.execute(f"GRANT USAGE ON SCHEMA reporting TO {ro}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO {ro}")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS reporting CASCADE")
