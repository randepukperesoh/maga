"""add quasi-static run artifacts table

Revision ID: 0004_quasi_static_run_artifacts
Revises: 0003_quasi_static_scenarios
Create Date: 2026-04-03 23:55:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_quasi_static_run_artifacts"
down_revision: Union[str, Sequence[str], None] = "0003_quasi_static_scenarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quasi_static_run_artifacts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("quasi_static_run_artifacts")
