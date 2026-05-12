# skill-hub

**Skills-as-RAG**: 轻量级智能体技能注册中心 — 先索引，按需加载。

## 它做什么

不把所有技能全文加载到上下文（贵且慢），skill-hub 维护一个**紧凑可搜索索引**。智能体搜索索引，只加载需要的技能。

```
智能体系统提示词 (~5KB 索引, 309 技能)
  │
  ├── search("plot") → 3 个候选
  │
  └── load_skill("nature-figure") → 按需加载完整技能目录
                                     (SKILL.md + references/ + scripts/ + ...)
```

## 快速开始

```bash
# 安装
pip install -e .

# 1. 编辑 config/registries.yaml 配置来源
# 2. 同步（git clone，不需要 API key）
python -m skill_hub.cli.main sync

# 3. 搜索
python -m skill_hub.cli.main search "phylogenetic tree"
```

**前置条件**: Python 3.10+, Git

## 数据流

```
┌─────────────────────────────────────────────────────────────┐
│  来源 (config/registries.yaml)                               │
│  ├── GitHub 仓库 (8 个, git clone --depth 1)                 │
│  └── 本地目录                                                │
│              │                                              │
│              ▼ sync                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  skills_local/          (完整技能目录)                  │  │
│  │  skill_index.json       (紧凑可搜索索引)               │  │
│  └──────────────────────────────────────────────────────┘  │
│              │                                              │
│              ▼ serve                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MCP Server (9 个工具)                                │  │
│  │  ├── search_skills      — 关键词搜索                  │  │
│  │  ├── suggest_skills     — 语义路由                    │  │
│  │  ├── load_skill         — 加载完整 SKILL.md           │  │
│  │  ├── skill_info         — 元数据 + 应用提示           │  │
│  │  ├── list_skill_categories — 分类概览                 │  │
│  │  ├── plan_with_skills   — 计划→技能匹配               │  │
│  │  ├── get_skill_usage    — 使用统计 + 月度分析         │  │
│  │  ├── search_remote_skills — 搜索 ClawHub (需确认)     │  │
│  │  └── install_remote_skill — 安装远程技能 (需批准)     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## MCP 工具

### `search_skills(query, top_k=5)`
关键词搜索技能名称、描述、触发词。

### `suggest_skills(task_description, output_format?, domain?)`
语义路由 — 返回任务相关的候选技能。可按输出格式 (pptx, html, pdf...) 和领域 (science, engineering, writing...) 过滤。

### `load_skill(name)`
返回完整 SKILL.md 内容。从 `local_path` 或 `skills_local/` 缓存读取。

### `skill_info(name)`
返回结构化元数据：描述、阶段、执行模式、标签、触发词、决策卡、应用提示。

### `plan_with_skills(plan_text, top_k_per_task=3)`
输入计划文档（markdown），返回每个子任务的推荐技能。支持 4 种格式：
- `### Task N:` 标题（superpowers writing-plans 格式）
- `## / ###` 任意标题
- `- [ ]` 复选框
- 数字列表 (1. 2. 3.)

输出 JSON，每个子任务附带推荐技能名、目录路径、阶段、执行模式。

### `list_skill_categories()`
按分类展示所有技能的紧凑概览。

### `get_skill_usage(month?, top_k?)`
查看技能使用统计。返回每个技能的调用次数、最后使用时间、月度分布。`month` 参数可筛选特定月份。数据存储在 `skill_usage.json`（gitignored），采用缓冲写入（dirty flag），查询时才落盘。

