import re
from pathlib import PurePosixPath

CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".heic", ".heif"},
    "excel": {".xls", ".xlsx", ".xlsm", ".csv", ".ods"},
    "word": {".doc", ".docx", ".dot", ".dotx", ".rtf", ".odt"},
    "pdf": {".pdf"},
}
OTHERS_CATEGORY = "others"

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
MAX_BASENAME_LEN = 150


def classify(filename: str) -> str:
    ext = PurePosixPath(filename).suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return OTHERS_CATEGORY


def sanitize_filename(filename: str, fallback_ext: str = ".bin") -> str:
    filename = (filename or "").strip()
    # Strip any path components an attacker/broken client might smuggle in.
    filename = PurePosixPath(filename).name.replace("\\", "_")
    if not filename:
        return f"attachment{fallback_ext}"

    stem = PurePosixPath(filename).stem
    ext = PurePosixPath(filename).suffix

    stem = _UNSAFE_CHARS.sub("_", stem).strip("_") or "attachment"
    ext = _UNSAFE_CHARS.sub("", ext)

    if len(stem) + len(ext) > MAX_BASENAME_LEN:
        stem = stem[: max(1, MAX_BASENAME_LEN - len(ext))]

    return f"{stem}{ext}" if ext else stem
