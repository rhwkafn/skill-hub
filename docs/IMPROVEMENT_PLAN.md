# Skill-Hub 长期改进方案

## 背景

当前状态：307 skills，6 MCP tools，TF-IDF router。
问题：(1) 规划过程不可见 (2) skill 调用率低，召回质量差。

已做改进（本分支）：
- TF-IDF 语料扩展（+domain/phase/decision_card）
- auto-tags 自动提取（0% → 100%）
- intent→phase/domain 映射 + 跨域惩罚
- 规划可见性（suggest_skills 推荐 plan_with_skills）

5 查询实测噪声率：28% → 8%。

---

## 阶段一：短期优化（纯本地，零依赖）

### 1.1 Auto-tags 质量提升
**问题**：当前 auto-tags 仍有 "current", "note", "original" 等通用词。
**方案**：
- 用 SKILL.md 的 heading 结构提取语义关键词（# 后面的词更有意义）
- 对 tags 做 TF-IDF 跨语料去重：如果一个词在 >50% 的 skill 中出现，降权
- 从 description 和 use_when 提取关键词优先级高于 body

### 1.2 search_skills 统一到 TF-IDF
**问题**：`search_skills` 用 `SkillMeta.matches()`（简单子串匹配），`suggest_skills` 用 TF-IDF。两个工具返回不同结果。
**方案**：`search_skills` 也走 TFIDFRouter，保持一致性。

### 1.3 推理链优化
**问题**：boost 是加法，cosine 分数范围 0-1，boost 范围 0-0.3，信号容易被淹没。
**方案**：
- 将 cosine 分数和 boost 分数分开计算，用加权融合：`final = 0.7 * cosine + 0.3 * normalized_boost`
- 或用 rank fusion：先按 cosine 排序，再按 boost 排序，合并两个排名

### 1.4 阈值自适应
**问题**：硬编码 `score > 0.01` 阈值，对短查询和长查询效果不同。
**方案**：根据 top-1 分数动态调整阈值，如 `threshold = max(0.01, top1_score * 0.3)`。

---

## 阶段二：中期增强（需少量依赖）

### 2.1 Embedding 语义检索
**问题**：TF-IDF 是词袋模型，无法理解语义相似性。"debug" 匹配不到 "investigate" 的同义关系。
**方案**：
- 用 `sentence-transformers` 的 `all-MiniLM-L6-v2` 模型（本地，~80MB）
- 对 skill 文本和查询做 embedding，用 cosine similarity
- 与 TF-IDF 做 hybrid：TF-IDF 做 recall（快），embedding 做 re-rank（准）
- 预计算 embedding 存入索引，运行时只算查询的 embedding

### 2.2 查询扩展（Query Expansion）
**问题**：短查询（2-3 词）TF-IDF 向量太稀疏。
**方案**：
- 用 WordNet 或简单同义词表扩展查询词
- "debug" → "debug, diagnose, investigate, troubleshoot, fix"
- 或用 LLM 做 query rewriting（一次 API 调用）

### 2.3 Skill 使用反馈循环
**问题**：无法知道哪些 skill 实际被使用了，哪些匹配成功。
**方案**：
- 在 `load_skill` 时记录：查询词、选中的 skill、时间戳
- 存入 `skill_usage.json`
- 用 usage 数据调整 TF-IDF 权重：被选中过的 skill 在相似查询中 boost

---

## 阶段三：长期架构（解决根本问题）

### 3.1 LLM Re-ranker
**问题**：纯本地方法的上限是词袋 + 向量相似度，无法理解复杂意图。
**方案**：
- 已有 `LLMRouter` 骨架，接入廉价模型（qwen2.5:14b / gpt-4o-mini）
- TF-IDF recall 30 → LLM re-rank → top 5
- 成本：~100 token/查询，每天 100 次查询 ≈ $0.01

### 3.2 Skill 自动生成 Tags
**问题**：auto-tags 质量取决于 SKILL.md 写作质量，很多 skill 文档质量差。
**方案**：
- sync 阶段用 LLM 为每个 skill 生成标准化 tags
- 输入：description + body 前 500 字 → 输出：5-8 个语义 tags
- 一次 sync 处理 300 skills ≈ $0.30，成本可接受

### 3.3 Plan 端到端自动化
**问题**：`plan_with_skills` 只做匹配，不执行。用户需要手动 load_skill + 执行。
**方案**：
- `auto_execute_plan` 工具：plan_with_skills → 对每个子任务 load_skill → 创建 subagent 执行
- 用户只需提供计划文本，skill-hub 自动编排执行

---

## 优先级排序

| 阶段 | 改进项 | 效果 | 成本 | 优先级 |
|------|--------|------|------|--------|
| 1.1 | auto-tags 质量 | 中 | 零 | P1 |
| 1.2 | search_skills 统一 | 低 | 零 | P2 |
| 1.3 | 推理链优化 | 高 | 零 | P1 |
| 1.4 | 阈值自适应 | 低 | 零 | P3 |
| 2.1 | Embedding 语义检索 | 高 | 80MB | P1 |
| 2.2 | 查询扩展 | 中 | 零/低 | P2 |
| 2.3 | 使用反馈循环 | 中 | 零 | P2 |
| 3.1 | LLM Re-ranker | 高 | $0.01/天 | P1 |
| 3.2 | LLM 生成 tags | 高 | $0.30/次 | P2 |
| 3.3 | 端到端自动化 | 高 | 依赖 3.1 | P3 |

**建议下一步**：1.3（推理链优化）→ 2.1（Embedding）→ 3.1（LLM Re-ranker）
