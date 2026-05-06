"""Core data models for skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SkillMode(Enum):
    """How a skill should be applied to an agent session."""
    GLOBAL = "global"       # Always active (e.g. guard, careful) — hooks + tool restrictions
    ON_DEMAND = "on_demand" # Load once when needed (e.g. tdd, diagnose) — inject as instructions
    COMPOSE = "compose"     # Can combine with other skills (e.g. code-review + security)


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
    # Application model
    mode: SkillMode = SkillMode.ON_DEMAND
    tools_required: list[str] = field(default_factory=list)  # e.g. ["Bash", "Read"]
    has_hooks: bool = False  # whether the skill defines PreToolUse/PostToolUse hooks
    triggers: list[str] = field(default_factory=list)  # activation phrases
    decision_card: str = ""  # compact structured summary for the selector (~50 tokens)

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
            "mode": self.mode.value,
            "tools_required": self.tools_required,
            "has_hooks": self.has_hooks,
            "triggers": self.triggers,
            "decision_card": self.decision_card,
        }

    def build_decision_card(self, content_head: str = "") -> str:
        """Generate a compact decision card for the selector.

        Format: structured, ~50 tokens per skill.
        The selector sees these cards instead of raw SKILL.md.
        """
        parts = []

        # Header: [name] mode=X hooks=true
        flags = []
        if self.has_hooks:
            flags.append("hooks=true")
        if self.tools_required:
            flags.append(f"needs={','.join(self.tools_required[:3])}")
        flag_str = f" {' '.join(flags)}" if flags else ""
        parts.append(f"[{self.name}] mode={self.mode.value}{flag_str}")

        # When: triggers or use_when
        when_parts = self.triggers[:3] if self.triggers else []
        if self.use_when and self.use_when not in when_parts:
            when_parts.append(self.use_when[:80])
        if when_parts:
            parts.append(f"When: {', '.join(when_parts)}")

        # What: extract from content head or description
        what = self._extract_what(content_head)
        if what:
            parts.append(f"What: {what}")

        self.decision_card = "\n".join(parts)
        return self.decision_card

    def _extract_what(self, content_head: str) -> str:
        """Extract a one-sentence 'what does this skill do' from content."""
        import re

        # Try description first (already parsed from frontmatter)
        if self.description and len(self.description) > 10:
            # Take first sentence
            desc = self.description.split(".")[0].strip()
            if len(desc) > 10:
                return desc[:120]

        # Try first meaningful paragraph from content
        if content_head:
            body = re.sub(r"^---.*?---\s*", "", content_head, flags=re.DOTALL)
            body = re.sub(r"^#.*\n", "", body).strip()
            # Skip empty lines
            for line in body.split("\n"):
                line = line.strip()
                if line and len(line) > 15 and not line.startswith("|"):
                    return line[:120]

        return ""

    def matches(self, query: str) -> float:
        """Simple relevance score against a query string. Returns 0.0-1.0."""
        q = query.lower()
        fields = [
            (self.name, 0.3),
            (self.description, 0.25),
            (self.use_when, 0.15),
            (" ".join(self.tags), 0.1),
            (" ".join(self.triggers), 0.2),
        ]
        score = 0.0
        for text, weight in fields:
            if q in text.lower():
                score += weight
            for word in q.split():
                if word and word in text.lower():
                    score += weight * 0.3
        return min(score, 1.0)

    def apply_hint(self) -> dict:
        """Structured hint for how an agent should apply this skill."""
        if self.mode == SkillMode.GLOBAL:
            return {
                "mode": "global",
                "instruction": (
                    f"Activate '{self.name}' as a session-wide rule. "
                    f"This skill modifies agent behavior through hooks and tool restrictions. "
                    f"Inject its instructions into the system prompt for the entire session."
                ),
                "tools_required": self.tools_required,
                "has_hooks": self.has_hooks,
            }
        elif self.mode == SkillMode.COMPOSE:
            return {
                "mode": "compose",
                "instruction": (
                    f"Load '{self.name}' as reference material. "
                    f"It can be combined with other skills. "
                    f"Inject its content into context alongside any co-active skills."
                ),
                "tools_required": self.tools_required,
            }
        else:
            return {
                "mode": "on_demand",
                "instruction": (
                    f"Load '{self.name}' for this specific task only. "
                    f"Follow its workflow step by step. "
                    f"Inject its content into the system prompt for this task."
                ),
                "tools_required": self.tools_required,
            }
