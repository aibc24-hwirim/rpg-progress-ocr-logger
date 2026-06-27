from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import run_upstage_audit
from .env import load_dotenv
from .inventory_scanner import scan_inventory
from .parser import load_ocr_blocks, parse_progress_records
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
    scan_cmd.add_argument("--out", default="local_outputs/scan.json", help="Result JSON path.")

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
        result = scan_inventory(args.image, args.ocr_json, args.templates)
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote scan result to {output_path}")


if __name__ == "__main__":
    main()
