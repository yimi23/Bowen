#!/usr/bin/env bash
# setup.sh — One-command environment setup for BOWEN
# Run: bash scripts/setup.sh

set -e

BOWEN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BOWEN_DIR"

echo ""
echo "=== BOWEN Setup ==="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install Phase 1 dependencies only
echo "Installing Phase 1 dependencies..."
pip install --quiet anthropic>=0.40.0 pydantic>=2.0.0 python-dotenv==1.0.0

# Check for .env
if [ ! -f ".env" ] || ! grep -q "ANTHROPIC_API_KEY=." ".env"; then
    echo ""
    echo "[!] ANTHROPIC_API_KEY is not set in .env"
    echo "    Edit .env and add your key before running clawdbot.py"
fi

# Create memory directory
mkdir -p memory/chroma

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Add your ANTHROPIC_API_KEY to .env"
echo "  2. source .venv/bin/activate"
echo "  3. python clawdbot.py"
echo ""
