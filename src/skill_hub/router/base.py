"""Base class for skill routers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import SkillMeta


@dataclass
class RouteResult:
    """A skill routing result."""
    skill: SkillMeta
    score: float
    reason: str = ""  # why this skill was matched


class SkillRouter(ABC):
    """Abstract base for skill routing strategies.

    A router takes a user query and returns ranked skill matches.
    Different implementations trade off speed, accuracy, and cost.
    """

    name: str

    @abstractmethod
    def route(self, query: str, skills: list[SkillMeta], top_k: int = 10) -> list[RouteResult]:
        """Route a user query to matching skills.

        Args:
            query: Natural language user input
            skills: All available skills to search through
            top_k: Maximum results to return

        Returns:
            List of RouteResult sorted by relevance (highest first).
        """
        ...

    def batch_route(self, queries: list[str], skills: list[SkillMeta], top_k: int = 10) -> list[list[RouteResult]]:
        """Route multiple queries. Default: call route() for each."""
        return [self.route(q, skills, top_k) for q in queries]
