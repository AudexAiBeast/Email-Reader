import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def call_sp(session: Session, sp_name: str, **params: Any) -> dict | None:
    """Execute a stored procedure and return its first result row as a dict.

    Parameters
    ----------
    session : Session
        An active SQLAlchemy ORM Session.  The SP runs inside the session's
        current transaction; the caller must commit/rollback explicitly.
    sp_name : str
        Fully qualified stored-procedure name, e.g. ``"dbo.sp_InsertEmailStore"``.
    **params : Any
        Keyword arguments mapped to SP parameters by name.  ``None`` values
        are passed as SQL ``NULL``.

    Returns
    -------
    dict | None
        The first row of the SP's first result set as a dict, or ``None`` if
        the SP returned no rows.

    Notes
    -----
    The SP **must** use ``SET NOCOUNT ON`` so that pyodbc does not get confused
    by row-count messages, and it **must** return a single result set via
    ``SELECT`` when the caller expects a return value.
    """
    placeholders = ", ".join(f"@{k} = :{k}" for k in params)
    sql = f"EXEC {sp_name} {placeholders}"
    result = session.execute(text(sql), params)
    row = result.mappings().first()
    return dict(row) if row else None
