"""GitHub-based skill source — discovers and fetches skills via git clone."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from .base import SkillSource
from ..models import SkillMeta


class GitHubSource(SkillSource):
    """Pull skills from a GitHub repository using shallow git clone.

    No GitHub API calls — avoids rate limits entirely.
    Clones (or pulls) the repo locally, then globs for SKILL.md files.
    """

    def __init__(self, repo: str, skill_glob: str = "*/SKILL.md",
                 token: str | None = None, cache_dir: str | None = None):
        self.name = repo
        self.repo = repo
        self.skill_glob = skill_glob
        self._token = token  # unused, kept for config compat
        # Clone target: skills_local/owner--repo/
        safe_repo = repo.replace("/", "--")
        if cache_dir:
            self._clone_dir = Path(cache_dir) / safe_repo
        else:
            self._clone_dir = Path("skills_local") / safe_repo

    async def _run_git(self, *args: str) -> None:
        """Run a git command, raise on failure."""
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git failed ({proc.returncode}): {stderr.decode().strip()}")

    async def _clone_or_pull(self) -> None:
        """Shallow clone if missing, otherwise fast-forward pull."""
        if (self._clone_dir / ".git").exists():
            try:
                await self._run_git(
                    "git", "-C", str(self._clone_dir),
                    "pull", "--ff-only", "--depth", "1",
                )
            except RuntimeError:
                # Diverged (e.g. remote force-pushed) — hard-reset to origin
                await self._run_git(
                    "git", "-C", str(self._clone_dir),
                    "fetch", "--depth", "1", "origin", "main",
                )
                await self._run_git(
                    "git", "-C", str(self._clone_dir),
                    "reset", "--hard", "origin/main",
                )
        else:
            # Remove stale non-git directory (e.g. from old tarball cache)
            if self._clone_dir.exists():
                import shutil
                shutil.rmtree(self._clone_dir)
            self._clone_dir.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://github.com/{self.repo}.git"
            await self._run_git("git", "clone", "--depth", "1", url, str(self._clone_dir))

    def _find_skill_mds(self) -> list[Path]:
        """Glob for SKILL.md files matching the configured pattern."""
        results = sorted(self._clone_dir.glob(self.skill_glob))
        if not results:
            # Fallback: try **/SKILL.md if the configured glob misses
            results = sorted(self._clone_dir.glob("**/SKILL.md"))
        return results

    async def list_skills(self, skip_names: set[str] | None = None) -> list[SkillMeta]:
        """Clone/pull the repo and discover SKILL.md files.

        Args:
            skip_names: Set of skill names to skip (already in index).
                        Skipped skills still exist on disk but are not returned.
        """
        skip = skip_names or set()
        await self._clone_or_pull()

        skill_mds = self._find_skill_mds()
        skills = []
        skipped = 0

        for smd in skill_mds:
            # Derive skill name from parent directory
            skill_dir = smd.parent
            name = skill_dir.name
            if name in skip:
                skipped += 1
                continue

            rel_path = smd.relative_to(self._clone_dir)
            skills.append(SkillMeta(
                name=name,
                registry=self.name,
                source_url=f"https://github.com/{self.repo}/blob/main/{rel_path}",
                local_path=str(skill_dir),
                repo_path=str(rel_path),
            ))

        if skipped:
            print(f"    [{self.name}] skipped {skipped} cached skills")

        # Parse metadata from local SKILL.md files
        for skill in skills:
            try:
                skill_dir = Path(skill.local_path)
                smd = skill_dir / "SKILL.md"
                skill_content = smd.read_text(encoding="utf-8")

                meta = _parse_skill_md(skill_content)
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
                skill.phase = meta["phase"]
                skill.execution_mode = meta["execution_mode"]

                # Detect resource dependencies
                skill.requires_clone, skill.pip_deps = _detect_resource_deps(skill_dir, skill_content)

                skill.build_decision_card(skill_content)

                file_count = sum(1 for _ in skill_dir.rglob("*") if _.is_file())
                dep_tag = " [resources]" if skill.requires_clone else ""
                print(f"    [{self.name}] {skill.name}/ ({file_count} files){dep_tag}")

            except Exception as e:
                print(f"    [{self.name}] WARN: failed to parse {skill.name}: {type(e).__name__}: {e}")

        return skills

    async def fetch_skill(self, skill: SkillMeta) -> str:
        """Read SKILL.md from the local clone."""
        smd = Path(skill.local_path) / "SKILL.md"
        return smd.read_text(encoding="utf-8")

    async def close(self):
        """No-op — no persistent connections."""
        pass


def _parse_skill_md(content: str) -> dict:
    """Extract metadata from a SKILL.md file's frontmatter and content.

    Returns a dict with keys: description, use_when, tags, category,
    mode, tools_required, has_hooks, triggers.
    """
    from ..models import ExecutionMode, SkillMode, SkillPhase

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

    # Auto-extract tags from body when frontmatter has none
    if not tags:
        tags = _auto_extract_tags(content, description)

    # Infer mode from metadata
    if has_hooks or "hooks" in content.lower() and "PreToolUse" in content:
        mode = SkillMode.GLOBAL
    elif any(t in description.lower() for t in ["combin", "alongside", "compose"]):
        mode = SkillMode.COMPOSE

    # Extract capabilities from content
    output_formats, input_types, domain = _extract_capabilities(content, description)

    # Infer phase from content + metadata
    phase = _infer_phase(content, description)

    # Infer execution mode
    execution_mode = _infer_execution_mode(content, description)

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
        "phase": phase,
        "execution_mode": execution_mode,
    }


def _infer_phase(content: str, description: str):
    """Infer which workflow phase a skill belongs to from its content."""
    from ..models import SkillPhase
    text = (content + " " + description).lower()

    # Order matters: more specific patterns first
    phase_patterns = {
        SkillPhase.DEFINE: ["spec", "requirement", "brainstorm", "ideation", "brief"],
        SkillPhase.PLAN: ["plan", "task breakdown", "architecture", "roadmap", "estimat"],
        SkillPhase.BUILD: ["implement", "creat", "writ", "develop", "build", "generat", "produc", "cod"],
        SkillPhase.VERIFY: ["test", "debug", "qa", "verif", "validat", "inspect", "diagnos"],
        SkillPhase.REVIEW: ["code review", "security audit", "quality", "refactor", "simplif", "hardening"],
        SkillPhase.SHIP: ["deploy", "release", "ci/cd", "cicd", "documentation", "adr", "git workflow", "launch", "migrat"],
    }

    best_phase = SkillPhase.EXECUTE
    best_hits = 0
    for phase, patterns in phase_patterns.items():
        hits = sum(1 for p in patterns if (_has_word(text, p) if " " not in p else p in text))
        if hits > best_hits:
            best_hits = hits
            best_phase = phase

    return best_phase


def _infer_execution_mode(content: str, description: str):
    """Infer execution mode from content."""
    from ..models import ExecutionMode
    text = (content + " " + description).lower()

    if any(kw in text for kw in ["step-by-step", "sequential", "serial", "in order", "first.*then"]):
        return ExecutionMode.SERIAL
    if any(kw in text for kw in ["parallel", "concurrent", "independent", "simultaneous"]):
        return ExecutionMode.PARALLEL

    return ExecutionMode.INDEPENDENT


def _has_word(text: str, word: str) -> bool:
    """Check if word exists as a whole word in text (not substring)."""
    import re
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))


def _infer_domain(content: str, description: str, tags: list[str]) -> str:
    """Infer skill domain from SKILL.md content, description, and tags.

    Returns one of: engineering, science, writing, marketing, data-science, design, biology, chemistry.
    Empty string if no strong signal.
    """
    text = (content + " " + description + " " + " ".join(tags)).lower()

    domain_keywords = {
        "engineering": [
            "api", "rest", "graphql", "microservice", "backend", "server", "deploy",
            "kubernetes", "docker", "ci/cd", "pipeline", "refactor", "debug",
            "unit test", "integration test", "authentication", "middleware",
            "database", "sql", "typescript", "javascript", "golang", "rust",
        ],
        "science": [
            "biology", "chemistry", "physics", "genomics", "phylogenetic", "rna",
            "protein", "molecule", "sequencing", "crispr", "bioinformatics",
            "experiment", "hypothesis", "clinical", "medical", "drug",
            "microscopy", "pathology", "ecology", "neuroscience",
        ],
        "biology": [
            "single cell", "scrnaseq", "flow cytometry", "histology",
            "tissue", "organoid", "cell culture", "western blot",
        ],
        "writing": [
            "blog", "article", "copywriting", "content writing", "manuscript",
            "academic writing", "creative writing", "newsletter", "editorial",
            "proofreading", "thesis", "dissertation",
        ],
        "marketing": [
            "seo", "sem", "conversion rate", "funnel", "landing page",
            "email marketing", "social media", "campaign", "a/b test",
            "growth", "customer research", "brand", "content marketing",
            "ppc", "ads", "copywriting",
        ],
        "data-science": [
            "data analysis", "visualization", "dashboard", "pandas", "dataframe",
            "etl", "data pipeline", "machine learning", "deep learning",
            "neural network", "model training", "prediction", "classification",
            "regression", "clustering", "feature engineering",
        ],
        "design": [
            "ui design", "ux design", "mockup", "wireframe", "figma",
            "prototype", "user interface", "user experience", "layout",
            "typography", "responsive design", "slide", "presentation",
            "deck", "powerpoint", "pptx",
        ],
    }

    best_domain = ""
    best_hits = 0
    for domain, keywords in domain_keywords.items():
        hits = sum(1 for kw in keywords if (_has_word(text, kw) if " " not in kw else kw in text))
        if hits > best_hits:
            best_hits = hits
            best_domain = domain

    return best_domain if best_hits >= 2 else ""


def _auto_extract_tags(content: str, description: str) -> list[str]:
    """Extract top keywords from SKILL.md body as auto-tags.

    Uses word frequency (not TF-IDF — single document, IDF=1) to find
    the most prominent terms. Only runs when frontmatter has no explicit tags.
    Returns up to 8 tags.
    """
    from collections import Counter

    # Strip frontmatter and markdown formatting aggressively
    body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
    body = re.sub(r"^#{1,6}\s+", "", body, flags=re.MULTILINE)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)  # markdown links
    body = re.sub(r"[`*_~>]", "", body)  # inline formatting
    body = re.sub(r"```[\s\S]*?```", " ", body)  # code blocks — replace with space
    body = re.sub(r"<[^>]+>", " ", body)  # HTML tags
    body = re.sub(r"\$[A-Z_]+", "", body)  # $VARIABLE placeholders
    body = re.sub(r"--[a-z-]+", "", body)  # CLI flags like --force
    body = re.sub(r"\b[a-z]+/[a-z]+\b", "", body)  # paths like src/utils
    body = body.strip()

    if len(body) < 50:
        return []

    # Extract words (3+ chars) and bigrams
    words = re.findall(r"(?u)\b[a-zA-Z][a-zA-Z-]{2,}\b", body.lower())
    bigrams = [f"{a} {b}" for a, b in zip(words, words[1:])]

    # Generic terms, code tokens, tool names, CLI artifacts — skip these
    skip = {
        "skill", "use", "when", "user", "file", "this", "that",
        "should", "will", "can", "may", "must", "need", "want",
        "using", "used", "make", "also", "just", "like", "one",
        "get", "set", "run", "first", "step", "follow", "bundled",
        "workflow", "invoke", "invoked", "explicitly", "only",
        "create", "provide", "allow", "ensure", "return", "check",
        "include", "support", "default", "option", "value", "type",
        "based", "simple", "specific", "different", "available",
        "example", "command", "output", "result", "content",
        "does", "currently", "note", "original", "current", "guide",
        # CLI / tool artifacts
        "bash", "bin", "claude", "claude skills", "dev", "main",
        "branch", "node", "python", "pip", "npm", "yarn",
        "stdout", "stderr", "stdin", "exit", "arg", "args",
        "flag", "flags", "cli", "cmd", "shell", "terminal",
        "bundled workflow", "invoke skill", "explicitly invoke",
        "workflow step", "skill invoke",
    }

    # English stopwords (inlined to avoid nltk dependency)
    stopwords = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her",
        "she", "or", "an", "will", "my", "one", "all", "would", "there",
        "their", "what", "so", "up", "out", "if", "about", "who", "get",
        "which", "go", "me", "when", "make", "can", "like", "time", "no",
        "just", "him", "know", "take", "people", "into", "year", "your",
        "good", "some", "could", "them", "see", "other", "than", "then",
        "now", "look", "only", "come", "its", "over", "think", "also",
        "back", "after", "use", "two", "how", "our", "work", "first",
        "well", "way", "even", "new", "want", "because", "any", "these",
        "give", "day", "most", "us", "is", "are", "was", "were", "been",
        "has", "had", "did", "does", "doing", "done", "being",
    }

    counter = Counter()
    for w in words:
        if w not in skip and w not in stopwords and len(w) > 3:
            counter[w] += 1
    for bg in bigrams:
        if bg not in skip:
            counter[bg] += 1

    # Take top by frequency, prefer words over bigrams when tied
    tags = [tag for tag, _ in counter.most_common(30)]
    # Filter: prefer longer/more specific terms
    tags = [t for t in tags if len(t) > 3 or " " in t]
    return tags[:8]


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
        if any((_has_word(text, p) if " " not in p else p in text) for p in patterns):
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
        if any((_has_word(text, p) if " " not in p else p in text) for p in patterns):
            input_types.append(itype)

    # Domain — use word boundary matching for single words to avoid
    # false positives like "generate" matching "gene" + "rna"
    domain = ""
    domain_patterns = {
        "science": ["research", "scientific", "journal", "paper", "publication", "hypothesis", "experiment", "peer review", "arxiv"],
        "biology": ["rna", "dna", "protein", "cell", "gene", "genomic", "phylogen", "molecular", "sequencing", "crispr", "bioinformatic", "microscop", "patholog", "single cell", "flow cytometry"],
        "chemistry": ["molecule", "compound", "chemical", "drug", "smiles", "docking", "reaction", "solvent", "catalyst"],
        "data-science": ["machine learning", "neural", "model training", "dataset", "pandas", "sklearn", "visualization", "dashboard", "data pipeline", "etl", "feature engineering", "classification", "regression", "clustering", "deep learning", "tensorflow", "pytorch"],
        "engineering": ["deploy", "ci/cd", "testing", "refactor", "code review", "api", "microservice", "backend", "server", "kubernetes", "docker", "database", "authentication", "middleware", "rest api", "graphql", "devops", "sre"],
        "writing": ["writing", "manuscript", "polish", "abstract", "bibliography", "citation", "thesis", "dissertation", "blog", "article", "editorial", "proofreading", "copywriting", "newsletter"],
        "marketing": ["marketing", "seo", "ad copy", "landing page", "conversion", "campaign", "funnel", "email marketing", "social media", "growth", "ab test", "customer research", "brand", "ppc", "content marketing"],
        "design": ["ui design", "ux design", "mockup", "wireframe", "figma", "prototype", "user interface", "user experience", "layout", "typography", "responsive", "slide", "presentation", "deck", "powerpoint", "pptx"],
    }

    for dom, patterns in domain_patterns.items():
        hits = sum(1 for p in patterns if (_has_word(text, p) if " " not in p else p in text))
        if hits >= 2:
            domain = dom
            break

    # Fallback: if no domain with >=2 hits, try _infer_domain with relaxed threshold
    if not domain:
        domain = _infer_domain(content, description, [])

    return output_formats, input_types, domain


def _detect_resource_deps(skill_dir: Path, content: str) -> tuple[bool, list[str]]:
    """Detect whether a skill needs its full repo directory (not just SKILL.md).

    Scans SKILL.md for references to local directories (scripts/, references/, assets/)
    and Python import patterns that imply third-party dependencies.

    Returns:
        (requires_clone, pip_deps)
    """
    from ..utils import _find_resource_refs

    referenced_dirs = {ref.split("/")[0] for ref in _find_resource_refs(content)}
    requires_clone = len(referenced_dirs) > 0

    # Detect pip dependencies from requirements.txt if it exists
    pip_deps: list[str] = []
    req_file = skill_dir / "requirements.txt"
    if req_file.exists():
        try:
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    # Strip version specifiers: "python-docx>=0.8" -> "python-docx"
                    dep = re.split(r'[><=!~\[]', line)[0].strip()
                    if dep:
                        pip_deps.append(dep)
        except OSError:
            pass

    return requires_clone, pip_deps
