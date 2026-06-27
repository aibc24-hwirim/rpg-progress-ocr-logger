from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .models import Box, InventoryItem, OcrWord
from .profile import ScannerProfile


def scan_inventory(
    image_path: str | Path,
    ocr_json_path: str | Path,
    template_dir: str | Path,
    profile: ScannerProfile | None = None,
    quantity_reader: Callable[[np.ndarray, Box, float], int | None] | None = None,
) -> dict:
    """파일명에 의존하지 않고 시각 탐지와 OCR 단어를 결합한다."""
    image = _read_image(Path(image_path))
    words = load_upstage_words(ocr_json_path)
    numbers = [word for word in words if _integer_value(word.text) is not None]
    profile = profile or ScannerProfile()
    scale = image.shape[1] / profile.base_screen_width
    templates = Path(template_dir)

    results = _scan_single_items(
        image, templates, numbers, scale, profile, quantity_reader
    )
    results.extend(_scan_unbound_gems(image, templates, numbers, scale, profile))
    return {
        "source": Path(image_path).name,
        "character_id": extract_character_id(words, image.shape[1]),
        "items": [
            {
                "name": item.name,
                "quantity": item.quantity,
                "match_score": item.match_score,
                "status": item.status,
                "notes": item.notes,
            }
            for item in results
        ],
    }


def calibrate_templates(
    image_path: str | Path,
    template_dir: str | Path,
    profile: ScannerProfile | None = None,
) -> list[dict]:
    image = _read_image(Path(image_path))
    profile = profile or ScannerProfile()
    scale = image.shape[1] / profile.base_screen_width
    root = Path(template_dir)
    templates = (
        profile.item_templates
        | {f"gem_{name}": filename for name, filename in profile.gem_templates.items()}
        | {"trade_marker": "trade_marker.png"}
    )
    results = []
    for name, filename in templates.items():
        path = root / filename
        if not path.exists():
            continue
        box, score = _best_match(image, _scaled_template(path, scale))
        results.append(
            {
                "name": name,
                "template": filename,
                "score": round(score, 4),
                "box": {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                },
            }
        )
    return sorted(results, key=lambda result: result["score"], reverse=True)


def load_upstage_words(path: str | Path) -> list[OcrWord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    if not pages:
        return []

    words: list[OcrWord] = []
    for word in pages[0].get("words", []):
        vertices = word.get("boundingBox", {}).get("vertices", [])
        if len(vertices) < 2:
            continue
        xs = [int(vertex["x"]) for vertex in vertices]
        ys = [int(vertex["y"]) for vertex in vertices]
        words.append(
            OcrWord(
                text=str(word.get("text", "")).strip(),
                confidence=float(word.get("confidence", 0)),
                box=Box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)),
            )
        )
    return words


def extract_character_id(words: list[OcrWord], image_width: int) -> str:
    # 해상도가 달라도 캐릭터 ID는 좌측 상단의 동일한 의미 영역에 머문다.
    candidates = [
        word
        for word in words
        if word.box.x < image_width * 0.27
        and word.box.y < image_width * 0.095
        and word.text
        and not any(character.isdigit() for character in word.text)
    ]
    if not candidates:
        return ""
    first = min(candidates, key=lambda word: (word.box.y, word.box.x))
    same_line = [
        word
        for word in candidates
        if abs(word.box.center_y - first.box.center_y) <= max(4, first.box.height * 0.35)
    ]
    return "".join(word.text for word in sorted(same_line, key=lambda word: word.box.x))


def _scan_single_items(
    image: np.ndarray,
    template_dir: Path,
    numbers: list[OcrWord],
    scale: float,
    profile: ScannerProfile,
    quantity_reader: Callable[[np.ndarray, Box, float], int | None] | None,
) -> list[InventoryItem]:
    results: list[InventoryItem] = []
    for name, filename in profile.item_templates.items():
        template_path = template_dir / filename
        if not template_path.exists():
            continue
        box, score = _best_match(image, _scaled_template(template_path, scale))
        if score < profile.item_presence_threshold:
            continue
        quantity = _nearest_quantity(box, numbers, scale)
        refined_quantity = (
            quantity_reader(image, box, scale)
            if quantity is None and quantity_reader is not None
            else None
        )
        # 아이템 외형이 일치해도 주변 OCR 숫자가 없으면 수량을 확정하지 않는다.
        value = _integer_value(quantity.text) if quantity else refined_quantity
        status = "found" if value is not None else "needs_review"
        results.append(
            InventoryItem(
                name=name,
                quantity=value,
                match_score=round(score, 4),
                status=status,
                notes=(
                    "quantity read from item region"
                    if refined_quantity is not None
                    else ("" if status == "found" else "item or nearby OCR quantity is ambiguous")
                ),
            )
        )
    return results


