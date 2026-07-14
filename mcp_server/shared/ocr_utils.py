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
        # Preprocessing: Grayscale + 2x resize for better OCR on small/low-res text
        gray = image.convert('L')
        large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        
        text_raw = pytesseract.image_to_string(image).strip()
        text_processed = pytesseract.image_to_string(large).strip()
        text_psm11 = pytesseract.image_to_string(large, config='--psm 11').strip()
        
        # Combine lines, filtering out duplicates and junk symbols
        lines = []
        seen = set()
        for t in [text_raw, text_processed, text_psm11]:
            for line in t.splitlines():
                line_cleaned = line.strip()
                # Clean up junk symbols if any
                line_cleaned = "".join(c for c in line_cleaned if c.isprintable()).strip()
                # Basic length and junk characters filter
                if len(line_cleaned) >= 2 and not all(c in r"\/|~_<>*#@+[]{}()=" for c in line_cleaned):
                    key = line_cleaned.lower()
                    if key not in seen:
                        seen.add(key)
                        lines.append(line_cleaned)
        
        return "\n".join(lines)
    except Exception:
        try:
            return pytesseract.image_to_string(image).strip()
        except Exception:
            return ""
