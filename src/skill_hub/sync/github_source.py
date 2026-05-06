"""GitHub-based skill source — discovers and fetches skills from a repo."""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from .base import SkillSource
from ..models import SkillMeta

GITHUB_API = "https://api.github.com"


class GitHubSource(SkillSource):
    """Pull skills from a GitHub repository."""

    def __init__(self, repo: str, skill_glob: str = "*/SKILL.md",
                 token: str | None = None, cache_dir: str | None = None):
        self.name = repo
        self.repo = repo
        self.skill_glob = skill_glob
        self.cache_dir = Path(cache_dir) if cache_dir else None
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API, headers=headers, timeout=30,
        )

    def _local_cache_path(self, repo_path: str) -> Path | None:
        """Return the local cache path for a skill's SKILL.md."""
        if not self.cache_dir:
            return None
        # e.g. skills_local/garrytan--gstack/browse/SKILL.md
        safe_repo = self.repo.replace("/", "--")
        return self.cache_dir / safe_repo / repo_path

    async def list_skills(self) -> list[SkillMeta]:
        """Walk the repo tree to find SKILL.md files matching the glob pattern."""
        # Get default branch
        repo_info = (await self._client.get(f"/repos/{self.repo}")).json()
        branch = repo_info.get("default_branch", "main")

        # Get full tree
        tree_resp = await self._client.get(
            f"/repos/{self.repo}/git/trees/{branch}", params={"recursive": "1"},
        )
        tree = tree_resp.json().get("tree", [])

        # Filter by glob pattern
        pattern_parts = self.skill_glob.replace("*/", "").replace("SKILL.md", "")
        skills = []
        for item in tree:
            if item["path"].endswith("/SKILL.md"):
                skill_dir = item["path"].rsplit("/SKILL.md", 1)[0]
                # Check if it matches the glob prefix
                if self.skill_glob.startswith("*/") or self.skill_glob.startswith("**/") or \
                   skill_dir.startswith(pattern_parts.rstrip("/")):
                    skills.append(SkillMeta(
                        name=skill_dir.split("/")[-1],
                        registry=self.name,
                        source_url=f"https://github.com/{self.repo}/blob/{branch}/{item['path']}",
                        local_path=None,
                        repo_path=item["path"],
                    ))

        # Enrich with metadata by fetching each SKILL.md
        for skill in skills:
            try:
                content = await self.fetch_skill(skill)
                skill.description, skill.use_when, skill.tags, skill.category = _parse_skill_md(content)

                # Save to local cache
                cache_path = self._local_cache_path(skill.repo_path)
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(content, encoding="utf-8")
                    skill.local_path = str(cache_path.parent)
            except Exception:
                pass

        return skills

    async def fetch_skill(self, skill: SkillMeta) -> str:
        """Fetch SKILL.md content via GitHub API."""
        # Find the SKILL.md path from source_url
        path = skill.source_url.split(f"/blob/")[-1] if "/blob/" in skill.source_url else ""
        if not path:
            branch = "main"
            path = f"{skill.name}/SKILL.md"
        else:
            parts = path.split("/", 1)
            branch = parts[0]
            path = parts[1] if len(parts) > 1 else path

        resp = await self._client.get(
            f"/repos/{self.repo}/contents/{path}",
            params={"ref": branch},
            headers={"Accept": "application/vnd.github.v3.raw"},
        )
        resp.raise_for_status()
        return resp.text

    async def close(self):
        await self._client.aclose()


def _parse_skill_md(content: str) -> tuple[str, str, list[str], str]:
    """Extract metadata from a SKILL.md file's frontmatter and content."""
    description = ""
    use_when = ""
    tags = []
    category = ""

    # Parse YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.split("\n"):
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("name:"):
                pass
            elif line.startswith("tags:"):
                tag_str = line.split(":", 1)[1].strip()
                tags = [t.strip().strip("- ") for t in tag_str.split(",")]

    # Look for "Use when" or "useWhen" patterns
    uw_match = re.search(r"(?:use[_\s]when|when to use):\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if uw_match:
        use_when = uw_match.group(1).strip()

    # Fallback: use first paragraph as description
    if not description:
        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        body = re.sub(r"^#.*\n", "", body).strip()
        first_para = body.split("\n\n")[0] if body else ""
        description = first_para[:200]

    return description, use_when, tags, category
