from __future__ import annotations

import json

from rpg_progress_ocr_logger.inventory_scanner import (
    extract_character_id,
    load_upstage_words,
)
from rpg_progress_ocr_logger.models import Box, OcrWord


def test_extract_character_id_uses_top_left_region() -> None:
    words = [
        OcrWord("SampleHero", 0.98, Box(34, 20, 80, 18)),
        OcrWord("60", 0.99, Box(40, 52, 20, 14)),
        OcrWord("Inventory", 0.96, Box(700, 30, 70, 18)),
    ]

    assert extract_character_id(words, image_width=960) == "SampleHero"


def test_load_upstage_words_preserves_text_and_coordinates(tmp_path) -> None:
    response = {
        "pages": [
            {
                "words": [
                    {
                        "text": "58",
                        "confidence": 0.97,
                        "boundingBox": {
                            "vertices": [
                                {"x": 760, "y": 180},
                                {"x": 780, "y": 180},
                                {"x": 780, "y": 195},
                                {"x": 760, "y": 195},
                            ]
                        },
                    }
                ]
            }
        ]
    }
    path = tmp_path / "ocr.json"
    path.write_text(json.dumps(response), encoding="utf-8")

    words = load_upstage_words(path)

    assert words[0].text == "58"
    assert words[0].box == Box(760, 180, 20, 15)
