"""ocr_utils.py — shared OCR helper used by content extraction and step 3
(fact-checking text found inside images)."""

from PIL import Image

try:
    import pytesseract
    import os
    HAS_TESSERACT = True
    # Default Windows Tesseract path
    tesseract_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_win_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_win_path
except ImportError:
    HAS_TESSERACT = False


def extract_text(image: Image.Image) -> str:
    if not HAS_TESSERACT:
        return ""
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""
