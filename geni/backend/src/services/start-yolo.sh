#!/bin/bash
# Start GENI Master Sensing (YOLO Emergency Detection)
# This script runs the Python YOLO pose detection service
# It communicates with the Node.js backend via HTTP

cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    exit 1
fi

# Check if required packages are installed
echo "📦 Checking Python dependencies..."
python3 -m pip list | grep -q ultralytics || {
    echo "⚠️  ultralytics not found. Installing..."
    python3 -m pip install ultralytics opencv-python torch requests
}

# Download YOLOv8 model if not exists
if [ ! -f "yolov8n-pose.pt" ]; then
    echo "📥 Downloading YOLOv8n-pose model (~50MB)..."
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"
fi

# Set backend URL
export YOLO_BACKEND_URL="${1:-http://localhost:5001}"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║  🚀 GENI Master Sensing (YOLO) Starting...                ║"
echo "║                                                            ║"
echo "║  Backend: $YOLO_BACKEND_URL"
echo "║  Model:   YOLOv8n-pose (skeleton detection)               ║"
echo "║                                                            ║"
echo "║  Press Ctrl+C to stop                                      ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Run the YOLO service
python3 ./yolo_master.py
