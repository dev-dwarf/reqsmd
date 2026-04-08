"""Core data models and parsing for MDOORS requirements management."""

import json
import os
import re
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

    @property
    def phase(self) -> str | None:
        return self.metadata.get("phase")


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

    def get_template_defaults(self) -> dict[str, Any]:
        """Get default values from template (new format with 'default' key)."""
        defaults = {}
        for key, value in self.template.items():
            if isinstance(value, dict) and "default" in value:
                defaults[key] = value["default"]
            else:
                # Legacy format: value is the default directly
                defaults[key] = value
        return defaults

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
