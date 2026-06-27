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


def quantity_crop(image: np.ndarray, item_box: Box, scale: float) -> np.ndarray:
    x1 = max(0, round(item_box.x + item_box.width * 0.55))
    y1 = max(0, round(item_box.y + item_box.height * 0.65))
    x2 = min(image.shape[1], round(item_box.x + item_box.width + 24 * scale))
    y2 = min(image.shape[0], round(item_box.y + item_box.height + 24 * scale))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return crop
    resize_factor = max(1, min(4, math.ceil(240 / max(crop.shape[:2]))))
    return cv2.resize(
        crop,
        None,
        fx=resize_factor,
        fy=resize_factor,
        interpolation=cv2.INTER_CUBIC,
    ) if resize_factor > 1 else crop


def read_quantity_region(
    image: np.ndarray,
    item_box: Box,
    scale: float,
    ocr_caller: Callable[[str | Path], dict[str, Any]] = ocr_document_with_upstage,
) -> int | None:
    """아이템 셀의 수량 영역만 다시 읽고, 값이 하나일 때만 확정한다."""
    crop = quantity_crop(image, item_box, scale)
    if crop.size == 0:
        return None

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


def read_quantity_glyph(
    image: np.ndarray,
    item_box: Box,
    scale: float,
    template_dir: str | Path,
    threshold: float = 0.72,
    margin: float = 0.08,
) -> int | None:
    glyph = extract_digit_glyph(quantity_crop(image, item_box, scale))
    if glyph is None:
        return None
    scores = []
    for path in Path(template_dir).glob("*.png"):
        if not path.stem.isdigit():
            continue
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue
        score = float(cv2.matchTemplate(glyph, template, cv2.TM_CCOEFF_NORMED)[0, 0])
        scores.append((score, int(path.stem)))
    scores.sort(reverse=True)
    if not scores or scores[0][0] < threshold:
        return None
    if len(scores) > 1 and scores[0][0] - scores[1][0] < margin:
        return None
    return scores[0][1]


def extract_digit_glyph(crop: np.ndarray) -> np.ndarray | None:
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    _, mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    candidates = []
    height, width = mask.shape
    for index in range(1, count):
        x, y, w, h, area = (int(value) for value in stats[index])
        touches_edge = x == 0 or y == 0 or x + w >= width or y + h >= height
        if not touches_edge and area >= 20 and h >= 10 and w / h <= 1.2:
            candidates.append((area, index, x, y, w, h))
    if not candidates:
        return None
    _, index, x, y, w, h = max(candidates)
    glyph = np.where(labels[y : y + h, x : x + w] == index, 255, 0).astype(np.uint8)
    canvas = np.zeros((48, 32), dtype=np.uint8)
    factor = min(28 / glyph.shape[1], 44 / glyph.shape[0])
    resized = cv2.resize(
        glyph,
        (max(1, round(glyph.shape[1] * factor)), max(1, round(glyph.shape[0] * factor))),
        interpolation=cv2.INTER_NEAREST,
    )
    y0 = (48 - resized.shape[0]) // 2
    x0 = (32 - resized.shape[1]) // 2
    canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
    return canvas
