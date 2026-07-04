"""
corpus/ingest.py — Raw document → reviewable JSONL proposals.

Claude (through the LLMProvider seam, structured outputs) reads chunks of
a raw document and proposes typed corpus entries. Every proposal lands
with verified=false. The pipeline NEVER self-verifies — a human reviews
the JSONL and flips the flag. That review step is the whole point.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from llm import get_provider
from corpus.schema import LANGUAGES, dump_jsonl_line, parse_entry

logger = logging.getLogger(__name__)

CHUNK_CHARS = 3000

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entry_type": {"type": "string", "enum": ["sentence_pair", "glossary", "phrase"]},
                    "source_lang": {"type": "string"},
                    "target_lang": {"type": "string"},
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "term": {"type": "string"},
                    "gloss": {"type": "string"},
                    "notes": {"type": "string"},
                    "text": {"type": "string"},
                    "translation": {"type": "string"},
                    "register": {"type": "string", "enum": ["formal", "neutral", "casual", "intimate"]},
                },
                "required": ["entry_type"],
            },
        }
    },
    "required": ["entries"],
}

EXTRACTION_SYSTEM = """\
You are a corpus builder for {lang}, a Nigerian language. From the document
chunk you receive, extract high-quality entries of three kinds:

1. sentence_pair — a sentence in one language with its translation
   (fields: source_lang, target_lang, source, target)
2. glossary — a single term with its meaning
   (fields: term, gloss, notes)
3. phrase — a common expression with translation and register
   (fields: text, translation, register: formal|neutral|casual|intimate)

Rules:
- Extract ONLY what the document actually supports. Never invent
  translations. Skip anything you are unsure of — a human reviews every
  entry, and false entries poison the corpus.
- Preserve orthography and diacritics exactly as written.
- Prefer complete natural sentences over fragments for sentence_pairs.
- If the chunk contains nothing extractable, return an empty entries list.
"""


def read_document(path: Path) -> str:
    """Read .txt / .md directly; .docx via its XML (no extra dependency)."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(errors="replace")
    if suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        # Paragraph boundaries → newlines, then strip all remaining tags
        xml = re.sub(r"</w:p>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        return text
    raise ValueError(f"Unsupported file type: {suffix} (use .txt, .md, or .docx)")


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Chunk on paragraph boundaries, ~size chars per chunk."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if current and len(current) + len(p) > size:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


async def ingest_file(
    path: Path,
    lang: str,
    config,
    contributor: str = "",
    model_alias: str = "haiku",
    out_dir: Path | None = None,
) -> Path:
    """
    Ingest one document. Returns the path of the written JSONL file.
    Every entry lands verified=false — review, then flip.
    """
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language {lang!r} (supported: {', '.join(LANGUAGES)})")

    text = read_document(path)
    chunks = chunk_text(text)
    provider = get_provider("anthropic", config)
    model = {"haiku": config.HAIKU_MODEL, "sonnet": config.SONNET_MODEL}.get(model_alias, model_alias)

    accepted, rejected = [], 0
    for i, chunk in enumerate(chunks):
        response = await provider.complete(
            [{"role": "user", "content": f"Document chunk {i + 1}/{len(chunks)}:\n\n{chunk}"}],
            model=model,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM.format(lang=lang),
            output_schema=EXTRACTION_SCHEMA,
        )
        for raw in (response.structured or {}).get("entries", []):
            raw = {k: v for k, v in raw.items() if v not in ("", None)}
            raw.update(
                lang=lang,
                source_doc=path.name,
                contributor=contributor,
                verified=False,          # the pipeline never self-verifies
            )
            try:
                accepted.append(parse_entry(raw))
            except Exception as exc:
                rejected += 1
                logger.warning("Rejected malformed proposal: %s | %s", exc, json.dumps(raw)[:150])

    out_dir = out_dir or (config.CORPUS_DATA_DIR / lang)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{path.stem}-{stamp}.jsonl"
    out_path.write_text("\n".join(dump_jsonl_line(e) for e in accepted) + ("\n" if accepted else ""))

    logger.info(
        "Corpus ingest complete",
        extra={"file": path.name, "lang": lang, "chunks": len(chunks),
               "proposed": len(accepted), "rejected": rejected, "out": str(out_path)},
    )
    print(f"✓ {len(accepted)} entries proposed ({rejected} rejected) → {out_path}")
    print("  Review the JSONL and flip \"verified\": true on good entries,")
    print(f"  then run:  python -m corpus.cli index --lang {lang}")
    return out_path
