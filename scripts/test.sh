#!/bin/bash
# scripts/test.sh — The unified suite: BOWEN (pytest) + GENI (vitest).
# GENI's 19 tests run UNCHANGED against its proven internals; the pytest
# side covers the OS, the gate, the seam, and the merge integration.
set -e
cd "$(dirname "$0")/.."

echo "── BOWEN suite (pytest) ──────────────────────────────────────────"
.venv/bin/python -m pytest

echo ""
echo "── GENI suite (vitest, unchanged) ────────────────────────────────"
cd geni/backend && npm test --silent

echo ""
echo "✅ Unified suite green."
