"""Base class for skill routers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..models import SkillMeta


@dataclass
class RouteResult:
    """A skill routing result."""
    skill: SkillMeta
    score: float
    reason: str = ""


@dataclass
class RouteOutput:
    """Full routing output — not just top picks, but a structured handoff to the main model.

    The router's job is RECALL (find candidates), not DECISION (pick what to use).
    The main model sees the full context and makes the final call.
    """
    candidates: list[RouteResult]          # all candidates above threshold, sorted by score
    global_skills: list[RouteResult]       # session-wide skills that should always be active
    categorized: dict[str, list[RouteResult]] = field(default_factory=dict)  # by category
    catalog_text: str = ""                 # compact catalog of candidates for the main model

    def to_prompt(self) -> str:
        """Generate a structured prompt section for the main model.

        This gives the main model enough context to make informed decisions
        about which skills to load and how to combine them.
        """
        lines = ["## Available Skills (Router Results)\n"]
        lines.append(f"Found {len(self.candidates)} relevant skills for this task.\n")

        if self.global_skills:
            lines.append("### Global Skills (activate for entire session)")
            for r in self.global_skills:
                hooks_tag = " [has hooks]" if r.skill.has_hooks else ""
                lines.append(f"- **{r.skill.name}**{hooks_tag}: {r.skill.description[:100]}")
                if r.skill.triggers:
                    lines.append(f"  Triggers: {', '.join(r.skill.triggers[:3])}")
            lines.append("")

        # Group remaining by mode
        on_demand = [r for r in self.candidates if r.skill.mode.value == "on_demand"]
        compose = [r for r in self.candidates if r.skill.mode.value == "compose"]

        if on_demand:
            lines.append("### Task Skills (load as needed)")
            for r in on_demand[:10]:
                lines.append(f"- **{r.skill.name}** (score={r.score:.2f}): {r.skill.description[:100]}")
                if r.skill.triggers:
                    lines.append(f"  Triggers: {', '.join(r.skill.triggers[:3])}")
            lines.append("")

        if compose:
            lines.append("### Composable Skills (combine with others)")
            for r in compose[:5]:
                lines.append(f"- **{r.skill.name}** (score={r.score:.2f}): {r.skill.description[:100]}")
            lines.append("")

        lines.append("To use a skill, call `load_skill(name)` to get full instructions.")
        return "\n".join(lines)


class SkillRouter(ABC):
    """Abstract base for skill routing strategies.

    A router takes a user query and returns ranked skill matches.
    Its job is RECALL — find all potentially relevant skills.
    The main model does DECISION — pick which to actually use.
    """

    name: str

    @abstractmethod
    def route(self, query: str, skills: list[SkillMeta], top_k: int = 20) -> RouteOutput:
        """Route a user query to matching skills.

        Args:
            query: Natural language user input (full context, not compressed)
            skills: All available skills
            top_k: Maximum candidates to return

        Returns:
            RouteOutput with candidates, global skills, and a prompt for the main model.
        """
        ...
