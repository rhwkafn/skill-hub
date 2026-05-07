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

    async def list_skills(self, skip_names: set[str] | None = None) -> list[SkillMeta]:
        """Walk the repo tree to find SKILL.md files matching the glob pattern.

        Args:
            skip_names: Set of skill names to skip (already in index).
                        Skips the expensive GitHub API fetch for these skills.
        """
        skip = skip_names or set()

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
        skipped = 0
        for item in tree:
            if item["path"].endswith("/SKILL.md"):
                skill_dir = item["path"].rsplit("/SKILL.md", 1)[0]
                # Check if it matches the glob prefix
                if self.skill_glob.startswith("*/") or self.skill_glob.startswith("**/") or \
                   skill_dir.startswith(pattern_parts.rstrip("/")):
                    name = skill_dir.split("/")[-1]
                    if name in skip:
                        skipped += 1
                        continue
                    skills.append(SkillMeta(
                        name=name,
                        registry=self.name,
                        source_url=f"https://github.com/{self.repo}/blob/{branch}/{item['path']}",
                        local_path=None,
                        repo_path=item["path"],
                    ))

        if skipped:
            print(f"    [{self.name}] skipped {skipped} cached skills (API fetch avoided)")

        # Enrich with metadata by fetching each SKILL.md
        for skill in skills:
            try:
                content = await self.fetch_skill(skill)
                meta = _parse_skill_md(content)
                skill.description = meta["description"]
                skill.use_when = meta["use_when"]
                skill.tags = meta["tags"]
                skill.category = meta["category"]
                skill.mode = meta["mode"]
                skill.tools_required = meta["tools_required"]
                skill.has_hooks = meta["has_hooks"]
                skill.triggers = meta["triggers"]
                skill.output_formats = meta["output_formats"]
                skill.input_types = meta["input_types"]
                skill.domain = meta["domain"]

                # Build decision card from the content we already have
                skill.build_decision_card(content)

                # Save to local cache
                cache_path = self._local_cache_path(skill.repo_path)
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(content, encoding="utf-8")
                    skill.local_path = str(cache_path.parent)
            except Exception as e:
                print(f"    [{self.name}] WARN: failed to fetch {skill.name}: {type(e).__name__}: {e}")

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


