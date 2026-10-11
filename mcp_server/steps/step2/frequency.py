import numpy as np
from PIL import Image


def compute_frequency_signal(image: Image.Image) -> dict:
    gray = np.array(image.convert("L").resize((512, 512))).astype(float)
    fft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.abs(fft)
    h, w = magnitude.shape
    cy, cx = (h // 2, w // 2)
    radius = min(h, w) // 4
    y, x = np.ogrid[:h, :w]
    mask_high = (x - cx) ** 2 + (y - cy) ** 2 > radius**2
    high = magnitude[mask_high].mean()
    low = magnitude[~mask_high].mean()
    ratio = high / max(low, 1e-06)
    suspicion = round(max(0, min(100, (0.15 - ratio) * 500)), 1) if ratio < 0.15 else 0.0
    return {"ratio": round(ratio, 4), "suspicion": suspicion}
