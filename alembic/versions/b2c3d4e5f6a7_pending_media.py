"""pending media uploads

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "animal_photos",
        sa.Column("is_pending", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(op.f("ix_animal_photos_is_pending"), "animal_photos", ["is_pending"], unique=False)

    op.add_column("organizations", sa.Column("logo_pending_path", sa.String(length=500), nullable=True))
    op.add_column("organizations", sa.Column("cover_pending_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "cover_pending_path")
    op.drop_column("organizations", "logo_pending_path")
    op.drop_index(op.f("ix_animal_photos_is_pending"), table_name="animal_photos")
    op.drop_column("animal_photos", "is_pending")
