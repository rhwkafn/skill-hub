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
from ..router.base import SkillRouter
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
        """Semantic skill routing — find the best skills for a complex task.

        This is the main entry point for skill discovery. Unlike search_skills
        (keyword matching), this uses semantic understanding to match natural
        language task descriptions to the right skills.

        It returns:
        - Primary skill: the main workflow to follow
        - Global skills: safety/config skills to activate for the session
        - Application plan: how to combine them

        Args:
            task_description: What you need to do, in natural language.
                Examples:
                - "部署修复到生产环境，注意安全"
                - "build a React component with tests and review code quality"
                - "debug why the page is slow and find the root cause"

        Returns:
            JSON with recommended skills and application plan.
        """
        # Use the router for semantic matching
        route_results = router.route(task_description, all_skills, top_k=15)

        if not route_results:
            return json.dumps({"suggestion": "No matching skills found."})

        # Classify by mode
        global_skills = []
        primary = []
        complementary = []

        for r in route_results:
            d = {
                "name": r.skill.name,
                "registry": r.skill.registry,
                "score": round(r.score, 3),
                "mode": r.skill.mode.value,
                "reason": r.reason,
                "description": r.skill.description[:120],
                "triggers": r.skill.triggers[:3],
                "tools_required": r.skill.tools_required,
                "has_hooks": r.skill.has_hooks,
            }
            if r.skill.mode == SkillMode.GLOBAL:
                global_skills.append(d)
            elif r.score >= 0.15 and not primary:
                primary.append(d)
            else:
                complementary.append(d)

        # Build plan
        instructions = []
        if global_skills:
            names = ", ".join(s["name"] for s in global_skills[:3])
            instructions.append(
                f"ACTIVATE GLOBAL: {names} — inject into system prompt. "
                f"These add safety hooks and tool restrictions."
            )
        if primary:
            s = primary[0]
            instructions.append(
                f"LOAD PRIMARY: {s['name']} — follow its workflow. "
                f"Reason: {s['reason']}."
            )
        if complementary:
            names = ", ".join(s["name"] for s in complementary[:3])
            instructions.append(f"OPTIONAL: {names} — load if task expands.")

        plan = {
            "task": task_description,
            "router": router.name,
            "primary_skill": primary[0] if primary else None,
            "global_skills": global_skills[:3],
            "complementary_skills": complementary[:3],
            "application_plan": " | ".join(instructions) if instructions else "No clear match.",
        }

        return json.dumps(plan, indent=2, ensure_ascii=False)

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
