"""CLI for skill-hub operations."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

import yaml

from ..indexer import SkillIndex
from ..registry import SkillRegistry
from ..sync import GitHubSource, LocalSource, SkillSyncer


def _gh_token() -> str | None:
    """Try to get a GitHub token from the gh CLI."""
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _project_root() -> Path:
    """Find the project root (where config/ lives)."""
    # Walk up from this file to find config/registries.yaml
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "config" / "registries.yaml").exists():
            return d
        d = d.parent
    return Path.cwd()


def load_registries(config_path: str, cache_dir: str | None = None,
                    token: str | None = None) -> list:
    """Load registry configs from YAML."""
    with open(config_path, encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)

    sources = []
    for reg in config.get("registries", []):
        if reg["type"] == "github":
            sources.append(GitHubSource(
                repo=reg["repo"],
                skill_glob=reg.get("skill_glob", "*/SKILL.md"),
                token=token,
                cache_dir=cache_dir,
            ))
        elif reg["type"] == "local":
            sources.append(LocalSource(
                path=reg["path"],
                skill_glob=reg.get("skill_glob", "*/SKILL.md"),
                manifest=reg.get("manifest"),
                name=reg.get("name", "local"),
            ))
    return sources


async def cmd_sync(args):
    """Sync all registries and build the index."""
    cache_dir = args.cache_dir
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        print(f"Caching skill content to: {cache_dir}")

    token = _gh_token()
    if token:
        print("Using GitHub token from gh CLI")
    else:
        print("No GitHub token found (rate limit: 60 req/hr). Run 'gh auth login' for more.")

    sources = load_registries(args.config, cache_dir=cache_dir, token=token)
    syncer = SkillSyncer(sources, index_path=args.index)
    index = await syncer.sync_all(force=args.force)
    print()
    print(index.summary())


async def cmd_search(args):
    """Search the skill index."""
    index = SkillIndex.load(args.index)
    registry = SkillRegistry(index)
    results = registry.search(args.query, top_k=args.top_k)
    if not results:
        print("No matching skills found.")
        return
    for r in results:
        print(f"  [{r['score']:.3f}] {r['name']} ({r['registry']})")
        print(f"         {r['use_when'] or r['description']}")
        print()


async def cmd_load(args):
    """Load full content of a specific skill."""
    index = SkillIndex.load(args.index)
    skill = index.get(args.name)
    if not skill:
        print(f"Skill not found: {args.name}", file=sys.stderr)
        sys.exit(1)

    # Try local cache first
    if skill.local_path:
        skill_md = Path(skill.local_path) / "SKILL.md"
        if skill_md.exists():
            print(skill_md.read_text(encoding="utf-8"))
            return

    # Fallback: try repo_path in default cache location
    root = _project_root()
    cache_dir = root / "skills_local"
    if skill.repo_path:
        safe_repo = skill.registry.replace("/", "--")
        cached = cache_dir / safe_repo / skill.repo_path
        if cached.exists():
            print(cached.read_text(encoding="utf-8"))
            return

    print(f"Skill content not cached locally. Run 'sync --cache-dir skills_local' first.",
          file=sys.stderr)
    sys.exit(1)


async def cmd_info(args):
    """Show index info."""
    index = SkillIndex.load(args.index)
    print(index.summary())


async def cmd_prompt(args):
    """Generate compact prompt for agent injection."""
    index = SkillIndex.load(args.index)
    registry = SkillRegistry(index)
    print(registry.compact_prompt())


def main():
    root = _project_root()
    default_config = str(root / "config" / "registries.yaml")
    default_index = str(root / "skill_index.json")
    default_cache = str(root / "skills_local")

    parser = argparse.ArgumentParser(description="Skill Hub — agent skill registry")
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--index", default=default_index)
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="Sync skills from all registries")
    p_sync.add_argument("--cache-dir", default=default_cache,
                        help="Directory to cache SKILL.md content locally")
    p_sync.add_argument("--force", action="store_true",
                        help="Re-process all skills (ignore existing index)")
    s_search = sub.add_parser("search", help="Search skills")
    s_search.add_argument("query", help="Search query")
    s_search.add_argument("--top-k", type=int, default=5)

    s_load = sub.add_parser("load", help="Load full content of a skill by name")
    s_load.add_argument("name", help="Skill name")

    sub.add_parser("info", help="Show index info")
    sub.add_parser("prompt", help="Generate agent prompt with skill catalog")

    args = parser.parse_args()

    commands = {
        "sync": cmd_sync,
        "search": cmd_search,
        "load": cmd_load,
        "info": cmd_info,
        "prompt": cmd_prompt,
    }

    if args.command in commands:
        asyncio.run(commands[args.command](args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
