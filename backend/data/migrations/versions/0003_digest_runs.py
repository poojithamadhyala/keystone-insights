"""digest_runs: every built weekly digest, exactly as previewed and (if sent) as delivered

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "digest_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),  # preview | schedule
        sa.Column("facts", JSONB, nullable=False),
        sa.Column("text", sa.Text, nullable=False),  # exactly what is shown and sent
        sa.Column("narrative_ok", sa.Boolean, nullable=False),  # False -> facts-only fallback
        sa.Column("ungrounded", JSONB, nullable=False),  # numbers that failed the check
        sa.Column("model", sa.String(60)),
        sa.Column("prompt_version", sa.String(20)),
        sa.Column("cost_usd", sa.Numeric(8, 4)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_status", sa.String(200)),
    )


def downgrade() -> None:
    op.drop_table("digest_runs")
