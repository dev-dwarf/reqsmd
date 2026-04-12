"""Core data models and parsing for reqsmd requirements management."""

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Requirement:
    """A single requirement with ID, metadata, and content."""
    id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    file_path: Path = None
    link_to: list[str] = field(default_factory=list)
    link_from: list[str] = field(default_factory=list)

    @property
    def priority(self) -> int | None:
        return self.metadata.get("priority")


@dataclass
class Document:
    """A document containing requirements, corresponds to a folder."""
    name: str
    path: Path
    requirements: list[Requirement] = field(default_factory=list)
    children: list["Document"] = field(default_factory=list)
    parent: "Document" = None

    @property
    def all_requirements(self) -> list[Requirement]:
        """Get all requirements in this document and all descendants."""
        reqs = list(self.requirements)
        for child in self.children:
            reqs.extend(child.all_requirements)
        return reqs


@dataclass
class Project:
    """A complete requirements project with a root document."""
    root: Document
    root_path: Path
    template: dict[str, Any] = field(default_factory=dict)
    _req_index: dict[str, Requirement] = field(default_factory=dict, repr=False)

    def get_requirement(self, req_id: str) -> Requirement | None:
        """Look up a requirement by ID."""
        return self._req_index.get(req_id)

    def all_requirements(self) -> list[Requirement]:
        """Get all requirements in the project."""
        return self.root.all_requirements

    def all_documents(self) -> list[Document]:
        """Get all documents in the project."""
        docs = []
        def collect(doc: Document):
            docs.append(doc)
            for child in doc.children:
                collect(child)
        collect(self.root)
        return docs

    def get_hidden_fields(self) -> set[str]:
        """Get set of field names not shown in search (show-search: false)."""
        hidden = set()
        for key, value in self.template.items():
            if isinstance(value, dict) and not value.get("show-search", True):
                hidden.add(key)
        return hidden

    def get_compact_hidden_fields(self) -> set[str]:
        """Get set of field names not shown in compact view (show-compact: false)."""
        hidden = set()
        for key, value in self.template.items():
            if isinstance(value, dict) and not value.get("show-compact", True):
                hidden.add(key)
        return hidden


def parse_lenient_json(text: str) -> dict[str, Any]:
    """Parse JSON with trailing commas allowed."""
    # Remove trailing commas before ] or }
    cleaned = re.sub(r',\s*([}\]])', r'\1', text)
    return json.loads(cleaned)


def parse_requirement_file(file_path: Path) -> Requirement:
    """Parse a markdown file with JSON frontmatter into a Requirement."""
    content = file_path.read_text(encoding="utf-8")
    req_id = file_path.stem

    # Check if file starts with JSON frontmatter
    if content.lstrip().startswith("{"):
        # Find the end of JSON block (look for } followed by ---)
        lines = content.split("\n")
        json_lines = []
        rest_start = 0
        brace_count = 0
        in_json = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not in_json and stripped.startswith("{"):
                in_json = True

            if in_json:
                json_lines.append(line)
                brace_count += line.count("{") - line.count("}")
                if brace_count == 0:
                    rest_start = i + 1
                    break

        # Skip separator line (---)
        if rest_start < len(lines) and lines[rest_start].strip() == "---":
            rest_start += 1

        json_text = "\n".join(json_lines)
        markdown_content = "\n".join(lines[rest_start:]).strip()

        try:
            metadata = parse_lenient_json(json_text)
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}
        markdown_content = content.strip()

    # Extract references using [[REQID]] syntax
    link_to = extract_references(markdown_content)

    return Requirement(
        id=req_id,
        metadata=metadata,
        content=markdown_content,
        file_path=file_path,
        link_to=link_to,
    )


def extract_references(content: str) -> list[str]:
    """Extract [[REQID]] references from markdown content, skipping code blocks and spans."""
    code_pattern = re.compile(r'```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`]*`')
    non_code = code_pattern.sub('', content)
    matches = re.findall(r'\[\[([^\]]+)\]\]', non_code)
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def sort_key(req_id: str) -> tuple:
    """
    Generate sort key for requirement ordering.

    Splits on dots and sorts numeric parts numerically, alpha parts alphabetically.
    e.g., "REQ-1.1.2" -> ("REQ-1", 1, 2) for proper numeric ordering.
    """
    parts = req_id.replace("-", ".").split(".")
    result = []
    for part in parts:
        # Try to parse as integer for numeric sorting
        try:
            result.append((0, int(part)))
        except ValueError:
            result.append((1, part.lower()))
    return tuple(result)


