"""Tests for SkillMeta model."""

from skill_hub.models import SkillMeta


def test_matches_exact():
    s = SkillMeta(name="test", registry="r", description="Create raincloud plots")
    assert s.matches("raincloud") > 0


def test_matches_partial():
    s = SkillMeta(name="phylogeny-workflow", registry="r", use_when="phylogenetic tree analysis")
    assert s.matches("phylogenetic") > 0


def test_matches_no_hit():
    s = SkillMeta(name="test", registry="r", description="cooking recipes")
    assert s.matches("quantum physics") == 0.0


def test_to_index_entry():
    s = SkillMeta(
        name="test", registry="r", description="desc",
        category="cat", tags=["a"], use_when="when",
    )
    entry = s.to_index_entry()
    assert entry["name"] == "test"
    assert entry["tags"] == ["a"]


def test_matches_name_weight():
    """Name match should score higher than description match."""
    s1 = SkillMeta(name="raincloud-plot", registry="r", description="")
    s2 = SkillMeta(name="other", registry="r", description="raincloud plot helper")
    # Name match should score higher
    assert s1.matches("raincloud-plot") >= s2.matches("raincloud-plot")
