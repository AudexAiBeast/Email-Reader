import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.company.ollama_client import summarize_thread, update_summary
from app.db.models import AiSummaryEvent, EmailStore
from app.db.session import session_scope
from app.graphql.queries import _normalize_subject

logger = logging.getLogger(__name__)

_summary_bg_locks = {}
_summary_bg_lock = threading.Lock()


def _format_row_as_text(table: str, row: dict) -> str:
    """Convert a raw DB row dict into a readable key=value block."""
    parts = [f"--- {table} row ---"]
    for k, v in row.items():
        if v is None:
            continue
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


def _read_document_rows(session, sno_column: str, table: str, sno: int) -> str | None:
    """Read a document row by its SNO and return formatted text, or None."""
    if not sno:
        return None
    result = session.execute(
        text(f"SELECT * FROM {table} WHERE {sno_column} = :sno"),
        {"sno": sno},
    )
    row = result.mappings().first()
    if not row:
        return None
    return _format_row_as_text(table, dict(row))


def _generate_combined_summary(email_id: int) -> None:
    """Background task: generate/update combined AI summary for the
    email thread AND any matched WoExecutionDoc / JOB_ORDER rows.

    Uses an **incremental** approach:
      - If any sibling email already has a cached summary → use as context.
      - Otherwise → full thread text (first email in thread).
      - Appends the new email's body + any matched document data.
      - ONE Ollama call → single combined summary.

    Stores the result on:
      - ALL sibling emails (so opening any email shows the latest summary)
      - WoExecutionDoc row (if matched on the NEW email)
      - JOB_ORDER row (if matched on the NEW email)
      - A new row in ai_summary_event (audit trail)
    """
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

            # Dedup: one background generation per thread at a time
            with _summary_bg_lock:
                if norm in _summary_bg_locks:
                    return
                _summary_bg_locks[norm] = True

            try:
                # -------------------------------------------------------
                # 1. Find ALL siblings in the thread
                # -------------------------------------------------------
                siblings = session.execute(
                    select(EmailStore).where(
                        func.lower(EmailStore.subject).contains(norm)
                    )
                ).scalars().all()

                if not siblings:
                    return

                # -------------------------------------------------------
                # 2. Check for a PREVIOUS cached summary on any sibling
                # -------------------------------------------------------
                previous_summary = None
                for sib in siblings:
                    if sib.ai_summary:
                        previous_summary = sib.ai_summary
                        break

                # -------------------------------------------------------
                # 3. Get the new content (just this email's body)
                # -------------------------------------------------------
                new_body = row.body_text or row.body_html or ""
                if new_body.startswith("<"):
                    import re as _re
                    new_body = _re.sub(r"<[^>]+>", "", new_body)
                    new_body = _re.sub(r"\s+", " ", new_body).strip()

                # -------------------------------------------------------
                # 4. Read matched document rows
                # -------------------------------------------------------
                doc_parts = []
                if row.job_ordersno:
                    doc = _read_document_rows(session, "JobOrderSno", "JOB_ORDER", row.job_ordersno)
                    if doc:
                        doc_parts.append(doc)
                if row.wo_execution_doc_sno:
                    doc = _read_document_rows(session, "WoExecutionDocSno", "WoExecutionDoc", row.wo_execution_doc_sno)
                    if doc:
                        doc_parts.append(doc)

                # -------------------------------------------------------
                # 5. Build the prompt
                # -------------------------------------------------------
                if previous_summary:
                    prompt_body = (
                        f"Previous summary:\n{previous_summary}\n\n"
                        f"New message:\nFrom: {row.from_address or 'unknown'}\n"
                        f"Subject: {row.subject or '(no subject)'}\n"
                        f"{new_body}"
                    )
                else:
                    # First email in the thread — include all sibling bodies
                    from app.graphql.queries import _assemble_thread
                    full_thread = _assemble_thread(row, session)
                    prompt_body = (
                        f"Full email thread:\n{full_thread}"
                    )

                if doc_parts:
                    prompt_body += "\n\n" + "\n\n".join(doc_parts)

                # -------------------------------------------------------
                # 6. Call Ollama
                # -------------------------------------------------------
                if previous_summary:
                    summary = update_summary(prompt_body)
                else:
                    summary = summarize_thread(prompt_body)

                if not summary:
                    return

                # -------------------------------------------------------
                # 7. Store on all sibling emails
                # -------------------------------------------------------
                for sib in siblings:
                    sib.ai_summary = summary

                # -------------------------------------------------------
                # 8. Store on matched document rows
                # -------------------------------------------------------
                if row.job_ordersno:
                    session.execute(
                        text("UPDATE JOB_ORDER SET ai_summary = :s WHERE JobOrderSno = :sno"),
                        {"s": summary, "sno": row.job_ordersno},
                    )
                if row.wo_execution_doc_sno:
                    session.execute(
                        text("UPDATE WoExecutionDoc SET ai_summary = :s WHERE WoExecutionDocSno = :sno"),
                        {"s": summary, "sno": row.wo_execution_doc_sno},
                    )

                # -------------------------------------------------------
                # 9. Audit trail in ai_summary_event
                # -------------------------------------------------------
                now = datetime.now(timezone.utc)
                events = []
                events.append(AiSummaryEvent(source_table="EmailStore", source_sno=email_id, ai_summary=summary, created_at=now))
                if row.job_ordersno:
                    events.append(AiSummaryEvent(source_table="JOB_ORDER", source_sno=row.job_ordersno, ai_summary=summary, created_at=now))
                if row.wo_execution_doc_sno:
                    events.append(AiSummaryEvent(source_table="WoExecutionDoc", source_sno=row.wo_execution_doc_sno, ai_summary=summary, created_at=now))
                for ev in events:
                    session.add(ev)

                session.commit()
                logger.info(
                    "Combined summary generated for thread %r (%s emails, JOB_ORDER=%s, WoExecutionDoc=%s)",
                    norm, len(siblings), row.job_ordersno, row.wo_execution_doc_sno,
                )
            finally:
                with _summary_bg_lock:
                    _summary_bg_locks.pop(norm, None)
    except Exception:
        logger.exception("Background combined-summary failed for email_id=%s", email_id)
