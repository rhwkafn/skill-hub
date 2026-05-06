"""Keyword router — fast, zero-dependency skill matching."""

from __future__ import annotations

from .base import SkillRouter, RouteOutput, RouteResult
from ..models import SkillMeta, SkillMode


class KeywordRouter(SkillRouter):
    """Match skills by keyword overlap. Fastest, no dependencies."""

    name = "keyword"

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 20) -> RouteOutput:
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
        candidates = scored[:top_k]

        global_skills = [r for r in candidates if r.skill.mode == SkillMode.GLOBAL]

        return RouteOutput(
            candidates=candidates,
            global_skills=global_skills,
        )
