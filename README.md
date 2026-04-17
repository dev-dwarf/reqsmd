![reqsmd logo](static/logo-black.svg)

Requirements management using plain markdown files. Requirements live in version control alongside your code.

## Concepts

**Requirements** are individual markdown files. The filename is the requirement ID (e.g., `SYS-1.md`). Each file has a JSON frontmatter block followed by optional markdown content (rationale, notes, details).

**Documents** are folders. All `.md` files in a folder belong to that document. Subfolders are child documents, forming a tree that mirrors your system decomposition.

**Cross-references** use `[[REQ-ID]]` syntax anywhere in a requirement. Links are bidirectional — the tool tracks both `link_to` and `link_from` automatically.

## File Format

```
{
  "req": "The system shall do X.",
  "priority": 1,
}
---
Optional rationale and notes in markdown.

This requirement traces to [[SYS-2]].
```

## Project Structure

```
my-project/
├── req-template.json        # field definitions
├── SYS-1.md
├── SYS-2.md
└── software/
    ├── SW-1.md
    └── interfaces/
        └── IF-1.md
```

`req-template.json` defines the fields available on requirements:

```json
{
  "req":      { "show-search": true, "verified": true },
  "priority": { "show-compact": false, "verified": true }
}
```

- `show-search` — whether the field appears as a column in the search UI (default: true)
- `show-compact` — whether the field appears in compact view (default: true)
- `verified` — whether the field is included in the verification hash (default: false); `req` is always included regardless

## Usage

Install with Python 3.10+:

```
python3 -m venv .venv && .venv/bin/pip install -e .
```

Then before running any of the below commands:
```
(windows) venv\Scripts\activate
(linux) venv/bin/activate
```

Verify requirements and check the project:
```
reqsmd req verify SYS-1 alice           # hash and sign a requirement
reqsmd req verify SYS-2 alice --force   # recursively verify dependencies first
reqsmd check                            # check all — prints FAIL / UNVERIFIED / STALE
```

Each requirement's hash covers its `req` field, any fields marked `verified: true` in `req-template.json`, and the stored hashes of its linked-to requirements. If a dependency changes, all dependents become STALE until re-verified. Verification fields (`verified-hash`, `verified-by`) are stored in frontmatter and commit to version control.

Export and browse:

```
reqsmd export web [--doc PATH] [--output DIR]   # static site, default: _site
reqsmd export csv [--doc PATH] [--output FILE]
reqsmd export sqlite [--doc PATH] [--output FILE]
python3 -m http.server --directory _site
```

## Recommended Tools

- **[Obsidian](https://obsidian.md)** — open the requirements folder as a vault. Provides a file tree, markdown editing, and `[[link]]` navigation.
- **[Sourcetree](https://www.sourcetreeapp.com)** — visual git client for reviewing and committing requirements changes.