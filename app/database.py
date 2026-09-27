"""Engine and session plumbing."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def make_engine(url: str):
    """Create an engine, enabling the SQLite niceties when applicable."""
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )

        @event.listens_for(engine, "connect")
        def _enable_sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover
            # SQLite does not enforce foreign keys unless asked to.
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, future=True)


def make_memory_engine():
    """A single shared in-memory SQLite database (used by tests)."""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


def make_sessionmaker(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
