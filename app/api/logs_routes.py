import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.logging_hub import broadcaster

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/stream")
async def stream_logs() -> StreamingResponse:
    """Server-Sent Events stream: replays the recent buffer, then live-tails new log records."""

    async def event_generator():
        for entry in broadcaster.recent():
            yield f"data: {json.dumps(entry)}\n\n"

        q = broadcaster.subscribe()
        try:
            while True:
                entry = await run_in_threadpool(q.get)
                yield f"data: {json.dumps(entry)}\n\n"
        finally:
            broadcaster.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
