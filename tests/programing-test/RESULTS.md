# Programming Test Results

**Date:** 2026-06-23
**Tasks:** 10
**Completed:** 10/10

## 3-Round Comparison

| | Round 1 | Round 2 | Round 3 (MCP重启) |
|---|---------|---------|-------------------|
| Skill Index | 313 | 313 | **317** |
| suggest_skills | 10/10 | 10/10 | 10/10 |
| skill loads | 1 | 4 | **5** |
| load rate | 10% | 40% | **50%** |
| useful loads | 1 | 1 | **4** |

## Round 3 Detail (Final)

| # | Task | Top Suggestions (score) | Loaded | Helpful? |
|---|------|------------------------|--------|---------|
| 1 | Binary Search | incremental-implementation (0.40), python-cookbook (0.34) | python-cookbook | Partial |
| 2 | Flask API | to-prd (0.40), incremental-implementation (0.34) | python-cookbook | Partial |
| 3 | Unit Tests | tdd (0.42), design-an-interface (0.37) | tdd | Yes |
| 4 | Data Viz | vaex (0.44) | — | — |
| 5 | Blog Outline | article-writing (0.34) | article-writing | Yes |
| 6 | CLI Tool | tdd (0.38), to-prd (0.27) | — | — |
| 7 | CSV Parser | context-save (0.37) | — | — |
| 8 | Caching | python-cookbook (0.25) | — | — |
| 9 | Web Scraper | qa-api-tester (0.44), tdd (0.42) | python-cookbook | Yes |
| 10 | Doc Generator | python-cookbook (0.53), qa-api-tester (0.54) | python-cookbook | Yes |

## Cumulative Usage (All 3 Rounds)

```
suggest_skills:  30 calls (100%)
skill:article-writing:  3 loads
skill:tdd:             2 loads
skill:python-cookbook:  2 loads
skill:design-an-interface: 1 load
skill:vaex:            1 load
Total: 9 loads, 5 distinct skills
```

## Key Findings

1. **MCP instructions work:** 100% suggest_skills call rate across all rounds
2. **New skills activate after MCP restart:** tdd and python-cookbook only appeared in Round 3
3. **Load rate improved 5x:** 10% → 50% after adding general programming skills
4. **Remaining gap:** No skills for algorithms, CLI tools, data structures, web frameworks
