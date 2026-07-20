import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

_SP_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"

engine = create_engine(settings.mssql_connection_string, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

_NEW_COLUMNS = [
    ("company_name", "NVARCHAR(255)"),
    ("company_domain_source", "NVARCHAR(255)"),
    ("company_signature_source", "NVARCHAR(255)"),
    ("ai_summary", "NVARCHAR(MAX)"),
    ("ocr_markdown_paths", "NVARCHAR(MAX)"),
    ("JOB_ORDERSNO", "INT"),
    ("WoExecutionDocSno", "INT"),
]


_EXTERNAL_AI_COLUMNS = [
    ("WoExecutionDoc", "WoExecutionDocSno", "ai_summary", "NVARCHAR(MAX)"),
    ("JOB_ORDER", "JobOrderSno", "ai_summary", "NVARCHAR(MAX)"),
]


def ensure_schema() -> None:
    """Create EmailStore / email_sync_state if they don't already exist, and
    migrate new columns onto the existing table if missing. Idempotent."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t.name for t in Base.metadata.sorted_tables if t.name not in existing]
    if missing:
        logger.info("Creating missing tables: %s", missing)
        Base.metadata.create_all(bind=engine, checkfirst=True)
    else:
        logger.info("EmailStore / email_sync_state already present, skipping table creation")

    if "EmailStore" in existing:
        _migrate_emailstore(inspector)

    _migrate_external_tables(inspector)
    _ensure_stored_procedures()


def _migrate_emailstore(inspector) -> None:
    existing_columns = {c["name"] for c in inspector.get_columns("EmailStore")}
    with engine.connect() as conn:
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing_columns:
                logger.info("Adding column EmailStore.%s", col_name)
                conn.execute(text(f"ALTER TABLE EmailStore ADD {col_name} {col_type}"))
        conn.commit()


def _ensure_stored_procedures() -> None:
    sp_file = _SP_DIR / "sp_InsertEmailStore.sql"
    if not sp_file.exists():
        logger.warning("Stored-procedure script not found: %s", sp_file)
        return
    sql = sp_file.read_text()
    batches = [b.strip() for b in sql.replace("\r\n", "\n").split("\nGO\n") if b.strip()]
    with engine.begin() as conn:
        for batch in batches:
            conn.exec_driver_sql(batch)
    logger.info("Stored procedures deployed (CREATE OR ALTER)")


def _migrate_external_tables(inspector) -> None:
    for table, pk_col, col_name, col_type in _EXTERNAL_AI_COLUMNS:
        if table not in inspector.get_table_names():
            logger.warning("External table %s not found, skipping ai_summary migration", table)
            continue
        existing_columns = {c["name"] for c in inspector.get_columns(table)}
        if col_name not in existing_columns:
            logger.info("Adding column %s.%s", table, col_name)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD {col_name} {col_type}"))


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
