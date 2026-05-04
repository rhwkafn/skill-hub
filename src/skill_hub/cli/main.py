"""CLI for skill-hub operations."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from ..indexer import SkillIndex
from ..registry import SkillRegistry
from ..sync import GitHubSource, LocalSource, SkillSyncer


def load_registries(config_path: str) -> list:
    """Load registry configs from YAML."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    sources = []
    for reg in config.get("registries", []):
        if reg["type"] == "github":
            sources.append(GitHubSource(
                repo=reg["repo"],
                skill_glob=reg.get("skill_glob", "*/SKILL.md"),
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
    sources = load_registries(args.config)
    syncer = SkillSyncer(sources, index_path=args.index)
    index = await syncer.sync_all()
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
    parser = argparse.ArgumentParser(description="Skill Hub — agent skill registry")
    parser.add_argument("--config", default="config/registries.yaml")
    parser.add_argument("--index", default="skill_index.json")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("sync", help="Sync skills from all registries")
    s_search = sub.add_parser("search", help="Search skills")
    s_search.add_argument("query", help="Search query")
    s_search.add_argument("--top-k", type=int, default=5)
    sub.add_parser("info", help="Show index info")
    sub.add_parser("prompt", help="Generate agent prompt with skill catalog")

    args = parser.parse_args()

    commands = {
        "sync": cmd_sync,
        "search": cmd_search,
        "info": cmd_info,
        "prompt": cmd_prompt,
    }

    if args.command in commands:
        asyncio.run(commands[args.command](args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
