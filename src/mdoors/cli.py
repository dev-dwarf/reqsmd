"""CLI entry point for MDOORS requirements management."""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from .core import load_project, parse_lenient_json


def find_project_root(start_path: Path) -> Path:
    """Find project root by looking for req-template.json or using start_path."""
    current = start_path.resolve()
    while current != current.parent:
        if (current / "req-template.json").exists():
            return current
        current = current.parent
    return start_path.resolve()


def cmd_req_add(args):
    """Add a new requirement."""
    req_id = args.req_id
    doc_path = Path(args.doc) if args.doc else Path(".")

    # Find project root for template
    project_root = find_project_root(doc_path)

    # Load template
    template_path = project_root / "req-template.json"
    if template_path.exists():
        try:
            template = parse_lenient_json(template_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            template = {}
    else:
        template = {}

    # Extract default values from template (supports new format with 'default' key)
    defaults = {}
    for key, value in template.items():
        if isinstance(value, dict) and "default" in value:
            defaults[key] = value["default"]
        else:
            # Legacy format: value is the default directly
            defaults[key] = value

    # Create requirement file
    req_file = doc_path / f"{req_id}.md"

    if req_file.exists():
        print(f"Error: Requirement {req_id} already exists at {req_file}", file=sys.stderr)
        return 1

    # Ensure directory exists
    doc_path.mkdir(parents=True, exist_ok=True)

    # Format JSON with trailing comma style to match existing files
    json_lines = ["{"]
    items = list(defaults.items())
    for i, (key, value) in enumerate(items):
        json_value = json.dumps(value)
        json_lines.append(f'  "{key}": {json_value},')
    json_lines.append("}")

    content = "\n".join(json_lines) + "\n---\n"

    req_file.write_text(content, encoding="utf-8")
    print(f"Created {req_file}")
    return 0


def cmd_export_csv(args):
    """Export requirements to CSV."""
    doc_path = Path(args.doc)
    output = args.output

    project = load_project(doc_path)
    reqs = project.all_requirements()

    if not reqs:
        print("No requirements found.", file=sys.stderr)
        return 1

    # Collect all unique metadata keys
    all_keys = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())

    # Define column order
    fixed_columns = ["id", "content", "link_to", "link_from"]
    meta_columns = sorted(all_keys)
    columns = fixed_columns + meta_columns

    # Write CSV
    if output:
        outfile = open(output, "w", newline="", encoding="utf-8")
    else:
        outfile = sys.stdout

    try:
        writer = csv.DictWriter(outfile, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for req in reqs:
            row = {
                "id": req.id,
                "content": req.content,
                "link_to": ";".join(req.link_to),
                "link_from": ";".join(req.link_from),
            }
            for key, value in req.metadata.items():
                if isinstance(value, list):
                    row[key] = ";".join(str(v) for v in value)
                else:
                    row[key] = value
            writer.writerow(row)
    finally:
        if output:
            outfile.close()

    if output:
        print(f"Exported {len(reqs)} requirements to {output}")
    return 0


def cmd_export_sqlite(args):
    """Export requirements to SQLite database."""
    doc_path = Path(args.doc)
    output = args.output or "requirements.db"

    project = load_project(doc_path)
    reqs = project.all_requirements()

    if not reqs:
        print("No requirements found.", file=sys.stderr)
        return 1

    # Collect all unique metadata keys
    all_keys = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())
    meta_columns = sorted(all_keys)

    # Create database
    if Path(output).exists():
        Path(output).unlink()

    conn = sqlite3.connect(output)
    cursor = conn.cursor()

    # Create table with dynamic columns for metadata
    # Use safe column names (replace - with _)
    safe_columns = {k: k.replace("-", "_") for k in meta_columns}

    columns_sql = ", ".join(
        f'"{safe_columns[k]}" TEXT' for k in meta_columns
    )

    create_sql = f"""
    CREATE TABLE requirements (
        id TEXT PRIMARY KEY,
        content TEXT,
        link_to TEXT,
        link_from TEXT,
        file_path TEXT
        {', ' + columns_sql if columns_sql else ''}
    )
    """
    cursor.execute(create_sql)

    # Insert requirements
    for req in reqs:
        values = {
            "id": req.id,
            "content": req.content,
            "link_to": ";".join(req.link_to),
            "link_from": ";".join(req.link_from),
            "file_path": str(req.file_path) if req.file_path else "",
        }
        for key in meta_columns:
            value = req.metadata.get(key)
            if isinstance(value, list):
                values[safe_columns[key]] = ";".join(str(v) for v in value)
            elif value is not None:
                values[safe_columns[key]] = str(value)
            else:
                values[safe_columns[key]] = None

        columns = ", ".join(f'"{k}"' for k in values.keys())
        placeholders = ", ".join("?" for _ in values)
        insert_sql = f"INSERT INTO requirements ({columns}) VALUES ({placeholders})"
        cursor.execute(insert_sql, list(values.values()))

    conn.commit()
    conn.close()

    print(f"Exported {len(reqs)} requirements to {output}")
    return 0


def cmd_export_web(args):
    """Export requirements to a static website."""
    doc_path = Path(args.doc) if args.doc else Path(".")
    output = Path(args.output) if args.output else Path("_site")

    from .web import generate_website

    project = load_project(doc_path)
    generate_website(project, output)

    print(f"Generated website in {output}/")
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mdoors",
        description="MDOORS - Requirements management using markdown files"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # req command
    req_parser = subparsers.add_parser("req", help="Requirement operations")
    req_subparsers = req_parser.add_subparsers(dest="req_command")

    # req add
    req_add_parser = req_subparsers.add_parser("add", help="Add a new requirement")
    req_add_parser.add_argument("req_id", help="Requirement ID (e.g., PRES-02)")
    req_add_parser.add_argument("--doc", "-d", help="Document folder path", default=".")

    # export command
    export_parser = subparsers.add_parser("export", help="Export operations")
    export_subparsers = export_parser.add_subparsers(dest="export_command")

    # export csv
    csv_parser = export_subparsers.add_parser("csv", help="Export to CSV")
    csv_parser.add_argument("doc", help="Document folder path")
    csv_parser.add_argument("--output", "-o", help="Output file path")

    # export sqlite
    sqlite_parser = export_subparsers.add_parser("sqlite", help="Export to SQLite")
    sqlite_parser.add_argument("doc", help="Document folder path")
    sqlite_parser.add_argument("--output", "-o", help="Output file path", default="requirements.db")

    # export web
    web_parser = export_subparsers.add_parser("web", help="Export to static website")
    web_parser.add_argument("--doc", "-d", help="Document folder path", default=".")
    web_parser.add_argument("--output", "-o", help="Output directory", default="_site")

    args = parser.parse_args()

    if args.command == "req":
        if args.req_command == "add":
            return cmd_req_add(args)
        else:
            req_parser.print_help()
            return 1
    elif args.command == "export":
        if args.export_command == "csv":
            return cmd_export_csv(args)
        elif args.export_command == "sqlite":
            return cmd_export_sqlite(args)
        elif args.export_command == "web":
            return cmd_export_web(args)
        else:
            export_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
