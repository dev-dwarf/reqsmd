"""Web export generator for reqsmd requirements management."""

import html
import json
import os
import re
import shutil
import time
import urllib.parse
from pathlib import Path

import markdown

from .core import (Document, Project, Requirement, compute_cascade_failures, export_sqlite,
                   get_hash_fields, get_stored_hashes, req_verification_status,
                   sort_key, strip_trailing_zeros)


# HTML Templates

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - reqsmd</title>
    <link rel="stylesheet" href="{root_path}style.css">
    {head_extra}
</head>
<body>
    <nav>
        <a href="{root_path}index.html"><img src="{root_path}logo-white.svg" alt="reqsmd"></a>
        <a href="{root_path}search.html"{nav_search}>Search</a>
    </nav>
    <div>
        {sidebar}
        <main>
            {content}
        </main>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var toggle = document.getElementById('compact-toggle');
            if (!toggle) return;
            var active = localStorage.getItem('compactView') === 'true';
            if (active) {{ document.body.classList.add('compact-view'); toggle.setAttribute('aria-pressed', 'true'); }}
            toggle.addEventListener('click', function() {{
                document.body.classList.toggle('compact-view');
                var on = document.body.classList.contains('compact-view');
                toggle.setAttribute('aria-pressed', on);
                localStorage.setItem('compactView', on);
            }});
        }});
    </script>
