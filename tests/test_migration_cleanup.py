import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _upgrade(database_path: Path, revision: str) -> None:
    environment = os.environ.copy()
    environment["PRICE_MONITOR_DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_removed_provider_data_is_deleted_by_migration(tmp_path):
    database_path = tmp_path / "migration.db"
    _upgrade(database_path, "20260627_0003")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO products (
                id, name, search_query, url, target_price, currency, active,
                created_at, updated_at, last_checked_at, last_price, last_status,
                last_offer_url, last_store
            ) VALUES (
                1, 'Produto', 'Produto', NULL, 1000, 'BRL', 1,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 900,
                'available', 'https://example.com/legacy', 'Mercado Livre'
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO offers (
                id, product_id, store, external_id, title, url, condition,
                currency, current_price, active, first_seen_at, last_seen_at
            ) VALUES (?, 1, ?, ?, ?, ?, 'desconhecido', 'BRL', 900, 1,
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [
                (1, "Mercado Livre", "ml-1", "Produto ML", "https://example.com/ml"),
                (2, "Magalu", "magalu-1", "Produto Magalu", "https://example.com/magalu"),
                (
                    3,
                    "Magazine Luiza",
                    "magazine-1",
                    "Produto Magazine",
                    "https://example.com/magazine",
                ),
                (4, "Amazon", "amazon-1", "Produto Amazon", "https://example.com/amazon"),
            ],
        )
        connection.executemany(
            "INSERT INTO offer_checks (offer_id, checked_at, price, available) "
            "VALUES (?, CURRENT_TIMESTAMP, 900, 1)",
            [(1,), (2,), (3,), (4,)],
        )
        connection.executemany(
            "INSERT INTO provider_statuses (provider) VALUES (?)",
            [("Mercado Livre",), ("Magalu",), ("Magazine Luiza",), ("Amazon",)],
        )
        connection.commit()

    _upgrade(database_path, "head")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT store FROM offers").fetchall() == [("Amazon",)]
        assert connection.execute("SELECT offer_id FROM offer_checks").fetchall() == [(4,)]
        assert connection.execute("SELECT provider FROM provider_statuses").fetchall() == [
            ("Amazon",)
        ]
        summary = connection.execute(
            "SELECT last_checked_at, last_price, last_status, last_offer_url, last_store "
            "FROM products WHERE id = 1"
        ).fetchone()
        assert summary == (None, None, None, None, None)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "20260628_0004",
        )
