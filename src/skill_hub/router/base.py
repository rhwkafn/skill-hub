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

    def _format_skill(self, r: RouteResult, show_score: bool = False) -> str:
        """Format a single skill entry for the prompt."""
        s = r.skill
        hooks_tag = " [has hooks]" if s.has_hooks else ""
        score_tag = f" (score={r.score:.2f})" if show_score else ""
        path_tag = f" `{s.repo_path}`" if s.repo_path else ""
        line = f"- **{s.name}**{hooks_tag}{score_tag}{path_tag}: {s.description}"
        if s.triggers:
            line += f"\n  Triggers: {', '.join(s.triggers[:3])}"
        return line

    def to_prompt(self) -> str:
        """Generate a structured prompt section for the main model."""
        lines = []

        # Top recommendation — clear action for the main model
        if self.candidates:
            top = self.candidates[0]
            lines.append(f"## Recommended: `{top.skill.name}` (score: {top.score:.2f})")
            lines.append(f"{top.skill.description[:200]}")
            lines.append(f"→ Call `load_skill('{top.skill.name}')` to get instructions.\n")

        lines.append(f"## All Candidates ({len(self.candidates)} found)\n")

        if self.global_skills:
            lines.append("### Global Skills (activate for entire session)")
            for r in self.global_skills:
                lines.append(self._format_skill(r))
            lines.append("")

        on_demand = [r for r in self.candidates if r.skill.mode.value == "on_demand"]
        compose = [r for r in self.candidates if r.skill.mode.value == "compose"]

        if on_demand:
            lines.append("### Task Skills (load as needed)")
            for r in on_demand[:10]:
                lines.append(self._format_skill(r, show_score=True))
                if r.skill.triggers:
                    lines.append(f"  Triggers: {', '.join(r.skill.triggers[:3])}")
            lines.append("")

        if compose:
            lines.append("### Composable Skills (combine with others)")
            for r in compose[:5]:
                lines.append(self._format_skill(r, show_score=True))
            lines.append("")

        # Phase-based grouping for planning visibility
        non_global = [r for r in self.candidates if r.skill.mode.value != "global"]
        if len(non_global) >= 2:
            from collections import defaultdict
            phase_groups = defaultdict(list)
            for r in non_global:
                phase_groups[r.skill.phase.value].append(r)

            phase_order = ["define", "plan", "build", "verify", "review", "ship", "execute"]
            phase_labels = {
                "define": "Define (requirements, specs)",
                "plan": "Plan (architecture, breakdown)",
                "build": "Build (implementation, coding)",
                "verify": "Verify (testing, debugging)",
                "review": "Review (quality, audit)",
                "ship": "Ship (deploy, release, docs)",
                "execute": "Execute (general-purpose)",
            }
            lines.append("### Skills by Workflow Phase\n")
            for phase in phase_order:
                if phase in phase_groups:
                    group = phase_groups[phase]
                    lines.append(f"**{phase_labels.get(phase, phase)}**")
                    for r in group[:3]:
                        lines.append(f"  - `{r.skill.name}` — {r.skill.description[:80]}")
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
