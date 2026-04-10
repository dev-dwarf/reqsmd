"""CLI entry point for reqsmd requirements management."""

import argparse
import csv
import json
import sys
from pathlib import Path

from .core import export_sqlite, load_project, parse_lenient_json


def cmd_req_add(args):
    """Add a new requirement."""
    req_id = args.req_id
    doc_path = Path(args.doc) if args.doc else Path(".")

    # Find project root by walking up for req-template.json
    current = doc_path.resolve()
    project_root = current
    while current != current.parent:
        if (current / "req-template.json").exists():
            project_root = current
            break
        current = current.parent

    template_path = project_root / "req-template.json"
    if template_path.exists():
        try:
            template = parse_lenient_json(template_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            template = {}
    else:
        template = {}

    defaults = {}
    for key, value in template.items():
        if isinstance(value, dict) and "default" in value:
            defaults[key] = value["default"]
        else:
            defaults[key] = value

    req_file = doc_path / f"{req_id}.md"
    if req_file.exists():
        print(f"Error: Requirement {req_id} already exists at {req_file}", file=sys.stderr)
        return 1

    doc_path.mkdir(parents=True, exist_ok=True)

    json_lines = ["{"]
    for key, value in defaults.items():
        json_lines.append(f'  "{key}": {json.dumps(value)},')
    json_lines.append("}")

    req_file.write_text("\n".join(json_lines) + "\n---\n", encoding="utf-8")
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

    all_keys: set[str] = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())

    columns = ["id", "content", "link_to", "link_from"] + sorted(all_keys)

    outfile = open(output, "w", newline="", encoding="utf-8") if output else sys.stdout
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
                row[key] = ";".join(str(v) for v in value) if isinstance(value, list) else value
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
    if not project.all_requirements():
        print("No requirements found.", file=sys.stderr)
        return 1

    count = export_sqlite(project, output)
    print(f"Exported {count} requirements to {output}")
    return 0


def cmd_export_web(args):
    """Export requirements to a static website."""
    from .web import generate_website
    project = load_project(Path(args.doc) if args.doc else Path("."))
    generate_website(project, Path(args.output) if args.output else Path("_site"))
    print(f"Generated website in {args.output or '_site'}/")
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="reqsmd",
        description="reqsmd - Requirements management using markdown files"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    req_parser = subparsers.add_parser("req", help="Requirement operations")
    req_subparsers = req_parser.add_subparsers(dest="req_command")

    req_add_parser = req_subparsers.add_parser("add", help="Add a new requirement")
    req_add_parser.add_argument("req_id", help="Requirement ID (e.g., PRES-02)")
    req_add_parser.add_argument("--doc", "-d", help="Document folder path", default=".")

    export_parser = subparsers.add_parser("export", help="Export operations")
    export_subparsers = export_parser.add_subparsers(dest="export_command")

    csv_parser = export_subparsers.add_parser("csv", help="Export to CSV")
    csv_parser.add_argument("--doc", "-d", help="Document folder path")
    csv_parser.add_argument("--output", "-o", help="Output file path")

    sqlite_parser = export_subparsers.add_parser("sqlite", help="Export to SQLite")
    sqlite_parser.add_argument("--doc", "-d", help="Document folder path")
    sqlite_parser.add_argument("--output", "-o", help="Output file path", default="requirements.db")

    web_parser = export_subparsers.add_parser("web", help="Export to static website")
    web_parser.add_argument("--doc", "-d", help="Document folder path", default=".")
    web_parser.add_argument("--output", "-o", help="Output directory", default="_site")

    args = parser.parse_args()

    if args.command == "req":
        if args.req_command == "add":
            return cmd_req_add(args)
        req_parser.print_help()
        return 1
    elif args.command == "export":
        if args.export_command == "csv":
            return cmd_export_csv(args)
        elif args.export_command == "sqlite":
            return cmd_export_sqlite(args)
        elif args.export_command == "web":
            return cmd_export_web(args)
        export_parser.print_help()
        return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
