import logging
import threading

from sqlalchemy import func, select

from app.company.ollama_client import summarize_thread
from app.db.models import EmailStore
from app.db.session import session_scope
from app.graphql.queries import _assemble_thread, _normalize_subject

logger = logging.getLogger(__name__)

_summary_bg_locks = {}
_summary_bg_lock = threading.Lock()


def _generate_thread_summary(email_id: int) -> None:
    """Background task: generate AI summary for the entire thread and store
    it on every email in the thread so the UI never needs to wait for Ollama."""
    try:
        with session_scope() as session:
            row = session.execute(
                select(EmailStore).where(EmailStore.id == email_id)
            ).scalar_one_or_none()
            if not row:
                return

            norm = _normalize_subject(row.subject)
            if not norm:
                return

            thread_text = _assemble_thread(row, session)
            if not thread_text.strip():
                return

            # Dedup: only one background generation per thread at a time
            with _summary_bg_lock:
                if norm in _summary_bg_locks:
                    return
                _summary_bg_locks[norm] = True

            try:
                summary = summarize_thread(thread_text)
                if not summary:
                    return

                siblings = session.execute(
                    select(EmailStore).where(
                        func.lower(EmailStore.subject).contains(norm)
                    )
                ).scalars().all()
                for sib in siblings:
                    sib.ai_summary = summary
                session.commit()
                logger.info("Background summary generated for thread %r (%s emails)", norm, len(siblings))
            finally:
                with _summary_bg_lock:
                    _summary_bg_locks.pop(norm, None)
    except Exception:
        logger.exception("Background thread-summary failed for email_id=%s", email_id)
