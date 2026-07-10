import email
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email import policy
from email.message import Message
from email.utils import parsedate_to_datetime

from app.utils.mime_headers import decode_hdr

logger = logging.getLogger(__name__)

MAX_MESSAGE_ID_LEN = 400


@dataclass
class AttachmentPart:
    filename: str
    content_type: str
    content: bytes


@dataclass
class ParsedEmail:
    message_id: str
    message_id_raw: str
    from_address: str
    to_address: str
    cc_address: str
    bcc_address: str
    reply_to: str
    in_reply_to: str
    references_header: str
    subject: str
    date_raw: str
    email_date_utc: datetime
    mail_date: date
    body_text: str
    body_html: str
    raw_headers: str
    attachments: list[AttachmentPart] = field(default_factory=list)


def _normalize_message_id(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if len(raw) <= MAX_MESSAGE_ID_LEN:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
    return f"sha256:{digest}"


def _parse_dates(date_header: str | None) -> tuple[datetime, date]:
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                mail_date = parsed.date()
                email_date_utc = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                return email_date_utc, mail_date
        except (TypeError, ValueError, OverflowError) as exc:
            logger.warning("Failed to parse Date header %r: %s", date_header, exc)

    now = datetime.now(timezone.utc)
    return now.replace(tzinfo=None), now.date()


def _get_text(part: Message) -> str:
    try:
        content = part.get_content()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")
    if isinstance(content, bytes):
        charset = part.get_content_charset() or "utf-8"
        return content.decode(charset, errors="ignore")
    return str(content)


def _get_bytes(part: Message) -> bytes:
    try:
        content = part.get_content()
    except Exception:
        return part.get_payload(decode=True) or b""
    if isinstance(content, str):
        return content.encode("utf-8", errors="ignore")
    return content


def parse_message(raw_bytes: bytes) -> ParsedEmail:
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    message_id_raw = (msg["Message-ID"] or "").strip()
    message_id = _normalize_message_id(message_id_raw)

    date_header = msg["Date"]
    email_date_utc, mail_date = _parse_dates(date_header)

    body_text_parts: list[str] = []
    body_html_parts: list[str] = []
    attachments: list[AttachmentPart] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue

            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()
            filename = part.get_filename()

            is_attachment = bool(filename) and content_disposition in ("attachment", "inline")
            if is_attachment:
                attachments.append(
                    AttachmentPart(
                        filename=decode_hdr(filename),
                        content_type=content_type,
                        content=_get_bytes(part),
                    )
                )
                continue

            if content_type == "text/plain":
                body_text_parts.append(_get_text(part))
            elif content_type == "text/html":
                body_html_parts.append(_get_text(part))
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            body_text_parts.append(_get_text(msg))
        elif content_type == "text/html":
            body_html_parts.append(_get_text(msg))

    raw_headers = "\n".join(f"{key}: {value}" for key, value in msg.items())

    return ParsedEmail(
        message_id=message_id,
        message_id_raw=message_id_raw,
        from_address=decode_hdr(msg["From"]),
        to_address=decode_hdr(msg["To"]),
        cc_address=decode_hdr(msg["Cc"]),
        bcc_address=decode_hdr(msg["Bcc"]),
        reply_to=decode_hdr(msg["Reply-To"]),
        in_reply_to=(msg["In-Reply-To"] or "").strip(),
        references_header=(msg["References"] or "").strip(),
        subject=decode_hdr(msg["Subject"]),
        date_raw=date_header or "",
        email_date_utc=email_date_utc,
        mail_date=mail_date,
        body_text="\n\n".join(p for p in body_text_parts if p),
        body_html="\n\n".join(p for p in body_html_parts if p),
        raw_headers=raw_headers,
        attachments=attachments,
    )
