from __future__ import annotations

import json
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class UpstageClientConfigError(RuntimeError):
    pass


DEFAULT_DOCUMENT_DIGITIZATION_URL = "https://api.upstage.ai/v1/document-digitization"


def parse_document_with_upstage(image_path: str | Path) -> dict[str, Any]:
    return call_document_digitization(image_path, model="document-parse")


def ocr_document_with_upstage(image_path: str | Path) -> dict[str, Any]:
    return call_document_digitization(image_path, model="ocr")


def call_document_digitization(image_path: str | Path, model: str) -> dict[str, Any]:
    api_key = os.getenv("UPSTAGE_API_KEY")
    endpoint = _endpoint_for_model(model)
    if not api_key:
        raise UpstageClientConfigError("Set UPSTAGE_API_KEY before calling Upstage.")

    path = Path(image_path)
    body, content_type = _multipart_form_data(
        fields={"model": model, "ocr": "force"},
        files={"document": (path.name, path.read_bytes(), _content_type(path))},
    )
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_texts(data: Any) -> list[str]:
    texts: list[str] = []

    def walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            stripped = node.strip()
            if stripped:
                texts.append(stripped)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, dict):
            for key in ("text", "markdown", "html", "content"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    walk(data)
    return _dedupe_preserve_order(texts)


def _endpoint_for_model(model: str) -> str:
    if model == "ocr":
        return os.getenv("UPSTAGE_OCR_URL") or DEFAULT_DOCUMENT_DIGITIZATION_URL
    return os.getenv("UPSTAGE_DOCUMENT_PARSE_URL") or DEFAULT_DOCUMENT_DIGITIZATION_URL


def _multipart_form_data(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----rpg-progress-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    for name, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                content,
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
