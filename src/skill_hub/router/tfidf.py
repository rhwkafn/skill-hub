"""TF-IDF router — local semantic matching without API calls.

Uses scikit-learn's TF-IDF vectorizer + cosine similarity.
Good balance of speed and accuracy. No network required.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import SkillRouter, RouteResult
from ..models import SkillMeta


class TFIDFRouter(SkillRouter):
    """Match skills using TF-IDF cosine similarity.

    Builds an index on first call, then reuses it for subsequent queries.
    Good for natural language queries like "my page loads slowly".
    """

    name = "tfidf"

    def __init__(self):
        self._vectorizer: TfidfVectorizer | None = None
        self._skill_vectors = None
        self._skills: list[SkillMeta] = []
        self._corpus: list[str] = []

    def _build_index(self, skills: list[SkillMeta]):
        """Build TF-IDF index from skill metadata."""
        self._skills = skills
        self._corpus = []
        for s in skills:
            # Combine all text fields for rich representation
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

    def route(self, query: str, skills: list[SkillMeta], top_k: int = 10) -> list[RouteResult]:
        # Rebuild index if skills changed
        if not self._skills or len(self._skills) != len(skills):
            self._build_index(skills)

        # Vectorize query
        query_vec = self._vectorizer.transform([query.lower()])

        # Cosine similarity
        similarities = cosine_similarity(query_vec, self._skill_vectors).flatten()

        # Top-k results
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.01:  # minimum threshold
                results.append(RouteResult(
                    skill=self._skills[idx],
                    score=score,
                    reason=f"tfidf cosine={score:.3f}",
                ))

        return results

    def batch_route(self, queries: list[str], skills: list[SkillMeta], top_k: int = 10) -> list[list[RouteResult]]:
        """Efficiently route multiple queries at once."""
        if not self._skills or len(self._skills) != len(skills):
            self._build_index(skills)

        query_vecs = self._vectorizer.transform([q.lower() for q in queries])
        all_sims = cosine_similarity(query_vecs, self._skill_vectors)

        results = []
        for i, query in enumerate(queries):
            sims = all_sims[i]
            top_indices = np.argsort(sims)[::-1][:top_k]
            query_results = []
            for idx in top_indices:
                score = float(sims[idx])
                if score > 0.01:
                    query_results.append(RouteResult(
                        skill=self._skills[idx],
                        score=score,
                        reason=f"tfidf cosine={score:.3f}",
                    ))
            results.append(query_results)

        return results
