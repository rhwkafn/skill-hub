"""Tests for the skill index."""

import json
import tempfile
from pathlib import Path

from skill_hub.indexer import SkillIndex
from skill_hub.models import SkillMeta


def test_add_and_search():
    idx = SkillIndex()
    idx.add(SkillMeta(
        name="raincloud-plot",
        registry="test",
        description="Build raincloud plots with distributions and raw points",
        use_when="User wants raincloud or half-violin plots",
        tags=["plotting", "r"],
    ))
    idx.add(SkillMeta(
        name="phylogeny-workflow",
        registry="test",
        description="Match trait data to phylogenetic trees",
        use_when="User needs phylogenetic analysis",
        tags=["ecology", "evolution"],
    ))

    results = idx.search("raincloud plot")
    assert len(results) > 0
    assert results[0][0].name == "raincloud-plot"


def test_search_by_use_when():
    idx = SkillIndex()
    idx.add(SkillMeta(
        name="some-skill",
        registry="test",
        use_when="Create scatterplots with regression lines",
    ))
    results = idx.search("scatterplot regression")
    assert len(results) > 0


def test_save_and_load(tmp_path):
    idx = SkillIndex()
    idx.add(SkillMeta(name="test-skill", registry="test", description="A test"))
    path = tmp_path / "index.json"
    idx.save(path)

    loaded = SkillIndex.load(path)
    assert "test-skill" in loaded.skills
    assert loaded.skills["test-skill"].description == "A test"


def test_list_by_category():
    idx = SkillIndex()
    idx.add(SkillMeta(name="a", registry="r", category="plotting"))
    idx.add(SkillMeta(name="b", registry="r", category="plotting"))
    idx.add(SkillMeta(name="c", registry="r", category="ecology"))

    cats = idx.list_by_category()
    assert len(cats["plotting"]) == 2
    assert len(cats["ecology"]) == 1


def test_list_by_registry():
    idx = SkillIndex()
    idx.add(SkillMeta(name="a", registry="nature-skills"))
    idx.add(SkillMeta(name="b", registry="scientific"))
    regs = idx.list_by_registry()
    assert "nature-skills" in regs
    assert "scientific" in regs


def test_summary():
    idx = SkillIndex()
    idx.add(SkillMeta(name="a", registry="r", category="cat1", use_when="do stuff"))
    summary = idx.summary()
    assert "1 skills" in summary
    assert "cat1" in summary
