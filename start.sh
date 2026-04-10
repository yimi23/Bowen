#!/bin/bash
# start.sh — Boot BOWEN
# Usage: ./start.sh [--tui | --ui | --server | --cli]
#   ./start.sh          → FastAPI backend + Textual TUI (default)
#   ./start.sh --ui     → FastAPI backend + Vite browser UI (http://localhost:5173)
#   ./start.sh --server → FastAPI backend only (headless, for API use)
#   ./start.sh --cli    → Raw terminal loop (no WebSocket, no TUI)

set -e

BOWEN_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BOWEN_DIR"

# ── Sanity checks ──────────────────────────────────────────────────────────────
if [ ! -f ".bowen_id" ]; then
    echo "ERROR: .bowen_id not found. Is S1 mounted at the right path?"
    exit 1
fi

if [ ! -f ".venv/bin/python3" ]; then
    echo "ERROR: .venv not found. Run:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# ── Ollama (needed for Mem0 embeddings — fails silently if offline) ────────────
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama..."
    OLLAMA_MODELS=/Volumes/S1/ollama/models ollama serve &>/tmp/ollama.log &
    sleep 2
fi

# ── Launch mode ────────────────────────────────────────────────────────────────
MODE="${1:---tui}"

case "$MODE" in
    --cli)
        echo "Starting BOWEN CLI (single-process, no WebSocket)..."
        .venv/bin/python3 clawdbot.py
        ;;

    --server)
        echo "Starting BOWEN FastAPI backend on http://localhost:8000"
        echo "WebSocket at ws://localhost:8000/ws/chat"
        .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
        ;;

    --ui)
        # Browser UI mode: start backend + Vite dev server
        echo "Starting BOWEN backend (logs → /tmp/bowen_server.log)..."
        .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/bowen_server.log 2>&1 &
        BACKEND_PID=$!

        echo "Waiting for backend to be ready (cold start can take ~90s)..."
        for i in $(seq 1 240); do
            if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
                echo "Backend ready."
                break
            fi
            sleep 0.5
            if [ $((i % 60)) -eq 0 ]; then
                echo "  Still loading... ($(echo "scale=0; $i/2" | bc)s elapsed)"
            fi
        done

        if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
            echo "ERROR: Backend failed to start within 120s. Check /tmp/bowen_server.log"
            kill $BACKEND_PID 2>/dev/null
            exit 1
        fi

        trap "echo 'Shutting down BOWEN...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

        # Check if frontend node_modules exists, install if not
        if [ ! -d "frontend/node_modules" ]; then
            echo "Installing frontend dependencies (first run)..."
            cd frontend && npm install && cd ..
        fi

        echo "BOWEN UI starting at http://localhost:5173"
        cd frontend && npm run dev
        kill $BACKEND_PID 2>/dev/null
        ;;

    --tui|*)
        # Two-process mode: start backend, wait until healthy, then launch TUI
        echo "Starting BOWEN backend (logs → /tmp/bowen_server.log)..."
        .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/bowen_server.log 2>&1 &
        BACKEND_PID=$!

        # Wait up to 120s for the backend to become healthy
        # (SentenceTransformer model load from S1 drive takes ~90s on cold start)
        echo "Waiting for backend to be ready (cold start can take ~90s)..."
        for i in $(seq 1 240); do
            if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
                echo "Backend ready."
                break
            fi
            sleep 0.5
            if [ $((i % 60)) -eq 0 ]; then
                echo "  Still loading... ($(echo "scale=0; $i/2" | bc)s elapsed)"
            fi
        done

        if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
            echo "ERROR: Backend failed to start within 120s. Check /tmp/bowen_server.log"
            kill $BACKEND_PID 2>/dev/null
            exit 1
        fi

        # Trap Ctrl+C: kill backend when TUI exits
        trap "echo 'Shutting down BOWEN...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

        # Launch TUI (foreground)
        .venv/bin/python3 tui.py

        # TUI exited — clean up backend
        kill $BACKEND_PID 2>/dev/null
        echo "BOWEN stopped."
        ;;
esac
