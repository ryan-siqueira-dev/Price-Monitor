"""remove Mercado Livre and Magalu legacy data

Revision ID: 20260628_0004
Revises: 20260627_0003
"""

import sqlalchemy as sa

from alembic import op

revision = "20260628_0004"
down_revision = "20260627_0003"
branch_labels = None
depends_on = None

REMOVED_STORES = ("Mercado Livre", "Magalu", "Magazine Luiza")


def upgrade() -> None:
    connection = op.get_bind()
    stores = {f"store_{index}": store for index, store in enumerate(REMOVED_STORES)}
    placeholders = ", ".join(f":store_{index}" for index in range(len(REMOVED_STORES)))

    connection.execute(
        sa.text(
            "DELETE FROM offer_checks WHERE offer_id IN "
            f"(SELECT id FROM offers WHERE store IN ({placeholders}))"
        ),
        stores,
    )
    connection.execute(
        sa.text(f"DELETE FROM offers WHERE store IN ({placeholders})"),
        stores,
    )
    connection.execute(
        sa.text(f"DELETE FROM provider_statuses WHERE provider IN ({placeholders})"),
        stores,
    )
    connection.execute(
        sa.text(
            "UPDATE products SET last_checked_at = NULL, last_price = NULL, "
            "last_status = NULL, last_error = NULL, last_offer_url = NULL, last_store = NULL "
            f"WHERE last_store IN ({placeholders})"
        ),
        stores,
    )


def downgrade() -> None:
    # A remoção foi solicitada como definitiva; dados excluídos não podem ser reconstruídos.
    pass
