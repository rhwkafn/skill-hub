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
            ])
            self._corpus.append(text.lower())

        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words="english",
        )
        self._skill_vectors = self._vectorizer.fit_transform(self._corpus)

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 20) -> RouteOutput:
        if not self._skills or len(self._skills) != len(skills):
            self._build_index(skills)

        query_vec = self._vectorizer.transform([query.lower()])
        similarities = cosine_similarity(query_vec, self._skill_vectors).flatten()

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
