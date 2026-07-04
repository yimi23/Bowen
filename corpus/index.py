"""
corpus/index.py — Verified entries → per-language Chroma collections.

Foundry data lives in corpus/chroma/ with one collection per language
(foundry_<lang>). It NEVER shares a store with tenant memory — house data
and Foundry data are separate universes by construction.

Only verified=true entries are indexed. Re-indexing is idempotent
(entry ids are content hashes).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from corpus.schema import LANGUAGES, entry_id, parse_jsonl_line

logger = logging.getLogger(__name__)

EMBED_MODEL = "all-MiniLM-L6-v2"   # same family as house memory; separate store

_client = None
_embed_fn = None


def _get_collection(lang: str, chroma_dir: Path):
    global _client, _embed_fn
    if _client is None:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(chroma_dir))
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
    return _client.get_or_create_collection(
        name=f"foundry_{lang}",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def reset_client_for_tests() -> None:
    global _client, _embed_fn
    _client = None
    _embed_fn = None


def index_language(lang: str, data_dir: Path, chroma_dir: Path) -> dict:
    """Index every VERIFIED entry for one language. Returns stats."""
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language {lang!r}")

    lang_dir = data_dir / lang
    stats = {"files": 0, "verified": 0, "unverified_skipped": 0, "invalid": 0}
    if not lang_dir.exists():
        return stats

    collection = _get_collection(lang, chroma_dir)

    docs, ids, metas = [], [], []
    for jsonl in sorted(lang_dir.glob("*.jsonl")):
        stats["files"] += 1
        for line in jsonl.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = parse_jsonl_line(line)
            except Exception:
                stats["invalid"] += 1
                continue
            if not entry.verified:
                stats["unverified_skipped"] += 1
                continue
            eid = entry_id(entry)
            docs.append(entry.searchable_text())
            ids.append(eid)
            metas.append({
                "entry_id": eid,
                "entry_type": entry.entry_type,
                "lang": entry.lang,
                "source_doc": entry.source_doc,
                "contributor": entry.contributor,
                "payload": json.dumps(entry.model_dump(), ensure_ascii=False),
            })
            stats["verified"] += 1

    if ids:
        # upsert: idempotent re-index by content hash
        collection.upsert(documents=docs, ids=ids, metadatas=metas)

    logger.info("Corpus indexed", extra={"lang": lang, **stats})
    return stats


def query_language(
    lang: str,
    query: str,
    chroma_dir: Path,
    top_k: int = 5,
    min_relevance: float = 0.3,
) -> list[dict]:
    """Retrieve verified entries relevant to a query. Returns entry payloads."""
    collection = _get_collection(lang, chroma_dir)
    if collection.count() == 0:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        if 1.0 - dist < min_relevance:
            continue
        try:
            payload = json.loads(meta.get("payload", "{}"))
        except Exception:
            payload = {}
        payload["_text"] = doc
        out.append(payload)
    return out
