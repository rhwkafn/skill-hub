# skill-hub

**Skills-as-RAG**: A lightweight agent skill registry that treats skills like retrieval-augmented generation — index first, load on demand.

## What It Does

Instead of loading every skill's full content into context (expensive, slow), skill-hub maintains a **compact searchable index**. Agents search the index, then load only the skills they need.

```
Agent System Prompt (~5KB index, 313 skills)
  │
  ├── search("plot") → 3 candidates found
  │
  └── load_skill("nature-figure") → full skill directory loaded on demand
                                     (SKILL.md + references/ + scripts/ + ...)
```

## Quick Start

```bash
# Install
pip install -e .

# 1. Configure sources (edit config/registries.yaml)
# 2. Sync skills from all sources (uses git clone — no API key needed)
python -m skill_hub.cli.main sync

# 3. Search
python -m skill_hub.cli.main search "phylogenetic tree"

# 4. Load a specific skill
python -m skill_hub.cli.main load tdd
```

### Prerequisites

- Python 3.10+
- Git (for cloning skill repos)

## How It Works

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Sources (config/registries.yaml)                           │
│  ├── GitHub repos (8 sources, via git clone --depth 1)      │
│  └── Local directories                                      │
│              │                                              │
│              ▼ sync                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  skills_local/          (full skill directories)       │  │
│  │  skill_index.json       (compact searchable index)    │  │
│  └──────────────────────────────────────────────────────┘  │
│              │                                              │
│              ▼ serve                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MCP Server (6 tools exposed to agent)                │  │
│  │  ├── search_skills(query)      — keyword search       │  │
│  │  ├── suggest_skills(task)      — semantic routing     │  │
│  │  ├── load_skill(name)          — full skill content   │  │
│  │  ├── skill_info(name)          — metadata + hints     │  │
│  │  ├── list_skill_categories()   — compact overview     │  │
│  │  └── plan_with_skills(plan)    — match skills to plan │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `sync` | Discover + index skills from all sources (incremental by default) |
| `sync --force` | Full rebuild — re-process all skills |
| `search <query>` | Search the index by keyword |
| `load <name>` | Print full SKILL.md content for a skill |
| `info` | Show index stats |

### MCP Server (Agent Integration)

The MCP server lets agents search and load skills through tool calls:

```bash
# Default: TF-IDF semantic matching (no API needed)
python -m skill_hub.mcp.server

# With skill selection model (isolated context, precise)
python -m skill_hub.mcp.server --selector-model gpt-4o
```

Configure in Claude Code / Cursor / any MCP-compatible agent:

```json
{
  "mcpServers": {
    "skill-hub": {
      "command": "python",
      "args": ["-m", "skill_hub.mcp.server"],
      "cwd": "/path/to/skill-hub"
    }
  }
}
```

## MCP Tools

### `search_skills(query, top_k)`
Keyword search across skill names, descriptions, and triggers.

### `suggest_skills(task_description, output_format?, domain?)`
Semantic routing — returns ranked candidates for a task. Optional filters for output format (pptx, html, pdf...) and domain (science, engineering, writing...).

### `load_skill(name)`
Returns the full SKILL.md content for a skill. Use after selecting a skill from search/suggest results.

### `skill_info(name)`
Returns structured metadata: description, phase, execution_mode, tags, triggers, decision card, and an `apply_hint` for how to inject the skill.

### `plan_with_skills(plan_text, top_k_per_task?)`
Takes a plan document (markdown) and returns skill recommendations for each sub-task. Parses multiple plan formats:
- `### Task N:` headers (superpowers writing-plans format)
- `## / ###` headings
- `- [ ]` checkboxes
- Numbered lists

Returns JSON with each sub-task mapped to recommended skills, including `local_path` for direct file access.

### `list_skill_categories()`
Compact overview of all skills grouped by category.

## Skill Metadata

Each skill in the index carries:

