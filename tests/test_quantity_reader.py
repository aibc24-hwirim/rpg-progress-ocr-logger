from __future__ import annotations

import numpy as np
import cv2

from rpg_progress_ocr_logger.models import Box
from rpg_progress_ocr_logger.quantity_reader import (
    extract_digit_glyph,
    read_quantity_glyph,
    read_quantity_region,
)


def test_quantity_region_accepts_single_digit() -> None:
    response = {"pages": [{"words": [{"text": "1"}]}]}
    value = read_quantity_region(
        np.zeros((100, 100, 3), dtype=np.uint8),
        Box(20, 20, 30, 30),
        1.0,
        ocr_caller=lambda _: response,
    )
    assert value == 1


def test_quantity_region_rejects_ambiguous_numbers() -> None:
    response = {"pages": [{"words": [{"text": "1"}, {"text": "7"}]}]}
    value = read_quantity_region(
        np.zeros((100, 100, 3), dtype=np.uint8),
        Box(20, 20, 30, 30),
        1.0,
        ocr_caller=lambda _: response,
    )
    assert value is None


def test_digit_glyph_template_resolves_missing_quantity(tmp_path) -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.putText(image, "4", (48, 67), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
    box = Box(20, 20, 30, 30)
    from rpg_progress_ocr_logger.quantity_reader import quantity_crop

    glyph = extract_digit_glyph(quantity_crop(image, box, 1.0))
    assert glyph is not None
    template_dir = tmp_path / "digits"
    template_dir.mkdir()
    cv2.imwrite(str(template_dir / "4.png"), glyph)

    assert read_quantity_glyph(image, box, 1.0, template_dir) == 4
