import datetime

import strawberry
from sqlalchemy import func, select

from app.config import settings
from app.db.models import EmailStore
from app.db.session import session_scope
from app.graphql.types import EmailConnection, EmailOrderBy, EmailType


@strawberry.type
class Query:
    @strawberry.field(description="Look up a single email by its Message-ID (as stored, post sha256 normalization).")
    def email(self, message_id: str) -> EmailType | None:
        with session_scope() as session:
            row = session.execute(select(EmailStore).where(EmailStore.message_id == message_id)).scalar_one_or_none()
            return EmailType.from_model(row) if row else None

    @strawberry.field(description="Filter/paginate stored emails. Read-only — no mutations exist in this API.")
    def emails(
        self,
        date: datetime.date | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        sender: str | None = None,
        subject_contains: str | None = None,
        has_attachments: bool | None = None,
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
