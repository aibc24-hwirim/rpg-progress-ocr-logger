from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import run_upstage_audit
from .env import load_dotenv
from .inventory_scanner import calibrate_templates, scan_inventory
from .inventory_export import (
    append_to_google_sheets,
    build_wide_rows,
    load_scan_results,
    write_wide_csv,
)
from .parser import load_ocr_blocks, parse_progress_records
from .profile import load_profile
from .quantity_reader import read_quantity_region
from .upstage_client import ocr_document_with_upstage
from .sheets_export import write_csv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Parse OCR result JSON into a Google Sheets-compatible progress log."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parse an OCR JSON fixture.")
    parse_cmd.add_argument("input", help="Path to OCR JSON output.")
    parse_cmd.add_argument("--out", default="examples/progress_log.csv", help="CSV output path.")

    audit_cmd = subparsers.add_parser(
        "audit-upstage",
        help="Compare Upstage OCR and Document Parse text extraction for screenshots.",
    )
    audit_cmd.add_argument("images", nargs="+", help="Screenshot paths.")
    audit_cmd.add_argument("--out-dir", default="local_outputs", help="Local output directory.")

    scan_cmd = subparsers.add_parser(
        "scan",
        help="Join a screenshot, Upstage OCR JSON, and local visual templates.",
    )
    scan_cmd.add_argument("image", help="Manually captured screenshot.")
    scan_cmd.add_argument("--ocr-json", required=True, help="Upstage OCR response JSON.")
    scan_cmd.add_argument("--templates", required=True, help="Local template directory.")
    scan_cmd.add_argument("--profile", help="Scanner profile JSON path.")
    scan_cmd.add_argument(
        "--refine-missing-quantities",
        action="store_true",
        help="Run OCR again on an item's quantity region when the original OCR omitted it.",
    )
    scan_cmd.add_argument("--out", default="local_outputs/scan.json", help="Result JSON path.")

    wide_cmd = subparsers.add_parser("export-wide", help="Merge scan JSON files into one row per character.")
    wide_cmd.add_argument("inputs", nargs="+", help="Scan result JSON paths.")
    wide_cmd.add_argument("--captured-at", required=True)
    wide_cmd.add_argument("--session-id", required=True)
    wide_cmd.add_argument("--out", default="local_outputs/inventory-wide.csv")

    sheets_cmd = subparsers.add_parser("export-sheets", help="Append merged rows to Google Sheets.")
    sheets_cmd.add_argument("inputs", nargs="+", help="Scan result JSON paths.")
    sheets_cmd.add_argument("--captured-at", required=True)
    sheets_cmd.add_argument("--session-id", required=True)
    sheets_cmd.add_argument("--spreadsheet-id", required=True)
    sheets_cmd.add_argument("--range", default="진척도!A:M")

    calibrate_cmd = subparsers.add_parser(
        "calibrate",
        help="Report template scores and coordinates without expected quantities.",
    )
    calibrate_cmd.add_argument("image")
    calibrate_cmd.add_argument("--templates", required=True)
    calibrate_cmd.add_argument("--profile")
    calibrate_cmd.add_argument("--out", default="local_outputs/calibration.json")

    ocr_cmd = subparsers.add_parser(
        "ocr-images",
        help="Run Upstage OCR for images and cache each response as JSON.",
    )
    ocr_cmd.add_argument("images", nargs="+")
    ocr_cmd.add_argument("--out-dir", default="local_outputs/upstage_ocr")

    args = parser.parse_args()
    if args.command == "parse":
        captured_at, blocks = load_ocr_blocks(args.input)
        records = parse_progress_records(captured_at, blocks)
        write_csv(records, args.out)
        print(f"Wrote {len(records)} records to {args.out}")
    elif args.command == "audit-upstage":
        report_path = run_upstage_audit(args.images, args.out_dir)
        print(f"Wrote audit report to {report_path}")
    elif args.command == "scan":
        result = scan_inventory(
            args.image,
            args.ocr_json,
            args.templates,
            profile=load_profile(args.profile),
            quantity_reader=read_quantity_region if args.refine_missing_quantities else None,
        )
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote scan result to {output_path}")
    elif args.command in {"export-wide", "export-sheets"}:
        rows = build_wide_rows(
            load_scan_results(args.inputs),
            captured_at=args.captured_at,
            session_id=args.session_id,
        )
        if args.command == "export-wide":
            write_wide_csv(rows, args.out)
            print(f"Wrote {len(rows)} rows to {args.out}")
        else:
            result = append_to_google_sheets(
                rows,
                spreadsheet_id=args.spreadsheet_id,
                range_name=args.range,
            )
            print(f"Synced {result['rows']} rows")
    elif args.command == "calibrate":
        results = calibrate_templates(
            args.image,
            args.templates,
            profile=load_profile(args.profile),
        )
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {len(results)} template candidates to {output_path}")
    elif args.command == "ocr-images":
        output_dir = Path(args.out_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for image in args.images:
            output_path = output_dir / f"{Path(image).stem}.json"
            if output_path.exists():
                print(f"Reused {output_path}")
                continue
            response = ocr_document_with_upstage(image)
            output_path.write_text(
                json.dumps(response, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
