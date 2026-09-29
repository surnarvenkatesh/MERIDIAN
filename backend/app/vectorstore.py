"""
RAG vector store.

Primary path: ChromaDB (embedded, persistent on disk) with sentence-transformers
embeddings — no external service required, just local pip packages.

Fallback path: if chromadb / sentence-transformers aren't installed (or fail
to load, e.g. no internet to pull the embedding model on first run), we drop
to a small in-process TF-IDF-cosine store. This keeps `/research` fully
functional in constrained environments while preserving the same interface,
so swapping back to Chroma later is a no-op for the rest of the app.
"""
from __future__ import annotations

import logging
import math
import os
import re
import uuid
from collections import Counter

from .config import settings
from .models import Source

logger = logging.getLogger("research_agent.vectorstore")


class VectorStore:
    def add_documents(self, docs: list[str], metadatas: list[dict], ids: list[str] | None = None) -> None:
        raise NotImplementedError

    def query(self, text: str, k: int = 5) -> list[dict]:
        raise NotImplementedError


class ChromaVectorStore(VectorStore):
    def __init__(self) -> None:
        import chromadb
        from chromadb.utils import embedding_functions

        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self._collection = self._client.get_or_create_collection(
            name="research_notes", embedding_function=self._embed_fn
        )

    def add_documents(self, docs: list[str], metadatas: list[dict], ids: list[str] | None = None) -> None:
        if not docs:
            return
        ids = ids or [uuid.uuid4().hex for _ in docs]
        self._collection.add(documents=docs, metadatas=metadatas, ids=ids)

    def query(self, text: str, k: int = 5) -> list[dict]:
        if self._collection.count() == 0:
            return []
        res = self._collection.query(query_texts=[text], n_results=min(k, self._collection.count()))
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"text": doc, "metadata": meta, "score": 1 - dist})
        return out


class InMemoryTfidfStore(VectorStore):
    """Zero-dependency fallback: cosine similarity over TF-IDF vectors."""

    def __init__(self) -> None:
        self._docs: list[str] = []
        self._metas: list[dict] = []
        self._df: Counter = Counter()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def add_documents(self, docs: list[str], metadatas: list[dict], ids: list[str] | None = None) -> None:
        for doc, meta in zip(docs, metadatas):
            self._docs.append(doc)
            self._metas.append(meta)
            for tok in set(self._tokenize(doc)):
                self._df[tok] += 1

    def _vector(self, text: str) -> Counter:
        toks = self._tokenize(text)
        tf = Counter(toks)
        n_docs = max(len(self._docs), 1)
        return Counter(
            {t: (c / len(toks)) * math.log((n_docs + 1) / (self._df.get(t, 0) + 1)) for t, c in tf.items()}
        )

    @staticmethod
    def _cosine(a: Counter, b: Counter) -> float:
        common = set(a) & set(b)
        num = sum(a[t] * b[t] for t in common)
        denom_a = math.sqrt(sum(v * v for v in a.values())) or 1e-9
        denom_b = math.sqrt(sum(v * v for v in b.values())) or 1e-9
        return num / (denom_a * denom_b)

    def query(self, text: str, k: int = 5) -> list[dict]:
        if not self._docs:
            return []
        q_vec = self._vector(text)
        scored = []
        for doc, meta in zip(self._docs, self._metas):
            score = self._cosine(q_vec, self._vector(doc))
            scored.append({"text": doc, "metadata": meta, "score": score})
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:k]


def _build_store() -> VectorStore:
    try:
        return ChromaVectorStore()
    except Exception as exc:  # pragma: no cover - depends on optional deps
        logger.warning("Chroma unavailable (%s); using in-memory TF-IDF vector store fallback", exc)
        return InMemoryTfidfStore()


vector_store = _build_store()


def index_sources(sources: list[Source], page_bodies: dict[str, str]) -> None:
    """Chunk and index fetched page bodies for retrieval-augmented synthesis."""
    docs, metas, ids = [], [], []
    for src in sources:
        body = page_bodies.get(src.url, src.snippet)
        for i, chunk in enumerate(_chunk(body)):
            docs.append(chunk)
            metas.append({"source_id": src.id, "url": src.url, "title": src.title, "chunk": i})
            ids.append(f"{src.id}_{i}")
    vector_store.add_documents(docs, metas, ids)


def _chunk(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks
