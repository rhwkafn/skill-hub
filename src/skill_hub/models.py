"""Core data models for skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillMeta:
    """Lightweight metadata — this is what gets indexed and stored in the hub."""
    name: str
    registry: str  # which registry it came from
    description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    use_when: str = ""  # one-line trigger condition
    source_url: str = ""  # remote URL or local path
    local_path: str | None = None  # if synced locally
    repo_path: str = ""  # relative path within the repo (e.g. "skills/tdd/SKILL.md")

    def to_index_entry(self) -> dict:
        """Minimal dict for the searchable index."""
        return {
            "name": self.name,
            "registry": self.registry,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "use_when": self.use_when,
            "source_url": self.source_url,
            "repo_path": self.repo_path,
        }

    def matches(self, query: str) -> float:
        """Simple relevance score against a query string. Returns 0.0-1.0."""
        q = query.lower()
        fields = [
            (self.name, 0.4),
            (self.description, 0.3),
            (self.use_when, 0.2),
            (" ".join(self.tags), 0.1),
        ]
        score = 0.0
        for text, weight in fields:
            if q in text.lower():
                score += weight
            # partial word match
            for word in q.split():
                if word and word in text.lower():
                    score += weight * 0.3
        return min(score, 1.0)
