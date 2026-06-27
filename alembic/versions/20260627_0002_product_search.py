"""add product search and offer details

Revision ID: 20260627_0002
Revises: 20260626_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20260627_0002"
down_revision = "20260626_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("url", existing_type=sa.Text(), nullable=True)
        batch_op.add_column(sa.Column("search_query", sa.String(length=300)))
        batch_op.add_column(sa.Column("last_offer_url", sa.Text()))
        batch_op.add_column(sa.Column("last_store", sa.String(length=100)))
        batch_op.create_index("ix_products_search_query", ["search_query"])

    with op.batch_alter_table("price_checks") as batch_op:
        batch_op.add_column(sa.Column("offer_url", sa.Text()))
        batch_op.add_column(
            sa.Column("offers_found", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("price_checks") as batch_op:
        batch_op.drop_column("offers_found")
        batch_op.drop_column("offer_url")

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_index("ix_products_search_query")
        batch_op.drop_column("last_store")
        batch_op.drop_column("last_offer_url")
        batch_op.drop_column("search_query")
        batch_op.alter_column("url", existing_type=sa.Text(), nullable=False)
