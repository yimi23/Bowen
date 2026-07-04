"""
tests/test_corpus.py — The Foundry's first organ: corpus pipeline.

Schema validation, fixture-document ingestion (seam mocked), verified-only
indexing, language detection, and the acceptance case: a Pidgin message
visibly pulls corpus context into the composed (and logged) prompt.
"""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

import corpus.index as index_mod
from corpus.ingest import chunk_text, ingest_file, read_document
from corpus.retrieval import build_language_pack, detect_language
from corpus.schema import (
    Glossary,
    Phrase,
    SentencePair,
    dump_jsonl_line,
    entry_id,
    parse_entry,
    parse_jsonl_line,
)
from llm.provider import LLMResponse
from tests.conftest import FakeCollection, FakeProvider, make_config


# ── Factories ──────────────────────────────────────────────────────────────────


def make_pair(**overrides) -> dict:
    d = dict(
        entry_type="sentence_pair", lang="pidgin", source_doc="fixture.txt",
        source_lang="english", target_lang="pidgin",
        source="How are you?", target="How you dey?",
    )
    d.update(overrides)
    return d


def make_phrase(**overrides) -> dict:
    d = dict(
        entry_type="phrase", lang="pidgin", source_doc="fixture.txt",
        text="No wahala", translation="No problem", register="casual",
    )
    d.update(overrides)
    return d


# ── 1. Schema validation ───────────────────────────────────────────────────────


class TestSchema:
    def test_all_three_entry_types_parse(self):
        assert isinstance(parse_entry(make_pair()), SentencePair)
        assert isinstance(parse_entry(make_phrase()), Phrase)
        glossary = parse_entry(dict(
            entry_type="glossary", lang="igbo", source_doc="d.txt",
            term="biko", gloss="please", notes="softens requests",
        ))
        assert isinstance(glossary, Glossary)

    def test_entries_default_to_unverified(self):
        assert parse_entry(make_pair()).verified is False

    def test_unsupported_language_rejected(self):
        with pytest.raises(ValidationError):
            parse_entry(make_pair(lang="french"))

    def test_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            parse_entry(dict(entry_type="sentence_pair", lang="pidgin", source_doc="x"))

    def test_unknown_entry_type_rejected(self):
        with pytest.raises(ValueError, match="Unknown entry_type"):
            parse_entry(dict(entry_type="poem", lang="pidgin", source_doc="x"))

    def test_jsonl_roundtrip_and_stable_id(self):
        entry = parse_entry(make_phrase())
        line = dump_jsonl_line(entry)
        back = parse_jsonl_line(line)
        assert back == entry
        assert entry_id(back) == entry_id(entry)


# ── 2. Ingestion (seam mocked) ─────────────────────────────────────────────────


class TestIngestion:
    @pytest.fixture
    def fixture_doc(self, tmp_path):
        doc = tmp_path / "market-phrases.txt"
        doc.write_text(
            "Common Pidgin market phrases.\n\n"
            "How you dey? - How are you?\n"
            "Wetin be the price? - What is the price?\n\n"
            "No wahala means no problem.\n"
        )
        return doc

    async def test_fixture_document_becomes_reviewable_jsonl(self, tmp_path, fixture_doc, monkeypatch):
        proposals = {
            "entries": [
                {"entry_type": "sentence_pair", "source_lang": "pidgin",
                 "target_lang": "english", "source": "Wetin be the price?",
                 "target": "What is the price?"},
                {"entry_type": "phrase", "text": "No wahala",
                 "translation": "No problem", "register": "casual"},
                {"entry_type": "poem", "text": "invalid — wrong type"},   # must be rejected
            ]
        }
        fake = FakeProvider([LLMResponse(structured=proposals)])
        monkeypatch.setattr("corpus.ingest.get_provider", lambda kind, cfg: fake)

        config = make_config(CORPUS_DATA_DIR=tmp_path / "data")
        out = await ingest_file(fixture_doc, "pidgin", config, contributor="praise")

        lines = [json.loads(l) for l in out.read_text().splitlines()]
        assert len(lines) == 2                            # bad proposal rejected
        assert all(e["verified"] is False for e in lines)  # never self-verified
        assert all(e["lang"] == "pidgin" for e in lines)
        assert all(e["source_doc"] == "market-phrases.txt" for e in lines)
        assert all(e["contributor"] == "praise" for e in lines)
        # The seam got the language-specific extraction prompt
        assert "pidgin" in fake.calls[0]["system"]
        assert fake.calls[0]["output_schema"] is not None

    async def test_unsupported_language_refused(self, fixture_doc):
        with pytest.raises(ValueError, match="Unsupported language"):
            await ingest_file(fixture_doc, "french", make_config())

    def test_docx_reader_extracts_paragraph_text(self, tmp_path):
        import zipfile

        docx = tmp_path / "sample.docx"
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr(
                "word/document.xml",
                '<w:document><w:body><w:p><w:r><w:t>Abeg helep me</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>Please help me</w:t></w:r></w:p></w:body></w:document>',
            )
        text = read_document(docx)
        assert "Abeg helep me" in text
        assert "Please help me" in text

    def test_chunking_respects_paragraphs(self):
        text = "\n\n".join(f"Paragraph {i} " + "x" * 500 for i in range(10))
        chunks = chunk_text(text, size=1200)
        assert len(chunks) > 1
        assert all(len(c) <= 1300 for c in chunks)


