"""Skill Registry — the high-level API for agents to discover and load skills.

This is what agents actually interact with. It provides:
1. search(query) — find relevant skills by natural language
2. load(name) — fetch the full SKILL.md content for a skill
3. summary() — get a compact overview of all available skills

The key insight: agents only need the index to decide WHAT to load.
They load the full skill content only when they've decided WHICH one they need.
"""

from __future__ import annotations

from pathlib import Path

from ..indexer import SkillIndex
from ..models import SkillMeta
from ..sync.base import SkillSource


class SkillRegistry:
    """High-level API for agents to discover and use skills."""

    def __init__(self, index: SkillIndex, sources: list[SkillSource] | None = None):
        self.index = index
        self._sources = {s.name: s for s in (sources or [])}
        self._loaded: dict[str, str] = {}  # cache of loaded skill contents

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for skills matching a query. Returns lightweight metadata."""
        results = self.index.search(query, top_k)
        return [
            {
                "name": skill.name,
                "registry": skill.registry,
                "score": round(score, 3),
                "use_when": skill.use_when,
                "description": skill.description[:150],
                "category": skill.category,
                "tags": skill.tags,
            }
            for skill, score in results
        ]

    async def load(self, name: str) -> str | None:
        """Load the full SKILL.md content for a skill. Caches the result."""
        if name in self._loaded:
            return self._loaded[name]

        skill = self.index.get(name)
        if not skill:
            return None

        # Try local path first
        if skill.local_path:
            skill_md = Path(skill.local_path) / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                self._loaded[name] = content
                return content

        # Try fetching from source
        source = self._sources.get(skill.registry)
        if source:
            content = await source.fetch_skill(skill)
            self._loaded[name] = content
            return content

        return None

    def compact_prompt(self, max_skills: int = 50) -> str:
        """Generate a compact skill catalog for injection into agent system prompts.

        This is the key optimization: instead of loading all SKILL.md files,
        we give the agent a one-line-per-skill summary it can search through.
        """
        lines = ["# Available Skills", ""]
        lines.append("Search these skills by name or use-when description.")
        lines.append("To use a skill, call `load_skill(name)` to get the full instructions.\n")

        cats = self.index.list_by_category()
        for cat, skills in sorted(cats.items()):
            lines.append(f"## {cat}")
            for s in skills[:max_skills]:
                trigger = s.use_when or s.description[:80]
                lines.append(f"- **{s.name}**: {trigger}")
            lines.append("")

        return "\n".join(lines)

    def stats(self) -> dict:
        """Return index statistics."""
        return {
            "total_skills": len(self.index.skills),
            "categories": len(self.index.list_by_category()),
            "registries": len(self.index.list_by_registry()),
            "loaded_cache": len(self._loaded),
        }
