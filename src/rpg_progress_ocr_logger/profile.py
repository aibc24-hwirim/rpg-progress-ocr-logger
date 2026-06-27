from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScannerProfile:
    base_screen_width: int = 960
    item_presence_threshold: float = 0.90
    gem_classification_threshold: float = 0.80
    trade_marker_threshold: float = 0.90
    marker_roi: tuple[float, float, float, float] = (0.55, 0.18, 0.96, 0.75)
    item_templates: dict[str, str] = field(
        default_factory=lambda: {
            "eternal_legendary_crest": "crest_eternal_legendary.png",
            "legendary_crest": "crest_legendary.png",
            "rare_crest": "crest_rare.png",
            "unbound_gem_power": "gem_power_unbound.png",
        }
    )
    gem_templates: dict[str, str] = field(
        default_factory=lambda: {
            "tourmaline": "gem_tourmaline.png",
            "ruby": "gem_ruby.png",
            "citrine": "gem_citrine.png",
            "topaz": "gem_topaz.png",
            "sapphire": "gem_sapphire.png",
            "aquamarine": "gem_aquamarine.png",
        }
    )


def load_profile(path: str | Path | None = None) -> ScannerProfile:
    if path is None:
        return ScannerProfile()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    allowed = set(ScannerProfile.__dataclass_fields__)
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"Unknown profile fields: {', '.join(unknown)}")
    if "marker_roi" in data:
        data["marker_roi"] = tuple(data["marker_roi"])
    profile = ScannerProfile(**data)
    _validate(profile)
    return profile


def _validate(profile: ScannerProfile) -> None:
    if profile.base_screen_width <= 0:
        raise ValueError("base_screen_width must be positive")
    for name, value in (
        ("item_presence_threshold", profile.item_presence_threshold),
        ("gem_classification_threshold", profile.gem_classification_threshold),
        ("trade_marker_threshold", profile.trade_marker_threshold),
    ):
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if len(profile.marker_roi) != 4 or any(not 0 <= value <= 1 for value in profile.marker_roi):
        raise ValueError("marker_roi must contain four values between 0 and 1")