def _scan_unbound_gems(
    image: np.ndarray,
    template_dir: Path,
    numbers: list[OcrWord],
    scale: float,
    profile: ScannerProfile,
) -> list[InventoryItem]:
    marker_path = template_dir / "trade_marker.png"
    if not marker_path.exists():
        return []

    marker = _scaled_template(marker_path, scale)
    marker_boxes = [
        box
        for box, _ in _template_matches(image, marker, threshold=profile.trade_marker_threshold)
        if image.shape[1] * profile.marker_roi[0] <= box.x <= image.shape[1] * profile.marker_roi[2]
        and image.shape[0] * profile.marker_roi[1] <= box.y <= image.shape[0] * profile.marker_roi[3]
    ]

    results: list[InventoryItem] = []
    seen: set[str] = set()
    for marker_box in marker_boxes:
        cell = _cell_from_marker(marker_box, scale)
        name, score = _classify_gem(image, cell, template_dir, scale, profile)
        if not name or name in seen:
            continue
        seen.add(name)
        quantity = _quantity_in_cell(cell, numbers, scale)
        status = "found" if quantity is not None and score >= 0.35 else "needs_review"
        results.append(
            InventoryItem(
                name=f"unbound_{name}",
                quantity=_integer_value(quantity.text) if quantity else None,
                match_score=round(score, 4),
                status=status,
                notes="" if status == "found" else "trade marker found but item or quantity is ambiguous",
            )
        )
    return sorted(results, key=lambda item: item.name)


def _classify_gem(
    image: np.ndarray,
    cell: Box,
    template_dir: Path,
    scale: float,
    profile: ScannerProfile,
) -> tuple[str | None, float]:
    crop = image[
        max(0, cell.y) : min(image.shape[0], cell.y + cell.height),
        max(0, cell.x) : min(image.shape[1], cell.x + cell.width),
    ]
    best_name: str | None = None
    best_score = -1.0
    for name, filename in profile.gem_templates.items():
        path = template_dir / filename
        if not path.exists():
            continue
        _, score = _best_match(crop, _scaled_template(path, scale))
        if score > best_score:
            best_name, best_score = name, score
    if best_score < profile.gem_classification_threshold:
        return None, best_score
    return best_name, best_score


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _scaled_template(path: Path, scale: float) -> np.ndarray:
    template = _read_image(path)
    size = (
        max(1, round(template.shape[1] * scale)),
        max(1, round(template.shape[0] * scale)),
    )
    return cv2.resize(template, size, interpolation=cv2.INTER_CUBIC)


def _best_match(image: np.ndarray, template: np.ndarray) -> tuple[Box, float]:
    if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
        return Box(0, 0, 0, 0), -1.0
    scores = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(scores)
    return Box(location[0], location[1], template.shape[1], template.shape[0]), float(score)


def _template_matches(
    image: np.ndarray,
    template: np.ndarray,
    threshold: float,
) -> list[tuple[Box, float]]:
    scores = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(scores >= threshold)
    candidates = [
        (Box(int(x), int(y), template.shape[1], template.shape[0]), float(scores[y, x]))
        for x, y in zip(xs, ys)
    ]
    kept: list[tuple[Box, float]] = []
    for box, score in sorted(candidates, key=lambda item: item[1], reverse=True):
        if all(_iou(box, other) < 0.25 for other, _ in kept):
            kept.append((box, score))
    return kept[:50]


def _nearest_quantity(box: Box, numbers: list[OcrWord], scale: float) -> OcrWord | None:
    candidates: list[tuple[float, OcrWord]] = []
    for number in numbers:
        dx = abs(number.box.center_x - box.center_x)
        dy = number.box.center_y - box.center_y
        if number.box.center_x >= box.center_x and -6 * scale <= dy <= 62 * scale and dx <= 56 * scale:
            candidates.append((dx + abs(dy) * 0.6, number))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _cell_from_marker(marker: Box, scale: float) -> Box:
    return Box(
        round(marker.x - 10 * scale),
        round(marker.y - 8 * scale),
        round(62 * scale),
        round(72 * scale),
    )


def _quantity_in_cell(cell: Box, numbers: list[OcrWord], scale: float) -> OcrWord | None:
    candidates = [
        number
        for number in numbers
        if cell.x - 4 * scale <= number.box.center_x <= cell.x + cell.width + 14 * scale
        and cell.y <= number.box.center_y <= cell.y + cell.height + 14 * scale
    ]
    return (
        max(candidates, key=lambda number: (number.box.center_y, number.box.center_x))
        if candidates
        else None
    )


def _integer_value(text: str) -> int | None:
    compact = text.replace(",", "")
    return int(compact) if re.fullmatch(r"\d+", compact) else None


def _iou(left: Box, right: Box) -> float:
    x1, y1 = max(left.x, right.x), max(left.y, right.y)
    x2 = min(left.x + left.width, right.x + right.width)
    y2 = min(left.y + left.height, right.y + right.height)
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = left.width * left.height + right.width * right.height - intersection
    return intersection / union if union else 0.0
