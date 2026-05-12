"""Shared utilities for skill-hub."""

from __future__ import annotations

import json
import re
from pathlib import Path

# Directories that indicate a skill needs its full repo (not just SKILL.md)
RESOURCE_DIRS = {"scripts", "references", "assets", "templates", "tests", "agents"}


def _find_resource_refs(content: str) -> set[str]:
    """Extract relative paths to resource directories from SKILL.md content.

    Matches:
    - Backtick-quoted paths: `` `scripts/docx/analyze_docx.py` ``
    - Command paths: `` python scripts/workspace/init.py ``
    """
    refs: set[str] = set()

    # Match backtick-quoted paths
    for m in re.finditer(r'`(([^/`]+)/[^`]+)`', content):
        top_dir = m.group(2).strip()
        if top_dir in RESOURCE_DIRS:
            refs.add(m.group(1))

    # Match command paths
    for m in re.finditer(r'(?:^|\s)(?:python|node)\s+([\w./-]+)', content):
        path = m.group(1)
        top_dir = path.split("/")[0]
        if top_dir in RESOURCE_DIRS:
            refs.add(path)

    return refs


def build_resource_manifest(skill_dir: Path, content: str) -> dict:
    """Scan SKILL.md for referenced local files and build a resource manifest.

    Returns a dict mapping relative paths to their absolute paths and existence status.
    The agent uses this to Read/Bash referenced files without guessing paths.
    """
    refs = _find_resource_refs(content)

    manifest = {}
    for ref in sorted(refs):
        full_path = skill_dir / ref
        manifest[ref] = {
            "exists": full_path.exists(),
            "absolute": str(full_path),
        }
    return manifest


def prepend_resource_manifest(
    content: str,
    skill_dir: Path,
    pip_deps: list[str],
) -> str:
    """Prepend a resource manifest header to SKILL.md content.

    The header is HTML-comment-style so it doesn't interfere with
    frontmatter parsing or markdown rendering.
    """
    manifest = build_resource_manifest(skill_dir, content)
    header = (
        f"<!-- skill-hub resource manifest -->\n"
        f"<!-- local_path: {skill_dir} -->\n"
        f"<!-- pip_deps: {json.dumps(pip_deps)} -->\n"
        f"<!-- resources: {json.dumps(manifest)} -->\n\n"
    )
    return header + content
