"""Skill Syncer — orchestrates syncing from multiple sources into the local index."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ..indexer import SkillIndex
from ..models import SkillMeta
from .base import SkillSource


class SkillSyncer:
    """Syncs skills from multiple sources into a unified local index."""

    def __init__(self, sources: list[SkillSource], index_path: str = "skill_index.json"):
        self.sources = sources
        self.index_path = Path(index_path)

    async def sync_all(self) -> SkillIndex:
        """Discover skills from all sources and build the index."""
        index = SkillIndex()

        for source in self.sources:
            try:
                skills = await source.list_skills()
                for skill in skills:
                    index.add(skill)
            except Exception as e:
                print(f"Warning: failed to sync from {source.name}: {e}")

        index.save(self.index_path)
        return index

    async def sync_one(self, source: SkillSource) -> list[SkillMeta]:
        """Sync from a single source."""
        skills = await source.list_skills()
        # Merge with existing index
        index = SkillIndex.load(self.index_path)
        for skill in skills:
            index.add(skill)
        index.save(self.index_path)
        return skills
