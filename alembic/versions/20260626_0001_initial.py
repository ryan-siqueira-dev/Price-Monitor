"""create products and price checks

Revision ID: 20260626_0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "20260626_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_price", sa.Numeric(12, 2)),
        sa.Column("last_status", sa.String(length=30)),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_alerted_price", sa.Numeric(12, 2)),
    )
    op.create_index("ix_products_url", "products", ["url"], unique=True)
    op.create_index("ix_products_active", "products", ["active"])
    op.create_table(
        "price_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("scraper", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500)),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_price_checks_product_id", "price_checks", ["product_id"])
    op.create_index("ix_price_checks_checked_at", "price_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_table("price_checks")
    op.drop_table("products")
