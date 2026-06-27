from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from .models import ProgressRecord

FIELDNAMES = [
    "captured_at",
    "character",
    "activity",
    "reward",
    "progress",
    "confidence",
    "status",
    "notes",
]


def write_csv(records: list[ProgressRecord], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
