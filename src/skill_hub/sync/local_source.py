"""Local filesystem skill source."""

from __future__ import annotations

import json
from pathlib import Path

from .base import SkillSource
from .github_source import _auto_extract_tags, _infer_domain, _infer_execution_mode, _infer_phase
from ..models import SkillMeta


class LocalSource(SkillSource):
    """Discover and fetch skills from a local directory."""

    def __init__(self, path: str, skill_glob: str = "*/SKILL.md",
                 manifest: str | None = None, name: str = "local"):
        self.name = name
        self.base_path = Path(path)
        self.skill_glob = skill_glob
        self.manifest_path = Path(manifest) if manifest else None

    async def list_skills(self, skip_names: set[str] | None = None) -> list[SkillMeta]:
        """Discover skills by glob or manifest."""
        skip = skip_names or set()

        # If a manifest exists, prefer it
        if self.manifest_path and self.manifest_path.exists():
            return self._from_manifest()

        # Otherwise glob for SKILL.md files
        skills = []
        for skill_file in self.base_path.glob(self.skill_glob):
            skill_dir = skill_file.parent
            if skill_dir.name in skip:
                continue
            content = skill_file.read_text(encoding="utf-8")
            description, use_when, tags, category = _parse_skill_frontmatter(content)
            if not tags:
                tags = _auto_extract_tags(content, description)
            skill = SkillMeta(
                name=skill_dir.name,
                registry=self.name,
                description=description,
                category=category,
                tags=tags,
                use_when=use_when,
                source_url=str(skill_file),
                local_path=str(skill_dir),
                domain=_infer_domain(content, description, tags),
                phase=_infer_phase(content, description),
                execution_mode=_infer_execution_mode(content, description),
            )
            skill.build_decision_card(content)
            skills.append(skill)
        return skills

    def _from_manifest(self) -> list[SkillMeta]:
        """Load from a manifest JSON (like codex-skills-workbench's skills.json)."""
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        skills = []
        for entry in data:
            skill_dir = self.base_path / "skills" / entry.get("skillDir", entry.get("skillName", ""))
            skill = SkillMeta(
                name=entry.get("skillName", entry.get("name", "")),
                registry=self.name,
                description=entry.get("description", entry.get("useWhen", "")),
                category=entry.get("category", ""),
                tags=[],
                use_when=entry.get("useWhen", ""),
                source_url=str(skill_dir),
                local_path=str(skill_dir) if skill_dir.exists() else None,
            )
            # Build decision card from description if available
            skill.build_decision_card()
            skills.append(skill)
        return skills

    async def fetch_skill(self, skill: SkillMeta) -> str:
        """Read SKILL.md from local path."""
        if skill.local_path:
            skill_md = Path(skill.local_path) / "SKILL.md"
            if skill_md.exists():
                return skill_md.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Skill not found: {skill.name}")


def _parse_skill_frontmatter(content: str) -> tuple[str, str, list[str], str]:
    """Parse frontmatter from SKILL.md files.

    Handles: BOM prefix, multiline description (|, >, or indented continuation).
    """
    import re

    description = ""
    use_when = ""
    tags = []
    category = ""

    # Strip BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]

    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return description, use_when, tags, category

    fm = fm_match.group(1)
    lines = fm.split("\n")

    current_key = None
    current_list = []

    for line in lines:
        stripped = line.strip()

        # Top-level key: value
        key_match = re.match(r"^(\w[\w-]*):\s*(.*)", stripped)
        if key_match:
            # Flush previous list field
            if current_key and current_list:
                if current_key == "tags":
                    tags = current_list
                current_list = []
                current_key = None

            key = key_match.group(1)
            value = key_match.group(2).strip()

            if key == "description":
                if value in ("|", ">", "|+", "|-", ">+", ">-"):
                    # Block scalar — collect continuation lines
                    current_key = "description"
                    current_list = []
                elif value:
                    description = value.strip("'\"")
            elif key == "tags":
                if not value:
                    current_key = "tags"
                    current_list = []
                else:
                    tags = [v.strip().strip("- ") for v in value.split(",")]
            continue

        # Continuation lines for multiline fields
        if current_key and (line.startswith("  ") or stripped.startswith("- ")):
            if current_key == "description":
                current_list.append(stripped)
            elif current_key == "tags" and stripped.startswith("- "):
                current_list.append(stripped[2:].strip().strip("'\""))
            continue

    # Flush remaining
    if current_key == "description" and current_list:
        description = " ".join(v for v in current_list if v).strip()
    elif current_key == "tags" and current_list:
        tags = current_list

    # Fallback: first paragraph if no description
    if not description:
        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        body = re.sub(r"^#.*\n", "", body).strip()
        for para in body.split("\n\n"):
            para = para.strip()
            if para and len(para) > 15 and not para.startswith("|") and not para.startswith("-"):
                description = para[:200]
                break

    uw_match = re.search(r"use[_\s]when:\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if uw_match:
        use_when = uw_match.group(1).strip()

    return description, use_when, tags, category
