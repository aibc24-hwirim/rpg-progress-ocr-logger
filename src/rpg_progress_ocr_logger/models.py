from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class OcrBlock:
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float
    box: Box


@dataclass(frozen=True)
class InventoryItem:
    name: str
    quantity: int | None
    match_score: float
    status: str
    notes: str = ""


@dataclass(frozen=True)
class ProgressRecord:
    captured_at: str
    character: str
    activity: str
    reward: str
    progress: str
    confidence: float
    status: str
    notes: str = ""
