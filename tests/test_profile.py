from __future__ import annotations

import json

import pytest

from rpg_progress_ocr_logger.profile import ScannerProfile, load_profile


def test_default_profile_keeps_current_scanner_settings() -> None:
    profile = load_profile()
    assert profile.base_screen_width == 960
    assert profile.item_presence_threshold == 0.90
    assert profile.item_templates["rare_crest"] == "crest_rare.png"


def test_profile_overrides_selected_values(tmp_path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps({"base_screen_width": 1280, "item_presence_threshold": 0.93}),
        encoding="utf-8",
    )
    profile = load_profile(path)
    assert profile.base_screen_width == 1280
    assert profile.item_presence_threshold == 0.93


def test_profile_rejects_unknown_fields(tmp_path) -> None:
    path = tmp_path / "profile.json"
    path.write_text('{"expected_quantity": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown profile fields"):
        load_profile(path)
