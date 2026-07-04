"""
corpus/cli.py — The Foundry corpus CLI.

    python -m corpus.cli ingest <file> --lang pidgin [--contributor NAME] [--model sonnet]
    python -m corpus.cli index --lang pidgin
    python -m corpus.cli stats

ingest: raw .txt/.md/.docx → reviewable JSONL (verified=false, always).
index:  verified entries → the language's dedicated Chroma collection.
stats:  what's proposed vs verified per language.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from corpus.schema import LANGUAGES


def main() -> None:
    parser = argparse.ArgumentParser(prog="corpus")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="propose entries from a raw document")
    p_ingest.add_argument("file", type=Path)
    p_ingest.add_argument("--lang", required=True, choices=LANGUAGES)
    p_ingest.add_argument("--contributor", default="")
    p_ingest.add_argument("--model", default="haiku", help="haiku (default) | sonnet | explicit id")

    p_index = sub.add_parser("index", help="index verified entries into Chroma")
    p_index.add_argument("--lang", required=True, choices=LANGUAGES)

    sub.add_parser("stats", help="proposed vs verified counts per language")

    args = parser.parse_args()
    config = Config()

    if args.command == "ingest":
        from corpus.ingest import ingest_file

        asyncio.run(ingest_file(
            args.file, args.lang, config,
            contributor=args.contributor, model_alias=args.model,
        ))

    elif args.command == "index":
        from corpus.index import index_language

        stats = index_language(args.lang, config.CORPUS_DATA_DIR, config.CORPUS_CHROMA_DIR)
        print(f"✓ {args.lang}: {stats['verified']} verified entries indexed "
              f"({stats['unverified_skipped']} awaiting review, "
              f"{stats['invalid']} invalid, {stats['files']} files)")

    elif args.command == "stats":
        for lang in LANGUAGES:
            lang_dir = config.CORPUS_DATA_DIR / lang
            verified = proposed = 0
            if lang_dir.exists():
                for jsonl in lang_dir.glob("*.jsonl"):
                    for line in jsonl.read_text().splitlines():
                        if not line.strip():
                            continue
                        proposed += 1
                        try:
                            if json.loads(line).get("verified"):
                                verified += 1
                        except Exception:
                            pass
            flag = "enabled" if lang in (config.CORPUS_ENABLED_LANGS or "") else "disabled"
            print(f"  {lang:8s} {verified:4d} verified / {proposed:4d} proposed   [{flag}]")


if __name__ == "__main__":
    main()
