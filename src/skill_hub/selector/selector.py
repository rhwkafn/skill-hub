"""Skill Selector — isolated context for skill selection.

Architecture:
- Decision cards are pre-computed during sync (no file I/O at selection time)
- Selector sees ONLY decision cards (~50 tokens each), not raw SKILL.md
- Strict output: JSON array of skill names, nothing else
- Runs in its own context, not shared with the workbench

Token budget for 20 candidates: ~1000-1600 tokens (vs 8000+ with raw SKILL.md)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from ..models import SkillMeta

# Selection rules — injected as system prompt
SELECTION_RULES = """You are a skill selector. Your ONLY job is to choose which skills apply to a task.

## Rules

1. Return ONLY a JSON array of skill names. Nothing else.
2. No explanation. No reasoning. No commentary. No markdown fences.
3. Select 1-8 skills. Prefer fewer — only include skills that clearly apply.
4. Global skills (marked [GLOBAL]) should be included if the task involves safety, production, or destructive operations.
5. If no skills match, return: []

## Output

A raw JSON array. Example: ["tdd", "careful", "land-and-deploy"]

NOTHING else. No text before or after."""


@dataclass
class SelectionResult:
    """Result of a skill selection."""
    selected: list[str]           # skill names chosen
    shown: int                    # how many decision cards were shown
    total_candidates: int         # total candidates from router
    raw_response: str = ""        # raw LLM response for debugging


def _cards_to_text(candidates: list[SkillMeta]) -> str:
    """Convert candidate skills to decision card text.

    Uses pre-computed decision_card from index. No file I/O.
    ~50 tokens per skill → 20 candidates ≈ 1000 tokens.
    """
    lines = []
    for s in candidates:
        if s.decision_card:
            lines.append(s.decision_card)
        else:
            # Fallback: build inline from metadata
            mode_tag = f"[{s.mode.value.upper()}]" if s.mode.value == "global" else ""
            lines.append(f"[{s.name}] {mode_tag}")
            if s.description:
                lines.append(f"What: {s.description[:100]}")
    return "\n\n".join(lines)


class SkillSelector:
    """Dedicated skill selector with isolated context.

    Token budget:
      - System prompt: ~200 tokens
      - Decision cards (20 skills × ~50 tokens): ~1000 tokens
      - User task: ~100 tokens
      - Output: ~50 tokens
      - Total: ~1350 tokens (vs 8000+ with raw SKILL.md)
    """

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o",
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _call_llm(self, system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 200,
        }

        resp = httpx.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def select(
        self,
        task: str,
        candidates: list[SkillMeta],
    ) -> SelectionResult:
        """Select skills for a task using decision cards.

        Args:
            task: Full task description (don't compress)
            candidates: Pre-filtered candidates from router (typically 15-25)

        Returns:
            SelectionResult with selected skill names.
        """
        if not candidates:
            return SelectionResult(selected=[], shown=0, total_candidates=0)

        # Build catalog from pre-computed decision cards
        cards_text = _cards_to_text(candidates)
        user_msg = f"## Task\n{task}\n\n## Skills\n{cards_text}"

        raw = ""
        try:
            raw = self._call_llm(SELECTION_RULES, user_msg)
            selected = self._parse_output(raw, candidates)
        except Exception:
            selected = [s.name for s in candidates[:5]]

        return SelectionResult(
            selected=selected,
            shown=len(candidates),
            total_candidates=len(candidates),
            raw_response=raw,
        )

    def _parse_output(self, raw: str, candidates: list[SkillMeta]) -> list[str]:
        candidate_names = {s.name for s in candidates}

        # Direct JSON array
        try:
            data = json.loads(raw.strip())
            if isinstance(data, list):
                return [n for n in data if isinstance(n, str) and n in candidate_names]
            if isinstance(data, dict):
                for key in ("skills", "selected", "result"):
                    if key in data and isinstance(data[key], list):
                        return [n for n in data[key] if isinstance(n, str) and n in candidate_names]
        except json.JSONDecodeError:
            pass

        # Extract JSON array from text
        match = re.search(r'\[[\s\S]*?\]', raw)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return [n for n in data if isinstance(n, str) and n in candidate_names]
            except json.JSONDecodeError:
                pass

        return []
