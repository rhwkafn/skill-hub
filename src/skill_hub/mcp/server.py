"""MCP Tool Server for skill-hub.

Exposes tools to agents:
  - search_skills: find relevant skills by keyword
  - load_skill: get the full SKILL.md content
  - suggest_skills: semantic routing via cheap LLM or TF-IDF
  - list_skill_categories: compact overview
  - skill_info: metadata + apply instructions

Usage:
  # Default (keyword matching)
  python -m skill_hub.mcp.server

  # TF-IDF (local semantic, no API)
  python -m skill_hub.mcp.server --router tfidf

  # LLM (cheap model for routing)
  python -m skill_hub.mcp.server --router llm --llm-provider ollama
  python -m skill_hub.mcp.server --router llm --llm-provider openai --llm-model gpt-4o-mini
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
from ..router import KeywordRouter, TFIDFRouter, LLMRouter
from ..router.base import SkillRouter, RouteOutput
from ..router.llm import create_llm_router


def _find_project_root() -> Path:
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "config" / "registries.yaml").exists():
            return d
        d = d.parent
    return Path.cwd()


def _create_router(args) -> SkillRouter:
    """Create the appropriate router based on CLI args."""
    router_type = getattr(args, "router", "keyword")

    if router_type == "tfidf":
        return TFIDFRouter()
    elif router_type == "llm":
        provider = getattr(args, "llm_provider", "ollama")
        api_key = getattr(args, "llm_api_key", "") or os.environ.get("LLM_API_KEY", "")
        model = getattr(args, "llm_model", None)
        api_base = getattr(args, "llm_api_base", None)
        return create_llm_router(
            provider=provider,
            api_key=api_key,
            model=model,
            api_base=api_base,
        )
    else:
        return KeywordRouter()


def create_server(index_path: str | None = None, router: SkillRouter | None = None) -> FastMCP:
    """Create and configure the MCP server."""
    root = _find_project_root()

    if index_path is None:
        index_path = str(root / "skill_index.json")

    index = SkillIndex.load(index_path)
    registry = SkillRegistry(index)
    all_skills = list(index.skills.values())

    if router is None:
        router = KeywordRouter()

    mcp = FastMCP(
        "skill-hub",
        instructions=(
            "Agent skill registry with 250+ skills across 7 sources. "
            "Use suggest_skills for complex tasks (it uses semantic routing). "
            "Use search_skills for keyword lookup. "
            "Use load_skill to get full instructions. "
            "Skills have modes: global (always active), on_demand (task-specific), compose (combinable)."
        ),
    )

    @mcp.tool()
    def search_skills(query: str, top_k: int = 5) -> str:
        """Search for agent skills by keyword matching.

        For simple keyword-based lookup. For complex natural language tasks,
        use suggest_skills instead.

        Args:
            query: Keywords to search (e.g. "debug react", "unit test")
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

        First use search_skills or suggest_skills to find the right name.

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
        """Semantic skill discovery — find ALL relevant skills for a task.

        This returns a broad set of candidates for YOU (the main model) to
        evaluate. It does NOT decide which skills to use — that's your job.

        The router does recall (find candidates), you do decision (pick + combine).

        Args:
            task_description: The FULL task context, in natural language.
                Don't compress or summarize — include all requirements.
                Examples:
                - "重构认证模块，兼容旧接口，跑通测试，安全部署"
                - "build a React component with tests, review code quality, ensure security"

        Returns:
            Structured text with all candidate skills, grouped by type.
            Use load_skill(name) to get full instructions for any skill you choose.
        """
        route_output = router.route(task_description, all_skills, top_k=20)

        if not route_output.candidates:
            return "No matching skills found for this task."

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
            "apply_hint": skill.apply_hint(),
        }, indent=2, ensure_ascii=False)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="Skill Hub MCP Server")
    parser.add_argument("--index", default=None, help="Path to skill_index.json")
    parser.add_argument("--router", choices=["keyword", "tfidf", "llm"], default="keyword",
                        help="Routing strategy (default: keyword)")
    parser.add_argument("--llm-provider", choices=["openai", "ollama", "deepseek", "anthropic"],
                        default="ollama", help="LLM provider for --router llm")
    parser.add_argument("--llm-model", default=None, help="Model override")
    parser.add_argument("--llm-api-key", default=None, help="API key (or set LLM_API_KEY env)")
    parser.add_argument("--llm-api-base", default=None, help="API base URL override")
    args = parser.parse_args()

    router = _create_router(args)
    server = create_server(args.index, router=router)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
