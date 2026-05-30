"""plan improvements: hints, events capacity, report files

Revision ID: a1b2c3d4e5f6
Revises: 0827b0b69f86
Create Date: 2026-05-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0827b0b69f86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_articles", sa.Column("target_help_types_json", sa.Text(), nullable=True))
    op.add_column("knowledge_articles", sa.Column("target_species_json", sa.Text(), nullable=True))
    op.add_column("knowledge_articles", sa.Column("target_competency_slugs_json", sa.Text(), nullable=True))
    op.add_column("knowledge_articles", sa.Column("keywords_json", sa.Text(), nullable=True))

    op.add_column("events", sa.Column("entry_type", sa.String(length=20), server_default="free", nullable=False))
    op.add_column("events", sa.Column("capacity", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("seats_taken", sa.Integer(), server_default="0", nullable=False))

    op.add_column("organization_reports", sa.Column("file_path", sa.String(length=500), nullable=True))

    op.create_table(
        "volunteer_help_response_report_photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["volunteer_help_response_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_volunteer_help_response_report_photos_report_id"),
        "volunteer_help_response_report_photos",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_volunteer_help_response_report_photos_report_id"),
        table_name="volunteer_help_response_report_photos",
    )
    op.drop_table("volunteer_help_response_report_photos")
    op.drop_column("organization_reports", "file_path")
    op.drop_column("events", "seats_taken")
    op.drop_column("events", "capacity")
    op.drop_column("events", "entry_type")
    op.drop_column("knowledge_articles", "keywords_json")
    op.drop_column("knowledge_articles", "target_competency_slugs_json")
    op.drop_column("knowledge_articles", "target_species_json")
    op.drop_column("knowledge_articles", "target_help_types_json")
