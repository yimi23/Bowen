"""
corpus/schema.py — The Foundry corpus schema.

Three entry types, all carrying the same audit spine (language tag, source
document, contributor, verified flag, timestamp). Entries are stored as
JSONL under corpus/data/<lang>/ — one JSON object per line, human-editable,
because a HUMAN flips verified. The pipeline never self-verifies.

Foundry data and house data do not share a store: corpus vectors live in
corpus/chroma/, never in any tenant's memory.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal, Union

from pydantic import BaseModel, Field, ValidationError

LANGUAGES = ("ijaw", "urhobo", "isoko", "pidgin", "yoruba", "igbo")
LanguageTag = Literal["ijaw", "urhobo", "isoko", "pidgin", "yoruba", "igbo"]
Register = Literal["formal", "neutral", "casual", "intimate"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _EntryBase(BaseModel):
    lang: LanguageTag
    source_doc: str
    contributor: str = ""
    verified: bool = False            # a human flips this — never the pipeline
    created_at: str = Field(default_factory=_now)


class SentencePair(_EntryBase):
    entry_type: Literal["sentence_pair"] = "sentence_pair"
    source_lang: str                  # e.g. "english"
    target_lang: str                  # e.g. "pidgin"
    source: str
    target: str

    def searchable_text(self) -> str:
        return f"{self.source} ||| {self.target}"


class Glossary(_EntryBase):
    entry_type: Literal["glossary"] = "glossary"
    term: str
    gloss: str
    notes: str = ""

    def searchable_text(self) -> str:
        return f"{self.term}: {self.gloss}" + (f" ({self.notes})" if self.notes else "")


class Phrase(_EntryBase):
    entry_type: Literal["phrase"] = "phrase"
    text: str
    translation: str
    register: Register = "neutral"

    def searchable_text(self) -> str:
        return f"{self.text} = {self.translation} [{self.register}]"


CorpusEntry = Union[SentencePair, Glossary, Phrase]

_TYPE_MAP = {
    "sentence_pair": SentencePair,
    "glossary": Glossary,
    "phrase": Phrase,
}


def parse_entry(data: dict) -> CorpusEntry:
    """Validate a raw dict into a typed entry. Raises ValidationError/ValueError."""
    entry_type = data.get("entry_type", "")
    cls = _TYPE_MAP.get(entry_type)
    if cls is None:
        raise ValueError(f"Unknown entry_type: {entry_type!r} (expected one of {list(_TYPE_MAP)})")
    return cls.model_validate(data)


def entry_id(entry: CorpusEntry) -> str:
    """Stable content hash — dedup key for indexing (re-index is idempotent)."""
    return hashlib.sha256(
        f"{entry.lang}|{entry.entry_type}|{entry.searchable_text()}".encode()
    ).hexdigest()[:16]


def parse_jsonl_line(line: str) -> CorpusEntry:
    return parse_entry(json.loads(line))


def dump_jsonl_line(entry: CorpusEntry) -> str:
    return json.dumps(entry.model_dump(), ensure_ascii=False)
