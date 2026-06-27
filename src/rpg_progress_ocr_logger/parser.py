from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import OcrBlock, ProgressRecord

LABEL_ALIASES = {
    "character": {"character", "char", "name", "캐릭터", "이름"},
    "activity": {"activity", "task", "content", "콘텐츠", "활동"},
    "reward": {"reward", "item", "loot", "보상", "획득"},
    "progress": {"progress", "count", "진척도", "진행도"},
}


def load_ocr_blocks(path: str | Path) -> tuple[str, list[OcrBlock]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    captured_at = payload.get("captured_at", "")
    blocks = [
        OcrBlock(
            text=str(block.get("text", "")).strip(),
            confidence=_to_float(block.get("confidence")),
        )
        for block in payload.get("text_blocks", [])
        if str(block.get("text", "")).strip()
    ]
    return captured_at, blocks


def parse_progress_records(captured_at: str, blocks: list[OcrBlock]) -> list[ProgressRecord]:
    records: list[ProgressRecord] = []
    current: dict[str, str] = {}
    confidences: list[float] = []

    for block in blocks:
        key, value = _split_label_value(block.text)
        if key == "character" and current:
            records.append(_build_record(captured_at, current, confidences))
            current, confidences = {}, []

        if key:
            current[key] = value
            if block.confidence is not None:
                confidences.append(block.confidence)

    if current:
        records.append(_build_record(captured_at, current, confidences))
    return records


def _split_label_value(text: str) -> tuple[str | None, str]:
    match = re.match(r"^([^:：]+)\s*[:：]\s*(.+)$", text.strip())
    if not match:
        return None, text.strip()

    raw_label, value = match.group(1).strip().lower(), match.group(2).strip()
    for canonical, aliases in LABEL_ALIASES.items():
        if raw_label in aliases:
            return canonical, value
    return None, value


def _build_record(
    captured_at: str,
    fields: dict[str, str],
    confidences: list[float],
) -> ProgressRecord:
    missing = [
        field
        for field in ("character", "activity", "reward", "progress")
        if not fields.get(field)
    ]
    confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    status = "needs_review" if missing or confidence < 0.7 else "ok"
    return ProgressRecord(
        captured_at=captured_at,
        character=fields.get("character", ""),
        activity=fields.get("activity", ""),
        reward=fields.get("reward", ""),
        progress=fields.get("progress", ""),
        confidence=confidence,
        status=status,
        notes=", ".join(f"missing {field}" for field in missing),
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
