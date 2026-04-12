"""CLI entry point for reqsmd requirements management."""

import argparse
import csv
import sys
from pathlib import Path

from .core import (compute_cascade_failures, export_sqlite, get_hash_fields,
                   get_stored_hashes, load_project, req_verification_status,
                   verify_requirement)
from .importer import import_csv


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

    import_parser = subparsers.add_parser("import", help="Import operations")
    import_subparsers = import_parser.add_subparsers(dest="import_command")

    import_csv_parser = import_subparsers.add_parser("csv", help="Import requirements from CSV")
    import_csv_parser.add_argument("file", help="CSV file to import")
    import_csv_parser.add_argument("--id-col", required=True, help="Column to use as requirement ID")
    import_csv_parser.add_argument("--req-col", required=True, help="Column to use as requirement text")
    import_csv_parser.add_argument("--rationale-col", help="Column to use as rationale/body text")
    import_csv_parser.add_argument("--doc-col", help="Column to use as document folder")
    import_csv_parser.add_argument("--attrs", nargs="+", metavar="COL", help="Columns to include as metadata attributes")
    import_csv_parser.add_argument("--output", "-o", help="Output directory (default: CSV filename without extension)")

    args = parser.parse_args()

    if args.command == "req":
        if args.req_command == "verify":
            project = load_project(Path(args.doc))
            req = project.get_requirement(args.req_id)
            if not req:
                print(f"Error: Requirement {args.req_id} not found", file=sys.stderr)
                return 1
            hash_fields = get_hash_fields(project)
            stored_hashes = get_stored_hashes(project)
            try:
                ok = verify_requirement(
                    req, project, args.user, hash_fields, stored_hashes,
                    force=args.force,
                    on_verify=lambda rid, user, h: print(f"Verified {rid} by {user} (hash: {h[:16]}...)"),
                )
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            if not ok:
                unverified = [d for d in req.link_to if not stored_hashes.get(d)]
                print(f"Error: unverified dependencies: {', '.join(unverified)}", file=sys.stderr)
                print("Use --force to verify dependencies recursively.", file=sys.stderr)
                return 1
            return 0

        elif args.req_command == "check":
            project = load_project(Path(args.doc))
            req = project.get_requirement(args.req_id)
            if not req:
                print(f"Error: Requirement {args.req_id} not found", file=sys.stderr)
                return 1
            status = req_verification_status(req, get_stored_hashes(project), get_hash_fields(project))
            print(f"{status} {args.req_id}")
            return 0 if status == "OK" else 1

        req_parser.print_help()
        return 1

    elif args.command == "check":
        project = load_project(Path(args.doc))
        stored_hashes = get_stored_hashes(project)
        hash_fields = get_hash_fields(project)
        direct, cascade = compute_cascade_failures(project, stored_hashes, hash_fields)
        if direct or cascade:
            for req_id, status in direct:
                print(f"{status} {req_id}")
            for req_id in cascade:
                print(f"STALE {req_id}")
            total = len(direct) + len(cascade)
            print(f"\n{total} requirements require attention "
                  f"({len(direct)} direct, {len(cascade)} downstream)")
            return 1
        print(f"OK ({len(project.all_requirements())} requirements verified)")
        return 0

    elif args.command == "export":
        if args.export_command == "csv":
            project = load_project(Path(args.doc))
            reqs = project.all_requirements()
            if not reqs:
                print("No requirements found.", file=sys.stderr)
                return 1
            all_keys: set[str] = set()
            for req in reqs:
                all_keys.update(req.metadata.keys())
            columns = ["id", "content", "link_to", "link_from"] + sorted(all_keys)
            outfile = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
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
                if args.output:
                    outfile.close()
            if args.output:
                print(f"Exported {len(reqs)} requirements to {args.output}")
            return 0

        elif args.export_command == "sqlite":
            project = load_project(Path(args.doc))
            if not project.all_requirements():
                print("No requirements found.", file=sys.stderr)
                return 1
            count = export_sqlite(project, args.output)
            print(f"Exported {count} requirements to {args.output}")
            return 0

        elif args.export_command == "web":
            from .web import generate_website
            project = load_project(Path(args.doc))
            generate_website(project, Path(args.output))
            print(f"Generated website in {args.output}/")
            return 0

        export_parser.print_help()
        return 1

    elif args.command == "import":
        if args.import_command == "csv":
            output = args.output or Path(args.file).stem
            try:
                count = import_csv(
                    args.file, output,
                    id_col=args.id_col,
                    req_col=args.req_col,
                    rationale_col=args.rationale_col,
                    doc_col=args.doc_col,
                    attrs=args.attrs or [],
                )
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            print(f"Imported {count} requirements to {output}/")
            return 0
        import_parser.print_help()
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
