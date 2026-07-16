import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OCR_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "ocr_output"
OCR_EXTRACTED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"})
SKIP_EXTENSIONS = frozenset({".xls", ".xlsx", ".xlsm", ".csv", ".ods"})

def _hash_filename(original_name: str, email_message_id: str) -> str:
    raw = f"{email_message_id}::{original_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def classify_ocr_target(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return "skip"
    if ext in OCR_EXTRACTED_EXTENSIONS:
        return "ocr"
    return "skip"

# TODO: Replace with real MinerU OCR integration
def run_mineru_ocr(file_bytes: bytes, filename: str) -> str:
    """
    Stub for MinerU OCR processing.
    TODO: replace with real MinerU OCR integration

    Currently returns placeholder markdown text. When real MinerU is wired up,
    this function should call the MinerU pipeline on the file bytes and return
    the extracted text as markdown.
    """
    ext = Path(filename).suffix.lower()
    placeholder_text = (
        f"---\n"
        f"# OCR Extracted Content\n"
        f"**Source file:** {filename}\n"
        f"**Processed by:** MinerU OCR\n"
        f"**Status:** Placeholder (real MinerU integration pending)\n"
        f"---\n\n"
        f"*File type: {ext}*\n"
        f"*Size: {len(file_bytes)} bytes*\n\n"
        f"## Extracted Text\n\n"
        f"[TODO: Actual OCR text will appear here once MinerU is integrated.]\n"
        f"---\n"
        f"*End of OCR output*\n"
    )
    return placeholder_text

def process_attachment(
    filename: str,
    file_bytes: bytes,
    email_message_id: str,
    category: str,
) -> Optional[dict]:
    action = classify_ocr_target(filename)
    if action == "skip":
        logger.info("Skipping OCR for %s (file type not processed)", filename)
        return None
    ocr_dir = OCR_STORAGE_DIR
    ocr_dir.mkdir(parents=True, exist_ok=True)
    hash_prefix = _hash_filename(filename, email_message_id)
    md_filename = f"{hash_prefix}_{Path(filename).stem}.md"
    md_path = ocr_dir / md_filename
    markdown_content = run_mineru_ocr(file_bytes, filename)
    try:
        md_path.write_text(markdown_content, encoding="utf-8")
        logger.info("OCR markdown saved to %s", md_path)
    except Exception as exc:
        logger.error("Failed to write OCR markdown for %s: %s", filename, exc)
        return None
    return {
        "filename": md_filename,
        "path": str(md_path.relative_to(OCR_STORAGE_DIR.parent)),
        "original": filename,
    }

def get_stored_markdown_path(relative_path: str) -> Optional[Path]:
    full_path = OCR_STORAGE_DIR.parent / relative_path
    if full_path.exists() and full_path.suffix == ".md":
        return full_path
    return None
