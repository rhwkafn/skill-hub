"""Skill Selector — dedicated context for skill selection.

The selector runs in an isolated context, separate from the main workbench.
It reads skill briefs, applies selection rules, and returns ONLY skill names.
No reasoning, no explanation, no wasted tokens.
"""

from .selector import SkillSelector, SelectionResult

__all__ = ["SkillSelector", "SelectionResult"]
