"""Full MCP pipeline evaluation: suggest_skills → load_skill for each prompt.

Tests the actual MCP tool chain, not just the router directly.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from skill_hub.mcp.server import create_server

# Reuse the same 100 prompts
from run_eval import PROMPTS


def run_mcp_eval():
    print("Creating MCP server...")
    s = create_server()
    suggest = s._tool_manager._tools['suggest_skills'].fn
    load = s._tool_manager._tools['load_skill'].fn
    search = s._tool_manager._tools['search_skills'].fn

    results = []
    stats = {"total": 0, "suggest_ok": 0, "load_ok": 0, "errors": []}

    for i, prompt in enumerate(PROMPTS):
        stats["total"] += 1
        entry = {"id": i + 1, "prompt": prompt}

        # Step 1: suggest_skills
        try:
            t0 = time.time()
            suggest_result = suggest(prompt)
            t_suggest = time.time() - t0
            entry["suggest_time_ms"] = round(t_suggest * 1000)
            entry["suggest_result"] = suggest_result
            stats["suggest_ok"] += 1
        except Exception as e:
            entry["error"] = f"suggest_skills failed: {e}"
            stats["errors"].append((i + 1, "suggest", str(e)))
            results.append(entry)
            continue

        # Step 2: Extract skill names from suggest result
        # The result is either a structured text (to_prompt) or JSON (with selector)
        skill_names = []
        if suggest_result.startswith("{"):
            # JSON output from selector
            try:
                data = json.loads(suggest_result)
                skill_names = data.get("selected", [])
            except json.JSONDecodeError:
                pass

        if not skill_names:
            # Parse from structured text — extract **name** patterns
            import re
            skill_names = re.findall(r'\*\*(\w[\w-]*)\*\*', suggest_result)

        entry["candidates_found"] = len(skill_names)
        entry["top5_names"] = skill_names[:5]

        # Step 3: load_skill for top-1
        if skill_names:
            top1 = skill_names[0]
            try:
                t0 = time.time()
                content = load(top1)
                t_load = time.time() - t0
                entry["load_time_ms"] = round(t_load * 1000)
                entry["load_ok"] = True
                entry["load_chars"] = len(content)
                entry["load_first_line"] = content.splitlines()[0] if content else ""
                stats["load_ok"] += 1
            except Exception as e:
                entry["load_ok"] = False
                entry["load_error"] = str(e)
                stats["errors"].append((i + 1, "load", str(e)))
        else:
            entry["load_ok"] = False

        results.append(entry)

        # Progress
        top3 = entry.get("top5_names", [])[:3]
        status = "OK" if entry.get("load_ok") else "FAIL"
        print(f"  [{i+1:3d}/100] {prompt[:35]:35s} → {top3} [{status}]")

    # Save results
    output_dir = Path(__file__).resolve().parent
    output_file = output_dir / "mcp_eval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n=== MCP EVAL SUMMARY ===")
    print(f"Total: {stats['total']}")
    print(f"suggest_skills OK: {stats['suggest_ok']}")
    print(f"load_skill OK: {stats['load_ok']}")
    print(f"Errors: {len(stats['errors'])}")
    if stats['errors']:
        print("Error details:")
        for pid, step, err in stats['errors']:
            print(f"  #{pid} ({step}): {err[:80]}")

    # Generate markdown summary
    summary_file = output_dir / "mcp_eval_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# MCP Pipeline Evaluation\n\n")
        f.write(f"suggest_skills → load_skill full pipeline test\n\n")
        f.write(f"| Metric | Count |\n|--------|-------|\n")
        f.write(f"| Total | {stats['total']} |\n")
        f.write(f"| suggest OK | {stats['suggest_ok']} |\n")
        f.write(f"| load OK | {stats['load_ok']} |\n")
        f.write(f"| Errors | {len(stats['errors'])} |\n\n")

        for entry in results:
            f.write(f"## {entry['id']}. {entry['prompt']}\n\n")
            if 'error' in entry:
                f.write(f"**ERROR**: {entry['error']}\n\n")
                continue

            top5 = entry.get("top5_names", [])
            f.write(f"Candidates: {entry.get('candidates_found', 0)} | "
                    f"suggest: {entry.get('suggest_time_ms', '?')}ms | "
                    f"load: {entry.get('load_time_ms', '?')}ms\n\n")

            for j, name in enumerate(top5):
                marker = " **→ loaded**" if j == 0 and entry.get("load_ok") else ""
                f.write(f"{j+1}. `{name}`{marker}\n")

            if entry.get("load_ok"):
                f.write(f"\nLoaded: {entry.get('load_chars', 0)} chars\n")
            elif entry.get("load_error"):
                f.write(f"\nLoad error: {entry['load_error']}\n")
            f.write("\n")

    print(f"\nResults: {output_file}")
    print(f"Summary: {summary_file}")


if __name__ == "__main__":
    run_mcp_eval()
