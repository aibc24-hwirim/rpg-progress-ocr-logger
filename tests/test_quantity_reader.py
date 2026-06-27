from __future__ import annotations

import numpy as np

from rpg_progress_ocr_logger.models import Box
from rpg_progress_ocr_logger.quantity_reader import read_quantity_region


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
