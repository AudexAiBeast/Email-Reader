import datetime
import enum
import json
from typing import Any

import strawberry


@strawberry.type
class AttachmentEntry:
    category: str
    index: int
    filename: str
    ftp_path: str


@strawberry.type
class OcrEntry:
    filename: str
    path: str
    original: str


@strawberry.enum
class EmailOrderBy(enum.Enum):
    DATE_DESC = "DATE_DESC"
    DATE_ASC = "DATE_ASC"


@strawberry.type
class CompanyFolder:
    name: str
    count: int


@strawberry.type
class EmailType:
    id: int
    message_id: str
    from_address: str | None
    to_address: str | None
    cc_address: str | None
    bcc_address: str | None
    reply_to: str | None
    in_reply_to: str | None
    references: str | None
    subject: str | None
    date_raw: str | None
    email_date: datetime.datetime
    mail_date: datetime.date
    body_text: str | None
    body_html: str | None
    raw_headers: str | None
    has_attachments: bool
    attachment_count: int
    attachments: list[AttachmentEntry]
    company_name: str | None
    company_domain_source: str | None
    company_signature_source: str | None
    ai_summary: str | None
    ocr_markdown_paths: list[OcrEntry] | None
    created_at: datetime.datetime

    @staticmethod
    def from_model(row: Any) -> "EmailType":
        attachments_list: list[AttachmentEntry] = []
        if row.attachments:
            try:
                data = json.loads(row.attachments)
            except (json.JSONDecodeError, TypeError):
                data = {}
            for category, entries in data.items():
                for index_str, path in entries.items():
                    filename = path.rsplit("/", 1)[-1]
                    attachments_list.append(
                        AttachmentEntry(category=category, index=int(index_str), filename=filename, ftp_path=path)
                    )

        ocr_list: list[OcrEntry] = []
        if row.ocr_markdown_paths:
            try:
                ocr_data = json.loads(row.ocr_markdown_paths)
                ocr_list = [OcrEntry(**e) for e in ocr_data]
            except (json.JSONDecodeError, TypeError, Exception):
                pass

        return EmailType(
            id=row.id,
            message_id=row.message_id,
            from_address=row.from_address,
            to_address=row.to_address,
            cc_address=row.cc_address,
            bcc_address=row.bcc_address,
            reply_to=row.reply_to,
            in_reply_to=row.in_reply_to,
            references=row.references_header,
            subject=row.subject,
            date_raw=row.date_raw,
            email_date=row.email_date_utc,
            mail_date=row.mail_date,
            body_text=row.body_text,
            body_html=row.body_html,
            raw_headers=row.raw_headers,
            has_attachments=row.has_attachments,
            attachment_count=row.attachment_count,
            attachments=attachments_list,
            company_name=row.company_name,
            company_domain_source=row.company_domain_source,
            company_signature_source=row.company_signature_source,
            ai_summary=row.ai_summary,
            ocr_markdown_paths=ocr_list if ocr_list else None,
            created_at=row.created_at,
        )


@strawberry.type
class EmailConnection:
    items: list[EmailType]
    total_count: int
    limit: int
    offset: int
    has_more: bool
