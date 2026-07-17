"""
One-time backfill: assign company names to existing emails that have NULL company_name.
Run from the Email-Reader directory:
    python scripts/backfill_companies.py
"""
import sys
sys.path.insert(0, '.')

import logging
from collections import defaultdict

from sqlalchemy import select, update

from app.company.detector import _core_name, extract_company_name
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


def merge_similar():
    with session_scope() as session:
        rows = session.execute(
            select(EmailStore.company_name)
            .where(EmailStore.company_name.isnot(None))
            .where(EmailStore.company_name != "Uncategorized")
            .where(EmailStore.company_name != "System Notifications")
            .distinct()
        ).scalars().all()

        groups = defaultdict(list)
        for name in rows:
            core = _core_name(name)
            groups[core].append(name)

        all_names = list(rows)
        naked = {n: _core_name(n).replace(" ", "") for n in all_names}

        renames = {}
        for core, names in groups.items():
            if len(names) > 1:
                best = max(names, key=len)
                for n in names:
                    if n != best:
                        renames[n] = best
                        logger.info("Merge: %r -> %r", n, best)

        for a in all_names:
            for b in all_names:
                if a == b or a in renames or b in renames:
                    continue
                ac = naked[a]
                bc = naked[b]
                if len(ac) >= 5 and len(bc) >= 5:
                    if ac in bc or bc in ac:
                        best = max(a, b, key=len)
                        worst = a if best == b else b
                        renames[worst] = best
                        logger.info("Merge (fuzzy): %r -> %r", worst, best)

        if not renames:
            logger.info("No similar company names to merge.")
            return

        for old, new in renames.items():
            session.execute(
                update(EmailStore)
                .where(EmailStore.company_name == old)
                .values(company_name=new)
            )
        session.commit()
        logger.info("Merged %s company name variants.", len(renames))


if __name__ == "__main__":
    backfill()
    merge_similar()
