"""Tests for the skill registry."""

import pytest
from skill_hub.indexer import SkillIndex
from skill_hub.models import SkillMeta
from skill_hub.registry import SkillRegistry


def _make_registry() -> SkillRegistry:
    idx = SkillIndex()
    idx.add(SkillMeta(
        name="ggplot2-richtext-fixes",
        registry="codex",
        description="Fix ggplot2 superscript and richtext rendering",
        use_when="Fix ggplot2 labels or export rendering issues",
        category="Plotting",
        tags=["r", "ggplot2"],
    ))
    idx.add(SkillMeta(
        name="nature-polishing",
        registry="nature-skills",
        description="Polish manuscripts to Nature journal standards",
        use_when="Polishing paper for Nature submission",
        category="Writing",
        tags=["nature", "paper"],
    ))
    idx.add(SkillMeta(
        name="statistical-analysis",
        registry="scientific",
        description="Run statistical tests and generate reports",
        use_when="User needs statistical analysis or hypothesis testing",
        category="Analysis",
        tags=["statistics", "python"],
    ))
    return SkillRegistry(idx)


def test_search_returns_results():
    reg = _make_registry()
    results = reg.search("ggplot2 rendering")
    assert len(results) > 0
    assert results[0]["name"] == "ggplot2-richtext-fixes"


def test_search_by_use_when():
    reg = _make_registry()
    results = reg.search("hypothesis testing")
    assert any(r["name"] == "statistical-analysis" for r in results)


def test_compact_prompt():
    reg = _make_registry()
    prompt = reg.compact_prompt()
    assert "Available Skills" in prompt
    assert "ggplot2-richtext-fixes" in prompt
    assert "Plotting" in prompt


def test_stats():
    reg = _make_registry()
    stats = reg.stats()
    assert stats["total_skills"] == 3
    assert stats["categories"] == 3
    assert stats["registries"] == 3


def test_search_top_k():
    reg = _make_registry()
    results = reg.search("analysis", top_k=1)
    assert len(results) <= 1
