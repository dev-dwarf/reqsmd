"""CSV import tool for reqsmd requirements management."""

import csv
import json
import re
from pathlib import Path


def _safe_filename(value: str) -> str:
    """Convert an arbitrary string to a safe filename stem."""
    return re.sub(r'[^\w\-.]', '-', value).strip('-') or 'unnamed'


def _write_req_file(path: Path, metadata: dict, content: str) -> None:
    lines = ["{"]
    for key, value in metadata.items():
        lines.append(f'  "{key}": {json.dumps(value)},')
    lines.append("}")
    body = "\n".join(lines) + "\n---\n"
    if content:
        body += content + "\n"
    path.write_text(body, encoding="utf-8")


def import_csv(
    csv_path: str | Path,
    output_path: str | Path,
    id_col: str,
    req_col: str,
    rationale_col: str | None = None,
    doc_col: str | None = None,
    attrs: list[str] | None = None,
) -> int:
    """Import requirements from a CSV file into a reqsmd repository.

    Returns the number of requirements written.
    """
    attrs = attrs or []
    csv_path = Path(csv_path)
    output_path = Path(output_path)

    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = set(reader.fieldnames or [])

    if not rows:
        raise ValueError("CSV file is empty")

    required_cols = [id_col, req_col] + ([rationale_col] if rationale_col else []) \
                    + ([doc_col] if doc_col else []) + attrs
    missing = [c for c in required_cols if c not in fieldnames]
    if missing:
        available = ", ".join(sorted(fieldnames))
        raise ValueError(f"Columns not found in CSV: {missing}\nAvailable: {available}")

    output_path.mkdir(parents=True, exist_ok=True)

    # Write req-template.json
    template: dict = {"req": {"show-search": True, "show-compact": True, "verified": True}}
    for attr in attrs:
        template[attr] = {"show-search": True, "show-compact": True, "verified": False}
    template_lines = ["{"]
    for field, config in template.items():
        inner = ", ".join(f'"{k}": {json.dumps(v)}' for k, v in config.items())
        template_lines.append(f'  "{field}": {{ {inner} }},')
    template_lines.append("}")
    (output_path / "req-template.json").write_text(
        "\n".join(template_lines) + "\n", encoding="utf-8"
    )

    count = 0
    for row in rows:
        req_id = row[id_col].strip()
        if not req_id:
            continue

        doc_value = row[doc_col].strip() if doc_col and row.get(doc_col) else ""
        folder = output_path / _safe_filename(doc_value) if doc_value else output_path
        folder.mkdir(parents=True, exist_ok=True)

        metadata: dict = {"req": row[req_col].strip() if row.get(req_col) else ""}
        for attr in attrs:
            metadata[attr] = row[attr].strip() if row.get(attr) else None

        content = row[rationale_col].strip() if rationale_col and row.get(rationale_col) else ""

        _write_req_file(folder / f"{_safe_filename(req_id)}.md", metadata, content)
        count += 1

    return count
