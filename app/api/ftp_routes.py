import logging
import mimetypes

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.config import settings
from app.email_ingest.ftp_client import FtpClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ftp", tags=["ftp"])


def _safe_path(path: str) -> str:
    path = path or "/"
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    return path


@router.get("/list")
def list_dir(path: str = Query(default="/")) -> dict:
    path = _safe_path(path)
    try:
        with FtpClient(settings) as ftp:
            entries = ftp.list_dir(path)
    except Exception as exc:
        logger.exception("FTP list_dir failed for %s", path)
        raise HTTPException(status_code=502, detail=f"FTP error: {exc}") from exc
    return {"path": path, "entries": entries}


@router.get("/file")
def get_file(path: str = Query(...), disposition: str = Query(default="inline")) -> Response:
    path = _safe_path(path)
    try:
        with FtpClient(settings) as ftp:
            data = ftp.download(path)
    except Exception as exc:
        logger.exception("FTP download failed for %s", path)
        raise HTTPException(status_code=502, detail=f"FTP error: {exc}") from exc

    filename = path.rsplit("/", 1)[-1]
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"
    kind = "attachment" if disposition == "attachment" else "inline"

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'{kind}; filename="{filename}"'},
    )
