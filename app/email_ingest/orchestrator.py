import hashlib
import json
import logging
import posixpath
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.models import EmailStore
from app.db.session import session_scope
from app.email_ingest.attachment_classifier import classify, sanitize_filename
from app.email_ingest.ftp_client import FtpClient
from app.email_ingest.mime_parser import ParsedEmail, parse_message

logger = logging.getLogger(__name__)


def _upload_attachments(parsed: ParsedEmail) -> tuple[dict[str, dict[str, str]], int]:
    """Uploads every attachment to FTP under <dir>/<mail_date>/<category>/<ts>_<idx>_<name>.

    A failed upload is logged and simply omitted from the returned JSON structure;
    it never raises, so a partial failure still lets the email row get saved.
    """
    attachments_json: dict[str, dict[str, str]] = {}
    if not parsed.attachments:
        return attachments_json, 0

    processed_at = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    category_indexes: dict[str, int] = {}
    uploaded_count = 0

    try:
        with FtpClient(settings) as ftp:
            for attachment in parsed.attachments:
                category = classify(attachment.filename)
                idx = category_indexes.get(category, 0) + 1
                category_indexes[category] = idx

                safe_name = sanitize_filename(attachment.filename)
                filename = f"{processed_at}_{idx}_{safe_name}"
                remote_dir = posixpath.join(settings.ftp_directory, parsed.mail_date.isoformat(), category)

                try:
                    remote_path = ftp.upload(remote_dir, filename, attachment.content)
                except Exception:
                    logger.exception(
                        "Failed to upload attachment %r (category=%s) for message_id=%s",
                        attachment.filename,
                        category,
                        parsed.message_id,
                    )
                    continue

                attachments_json.setdefault(category, {})[str(idx)] = remote_path
                uploaded_count += 1
    except Exception:
        logger.exception(
            "Failed to establish FTP connection while processing message_id=%s; "
            "email will be saved with no attachments",
            parsed.message_id,
        )

    return attachments_json, uploaded_count


def process_message(raw_bytes: bytes, uid: int, mailbox: str) -> bool:
    """Processes one raw RFC822 message end to end.

    Returns True if the caller may safely advance past this UID (either the
    message was stored successfully, it was already stored before, or it is
    permanently unparseable). Returns False on a transient failure (DB/parse
    infra issue) so the caller retries it on the next pass instead of losing it.
    """
    try:
        parsed = parse_message(raw_bytes)
    except Exception:
        logger.exception("Permanently failed to parse message uid=%s in mailbox=%s; skipping", uid, mailbox)
        return True

    message_id = parsed.message_id or f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"

    try:
        with session_scope() as session:
            existing = session.execute(
                select(EmailStore.id).where(EmailStore.message_id == message_id)
            ).scalar_one_or_none()
            if existing is not None:
                logger.info("message_id=%s already stored (id=%s), skipping re-ingest", message_id, existing)
                return True

            attachments_json, attachment_count = _upload_attachments(parsed)

            row = EmailStore(
                message_id=message_id,
                message_id_raw=parsed.message_id_raw,
                from_address=parsed.from_address or None,
                to_address=parsed.to_address or None,
                cc_address=parsed.cc_address or None,
                bcc_address=parsed.bcc_address or None,
                reply_to=parsed.reply_to or None,
                in_reply_to=parsed.in_reply_to or None,
                references_header=parsed.references_header or None,
                subject=parsed.subject or None,
                date_raw=parsed.date_raw or None,
                email_date_utc=parsed.email_date_utc,
                mail_date=parsed.mail_date,
                body_text=parsed.body_text or None,
                body_html=parsed.body_html or None,
                raw_headers=parsed.raw_headers or None,
                attachments=json.dumps(attachments_json) if attachments_json else None,
                has_attachments=bool(attachments_json),
                attachment_count=attachment_count,
                mailbox=mailbox,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info("message_id=%s hit unique-constraint race, treating as already stored", message_id)
                return True

            logger.info(
                "Stored message_id=%s uid=%s subject=%r attachments=%s",
                message_id,
                uid,
                parsed.subject,
                attachment_count,
            )
            return True
    except Exception:
        logger.exception("Transient failure storing uid=%s message_id=%s; will retry", uid, message_id)
        return False
