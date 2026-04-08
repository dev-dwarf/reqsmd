"""Web export generator for MDOORS requirements management."""

import html
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import markdown

from .core import Document, Project, Requirement, sort_key


# HTML Templates

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - MDOORS</title>
    <link rel="stylesheet" href="{root_path}style.css">
    <script>
        if (localStorage.getItem('compactView') === 'true') {{
            document.documentElement.className = 'compact-view';
        }}
    </script>
</head>
<body>
    <nav class="sidebar">
        <div class="nav-header">
            <a href="{root_path}index.html">MDOORS</a>
        </div>
        {parent_link}
        {toc}
        <div class="nav-section-header">Documents</div>
        <ul class="nav-tree">
            {nav_tree}
        </ul>
        <div class="nav-footer">
            <a href="{root_path}search.html">Search</a>
        </div>
    </nav>
    <main class="content">
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

SEARCH_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search - MDOORS</title>
    <link rel="stylesheet" href="style.css">
    <script src="vendor/sql-wasm.js"></script>
    <script>
        window.MDOORS_CONFIG = {config_json};
    </script>
</head>
<body>
    <nav class="sidebar">
        <div class="nav-header">
            <a href="index.html">MDOORS</a>
        </div>
        <ul class="nav-tree">
            {nav_tree}
        </ul>
        <div class="nav-footer">
            <a href="search.html" class="active">Search</a>
        </div>
    </nav>
    <main class="content search-content">
        <div class="search-controls">
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
            <table id="results-table">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
    </main>
    <script src="search.js"></script>
</body>
</html>
"""


def get_indent_level(req_id: str) -> int:
    """
    Calculate indent level from requirement ID based on dot count in the suffix.

    Examples:
        REQ-1 -> level 1
        REQ-1.1 -> level 2
        REQ-1.1.2 -> level 3
    """
    # Find the numeric suffix (after the last dash or the whole string if no dash)
    parts = req_id.rsplit('-', 1)
    suffix = parts[-1] if len(parts) > 1 else req_id
    # Count dots to determine nesting level
    dot_count = suffix.count('.')
    return min(dot_count + 1, 3)  # Cap at level 3


def markdown_to_html(content: str) -> str:
    """
    Convert markdown to HTML using python-markdown library.

    Supports tables and other standard markdown features.
    Output includes newlines for inspectability.
    """
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    html_output = md.convert(content)

    # Add newlines after block-level tags for inspectability
    block_tags = ['</p>', '</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</h6>',
                  '</ul>', '</ol>', '</li>', '</table>', '</tr>', '</thead>',
                  '</tbody>', '</pre>', '</blockquote>', '</div>']
    for tag in block_tags:
        html_output = html_output.replace(tag, tag + '\n')

    return html_output


def resolve_references_html(content: str, project: Project, current_doc: Document) -> str:
    """Resolve [[REQID]] references to HTML links."""
    def replace_ref(match):
        req_id = match.group(1)
        req = project.get_requirement(req_id)
        if req:
            # Calculate relative path
            req_doc_path = req.file_path.parent
            rel_path = os.path.relpath(req_doc_path, current_doc.path)
            if rel_path == ".":
                href = f"index.html#{req_id}"
            else:
                href = f"{rel_path}/index.html#{req_id}"
            return f'<a href="{href}" class="req-link">{req_id}</a>'
        else:
            return f'<span class="req-link-broken">{req_id}</span>'

    return re.sub(r'\[\[([^\]]+)\]\]', replace_ref, content)


def generate_nav_tree(project: Project, current_doc: Document = None, root_path: str = "") -> str:
    """Generate navigation tree HTML."""
    def render_doc(doc: Document, depth: int = 0) -> str:
        rel_path = os.path.relpath(doc.path, project.root_path)
        if rel_path == ".":
            href = f"{root_path}index.html"
        else:
            href = f"{root_path}{rel_path}/index.html"

        is_current = current_doc and doc.path == current_doc.path
        active_class = ' class="active"' if is_current else ""

        parts = [f'<li><a href="{href}"{active_class}>{html.escape(doc.name)}</a>']

        if doc.children:
            parts.append("<ul>")
            for child in doc.children:
                parts.append(render_doc(child, depth + 1))
            parts.append("</ul>")

        parts.append("</li>")
        return "\n".join(parts)

    return render_doc(project.root)


def generate_toc(doc: Document) -> str:
    """Generate table of contents for a document's requirements."""
    if not doc.requirements:
        return ""

    parts = ['<div class="nav-section-header">Contents</div>', '<ul class="nav-toc">']
    for req in doc.requirements:
        parts.append(f'<li><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a></li>')
    parts.append('</ul>')
    return '\n'.join(parts)


def generate_parent_link(doc: Document, project: Project, root_path: str) -> str:
    """Generate a link to the parent document."""
    if not doc.parent:
        return ""

    parent = doc.parent
    parent_rel = os.path.relpath(parent.path, project.root_path)
    if parent_rel == ".":
        href = f"{root_path}index.html"
    else:
        href = f"{root_path}{parent_rel}/index.html"

    return f'''<div class="nav-parent">
        <a href="{href}">← {html.escape(parent.name)}</a>
    </div>'''


