"""MCP Tool Server for skill-hub.

Three-stage architecture:
  1. Router (TF-IDF): recall candidates from 250+ skills
  2. Selector (precise LLM): pick the right ones from decision cards
  3. Workbench (main agent): load full SKILL.md and execute

Usage:
  # With selector (recommended — precise model for decisions)
  python -m skill_hub.mcp.server --selector-model gpt-4o
  python -m skill_hub.mcp.server --selector-provider ollama --selector-model qwen2.5:14b

  # Without selector (router returns all candidates, main model decides)
  python -m skill_hub.mcp.server --router tfidf
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..indexer import SkillIndex
from ..models import SkillMode
from ..registry import SkillRegistry
from ..router import KeywordRouter, TFIDFRouter
from ..router.base import SkillRouter
from ..selector import SkillSelector


def _find_project_root() -> Path:
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "config" / "registries.yaml").exists():
            return d
        d = d.parent
    return Path.cwd()


def _create_selector(args) -> SkillSelector | None:
    """Create selector if configured, None otherwise."""
    model = getattr(args, "selector_model", None)
    if not model:
        return None

    provider = getattr(args, "selector_provider", "openai")
    api_key = getattr(args, "selector_api_key", "") or os.environ.get("SELECTOR_API_KEY", "")

    bases = {
        "openai": "https://api.openai.com/v1",
        "ollama": "http://localhost:11434/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
    }

    return SkillSelector(
        api_base=getattr(args, "selector_api_base", None) or bases.get(provider, bases["openai"]),
        api_key=api_key,
        model=model,
    )


def create_server(
    index_path: str | None = None,
    router: SkillRouter | None = None,
    selector: SkillSelector | None = None,
) -> FastMCP:
    """Create and configure the MCP server."""
    root = _find_project_root()

    if index_path is None:
        index_path = str(root / "skill_index.json")

    index = SkillIndex.load(index_path)
    registry = SkillRegistry(index)
    all_skills = list(index.skills.values())

    if router is None:
        router = TFIDFRouter()  # default: local semantic matching, no API needed

    selector_status = "enabled" if selector else "disabled (returning all candidates)"

    mcp = FastMCP(
        "skill-hub",
        instructions=(
            f"Agent skill registry with {len(all_skills)} skills across 7 sources. "
            f"Router: {router.name}. Selector: {selector_status}. "
            "Use suggest_skills for complex tasks. "
            "Use search_skills for keyword lookup. "
            "Use load_skill to get full instructions for a chosen skill."
        ),
    )

    @mcp.tool()
    def search_skills(query: str, top_k: int = 5) -> str:
        """Search for agent skills by keyword matching.

        Args:
            query: Keywords (e.g. "debug react", "unit test")
            top_k: Number of results (default 5)

        Returns:
            JSON list of matching skills.
        """
        results = registry.search(query, top_k=top_k)
        if not results:
            return "No matching skills found."
        return json.dumps(results, indent=2, ensure_ascii=False)

    @mcp.tool()
    def load_skill(name: str) -> str:
        """Load the full SKILL.md content for a skill.

        Args:
            name: Exact skill name (e.g. "tdd", "guard", "investigate")

        Returns:
            Full SKILL.md content or error message.
        """
        skill = index.get(name)
        if not skill:
            candidates = [s for s in all_skills if name.lower() in s.name.lower()]
            if candidates:
                return (f"Skill '{name}' not found. Did you mean:\n" +
                        "\n".join(f"  - {c.name}" for c in candidates[:5]))
            return f"Skill '{name}' not found. Use search_skills to discover skills."

        if skill.local_path:
            skill_md = Path(skill.local_path) / "SKILL.md"
            if skill_md.exists():
                return skill_md.read_text(encoding="utf-8")

        cache_dir = root / "skills_local"
        if skill.repo_path:
            safe_repo = skill.registry.replace("/", "--")
            cached = cache_dir / safe_repo / skill.repo_path
            if cached.exists():
                return cached.read_text(encoding="utf-8")

        return f"Skill '{name}' exists but content not cached. Run sync first."

    @mcp.tool()
    def suggest_skills(task_description: str) -> str:
        """Find the right skills for a complex task.

        Three-stage pipeline:
        1. Router (TF-IDF) recalls ~20 candidates
        2. Selector (precise LLM) picks the best ones from decision cards
        3. Returns selected skill names for you to load

        The selector runs in an isolated context — no pollution of your workbench.

        Args:
            task_description: FULL task context. Don't compress. Include all requirements.
                Examples:
                - "重构认证模块，兼容旧接口，跑通测试，安全部署"
                - "build a React component with tests, review code quality, deploy safely"

        Returns:
            If selector is enabled: JSON with selected skill names.
            If selector is disabled: structured candidate list for you to choose from.
        """
        # Stage 1: Router recall
        route_output = router.route(task_description, all_skills, top_k=20)

        if not route_output.candidates:
            return "No matching skills found for this task."

        candidates = [r.skill for r in route_output.candidates]

        # Stage 2: Selector decision (isolated context)
        if selector:
            result = selector.select(task_description, candidates)

            if result.selected:
                return json.dumps({
                    "selected": result.selected,
                    "selector_model": selector.model,
                    "candidates_shown": result.shown,
                    "next_step": "Call load_skill(name) for each selected skill to get full instructions.",
                }, indent=2, ensure_ascii=False)

            # Selector returned nothing — fall through to return all candidates

        # Fallback: return all candidates for the main model to decide
        return route_output.to_prompt()

    @mcp.tool()
    def list_skill_categories() -> str:
        """List all available skills grouped by category."""
        return registry.compact_prompt()

    @mcp.tool()
    def skill_info(name: str) -> str:
        """Get metadata and apply instructions for a skill."""
        skill = index.get(name)
        if not skill:
            return f"Skill '{name}' not found."
        return json.dumps({
            "name": skill.name,
            "registry": skill.registry,
            "description": skill.description,
            "category": skill.category,
            "tags": skill.tags,
            "use_when": skill.use_when,
            "triggers": skill.triggers,
            "mode": skill.mode.value,
            "tools_required": skill.tools_required,
            "has_hooks": skill.has_hooks,
            "source_url": skill.source_url,
            "has_local_content": skill.local_path is not None,
            "decision_card": skill.decision_card,
            "apply_hint": skill.apply_hint(),
        }, indent=2, ensure_ascii=False)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Skill Hub MCP Server")
    parser.add_argument("--index", default=None, help="Path to skill_index.json")
    parser.add_argument("--router", choices=["keyword", "tfidf"], default="tfidf",
                        help="Routing strategy (default: tfidf)")
    parser.add_argument("--selector-model", default=None,
                        help="Model for skill selection (e.g. gpt-4o, qwen2.5:14b)")
    parser.add_argument("--selector-provider", choices=["openai", "ollama", "deepseek", "anthropic"],
                        default="openai", help="Provider for selector model")
    parser.add_argument("--selector-api-key", default=None,
                        help="API key for selector (or set SELECTOR_API_KEY env)")
    parser.add_argument("--selector-api-base", default=None,
                        help="API base URL for selector")
    args = parser.parse_args()

    router = TFIDFRouter() if args.router == "tfidf" else KeywordRouter()
    selector = _create_selector(args)
    server = create_server(args.index, router=router, selector=selector)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
