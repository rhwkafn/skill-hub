"""Local filesystem skill source."""

from __future__ import annotations

import json
from pathlib import Path

from .base import SkillSource
from ..models import SkillMeta


class LocalSource(SkillSource):
    """Discover and fetch skills from a local directory."""

    def __init__(self, path: str, skill_glob: str = "*/SKILL.md",
                 manifest: str | None = None, name: str = "local"):
        self.name = name
        self.base_path = Path(path)
        self.skill_glob = skill_glob
        self.manifest_path = Path(manifest) if manifest else None

    async def list_skills(self) -> list[SkillMeta]:
        """Discover skills by glob or manifest."""
        # If a manifest exists, prefer it
        if self.manifest_path and self.manifest_path.exists():
            return self._from_manifest()

        # Otherwise glob for SKILL.md files
        skills = []
        for skill_file in self.base_path.glob(self.skill_glob):
            skill_dir = skill_file.parent
            content = skill_file.read_text(encoding="utf-8")
            description, use_when, tags, category = _parse_skill_frontmatter(content)
            skill = SkillMeta(
                name=skill_dir.name,
                registry=self.name,
                description=description,
                category=category,
                tags=tags,
                use_when=use_when,
                source_url=str(skill_file),
                local_path=str(skill_dir),
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
    """Quick frontmatter parse for local SKILL.md files."""
    import re
    description = ""
    use_when = ""
    tags = []
    category = ""

    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.split("\n"):
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("tags:"):
                tag_str = line.split(":", 1)[1].strip()
                tags = [t.strip().strip("- ") for t in tag_str.split(",")]

    uw_match = re.search(r"use[_\s]when:\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if uw_match:
        use_when = uw_match.group(1).strip()

    return description, use_when, tags, category
