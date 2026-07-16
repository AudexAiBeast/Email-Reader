import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.email_ingest.ocr_pipeline import get_stored_markdown_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.get("/markdown")
def get_ocr_markdown(path: str = Query(...)) -> PlainTextResponse:
    safe_path = path.replace("\\", "/")
    if ".." in safe_path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    md_path = get_stored_markdown_path(safe_path)
    if md_path is None:
        raise HTTPException(status_code=404, detail="OCR markdown not found")
    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read markdown: {exc}") from exc
    return PlainTextResponse(content, media_type="text/markdown")