def load_document(path: Path, parent: Document = None) -> Document:
    """Load a document from a directory, including its requirements and children."""
    name = path.name
    doc = Document(name=name, path=path, parent=parent)

    # Load all .md files in this directory as requirements
    md_files = sorted(path.glob("*.md"), key=lambda p: sort_key(p.stem))
    for md_file in md_files:
        req = parse_requirement_file(md_file)
        doc.requirements.append(req)

    # Load child documents (subdirectories)
    for subdir in sorted(path.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            child_doc = load_document(subdir, parent=doc)
            doc.children.append(child_doc)

    return doc


def load_project(root_path: str | Path) -> Project:
    """Load a complete project from a root directory."""
    root_path = Path(root_path)

    # Load template if it exists
    template_path = root_path / "req-template.json"
    if template_path.exists():
        try:
            template = parse_lenient_json(template_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            template = {}
    else:
        template = {}

    # Load root document
    root_doc = load_document(root_path)

    # Build requirement index
    req_index = {}
    for req in root_doc.all_requirements:
        req_index[req.id] = req

    # Resolve link_from references
    for req in root_doc.all_requirements:
        for target_id in req.link_to:
            target = req_index.get(target_id)
            if target and req.id not in target.link_from:
                target.link_from.append(req.id)

    return Project(
        root=root_doc,
        root_path=root_path,
        template=template,
        _req_index=req_index,
    )


def export_sqlite(project: Project, output_path: Path | str) -> int:
    """Export all requirements to a SQLite database. Returns count of requirements written."""
    output_path = Path(output_path)
    reqs = project.all_requirements()

    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    # Compute verification status for all requirements up front
    hash_fields = get_hash_fields(project)
    stored_hashes = get_stored_hashes(project)

    # Collect metadata keys from requirements AND template so columns exist even if unused
    all_keys: set[str] = set()
    for req in reqs:
        all_keys.update(req.metadata.keys())
    all_keys.update(project.template.keys())
    meta_columns = sorted(all_keys)
    safe_columns = {k: k.replace("-", "_") for k in meta_columns}

    columns_sql = ", ".join(f'"{safe_columns[k]}" TEXT' for k in meta_columns)
    cursor.execute(f"""
        CREATE TABLE requirements (
            id TEXT PRIMARY KEY,
            content TEXT,
            link_to TEXT,
            link_from TEXT,
            parent TEXT,
            verified_status TEXT
            {', ' + columns_sql if columns_sql else ''}
        )
    """)

    cursor.execute("""
        CREATE TABLE links (
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            PRIMARY KEY (source, target),
            FOREIGN KEY (source) REFERENCES requirements(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE template (
            field TEXT PRIMARY KEY,
            show_search INTEGER,
            show_compact INTEGER,
            verified INTEGER
        )
    """)

    for req in reqs:
        parent_path = os.path.relpath(req.file_path.parent, project.root_path)
        status = req_verification_status(req, stored_hashes, hash_fields)
        values: dict[str, Any] = {
            "id": req.id,
            "content": req.content,
            "link_to": ";".join(req.link_to),
            "link_from": ";".join(req.link_from),
            "parent": "" if parent_path == "." else parent_path,
            "verified_status": status,
        }
        for key in meta_columns:
            value = req.metadata.get(key)
            if isinstance(value, list):
                values[safe_columns[key]] = ";".join(str(v) for v in value)
            elif value is not None:
                values[safe_columns[key]] = str(value)
            else:
                values[safe_columns[key]] = None

        cols = ", ".join(f'"{k}"' for k in values)
        placeholders = ", ".join("?" for _ in values)
        cursor.execute(f"INSERT INTO requirements ({cols}) VALUES ({placeholders})", list(values.values()))

        for target_id in req.link_to:
            cursor.execute("INSERT OR IGNORE INTO links (source, target) VALUES (?, ?)",
                           (req.id, target_id))

    for field_name, field_config in project.template.items():
        if not isinstance(field_config, dict):
            continue
        cursor.execute(
            "INSERT INTO template (field, show_search, show_compact, verified) VALUES (?, ?, ?, ?)",
            (
                field_name,
                int(field_config.get("show-search", True)),
                int(field_config.get("show-compact", True)),
                int(field_config.get("verified", False)),
            ),
        )

    conn.commit()
    conn.close()
    return len(reqs)


_VERIFY_SYSTEM_FIELDS = {"verified-hash", "verified-by"}


def get_stored_hashes(project: Project) -> dict[str, str]:
    """Build a snapshot of stored verification hashes for all requirements."""
    return {r.id: r.metadata.get("verified-hash", "") for r in project.all_requirements()}


def get_hash_fields(project: Project) -> list[str]:
    """Return sorted list of metadata fields (beyond 'req') to include in requirement hash.

    'req' is always included in the hash regardless of the 'verified' flag, so it is excluded
    here to avoid double-counting.
    """
    return sorted(
        key for key, value in project.template.items()
        if isinstance(value, dict) and value.get("verified", False)
        and key not in _VERIFY_SYSTEM_FIELDS
        and key != "req"
    )


def compute_req_hash(req: Requirement, stored_hashes: dict[str, str],
                     hash_fields: list[str]) -> str:
    """Compute a deterministic SHA-256 hash for a requirement.

    Always includes the 'req' field. Also includes fields listed in hash_fields
    and the stored verification hashes of each linked-to requirement.
    """
    parts = [f"req:{req.metadata.get('req') or ''}"]

    for field_name in hash_fields:
        value = req.metadata.get(field_name)
        if value is None:
            value = ""
        elif isinstance(value, list):
            value = ";".join(str(v) for v in value)
        else:
            value = str(value)
        parts.append(f"{field_name}:{value}")

    for dep_id in sorted(req.link_to):
        parts.append(f"dep:{dep_id}:{stored_hashes.get(dep_id, '')}")

    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def req_verification_status(req: Requirement, stored_hashes: dict[str, str],
                             hash_fields: list[str]) -> str:
    """Return 'OK', 'FAIL', or 'UNVERIFIED' for a requirement."""
    stored_hash = stored_hashes.get(req.id, "")
    if not stored_hash:
        return "UNVERIFIED"
    if compute_req_hash(req, stored_hashes, hash_fields) == stored_hash:
        return "OK"
    return "FAIL"


def compute_cascade_failures(
    project: Project, stored_hashes: dict[str, str], hash_fields: list[str]
) -> tuple[list[tuple[str, str]], list[str]]:
    """Compute direct failures and the downstream requirements that will cascade.

    Returns (direct, cascade) where:
    - direct: list of (req_id, status) for requirements that currently FAIL or UNVERIFIED
    - cascade: list of req_ids that currently pass but will need re-verification once
               their failing dependencies are re-verified
    """
    direct: list[tuple[str, str]] = []
    failing_ids: set[str] = set()
    for req in project.all_requirements():
        status = req_verification_status(req, stored_hashes, hash_fields)
        if status != "OK":
            direct.append((req.id, status))
            failing_ids.add(req.id)

    cascade: list[str] = []
    cascade_ids: set[str] = set()
    queue = list(failing_ids)
    while queue:
        req = project.get_requirement(queue.pop())
        if req is None:
            continue
        for dependent_id in req.link_from:
            if dependent_id not in failing_ids and dependent_id not in cascade_ids:
                cascade_ids.add(dependent_id)
                cascade.append(dependent_id)
                queue.append(dependent_id)

    return direct, cascade


def verify_requirement(req: Requirement, project: Project, user: str,
                        hash_fields: list[str], stored_hashes: dict[str, str],
                        force: bool = False, on_verify=None,
                        _visiting: set = None, _verified: set = None) -> bool:
    """Recursively verify a requirement and write updated metadata to disk.

    Returns False if a dependency is unverified and force is not set.
    Raises ValueError on circular dependencies.
    Updates stored_hashes in place as requirements are verified.
    on_verify, if provided, is called as on_verify(req_id, user, hash) after each verification.
    """
    if _visiting is None:
        _visiting = set()
    if _verified is None:
        _verified = set()

    if req.id in _verified and not force:
        return True
    if req.id in _visiting:
        path = " -> ".join(_visiting) + f" -> {req.id}"
        raise ValueError(f"Circular dependency: {path}")

    _visiting.add(req.id)

    unverified_deps = [d for d in req.link_to if not stored_hashes.get(d)]
    if unverified_deps and not force:
        _visiting.discard(req.id)
        return False

    for dep_id in req.link_to:
        dep = project.get_requirement(dep_id)
        if dep is None:
            continue  # broken link
        if not force and stored_hashes.get(dep_id):
            continue  # already verified and not forcing re-verify
        if not verify_requirement(dep, project, user, hash_fields, stored_hashes,
                                  force=force, on_verify=on_verify,
                                  _visiting=_visiting, _verified=_verified):
            _visiting.discard(req.id)
            return False

    req_hash = compute_req_hash(req, stored_hashes, hash_fields)
    req.metadata["verified-hash"] = req_hash
    req.metadata["verified-by"] = user
    write_requirement_metadata(req)
    stored_hashes[req.id] = req_hash

    _visiting.discard(req.id)
    _verified.add(req.id)
    if on_verify:
        on_verify(req.id, user, req_hash)
    return True


def write_requirement_metadata(req: Requirement) -> None:
    """Rewrite the JSON frontmatter of a requirement file, preserving markdown content."""
    if not req.file_path:
        raise ValueError(f"Requirement {req.id} has no file path")
    lines = ["{"]
    for key, value in req.metadata.items():
        lines.append(f'  "{key}": {json.dumps(value)},')
    lines.append("}")
    body = "\n".join(lines) + "\n---\n"
    if req.content:
        body += req.content + "\n"
    req.file_path.write_text(body, encoding="utf-8")


def resolve_references(content: str, project: Project, current_doc_path: Path = None) -> str:
    """
    Resolve [[REQID]] references in content to HTML links.

    Args:
        content: Markdown content with [[REQID]] references
        project: The project to look up requirements in
        current_doc_path: Path of current document for relative links

    Returns:
        Content with references replaced by HTML links
    """
    def replace_ref(match):
        req_id = match.group(1)
        req = project.get_requirement(req_id)
        if req:
            # Calculate relative path to requirement's document
            doc_path = req.file_path.parent
            rel_path = os.path.relpath(doc_path, project.root_path)
            if rel_path == ".":
                html_path = f"index.html#{req_id}"
            else:
                html_path = f"{rel_path}/index.html#{req_id}"
            return f'<a href="{html_path}" class="req-link">{req_id}</a>'
        else:
            return f'<span class="req-link-broken">{req_id}</span>'

    pattern = r'\[\[([^\]]+)\]\]'
    return re.sub(pattern, replace_ref, content)
