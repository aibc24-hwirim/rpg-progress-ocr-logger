from __future__ import annotations

from rpg_progress_ocr_logger.inventory_export import (
    append_to_google_sheets,
    build_wide_rows,
)


def test_build_wide_row_merges_multiple_screens() -> None:
    rows = build_wide_rows(
        [
            {
                "character_id": "SampleHero",
                "items": [
                    {"name": "rare_crest", "quantity": 180, "status": "found"},
                    {"name": "legendary_crest", "quantity": None, "status": "needs_review"},
                ],
            },
            {
                "character_id": "SampleHero",
                "items": [
                    {"name": "unbound_ruby", "quantity": 45, "status": "found"},
                ],
            },
        ],
        captured_at="2026-06-27T12:00:00+09:00",
        session_id="session-001",
    )
    assert len(rows) == 1
    assert rows[0]["희귀 문장"] == 180
    assert rows[0]["미귀속 루비"] == 45
    assert rows[0]["전설 문장"] == ""
    assert rows[0]["검토 상태"] == "전설 문장 확인 필요"


def test_conflicting_values_are_not_silently_overwritten() -> None:
    rows = build_wide_rows(
        [
            {"character_id": "A", "items": [{"name": "rare_crest", "quantity": 10, "status": "found"}]},
            {"character_id": "A", "items": [{"name": "rare_crest", "quantity": 11, "status": "found"}]},
        ],
        captured_at="now",
        session_id="same-session",
    )
    assert rows[0]["희귀 문장"] == ""
    assert "값 충돌" in rows[0]["검토 상태"]


def test_sheets_adapter_appends_new_session() -> None:
    service = _FakeSheetsService([["기록시각", "세션 ID", "캐릭터 ID"]])
    rows = build_wide_rows(
        [{"character_id": "A", "items": [{"name": "unbound_ruby", "quantity": 45, "status": "found"}]}],
        captured_at="now",
        session_id="s1",
    )
    result = append_to_google_sheets(rows, "sheet-id", "진척도!A:M", service=service)
    assert result["rows"] == 1
    assert service.calls[-1][0] == "append"
    assert service.calls[-1][1]["body"]["values"][0][2] == "A"


def test_sheets_adapter_updates_same_session_and_character() -> None:
    service = _FakeSheetsService(
        [["기록시각", "세션 ID", "캐릭터 ID"], ["old", "s1", "A"]]
    )
    rows = build_wide_rows(
        [{"character_id": "A", "items": [{"name": "rare_crest", "quantity": 11, "status": "found"}]}],
        captured_at="new",
        session_id="s1",
    )
    append_to_google_sheets(rows, "sheet-id", "진척도!A:M", service=service)
    assert service.calls[-1][0] == "update"
    assert service.calls[-1][1]["range"] == "진척도!A2:M2"


class _FakeSheetsService:
    def __init__(self, existing) -> None:
        self.existing = existing
        self.calls = []
        self.result = {}

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        self.result = {"values": self.existing}
        return self

    def append(self, **kwargs):
        self.calls.append(("append", kwargs))
        self.result = {"updates": {"updatedRange": "진척도!A2:M2"}}
        return self

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        self.result = {"updatedRange": kwargs["range"]}
        return self

    def execute(self):
        return self.result
