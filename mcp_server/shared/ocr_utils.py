import logging
import os
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)
HAS_PYTESSERACT = False
pytesseract: Any = None
try:
    import pytesseract

    HAS_PYTESSERACT = True
    for candidate in [
        "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ]:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
except ImportError:
    pass
_OCR_CHECKED = False
_OCR_AVAILABLE = False


def is_ocr_available() -> bool:
    global _OCR_CHECKED, _OCR_AVAILABLE
    if not HAS_PYTESSERACT or pytesseract is None:
        return False
    if _OCR_CHECKED:
        return _OCR_AVAILABLE
    _OCR_CHECKED = True
    try:
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception as e:
        logger.info("Tesseract binary not found (%s) — OCR features will be skipped gracefully.", e)
        _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


def extract_text(image: Image.Image) -> str:
    if not is_ocr_available() or pytesseract is None:
        return ""
    try:
        gray = image.convert("L")
        if gray.width < 1200 and gray.height < 1200:
            large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
            text = pytesseract.image_to_string(large).strip()
        else:
            text = pytesseract.image_to_string(gray).strip()
        if len(text) < 5:
            text = pytesseract.image_to_string(image).strip()
        lines = []
        for line in text.splitlines():
            line_cleaned = "".join((c for c in line.strip() if c.isprintable())).strip()
            if len(line_cleaned) >= 2 and (
                not all((c in "\\/|~_<>*#@+[]{}()=" for c in line_cleaned))
            ):
                lines.append(line_cleaned)
        return "\n".join(lines)
    except Exception as err:
        logger.debug("Tesseract OCR extraction failed gracefully: %s", err)
        return ""


def extract_text_from_bytes(data: bytes) -> str:
    if not is_ocr_available() or not data:
        return ""
    try:
        import io

        img = Image.open(io.BytesIO(data))
        return extract_text(img)
    except Exception:
        return ""


def extract_text_from_path(path: str) -> str:
    if not is_ocr_available() or not os.path.exists(path):
        return ""
    try:
        img = Image.open(path)
        return extract_text(img)
    except Exception:
        return ""
