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
        
        # Only resize if the image resolution is small/low-res to avoid massive scaling
        # which slows down pytesseract dramatically and could cause timeouts on large screen captures.
        if gray.width < 1200 and gray.height < 1200:
            large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
            text = pytesseract.image_to_string(large).strip()
        else:
            text = pytesseract.image_to_string(gray).strip()
        
        # If the processed OCR is empty or very short, fallback to raw image
        if len(text) < 5:
            text = pytesseract.image_to_string(image).strip()
            
        # Basic cleaning of lines
        lines = []
        for line in text.splitlines():
            line_cleaned = line.strip()
            line_cleaned = "".join(c for c in line_cleaned if c.isprintable()).strip()
            if len(line_cleaned) >= 2 and not all(c in r"\/|~_<>*#@+[]{}()=" for c in line_cleaned):
                lines.append(line_cleaned)
                
        return "\n".join(lines)
    except Exception:
        try:
            return pytesseract.image_to_string(image).strip()
        except Exception:
            return ""
