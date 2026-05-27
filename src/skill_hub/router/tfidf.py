"""TF-IDF router — local semantic matching without API calls."""

from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import SkillRouter, RouteOutput, RouteResult
from ..models import SkillMeta, SkillMode

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
    "mockup": "design", "wireframe": "design", "ui": "design", "ux": "design",
    "deck": "design", "slide": "design", "presentation": "design",
    "figma": "design", "prototype": "design",
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
}


def _clean_decision_card(text: str) -> str:
    """Remove structured tokens from decision_card that pollute TF-IDF."""
    # Remove [name] mode=X phase=Y hooks=true needs=X,Y
    text = re.sub(r"\[.*?\]\s*", "", text)
    text = re.sub(r"\b(mode|phase|hooks|needs|true|false|on_demand|global|compose)=\S+", "", text)
    text = re.sub(r"\b(define|plan|build|verify|review|ship|execute)\b", "", text)
    return text.strip()


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
            text = " ".join([
                s.name.replace("-", " "),
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
            max_features=5000,
            ngram_range=(1, 2),
            stop_words="english",
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
        intent_domains = set()

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
                    intent_domains.add(ov["domain"])
                consumed_positions.add(i)
                consumed_positions.add(i + 1)

        # Single word intent — skip tokens consumed by bigrams
        for i, token in enumerate(query_tokens):
            if i in consumed_positions:
                continue
            if token in _INTENT_PHASE:
                intent_phases.add(_INTENT_PHASE[token])
            if token in _INTENT_DOMAIN:
                intent_domains.add(_INTENT_DOMAIN[token])

        for idx, s in enumerate(self._skills):
            boost = 0.0
            penalty = 0.0

            # Intent-phase alignment (cumulative: more intent words = stronger signal)
            if intent_phases and s.phase.value != "execute":
                if s.phase.value in intent_phases:
                    boost += 0.10 + 0.03 * len(intent_phases)
                else:
                    penalty -= 0.05  # penalty for phase mismatch

            # Intent-domain alignment
            if intent_domains and s.domain:
                if s.domain in intent_domains:
                    boost += 0.10
                else:
                    penalty -= 0.07  # strong penalty for domain mismatch

            # Domain keyword direct match
            if s.domain and any(w in query_lower for w in s.domain.replace("-", " ").split()):
                boost += 0.08

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
