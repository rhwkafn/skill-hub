"""TF-IDF router — local semantic matching without API calls."""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import SkillRouter, RouteOutput, RouteResult
from ..models import SkillMeta, SkillMode


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
                # Previously excluded fields — now included for better recall
                s.domain,
                s.phase.value if hasattr(s.phase, "value") else str(s.phase),
                " ".join(s.output_formats),
                " ".join(s.input_types),
                s.decision_card,
                " ".join(s.category.split()) if s.category else "",
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
        query_vec = self._vectorizer.transform([query_lower])
        similarities = cosine_similarity(query_vec, self._skill_vectors).flatten()

        # Domain/phase keyword boost: if query contains domain/phase terms,
        # boost skills that match
        query_words = set(query_lower.split())
        for idx, s in enumerate(self._skills):
            boost = 0.0
            if s.domain and any(w in query_lower for w in s.domain.replace("-", " ").split()):
                boost += 0.08
            if s.phase.value != "execute":
                phase_words = {"define": ["spec", "requirement", "brainstorm"],
                               "plan": ["plan", "architecture", "roadmap"],
                               "build": ["implement", "create", "write", "build"],
                               "verify": ["test", "debug", "validate"],
                               "review": ["review", "audit", "refactor"],
                               "ship": ["deploy", "release", "document"]}
                if any(w in query_lower for w in phase_words.get(s.phase.value, [])):
                    boost += 0.05
            if s.use_when and any(w in s.use_when.lower() for w in query_words if len(w) > 3):
                boost += 0.06
            similarities[idx] += boost

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
