#!/bin/bash
# start.sh — Boot BOWEN terminal interface
# Usage: ./start.sh [--cli | --server]
#   ./start.sh        → Textual TUI (default)
#   ./start.sh --cli  → Raw terminal loop (clawdbot.py)
#   ./start.sh --server → FastAPI WebSocket server (port 8000)

set -e

BOWEN_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BOWEN_DIR"

# Verify we're on the right drive
if [ ! -f ".bowen_id" ]; then
    echo "ERROR: .bowen_id not found. Is S1 mounted at the right path?"
    exit 1
fi

# Verify venv
if [ ! -f ".venv/bin/python3" ]; then
    echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Verify Ollama is running (needed for memory embeddings)
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama..."
    OLLAMA_MODELS=/Volumes/S1/ollama/models ollama serve &>/tmp/ollama.log &
    sleep 2
fi

# Launch mode
MODE="${1:---tui}"

case "$MODE" in
    --cli)
        echo "Starting BOWEN CLI..."
        .venv/bin/python3 clawdbot.py
        ;;
    --server)
        echo "Starting BOWEN FastAPI server on port 8000..."
        .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    --tui|*)
        .venv/bin/python3 tui.py
        ;;
esac
