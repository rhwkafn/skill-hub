"""Base class for skill sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import SkillMeta


class SkillSource(ABC):
    """A source that can enumerate and retrieve skills."""

    name: str

    @abstractmethod
    async def list_skills(self, skip_names: set[str] | None = None) -> list[SkillMeta]:
        """Discover all available skills from this source.

        Args:
            skip_names: Set of skill names to skip (already in index).
                        Source should avoid expensive operations for these.
        """
        ...

    @abstractmethod
    async def fetch_skill(self, skill: SkillMeta) -> str:
        """Fetch the full SKILL.md content for a skill."""
        ...
