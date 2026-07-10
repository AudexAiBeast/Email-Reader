import logging
import queue
import threading
from collections import deque
from datetime import datetime, timezone

BUFFER_SIZE = 500


class LogBroadcaster(logging.Handler):
    """Thread-safe logging.Handler that keeps a ring buffer and fans out new
    records to any number of subscriber queues, for the live log SSE endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=BUFFER_SIZE)
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        with self._lock:
            self._buffer.append(entry)
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(entry)

    def recent(self) -> list[dict]:
        with self._lock:
            return list(self._buffer)

    def subscribe(self) -> "queue.Queue[dict]":
        q: "queue.Queue[dict]" = queue.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            self._subscribers.discard(q)


broadcaster = LogBroadcaster()
broadcaster.setFormatter(logging.Formatter("%(message)s"))
