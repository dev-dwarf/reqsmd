"""Web export generator for reqsmd requirements management."""

import html
import json
import os
import re
import shutil
import time
from pathlib import Path

import markdown

from .core import Document, Project, Requirement, export_sqlite, sort_key


# HTML Templates

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - reqsmd</title>
    <link rel="stylesheet" href="{root_path}style.css">
    {head_extra}
    <script>
        if (localStorage.getItem('compactView') === 'true') {{
            document.documentElement.className = 'compact-view';
        }}
    </script>
</head>
<body{body_attrs}>
    <nav class="sidebar">
        <div class="nav-header">
            <a href="{root_path}index.html">reqsmd</a>
            <a href="{root_path}search.html" class="nav-link{nav_search}">Search</a>
        </div>
        {parent_link}
        {toc}
    </nav>
    <main class="content{content_class}">
        {content}
    </main>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var toggle = document.getElementById('compact-toggle');
            if (toggle) {{
                if (localStorage.getItem('compactView') === 'true') {{
                    document.body.classList.add('compact-view');
                    toggle.classList.add('active');
                }}
                toggle.addEventListener('click', function() {{
                    document.body.classList.toggle('compact-view');
                    toggle.classList.toggle('active');
                    localStorage.setItem('compactView', document.body.classList.contains('compact-view'));
                }});
            }}
        }});
    </script>
