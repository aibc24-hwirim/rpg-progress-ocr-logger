from __future__ import annotations

import re
import tempfile
import math
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from .models import Box
from .upstage_client import extract_texts, ocr_document_with_upstage


def read_quantity_region(
    image: np.ndarray,
    item_box: Box,
    scale: float,
    ocr_caller: Callable[[str | Path], dict[str, Any]] = ocr_document_with_upstage,
) -> int | None:
    """아이템 셀의 수량 영역만 다시 읽고, 값이 하나일 때만 확정한다."""
    x1 = max(0, round(item_box.x + item_box.width * 0.55))
    y1 = max(0, round(item_box.y + item_box.height * 0.65))
    x2 = min(image.shape[1], round(item_box.x + item_box.width + 24 * scale))
    y2 = min(image.shape[0], round(item_box.y + item_box.height + 24 * scale))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    longest_side = max(crop.shape[:2])
    resize_factor = max(1, min(4, math.ceil(240 / longest_side)))
    if resize_factor > 1:
        crop = cv2.resize(
            crop,
            None,
            fx=resize_factor,
            fy=resize_factor,
            interpolation=cv2.INTER_CUBIC,
        )

    with tempfile.TemporaryDirectory(prefix="rpg-quantity-") as directory:
        path = Path(directory) / "quantity.png"
        if not cv2.imwrite(str(path), crop):
            return None
        response = ocr_caller(path)

    values = {
        int(match.group().replace(",", ""))
        for text in extract_texts(response)
        for match in re.finditer(r"\d[\d,]*", text)
    }
    return next(iter(values)) if len(values) == 1 else None