def generate_requirement_html(req: Requirement, project: Project, current_doc: Document,
                              hidden_fields: set[str] = None, compact_hidden_fields: set[str] = None) -> str:
    """Generate HTML for a single requirement."""
    hidden_fields = hidden_fields or set()
    compact_hidden_fields = compact_hidden_fields or set()
    content_html = markdown_to_html(req.content)
    content_html = resolve_references_html(content_html, project, current_doc)

    def meta_class(field_name: str) -> str:
        """Return CSS class for metadata item, including compact-hide if needed."""
        if field_name in compact_hidden_fields:
            return 'meta-item compact-hide'
        return 'meta-item'

    # Build metadata display (skip hidden fields)
    meta_parts = []
    if "priority" not in hidden_fields and req.priority is not None:
        meta_parts.append(f'<span class="{meta_class("priority")}">Priority: {req.priority}</span>')
    if "phase" not in hidden_fields and req.phase:
        meta_parts.append(f'<span class="{meta_class("phase")}">Phase: {req.phase}</span>')

    # Show other metadata (skip hidden fields and special fields shown elsewhere)
    special_fields = {"priority", "phase", "req"}
    for key, value in req.metadata.items():
        if key in hidden_fields:
            continue
        if key not in special_fields:
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            meta_parts.append(f'<span class="{meta_class(key)}">{html.escape(key)}: {html.escape(str(value))}</span>')

    meta_html = " ".join(meta_parts) if meta_parts else ""

    # Links
    links_html = ""
    if req.link_to or req.link_from:
        links_parts = []
        if req.link_to:
            to_links = ", ".join(
                f'<a href="#{tid}" class="req-link">{tid}</a>'
                if project.get_requirement(tid) and project.get_requirement(tid).file_path.parent == current_doc.path
                else resolve_references_html(f"[[{tid}]]", project, current_doc)
                for tid in req.link_to
            )
            links_parts.append(f'<div class="links-to">Links to: {to_links}</div>')
        if req.link_from:
            from_links = ", ".join(
                f'<a href="#{fid}" class="req-link">{fid}</a>'
                if project.get_requirement(fid) and project.get_requirement(fid).file_path.parent == current_doc.path
                else resolve_references_html(f"[[{fid}]]", project, current_doc)
                for fid in req.link_from
            )
            links_parts.append(f'<div class="links-from">Linked from: {from_links}</div>')
        links_html = '<div class="req-links">' + "".join(links_parts) + '</div>'

    # Show the "req" field as the main requirement statement
    req_text = req.metadata.get("req")
    req_text_html = ""
    if req_text and "req" not in hidden_fields:
        escaped_req = html.escape(str(req_text))
        # Process [[references]] in the requirement text
        escaped_req = resolve_references_html(escaped_req, project, current_doc)
        req_text_html = f'<div class="req-statement">{escaped_req}</div>'

    # Only show rationale section if there's content
    rationale_html = ""
    if content_html.strip():
        rationale_html = f'''
        <div class="req-rationale">
            <h3 class="rationale-label">Rationale</h3>
            <div class="rationale-content">
                {content_html}
            </div>
        </div>'''

    # Determine heading level based on ID structure
    level = get_indent_level(req.id)
    heading_tag = f"h{level + 1}"  # h2, h3, or h4

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

    # Calculate root path
    rel_path = os.path.relpath(doc.path, project.root_path)
    if rel_path == ".":
        root_path = ""
    else:
        depth = rel_path.count(os.sep) + 1
        root_path = "../" * depth

    nav_tree = generate_nav_tree(project, doc, root_path)

    # Generate requirements HTML
    reqs_html = []
    for req in doc.requirements:
        reqs_html.append(generate_requirement_html(req, project, doc, hidden_fields, compact_hidden_fields))

    # Child documents links
    children_html = ""
    if doc.children:
        children_parts = ["<section class='child-docs'><h2>Child Documents</h2><ul>"]
        for child in doc.children:
            child_rel = os.path.relpath(child.path, doc.path)
            children_parts.append(f'<li><a href="{child_rel}/index.html">{html.escape(child.name)}</a></li>')
        children_parts.append("</ul></section>")
        children_html = "\n".join(children_parts)

    content = f"""
    <header class="doc-header">
        <h1>{html.escape(doc.name)}</h1>
        <div class="doc-controls">
            <button id="compact-toggle" class="compact-toggle">Compact</button>
            <a href="tree.html" class="tree-link">Tree</a>
        </div>
    </header>
    <section class="requirements">
        {"".join(reqs_html)}
    </section>
    {children_html}
    """

    # Generate TOC and parent link
    toc = generate_toc(doc)
    parent_link = generate_parent_link(doc, project, root_path)

    return BASE_TEMPLATE.format(
        title=doc.name,
        root_path=root_path,
        nav_tree=nav_tree,
        toc=toc,
        parent_link=parent_link,
        content=content
    )


