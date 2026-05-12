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
import datetime
import json
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..indexer import SkillIndex
from ..models import SkillMeta, SkillMode
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


def _load_usage(path: Path) -> dict:
    """Load skill usage stats from JSON file."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_usage(path: Path, data: dict) -> None:
    """Save skill usage stats to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_usage(usage: dict, name: str) -> None:
    """Record a skill usage event with timestamp."""
    now = datetime.datetime.now()
    ts = now.isoformat(timespec="seconds")
    month_key = now.strftime("%Y-%m")

    if name not in usage:
        usage[name] = {"total": 0, "months": {}, "last_used": None}
    entry = usage[name]
    entry["total"] += 1
    entry["last_used"] = ts
    entry["months"][month_key] = entry["months"].get(month_key, 0) + 1


def _run_clawhub(args: list[str], workdir: Path) -> tuple[int, str, str]:
    """Run a clawhub CLI command and return (returncode, stdout, stderr)."""
    cmd = ["npx", "clawhub", *args, "--workdir", str(workdir), "--no-input"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            shell=True,  # needed for npx on Windows
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "clawhub command timed out (60s)"
    except FileNotFoundError:
        return -1, "", "npx/clawhub not found. Install with: npm install -g clawhub"


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

    usage_path = root / "skill_usage.json"
    usage_data = _load_usage(usage_path)
    usage_dirty = [False]  # mutable flag for closure

    if router is None:
        router = TFIDFRouter()  # default: local semantic matching, no API needed

    selector_status = "enabled" if selector else "disabled (returning all candidates)"

    mcp = FastMCP(
        "skill-hub",
        instructions=(
            f"Agent skill registry with {len(all_skills)} skills across {len(set(s.registry for s in all_skills))} sources. "
            f"Router: {router.name}. Selector: {selector_status}. "
            "Use suggest_skills for complex tasks. "
            "Use search_skills for keyword lookup. "
            "Use load_skill to get full instructions for a chosen skill. "
            "Use plan_with_skills for complex tasks. "
            "Use get_skill_usage to see usage statistics and find unused skills. "
            "Use search_remote_skills ONLY when local skills don't match AND user confirms. "
            "Use install_remote_skill ONLY after user approves a remote search result."
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

        # Record usage (buffer writes, flush on get_skill_usage or shutdown)
        _record_usage(usage_data, name)
        usage_dirty[0] = True

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
    def suggest_skills(
        task_description: str,
        output_format: str = "",
        domain: str = "",
    ) -> str:
        """Find the right skills for a complex task.

        Three-stage pipeline:
        1. Router (TF-IDF) recalls ~20 candidates
        2. Optional: filter by output format or domain
        3. Returns candidates for you to choose from

        Args:
            task_description: FULL task context. Don't compress. Include all requirements.
            output_format: Filter by output format (e.g. "pptx", "html", "pdf", "csv").
                Use this when the workflow requires a specific output type.
            domain: Filter by domain (e.g. "science", "biology", "engineering", "writing").

        Returns:
            Structured candidate list with names, descriptions, paths, and capabilities.
        """
        # Stage 1: Router recall
        route_output = router.route(task_description, all_skills, top_k=30)

        if not route_output.candidates:
            return "No matching skills found for this task."

        candidates = [r.skill for r in route_output.candidates]

        # Stage 2: Filter by capabilities if specified
        if output_format:
            fmt = output_format.lower().strip(".")
            filtered = [s for s in candidates if fmt in s.output_formats]
            if filtered:
                candidates = filtered

        if domain:
            dom = domain.lower()
            filtered = [s for s in candidates if s.domain == dom]
            if filtered:
                candidates = filtered

        # Rebuild route output with (possibly filtered) candidates
        candidate_set = set(id(s) for s in candidates)
        from ..router.base import RouteOutput, RouteResult
        filtered_output = RouteOutput(
            candidates=[RouteResult(skill=r.skill, score=r.score, reason=r.reason)
                       for r in route_output.candidates if id(r.skill) in candidate_set],
            global_skills=[RouteResult(skill=r.skill, score=r.score, reason=r.reason)
                          for r in route_output.global_skills if id(r.skill) in candidate_set],
        )

        result = filtered_output.to_prompt()

        # Add planning hint for multi-skill tasks
        if len(candidates) >= 3:
            result += (
                "\n\n## Planning Recommendation\n"
                "This task matched multiple skills. Consider using `plan_with_skills` "
                "to create a structured execution plan with skill assignments per sub-task.\n"
                "Workflow: `suggest_skills` → understand capabilities → "
                "`plan_with_skills` → assign skills to sub-tasks → `load_skill` → execute."
            )

        return result

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
            "repo_path": skill.repo_path,
            "has_local_content": skill.local_path is not None,
            "decision_card": skill.decision_card,
            "apply_hint": skill.apply_hint(),
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    def get_skill_usage(month: str = "", top_k: int = 0) -> str:
        """Get skill usage statistics.

        Args:
            month: Filter by month (e.g. "2026-05"). Empty = all time totals.
            top_k: Limit to top N most-used skills. 0 = return all.

        Returns:
            JSON with per-skill usage counts, monthly breakdown, and unused skills list.
        """
        # Flush buffered usage data
        if usage_dirty[0]:
            _save_usage(usage_path, usage_data)
            usage_dirty[0] = False

        # Build usage report
        all_names = {s.name for s in all_skills}
        used_names = set(usage_data.keys())
        unused = sorted(all_names - used_names)

        report = {}
        for name in all_names:
            entry = usage_data.get(name, {"total": 0, "months": {}, "last_used": None})
            total = entry.get("total", 0)
            months = entry.get("months", {})
            last_used = entry.get("last_used")

            if month:
                count = months.get(month, 0)
            else:
                count = total

            report[name] = {
                "count": count,
                "total": total,
                "last_used": last_used,
                "months": months,
            }

        # Sort by count descending
        sorted_skills = sorted(report.items(), key=lambda x: x[1]["count"], reverse=True)
        if top_k > 0:
            sorted_skills = sorted_skills[:top_k]

        return json.dumps({
            "month_filter": month or "(all time)",
            "total_skills": len(all_names),
            "used_skills": len(used_names),
            "unused_skills": len(unused),
            "unused_list": unused,
            "usage": {name: data for name, data in sorted_skills},
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    def plan_with_skills(plan_text: str, top_k_per_task: int = 3) -> str:
        """Match a plan's sub-tasks to relevant skills.

        Takes a plan document (markdown) and returns skill recommendations
        for each sub-task. Use after writing-plans to enrich a plan with
        skill-hub capabilities.

        Args:
            plan_text: Full plan text in markdown format.
            top_k_per_task: Max skills to recommend per sub-task (default 3).

        Returns:
            JSON with each sub-task and its recommended skills (name, path, phase).
        """
        import re

        tasks = _parse_plan_tasks(plan_text)
        if not tasks:
            # Fallback: treat entire text as one task
            tasks = [{"id": 1, "title": "Main task", "text": plan_text[:500]}]

        results = []
        for task in tasks:
            query = task["text"][:300]
            route_output = router.route(query, all_skills, top_k=top_k_per_task * 2)

            # Filter by phase if task has phase indicators
            candidates = [r.skill for r in route_output.candidates]

            # Pick top_k
            selected = candidates[:top_k_per_task]

            results.append({
                "task_id": task["id"],
                "task_title": task["title"],
                "recommended_skills": [
                    {
                        "name": s.name,
                        "phase": s.phase.value,
                        "execution_mode": s.execution_mode.value,
                        "local_path": s.local_path,
                        "description": s.description[:120],
                        "use_when": s.use_when[:80] if s.use_when else "",
                    }
                    for s in selected
                ],
            })

        return json.dumps(results, indent=2, ensure_ascii=False)

    @mcp.tool()
    def search_remote_skills(query: str, top_k: int = 10) -> str:
        """Search ClawHub for skills not in the local registry.

        GATING RULES — only call this tool when:
        1. Local suggest_skills returned no good matches (score < 0.15) AND the task
           is specialized/complex enough to warrant external skills, AND the user confirms.
        2. OR the user explicitly asks to search remote/external skills.

        Do NOT call this tool on every task. Most tasks should use local skills only.

        Args:
            query: Search query (e.g. "causal inference DID", "R stats econometrics")
            top_k: Max results to return (default 10)

        Returns:
            Formatted list of matching skills with slug, name, and relevance score.
        """
        rc, stdout, stderr = _run_clawhub(
            ["search", query, "--limit", str(top_k)], root
        )
        if rc != 0:
            return f"ClawHub search failed: {stderr or stdout}"

        # Parse output: "slug  Name  (score)"
        lines = [l.strip() for l in stdout.strip().split("\n") if l.strip()]
        results = []
        for line in lines:
            if line.startswith("-") or not line:
                continue
            # Format: slug  Name  (score)
            parts = line.rsplit("(", 1)
            if len(parts) == 2:
                name_part = parts[0].strip()
                score_part = parts[1].rstrip(")")
                slug = name_part.split()[0] if name_part.split() else name_part
                results.append({"slug": slug, "display": name_part, "score": score_part})

        if not results:
            return f"No remote skills found for: {query}"

        out = [f"Found {len(results)} remote skills on ClawHub:\n"]
        for i, r in enumerate(results, 1):
            out.append(f"  {i}. {r['display']} [score: {r['score']}]")
        out.append("\nTo install, call install_remote_skill(slug=<slug>).")
        out.append("Only install skills you actually need.")
        return "\n".join(out)

    @mcp.tool()
    def install_remote_skill(slug: str) -> str:
        """Install a skill from ClawHub into the local registry.

        GATING RULES — only call this tool when:
        1. The user has reviewed search_remote_skills results AND explicitly approved installation.
        2. OR the user directly specifies a slug to install.

        After installation, the skill is added to the local index and becomes
        available via search_skills/suggest_skills/load_skill like any other skill.

        Args:
            slug: The skill slug from ClawHub (e.g. "causal-inference", "python-data-analysis")

        Returns:
            Installation result with skill metadata.
        """
        clawhub_dir = root / "skills_local" / "clawhub"

        rc, stdout, stderr = _run_clawhub(
            ["install", slug, "--dir", "skills_local/clawhub", "--force"], root
        )
        if rc != 0:
            return f"Failed to install '{slug}': {stderr or stdout}"

        # Parse the installed SKILL.md
        skill_dir = clawhub_dir / slug
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return f"Installed but SKILL.md not found at {skill_md}"

        content = skill_md.read_text(encoding="utf-8")

        # Parse frontmatter
        from ..sync.local_source import _parse_skill_frontmatter
        from ..sync.github_source import _auto_extract_tags, _infer_phase, _infer_execution_mode

        description, use_when, tags, category = _parse_skill_frontmatter(content)
        if not tags:
            tags = _auto_extract_tags(content, description)

        # Check if already in index
        if slug in index.skills:
            existing = index.skills[slug]
            existing.local_path = str(skill_dir)
            existing.description = description or existing.description
        else:
            skill = SkillMeta(
                name=slug,
                registry="clawhub",
                description=description,
                category=category,
                tags=tags,
                use_when=use_when,
                source_url=f"https://clawhub.com/skills/{slug}",
                local_path=str(skill_dir),
                phase=_infer_phase(content, description),
                execution_mode=_infer_execution_mode(content, description),
            )
            skill.build_decision_card(content)
            index.add(skill)
            all_skills.append(skill)

        # Persist index
        index.save(index_path)

        return (
            f"Installed '{slug}' from ClawHub.\n"
            f"  Path: {skill_dir}\n"
            f"  Description: {description[:120]}\n"
            f"  Tags: {', '.join(tags[:6])}\n"
            f"  Available via load_skill('{slug}')"
        )

    return mcp


def _parse_plan_tasks(plan_text: str) -> list[dict]:
    """Extract sub-tasks from a plan document. Multi-level fallback.

    Tries in order:
    1. ### Task N: headers (superpowers format)
    2. ## or ### headings
    3. - [ ] checkboxes
    4. Numbered list items (1. 2. 3.)
    """
    import re
    tasks = []

    # Strategy 1: ### Task N: (superpowers writing-plans format)
    blocks = re.split(r"(?=^### Task\s+\d+)", plan_text, flags=re.MULTILINE)
    if len(blocks) > 1:
        for block in blocks:
            m = re.match(r"^### Task\s+(\d+):\s*(.+)", block.strip())
            if m:
                task_id = int(m.group(1))
                title = m.group(2).strip()
                text = block.strip()
                tasks.append({"id": task_id, "title": title, "text": text})
        if tasks:
            return tasks

    # Strategy 2: Any ### or ## headings
    blocks = re.split(r"(?=^#{2,3}\s+)", plan_text, flags=re.MULTILINE)
    if len(blocks) > 1:
        for i, block in enumerate(blocks, 1):
            m = re.match(r"^#{2,3}\s+(.+)", block.strip())
            if m:
                title = m.group(1).strip()
                tasks.append({"id": i, "title": title, "text": block.strip()})
        if tasks:
            return tasks

    # Strategy 3: Checkboxes - [ ]
    lines = plan_text.split("\n")
    task_id = 0
    for line in lines:
        m = re.match(r"^\s*-\s*\[.\]\s*(.+)", line)
        if m:
            task_id += 1
            title = m.group(1).strip().strip("*")
            tasks.append({"id": task_id, "title": title, "text": title})
    if tasks:
        return tasks

    # Strategy 4: Numbered list
    for line in lines:
        m = re.match(r"^\s*\d+\.\s+(.+)", line)
        if m:
            task_id += 1
            title = m.group(1).strip()
            tasks.append({"id": task_id, "title": title, "text": title})

    return tasks


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