# ── 3. Indexing: verified entries only, separate store ─────────────────────────


@pytest.fixture
def fake_corpus_chroma(monkeypatch):
    collections: dict[str, FakeCollection] = {}

    class FakeUpsertCollection(FakeCollection):
        def upsert(self, documents, ids, metadatas):
            self.add(documents, metadatas, ids)

    def fake_client(path):
        class Client:
            def get_or_create_collection(self, name, **kw):
                return collections.setdefault(name, FakeUpsertCollection())
        return Client()

    monkeypatch.setattr(index_mod.chromadb, "PersistentClient", fake_client)
    monkeypatch.setattr(
        index_mod.embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda model_name: None,
    )
    index_mod.reset_client_for_tests()
    yield collections
    index_mod.reset_client_for_tests()


class TestIndexing:
    async def test_only_verified_entries_are_indexed(self, tmp_path, fake_corpus_chroma):
        data_dir = tmp_path / "data"
        (data_dir / "pidgin").mkdir(parents=True)
        entries = [
            parse_entry(make_pair(verified=True)),
            parse_entry(make_phrase(verified=False)),
            parse_entry(make_phrase(text="I dey come", translation="I'm coming", verified=True)),
        ]
        (data_dir / "pidgin" / "batch.jsonl").write_text(
            "\n".join(dump_jsonl_line(e) for e in entries)
        )

        stats = index_mod.index_language("pidgin", data_dir, tmp_path / "chroma")

        assert stats["verified"] == 2
        assert stats["unverified_skipped"] == 1
        collection = fake_corpus_chroma["foundry_pidgin"]
        assert collection.count() == 2
        assert all("No wahala" not in doc for doc in collection.docs.values())

    async def test_reindex_is_idempotent(self, tmp_path, fake_corpus_chroma):
        data_dir = tmp_path / "data"
        (data_dir / "pidgin").mkdir(parents=True)
        (data_dir / "pidgin" / "b.jsonl").write_text(
            dump_jsonl_line(parse_entry(make_pair(verified=True)))
        )
        index_mod.index_language("pidgin", data_dir, tmp_path / "chroma")
        index_mod.index_language("pidgin", data_dir, tmp_path / "chroma")
        assert fake_corpus_chroma["foundry_pidgin"].count() == 1   # content-hash ids


# ── 4. Detection ───────────────────────────────────────────────────────────────


class TestDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Abeg, wetin dey happen for market today?", "pidgin"),
            ("How far, you don chop? No wahala if you never.", "pidgin"),
            ("Kedu ka ị mere? Biko nwanne", "igbo"),
            ("Please schedule my meeting for tomorrow at noon.", None),
            ("Refactor the payment module and run the tests.", None),
        ],
    )
    def test_marker_detection(self, text, expected):
        assert detect_language(text) == expected

    def test_disabled_language_never_injects(self, tmp_path):
        config = make_config(CORPUS_ENABLED_LANGS="", CORPUS_CHROMA_DIR=tmp_path)
        assert build_language_pack("Abeg wetin dey happen?", config) is None


# ── 5. The acceptance case: Pidgin message pulls corpus into the prompt ────────


class TestPromptInjection:
    async def test_pidgin_message_pulls_corpus_context_into_logged_prompt(
        self, store, tmp_path, fake_corpus_chroma, caplog
    ):
        from agents.bowen import BOWENAgent
        from bus.message_bus import MessageBus

        # Verified pidgin corpus, indexed
        data_dir = tmp_path / "cdata"
        (data_dir / "pidgin").mkdir(parents=True)
        (data_dir / "pidgin" / "v.jsonl").write_text("\n".join([
            dump_jsonl_line(parse_entry(make_pair(
                source="What is happening?", target="Wetin dey happen?", verified=True))),
            dump_jsonl_line(parse_entry(make_phrase(
                text="Abeg", translation="Please", verified=True))),
        ]))
        index_mod.index_language("pidgin", data_dir, tmp_path / "cchroma")

        config = make_config(
            CORPUS_ENABLED_LANGS="pidgin",
            CORPUS_CHROMA_DIR=tmp_path / "cchroma",
        )
        agent = BOWENAgent(config, store, MessageBus())

        with caplog.at_level(logging.INFO, logger="corpus.retrieval"):
            prompt = await agent.build_system_prompt("Abeg, wetin dey happen for house today?")

        # The corpus context is IN the composed prompt...
        assert "## Language Pack (pidgin)" in prompt
        assert "Wetin dey happen?" in prompt
        assert "Abeg" in prompt
        # ...and the injection is logged (visible corpus pull)
        assert any("language pack injected" in r.message for r in caplog.records)

    async def test_english_message_gets_no_language_pack(self, store, tmp_path, fake_corpus_chroma):
        from agents.bowen import BOWENAgent
        from bus.message_bus import MessageBus

        config = make_config(
            CORPUS_ENABLED_LANGS="pidgin", CORPUS_CHROMA_DIR=tmp_path / "cchroma",
        )
        agent = BOWENAgent(config, store, MessageBus())
        prompt = await agent.build_system_prompt("Summarize my open tasks for the week.")
        assert "## Language Pack" not in prompt
