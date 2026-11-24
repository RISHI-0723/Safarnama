from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine, URL, make_url
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


def normalize_database_url(database_url: str | URL) -> URL:
    url = make_url(database_url)
    if url.drivername in {"postgresql", "postgres"}:
        return url.set(drivername="postgresql+psycopg")
    return url


def make_engine(database_url: str | URL) -> Engine:
    url = normalize_database_url(database_url)
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:" and str(url.query.get("uri", "")).lower() != "true":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    if url.drivername == "postgresql+psycopg":
        return create_engine(
            url,
            connect_args={"connect_timeout": 10, "prepare_threshold": None},
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            hide_parameters=True,
        )
    raise ValueError("Use a SQLite or PostgreSQL database URL (PostgreSQL driver: psycopg)")


def initialize_database(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        # Application startup and the importer share this transaction-scoped lock.
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(501842395)")
    Base.metadata.create_all(connection)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
