"""ocr_utils.py — optional OCR helper.

Tesseract OCR is completely optional. If Tesseract is not installed or
disabled via environment / settings, this helper returns an empty string
without error. The pipeline will automatically rely on the multimodal vision
model (Gemini, Grok, or Ollama's vision model) instead.
"""

import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

HAS_PYTESSERACT = False
try:
    import pytesseract
    HAS_PYTESSERACT = True
    # Check default Windows Tesseract paths
    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            break
except ImportError:
    pass

_OCR_CHECKED = False
_OCR_AVAILABLE = False


def is_ocr_available() -> bool:
    """Return True if pytesseract and the tesseract binary are actually usable."""
    global _OCR_CHECKED, _OCR_AVAILABLE
    if not HAS_PYTESSERACT:
        return False
    if _OCR_CHECKED:
        return _OCR_AVAILABLE

    _OCR_CHECKED = True
    try:
        # Quick version check to verify the binary is reachable
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception as e:
        logger.info("Tesseract binary not found (%s) — OCR features will be skipped gracefully.", e)
        _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


def extract_text(image: Image.Image) -> str:
    """Extract text from an image if Tesseract is installed and enabled.
    Returns an empty string safely if OCR is unavailable or fails.
    """
    if not is_ocr_available():
        return ""

    try:
        # Preprocessing: Grayscale + 2x resize for small/low-res text
        gray = image.convert("L")
        if gray.width < 1200 and gray.height < 1200:
            large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
            text = pytesseract.image_to_string(large).strip()
        else:
            text = pytesseract.image_to_string(gray).strip()

        if len(text) < 5:
            text = pytesseract.image_to_string(image).strip()

        # Clean non-printable characters
        lines = []
        for line in text.splitlines():
            line_cleaned = "".join(c for c in line.strip() if c.isprintable()).strip()
            if len(line_cleaned) >= 2 and not all(c in r"\/|~_<>*#@+[]{}()=" for c in line_cleaned):
                lines.append(line_cleaned)

        return "\n".join(lines)
    except Exception as err:
        logger.debug("Tesseract OCR extraction failed gracefully: %s", err)
        return ""


def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from image bytes if OCR is available."""
    if not is_ocr_available() or not data:
        return ""
    try:
        import io
        img = Image.open(io.BytesIO(data))
        return extract_text(img)
    except Exception:
        return ""


def extract_text_from_path(path: str) -> str:
    """Extract text from an image file path if OCR is available."""
    if not is_ocr_available() or not os.path.exists(path):
        return ""
    try:
        img = Image.open(path)
        return extract_text(img)
    except Exception:
        return ""
