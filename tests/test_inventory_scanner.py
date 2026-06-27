from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from rpg_progress_ocr_logger.inventory_scanner import (
    calibrate_templates,
    extract_character_id,
    load_upstage_words,
    scan_inventory,
)
from rpg_progress_ocr_logger.models import Box, OcrWord


def test_extract_character_id_uses_top_left_region() -> None:
    words = [
        OcrWord("SampleHero", 0.98, Box(34, 20, 80, 18)),
        OcrWord("60", 0.99, Box(40, 52, 20, 14)),
        OcrWord("Inventory", 0.96, Box(700, 30, 70, 18)),
    ]

    assert extract_character_id(words, image_width=960) == "SampleHero"


def test_extract_character_id_joins_words_on_same_line() -> None:
    words = [
        OcrWord("Sample", 0.98, Box(34, 18, 59, 18)),
        OcrWord("Hero", 0.98, Box(95, 18, 56, 18)),
        OcrWord("레벨:", 0.99, Box(33, 49, 33, 16)),
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


@pytest.mark.parametrize("scale", [1.0, 4 / 3])
def test_scan_inventory_matches_item_and_quantity_at_multiple_resolutions(
    tmp_path: Path,
    scale: float,
) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = _pattern(24, seed=10)
    cv2.imwrite(str(template_dir / "crest_rare.png"), template)

    width, height = round(960 * scale), round(540 * scale)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    scaled_template = cv2.resize(
        template,
        (round(24 * scale), round(24 * scale)),
        interpolation=cv2.INTER_CUBIC,
    )
    x, y = round(600 * scale), round(100 * scale)
    _place(image, scaled_template, x, y)

    image_path = tmp_path / f"screen-{width}.png"
    ocr_path = tmp_path / f"ocr-{width}.json"
    cv2.imwrite(str(image_path), image)
    _write_ocr(
        ocr_path,
        [
            ("SampleHero", 34 * scale, 20 * scale, 110 * scale, 38 * scale),
            ("180", 608 * scale, 124 * scale, 640 * scale, 142 * scale),
        ],
    )

    result = scan_inventory(image_path, ocr_path, template_dir)

    assert result["character_id"] == "SampleHero"
    assert result["items"] == [
        {
            "name": "rare_crest",
            "quantity": 180,
            "match_score": 1.0,
            "status": "found",
            "notes": "",
        }
    ]


def test_scan_inventory_marks_missing_quantity_for_review(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = _pattern(24, seed=20)
    cv2.imwrite(str(template_dir / "crest_legendary.png"), template)

    image = np.zeros((540, 960, 3), dtype=np.uint8)
    _place(image, template, 600, 100)
    image_path = tmp_path / "screen.png"
    ocr_path = tmp_path / "ocr.json"
    cv2.imwrite(str(image_path), image)
    _write_ocr(ocr_path, [("SampleHero", 34, 20, 110, 38)])

    item = scan_inventory(image_path, ocr_path, template_dir)["items"][0]

    assert item["name"] == "legendary_crest"
    assert item["quantity"] is None
    assert item["status"] == "needs_review"


def test_scan_inventory_uses_quantity_reader_for_missing_single_digit(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = _pattern(24, seed=21)
    cv2.imwrite(str(template_dir / "crest_eternal_legendary.png"), template)
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    _place(image, template, 600, 100)
    image_path, ocr_path = tmp_path / "screen.png", tmp_path / "ocr.json"
    cv2.imwrite(str(image_path), image)
    _write_ocr(ocr_path, [("SampleHero", 34, 20, 110, 38)])

    result = scan_inventory(
        image_path,
        ocr_path,
        template_dir,
        quantity_reader=lambda _image, _box, _scale: 1,
    )

    assert result["items"][0]["quantity"] == 1
    assert result["items"][0]["status"] == "found"
    assert result["items"][0]["notes"] == "quantity read from item region"


def test_trade_marker_selects_only_unbound_gem(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    marker = _pattern(12, seed=30)
    ruby = _pattern(20, seed=40)
    cv2.imwrite(str(template_dir / "trade_marker.png"), marker)
    cv2.imwrite(str(template_dir / "gem_ruby.png"), ruby)

    image = np.zeros((540, 960, 3), dtype=np.uint8)
    _place(image, marker, 650, 200)
    _place(image, ruby, 660, 220)
    image_path = tmp_path / "gems.png"
    ocr_path = tmp_path / "gems-ocr.json"
    cv2.imwrite(str(image_path), image)
    _write_ocr(
        ocr_path,
        [
            ("SampleHero", 34, 20, 110, 38),
            ("45", 660, 250, 682, 266),
        ],
    )

    result = scan_inventory(image_path, ocr_path, template_dir)

    assert result["items"][0]["name"] == "unbound_ruby"
    assert result["items"][0]["quantity"] == 45
    assert result["items"][0]["status"] == "found"


def test_quantity_in_cell_prefers_rightmost_number_on_same_row() -> None:
    from rpg_progress_ocr_logger.inventory_scanner import _quantity_in_cell

    numbers = [
        OcrWord("2", 0.99, Box(809, 160, 8, 10)),
        OcrWord("81", 0.99, Box(861, 159, 14, 12)),
    ]
    quantity = _quantity_in_cell(Box(816, 112, 62, 72), numbers, 1.0)
    assert quantity is not None
    assert quantity.text == "81"


def test_missing_templates_produce_no_false_items(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    image_path = tmp_path / "empty.png"
    ocr_path = tmp_path / "empty-ocr.json"
    cv2.imwrite(str(image_path), np.zeros((540, 960, 3), dtype=np.uint8))
    _write_ocr(ocr_path, [("SampleHero", 34, 20, 110, 38)])

    result = scan_inventory(image_path, ocr_path, template_dir)

    assert result["items"] == []


def test_calibration_reports_score_and_coordinates_without_answers(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = _pattern(24, seed=50)
    cv2.imwrite(str(template_dir / "crest_rare.png"), template)
    image = np.zeros((540, 960, 3), dtype=np.uint8)
    _place(image, template, 620, 140)
    image_path = tmp_path / "screen.png"
    cv2.imwrite(str(image_path), image)

    results = calibrate_templates(image_path, template_dir)

    assert results[0]["name"] == "rare_crest"
    assert results[0]["score"] == 1.0
    assert results[0]["box"]["x"] == 620
    assert "quantity" not in results[0]


def _pattern(size: int, seed: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    return generator.integers(0, 256, (size, size, 3), dtype=np.uint8)


def _place(image: np.ndarray, template: np.ndarray, x: int, y: int) -> None:
    height, width = template.shape[:2]
    image[y : y + height, x : x + width] = template


def _write_ocr(path: Path, words: list[tuple[str, float, float, float, float]]) -> None:
    payload = {
        "pages": [
            {
                "words": [
                    {
                        "text": text,
                        "confidence": 0.99,
                        "boundingBox": {
                            "vertices": [
                                {"x": round(x1), "y": round(y1)},
                                {"x": round(x2), "y": round(y1)},
                                {"x": round(x2), "y": round(y2)},
                                {"x": round(x1), "y": round(y2)},
                            ]
                        },
                    }
                    for text, x1, y1, x2, y2 in words
                ]
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
