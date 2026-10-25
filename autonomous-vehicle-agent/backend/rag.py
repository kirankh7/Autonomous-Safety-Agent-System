"""Retrieval-augmented generation over long-term memory (historical incidents).

Pipeline (see Checkpoint 3.1):
  1. Each incident becomes one chunk: a metadata header, "[SEP]", then the narrative and lesson
     (DPR-style title prefix, so the embedding captures context).
  2. Chunks are embedded and stored in a FAISS inner-product index (cosine on unit vectors).
  3. A query is embedded, metadata pre-filtered (hazard type), thresholded, then either ranked by
     pure relevance (confidence scoring) or diversified with MMR (research questions).

Embeddings: TF-IDF by default so the project runs offline with no model download. Set
EMBEDDINGS=sentence-transformers (and pip install sentence-transformers) to use all-MiniLM-L6-v2.
"""
import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import faiss
except ImportError:  # numpy fallback keeps the demo working if faiss is unavailable
    faiss = None

from backend import memory

EMBEDDINGS = os.getenv("EMBEDDINGS", "tfidf")
# TF-IDF similarities are lower than neural-embedding similarities, so thresholds differ.
MIN_SCORE = 0.08 if EMBEDDINGS == "tfidf" else 0.35


def chunk_text(incident: dict) -> str:
    header = " | ".join([incident["hazard_type"].replace("_", " "), incident["road_feature"],
                         incident["weather"].replace("_", " ")])
    return f"{header} [SEP] {incident['description']} {incident['lesson']}"


def query_text(hazard_type: str, weather: str, description: str) -> str:
    return f"{hazard_type.replace('_', ' ')} | {weather.replace('_', ' ')} [SEP] {description}"


class IncidentIndex:
    def __init__(self):
        self.incidents: list[dict] = []
        self.vectors = None
        self.index = None
        self.vectorizer = None
        self.encoder = None

    # ----- embedding -----
    def _embed(self, texts: list[str], fit: bool = False) -> np.ndarray:
        if EMBEDDINGS == "sentence-transformers":
            if self.encoder is None:
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            vecs = self.encoder.encode(texts)
        else:
            if fit:
                self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                                  sublinear_tf=True)
                vecs = self.vectorizer.fit_transform(texts).toarray()
            else:
                vecs = self.vectorizer.transform(texts).toarray()
        vecs = np.asarray(vecs, dtype="float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms == 0, 1, norms)

    def build(self) -> None:
        """(Re)build the index from long-term memory. Called at startup and after learning."""
        self.incidents = memory.incidents()
        self.vectors = self._embed([chunk_text(i) for i in self.incidents], fit=True)
        if faiss is not None:
            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(self.vectors)

    def _similarities(self, qvec: np.ndarray) -> list[tuple[int, float]]:
        n = len(self.incidents)
        if self.index is not None:
            scores, ids = self.index.search(qvec, n)
            return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]
        sims = self.vectors @ qvec[0]
        order = np.argsort(-sims)
        return [(int(i), float(sims[i])) for i in order]

    # ----- search -----
    def search(self, query: str, k: int = 3, hazard_type: str | None = None,
               use_mmr: bool = False, lambda_mult: float = 0.5, fetch_k: int = 20,
               min_score: float = MIN_SCORE) -> list[dict]:
        if not self.incidents:
            self.build()
        qvec = self._embed([query])
        candidates = [(i, s) for i, s in self._similarities(qvec)
                      if s >= min_score and (hazard_type is None
                                             or self.incidents[i]["hazard_type"] == hazard_type)]
        candidates = candidates[:fetch_k]
        chosen = self._mmr(candidates, k, lambda_mult) if use_mmr else candidates[:k]
        return [{**self.incidents[i], "score": round(s, 3)} for i, s in chosen]

    def _mmr(self, candidates: list[tuple[int, float]], k: int, lambda_mult: float):
        """Maximal Marginal Relevance: balance relevance to the query against redundancy."""
        selected: list[tuple[int, float]] = []
        remaining = list(candidates)
        while remaining and len(selected) < k:
            def mmr_score(c):
                redundancy = max((float(self.vectors[c[0]] @ self.vectors[s[0]]) for s in selected),
                                 default=0.0)
                return lambda_mult * c[1] - (1 - lambda_mult) * redundancy
            best = max(remaining, key=mmr_score)
            selected.append(best)
            remaining.remove(best)
        return selected


index = IncidentIndex()
