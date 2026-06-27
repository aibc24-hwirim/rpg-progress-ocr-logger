from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Callable

from .upstage_client import (
    extract_texts,
    ocr_document_with_upstage,
    parse_document_with_upstage,
)

def run_upstage_audit(image_paths: list[str | Path], output_dir: str | Path) -> Path:
    output_root = Path(output_dir)
    ocr_dir = output_root / "upstage_ocr"
    dp_dir = output_root / "upstage_dp"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    dp_dir.mkdir(parents=True, exist_ok=True)

    extracted: dict[str, dict[str, list[str]]] = {}
    for image_path in [Path(path) for path in image_paths]:
        extracted[image_path.name] = {
            "ocr": _call_and_save(ocr_document_with_upstage, image_path, ocr_dir),
            "document_parse": _call_and_save(parse_document_with_upstage, image_path, dp_dir),
        }

    report_path = output_root / "extraction_audit.md"
    report_path.write_text(_build_report(extracted), encoding="utf-8")
    return report_path


def _call_and_save(
    caller: Callable[[str | Path], dict],
    image_path: Path,
    output_dir: Path,
) -> list[str]:
    output_path = output_dir / f"{image_path.stem}.json"
    text_path = output_dir / f"{image_path.stem}.texts.txt"
    if output_path.exists() and text_path.exists():
        return [
            line.strip()
            for line in text_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    try:
        data = caller(image_path)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        error_path = output_dir / f"{image_path.stem}.error.txt"
        error_path.write_text(
            f"HTTP {error.code}: {error.reason}\n{body[:2000]}\n",
            encoding="utf-8",
        )
        return [f"ERROR: HTTP {error.code} {error.reason}"]
    except Exception as error:
        error_path = output_dir / f"{image_path.stem}.error.txt"
        error_path.write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
        return [f"ERROR: {type(error).__name__}: {error}"]

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    texts = extract_texts(data)
    text_path.write_text("\n".join(texts), encoding="utf-8")
    return texts


def _build_report(extracted: dict[str, dict[str, list[str]]]) -> str:
    lines = [
        "# Upstage OCR vs Document Parse Audit",
        "",
        "This local report compares the text exposed by both extraction paths.",
        "",
        "| screenshot | OCR text fragments | Document Parse text fragments |",
        "| --- | ---: | ---: |",
    ]

    for screenshot, methods in extracted.items():
        lines.append(
            f"| {screenshot} | {len(methods['ocr'])} | "
            f"{len(methods['document_parse'])} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation Guide",
            "",
            "- OCR is evaluated as a text-reading baseline.",
            "- Document Parse is evaluated as a structure-aware baseline.",
            "- Fragment counts are diagnostic, not an accuracy score.",
            "- Inspect the generated `.texts.txt` files to compare the actual content.",
            "- Extracted numbers still need icon, color, and trade-marker context.",
        ]
    )
    return "\n".join(lines) + "\n"
