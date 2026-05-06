"""LLM router — use a cheap/fast model for semantic skill re-ranking.

Architecture: TF-IDF does broad recall, LLM re-ranks the top candidates.
The LLM adds semantic understanding without seeing the full catalog.
"""

from __future__ import annotations

import json
import httpx

from .base import SkillRouter, RouteOutput, RouteResult
from .tfidf import TFIDFRouter
from ..models import SkillMeta, SkillMode

CHEAP_MODELS = {
    "openai": "gpt-4o-mini",
    "ollama": "qwen2.5:3b",
    "deepseek": "deepseek-chat",
    "anthropic": "claude-haiku-4-5",
}

RERANK_PROMPT = """You are a skill router. Given a user task and candidate skills,
re-rank them by relevance and explain why.

Return ONLY valid JSON:
```json
{
  "ranked": [
    {"name": "skill-name", "score": 0.95, "reason": "why this matches the task"}
  ]
}
```

Be generous with inclusion — it's better to include a marginally relevant skill
than to miss one the main model might need."""


def _build_candidates_block(candidates: list[RouteResult]) -> str:
    """Build a compact text block of candidates for the LLM."""
    lines = []
    for i, r in enumerate(candidates):
        mode_tag = ""
        if r.skill.mode == SkillMode.GLOBAL:
            mode_tag = " [GLOBAL]"
        trigger = r.skill.triggers[0] if r.skill.triggers else (r.skill.use_when or r.skill.description[:80])
        lines.append(f"{i+1}. {r.skill.name}{mode_tag}: {trigger}")
    return "\n".join(lines)


class LLMRouter(SkillRouter):
    """Two-stage router: TF-IDF recall + LLM re-ranking.

    Stage 1: TF-IDF finds top-30 candidates (fast, broad recall)
    Stage 2: Cheap LLM re-ranks top-30 → top-15 with semantic understanding

    The LLM only sees skill names + one-line descriptions (~1KB),
    not the full SKILL.md content. This keeps the routing cost minimal.
    """

    name = "llm"

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        recall_top_k: int = 30,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.recall_top_k = recall_top_k
        self._tfidf = TFIDFRouter()
        self._skill_map: dict[str, SkillMeta] = {}

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
            "temperature": 0.1,
            "max_tokens": 500,
        }

        resp = httpx.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 20) -> RouteOutput:
        # Stage 1: TF-IDF broad recall
        recall_output = self._tfidf.route(query, skills, top_k=self.recall_top_k)
        recall_candidates = recall_output.candidates

        if not recall_candidates:
            return recall_output

        # Stage 2: LLM re-ranking (only on the recalled candidates)
        self._skill_map = {r.skill.name: r.skill for r in recall_candidates}
        candidates_block = _build_candidates_block(recall_candidates)
        user_msg = f"## Candidate Skills\n{candidates_block}\n\n## User Task\n{query}"

        try:
            raw = self._call_llm(RERANK_PROMPT, user_msg)
            reranked = self._parse_response(raw, recall_candidates)
            if reranked:
                global_skills = [r for r in reranked if r.skill.mode == SkillMode.GLOBAL]
                return RouteOutput(
                    candidates=reranked[:top_k],
                    global_skills=global_skills,
                )
        except Exception:
            pass

        # Fallback: return TF-IDF results
        return recall_output

    def _parse_response(self, raw: str, fallback: list[RouteResult]) -> list[RouteResult]:
        json_str = raw
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            json_str = raw.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return fallback

        results = []
        for item in data.get("ranked", []):
            name = item.get("name", "")
            skill = self._skill_map.get(name)
            if skill:
                results.append(RouteResult(
                    skill=skill,
                    score=float(item.get("score", 0.5)),
                    reason=item.get("reason", "llm re-ranked"),
                ))

        return results if results else fallback


def create_llm_router(
    provider: str = "openai",
    api_key: str = "",
    model: str | None = None,
    api_base: str | None = None,
) -> LLMRouter:
    """Factory for common providers."""
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
