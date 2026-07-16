import datetime
from typing import Optional

import strawberry
from sqlalchemy import func, select
from sqlalchemy.orm import Query

from app.config import settings
from app.company.ollama_client import summarize_thread
from app.db.models import EmailStore
from app.db.session import session_scope
from app.graphql.types import CompanyFolder, EmailConnection, EmailOrderBy, EmailType


@strawberry.type
class Query:
    @strawberry.field(description="List all company folders with email counts.")
    def folders(self) -> list[CompanyFolder]:
        with session_scope() as session:
            rows = (
                session.execute(
                    select(EmailStore.company_name, func.count().label("cnt"))
                    .where(EmailStore.company_name.isnot(None))
                    .group_by(EmailStore.company_name)
                    .order_by(func.count().desc())
                )
                .all()
            )
            uncategorized_count = (
                session.execute(
                    select(func.count())
                    .where(EmailStore.company_name.is_(None))
                )
                .scalar_one()
            )
            folders = [CompanyFolder(name=r.company_name, count=r.cnt) for r in rows]
            if uncategorized_count > 0:
                folders.append(CompanyFolder(name="Uncategorized", count=uncategorized_count))
            return folders

    @strawberry.field(description="Look up a single email by its Message-ID.")
    def email(self, message_id: str) -> Optional[EmailType]:
        with session_scope() as session:
            row = session.execute(
                select(EmailStore).where(EmailStore.message_id == message_id)
            ).scalar_one_or_none()
            return EmailType.from_model(row) if row else None

    @strawberry.field(description="Generate or retrieve AI summary for an email thread.")
    def email_summary(self, email_id: int) -> Optional[str]:
        with session_scope() as session:
            row = session.execute(
                select(EmailStore).where(EmailStore.id == email_id)
            ).scalar_one_or_none()
            if not row:
                return None
            if row.ai_summary:
                return row.ai_summary
            thread_text = row.body_text or row.body_html or ""
            if thread_text.startswith("<"):
                import re
                thread_text = re.sub(r"<[^>]+>", "", thread_text)
                thread_text = re.sub(r"\s+", " ", thread_text).strip()
            if not thread_text.strip():
                return None
            summary = summarize_thread(thread_text)
            if summary:
                row.ai_summary = summary
                session.commit()
            return summary

    @strawberry.field(description="Filter/paginate stored emails. Read-only API.")
    def emails(
        self,
        date: Optional[datetime.date] = None,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
        sender: Optional[str] = None,
        subject_contains: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        company_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: EmailOrderBy = EmailOrderBy.DATE_DESC,
    ) -> EmailConnection:
        limit = max(1, min(limit, settings.graphql_max_page_size))
        offset = max(0, offset)

        conditions = []
        if date is not None:
            conditions.append(EmailStore.mail_date == date)
        if date_from is not None:
            conditions.append(EmailStore.mail_date >= date_from)
        if date_to is not None:
            conditions.append(EmailStore.mail_date <= date_to)
        if sender:
            conditions.append(EmailStore.from_address.ilike(f"%{sender}%"))
        if subject_contains:
            conditions.append(EmailStore.subject.ilike(f"%{subject_contains}%"))
        if has_attachments is not None:
            conditions.append(EmailStore.has_attachments == has_attachments)
        if company_name is not None:
            if company_name == "Uncategorized":
                conditions.append(EmailStore.company_name.is_(None))
            else:
                conditions.append(EmailStore.company_name == company_name)

        with session_scope() as session:
            stmt = select(EmailStore)
            count_stmt = select(func.count()).select_from(EmailStore)
            for condition in conditions:
                stmt = stmt.where(condition)
                count_stmt = count_stmt.where(condition)

            if order_by == EmailOrderBy.DATE_ASC:
                stmt = stmt.order_by(EmailStore.email_date_utc.asc())
            else:
                stmt = stmt.order_by(EmailStore.email_date_utc.desc())

            stmt = stmt.limit(limit).offset(offset)

            rows = session.execute(stmt).scalars().all()
            total_count = session.execute(count_stmt).scalar_one()

            items = [EmailType.from_model(row) for row in rows]
            return EmailConnection(
                items=items,
                total_count=total_count,
                limit=limit,
                offset=offset,
                has_more=offset + len(items) < total_count,
            )
