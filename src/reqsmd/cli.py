"""CLI entry point for reqsmd requirements management."""

import argparse
import csv
import sys
from pathlib import Path

from .core import (export_sqlite, get_hash_fields, get_stored_hashes,
                   load_project, req_verification_status, verify_requirement)

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


def cmd_req_verify(args):
    """Hash a requirement and mark it as verified."""
    doc_path = Path(args.doc) if args.doc else Path(".")
    project = load_project(doc_path)
    req = project.get_requirement(args.req_id)
    if not req:
        print(f"Error: Requirement {args.req_id} not found", file=sys.stderr)
        return 1

    hash_fields = get_hash_fields(project)
    stored_hashes = get_stored_hashes(project)

    def on_verify(req_id, user, req_hash):
        print(f"Verified {req_id} by {user} (hash: {req_hash[:16]}...)")

    try:
        ok = verify_requirement(req, project, args.user, hash_fields, stored_hashes,
                                force=args.force, on_verify=on_verify)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not ok:
        unverified = [d for d in req.link_to if not stored_hashes.get(d)]
        print(f"Error: unverified dependencies: {', '.join(unverified)}", file=sys.stderr)
        print("Use --force to verify dependencies recursively.", file=sys.stderr)
        return 1
    return 0


def cmd_req_check(args):
    """Check whether a requirement matches its stored verification hash."""
    doc_path = Path(args.doc) if args.doc else Path(".")
    project = load_project(doc_path)
    req = project.get_requirement(args.req_id)
    if not req:
        print(f"Error: Requirement {args.req_id} not found", file=sys.stderr)
        return 1

    hash_fields = get_hash_fields(project)
    stored_hashes = get_stored_hashes(project)
    status = req_verification_status(req, stored_hashes, hash_fields)
    print(f"{status} {args.req_id}")
    return 0 if status == "OK" else 1


def cmd_check(args):
    """Check all requirements and report any that have changed since verification."""
    doc_path = Path(args.doc) if args.doc else Path(".")
    project = load_project(doc_path)
    all_reqs = project.all_requirements()

    hash_fields = get_hash_fields(project)
    stored_hashes = get_stored_hashes(project)

    failing = []
    for req in all_reqs:
        status = req_verification_status(req, stored_hashes, hash_fields)
        if status != "OK":
            failing.append((req.id, status))

    if failing:
        for req_id, status in failing:
            print(f"{status} {req_id}")
        return 1
    print(f"OK ({len(all_reqs)} requirements verified)")
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

    req_verify_parser = req_subparsers.add_parser("verify", help="Verify a requirement")
    req_verify_parser.add_argument("req_id", help="Requirement ID")
    req_verify_parser.add_argument("user", help="Username of verifier")
    req_verify_parser.add_argument("--doc", "-d", help="Project root path", default=".")
    req_verify_parser.add_argument("--force", "-f", action="store_true",
                                   help="Recursively verify unverified dependencies first")

    req_check_parser = req_subparsers.add_parser("check", help="Check a requirement's hash")
    req_check_parser.add_argument("req_id", help="Requirement ID")
    req_check_parser.add_argument("--doc", "-d", help="Project root path", default=".")

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

    check_parser = subparsers.add_parser("check", help="Check all requirements")
    check_parser.add_argument("--doc", "-d", help="Project root path", default=".")

    args = parser.parse_args()

    if args.command == "req":
        if args.req_command == "verify":
            return cmd_req_verify(args)
        elif args.req_command == "check":
            return cmd_req_check(args)
        req_parser.print_help()
        return 1
    elif args.command == "check":
        return cmd_check(args)
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