def _parse_skill_md(content: str) -> dict:
    """Extract metadata from a SKILL.md file's frontmatter and content.

    Returns a dict with keys: description, use_when, tags, category,
    mode, tools_required, has_hooks, triggers.
    """
    from ..models import SkillMode

    # Strip BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]

    description = ""
    use_when = ""
    tags = []
    category = ""
    triggers = []
    tools_required = []
    has_hooks = False
    mode = SkillMode.ON_DEMAND

    # Parse YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        lines = fm.split("\n")

        current_key = None
        current_list = []
        block_scalar = False
        block_indent = 0

        for line in lines:
            # Handle block scalar continuation (| or >)
            if block_scalar:
                if not line.strip():
                    current_list.append("")
                    continue
                indent = len(line) - len(line.lstrip())
                if block_indent is None:
                    block_indent = indent
                if indent >= block_indent:
                    current_list.append(line.strip())
                    continue
                else:
                    # Block scalar ended
                    block_scalar = False
                    if current_key == "description":
                        description = " ".join(v for v in current_list if v).strip()
                    current_key = None
                    current_list = []

            stripped = line.strip()

            # Top-level key: value lines
            key_match = re.match(r"^(\w[\w-]*):\s*(.*)", stripped)
            if key_match:
                key = key_match.group(1)
                value = key_match.group(2).strip()

                # Flush previous list field
                if current_key and current_list:
                    if current_key == "triggers":
                        triggers = current_list
                    elif current_key == "allowed-tools":
                        tools_required = current_list
                    elif current_key == "tags":
                        tags = current_list
                    current_list = []
                    current_key = None

                if key == "description":
                    if value in ("|", ">", "|+", "|-", ">+", ">-"):
                        # Block scalar — collect continuation lines
                        block_scalar = True
                        block_indent = None  # will be set on first content line
                        current_key = "description"
                        current_list = []
                    elif value:
                        description = value.strip("'\"")
                elif key == "triggers":
                    if not value:
                        current_key = "triggers"
                        current_list = []
                    else:
                        triggers = [v.strip() for v in value.split(",")]
                elif key == "allowed-tools":
                    if not value:
                        current_key = "allowed-tools"
                        current_list = []
                    else:
                        tools_required = [v.strip() for v in value.split(",")]
                elif key == "tags":
                    if not value:
                        current_key = "tags"
                        current_list = []
                    else:
                        tags = [v.strip().strip("- ") for v in value.split(",")]
                elif key == "hooks":
                    has_hooks = True
                # name, version — skip
                continue

            # List continuation: "  - item"
            if current_key and stripped.startswith("- "):
                item = stripped[2:].strip().strip("'\"")
                if block_scalar and block_indent is None:
                    block_indent = len(line) - len(line.lstrip()) - 2
                current_list.append(item)
                continue

            # Block scalar first content line (to determine indent)
            if block_scalar and block_indent is None and stripped:
                block_indent = len(line) - len(line.lstrip())
                current_list.append(stripped)
                continue

        # Flush remaining
        if block_scalar and current_key == "description":
            description = " ".join(v for v in current_list if v).strip()
        if current_key == "triggers":
            triggers = current_list
        elif current_key == "allowed-tools":
            tools_required = current_list
        elif current_key == "tags":
            tags = current_list

    # Look for "Use when" or "useWhen" patterns in body
    uw_match = re.search(r"(?:use[_\s]when|when to use):\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
    if uw_match:
        use_when = uw_match.group(1).strip()

    # Fallback: use first paragraph as description
    if not description:
        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        body = re.sub(r"^#.*\n", "", body).strip()
        first_para = body.split("\n\n")[0] if body else ""
        description = first_para[:200]

    # Infer mode from metadata
    if has_hooks or "hooks" in content.lower() and "PreToolUse" in content:
        mode = SkillMode.GLOBAL
    elif any(t in description.lower() for t in ["combin", "alongside", "compose"]):
        mode = SkillMode.COMPOSE

    # Extract capabilities from content
    output_formats, input_types, domain = _extract_capabilities(content, description)

    return {
        "description": description,
        "use_when": use_when,
        "tags": tags,
        "category": category,
        "mode": mode,
        "tools_required": tools_required,
        "has_hooks": has_hooks,
        "triggers": triggers,
        "output_formats": output_formats,
        "input_types": input_types,
        "domain": domain,
    }


def _extract_capabilities(content: str, description: str) -> tuple[list[str], list[str], str]:
    """Extract output formats, input types, and domain from skill content.

    Uses keyword detection — no ML, no API, just pattern matching.
    """
    text = (content + " " + description).lower()

    # Output formats
    format_patterns = {
        "pptx": [".pptx", "powerpoint", "ppt", "slides", "presentation", "beamer"],
        "html": [".html", "html page", "web page", "webpage", "landing page"],
        "pdf": [".pdf", "pdf report", "generate pdf", "create pdf", "latex pdf"],
        "docx": [".docx", "word document", "docx file"],
        "csv": [".csv", "csv file", "export csv"],
        "xlsx": [".xlsx", ".xls", "excel", "spreadsheet"],
        "png": [".png", ".jpg", ".svg", "image", "figure", "plot", "chart", "diagram"],
        "md": [".md", "markdown", "readme", "documentation"],
        "json": [".json", "json output", "json file"],
        "api": ["rest api", "graphql", "endpoint", "openapi", "swagger"],
        "cli": ["cli tool", "command line", "argparse", "click"],
    }

    output_formats = []
    for fmt, patterns in format_patterns.items():
        if any(p in text for p in patterns):
            output_formats.append(fmt)

    # Input types
    input_patterns = {
        "paper": ["paper", "manuscript", "journal", "publication", "research paper"],
        "data": ["dataset", "dataframe", "csv", "data file", "tabular"],
        "code": ["codebase", "source code", "repository", "code review"],
        "image": ["image", "photo", "screenshot", "figure"],
        "sequence": ["sequence", "protein", "dna", "rna", "amino acid", "genome"],
        "molecule": ["molecule", "compound", "smiles", "chemical", "drug"],
    }

    input_types = []
    for itype, patterns in input_patterns.items():
        if any(p in text for p in patterns):
            input_types.append(itype)

    # Domain
    domain = ""
    domain_patterns = {
        "science": ["research", "scientific", "journal", "paper", "publication", "hypothesis", "experiment"],
        "biology": ["rna", "dna", "protein", "cell", "gene", "genomic", "phylogen", "molecular"],
        "chemistry": ["molecule", "compound", "chemical", "drug", "smiles", "docking"],
        "data-science": ["machine learning", "neural", "model training", "dataset", "pandas", "sklearn"],
        "engineering": ["deploy", "ci/cd", "testing", "refactor", "code review", "api"],
        "writing": ["writing", "manuscript", "polish", "abstract", "bibliography", "citation"],
    }

    for dom, patterns in domain_patterns.items():
        hits = sum(1 for p in patterns if p in text)
        if hits >= 2:
            domain = dom
            break

    return output_formats, input_types, domain