</body>
</html>
"""

# Search page content (injected into BASE_TEMPLATE; no Python format placeholders)
SEARCH_CONTENT = """        <div class="search-controls">
            <div class="search-row">
                <input type="text" id="search-input" placeholder="Search requirements...">
                <button id="search-btn">Search</button>
            </div>
            <div class="options-row">
                <div class="columns-dropdown">
                    <button id="columns-toggle-btn" type="button">Columns</button>
                    <div id="columns-popup" class="columns-popup">
                        <div id="columns-container"></div>
                    </div>
                </div>
                <div class="filters-row" id="filters-container"></div>
                <button id="reset-btn" type="button" class="reset-btn">Reset</button>
            </div>
            <div class="sql-row">
                <input type="text" id="sql-input" placeholder="SQL: SELECT * FROM requirements WHERE ...">
            </div>
        </div>
        <div id="results">
            <div id="error-message" style="display:none"></div>
            <table id="results-table">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
        <script src="search.js"></script>"""


def _render_page(title: str, root_path: str, content: str, *,
                 parent_link: str = "", toc: str = "",
                 head_extra: str = "", body_attrs: str = "",
                 nav_active: str = "", content_class: str = "") -> str:
    """Render a page using BASE_TEMPLATE."""
    return BASE_TEMPLATE.format(
        title=title,
        root_path=root_path,
        content=content,
        parent_link=parent_link,
        toc=toc,
        head_extra=head_extra,
        body_attrs=body_attrs,
        nav_search=" active" if nav_active == "search" else "",
        content_class=f" {content_class}" if content_class else "",
    )


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
    if suffix.endswith('.0'):
        suffix = suffix[:-2]
    dot_count = suffix.count('.')
    return min(dot_count + 1, 3)


def make_req_link_html(req_id: str, project: Project, current_doc: Document) -> str:
    """Generate an HTML link for a single requirement ID."""
    req = project.get_requirement(req_id)
    if req:
        req_doc_path = req.file_path.parent
        rel_path = os.path.relpath(req_doc_path, current_doc.path)
        href = f"index.html#{req_id}" if rel_path == "." else f"{rel_path}/index.html#{req_id}"
        return f'<a href="{href}" class="req-link">{req_id}</a>'
    return f'<span class="req-link-broken">{req_id}</span>'


def generate_requirement_html(req: Requirement, project: Project, current_doc: Document,
                              hidden_fields: set[str] = None,
                              compact_hidden_fields: set[str] = None) -> str:
    """Generate HTML for a single requirement."""
    hidden_fields = hidden_fields or set()
    compact_hidden_fields = compact_hidden_fields or set()

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

    def meta_class(field_name: str) -> str:
        if field_name in compact_hidden_fields:
            return 'meta-item compact-hide'
        return 'meta-item'

    meta_parts = []
    if "priority" not in hidden_fields and req.priority is not None:
        meta_parts.append(f'<span class="{meta_class("priority")}">Priority: {req.priority}</span>')
    if "phase" not in hidden_fields and req.phase:
        meta_parts.append(f'<span class="{meta_class("phase")}">Phase: {req.phase}</span>')

    special_fields = {"priority", "phase", "req"}
    for key, value in req.metadata.items():
        if key in hidden_fields or key in special_fields:
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        meta_parts.append(f'<span class="{meta_class(key)}">{html.escape(key)}: {html.escape(str(value))}</span>')

    meta_html = " ".join(meta_parts) if meta_parts else ""

    links_html = ""
    if req.link_to or req.link_from:
        links_parts = []
        if req.link_to:
            to_links = ", ".join(make_req_link_html(tid, project, current_doc) for tid in req.link_to)
            links_parts.append(f'<div class="links-to">Links to: {to_links}</div>')
        if req.link_from:
            from_links = ", ".join(make_req_link_html(fid, project, current_doc) for fid in req.link_from)
            links_parts.append(f'<div class="links-from">Linked from: {from_links}</div>')
        links_html = '<div class="req-links">' + "".join(links_parts) + '</div>'

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
        req_text_html = f'<div class="req-statement">{"".join(rendered_parts)}</div>'

    rationale_html = ""
    if content_html.strip():
        rationale_html = f'''
        <div class="req-rationale">
            <h3 class="rationale-label">Rationale</h3>
            <div class="rationale-content">
                {content_html}
            </div>
        </div>'''

    level = get_indent_level(req.id)
    heading_tag = f"h{level + 1}"

    return f"""
    <article class="requirement" id="{html.escape(req.id)}" data-level="{level}">
        <header class="req-header">
            <{heading_tag}><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a></{heading_tag}>
            <div class="req-meta">{meta_html}</div>
        </header>
        <div class="req-content">
            {req_text_html}
            {rationale_html}
        </div>
        {links_html}
    </article>
    """


def generate_document_page(doc: Document, project: Project, hidden_fields: set[str] = None,
                           compact_hidden_fields: set[str] = None) -> str:
    """Generate HTML page for a document."""
    hidden_fields = hidden_fields or set()
    compact_hidden_fields = compact_hidden_fields or set()

    rel_path = os.path.relpath(doc.path, project.root_path)
    root_path = "" if rel_path == "." else "../" * (rel_path.count(os.sep) + 1)

    reqs_html = [generate_requirement_html(req, project, doc, hidden_fields, compact_hidden_fields)
                 for req in doc.requirements]

    children_html = ""
    if doc.children:
        parts = ["<section class='child-docs compact-hide'><h2>Child Documents</h2><ul>"]
        for child in doc.children:
            child_rel = os.path.relpath(child.path, doc.path)
            parts.append(f'<li><a href="{child_rel}/index.html">{html.escape(child.name)}</a></li>')
        parts.append("</ul></section>")
        children_html = "\n".join(parts)

    content = f"""
    <header class="doc-header">
        <h1>{html.escape(doc.name)}</h1>
        <div class="doc-controls">
            <button id="compact-toggle" class="compact-toggle">Compact</button>
        </div>
    </header>
    {children_html}
    <section class="requirements">
        {"".join(reqs_html)}
    </section>
    """

    # Table of contents
    toc = ""
    if doc.requirements:
        toc_parts = ['<div class="nav-section-header">Contents</div>', '<ul class="nav-toc">']
        for req in doc.requirements:
            level = get_indent_level(req.id)
            toc_parts.append(f'<li class="toc-level-{level}"><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a></li>')
        toc_parts.append('</ul>')
        toc = '\n'.join(toc_parts)

    # Parent link
    parent_link = ""
    if doc.parent:
        parent = doc.parent
        parent_rel = os.path.relpath(parent.path, project.root_path)
        href = f"{root_path}index.html" if parent_rel == "." else f"{root_path}{parent_rel}/index.html"
        parent_link = f'<div class="nav-parent"><a href="{href}">← {html.escape(parent.name)}</a></div>'

    return _render_page(doc.name, root_path, content, parent_link=parent_link, toc=toc)


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
    compact_hidden_fields = project.get_compact_hidden_fields()

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
                     head_extra=search_head, nav_active="search",
                     content_class="search-content"),
        encoding="utf-8"
    )

    for doc in project.all_documents():
        rel_path = os.path.relpath(doc.path, project.root_path)
        doc_output = output_path if rel_path == "." else output_path / rel_path
        doc_output.mkdir(parents=True, exist_ok=True)
        doc_html = generate_document_page(doc, project, hidden_fields, compact_hidden_fields)
        (doc_output / "index.html").write_text(doc_html, encoding="utf-8")
