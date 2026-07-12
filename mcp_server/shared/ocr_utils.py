"""ocr_utils.py — shared OCR helper used by content extraction and step 3
(fact-checking text found inside images)."""

from PIL import Image

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


def extract_text(image: Image.Image) -> str:
    if not HAS_TESSERACT:
        return ""
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""
