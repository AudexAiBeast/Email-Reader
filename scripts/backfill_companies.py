"""
One-time backfill: assign company names to existing emails that have NULL company_name.
Run from the Email-Reader directory:
    python scripts/backfill_companies.py
"""
import sys
sys.path.insert(0, '.')

import logging
from sqlalchemy import select

from app.company.detector import extract_company_name
from app.db.models import EmailStore
from app.db.session import session_scope

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def backfill():
    with session_scope() as session:
        rows = session.execute(
            select(EmailStore).where(EmailStore.company_name.is_(None))
        ).scalars().all()

        logger.info("Found %s emails without company name", len(rows))
        updated = 0

        for row in rows:
            company_info = extract_company_name(
                row.from_address or "",
                row.body_text or row.body_html or "",
            )
            company_name = company_info.get("company_name")
            if company_name:
                row.company_name = company_name
                row.company_domain_source = company_info.get("domain_source")
                row.company_signature_source = company_info.get("signature_source")
                updated += 1
                logger.info(
                    "id=%s -> %s (domain=%s sig=%s)",
                    row.id, company_name,
                    company_info.get("domain_source"),
                    company_info.get("signature_source"),
                )
            else:
                row.company_name = "Uncategorized"
                updated += 1
                logger.info("id=%s -> Uncategorized (no signals found)", row.id)

        session.commit()
        logger.info("Done. Updated %s emails.", updated)


if __name__ == "__main__":
    backfill()
