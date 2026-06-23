"""TF-IDF router — local semantic matching without API calls."""

from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import SkillRouter, RouteOutput, RouteResult
from ..models import SkillMeta, SkillMode


# Chinese → English keyword mapping for cross-language matching
_ZH_EN_MAP = {
    "测": "test", "试": "test", "单元": "unit", "调试": "debug", "诊断": "diagnose",
    "修复": "fix", "错误": "error", "异常": "exception",
    "写": "write", "编写": "write", "创建": "create", "建": "build",
    "开发": "develop", "生成": "generate", "实现": "implement",
    "审": "review", "审查": "review", "重构": "refactor",
    "部署": "deploy", "发布": "release", "上线": "deploy",
    "规划": "plan", "设计": "design", "架构": "architecture",
    "分析": "analysis", "数据": "data", "可视化": "visualization",
    "仪表盘": "dashboard", "图表": "chart", "图": "figure",
    "博客": "blog", "文章": "article", "论文": "paper", "写作": "writing",
    "摘要": "abstract", "手稿": "manuscript", "编辑": "editorial",
    "营销": "marketing", "推广": "marketing", "落地页": "landing",
    "转化": "conversion", "漏斗": "funnel", "SEO": "seo",
    "研究": "research", "实验": "experiment", "基因": "gene",
    "蛋白": "protein", "RNA": "rna", "细胞": "cell", "生物": "biology",
    "化学": "chemistry", "物理": "physics",
    "界面": "ui", "原型": "prototype", "线框": "wireframe", "PPT": "pptx",
    "演示": "presentation", "幻灯片": "slide", "信息图": "infographic",
    "机器学习": "machine learning", "深度学习": "deep learning",
    "神经网络": "neural network", "模型": "model",
    "测试": "test", "单测": "unit test", "集成测试": "integration test",
    "API": "api", "数据库": "database", "服务器": "server",
    "容器": "docker", "持续集成": "ci/cd", "流水线": "pipeline",
    "word": "word docx document",
    "excel": "excel xlsx spreadsheet",
    "表格": "excel xlsx spreadsheet", "电子表格": "excel xlsx spreadsheet",
    "ppt": "pptx powerpoint presentation slide",
    "幻灯片": "pptx powerpoint presentation slide", "演示文稿": "pptx powerpoint presentation slide",
    "pdf": "pdf document",
    "文档": "docx word document", "报告": "report document pdf",
    # Programming
    "单元测试": "unit test pytest", "单测": "unit test pytest",
    "调试": "debug", "重构": "refactor",
    "装饰器": "decorator", "缓存": "cache",
    "爬虫": "scraper web scraping", "解析": "parser parse",
    "算法": "algorithm", "数据结构": "data structure",
    "接口": "api endpoint", "框架": "framework",
    "自动化": "automation script",
}


def _tokenize(text: str) -> list[str]:
    """Tokenizer that handles both English words and Chinese characters.

    English: split on non-alpha, keep 2+ char tokens.
    Chinese: map to English equivalents + keep individual characters.
    """
    tokens = []
    # Extract English words
    for word in re.findall(r"[a-z][a-z0-9_]+", text.lower()):
        tokens.append(word)
    # Extract Chinese characters and map to English equivalents
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            tokens.append(ch)
            if ch in _ZH_EN_MAP:
                tokens.append(_ZH_EN_MAP[ch])
    # Also check multi-character phrases (case-insensitive)
    text_lower = text.lower()
    for zh, en in _ZH_EN_MAP.items():
        if len(zh) > 1 and zh in text_lower:
            tokens.extend(en.split())
    return tokens

