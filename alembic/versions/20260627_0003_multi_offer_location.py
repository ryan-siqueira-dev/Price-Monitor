"""persist offers, location and provider status

Revision ID: 20260627_0003
Revises: 20260627_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20260627_0003"
down_revision = "20260627_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("city", sa.String(length=120)))
        batch_op.add_column(sa.Column("state", sa.String(length=2)))

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "provider_statuses",
        sa.Column("provider", sa.String(length=100), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("store", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(length=30), nullable=False, server_default="desconhecido"),
        sa.Column("city", sa.String(length=120)),
        sa.Column("state", sa.String(length=2)),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_alerted_price", sa.Numeric(12, 2)),
        sa.Column("last_alerted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("product_id", "store", "external_id"),
    )
    op.create_index("ix_offers_product_id", "offers", ["product_id"])
    op.create_index("ix_offers_store", "offers", ["store"])
    op.create_index("ix_offers_active", "offers", ["active"])
    op.create_table(
        "offer_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "offer_id",
            sa.Integer(),
            sa.ForeignKey("offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_offer_checks_offer_id", "offer_checks", ["offer_id"])
    op.create_index("ix_offer_checks_checked_at", "offer_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_table("offer_checks")
    op.drop_table("offers")
    op.drop_table("provider_statuses")
    op.drop_table("app_settings")
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("state")
        batch_op.drop_column("city")
