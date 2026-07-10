import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

engine = create_engine(settings.mssql_connection_string, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema() -> None:
    """Create EmailStore / email_sync_state if they don't already exist. Idempotent no-op otherwise."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t.name for t in Base.metadata.sorted_tables if t.name not in existing]
    if missing:
        logger.info("Creating missing tables: %s", missing)
        Base.metadata.create_all(bind=engine, checkfirst=True)
    else:
        logger.info("EmailStore / email_sync_state already present, skipping schema creation")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one Session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for the background IMAP thread: one Session per unit of work."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
