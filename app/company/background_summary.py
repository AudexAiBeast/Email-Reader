import base64
import json
import logging
import re as _re
import threading
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select, text

from app.company.ollama_client import summarize_thread, update_summary
from app.config import settings
from app.db.models import AiSummaryEvent, EmailStore
from app.db.session import session_scope
from app.graphql.queries import _assemble_thread, _normalize_subject

logger = logging.getLogger(__name__)

_jo_locks = {}
_jo_lock = threading.Lock()

_thread_locks = {}
_thread_lock = threading.Lock()


def _format_row_as_text(table: str, row: dict) -> str:
    parts = [f"--- {table} row ---"]
    for k, v in row.items():
        if v is None:
            continue
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


def _sanitize_body(body: str | None) -> str:
    if not body:
        return ""
    if body.startswith("<"):
        body = _re.sub(r"<[^>]+>", "", body)
        body = _re.sub(r"\s+", " ", body).strip()
    return body


def _truncate_oldest(text: str, max_chars: int = 20000) -> str:
    if len(text) <= max_chars:
        return text
    dropped = 0
    while len(text) > max_chars:
        parts = text.split("\n\n", 1)
        if len(parts) < 2:
            return text[:max_chars] + "\n\n[...truncated]"
        dropped += 1
        text = parts[1]
    logger.info("Truncated %s oldest blocks to fit %s chars", dropped, max_chars)
    return text + "\n\n[...older content truncated]"


def _generate_job_order_story(session, job_ordersno: int) -> None:
    with _jo_lock:
        if job_ordersno in _jo_locks:
            return
        _jo_locks[job_ordersno] = True

    try:
        wo_docs = session.execute(
            text("SELECT * FROM WoExecutionDoc WHERE PlanningMasSno = :sno"),
            {"sno": job_ordersno},
        ).mappings().all()

        wo_snos = [r["WoExecutionDocSno"] for r in wo_docs] if wo_docs else []

        if wo_snos:
            placeholders = ", ".join(f":ws{i}" for i in range(len(wo_snos)))
            params = {"sno": job_ordersno}
            params.update({f"ws{i}": s for i, s in enumerate(wo_snos)})
            emails = session.execute(
                text(f"""
                    SELECT * FROM EmailStore
                    WHERE JOB_ORDERSNO = :sno
                       OR WoExecutionDocSno IN ({placeholders})
                    ORDER BY email_date_utc ASC
                """),
                params,
            ).mappings().all()
        else:
            emails = session.execute(
                text("""
                    SELECT * FROM EmailStore
                    WHERE JOB_ORDERSNO = :sno
                    ORDER BY email_date_utc ASC
                """),
                {"sno": job_ordersno},
            ).mappings().all()

        job_order = session.execute(
            text("SELECT * FROM JOB_ORDER WHERE JobOrderSno = :sno"),
            {"sno": job_ordersno},
        ).mappings().first()

        if not emails and not wo_docs:
            return

        previous_story = None
        for email in emails:
            if email.get("ai_summary"):
                previous_story = email["ai_summary"]
                break
        if not previous_story:
            for doc in wo_docs:
                if doc.get("ai_summary"):
                    previous_story = doc["ai_summary"]
                    break
        if not previous_story and job_order and job_order.get("ai_summary"):
            previous_story = job_order["ai_summary"]

        parts = []
        if previous_story:
            parts.append(f"Previous story:\n{previous_story}")

        for email in emails:
            body = _sanitize_body(email.get("body_text") or email.get("body_html"))
            date_str = str(email.get("email_date_utc") or "")
            parts.append(
                f"Email from {email.get('from_address')} on {date_str}:\n"
                f"Subject: {email.get('subject')}\n{body}"
            )

        for doc in wo_docs:
            parts.append(_format_row_as_text("WoExecutionDoc", dict(doc)))

        if job_order:
            parts.append(_format_row_as_text("JOB_ORDER", dict(job_order)))

        prompt_body = _truncate_oldest("\n\n".join(parts))

        summary = update_summary(prompt_body) if previous_story else summarize_thread(prompt_body)
        if not summary:
            return

        for email in emails:
            session.execute(
                text("UPDATE EmailStore SET ai_summary = :s WHERE id = :id"),
                {"s": summary, "id": email["id"]},
            )

        for doc in wo_docs:
            session.execute(
                text("UPDATE WoExecutionDoc SET ai_summary = :s WHERE WoExecutionDocSno = :sno"),
                {"s": summary, "sno": doc["WoExecutionDocSno"]},
            )

        if job_order:
            session.execute(
                text("UPDATE JOB_ORDER SET ai_summary = :s WHERE JobOrderSno = :sno"),
                {"s": summary, "sno": job_order["JobOrderSno"]},
            )

        now = datetime.now(timezone.utc)
        events = []
        for email in emails:
            events.append(AiSummaryEvent(source_table="EmailStore", source_sno=email["id"], ai_summary=summary, created_at=now))
        for doc in wo_docs:
            events.append(AiSummaryEvent(source_table="WoExecutionDoc", source_sno=doc["WoExecutionDocSno"], ai_summary=summary, created_at=now))
        if job_order:
            events.append(AiSummaryEvent(source_table="JOB_ORDER", source_sno=job_order["JobOrderSno"], ai_summary=summary, created_at=now))
        for ev in events:
            session.add(ev)

        session.commit()
        logger.info("Job-order story for JOB_ORDERSNO=%s (%s emails, %s docs, incremental=%s)", job_ordersno, len(emails), len(wo_docs), bool(previous_story))
    except Exception:
        logger.exception("Background job-order story failed for JOB_ORDERSNO=%s", job_ordersno)
    finally:
        with _jo_lock:
            _jo_locks.pop(job_ordersno, None)