def generate_tree_page(doc: Document, project: Project) -> str:
    """Generate tree view page showing requirement connections."""
    rel_path = os.path.relpath(doc.path, project.root_path)
    if rel_path == ".":
        root_path = ""
    else:
        depth = rel_path.count(os.sep) + 1
        root_path = "../" * depth

    nav_tree = generate_nav_tree(project, doc, root_path)

    # Build nodes and edges for visualization
    nodes = []
    edges = []

    for req in doc.requirements:
        nodes.append({
            "id": req.id,
            "priority": req.priority,
        })
        for target in req.link_to:
            edges.append({"from": req.id, "to": target})

    # Simple text-based tree view
    tree_html = ['<div class="tree-view">']
    for req in doc.requirements:
        tree_html.append(f'<div class="tree-node" data-id="{html.escape(req.id)}">')
        tree_html.append(f'<span class="node-id">{html.escape(req.id)}</span>')

        if req.link_to:
            tree_html.append('<div class="node-links-to">')
            tree_html.append('<span class="link-label">→</span>')
            for tid in req.link_to:
                target = project.get_requirement(tid)
                if target:
                    tree_html.append(resolve_references_html(f"[[{tid}]]", project, doc))
                else:
                    tree_html.append(f'<span class="req-link-broken">{html.escape(tid)}</span>')
            tree_html.append('</div>')

        if req.link_from:
            tree_html.append('<div class="node-links-from">')
            tree_html.append('<span class="link-label">←</span>')
            for fid in req.link_from:
                tree_html.append(resolve_references_html(f"[[{fid}]]", project, doc))
            tree_html.append('</div>')

        tree_html.append('</div>')
    tree_html.append('</div>')

    content = f"""
    <header class="doc-header">
        <h1>{html.escape(doc.name)} - Tree View</h1>
        <a href="index.html" class="doc-link">Back to Document</a>
    </header>
    {"".join(tree_html)}
    """

    # Generate TOC and parent link
    toc = generate_toc(doc)
    parent_link = generate_parent_link(doc, project, root_path)

    return BASE_TEMPLATE.format(
        title=f"{doc.name} - Tree",
        root_path=root_path,
        nav_tree=nav_tree,
        toc=toc,
        parent_link=parent_link,
        content=content
    )


def generate_website(project: Project, output_path: Path):
    """Generate complete static website."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Copy static assets (including subdirectories like vendor)
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
    db_path = output_path / "requirements.db"
    generate_sqlite_db(project, db_path)

    # Build config for search page
    hidden_fields = project.get_hidden_fields()
    compact_hidden_fields = project.get_compact_hidden_fields()

    # Build template fields config
    template_fields = {}
    for key, value in project.template.items():
        if isinstance(value, dict):
            template_fields[key] = {
                "show-search": value.get("show-search", True),
            }
        else:
            # Legacy format
            template_fields[key] = {"show-search": True}

    config = {
        "hiddenColumns": list(hidden_fields),
        "templateFields": template_fields,
    }

    # Generate search page
    nav_tree = generate_nav_tree(project, root_path="")
    search_html = SEARCH_PAGE_TEMPLATE.format(
        nav_tree=nav_tree,
        config_json=json.dumps(config)
    )
    (output_path / "search.html").write_text(search_html, encoding="utf-8")

    # Generate document pages
    for doc in project.all_documents():
        rel_path = os.path.relpath(doc.path, project.root_path)
        if rel_path == ".":
            doc_output = output_path
        else:
            doc_output = output_path / rel_path
        doc_output.mkdir(parents=True, exist_ok=True)

        # Document page
        doc_html = generate_document_page(doc, project, hidden_fields, compact_hidden_fields)
        (doc_output / "index.html").write_text(doc_html, encoding="utf-8")

        # Tree page
        tree_html = generate_tree_page(doc, project)
        (doc_output / "tree.html").write_text(tree_html, encoding="utf-8")


def generate_sqlite_db(project: Project, output_path: Path):
    """Generate SQLite database for web search."""
    reqs = project.all_requirements()

    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    # Collect all metadata keys from requirements AND template
    all_keys = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())
    # Also include all template fields so columns exist even if unused
    all_keys.update(project.template.keys())
    meta_columns = sorted(all_keys)
    safe_columns = {k: k.replace("-", "_") for k in meta_columns}

    # Create table
    columns_sql = ", ".join(f'"{safe_columns[k]}" TEXT' for k in meta_columns)
    create_sql = f"""
    CREATE TABLE requirements (
        id TEXT PRIMARY KEY,
        content TEXT,
        link_to TEXT,
        link_from TEXT,
        parent TEXT
        {', ' + columns_sql if columns_sql else ''}
    )
    """
    cursor.execute(create_sql)

    # Insert requirements
    for req in reqs:
        parent_path = os.path.relpath(req.file_path.parent, project.root_path)
        values = {
            "id": req.id,
            "content": req.content,
            "link_to": ";".join(req.link_to),
            "link_from": ";".join(req.link_from),
            "parent": parent_path if parent_path != "." else "",
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
