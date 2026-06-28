from collections.abc import AsyncGenerator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
from price_monitor.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        database_path = database_url.removeprefix("sqlite:///")
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(target_engine: Engine = engine) -> None:
    from price_monitor import models  # noqa: F401

    Base.metadata.create_all(bind=target_engine)


def migrate_db() -> None:
    candidates = (
        Path.cwd() / "alembic.ini",
        Path(__file__).resolve().parent.parent / "alembic.ini",
    )
    config_path = next((path for path in candidates if path.exists()), None)
    if config_path is None:
        searched = ", ".join(str(path) for path in candidates)
        raise RuntimeError(f"arquivo de migração não encontrado; caminhos verificados: {searched}")
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(config, "head")


async def get_session() -> AsyncGenerator[Session, None]:
    with SessionLocal() as session:
        yield session