def _generate_thread_summary(session, row) -> None:
    norm = _normalize_subject(row.subject)
    if not norm:
        return

    with _thread_lock:
        if norm in _thread_locks:
            return
        _thread_locks[norm] = True

    try:
        siblings = session.execute(
            select(EmailStore).where(
                func.lower(EmailStore.subject).contains(norm),
            )
        ).scalars().all()

        if not siblings:
            return

        previous_summary = None
        for sib in siblings:
            if sib.ai_summary:
                previous_summary = sib.ai_summary
                break

        new_body = _sanitize_body(row.body_text or row.body_html)

        doc_parts = []
        if row.job_ordersno:
            doc = session.execute(
                text("SELECT * FROM JOB_ORDER WHERE JobOrderSno = :sno"),
                {"sno": row.job_ordersno},
            ).mappings().first()
            if doc:
                doc_parts.append(_format_row_as_text("JOB_ORDER", dict(doc)))
        if row.wo_execution_doc_sno:
            doc = session.execute(
                text("SELECT * FROM WoExecutionDoc WHERE WoExecutionDocSno = :sno"),
                {"sno": row.wo_execution_doc_sno},
            ).mappings().first()
            if doc:
                doc_parts.append(_format_row_as_text("WoExecutionDoc", dict(doc)))

        if previous_summary:
            prompt_body = (
                f"Previous summary:\n{previous_summary}\n\n"
                f"New message:\nFrom: {row.from_address or 'unknown'}\n"
                f"Subject: {row.subject or '(no subject)'}\n{new_body}"
            )
        else:
            full_thread = _assemble_thread(row, session)
            prompt_body = f"Full email thread:\n{full_thread}"

        if doc_parts:
            prompt_body += "\n\n" + "\n\n".join(doc_parts)

        prompt_body = _truncate_oldest(prompt_body)

        summary = update_summary(prompt_body) if previous_summary else summarize_thread(prompt_body)
        if not summary:
            return

        for sib in siblings:
            sib.ai_summary = summary

        now = datetime.now(timezone.utc)
        events = [AiSummaryEvent(source_table="EmailStore", source_sno=row.id, ai_summary=summary, created_at=now)]

        if row.job_ordersno:
            session.execute(
                text("UPDATE JOB_ORDER SET ai_summary = :s WHERE JobOrderSno = :sno"),
                {"s": summary, "sno": row.job_ordersno},
            )
            events.append(AiSummaryEvent(source_table="JOB_ORDER", source_sno=row.job_ordersno, ai_summary=summary, created_at=now))
        if row.wo_execution_doc_sno:
            session.execute(
                text("UPDATE WoExecutionDoc SET ai_summary = :s WHERE WoExecutionDocSno = :sno"),
                {"s": summary, "sno": row.wo_execution_doc_sno},
            )
            events.append(AiSummaryEvent(source_table="WoExecutionDoc", source_sno=row.wo_execution_doc_sno, ai_summary=summary, created_at=now))

        for ev in events:
            session.add(ev)
        session.commit()
        logger.info("Thread summary for %r (%s emails)", norm, len(siblings))
    except Exception:
        logger.exception("Background thread summary failed for email_id=%s", row.id)
    finally:
        with _thread_lock:
            _thread_locks.pop(norm, None)