# Query intent → expected phase mapping
_INTENT_PHASE = {
    "debug": "verify", "test": "verify", "diagnose": "verify", "fix": "verify",
    "investigate": "verify", "troubleshoot": "verify", "qa": "verify",
    "tests": "verify", "testing": "verify", "unit": "verify", "integration": "verify",
    "implement": "build", "create": "build", "write": "build", "build": "build",
    "develop": "build", "code": "build", "generate": "build", "produce": "build",
    "review": "review", "audit": "review", "refactor": "review", "quality": "review",
    "security": "review", "hardening": "review",
    "deploy": "ship", "release": "ship", "launch": "ship", "document": "ship",
    "plan": "plan", "architect": "plan", "design": "plan", "roadmap": "plan",
    "architecture": "plan",
    "spec": "define", "brainstorm": "define", "requirement": "define",
    # Chinese intent → phase
    "测": "verify", "调试": "verify", "诊断": "verify", "修复": "verify",
    "写": "build", "创建": "build", "建": "build", "开发": "build", "生成": "build",
    "审": "review", "审查": "review", "重构": "review",
    "部署": "ship", "发布": "ship", "上线": "ship",
    "规划": "plan", "设计": "plan", "架构": "plan",
}

# Chinese intent → expected domain mapping
_INTENT_DOMAIN_ZH = {
    "测试": "engineering", "调试": "engineering", "部署": "engineering", "运维": "engineering",
    "博客": "writing", "文章": "writing", "论文": "writing", "写作": "writing", "摘要": "writing", "手稿": "writing",
    "营销": "marketing", "推广": "marketing", "落地页": "marketing", "转化": "marketing",
    "研究": "science", "实验": "science", "基因": "science", "蛋白": "science", "RNA": "science",
    "数据": "data-science", "可视化": "data-science", "仪表盘": "data-science", "分析": "data-science",
    "设计": "design", "原型": "design", "界面": "design", "UI": "design", "PPT": "design", "演示": "design",
}

# Query intent → expected domain mapping
# Only use UNAMBIGUOUS words that always indicate a specific domain.
# Generic verbs (write, make, build, run) are NOT included.
_INTENT_DOMAIN = {
    # Engineering — always technical
    "debug": "engineering", "deploy": "engineering", "unit": "engineering",
    "code": "engineering", "refactor": "engineering", "api": "engineering",
    "microservice": "engineering", "pull": "engineering", "pr": "engineering",
    "kubernetes": "engineering", "docker": "engineering", "ci": "engineering",
    "pipeline": "engineering", "backend": "engineering", "server": "engineering",
    "middleware": "engineering", "authentication": "engineering",
    "sre": "engineering", "devops": "engineering", "incident": "engineering",
    "outage": "engineering", "troubleshoot": "engineering",
    # Writing — always writing domain
    "blog": "writing", "article": "writing",
    "essay": "writing", "manuscript": "writing",
    "narrative": "writing", "editorial": "writing",
    "abstract": "writing", "draft": "writing",
    # Marketing — always marketing
    "marketing": "marketing", "seo": "marketing", "campaign": "marketing",
    "funnel": "marketing", "landing": "marketing",
    "ab": "marketing",  # A/B test
    # Science — always science
    "research": "science", "paper": "science", "experiment": "science",
    "hypothesis": "science", "genomics": "science", "phylogenetic": "science",
    # Data science
    "visualization": "data-science", "dashboard": "data-science",
    "etl": "data-science", "dataset": "data-science",
    # Design
    "mockup": "design", "wireframe": "design", "wireframes": "design", "ui": "design", "ux": "design",
    "deck": "design", "slide": "design", "presentation": "design",
    "figma": "design", "prototype": "design", "infographic": "design", "poster": "design",
}

