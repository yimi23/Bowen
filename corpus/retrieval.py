"""
corpus/retrieval.py — The language pack: detect → retrieve → inject.

When an inbound message is detected as a supported Nigerian language (and
that language is enabled in config), the top-k verified corpus entries are
retrieved and injected as few-shot context before the agent replies. The
injection is logged so a corpus hit is always visible in the prompt log.

Detection is deliberately lightweight — marker-word scoring, no model
call. It only needs to be good enough to trigger retrieval; the corpus
itself carries the linguistic weight.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Marker words per language. Strong markers count double.
_MARKERS: dict[str, dict[str, set[str]]] = {
    "pidgin": {
        "strong": {"abeg", "wetin", "una", "sabi", "wahala", "shey", "dey", "oyibo", "japa"},
        "weak": {"oga", "waka", "chop", "gist", "vex", "sef", "abi", "jare", "comot", "yarn", "small small", "how far", "no wahala"},
    },
    "yoruba": {
        "strong": {"bawo", "ẹkaaro", "ekaaro", "ẹkaasan", "jọwọ", "jowo", "ṣeun", "dupe", "olorun"},
        "weak": {"ni", "ti", "wa", "omo", "baba", "iya", "ore", "owo", "oja"},
    },
    "igbo": {
        "strong": {"kedu", "biko", "ndewo", "chineke", "nwanne", "daalu", "maka", "unu"},
        "weak": {"nna", "obi", "ego", "nke", "anyi", "ihe", "onye"},
    },
    "urhobo": {
        "strong": {"migwo", "vrendo", "ọghẹnẹ", "oghene", "mavo", "wado"},
        "weak": {"avwanre", "ọmọ", "eje"},
    },
    "isoko": {
        "strong": {"migwo", "whaọ", "ọghẹnẹ", "yọ", "eva"},
        "weak": {"omo", "uke", "eje"},
    },
    "ijaw": {
        "strong": {"tobaraye", "woyengi", "ebi", "ama", "kẹmẹ"},
        "weak": {"beke", "owei", "ere", "indi"},
    },
}

_DETECTION_THRESHOLD = 2   # score needed to claim a language


def detect_language(text: str) -> Optional[str]:
    """Return the best-matching supported language tag, or None."""
    words = set(re.findall(r"[\w'ẹọṣàáèéìíòóùú]+", text.lower()))
    lowered = text.lower()

    best_lang, best_score = None, 0
    for lang, markers in _MARKERS.items():
        score = 0
        for marker in markers["strong"]:
            if (" " in marker and marker in lowered) or marker in words:
                score += 2
        for marker in markers["weak"]:
            if (" " in marker and marker in lowered) or marker in words:
                score += 1
        if score > best_score:
            best_lang, best_score = lang, score

    return best_lang if best_score >= _DETECTION_THRESHOLD else None


def enabled_languages(config) -> set[str]:
    raw = getattr(config, "CORPUS_ENABLED_LANGS", "") or ""
    return {tag.strip() for tag in raw.split(",") if tag.strip()}


def build_language_pack(query: str, config, top_k: int = 5) -> Optional[str]:
    """
    Detect + retrieve. Returns a prompt section string, or None when no
    supported/enabled language is detected or nothing relevant is indexed.
    Failure-proof: any error returns None — the language pack must never
    break an agent reply.
    """
    try:
        lang = detect_language(query)
        if lang is None or lang not in enabled_languages(config):
            return None

        from corpus.index import query_language

        entries = query_language(lang, query, config.CORPUS_CHROMA_DIR, top_k=top_k)
        if not entries:
            return None

        lines = []
        for e in entries:
            etype = e.get("entry_type", "")
            if etype == "sentence_pair":
                lines.append(f"- {e.get('source', '')} → {e.get('target', '')}")
            elif etype == "glossary":
                lines.append(f"- {e.get('term', '')}: {e.get('gloss', '')}")
            elif etype == "phrase":
                lines.append(f"- \"{e.get('text', '')}\" = {e.get('translation', '')} ({e.get('register', 'neutral')})")
            else:
                lines.append(f"- {e.get('_text', '')}")

        logger.info(
            "corpus language pack injected",
            extra={"lang": lang, "entries": len(lines), "query_preview": query[:60]},
        )
        return (
            f"## Language Pack ({lang})\n"
            f"The user is writing in {lang}. These are verified corpus examples — "
            f"use them to reply naturally and accurately in {lang}:\n" + "\n".join(lines)
        )
    except Exception as exc:
        logger.warning("language pack failed safely: %s: %s", type(exc).__name__, exc)
        return None
