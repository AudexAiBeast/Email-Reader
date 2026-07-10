import logging
import random
import threading

from imapclient import IMAPClient

from app.config import settings
from app.db.models import EmailSyncState
from app.db.session import session_scope
from app.email_ingest.orchestrator import process_message

logger = logging.getLogger(__name__)


class ImapIdleListener:
    """Runs a persistent IMAP IDLE connection in a background thread and ingests new mail."""

    def __init__(self) -> None:
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="imap-idle-listener", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30) -> None:
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        attempt = 0
        while not self._shutdown.is_set():
            try:
                self._connect_and_loop()
                attempt = 0
            except Exception:
                logger.exception("IMAP IDLE listener error; will reconnect")
                attempt += 1
                backoff = min(
                    settings.imap_reconnect_max_seconds,
                    settings.imap_reconnect_base_seconds * (2 ** (attempt - 1)),
                )
                backoff *= 0.5 + random.random()
                logger.info("Reconnecting in %.1fs (attempt %s)", backoff, attempt)
                self._shutdown.wait(backoff)

    def _connect_and_loop(self) -> None:
        with IMAPClient(
            settings.imap_server,
            port=settings.imap_port,
            use_uid=True,
            ssl=True,
            timeout=settings.imap_socket_timeout_seconds,
        ) as client:
            client.login(settings.email_user, settings.email_pass)
            select_info = client.select_folder(settings.mailbox, readonly=True)
            uidvalidity = select_info[b"UIDVALIDITY"]

            logger.info(
                "Connected to %s mailbox=%s UIDVALIDITY=%s", settings.imap_server, settings.mailbox, uidvalidity
            )

            self._run_backlog_recovery(client, uidvalidity)

            while not self._shutdown.is_set():
                client.idle()
                try:
                    client.idle_check(timeout=settings.idle_renew_seconds)
                finally:
                    client.idle_done()

                if self._shutdown.is_set():
                    break
                self._run_backlog_recovery(client, uidvalidity)

    def _run_backlog_recovery(self, client: IMAPClient, uidvalidity: int) -> None:
        mailbox = settings.mailbox

        with session_scope() as session:
            state = session.get(EmailSyncState, mailbox)
            if state is None:
                # First-ever run for this mailbox: baseline to the current highest UID so
                # only mail arriving from now on gets ingested (no historical backfill).
                all_uids = client.search("ALL")
                last_uid = max(all_uids) if all_uids else 0
                session.add(EmailSyncState(mailbox=mailbox, uidvalidity=uidvalidity, last_uid=last_uid))
                session.commit()
                logger.info(
                    "Initialized sync state for mailbox=%s at uid=%s (no historical backfill)", mailbox, last_uid
                )
                return

            if state.uidvalidity != uidvalidity:
                logger.warning(
                    "UIDVALIDITY changed for mailbox=%s (%s -> %s); resetting last_uid. "
                    "message_id dedup in EmailStore still prevents duplicate rows.",
                    mailbox,
                    state.uidvalidity,
                    uidvalidity,
                )
                state.uidvalidity = uidvalidity
                state.last_uid = 0
                session.commit()

            last_uid = state.last_uid

        uids = client.search(["UID", f"{last_uid + 1}:*"])
        # RFC 3501 "n:*" quirk: can return the highest existing UID even when none qualify.
        uids = sorted(uid for uid in uids if uid > last_uid)
        if not uids:
            return

        logger.info("Backlog recovery: %s new message(s) in mailbox=%s", len(uids), mailbox)
        for uid in uids:
            if self._shutdown.is_set():
                break

            try:
                response = client.fetch([uid], ["RFC822"])
            except Exception:
                # A timed-out/failed FETCH can leave the IMAP connection's protocol state
                # inconsistent, so don't retry on this same socket. Permanently skip this UID
                # (a server that can't serve a message once generally never will) and force a
                # fresh reconnect by re-raising, instead of hanging the whole pipeline forever.
                logger.exception(
                    "FETCH failed for uid=%s in mailbox=%s; skipping it permanently and reconnecting", uid, mailbox
                )
                self._advance_uid(mailbox, uid)
                raise

            raw = response.get(uid, {}).get(b"RFC822")
            if raw is None:
                logger.warning("No RFC822 body returned for uid=%s, skipping", uid)
                self._advance_uid(mailbox, uid)
                continue

            ok = process_message(raw, uid, mailbox)
            if not ok:
                logger.warning("Transient failure processing uid=%s; will retry on next pass", uid)
                break

            self._advance_uid(mailbox, uid)

    def _advance_uid(self, mailbox: str, uid: int) -> None:
        with session_scope() as session:
            state = session.get(EmailSyncState, mailbox)
            if state is not None:
                state.last_uid = uid
                session.commit()


_listener: ImapIdleListener | None = None


def start_listener() -> None:
    global _listener
    if _listener is None:
        _listener = ImapIdleListener()
        _listener.start()


def stop_listener() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None
