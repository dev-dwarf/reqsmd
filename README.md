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
  "req": { "default": "", "show-search": true },
  "priority": { "default": null, "show-compact": false },
  "phase": { "default": "" }
}
```

- `default` — value pre-filled when creating a new requirement
- `show-search` — whether the field appears as a column in the search UI (default: true)
- `show-compact` — whether the field appears in compact view (default: true)

## CLI

```
reqsmd req add REQ-ID [--doc PATH]
```
Create a new requirement file pre-populated with template defaults.

```
reqsmd export csv PATH [--output FILE]
```
Export all requirements in a document tree to CSV. Outputs to stdout if `--output` is omitted.

```
reqsmd export sqlite PATH [--output FILE]
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