### `search_remote_skills(query, top_k=10)`
搜索 [ClawHub](https://github.com/openclaw/clawhub) 技能目录（8500+ stars 的 Agent Skill 注册中心）。

**门控规则（写在 docstring 中，主模型必须遵守）：**
1. 本地 `suggest_skills` 召回不足（score < 0.15）且任务足够专业/复杂 → 告知用户 → 用户确认后才调用
2. 用户主动要求搜索远程技能 → 直接调用

### `install_remote_skill(slug)`
从 ClawHub 安装技能到 `skills_local/clawhub/<slug>/`，自动解析 SKILL.md 并加入本地索引。

**门控规则：**
1. 用户审查搜索结果并明确批准后才安装
2. 用户直接指定 slug → 直接安装

安装后技能融入本地索引，后续可通过 `load_skill` / `search_skills` 直接访问。

## 技能元数据

| 字段 | 说明 |
|------|------|
| `phase` | 工作流阶段: `define` / `plan` / `build` / `verify` / `review` / `ship` / `execute` |
| `execution_mode` | 执行方式: `serial` / `parallel` / `independent` |
| `domain` | 领域: `science` / `biology` / `engineering` / `writing` / `marketing` / `data-science` / `chemistry` |
| `output_formats` | 输出格式: `pptx` / `html` / `pdf` / `csv` / `png` / `md` / ... |
| `input_types` | 输入类型: `paper` / `data` / `code` / `image` / `sequence` / `molecule` |
| `mode` | 应用模式: `global` / `on_demand` / `compose` |

phase 和 execution_mode 在 sync 时从 SKILL.md 内容推断（关键词匹配，不用 LLM）。

## 添加新来源

编辑 `config/registries.yaml`：

```yaml
registries:
  - name: my-source
    type: github
    repo: "owner/repo-name"
    skill_glob: "skills/*/SKILL.md"
```

然后: `python -m skill_hub.cli.main sync`

本地来源：
```yaml
  - name: my-local
    type: local
    path: "/path/to/skills"
    skill_glob: "*/SKILL.md"
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `sync` | 增量同步所有来源 |
| `sync --force` | 全量重建索引 |
| `search <query>` | 关键词搜索 |
| `load <name>` | 输出完整 SKILL.md |
| `info` | 显示索引统计 |

## 技能来源

| 来源 | 数量 | 说明 |
|------|------|------|
| [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 137 | 科研 — 单细胞分析、ML/DL、分子化学、统计 |
| [marketingskills](https://github.com/coreyhaines31/marketingskills) | 41 | 营销 — SEO、广告、分析、内容、A/B 测试 |
| [gstack](https://github.com/garrytan/gstack) | 51 | QA、设计评审、部署、浏览器自动化 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 27 | TDD、调试、原型、架构 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 22 | 代码评审、CI/CD、安全、性能 |
| [codex-skills-workbench](https://github.com/Jinze-Lee/codex-skills-workbench) | 17 | 生态学、绘图、数据管道、学术工作流 |
| [superpowers](https://github.com/obra/superpowers) | 14 | 规划、子智能体调度、调试、git 工作流 |
| [nature-skills](https://github.com/Yuan1z0825/nature-skills) | 6 | Nature 期刊写作、图表、数据处理 |

**总计: 309 技能，8 来源**

## 路由架构

路由器做**召回**（找候选），主模型做**决策**（选择+组合）：

```
用户: "重构 auth，跑测试，安全部署"
  │
  ▼
路由器 (TF-IDF)
  职责: 召回 — 找 20 个候选
  返回: 候选 + 元数据
  不决定用哪个
  │
  ▼
主模型 (你的智能体)
  职责: 决策 — 选择 + 组合
  看到: 完整任务上下文 + 候选
  加载: 只加载选中的技能
```

## 工作流集成

skill-hub 可与 superpowers 等规划工具配合：

1. **规划**: superpowers `writing-plans` 生成计划 MD
2. **匹配**: `plan_with_skills` 为每个子任务推荐技能
3. **执行**: 主智能体用 Agent tool 启动子智能体，注入 SKILL.md + 目录路径
4. **子智能体**: 按 SKILL.md 指引执行，按需读取 references/、scripts/ 等附带文件

子智能体有独立上下文，不污染主对话。

## ClawHub 远程技能集成

当本地 309 个技能无法覆盖某个专业任务时，可通过 [ClawHub](https://github.com/openclaw/clawhub) 搜索和安装远程技能。

```
用户任务 → suggest_skills → 本地召回不足?
    ↓ 是 (需用户确认)
search_remote_skills("causal inference DID")
    ↓ 返回 ClawHub 候选列表
用户选择 → install_remote_skill("causal-inference")
    ↓ 安装到 skills_local/clawhub/
    ↓ 自动加入本地索引
后续直接召回，无需再次远程搜索
```

**设计原则：**
- 不全量加载 — 只安装用户确认需要的技能
- 严格门控 — 主模型判断 + 用户确认，不会自动触发
- 安装即本地 — 远程技能安装后与本地技能无区别

## 使用统计

`get_skill_usage` 工具追踪每次 `load_skill` 调用：

```json
{
  "total_skills": 309,
  "used_skills": 12,
  "unused_skills": 297,
  "usage": {
    "tdd": { "count": 8, "last_used": "2026-05-12T14:30:00" },
    "guard": { "count": 3, "last_used": "2026-05-11T09:15:00" }
  }
}
```

生成可视化分析面板：
```bash
python dashboard/gen_usage.py   # 输出 dashboard/skill-usage.html
```

## 项目结构

```
skill-hub/
├── config/
│   └── registries.yaml          # 来源定义 (gitignored)
├── dashboard/
│   ├── index.html               # 交互式技能面板
│   ├── skill-usage.html         # 使用率分析面板
│   ├── gen.py                   # 生成技能面板
│   └── gen_usage.py             # 生成使用分析面板
├── src/skill_hub/
│   ├── models.py                # SkillMeta + SkillPhase + ExecutionMode
│   ├── indexer/skill_index.py   # 可搜索索引
│   ├── sync/
│   │   ├── github_source.py     # git clone --depth 1 (不需要 API)
│   │   ├── local_source.py      # 本地目录源
│   │   └── syncer.py            # 多源编排器 (增量)
│   ├── router/                  # 技能路由 (keyword / TF-IDF)
│   ├── selector/                # 技能选择器 (隔离上下文)
│   ├── mcp/server.py            # MCP 工具服务器 (9 工具)
│   └── cli/main.py              # CLI 入口
├── skill_index.json             # 生成的索引 (gitignored)
├── skill_usage.json             # 使用统计 (gitignored)
├── skills_local/                # 缓存的技能目录 (gitignored)
│   └── clawhub/                 # ClawHub 安装的技能 (gitignored)
└── tests/
```

## Dashboard

浏览器打开 `dashboard/index.html`，可按领域、来源、模式、阶段过滤，按名称/描述搜索。

```bash
python dashboard/gen.py   # 同步后重新生成
```

## 经验总结

### TF-IDF 召回率优化
- 11 字段语料库（vs 原始 5 字段）：name, description, tags, use_when, category, domain, phase, output_formats, input_types, triggers, decision_card
- 意图→阶段/领域映射：查询中的 "test" 自动提升 verify 阶段技能的分数
- 跨领域惩罚 (-0.07) 和阶段不匹配惩罚 (-0.05)
- 名称精确匹配奖励 (0.15 × 命中率)

### domain 推断要用词边界匹配
子串匹配会导致 "generate" 匹配 "gene"+"rna"，把营销技能误判为 biology。用 `\b` 正则词边界解决。

### local_path 必须持久化到索引
`to_index_entry()` 最初没包含 `local_path`，导致 `load_skill` 找不到文件。索引是唯一的持久化存储，所有运行时需要的字段都必须包含。

### 高频写入用 dirty flag 缓冲
`load_skill` 每次调用都记录使用事件，但不立即写盘。用 `usage_dirty = [False]` 标记，只在 `get_skill_usage` 查询时才落盘。

### MCP 工具在启动时注册
新增的 MCP 工具需要重启服务器才能被客户端发现。不能热加载。

### ClawHub CLI 需要显式 --workdir
`npx clawhub install` 默认用 cwd 作为工作目录，但 npx 执行时 cwd 可能不是项目根目录。必须 `--workdir` 明确传入。

## License

MIT
