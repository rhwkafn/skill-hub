"""LLM router — use a cheap/fast model for semantic skill matching.

This is the key architecture: a small model handles routing,
the main model only sees the matched skill content.

Supports any OpenAI-compatible API (OpenAI, Ollama, vLLM, LiteLLM, etc.)
"""

from __future__ import annotations

import json
import httpx

from .base import SkillRouter, RouteResult
from ..models import SkillMeta, SkillMode

# Default models for different providers
CHEAP_MODELS = {
    "openai": "gpt-4o-mini",
    "ollama": "qwen2.5:3b",
    "deepseek": "deepseek-chat",
    "anthropic": "claude-haiku-4-5",
}

# System prompt for the routing LLM
ROUTING_PROMPT = """You are a skill router. Given a user task and a catalog of available skills,
select the most relevant skills and classify how they should be applied.

Rules:
- Select 1-3 skills maximum
- Classify each as: global (session-wide safety/config), on_demand (load for this task), or compose (combine with others)
- Return ONLY valid JSON, no explanation

Output format:
```json
{
  "selected": [
    {"name": "skill-name", "mode": "on_demand", "reason": "why it matches"}
  ]
}
```"""


def _build_catalog(skills: list[SkillMeta], max_skills: int = 80) -> str:
    """Build a compact skill catalog for the routing LLM.

    Keeps token count low: one line per skill, only essential fields.
    """
    lines = []
    for s in skills[:max_skills]:
        mode_tag = ""
        if s.mode == SkillMode.GLOBAL:
            mode_tag = " [GLOBAL]"
        trigger = s.triggers[0] if s.triggers else (s.use_when or s.description[:60])
        lines.append(f"- {s.name}{mode_tag}: {trigger}")
    return "\n".join(lines)


class LLMRouter(SkillRouter):
    """Use a cheap LLM for semantic skill routing.

    Architecture:
    1. Build compact skill catalog (~2KB for 80 skills)
    2. Send catalog + user query to cheap model
    3. Model returns structured JSON with selected skills
    4. Map back to full SkillMeta objects

    Supports any OpenAI-compatible API endpoint.
    """

    name = "llm"

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        max_catalog_skills: int = 80,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_catalog_skills = max_catalog_skills
        self._skill_map: dict[str, SkillMeta] = {}

    def _call_llm(self, system: str, user: str) -> str:
        """Call the LLM API (OpenAI-compatible chat completions)."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        }

        resp = httpx.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 10) -> list[RouteResult]:
        # Build skill map for lookup
        self._skill_map = {s.name: s for s in skills}

        # Build compact catalog
        catalog = _build_catalog(skills, self.max_catalog_skills)

        # Call cheap LLM
        user_msg = f"## Available Skills\n{catalog}\n\n## User Task\n{query}"

        try:
            raw = self._call_llm(ROUTING_PROMPT, user_msg)
        except Exception as e:
            # Fallback to keyword matching on API failure
            from .keyword import KeywordRouter
            return KeywordRouter().route(query, skills, top_k)

        # Parse response
        return self._parse_response(raw, skills)

    def _parse_response(self, raw: str, skills: list[SkillMeta]) -> list[RouteResult]:
        """Parse LLM JSON response into RouteResults."""
        # Extract JSON from response (handle markdown code blocks)
        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback
            from .keyword import KeywordRouter
            return KeywordRouter().route("", skills, 5)

        results = []
        for item in data.get("selected", []):
            name = item.get("name", "")
            skill = self._skill_map.get(name)
            if skill:
                results.append(RouteResult(
                    skill=skill,
                    score=1.0,  # LLM-selected skills get max score
                    reason=item.get("reason", "llm selected"),
                ))

        return results


def create_llm_router(
    provider: str = "openai",
    api_key: str = "",
    model: str | None = None,
    api_base: str | None = None,
) -> LLMRouter:
    """Factory function to create an LLM router for common providers.

    Args:
        provider: "openai", "ollama", "deepseek", "anthropic"
        api_key: API key (not needed for Ollama)
        model: Model override (uses provider default if None)
        api_base: API base URL override
    """
    bases = {
        "openai": "https://api.openai.com/v1",
        "ollama": "http://localhost:11434/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
    }

    return LLMRouter(
        api_base=api_base or bases.get(provider, bases["openai"]),
        api_key=api_key,
        model=model or CHEAP_MODELS.get(provider, "gpt-4o-mini"),
    )
