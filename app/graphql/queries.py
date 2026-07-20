import datetime
import re
import threading
from typing import Optional

import strawberry
from sqlalchemy import func, or_, select

from app.config import settings
from app.company.ollama_client import summarize_thread
from app.db.models import EmailStore
from app.db.session import session_scope
from app.graphql.types import CompanyFolder, EmailConnection, EmailOrderBy, EmailType

_RE_PREFIX = re.compile(r"^(?:\s*(?:re|fwd?|aw|wg|ref|sv|vs|antw|odp|答复|转发)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)

_summary_locks = {}
_summary_lock = threading.Lock()


def _normalize_subject(subject: Optional[str]) -> str:
    if not subject:
        return ""
    s = _RE_PREFIX.sub("", subject).strip()
    return s.lower() if s else subject.lower().strip()


def _assemble_thread(row, session) -> str:
    thread_msgs = {}
    thread_msgs[row.message_id] = row

    norm = _normalize_subject(row.subject)
    if norm:
        candidates = session.execute(
            select(EmailStore).where(
                EmailStore.id != row.id,
                func.lower(EmailStore.subject).contains(norm),
            )
        ).scalars().all()
        for c in candidates:
            thread_msgs[c.message_id] = c

    raw_ids = set()
    if row.in_reply_to:
        rid = row.in_reply_to.strip().strip("<>")
        if rid:
            raw_ids.add(rid)
    if row.references_header:
        for ref in re.findall(r"<[^>]+>", row.references_header):
            raw_ids.add(ref.strip("<>"))

    if raw_ids:
        parents = session.execute(
            select(EmailStore).where(
                or_(EmailStore.message_id_raw.in_(raw_ids), EmailStore.message_id.in_(raw_ids))
            )
        ).scalars().all()
        for p in parents:
            thread_msgs[p.message_id] = p

        children = session.execute(
            select(EmailStore).where(EmailStore.in_reply_to.in_(raw_ids))
        ).scalars().all()
        for c in children:
            thread_msgs[c.message_id] = c

    sorted_msgs = sorted(thread_msgs.values(), key=lambda m: m.email_date_utc)

    parts = []
    for msg in sorted_msgs:
        body = msg.body_text or msg.body_html or ""
        if body.startswith("<"):
            body = re.sub(r"<[^>]+>", "", body)
            body = re.sub(r"\s+", " ", body).strip()
        sender = msg.from_address or "unknown"
        subject = msg.subject or "(no subject)"
        date = msg.date_raw or str(msg.email_date_utc)[:19]
        parts.append(f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}")

    return "\n\n---\n\n".join(parts)


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

            norm = _normalize_subject(row.subject)
            if norm:
                sibling_summary = session.execute(
                    select(EmailStore.ai_summary)
                    .where(EmailStore.id != email_id)
                    .where(func.lower(EmailStore.subject).contains(norm))
                    .where(EmailStore.ai_summary.isnot(None))
                    .order_by(EmailStore.email_date_utc.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if sibling_summary:
                    return sibling_summary

        # Resolve JOB_ORDERSNO (direct or via WoExecutionDoc)
        jo_sno = row.job_ordersno
        if not jo_sno and row.wo_execution_doc_sno:
            from sqlalchemy import text as _text
            with session_scope() as s2:
                result = s2.execute(
                    _text("SELECT PlanningMasSno FROM WoExecutionDoc WHERE WoExecutionDocSno = :sno"),
                    {"sno": row.wo_execution_doc_sno},
                ).scalar_one_or_none()
                if result:
                    jo_sno = result
        lock_key = jo_sno if jo_sno else email_id

        with _summary_lock:
            if lock_key in _summary_locks:
                return None
            _summary_locks[lock_key] = True

        try:
            with session_scope() as session:
                row = session.execute(
                    select(EmailStore).where(EmailStore.id == email_id)
                ).scalar_one_or_none()
                if not row:
                    return None
                if row.ai_summary:
                    return row.ai_summary
                thread_text = _assemble_thread(row, session)
                if not thread_text.strip():
                    return None
                summary = summarize_thread(thread_text)
                if summary:
                    row.ai_summary = summary
                    session.commit()
                return summary
        finally:
            with _summary_lock:
                _summary_locks.pop(lock_key, None)

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
