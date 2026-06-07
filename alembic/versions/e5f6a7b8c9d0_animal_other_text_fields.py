"""animal other text fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("animals")}
    if "health_care_other" not in existing:
        op.add_column("animals", sa.Column("health_care_other", sa.Text(), nullable=True))
    if "character_other" not in existing:
        op.add_column("animals", sa.Column("character_other", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("animals", "character_other")
    op.drop_column("animals", "health_care_other")
