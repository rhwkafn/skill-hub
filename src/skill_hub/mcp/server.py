"""MCP Tool Server for skill-hub.

Exposes tools to agents:
  - search_skills: find relevant skills by natural language query
  - load_skill: get the full SKILL.md content for a specific skill
  - suggest_skills: recommend skills for a complex task description
  - list_skill_categories: get a compact overview of all available skills
  - skill_info: get metadata + apply instructions for a skill

Usage:
  python -m skill_hub.mcp.server

  # Or configure in MCP settings:
  {
    "mcpServers": {
      "skill-hub": {
        "command": "python",
        "args": ["-m", "skill_hub.mcp.server"]
      }
    }
  }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..indexer import SkillIndex
from ..models import SkillMode
from ..registry import SkillRegistry


def _find_project_root() -> Path:
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "config" / "registries.yaml").exists():
            return d
        d = d.parent
    return Path.cwd()


def create_server(index_path: str | None = None) -> FastMCP:
    """Create and configure the MCP server."""
    root = _find_project_root()

    if index_path is None:
        index_path = str(root / "skill_index.json")

    index = SkillIndex.load(index_path)
    registry = SkillRegistry(index)

    mcp = FastMCP(
        "skill-hub",
        instructions=(
            "Agent skill registry with 250+ skills. "
            "Use search_skills to find skills, load_skill to get full instructions, "
            "suggest_skills for complex task decomposition. "
            "Skills have three modes: global (always active), on_demand (load for a task), "
            "compose (combine with other skills)."
        ),
    )

    @mcp.tool()
    def search_skills(query: str, top_k: int = 5) -> str:
        """Search for agent skills matching a natural language query.

        Args:
            query: What you're looking for (e.g. "debug react app", "write unit tests")
            top_k: Number of results to return (default 5)

        Returns:
            JSON list of matching skills with name, score, description, mode, and apply hints.
        """
        results = registry.search(query, top_k=top_k)
        if not results:
            return "No matching skills found."
        return json.dumps(results, indent=2, ensure_ascii=False)

    @mcp.tool()
    def load_skill(name: str) -> str:
        """Load the full instructions for a specific skill by name.

        Args:
            name: The exact skill name (e.g. "tdd", "browse", "guard")

        Returns:
            The full SKILL.md content, or an error message if not found.
        """
        skill = index.get(name)
        if not skill:
            candidates = [s for s in index.skills.values()
                         if name.lower() in s.name.lower()]
            if candidates:
                return (f"Skill '{name}' not found. Did you mean:\n" +
                        "\n".join(f"  - {c.name}" for c in candidates[:5]))
            return f"Skill '{name}' not found. Use search_skills to discover available skills."

        # Try local path
        if skill.local_path:
            skill_md = Path(skill.local_path) / "SKILL.md"
            if skill_md.exists():
                return skill_md.read_text(encoding="utf-8")

        # Try cache dir
        cache_dir = root / "skills_local"
        if skill.repo_path:
            safe_repo = skill.registry.replace("/", "--")
            cached = cache_dir / safe_repo / skill.repo_path
            if cached.exists():
                return cached.read_text(encoding="utf-8")

        return (f"Skill '{name}' exists but content is not cached. "
                f"Run 'python -m skill_hub.cli.main sync' first.")

    @mcp.tool()
    def suggest_skills(task_description: str) -> str:
        """Given a complex task, suggest which skills to activate and how to combine them.

        This is the key tool for matching complex inputs to the right skills.
        It analyzes the task and returns:
        1. Primary skill (the main workflow to follow)
        2. Global skills (safety/config skills to activate for the session)
        3. Complementary skills (optional additions)
        4. Application instructions (how to combine them)

        Args:
            task_description: Natural language description of what you need to do.
                e.g. "I need to build a React component with tests and make sure it's secure"
                e.g. "Debug why my page is slow, then deploy the fix safely"

        Returns:
            JSON with recommended skill combination and application plan.
        """
        # Stage 1: Broad keyword search — get more candidates
        candidates = registry.search(task_description, top_k=15)

        if not candidates:
            return json.dumps({"suggestion": "No matching skills found for this task."})

        # Stage 2: Classify candidates by mode
        globals_skills = []
        primary = []
        complementary = []

        for c in candidates:
            mode = c.get("mode", "on_demand")
            score = c.get("score", 0)

            if mode == "global":
                globals_skills.append(c)
            elif score >= 0.15:
                primary.append(c)
            else:
                complementary.append(c)

        # Build application plan
        plan = {
            "task": task_description,
            "primary_skill": primary[0] if primary else None,
            "global_skills": globals_skills[:3],
            "complementary_skills": complementary[:3],
        }

        # Add application instructions
        instructions = []
        if globals_skills:
            names = ", ".join(s["name"] for s in globals_skills[:3])
            instructions.append(
                f"ACTIVATE GLOBAL: {names} — inject into system prompt for the entire session. "
                f"These modify agent behavior (hooks, tool restrictions)."
            )
        if primary:
            s = primary[0]
            instructions.append(
                f"LOAD PRIMARY: {s['name']} — follow its workflow for this task. "
                f"Score: {s['score']}."
            )
        if complementary:
            names = ", ".join(s["name"] for s in complementary[:3])
            instructions.append(
                f"OPTIONAL: {names} — load if the task expands in scope."
            )

        plan["application_plan"] = " | ".join(instructions) if instructions else "No clear skill match."

        return json.dumps(plan, indent=2, ensure_ascii=False)

    @mcp.tool()
    def list_skill_categories() -> str:
        """List all available skill categories with skill counts and names.

        Returns:
            A compact text summary of all skills grouped by category.
        """
        return registry.compact_prompt()

    @mcp.tool()
    def skill_info(name: str) -> str:
        """Get metadata about a specific skill, including how to apply it.

        Args:
            name: The skill name

        Returns:
            JSON with metadata, apply mode, tools required, and application instructions.
        """
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
    args = parser.parse_args()

    server = create_server(args.index)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
