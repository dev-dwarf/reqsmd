"""Web export generator for MDOORS requirements management."""

import html
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

from .core import Document, Project, Requirement, sort_key


# HTML Templates

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - MDOORS</title>
    <link rel="stylesheet" href="{root_path}style.css">
</head>
<body>
    <nav class="sidebar">
        <div class="nav-header">
            <a href="{root_path}index.html">MDOORS</a>
        </div>
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/sql-wasm.js"></script>
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
        <h1>Search Requirements</h1>

        <div class="search-controls">
            <div class="search-box">
                <input type="text" id="search-input" placeholder="Search requirements...">
                <button id="search-btn">Search</button>
            </div>

            <div class="filter-box">
                <h3>Filters</h3>
                <div id="filters-container"></div>
            </div>

            <div class="column-box">
                <h3>Columns</h3>
                <div id="columns-container"></div>
            </div>

            <div class="sql-box">
                <h3>SQL Query</h3>
                <textarea id="sql-input" placeholder="SELECT * FROM requirements WHERE priority = 1"></textarea>
                <button id="sql-btn">Run SQL</button>
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


def markdown_to_html(content: str) -> str:
    """
    Simple markdown to HTML converter.

    Supports:
    - Paragraphs
    - Headers (#, ##, ###)
    - Bold (**text**)
    - Italic (*text*)
    - Code (`code`)
    - Links [text](url)
    - Lists (- item)
    """
    lines = content.split("\n")
    html_parts = []
    in_list = False
    paragraph_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(paragraph_lines)
            text = convert_inline(text)
            html_parts.append(f"<p>{text}</p>")
            paragraph_lines = []

    def convert_inline(text: str) -> str:
        # Code (must be before bold/italic to avoid conflicts)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # Bold
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        # Links [text](url) but not [[ref]]
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        stripped = line.strip()

        # Empty line ends paragraph
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            flush_paragraph()
            continue

        # Headers
        if stripped.startswith("###"):
            flush_paragraph()
            text = convert_inline(stripped[3:].strip())
            html_parts.append(f"<h3>{text}</h3>")
            continue
        if stripped.startswith("##"):
            flush_paragraph()
            text = convert_inline(stripped[2:].strip())
            html_parts.append(f"<h2>{text}</h2>")
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            text = convert_inline(stripped[1:].strip())
            html_parts.append(f"<h1>{text}</h1>")
            continue

        # List items
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            text = convert_inline(stripped[2:])
            html_parts.append(f"<li>{text}</li>")
            continue

        # Regular text - accumulate for paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        paragraph_lines.append(stripped)

    # Flush remaining content
    if in_list:
        html_parts.append("</ul>")
    flush_paragraph()

    return "\n".join(html_parts)


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


def generate_requirement_html(req: Requirement, project: Project, current_doc: Document, hidden_fields: set[str] = None) -> str:
    """Generate HTML for a single requirement."""
    hidden_fields = hidden_fields or set()
    content_html = markdown_to_html(req.content)
    content_html = resolve_references_html(content_html, project, current_doc)

    # Build metadata display (skip hidden fields)
    meta_parts = []
    if "priority" not in hidden_fields and req.priority is not None:
        meta_parts.append(f'<span class="meta-item">Priority: {req.priority}</span>')
    if "phase" not in hidden_fields and req.phase:
        meta_parts.append(f'<span class="meta-item">Phase: {req.phase}</span>')

    # Show other metadata (skip hidden fields)
    for key, value in req.metadata.items():
        if key in hidden_fields:
            continue
        if key not in ("priority", "phase"):
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            meta_parts.append(f'<span class="meta-item">{html.escape(key)}: {html.escape(str(value))}</span>')

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

    return f"""
    <article class="requirement" id="{html.escape(req.id)}">
        <header class="req-header">
            <h2><a href="#{html.escape(req.id)}">{html.escape(req.id)}</a></h2>
            <div class="req-meta">{meta_html}</div>
        </header>
        <div class="req-content">
            {content_html}
        </div>
        {links_html}
    </article>
    """


def generate_document_page(doc: Document, project: Project, hidden_fields: set[str] = None) -> str:
    """Generate HTML page for a document."""
    hidden_fields = hidden_fields or set()

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
        reqs_html.append(generate_requirement_html(req, project, doc, hidden_fields))

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
        <a href="tree.html" class="tree-link">View Tree</a>
    </header>
    <section class="requirements">
        {"".join(reqs_html)}
    </section>
    {children_html}
    """

    return BASE_TEMPLATE.format(
        title=doc.name,
        root_path=root_path,
        nav_tree=nav_tree,
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

    return BASE_TEMPLATE.format(
        title=f"{doc.name} - Tree",
        root_path=root_path,
        nav_tree=nav_tree,
        content=content
    )


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

    # Generate SQLite database for search
    db_path = output_path / "requirements.db"
    generate_sqlite_db(project, db_path)

    # Build config for search page
    hidden_fields = project.get_hidden_fields()

    # Build template fields config
    template_fields = {}
    for key, value in project.template.items():
        if isinstance(value, dict):
            template_fields[key] = {
                "hidden": value.get("hidden", False),
            }
        else:
            # Legacy format
            template_fields[key] = {"hidden": False}

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
        doc_html = generate_document_page(doc, project, hidden_fields)
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

    # Collect all metadata keys
    all_keys = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())
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
