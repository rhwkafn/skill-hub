"""Keyword router — fast, zero-dependency skill matching."""

from __future__ import annotations

from .base import SkillRouter, RouteResult
from ..models import SkillMeta


class KeywordRouter(SkillRouter):
    """Match skills by keyword overlap. Fastest, no dependencies."""

    name = "keyword"

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 10) -> list[RouteResult]:
        scored = []
        for skill in skills:
            score = skill.matches(query)
            if score > 0:
                scored.append(RouteResult(
                    skill=skill,
                    score=score,
                    reason=f"keyword match (score={score:.2f})",
                ))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