| Field | Description |
|-------|-------------|
| `phase` | Workflow phase: `define` / `plan` / `build` / `verify` / `review` / `ship` / `execute` |
| `execution_mode` | How to run: `serial` / `parallel` / `independent` |
| `domain` | Topic area: `science` / `biology` / `engineering` / `writing` / `data-science` |
| `output_formats` | What it produces: `pptx` / `html` / `pdf` / `csv` / `png` / ... |
| `input_types` | What it consumes: `paper` / `data` / `code` / `image` / `sequence` / ... |
| `mode` | Application mode: `global` / `on_demand` / `compose` |

Phase and execution_mode are inferred from SKILL.md content during sync (keyword matching, no LLM).

## Adding New Sources

Edit `config/registries.yaml`:

```yaml
registries:
  - name: my-new-source
    type: github
    repo: "owner/repo-name"
    skill_glob: "skills/*/SKILL.md"
```

Then: `python -m skill_hub.cli.main sync`

For local sources:

```yaml
  - name: my-local-skills
    type: local
    path: "/path/to/skills"
    skill_glob: "*/SKILL.md"
```

## Skill Sources

| Source | Skills | Description |
|--------|--------|-------------|
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 137 | Scientific research — single-cell analysis, ML/DL, molecular chemistry, statistics |
| [marketingskills](https://github.com/coreyhaines31/marketingskills) | 41 | Marketing — SEO, ads, analytics, content, A/B testing |
| [gstack](https://github.com/garrytan/gstack) | 51 | QA, design review, deployment, browser automation |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 27 | TDD, debugging, prototyping, architecture |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 22 | Code review, CI/CD, security, performance |
| [codex-skills-workbench](https://github.com/Jinze-Lee/codex-skills-workbench) | 17 | Ecology, plotting, data pipelines, academic workflows |
| [superpowers](https://github.com/obra/superpowers) | 14 | Planning, subagent dispatch, debugging, git workflow |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | 6 | Nature journal writing, figures, data processing |

**Total: 313 skills across 9 sources**

## Router Architecture

The router does **recall** (find candidates), the main model does **decision** (pick + combine):

```
User: "refactor auth, run tests, deploy safely"
  │
  ▼
Router (TF-IDF)
  Job: RECALL — find 20 candidates
  Returns: candidates + metadata
  Does NOT decide which to use
  │
  ▼
Main Model (your agent)
  Job: DECISION — pick + combine
  Sees: full task context + candidates
  Loads: only the skills it chooses
```

## Project Structure

```
skill-hub/
├── config/
│   └── registries.yaml          # Source definitions (gitignored)
├── dashboard/
│   ├── index.html               # Interactive skill dashboard (English)
│   ├── index_zh.html            # Chinese version
│   └── gen.py                   # Regenerate dashboards from skill_index.json
├── src/skill_hub/
│   ├── models.py                # SkillMeta + SkillPhase + ExecutionMode
│   ├── indexer/
│   │   └── skill_index.py       # Searchable index
│   ├── sync/
│   │   ├── base.py              # Abstract skill source
│   │   ├── github_source.py     # git clone --depth 1 (no API needed)
│   │   ├── local_source.py      # Local directory source
│   │   └── syncer.py            # Multi-source orchestrator (incremental)
│   ├── registry/
│   │   └── skill_registry.py    # Agent-facing API
│   ├── router/                  # Skill routing (keyword / TF-IDF)
│   ├── selector/                # Skill selection with isolated context
│   ├── mcp/
│   │   └── server.py            # MCP tool server (6 tools)
│   └── cli/
│       └── main.py              # CLI entry point
├── skill_index.json             # Generated index (gitignored)
├── skills_local/                # Cached skill directories (gitignored)
└── tests/
```

## Dashboard

Open `dashboard/index.html` in a browser to explore all skills interactively — filter by domain, source, mode, or phase; search by name/description.

```bash
python dashboard/gen.py   # Regenerate after syncing
```

## License

MIT
