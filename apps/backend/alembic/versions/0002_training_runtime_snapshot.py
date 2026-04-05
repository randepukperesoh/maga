"""add runtime snapshot table

Revision ID: 0002_training_runtime_snapshot
Revises: 0001_training_tables
Create Date: 2026-04-03 00:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_training_runtime_snapshot"
down_revision: Union[str, Sequence[str], None] = "0001_training_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_runtime_snapshot",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("training_runtime_snapshot")
