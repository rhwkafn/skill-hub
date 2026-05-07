# skill-hub

**Skills-as-RAG**: A lightweight agent skill registry that treats skills like retrieval-augmented generation — index first, load on demand.

## What It Does

Instead of loading every skill's full content into context (expensive, slow), skill-hub maintains a **compact searchable index**. Agents search the index, then load only the skills they need.

```
Agent System Prompt (~5KB index, 250+ skills)
  │
  ├── search("plot") → 3 candidates found
  │
  └── load_skill("raincloud-plot") → full SKILL.md loaded on demand
```

## Quick Start

```bash
# Install
pip install -e .

# 1. Configure sources (edit config/registries.yaml)
# 2. Sync skills from all sources
python -m skill_hub.cli.main sync

# 3. Search
python -m skill_hub.cli.main search "phylogenetic tree"

# 4. Load a specific skill
python -m skill_hub.cli.main load tdd

# 5. Generate compact prompt for agent injection
python -m skill_hub.cli.main prompt
```

### Prerequisites

- Python 3.10+
- `gh auth login` for GitHub API access (avoids rate limits)

## How It Works

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Sources (config/registries.yaml)                           │
│  ├── GitHub repos (6 sources)                               │
│  └── Local directories                                      │
│              │                                              │
│              ▼ sync                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  skills_local/          (cached SKILL.md files)       │  │
│  │  skill_index.json       (compact searchable index)    │  │
│  └──────────────────────────────────────────────────────┘  │
│              │                                              │
│              ▼ serve                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MCP Server (4 tools exposed to agent)                │  │
│  │  ├── search_skills(query)    — keyword search         │  │
│  │  ├── suggest_skills(task)    — semantic routing       │  │
│  │  ├── load_skill(name)        — full SKILL.md content  │  │
│  │  └── list_skill_categories() — compact overview       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `sync` | Discover + index skills from all sources (incremental by default) |
| `sync --force` | Full rebuild — re-process all skills |
| `sync --cache-dir skills_local` | Also download full SKILL.md files locally |
| `search <query>` | Search the index by keyword |
| `load <name>` | Print full SKILL.md content for a skill |
| `info` | Show index stats |
| `prompt` | Generate compact skill catalog for agent injection |

### MCP Server (Agent Integration)

The MCP server lets agents search and load skills through tool calls:

```bash
# Default: TF-IDF semantic matching (no API needed)
python -m skill_hub.mcp.server

# Keyword matching (fastest, less accurate)
python -m skill_hub.mcp.server --router keyword

# LLM routing (best accuracy, needs API)
python -m skill_hub.mcp.server --router llm --llm-provider ollama
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

### Router Architecture

The router does **recall** (find candidates), the main model does **decision** (pick + combine):

```
User: "refactor auth, run tests, deploy safely"
  │
  ▼
Router (TF-IDF or cheap LLM)
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

Then: `python -m skill_hub.cli.main sync`

For local sources:

```yaml
  - name: my-local-skills
    type: local
    path: "/path/to/skills"
    skill_glob: "*/SKILL.md"
```

## Project Structure

```
skill-hub/
├── config/
│   └── registries.yaml          # Source definitions (gitignored — has local paths)
├── dashboard/
│   ├── index.html               # Interactive skill dashboard (English)
│   ├── index_zh.html            # Chinese version
│   └── gen.py                   # Regenerate dashboards from skill_index.json
├── src/skill_hub/
│   ├── models.py                # SkillMeta data model
│   ├── indexer/
│   │   └── skill_index.py       # Searchable index (like a vector store)
│   ├── sync/
│   │   ├── base.py              # Abstract skill source
│   │   ├── github_source.py     # Pull + cache skills from GitHub repos
│   │   ├── local_source.py      # Pull skills from local directories
│   │   └── syncer.py            # Multi-source orchestrator (incremental)
│   ├── registry/
│   │   └── skill_registry.py    # Agent-facing API (search + load)
│   ├── router/                  # Skill routing (keyword / TF-IDF / LLM)
│   ├── selector/                # Skill selection (disabled by default)
│   ├── mcp/
│   │   └── server.py            # MCP tool server
│   └── cli/
│       └── main.py              # CLI entry point
├── skill_index.json             # Generated index (gitignored)
├── skills_local/                # Cached SKILL.md files (gitignored)
└── tests/
```

## Skill Sources

| Source | Skills | Description |
|--------|--------|-------------|
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 137 | Scientific research — single-cell analysis, ML/DL, molecular chemistry, statistics |
| [gstack](https://github.com/garrytan/gstack) | 49 | QA, design review, deployment, browser automation |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 27 | TDD, debugging, prototyping, architecture |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 21 | Code review, CI/CD, security, performance |
| [codex-skills-workbench](https://github.com/Jinze-Lee/codex-skills-workbench) | 17 | Ecology, plotting, data pipelines, academic workflows |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | 5 | Nature journal writing, figures, data processing |

## Dashboard

Open `dashboard/index.html` in a browser to explore all skills interactively — filter by domain, source, or mode; search by name/description.

To regenerate after syncing:

```bash
python dashboard/gen.py
```

## License

MIT
