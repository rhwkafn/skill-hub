"""Evaluation: 100 test prompts → TF-IDF router → top-10 results per prompt."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from skill_hub.indexer import SkillIndex
from skill_hub.router import TFIDFRouter

# 100 diverse test prompts (~30 chars each)
PROMPTS = [
    # --- Software Engineering ---
    "write unit tests for a REST API",
    "debug a memory leak in production",
    "set up CI/CD pipeline from scratch",
    "review this pull request for bugs",
    "refactor legacy code to clean arch",
    "optimize slow database queries",
    "implement authentication with JWT",
    "create a GraphQL schema design",
    "migrate from monolith to microservices",
    "set up Docker container for Node app",
    # --- Frontend ---
    "build a responsive landing page",
    "create a React component library",
    "fix CSS layout issues on mobile",
    "implement dark mode toggle",
    "optimize bundle size for web app",
    "set up Storybook for UI components",
    "build a data visualization dashboard",
    "create accessible form validation",
    "implement infinite scroll loading",
    "add animations to page transitions",
    # --- Data Science ---
    "analyze dataset and find correlations",
    "build a machine learning pipeline",
    "create a neural network for images",
    "perform statistical hypothesis testing",
    "visualize time series data trends",
    "clean and preprocess messy CSV data",
    "build a recommendation system",
    "train a text classification model",
    "do exploratory data analysis on survey",
    "implement k-means clustering algorithm",
    # --- Biology & Chemistry ---
    "analyze single cell RNA sequencing data",
    "build phylogenetic tree from sequences",
    "perform molecular docking simulation",
    "query protein database for structures",
    "run differential gene expression analysis",
    "calculate drug likeness properties",
    "search literature for protein functions",
    "analyze mass spectrometry proteomics",
    "build metabolic network model",
    "perform CRISPR guide RNA design",
    # --- Scientific Writing ---
    "write a Nature style research paper",
    "create scientific figures for journal",
    "polish manuscript for submission",
    "generate bibliography from references",
    "convert paper to presentation slides",
    "write a literature review section",
    "create a methods section for protocol",
    "format citations in APA style",
    "write an abstract for conference",
    "prepare supplementary materials",
    # --- DevOps & Security ---
    "scan codebase for security vulnerabilities",
    "set up monitoring and alerting system",
    "configure nginx reverse proxy",
    "implement rate limiting for API",
    "set up SSL certificates with Let's Encrypt",
    "create Terraform infrastructure as code",
    "audit IAM permissions and roles",
    "set up log aggregation pipeline",
    "configure auto-scaling for Kubernetes",
    "implement backup and disaster recovery",
    # --- Productivity ---
    "organize notes and knowledge base",
    "create a project roadmap document",
    "write meeting notes and action items",
    "automate repetitive file operations",
    "build a personal task management system",
    "create an email template library",
    "generate a weekly status report",
    "set up automated file backups",
    "create a checklist for code review",
    "write a technical design document",
    # --- Quality & Testing ---
    "write integration tests for API endpoints",
    "set up end-to-end testing with Playwright",
    "create a test coverage report",
    "implement property-based testing",
    "set up load testing for web service",
    "write fuzz tests for parser",
    "create mock data for testing",
    "set up mutation testing framework",
    "implement contract testing for APIs",
    "write performance benchmarks",
    # --- Creative & Misc ---
    "create an infographic about climate data",
    "build a CLI tool with argument parsing",
    "generate a PDF report from data",
    "create a Mermaid diagram for architecture",
    "write a blog post about tech stack",
    "build a web scraper for news articles",
    "create a REST API from OpenAPI spec",
    "implement a rate limiter algorithm",
    "build a real-time chat application",
    "create a markdown documentation site",
    # --- Specific Tools ---
    "use pandas to merge multiple CSV files",
    "deploy app to AWS with CloudFormation",
    "set up Prisma ORM for PostgreSQL",
    "configure ESLint and Prettier rules",
    "use PyTorch for image segmentation",
    "implement Redis caching layer",
    "set up GitHub Actions for releases",
    "use Selenium for browser automation",
    "configure Prometheus metrics endpoint",
    "implement WebSocket server in Node.js",
]


def run_eval():
    root = Path(__file__).resolve().parent.parent.parent
    index_path = root / "skill_index.json"
    output_dir = Path(__file__).resolve().parent

    print(f"Loading index from {index_path}...")
    index = SkillIndex.load(index_path)
    skills = list(index.skills.values())
    print(f"Loaded {len(skills)} skills")

    router = TFIDFRouter()
    results = []

    for i, prompt in enumerate(PROMPTS):
        output = router.route(prompt, skills, top_k=10)
        candidates = []
        for r in output.candidates:
            candidates.append({
                "name": r.skill.name,
                "score": round(r.score, 3),
                "mode": r.skill.mode.value,
                "description": r.skill.description[:80],
                "triggers": r.skill.triggers[:2],
            })

        entry = {
            "id": i + 1,
            "prompt": prompt,
            "candidates": candidates,
        }
        results.append(entry)

        # Progress
        top3 = [c["name"] for c in candidates[:3]]
        print(f"  [{i+1:3d}/100] {prompt[:35]:35s} → {top3}")

    # Save results
    output_file = output_dir / "eval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_file}")

    # Also save a human-readable summary
    summary_file = output_dir / "eval_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# Skill Hub Evaluation Results\n\n")
        f.write(f"Router: TF-IDF | Skills: {len(skills)} | Prompts: {len(PROMPTS)}\n\n")

        for entry in results:
            f.write(f"## {entry['id']}. {entry['prompt']}\n\n")
            for c in entry["candidates"]:
                flag = " **[GLOBAL]**" if c["mode"] == "global" else ""
                f.write(f"- `{c['name']}` ({c['score']}){flag}: {c['description']}\n")
            f.write("\n")

    print(f"Summary saved to {summary_file}")


if __name__ == "__main__":
    run_eval()
