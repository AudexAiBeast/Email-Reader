import datetime

from sqlalchemy import BigInteger, Boolean, Identity, Integer, UniqueConstraint
from sqlalchemy.dialects.mssql import DATE, DATETIME2, NVARCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EmailStore(Base):
    __tablename__ = "EmailStore"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1), primary_key=True)

    message_id: Mapped[str] = mapped_column(NVARCHAR(400), nullable=False)
    message_id_raw: Mapped[str] = mapped_column(NVARCHAR("max"), nullable=False)

    from_address: Mapped[str | None] = mapped_column(NVARCHAR(998))
    to_address: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    cc_address: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    bcc_address: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    reply_to: Mapped[str | None] = mapped_column(NVARCHAR(998))
    in_reply_to: Mapped[str | None] = mapped_column(NVARCHAR(998))
    references_header: Mapped[str | None] = mapped_column(NVARCHAR("max"))

    subject: Mapped[str | None] = mapped_column(NVARCHAR(998))
    date_raw: Mapped[str | None] = mapped_column(NVARCHAR(255))
    email_date_utc: Mapped[datetime.datetime] = mapped_column(DATETIME2(precision=3), nullable=False)
    mail_date: Mapped[datetime.date] = mapped_column(DATE, nullable=False)

    body_text: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    body_html: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    raw_headers: Mapped[str | None] = mapped_column(NVARCHAR("max"))

    attachments: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    company_name: Mapped[str | None] = mapped_column(NVARCHAR(255))
    company_domain_source: Mapped[str | None] = mapped_column(NVARCHAR(255))
    company_signature_source: Mapped[str | None] = mapped_column(NVARCHAR(255))

    ai_summary: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    ocr_markdown_paths: Mapped[str | None] = mapped_column(NVARCHAR("max"))
    raw_email: Mapped[str | None] = mapped_column(NVARCHAR("max"))

    job_ordersno: Mapped[int | None] = mapped_column("JOB_ORDERSNO", Integer)
    wo_execution_doc_sno: Mapped[int | None] = mapped_column("WoExecutionDocSno", Integer)

    mailbox: Mapped[str | None] = mapped_column(NVARCHAR(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DATETIME2(precision=3), nullable=False, default=datetime.datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("message_id", name="UQ_EmailStore_message_id"),)


class AiSummaryEvent(Base):
    __tablename__ = "ai_summary_event"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1), primary_key=True)
    source_table: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    source_sno: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_summary: Mapped[str] = mapped_column(NVARCHAR("max"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DATETIME2(precision=3), nullable=False, default=datetime.datetime.utcnow
    )


class EmailSyncState(Base):
    __tablename__ = "email_sync_state"

    mailbox: Mapped[str] = mapped_column(NVARCHAR(255), primary_key=True)
    uidvalidity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_uid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DATETIME2(precision=3), nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