</body>
</html>
"""

# Search page content (injected into BASE_TEMPLATE; no Python format placeholders)
SEARCH_CONTENT = """        <div id="search-controls">
            <div id="search-row">
                <input type="text" id="search-input" placeholder="Search requirements...">
                <button type="button" id="search-btn">Search</button>
            </div>
            <div id="options-row">
                <div>
                    <button type="button" id="columns-toggle-btn">Columns</button>
                    <div id="columns-popup" class="columns-popup">
                        <div id="columns-container"></div>
                    </div>
                </div>
                <div id="filters-container"></div>
                <button type="button" id="reset-btn">Reset</button>
            </div>
            <input type="text" id="sql-input" placeholder="SQL: SELECT * FROM requirements WHERE ...">
        </div>
        <div id="results">
            <div id="error-message"></div>
            <table id="results-table">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
        <script src="search.js"></script>"""


def _render_page(title: str, root_path: str, content: str, *,
                 sidebar: str = "", head_extra: str = "", nav_active: str = "") -> str:
    """Render a page using BASE_TEMPLATE."""
    return BASE_TEMPLATE.format(
        title=title,
        root_path=root_path,
        content=content,
        sidebar=sidebar,
        head_extra=head_extra,
        nav_search=' class="active"' if nav_active == "search" else "",
    )


def _root_path(doc: Document, project: Project) -> str:
    rel = os.path.relpath(doc.path, project.root_path)
    return "" if rel == "." else "../" * (rel.count(os.sep) + 1)


def get_indent_level(req_id: str) -> int:
    """
    Calculate indent level from requirement ID based on dot count in the suffix.

    Examples:
        REQ-1 -> level 1
        REQ-1.1 -> level 2
        REQ-1.1.2 -> level 3
    """
    parts = req_id.rsplit('-', 1)
    suffix = parts[-1] if len(parts) > 1 else req_id
    dot_count = suffix.count('.')
    return min(dot_count + 1, 3)


def make_req_link_html(req_id: str, project: Project, current_doc: Document) -> str:
    """Generate an HTML link for a single requirement ID."""
    req_id = strip_trailing_zeros(req_id)
    req = project.get_requirement(req_id)
    if req:
        req_doc_path = req.file_path.parent
        rel_path = os.path.relpath(req_doc_path, current_doc.path)
        href = f"index.html#{req_id}" if rel_path == "." else f"{rel_path}/index.html#{req_id}"
        return f'<a href="{href}">{req_id}</a>'
    return f'<del>{req_id}</del>'


def generate_requirement_html(req: Requirement, project: Project, current_doc: Document,
                              hidden_fields: set[str] = None, status_map: dict = None,
                              root_path: str = "") -> str:
    """Generate HTML for a single requirement."""
    hidden_fields = hidden_fields or set()

    # Resolve [[REQID]] references in content, skipping code blocks
    code_pattern = re.compile(r'(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`]*`)')
    parts = code_pattern.split(req.content)
    resolved_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            resolved_parts.append(re.sub(r'\[\[([^\]]+)\]\]',
                                         lambda m: make_req_link_html(m.group(1), project, current_doc),
                                         part))
        else:
            resolved_parts.append(part)
    content_resolved = ''.join(resolved_parts)

    # Convert markdown to HTML (ensure blank line before lists first)
    list_marker = re.compile(r'^(\s*)([-*+]|\d+[.)]) ')
    lines = content_resolved.splitlines()
    fixed_lines = []
    for i, line in enumerate(lines):
        if i > 0 and list_marker.match(line):
            prev = lines[i - 1]
            if prev.strip() and not list_marker.match(prev):
                fixed_lines.append('')
        fixed_lines.append(line)
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'sane_lists'])
    content_html = md.convert('\n'.join(fixed_lines))
    block_tags = ['</p>', '</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</h6>',
                  '</ul>', '</ol>', '</li>', '</table>', '</tr>', '</thead>',
                  '</tbody>', '</pre>', '</blockquote>', '</div>']
    for tag in block_tags:
        content_html = content_html.replace(tag, tag + '\n')

    meta_parts = []
    if "priority" not in hidden_fields and req.priority is not None:
        meta_parts.append(f'<span>Priority: {req.priority}</span>')
    special_fields = {"priority", "req"}
    for key, value in req.metadata.items():
        if key in hidden_fields or key in special_fields:
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        meta_parts.append(f'<span>{html.escape(key)}: {html.escape(str(value))}</span>')

    meta_html = " ".join(meta_parts) if meta_parts else ""

    links_html = ""
    if req.link_to or req.link_from:
        links_parts = []
        if req.link_to:
            to_links = ", ".join(make_req_link_html(tid, project, current_doc) for tid in req.link_to)
            ids = ", ".join(f"'{tid}'" for tid in req.link_to)
            sql = urllib.parse.quote(f"SELECT * FROM requirements WHERE id IN ({ids})")
            links_parts.append(f'<div><a class="link-quiet" href="{root_path}search.html?sql={sql}">Links to</a>: {to_links}</div>')
        if req.link_from:
            from_links = ", ".join(make_req_link_html(fid, project, current_doc) for fid in req.link_from)
            ids = ", ".join(f"'{fid}'" for fid in req.link_from)
            sql = urllib.parse.quote(f"SELECT * FROM requirements WHERE id IN ({ids})")
            links_parts.append(f'<div><a class="link-quiet" href="{root_path}search.html?sql={sql}">Linked from</a>: {from_links}</div>')
        links_html = '<footer>' + "".join(links_parts) + '</footer>'

    req_text = req.metadata.get("req")
    req_text_html = ""
    if req_text and "req" not in hidden_fields:
        parts = re.split(r'(`[^`]*`)', str(req_text))
        rendered_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                rendered_parts.append(f'<code>{html.escape(part[1:-1])}</code>')
            else:
                escaped = html.escape(part)
                rendered_parts.append(re.sub(r'\[\[([^\]]+)\]\]',
                                             lambda m: make_req_link_html(m.group(1), project, current_doc),
                                             escaped))
        req_text_html = f'<p>{"".join(rendered_parts)}</p>'

    rationale_html = ""
    if content_html.strip():
        rationale_html = f'<blockquote>{content_html}</blockquote>'

    status = (status_map or {}).get(req.id)
    status_html = ""
    if status == "FAIL":
        rid = req.id.replace("'", "''")
        recursive_sql = (
            f"WITH RECURSIVE dependents(id) AS ("
            f"SELECT link_from FROM links WHERE link_to = '{rid}' "
            f"UNION SELECT l.link_from FROM links l JOIN dependents d ON l.link_to = d.id"
            f") SELECT r.* FROM requirements r JOIN dependents d ON r.id = d.id "
            f"WHERE r.verified_status = 'STALE'"
        )
        sql = urllib.parse.quote(recursive_sql)
        status_html = f'<strong><a href="{root_path}search.html?sql={sql}">FAIL</a></strong>'
    elif status == "STALE":
        rid = req.id.replace("'", "''")
        recursive_sql = (
            f"WITH RECURSIVE deps(id) AS ("
            f"SELECT link_to FROM links WHERE link_from = '{rid}' "
            f"UNION SELECT l.link_to FROM links l JOIN deps d ON l.link_from = d.id"
            f") SELECT r.* FROM requirements r JOIN deps d ON r.id = d.id "
            f"WHERE r.verified_status != 'OK'"
        )
        sql = urllib.parse.quote(recursive_sql)
        status_html = f'<strong><a href="{root_path}search.html?sql={sql}">STALE</a></strong>'

    level = get_indent_level(req.id)
    heading_tag = f"h{level + 1}"

    return f"""
    <article id="{html.escape(req.id)}">
        <header>
            <{heading_tag}><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a></{heading_tag}>
            {req_text_html}
            {meta_html}
            {status_html}
        </header>
        {rationale_html}
        {links_html}
    </article>
    """


def _build_toc(requirements: list) -> str:
    if not requirements:
        return ""
    parts = ["<ul>"]
    current_level = 1
    first = True
    for req in requirements:
        level = get_indent_level(req.id)
        if level > current_level:
            for _ in range(level - current_level):
                parts.append("<ul>")
        elif level < current_level:
            for _ in range(current_level - level):
                parts.append("</li></ul>")
            parts.append("</li>")
        elif not first:
            parts.append("</li>")
        parts.append(f'<li><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a>')
        current_level = level
        first = False
    for _ in range(current_level - 1):
        parts.append("</li></ul>")
    parts.append("</li></ul>")
    return "".join(parts)


def generate_document_page(doc: Document, project: Project, hidden_fields: set[str] = None,
                           status_map: dict = None) -> str:
    """Generate HTML page for a document."""
    hidden_fields = hidden_fields or set()

    root_path = _root_path(doc, project)

    reqs_html = [generate_requirement_html(req, project, doc, hidden_fields, status_map, root_path)
                 for req in doc.requirements]

    content = f"""
    <h2>{html.escape(doc.name)}</h2>
    <section>
        {"".join(reqs_html)}
    </section>
    """

    # Build aside sidebar with compact toggle, parent link, child docs, and TOC
    sidebar = ""
    if doc.parent or doc.children or doc.requirements:
        aside_parts = ["<aside>"]
        aside_parts.append('<button id="compact-toggle" aria-pressed="false">Compact</button>')
        aside_parts.append("<ul>")
        if doc.parent:
            parent = doc.parent
            parent_rel = os.path.relpath(parent.path, project.root_path)
            href = f"{root_path}index.html" if parent_rel == "." else f"{root_path}{parent_rel}/index.html"
            aside_parts.append(f'<li><a href="{href}">← {html.escape(parent.name)}</a></li>')
        if doc.children:
            for child in doc.children:
                child_rel = os.path.relpath(child.path, doc.path)
                aside_parts.append(f'<li><a href="{child_rel}/index.html">{html.escape(child.name)} →</a></li>')
        aside_parts.append("</ul>")
        if doc.requirements:
            aside_parts.append(_build_toc(doc.requirements))
        aside_parts.append("</aside>")
        sidebar = "\n".join(aside_parts)

    return _render_page(doc.name, root_path, content, sidebar=sidebar)


def generate_website(project: Project, output_path: Path):
    """Generate complete static website."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        for asset in static_dir.iterdir():
            if asset.is_file():
                shutil.copy(asset, output_path / asset.name)
            elif asset.is_dir():
                dest_dir = output_path / asset.name
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.copytree(asset, dest_dir)

    # Generate SQLite database for search
    export_sqlite(project, output_path / "requirements.db")

    hidden_fields = project.get_hidden_fields()

    # Build full status map (OK/FAIL/UNVERIFIED/STALE) for badge display
    _hash_fields = get_hash_fields(project)
    _stored_hashes = get_stored_hashes(project)
    _, _cascade = compute_cascade_failures(project, _stored_hashes, _hash_fields)
    _cascade_ids = set(_cascade)
    status_map = {}
    for req in project.all_requirements():
        s = req_verification_status(req, _stored_hashes, _hash_fields)
        if s == "OK" and req.id in _cascade_ids:
            s = "STALE"
        status_map[req.id] = s

    template_fields = {}
    for key, value in project.template.items():
        template_fields[key] = {"show-search": value.get("show-search", True) if isinstance(value, dict) else True}
    config = {
        "hiddenColumns": list(hidden_fields),
        "templateFields": template_fields,
        "dbVersion": int(time.time()),
    }
    search_head = (
        '<script src="vendor/sql-wasm.js"></script>\n    '
        f'<script>window.reqsmd_CONFIG = {json.dumps(config)};</script>'
    )
    (output_path / "search.html").write_text(
        _render_page("Search", "", SEARCH_CONTENT,
                     head_extra=search_head, nav_active="search"),
        encoding="utf-8"
    )

    for doc in project.all_documents():
        rel_path = os.path.relpath(doc.path, project.root_path)
        doc_output = output_path if rel_path == "." else output_path / rel_path
        doc_output.mkdir(parents=True, exist_ok=True)
        doc_html = generate_document_page(doc, project, hidden_fields, status_map)
        (doc_output / "index.html").write_text(doc_html, encoding="utf-8")
