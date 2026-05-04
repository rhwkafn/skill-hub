# skill-hub

**Skills-as-RAG**: A lightweight skill registry that treats agent skills like retrieval-augmented generation — index first, load on demand.

## The Problem

Multi-agent systems often load all available skills into context at startup. As skill libraries grow to hundreds of entries across multiple sources, this becomes:

- **Token-expensive**: Loading 100+ SKILL.md files wastes thousands of tokens per agent turn
- **Slow**: Parsing large skill catalogs adds latency to every inference call
- **Brittle**: Global skill lists make it hard to maintain, version, and update skills across projects

## The Solution: Skills-as-RAG

Instead of loading every skill's full content, we maintain a **lightweight searchable index** (like a RAG vector store, but for agent capabilities). Agents see only a compact catalog:

```
# Available Skills (injected into system prompt)

## Plotting
- **raincloud-plot**: Build raincloud plots with distributions and raw points
- **ggplot2-richtext-fixes**: Fix ggplot2 labels or export rendering issues

## Analysis
- **statistical-analysis**: Run statistical tests and generate reports

## Writing
- **nature-polishing**: Polish manuscripts to Nature journal standards
```

When an agent identifies a relevant skill, it calls `load_skill(name)` to fetch the full instructions — just like RAG retrieves relevant documents.

```
┌─────────────────────────────────────────────────────────┐
│                    Agent System Prompt                    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Compact Skill Catalog (index)            │    │
│  │  - name: "raincloud-plot"                        │    │
│  │    use_when: "Build raincloud plots..."          │    │
│  │  - name: "statistical-analysis"                  │    │
│  │    use_when: "Run statistical tests..."          │    │
│  │  ... (one line per skill, ~2KB total)            │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                                │
│                    search("plot")                        │
│                         │                                │
│                         ▼                                │
│              load_skill("raincloud-plot")                 │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │          Full SKILL.md (loaded on demand)        │    │
│  │  Detailed workflow, code templates, references   │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Skill Sources

This registry aggregates skills from multiple open-source repositories:

| Source | Type | Description | Skills |
|--------|------|-------------|--------|
| [codex-skills-workbench](D:/AI-agent/claude-app/codex-reaserch/codex-skills-workbench) | Local | Research workflow skills (ecology, plotting, data pipelines) | 16 |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | GitHub | Nature journal academic writing and scientific figure skills | 4+ |
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | GitHub | Comprehensive scientific research agent skills | 100+ |

### codex-skills-workbench (Local)

Skills for ecological research, data visualization, and academic workflows:

- `ggplot2-richtext-fixes` — Fix ggplot2 superscript and richtext rendering
- `hypervolume-workflow` — Ecological niche and trait-space analysis
- `keyword-literature-download` — Search and download scholarly papers
- `phylogeny-workflow` — Phylogenetic tree matching and visualization
- `raincloud-plot-guide` — Build raincloud plots
- `weighted-data-pipeline` — End-to-end weighted data workflows
- ... and 10 more

### nature-skills (GitHub)

Skills aligned with Nature journal standards:

- `nature-figure` — Scientific figure creation following Nature guidelines
- `nature-data` — Data processing and analysis for Nature submissions
- `nature-paper2ppt` — Convert papers to presentation slides
- `nature-polishing` — Manuscript polishing for Nature standards

### scientific-agent-skills (GitHub)

A massive collection covering research, engineering, and analysis:

- `scanpy`, `anndata`, `scvelo` — Single-cell analysis
- `rdkit`, `deepchem` — Molecular chemistry
- `pytorch-lightning`, `transformers` — ML/DL
- `statistical-analysis`, `exploratory-data-analysis` — Statistics
- `scientific-writing`, `scientific-visualization` — Publishing
- `literature-review`, `paper-lookup` — Literature
- ... and 80+ more

## Architecture

```
skill-hub/
├── config/
│   └── registries.yaml       # Source definitions (repos, paths, globs)
├── src/skill_hub/
│   ├── models.py              # SkillMeta data model
│   ├── indexer/
│   │   └── skill_index.py     # The searchable index (like a vector store)
│   ├── sync/
│   │   ├── base.py            # Abstract skill source
│   │   ├── github_source.py   # Pull skills from GitHub repos
│   │   ├── local_source.py    # Pull skills from local directories
│   │   └── syncer.py          # Multi-source orchestrator
│   ├── registry/
│   │   └── skill_registry.py  # Agent-facing API (search + load)
│   └── cli/
│       └── main.py            # CLI: sync, search, info, prompt
└── tests/                     # Unit tests
```

## Quick Start

```bash
pip install -e ".[dev]"

# Sync skills from all configured sources
python -m skill_hub.cli.main sync

# Search for a skill
python -m skill_hub.cli.main search "phylogenetic tree"

# Generate compact prompt for agent injection
python -m skill_hub.cli.main prompt

# Show index stats
python -m skill_hub.cli.main info
```

## Usage in Your Agent

```python
from skill_hub.indexer import SkillIndex
from skill_hub.registry import SkillRegistry
from skill_hub.sync import GitHubSource, LocalSource

# Load the pre-built index
index = SkillIndex.load("skill_index.json")
registry = SkillRegistry(index, sources=[
    GitHubSource("K-Dense-AI/scientific-agent-skills"),
    LocalSource("D:/AI-agent/claude-app/codex-reaserch/codex-skills-workbench"),
])

# Inject compact catalog into agent system prompt
system_prompt = f"""
You are a research assistant.
{registry.compact_prompt()}
When you need a skill, call load_skill(name).
"""

# Agent searches for relevant skills
results = registry.search("create a phylogenetic tree")
# [{'name': 'phylogeny-workflow', 'score': 0.82, ...}]

# Agent loads only the skill it needs
content = await registry.load("phylogeny-workflow")
# Full SKILL.md content — only loaded when actually needed
```

## Adding New Sources

Edit `config/registries.yaml`:

```yaml
registries:
  - name: my-new-source
    type: github
    repo: "owner/repo-name"
    skill_glob: "skills/*/SKILL.md"
```

Then re-sync: `python -m skill_hub.cli.main sync`

## How This Differs from Global Skill Loading

| Approach | Context Cost | Latency | Scalability |
|----------|-------------|---------|-------------|
| Global load all | O(n × skill_size) | High on every turn | Breaks at ~50 skills |
| Skills-as-RAG (this) | O(n × one_line) + O(1) per use | Low baseline, spike only when needed | Scales to 1000+ |

The compact catalog for 120+ skills is roughly **3KB**. Loading all SKILL.md files would be **200KB+**.

## License

MIT
