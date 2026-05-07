"""Skill Syncer — orchestrates syncing from multiple sources into the local index."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ..indexer import SkillIndex
from ..models import SkillMeta
from .base import SkillSource


class SkillSyncer:
    """Syncs skills from multiple sources into a unified local index.

    Incremental: loads existing index first, only processes new skills.
    """

    def __init__(self, sources: list[SkillSource], index_path: str = "skill_index.json"):
        self.sources = sources
        self.index_path = Path(index_path)

    async def sync_all(self, force: bool = False) -> SkillIndex:
        """Discover skills from all sources and build the index.

        Incremental by default: skips skills already in the index.
        Pass force=True to re-process all skills (full rebuild).
        """
        if force:
            index = SkillIndex()
            print("  Force mode: rebuilding index from scratch")
        else:
            index = SkillIndex.load(self.index_path)
        existing = set(index.skills.keys())
        new_count = 0

        for source in self.sources:
            try:
                skills = await source.list_skills()
                added = 0
                for skill in skills:
                    if force or skill.name not in existing:
                        index.add(skill)
                        existing.add(skill.name)
                        added += 1
                        new_count += 1
                skipped = len(skills) - added
                msg = f"  [{source.name}] {len(skills)} found, {added} processed"
                if skipped:
                    msg += f", {skipped} skipped"
                print(msg)
            except Exception as e:
                print(f"  [{source.name}] FAILED: {type(e).__name__}: {e}")

        index.save(self.index_path)
        if new_count:
            print(f"  Total: {new_count} skills processed")
        else:
            print(f"  No new skills found. Index unchanged ({len(index.skills)} total).")
        return index

    async def sync_one(self, source: SkillSource) -> list[SkillMeta]:
        """Sync from a single source."""
        skills = await source.list_skills()
        index = SkillIndex.load(self.index_path)
        for skill in skills:
            index.add(skill)
        index.save(self.index_path)
        return skills
