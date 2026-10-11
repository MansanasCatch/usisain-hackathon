import io

import numpy as np
from PIL import Image, ImageChops

from mcp_server.constants import ELA_JPEG_QUALITY


def compute_ela_suspicion(image: Image.Image, quality: int = ELA_JPEG_QUALITY) -> float:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    diff = ImageChops.difference(image.convert("RGB"), resaved)
    variance = np.array(diff).astype(float).std()
    return round(min(variance * 4, 100), 1)