# Bigram overrides: when these word pairs appear, override single-word intent
_INTENT_BIGRAM_OVERRIDES = {
    ("a", "b"): {"domain": "marketing"},       # A/B test
    ("ab", "test"): {"domain": "marketing"},
    ("pitch", "deck"): {"domain": "design"},
    ("slide", "deck"): {"domain": "design"},
    ("code", "review"): {"phase": "review", "domain": "engineering"},
    ("unit", "test"): {"phase": "verify", "domain": "engineering"},
    ("integration", "test"): {"phase": "verify", "domain": "engineering"},
    ("protein", "structure"): {"domain": "science"},     # protein structure = science
    ("landing", "page"): {"domain": "marketing"},        # landing page = marketing
    ("email", "marketing"): {"domain": "marketing"},
    ("social", "media"): {"domain": "marketing"},
    ("paper", "abstract"): {"domain": "writing"},        # paper abstract = writing task
    ("paper", "draft"): {"domain": "writing"},           # paper draft = writing task
    ("word", "document"): {"domain": "engineering"},     # Word document = docx
    ("word", "file"): {"domain": "engineering"},
    ("excel", "spreadsheet"): {"domain": "data-science"},
    ("excel", "file"): {"domain": "data-science"},
    ("powerpoint", "presentation"): {"domain": "design"},
    ("powerpoint", "file"): {"domain": "design"},
    # Programming
    ("unit", "test"): {"phase": "verify", "domain": "engineering"},
    ("binary", "search"): {"domain": "engineering"},
    ("rest", "api"): {"domain": "engineering"},
    ("csv", "parser"): {"domain": "engineering"},
    ("web", "scraper"): {"domain": "engineering"},
    ("cli", "tool"): {"domain": "engineering"},
    ("data", "structure"): {"domain": "engineering"},
    ("flask", "api"): {"domain": "engineering"},
    ("fastapi", "api"): {"domain": "engineering"},
}


def _clean_decision_card(text: str) -> str:
    """Remove structured tokens from decision_card that pollute TF-IDF."""
    # Remove [name] mode=X phase=Y hooks=true needs=X,Y
    text = re.sub(r"\[.*?\]\s*", "", text)
    text = re.sub(r"\b(mode|phase|hooks|needs|true|false|on_demand|global|compose)=\S+", "", text)
    text = re.sub(r"\b(define|plan|build|verify|review|ship|execute)\b", "", text)
    return text.strip()


# Skill name → synonym text added to corpus for better TF-IDF matching
_SKILL_SYNONYMS = {
    "xlsx": "excel spreadsheet xls table",
    "docx": "word document doc ms office",
    "pptx": "powerpoint presentation slides ppt deck",
    "pdf": "pdf document portable",
    "markitdown": "convert office document word excel powerpoint pdf markdown",
    # Programming skills
    "tdd": "test driven development unit test pytest unittest testing",
    "test-driven-development": "test driven development tdd unit test pytest",
    "nm-parseltongue-python-testing": "python testing pytest unittest unit test",
    "python-cookbook": "python recipe pattern decorator algorithm data structure function",
    "qa-api-tester": "api testing REST flask fastapi endpoint web",
    "laosi-tdd": "测试驱动开发 tdd 单元测试 pytest",
    "code-review-and-quality": "code review quality audit lint",
    "code-simplification": "refactor simplify clean code",
    "incremental-implementation": "implement feature build code python function",
    "performance-optimization": "optimize performance speed benchmark",
    "security-and-hardening": "security vulnerability audit hardening",
    "weighted-data-pipeline": "data pipeline processing etl csv",
    "scrape": "web scraping requests html parse links extract",
}


