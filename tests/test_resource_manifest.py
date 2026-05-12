"""Tests for resource manifest and dependency detection."""

import json

from skill_hub.models import SkillMeta
from skill_hub.utils import build_resource_manifest
from skill_hub.sync.github_source import _detect_resource_deps


class TestBuildResourceManifest:
    """Tests for build_resource_manifest utility."""

    def test_detects_backtick_paths(self, tmp_path):
        """Should find backtick-quoted paths referencing scripts/, references/, etc."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "init.py").write_text("print('hi')")

        content = """
# My Skill

Run `scripts/init.py` to start.
Read `references/workflow/intake.md` for details.
"""
        manifest = build_resource_manifest(skill_dir, content)

        assert "scripts/init.py" in manifest
        assert manifest["scripts/init.py"]["exists"] is True
        assert "references/workflow/intake.md" in manifest
        assert manifest["references/workflow/intake.md"]["exists"] is False

    def test_detects_command_paths(self, tmp_path):
        """Should find paths after python/node/bash commands."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "workspace").mkdir()
        (skill_dir / "scripts" / "workspace" / "init.py").write_text("")

        content = """
Run this:
```bash
python scripts/workspace/init.py .
```
"""
        manifest = build_resource_manifest(skill_dir, content)

        assert "scripts/workspace/init.py" in manifest
        assert manifest["scripts/workspace/init.py"]["exists"] is True

    def test_ignores_non_resource_paths(self, tmp_path):
        """Should not pick up paths outside resource_dirs."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        content = """
Run `src/main.py` and check `docs/README.md`.
"""
        manifest = build_resource_manifest(skill_dir, content)
        assert len(manifest) == 0

    def test_absolute_paths_are_correct(self, tmp_path):
        """Absolute paths in manifest should resolve correctly."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "foo.md").write_text("content")

        content = "Read `references/foo.md`."
        manifest = build_resource_manifest(skill_dir, content)

        expected = str(skill_dir / "references" / "foo.md")
        assert manifest["references/foo.md"]["absolute"] == expected

    def test_empty_content(self, tmp_path):
        """Empty content should produce empty manifest."""
        manifest = build_resource_manifest(tmp_path, "")
        assert manifest == {}


class TestDetectResourceDeps:
    """Tests for _detect_resource_deps during sync."""

    def test_detects_requires_clone(self, tmp_path):
        """Skills referencing scripts/ should be marked requires_clone."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        content = """
# My Skill

Run `scripts/build.py` to generate output.
"""
        requires, deps = _detect_resource_deps(skill_dir, content)
        assert requires is True
        assert deps == []

    def test_no_deps_when_self_contained(self, tmp_path):
        """Self-contained skills (no script refs) should not require clone."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        content = """
# My Skill

Just follow these instructions. No external files needed.
"""
        requires, deps = _detect_resource_deps(skill_dir, content)
        assert requires is False

    def test_reads_requirements_txt(self, tmp_path):
        """Should parse requirements.txt for pip dependencies."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        req = skill_dir / "requirements.txt"
        req.write_text("python-docx>=0.8\npypdf>=3.0\n# comment\n-r dev.txt\n")

        content = "Run `scripts/build.py`."
        requires, deps = _detect_resource_deps(skill_dir, content)

        assert requires is True
        assert "python-docx" in deps
        assert "pypdf" in deps
        assert "# comment" not in deps
        assert "-r dev.txt" not in deps

    def test_handles_missing_requirements(self, tmp_path):
        """No requirements.txt should give empty deps list."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        content = "Run `scripts/build.py`."
        _, deps = _detect_resource_deps(skill_dir, content)
        assert deps == []

    def test_strips_version_specifiers(self, tmp_path):
        """Should strip version specifiers from dependency names."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        req = skill_dir / "requirements.txt"
        req.write_text("scikit-learn>=1.0,<2.0\nhttpx[socks]\n")

        content = "Run `scripts/build.py`."
        _, deps = _detect_resource_deps(skill_dir, content)

        assert "scikit-learn" in deps
        assert "httpx" in deps


class TestSkillMetaNewFields:
    """Tests for the new requires_clone and pip_deps fields."""

    def test_default_values(self):
        s = SkillMeta(name="test", registry="r")
        assert s.requires_clone is False
        assert s.pip_deps == []

    def test_to_index_entry_includes_new_fields(self):
        s = SkillMeta(
            name="test", registry="r",
            requires_clone=True,
            pip_deps=["python-docx", "pypdf"],
        )
        entry = s.to_index_entry()
        assert entry["requires_clone"] is True
        assert entry["pip_deps"] == ["python-docx", "pypdf"]

    def test_save_load_roundtrip(self, tmp_path):
        """New fields should survive index save/load."""
        from skill_hub.indexer import SkillIndex

        idx = SkillIndex()
        idx.add(SkillMeta(
            name="thesis-workbench",
            registry="test",
            requires_clone=True,
            pip_deps=["python-docx"],
        ))
        path = tmp_path / "index.json"
        idx.save(path)

        loaded = SkillIndex.load(path)
        skill = loaded.skills["thesis-workbench"]
        assert skill.requires_clone is True
        assert skill.pip_deps == ["python-docx"]

    def test_backwards_compatible_load(self, tmp_path):
        """Loading an old index without new fields should use defaults."""
        from skill_hub.indexer import SkillIndex

        # Simulate old index format
        old_data = [{"name": "old-skill", "registry": "r", "description": "old"}]
        path = tmp_path / "index.json"
        path.write_text(json.dumps(old_data), encoding="utf-8")

        loaded = SkillIndex.load(path)
        skill = loaded.skills["old-skill"]
        assert skill.requires_clone is False
        assert skill.pip_deps == []
