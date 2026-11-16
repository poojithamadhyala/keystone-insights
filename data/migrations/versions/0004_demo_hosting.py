"""Hosted-demo support: self-grant the read-only role, and an LLM spend ledger

Revision ID: 0004
Revises: 0003

1. On managed Postgres (Neon) the app's user is not a superuser. Since Postgres 16, a non-superuser
   that creates a role gets ADMIN on it but NOT the right to `SET ROLE` to it, so the agent's
   `SET LOCAL ROLE leaselens_ro` would fail with "permission denied to set role". Granting the
   role to the current user fixes it (reproduced and verified locally; DECISIONS.md D-043). The
   read-only role's own privileges are unchanged: it still sees only the `reporting` views.
2. llm_spend: one row per UTC day with the summed Claude cost, so the public demo's daily spend cap
   survives restarts (the free host sleeps and restarts often).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from common.settings import get_settings

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ro = get_settings().postgres_ro_user
    # A superuser can already SET ROLE to anything; for everyone else this grant is what makes
    # it possible. Wrapped so an existing membership (or a role owned by someone else) can't
    # block the migration: the agent tests will catch it if SET ROLE still fails.
    op.execute(
        f"""DO $$ BEGIN
              EXECUTE format('GRANT %I TO %I', '{ro}', current_user);
            EXCEPTION WHEN insufficient_privilege THEN
              RAISE NOTICE 'could not grant {ro} to %', current_user;
            END $$"""
    )
    op.create_table(
        "llm_spend",
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("calls", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("llm_spend")
