import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.requests import ClientDisconnect
from strawberry.fastapi import GraphQLRouter

from app.api.ftp_routes import router as ftp_router
from app.api.logs_routes import router as logs_router
from app.api.ocr_routes import router as ocr_router
from app.config import settings
from app.db.session import ensure_schema
from app.email_ingest.idle_listener import start_listener, stop_listener
from app.graphql.schema import schema
from app.logging_hub import broadcaster

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger().addHandler(broadcaster)
logger = logging.getLogger(__name__)

APP_PORT = 8000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up: ensuring schema and launching IMAP IDLE listener")
    ensure_schema()
    start_listener()
    try:
        yield
    finally:
        logger.info("Shutting down: stopping IMAP IDLE listener")
        stop_listener()


app = FastAPI(title="TMS_ImportExport Mail Ingestion Service", lifespan=lifespan)

# No auth on this API by design (internal-network dashboard); harmless to leave
# permissive even though the frontend is now same-origin (served by this app).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ClientDisconnect)
async def _client_disconnect_handler(request, exc: ClientDisconnect):
    logger.warning("Client disconnected before GraphQL response could be sent")
    return Response(status_code=499)

graphql_router = GraphQLRouter(schema)
app.include_router(graphql_router, prefix="/graphql")
app.include_router(ftp_router)
app.include_router(logs_router)
app.include_router(ocr_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built React dashboard (frontend/dist, produced by `npm run build`)
# from this same app/port. Mounted last so it only catches paths not already
# matched by the API routes above.
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    logger.warning("frontend/dist not found (run `npm run build` in frontend/) - dashboard UI will not be served")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=APP_PORT)
