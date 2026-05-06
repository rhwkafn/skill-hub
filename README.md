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
| [codex-skills-workbench](https://github.com/Jinze-Lee/codex-skills-workbench) | GitHub | Open-source version of the above, same structure | 16 |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | GitHub | Nature journal academic writing and scientific figure skills | 4+ |
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | GitHub | Comprehensive scientific research agent skills | 136 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | GitHub | Production engineering skills (testing, CI/CD, security, code review) | 21 |
| [garrytan/gstack](https://github.com/garrytan/gstack) | GitHub | Headless browser QA, design review, deployment testing, and agent workflow skills | 50 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | GitHub | Real engineering skills — TDD, diagnosis, prototyping, architecture, productivity | 27 |

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

### addyosmani/agent-skills (GitHub)

Production-grade engineering skills by Addy Osmani:

- `code-review-and-quality` — Code review, linting, quality gates
- `test-driven-development` — TDD workflow and test strategy
- `ci-cd-and-automation` — CI/CD pipeline design and automation
- `security-and-hardening` — Security auditing and hardening
- `performance-optimization` — Profiling and optimization patterns
- `api-and-interface-design` — API design and contract-driven development
- `debugging-and-error-recovery` — Systematic debugging methodology
- `frontend-ui-engineering` — UI component architecture and patterns
- ... and 13 more

### garrytan/gstack (GitHub)

Garry Tan's gstack — a comprehensive agent skill framework for QA, design review, and deployment workflows:

- `browse` — Headless browser navigation, interaction, and screenshot capture
- `qa` / `qa-only` — Quality assurance testing and verification workflows
- `design-review` / `design-html` / `design-consultation` — Design review and feedback loops
- `ship` / `land-and-deploy` — Deployment and release management
- `review` / `devex-review` / `plan-eng-review` — Multi-perspective code and architecture reviews
- `investigate` / `learn` — Systematic debugging and knowledge acquisition
- `guard` / `freeze` / `unfreeze` — Workflow state management and protection
- `context-save` / `context-restore` — Session context persistence across agent runs
- `skillify` — Convert any workflow into a reusable skill
- ... and 38 more

### mattpocock/skills (GitHub)

Matt Pocock's "Skills For Real Engineers" — small, composable, production-grade engineering skills:

- `tdd` — Test-driven development workflow with red-green-refactor cycle
- `diagnose` — Systematic debugging with human-in-the-loop escalation
- `prototype` — Rapid prototyping with logic and UI separation
- `improve-codebase-architecture` — Architecture improvement with interface design and deepening
- `grill-with-docs` — Documentation-driven code review with ADR and context formats
- `triage` — Issue triage and prioritization
- `to-prd` / `to-issues` — Convert ideas to PRDs and issues
- `zoom-out` — High-level codebase analysis and refactoring plans
- `caveman` — Minimal, no-frills task execution mode
- `grill-me` — Socratic questioning for better problem understanding
- ... and 17 more

## Architecture

```
skill-hub/
├── config/
│   └── registries.yaml       # Source definitions (repos, paths, globs)
├── skills_local/              # Cached SKILL.md files (gitignored)
│   ├── garrytan--gstack/
│   ├── mattpocock--skills/
│   └── ...
├── src/skill_hub/
│   ├── models.py              # SkillMeta data model
│   ├── indexer/
│   │   └── skill_index.py     # The searchable index (like a vector store)
│   ├── sync/
│   │   ├── base.py            # Abstract skill source
│   │   ├── github_source.py   # Pull + cache skills from GitHub repos
│   │   ├── local_source.py    # Pull skills from local directories
│   │   └── syncer.py          # Multi-source orchestrator
│   ├── registry/
│   │   └── skill_registry.py  # Agent-facing API (search + load)
│   ├── mcp/
│   │   └── server.py          # MCP tool server for agent integration
│   └── cli/
│       └── main.py            # CLI: sync, search, load, info, prompt
└── tests/                     # Unit tests
```

## Quick Start

```bash
pip install -e ".[dev]"

# Sync skills + download all SKILL.md content locally (requires `gh auth login`)
python -m skill_hub.cli.main sync

# Search for a skill
python -m skill_hub.cli.main search "phylogenetic tree"

# Load a specific skill's full content (from local cache)
python -m skill_hub.cli.main load tdd

# Generate compact prompt for agent injection
python -m skill_hub.cli.main prompt

# Show index stats
python -m skill_hub.cli.main info
```

## MCP Server (Agent Integration)

The MCP server lets agents search and load skills through tool calls — no manual prompt injection needed.

```bash
# Default: keyword matching
python -m skill_hub.mcp.server

# TF-IDF: local semantic matching (no API needed, much better accuracy)
python -m skill_hub.mcp.server --router tfidf

# LLM: cheap model does routing (best accuracy, needs API)
python -m skill_hub.mcp.server --router llm --llm-provider ollama
python -m skill_hub.mcp.server --router llm --llm-provider openai --llm-model gpt-4o-mini
```

Configure in Claude Code / Cursor / any MCP-compatible agent:

```json
{
  "mcpServers": {
    "skill-hub": {
      "command": "python",
      "args": ["-m", "skill_hub.mcp.server"]
    }
  }
}
```

This exposes 4 tools to the agent:

| Tool | Description |
|------|-------------|
| `search_skills(query)` | Keyword-based skill search |
| `suggest_skills(task)` | Semantic routing — finds best skills for complex tasks |
| `load_skill(name)` | Load full SKILL.md content from local cache |
| `list_skill_categories()` | Get compact overview of all available skills |
| `skill_info(name)` | Get metadata + apply instructions |

### Router Architecture

The `suggest_skills` tool uses a **two-stage architecture**: cheap model routes, main model executes.

```
User: "部署修复到生产环境，注意安全"
  │
  ▼
┌─────────────────────────────────────┐
│  Router (cheap model or TF-IDF)     │
│  Input: task + skill catalog (~2KB)  │
│  Output: selected skills + modes    │
│  Cost: ~$0.001 per query            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Main Agent (expensive model)       │
│  Input: full SKILL.md of matches    │
│  Executes: land-and-deploy workflow  │
│  Activates: careful (global hooks)  │
└─────────────────────────────────────┘
```

| Router | Speed | Accuracy | Dependencies |
|--------|-------|----------|-------------|
| `keyword` | <1ms | Low | None |
| `tfidf` | ~5ms | Medium | scikit-learn |
| `llm` | ~500ms | High | HTTP API |

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

The compact catalog for 250+ skills is roughly **5KB**. Loading all SKILL.md files would be **500KB+**.

## License

MIT
