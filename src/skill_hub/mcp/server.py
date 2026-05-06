"""MCP Tool Server for skill-hub.

Exposes three tools to agents:
  - search_skills: find relevant skills by natural language query
  - load_skill: get the full SKILL.md content for a specific skill
  - list_skill_categories: get a compact overview of all available skills

Usage:
  # Run as stdio MCP server (for Claude Code, Cursor, etc.)
  python -m skill_hub.mcp.server

  # Or configure in your agent's MCP settings:
  {
    "mcpServers": {
      "skill-hub": {
        "command": "python",
        "args": ["-m", "skill_hub.mcp.server", "--index", "skill_index.json"]
      }
    }
  }
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..indexer import SkillIndex
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
        instructions="Agent skill registry — search, discover, and load agent skills from a curated index.",
    )

    @mcp.tool()
    def search_skills(query: str, top_k: int = 5) -> str:
        """Search for agent skills matching a natural language query.

        Args:
            query: What you're looking for (e.g. "debug react app", "write unit tests", "phylogenetic tree")
            top_k: Number of results to return (default 5)

        Returns:
            JSON list of matching skills with name, score, description, and category.
        """
        results = registry.search(query, top_k=top_k)
        if not results:
            return "No matching skills found."
        return json.dumps(results, indent=2, ensure_ascii=False)

    @mcp.tool()
    def load_skill(name: str) -> str:
        """Load the full instructions for a specific skill by name.

        First use search_skills to find the right skill name, then call this
        to get the complete SKILL.md content with detailed workflow, templates,
        and references.

        Args:
            name: The exact skill name (e.g. "tdd", "browse", "raincloud-plot-guide")

        Returns:
            The full SKILL.md content, or an error message if not found.
        """
        skill = index.get(name)
        if not skill:
            # Try fuzzy match
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

        return (f"Skill '{name}' exists in the index but content is not cached locally. "
                f"Run 'python -m skill_hub.cli.main sync --cache-dir skills_local' to download it.")

    @mcp.tool()
    def list_skill_categories() -> str:
        """List all available skill categories with skill counts and names.

        Use this to get a quick overview of what skills are available,
        organized by category.

        Returns:
            A compact text summary of all skills grouped by category.
        """
        return registry.compact_prompt()

    @mcp.tool()
    def skill_info(name: str) -> str:
        """Get metadata about a specific skill without loading full content.

        Args:
            name: The skill name

        Returns:
            JSON with the skill's metadata (description, tags, category, use_when, source).
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
            "source_url": skill.source_url,
            "has_local_content": skill.local_path is not None,
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
