from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

ITEM_COLUMNS = {
    "eternal_legendary_crest": "영원의 전설 문장",
    "legendary_crest": "전설 문장",
    "rare_crest": "희귀 문장",
    "unbound_gem_power": "미귀속 보석 마력",
    "unbound_tourmaline": "미귀속 전기석",
    "unbound_ruby": "미귀속 루비",
    "unbound_citrine": "미귀속 황수정",
    "unbound_topaz": "미귀속 토파즈",
    "unbound_sapphire": "미귀속 사파이어",
    "unbound_aquamarine": "미귀속 남옥",
}
WIDE_COLUMNS = ["기록시각", "세션 ID", "캐릭터 ID", *ITEM_COLUMNS.values(), "검토 상태"]


def load_scan_results(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]


def build_wide_rows(
    scans: Iterable[dict[str, Any]],
    captured_at: str,
    session_id: str,
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    review_notes: dict[str, list[str]] = {}

    for scan in scans:
        character_id = str(scan.get("character_id", "")).strip()
        if not character_id:
            raise ValueError("Every scan must include character_id")
        row = rows.setdefault(
            character_id,
            {
                column: ""
                for column in WIDE_COLUMNS
            }
            | {"기록시각": captured_at, "세션 ID": session_id, "캐릭터 ID": character_id},
        )
        notes = review_notes.setdefault(character_id, [])
        for item in scan.get("items", []):
            name = item.get("name")
            column = ITEM_COLUMNS.get(name)
            if column is None:
                continue
            quantity = item.get("quantity")
            if item.get("status") != "found" or quantity is None:
                notes.append(f"{column} 확인 필요")
                continue
            if row[column] not in ("", quantity):
                notes.append(f"{column} 값 충돌: {row[column]} / {quantity}")
                row[column] = ""
                continue
            row[column] = quantity

    for character_id, row in rows.items():
        row["검토 상태"] = "; ".join(dict.fromkeys(review_notes[character_id])) or "확인 완료"
    return list(rows.values())


def write_wide_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=WIDE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def rows_as_values(rows: list[dict[str, Any]], include_header: bool = True) -> list[list[Any]]:
    values = [[row.get(column, "") for column in WIDE_COLUMNS] for row in rows]
    return ([WIDE_COLUMNS] + values) if include_header else values


def append_to_google_sheets(
    rows: list[dict[str, Any]],
    spreadsheet_id: str,
    range_name: str,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        try:
            from google.auth import default
            from googleapiclient.discovery import build
        except ImportError as error:
            raise RuntimeError(
                'Install the Sheets option with: pip install -e ".[sheets]"'
            ) from error
        credentials, _ = default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=credentials)

    values_api = service.spreadsheets().values()
    existing = values_api.get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
    ).execute().get("values", [])
    if not existing:
        values_api.update(
            spreadsheetId=spreadsheet_id,
            range=_row_range(range_name, 1),
            valueInputOption="RAW",
            body={"values": [WIDE_COLUMNS]},
        ).execute()
        existing = [WIDE_COLUMNS]

    responses = []
    for row in rows:
        values = [row.get(column, "") for column in WIDE_COLUMNS]
        row_number = next(
            (
                index
                for index, current in enumerate(existing[1:], start=2)
                if len(current) > 2
                and current[1] == row["세션 ID"]
                and current[2] == row["캐릭터 ID"]
            ),
            None,
        )
        if row_number is not None:
            response = values_api.update(
                spreadsheetId=spreadsheet_id,
                range=_row_range(range_name, row_number),
                valueInputOption="RAW",
                body={"values": [values]},
            ).execute()
        else:
            response = values_api.append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            ).execute()
            existing.append(values)
        responses.append(response)
    return {"rows": len(rows), "responses": responses}


def _row_range(range_name: str, row_number: int) -> str:
    sheet = range_name.split("!", 1)[0]
    return f"{sheet}!A{row_number}:M{row_number}"
