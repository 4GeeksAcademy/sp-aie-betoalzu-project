from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB

# Import ORM models so SQLModel.metadata discovers them
import services.models  # noqa: F401

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()  # Load variables from .env file

# ---------------------------------------------------------------------------
# TinyDB – existing document store for auth, users, profiles, incidents, etc.
# ---------------------------------------------------------------------------

_ROOT_DIR = Path(__file__).resolve().parent.parent  # services/
_DATA_DIR = _ROOT_DIR / "data"


def _ensure_data_dir() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


def get_tinydb(db_name: str = "users_db.json") -> TinyDB:
    """Open a TinyDB database file from the data/ directory.

    The caller is responsible for closing the database.
    """
    path = _DATA_DIR / db_name
    path.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(str(path))


# ---------------------------------------------------------------------------
# SQLModel / Supabase (PostgreSQL)
# ---------------------------------------------------------------------------

DATABASE_URL: str | None = os.getenv("DATABASE_URL")

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        echo=False,                      # Set to True for SQL debug logs
        pool_pre_ping=True,              # Verify connections before use
        pool_size=5,                     # Max connections in the pool
        max_overflow=10,                 # Extra connections beyond pool_size
    )
else:
    # Fallback: SQLite in-memory for local development without Supabase
    engine = create_engine("sqlite:///./data/nexova_dev.db", echo=False)


def init_db() -> None:
    """Create all tables defined via SQLModel metadata.

    Call this during application startup (lifespan event) to ensure
    the Supabase/Postgres schema is up to date.
    """
    SQLModel.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLModel session per request.

    Usage:
        @app.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()