class TFIDFRouter(SkillRouter):
    """Match skills using TF-IDF cosine similarity."""

    name = "tfidf"

    def __init__(self):
        self._vectorizer: TfidfVectorizer | None = None
        self._skill_vectors = None
        self._skills: list[SkillMeta] = []
        self._corpus: list[str] = []
        self._index_hash: str = ""

    def _build_index(self, skills: list[SkillMeta]):
        self._skills = skills
        self._corpus = []
        for s in skills:
            synonyms = _SKILL_SYNONYMS.get(s.name, "")
            text = " ".join([
                s.name.replace("-", " "),
                synonyms,
                s.description,
                s.use_when,
                " ".join(s.tags),
                " ".join(s.triggers),
                # Metadata fields for better recall
                s.domain,
                s.phase.value if hasattr(s.phase, "value") else str(s.phase),
                " ".join(s.output_formats),
                " ".join(s.input_types),
                _clean_decision_card(s.decision_card),
            ])
            self._corpus.append(text.lower())

        self._vectorizer = TfidfVectorizer(
            tokenizer=_tokenize,
            max_features=8000,
            ngram_range=(1, 2),
            stop_words=None,  # custom tokenizer handles filtering
            token_pattern=None,  # use custom tokenizer instead
        )
        self._skill_vectors = self._vectorizer.fit_transform(self._corpus)

    def _skills_hash(self, skills: list[SkillMeta]) -> str:
        """Fast hash to detect when index needs rebuilding."""
        return f"{len(skills)}_{sum(hash(s.name) for s in skills) & 0xFFFFFFFF:08x}"

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 20) -> RouteOutput:
        h = self._skills_hash(skills)
        if h != self._index_hash:
            self._build_index(skills)
            self._index_hash = h

        query_lower = query.lower()
        query_words = set(re.findall(r"[a-z]+", query_lower))
        query_vec = self._vectorizer.transform([query_lower])
        similarities = cosine_similarity(query_vec, self._skill_vectors).flatten()

        # Detect intent from query — bigram overrides first, then single words
        intent_phases = set()
        domain_votes: dict[str, int] = {}  # domain → signal count (weighted voting)

        # Bigram overrides (higher priority — consumed tokens skipped in single-word pass)
        query_tokens = re.findall(r"[a-z]+", query_lower)
        consumed_positions = set()
        for i in range(len(query_tokens) - 1):
            bigram = (query_tokens[i], query_tokens[i + 1])
            if bigram in _INTENT_BIGRAM_OVERRIDES:
                ov = _INTENT_BIGRAM_OVERRIDES[bigram]
                if "phase" in ov:
                    intent_phases.add(ov["phase"])
                if "domain" in ov:
                    domain_votes[ov["domain"]] = domain_votes.get(ov["domain"], 0) + 2
                consumed_positions.add(i)
                consumed_positions.add(i + 1)

        # Single word intent — skip consumed tokens
        for i, token in enumerate(query_tokens):
            if i in consumed_positions:
                continue
            if token in _INTENT_PHASE:
                intent_phases.add(_INTENT_PHASE[token])
            if token in _INTENT_DOMAIN:
                d = _INTENT_DOMAIN[token]
                domain_votes[d] = domain_votes.get(d, 0) + 1

        # Chinese intent detection — check for Chinese keywords in query
        for zh_keyword, domain in _INTENT_DOMAIN_ZH.items():
            if zh_keyword in query_lower:
                domain_votes[domain] = domain_votes.get(domain, 0) + 1

        # Multi-domain queries get boosts for ALL matching domains (no penalty)
        intent_domains = set(domain_votes.keys())
        max_domain_votes = max(domain_votes.values()) if domain_votes else 0

        for idx, s in enumerate(self._skills):
            boost = 0.0
            penalty = 0.0

            # Intent-phase alignment (cumulative: more intent words = stronger signal)
            if intent_phases and s.phase.value != "execute":
                if s.phase.value in intent_phases:
                    boost += 0.10 + 0.03 * len(intent_phases)
                else:
                    penalty -= 0.05  # penalty for phase mismatch only

            # Intent-domain alignment — boost only, no penalty
            # Proportional to vote count: domain with more signals gets stronger boost
            if intent_domains and s.domain:
                if s.domain in domain_votes:
                    vote_strength = domain_votes[s.domain] / max(max_domain_votes, 1)
                    boost += 0.08 + 0.07 * vote_strength  # 0.08-0.15 based on signal strength

            # Domain keyword direct match (domain name in query text)
            # Stronger when query has fewer domain signals (focused query)
            if s.domain and any(w in query_lower for w in s.domain.replace("-", " ").split()):
                boost += 0.08 if len(intent_domains) > 1 else 0.12

            # use_when relevance
            if s.use_when and any(w in s.use_when.lower() for w in query_words if len(w) > 3):
                boost += 0.06

            # Name exact match bonus: if query words match skill name words
            name_words = set(s.name.replace("-", " ").lower().split())
            name_hits = query_words & name_words
            if name_hits:
                boost += 0.15 * len(name_hits) / max(len(name_words), 1)

            similarities[idx] += boost + penalty

        top_indices = np.argsort(similarities)[::-1][:top_k]

        candidates = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.01:
                candidates.append(RouteResult(
                    skill=self._skills[idx],
                    score=score,
                    reason=f"tfidf cosine={score:.3f}",
                ))

        global_skills = [r for r in candidates if r.skill.mode == SkillMode.GLOBAL]

        return RouteOutput(
            candidates=candidates,
            global_skills=global_skills,
        )
