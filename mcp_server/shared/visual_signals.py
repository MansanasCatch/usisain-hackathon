"""
visual_signals.py — the core, dependency-light signal extraction that
step 2 (content analyser) is built on. No LLM, no network calls — pure
local computer vision, which is why this is the fastest piece to get
running end to end.

Every frame (a still image, or one sampled frame from a video) is scored
on three independent signals and combined into real / edited /
AI-generated evidence percentages that sum to 100.
"""

import io
from PIL import Image, ImageChops
import numpy as np


def ela_suspicion(image: Image.Image, quality: int = 90) -> float:
    """Error Level Analysis: resave at a known JPEG quality and diff against
    the original. Uneven recompression across regions is a classic sign of
    localized editing. Returns 0-100, higher = more suspicious."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    diff = ImageChops.difference(image.convert("RGB"), resaved)
    variance = np.array(diff).astype(float).std()
    return round(min(variance * 4, 100), 1)


def frequency_signal(image: Image.Image) -> dict:
    """Compares high-frequency vs low-frequency energy in the image's
    Fourier transform. Real camera sensors add natural high-frequency
    noise; many AI-generated images are unusually smooth or show
    unnaturally regular high-frequency patterns instead."""
    gray = np.array(image.convert("L").resize((512, 512))).astype(float)
    fft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.abs(fft)

    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 4
    y, x = np.ogrid[:h, :w]
    mask_high = (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2

    high = magnitude[mask_high].mean()
    low = magnitude[~mask_high].mean()
    ratio = high / max(low, 1e-6)
    suspicion = round(max(0, min(100, (0.15 - ratio) * 500)), 1) if ratio < 0.15 else 0.0
    return {"ratio": round(ratio, 4), "suspicion": suspicion}


def metadata_signal(image: Image.Image) -> dict:
    exif = image.getexif()
    has_camera_tags = any(tag in exif for tag in (271, 272, 306))  # Make, Model, DateTime
    editing_tools = ["photoshop", "gimp", "snapseed", "picsart", "canva"]
    software_tag = exif.get(305)
    flagged_software = None
    if software_tag and any(tool in str(software_tag).lower() for tool in editing_tools):
        flagged_software = str(software_tag)
    return {"has_camera_metadata": has_camera_tags, "flagged_software": flagged_software}


def normalize_pct(d: dict) -> dict:
    """Scale a dict of non-negative values to percentages that sum to
    exactly 100 (rounding drift gets absorbed into the largest value)."""
    total = sum(d.values())
    if total <= 0:
        keys = list(d.keys())
        return {k: (100.0 if i == 0 else 0.0) for i, k in enumerate(keys)}
    rounded = {k: round(v / total * 100, 1) for k, v in d.items()}
    diff = round(100 - sum(rounded.values()), 1)
    if abs(diff) >= 0.1:
        max_key = max(rounded, key=rounded.get)
        rounded[max_key] = round(rounded[max_key] + diff, 1)
    return rounded


def classify_frame(image: Image.Image) -> dict:
    """Classify a single image/frame into real / edited / AI-generated
    evidence percentages, plus which category dominates."""
    ela = ela_suspicion(image)
    freq = frequency_signal(image)
    meta = metadata_signal(image)

    edited_evidence = ela * 0.8 + (25 if meta["flagged_software"] else 0)
    ai_evidence = freq["suspicion"] * 0.8 + (20 if not meta["has_camera_metadata"] else 0)
    real_evidence = max(0.0, 100 - edited_evidence * 0.5 - ai_evidence * 0.5)

    pct = normalize_pct({"real": real_evidence, "edited": edited_evidence, "ai_generated": ai_evidence})
    dominant = max(pct, key=pct.get)

    return {
        "real_pct": pct["real"], "edited_pct": pct["edited"], "ai_generated_pct": pct["ai_generated"],
        "dominant_category": dominant,
        "signals": {"ela_suspicion": ela, "frequency": freq, "metadata": meta},
    }
