"""Retrieval-augmented generation over long-term memory (historical incidents).

Pipeline (see Checkpoint 3.1):
  1. Each incident becomes one chunk: a metadata header, "[SEP]", then the narrative and lesson
     (DPR-style title prefix, so the embedding captures context).
  2. Chunks are embedded and stored in a vector database with their metadata.
  3. A query is embedded, metadata pre-filtered (hazard type) inside the vector query, thresholded,
     then either ranked by pure relevance (confidence scoring) or diversified with MMR (research).

Vector database (VECTOR_DB):
  chroma (default) - ChromaDB, persistent on disk, all-MiniLM-L6-v2 embeddings (ONNX, downloaded
                     once, about 80 MB), cosine similarity, metadata filter in the query.
  faiss            - offline fallback: FAISS in-memory index over TF-IDF vectors (no download).
SQLite (memory.py) stays the source of truth; the vector database is kept in sync with it.
"""
import os
from pathlib import Path

import numpy as np

from backend import memory

VECTOR_DB = os.getenv("VECTOR_DB", "chroma").strip().lower()
CHROMA_PATH = os.getenv("CHROMA_PATH", str(Path(__file__).resolve().parent.parent / "chroma_db"))
COLLECTION = "incidents"

# Similarity thresholds: strict for confidence scoring (precision), looser for research (recall).
THRESHOLDS = {"chroma": {"scoring": 0.75, "research": 0.45},
              "faiss": {"scoring": 0.08, "research": 0.05}}


def chunk_text(incident: dict) -> str:
    header = " | ".join([incident["hazard_type"].replace("_", " "), incident["road_feature"],
                         incident["weather"].replace("_", " ")])
    return f"{header} [SEP] {incident['description']} {incident['lesson']}"


def query_text(hazard_type: str, weather: str, description: str) -> str:
    return f"{hazard_type.replace('_', ' ')} | {weather.replace('_', ' ')} [SEP] {description}"


def _unit(vecs) -> np.ndarray:
    vecs = np.asarray(vecs, dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.where(norms == 0, 1, norms)


class ChromaStore:
    """ChromaDB collection holding one chunk per incident, with metadata for filtering."""
    name = "ChromaDB (all-MiniLM-L6-v2)"

    def __init__(self):
        import chromadb
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    def sync(self, incidents: list[dict]) -> None:
        wanted = {i["id"]: i for i in incidents}
        stored = set(self.collection.get(include=[])["ids"])
        if stale := sorted(stored - wanted.keys()):        # e.g. after "Reset All Memory"
            self.collection.delete(ids=stale)
        if new := [wanted[i] for i in sorted(wanted.keys() - stored)]:
            self.collection.add(
                ids=[i["id"] for i in new], documents=[chunk_text(i) for i in new],
                metadatas=[{"hazard_type": i["hazard_type"], "segment": i["segment"],
                            "outcome": i["outcome"], "source": i["source"]} for i in new])

    def query(self, text: str, n: int, hazard_type: str | None):
        """Return [(incident_id, cosine similarity, unit vector)] best first."""
        count = self.collection.count()
        if not count:
            return []
        res = self.collection.query(query_texts=[text], n_results=min(n, count),
                                    where={"hazard_type": hazard_type} if hazard_type else None,
                                    include=["distances", "embeddings"])
        vecs = _unit(res["embeddings"][0]) if len(res["ids"][0]) else []
        return [(rid, 1 - d, v) for rid, d, v in zip(res["ids"][0], res["distances"][0], vecs)]


class FaissStore:
    """Offline fallback: FAISS inner-product index over TF-IDF vectors, rebuilt on each sync."""
    name = "FAISS (TF-IDF)"

    def __init__(self):
        import faiss
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.faiss, self.vectorizer_cls = faiss, TfidfVectorizer
        self.ids, self.meta, self.vectors, self.index, self.vectorizer = [], [], None, None, None

    def sync(self, incidents: list[dict]) -> None:
        self.vectorizer = self.vectorizer_cls(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.vectors = _unit(self.vectorizer.fit_transform([chunk_text(i) for i in incidents]).toarray())
        self.ids, self.meta = [i["id"] for i in incidents], [i["hazard_type"] for i in incidents]
        self.index = self.faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def query(self, text: str, n: int, hazard_type: str | None):
        qvec = _unit(self.vectorizer.transform([text]).toarray())
        scores, idx = self.index.search(qvec, len(self.ids))
        hits = [(int(i), float(s)) for i, s in zip(idx[0], scores[0])
                if i >= 0 and (hazard_type is None or self.meta[i] == hazard_type)]
        return [(self.ids[i], s, self.vectors[i]) for i, s in hits[:n]]


class IncidentIndex:
    def __init__(self):
        self.store = None
        self.backend = VECTOR_DB

    def _ensure_store(self):
        if self.store is None:
            try:
                self.store = ChromaStore() if VECTOR_DB == "chroma" else FaissStore()
            except Exception as exc:  # e.g. chromadb missing or model download blocked
                print(f"[rag] {VECTOR_DB} unavailable ({type(exc).__name__}: {exc}); using FAISS fallback")
                self.store = FaissStore()
            self.backend = "chroma" if isinstance(self.store, ChromaStore) else "faiss"

    @property
    def name(self) -> str:
        self._ensure_store()
        return self.store.name

    def build(self) -> None:
        """Sync the vector database with long-term memory. Called at startup and after learning."""
        self._ensure_store()
        self.store.sync(memory.incidents())

    def search(self, query: str, k: int = 3, hazard_type: str | None = None,
               use_mmr: bool = False, lambda_mult: float = 0.5, fetch_k: int = 20,
               purpose: str = "scoring") -> list[dict]:
        self._ensure_store()
        min_score = THRESHOLDS[self.backend][purpose]
        candidates = [c for c in self.store.query(query, fetch_k, hazard_type) if c[1] >= min_score]
        chosen = self._mmr(candidates, k, lambda_mult) if use_mmr else candidates[:k]
        results = []
        for rid, score, _ in chosen:
            incident = memory.get_incident(rid)
            if incident:
                results.append({**incident, "score": round(score, 3)})
        return results

    @staticmethod
    def _mmr(candidates, k: int, lambda_mult: float):
        """Maximal Marginal Relevance: balance relevance to the query against redundancy."""
        selected, remaining = [], list(candidates)
        while remaining and len(selected) < k:
            def mmr_score(c):
                redundancy = max((float(c[2] @ s[2]) for s in selected), default=0.0)
                return lambda_mult * c[1] - (1 - lambda_mult) * redundancy
            best = max(remaining, key=mmr_score)
            selected.append(best)
            remaining.remove(best)
        return selected


index = IncidentIndex()
