# reqsmd

Requirements management using plain markdown files. Requirements live in version control alongside your code.

## Concepts

**Requirements** are individual markdown files. The filename is the requirement ID (e.g., `SYS-1.md`). Each file has a JSON frontmatter block followed by markdown content (rationale, notes, details).

**Documents** are folders. All `.md` files in a folder belong to that document. Subfolders are child documents. The result is a tree of documents, each containing a list of requirements.

**Cross-references** use `[[REQ-ID]]` syntax in requirement content. Links are bidirectional — the tool tracks both `link-to` and `link-from` automatically.

## File Format

```
{
  "req": "The system shall do X.",
  "priority": 1,
  "phase": "design",
}
---
Optional rationale and notes in markdown.

This requirement exists because [[SYS-2]] depends on it.
```

The `req` field holds the formal requirement statement. Everything after `---` is markdown content (rationale, context, etc.).

## Project Structure

```
my-project/
├── req-template.json        # default fields for new requirements
├── SYS-1.md
├── SYS-2.md
└── software/
    ├── SW-1.md
    ├── SW-2.md
    └── interfaces/
        └── IF-1.md
```

`req-template.json` defines the fields available on requirements and their defaults:

```json
{
  "req":      { "default": "", "show-search": true, "hash-include": true },
  "priority": { "default": null, "show-compact": false, "hash-include": true },
  "phase":    { "default": "" }
}
```

- `default` — value pre-filled when creating a new requirement
- `show-search` — whether the field appears as a column in the search UI (default: true)
- `show-compact` — whether the field appears in compact view (default: true)
- `hash-include` — whether the field is included in the verification hash (default: false); `req` is always included regardless

## Verification

reqsmd can hash requirements and detect changes — a "compile step" that ensures traceability links remain valid as requirements evolve.

Each requirement's hash covers its `req` statement, any `hash-include` fields, and the stored verification hashes of all linked-to requirements. This means that if a dependency changes and is re-verified, all requirements that depend on it will fail their check until they are re-verified as well.

```
reqsmd req verify REQ-ID USER [--force] [--doc PATH]
```
Compute and store a verification hash for a requirement, recording who verified it. Fails if any linked-to requirements are not yet verified — they must be verified first to produce a stable hash. Use `--force` to recursively verify all unverified dependencies before verifying the target.

```
reqsmd req check REQ-ID [--doc PATH]
```
Check whether a requirement matches its stored verification hash. Exits non-zero if the requirement has changed or has never been verified.

```
reqsmd check [--doc PATH]
```
Check all requirements in the project. Prints a line per failing requirement (`FAIL`) or never-verified requirement (`UNVERIFIED`). Exits non-zero if any fail. Designed to run efficiently on large repositories — all hashes are computed in a single O(n) pass using a snapshot of stored dependency hashes.

**Example workflow:**

```
# Verify a leaf requirement (no dependencies)
reqsmd req verify SYS-1 alice

# Verify a requirement with unverified dependencies — fails:
reqsmd req verify SYS-2 alice
# Error: unverified dependencies: SYS-1
# Use --force to verify dependencies recursively.

# Use --force to verify the whole chain at once:
reqsmd req verify SYS-2 alice --force

# Check the entire project:
reqsmd check
# OK (42 requirements verified)

# After modifying SYS-1:
reqsmd check
# FAIL SYS-1          ← content changed since last verification
# FAIL SYS-2          ← dependency SYS-1 was re-verified, hash changed

# Re-verify the chain:
reqsmd req verify SYS-2 alice --force
reqsmd check
# OK (42 requirements verified)
```

The verification fields (`verified-hash`, `verified-by`) are stored in the requirement frontmatter and commit naturally to version control. Add them to `req-template.json` with `"show-search": false` to hide them from the search UI.

Circular dependencies are detected and reported as errors during `--force` traversal. Avoid mutual cross-references between requirements — links should flow in one direction (e.g., higher-level requirements linking to the lower-level ones that implement them).

## CLI
```
reqsmd export csv [--doc PATH] [--output FILE]
```
Export all requirements in a document tree to CSV. Outputs to stdout if `--output` is omitted.

```
reqsmd export sqlite [--doc PATH] [--output FILE]
```
Export all requirements to a SQLite database (`requirements` table with columns for all metadata fields).

```
reqsmd export web [--doc PATH] [--output DIR]
```
Generate a static website. Default output directory is `_site`. Serve with any static file server, e.g.:

```
python3 -m http.server --directory _site
```

## Web Export

The generated site includes:

- **Document pages** — one page per folder, listing all requirements with metadata, rationale, and cross-reference links
- **Search page** — client-side full-text search and filtering across all requirements, with SQL query support
- **Compact toggle** — hides rationale and secondary metadata for a denser view

The site is plain HTML/CSS/JS with no framework dependencies. `sql.js` is vendored locally for the search page.

## Installation

```
python3 -m venv .venv
.venv/bin/pip install -e .
```

Requires Python 3.10+.