_OCR_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_OCR_MIN_FILE_BYTES = 10240  # 10 KB — skip tiny files (signatures, icons)


def _post_email_to_ocr(email_id: int, raw_email_b64: str) -> None:
    """Extract PDF/image attachments from the raw email and POST each to
    the external OCR endpoint. Only fires when JOB_ORDERSNO is matched."""
    import email as eml
    from email import policy as eml_policy

    url = settings.ocr_endpoint_url
    if not url:
        return
    try:
        raw_bytes = base64.b64decode(raw_email_b64)
        msg = eml.message_from_bytes(raw_bytes, policy=eml_policy.default)

        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                fn = part.get_filename()
                if not fn:
                    continue
                ext = "." + fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
                if ext not in _OCR_ALLOWED_EXTENSIONS:
                    continue
                content = part.get_payload(decode=True)
                if content and len(content) >= _OCR_MIN_FILE_BYTES:
                    attachments.append((fn, content))
        else:
            # Single-part email: try sending body as text if it's short
            pass

        if not attachments:
            logger.info("No OCR-able attachments in email %s", email_id)
            return

        results = []
        for fn, content in attachments:
            files = {"file": (fn, content)}
            resp = httpx.post(url, files=files, timeout=120)
            resp.raise_for_status()
            results.append({"filename": fn, "status": resp.status_code, "response": resp.text})
            logger.info("OCR POST for email %s attachment %r → status %s", email_id, fn, resp.status_code)

        with session_scope() as session:
            existing = session.execute(
                select(EmailStore.ocr_markdown_paths).where(EmailStore.id == email_id)
            ).scalar_one_or_none()
            if existing:
                try:
                    paths = json.loads(existing)
                except (json.JSONDecodeError, TypeError):
                    paths = []
                if not isinstance(paths, list):
                    paths = [paths]
            else:
                paths = []
            paths.append({"source": "external_ocr", "attachments": results})
            session.execute(
                text("UPDATE EmailStore SET ocr_markdown_paths = :s WHERE id = :id"),
                {"s": json.dumps(paths), "id": email_id},
            )
            session.commit()
        logger.info("OCR POST for email %s: %s attachment(s) sent to %s", email_id, len(attachments), url)
    except Exception:
        logger.exception("OCR POST failed for email_id=%s to %s", email_id, url)


def _generate_combined_summary(email_id: int) -> None:
    raw_email_b64 = None
    job_ordersno = None
    try:
        with session_scope() as session:
            row = session.execute(
                select(EmailStore).where(EmailStore.id == email_id)
            ).scalar_one_or_none()
            if not row:
                return

            job_ordersno = row.job_ordersno
            if not job_ordersno and row.wo_execution_doc_sno:
                result = session.execute(
                    text("SELECT PlanningMasSno FROM WoExecutionDoc WHERE WoExecutionDocSno = :sno"),
                    {"sno": row.wo_execution_doc_sno},
                ).scalar_one_or_none()
                if result:
                    job_ordersno = result

            raw_email_b64 = row.raw_email

            if job_ordersno:
                logger.info("Routing to JOB_ORDER story for JOB_ORDERSNO=%s", job_ordersno)
                _generate_job_order_story(session, job_ordersno)
            else:
                logger.info("Routing to per-thread summary (no JOB_ORDERSNO)")
                _generate_thread_summary(session, row)
    except Exception:
        logger.exception("Background combined-summary failed for email_id=%s", email_id)

    # POST to OCR endpoint AFTER session is closed (matched emails only)
    if job_ordersno and raw_email_b64:
        _post_email_to_ocr(email_id, raw_email_b64)
