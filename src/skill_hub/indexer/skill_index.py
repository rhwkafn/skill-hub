"""The Skill Index — a lightweight, searchable catalog of all available skills.

This is the core idea: instead of loading every skill's full content into context,
we maintain a compact index that agents can search. Only when an agent decides
a skill is relevant do we load the full SKILL.md.

Think of it as RAG for agent capabilities.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import SkillMeta


class SkillIndex:
    """A lightweight, searchable index of all registered skills."""

    def __init__(self):
        self.skills: dict[str, SkillMeta] = {}

    def add(self, skill: SkillMeta):
        self.skills[skill.name] = skill

    def search(self, query: str, top_k: int = 5) -> list[tuple[SkillMeta, float]]:
        """Search skills by relevance. Returns top_k results sorted by score."""
        scored = []
        for skill in self.skills.values():
            score = skill.matches(query)
            if score > 0:
                scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def list_by_category(self) -> dict[str, list[SkillMeta]]:
        """Group skills by category."""
        cats: dict[str, list[SkillMeta]] = {}
        for s in self.skills.values():
            cats.setdefault(s.category or "uncategorized", []).append(s)
        return cats

    def list_by_registry(self) -> dict[str, list[SkillMeta]]:
        """Group skills by source registry."""
        regs: dict[str, list[SkillMeta]] = {}
        for s in self.skills.values():
            regs.setdefault(s.registry, []).append(s)
        return regs

    def get(self, name: str) -> SkillMeta | None:
        return self.skills.get(name)

    def save(self, path: str | Path):
        """Serialize the index to a JSON file for fast reload."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.to_index_entry() for s in self.skills.values()]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> SkillIndex:
        """Load index from a previously saved JSON file."""
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        idx = cls()
        for entry in data:
            # Handle missing fields for backwards compatibility
            entry.setdefault("source_url", "")
            entry.setdefault("repo_path", "")
            entry.setdefault("mode", "on_demand")
            entry.setdefault("tools_required", [])
            entry.setdefault("has_hooks", False)
            entry.setdefault("triggers", [])
            entry.setdefault("decision_card", "")
            entry.setdefault("output_formats", [])
            entry.setdefault("input_types", [])
            entry.setdefault("domain", "")
            # Convert mode string to enum
            from ..models import SkillMode
            entry["mode"] = SkillMode(entry["mode"])
            idx.add(SkillMeta(**entry))
        return idx

    def summary(self) -> str:
        cats = self.list_by_category()
        lines = [f"Skill Index: {len(self.skills)} skills across {len(cats)} categories"]
        for cat, skills in sorted(cats.items()):
            lines.append(f"  [{cat}] {len(skills)} skills")
            for s in skills:
                lines.append(f"    - {s.name}: {s.use_when or s.description[:80]}")
        return "\n".join(lines)
