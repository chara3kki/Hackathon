#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Run START_V7.command once first so the Python environment is installed."
  read -p "Press Enter to close..."
  exit 1
fi

source .venv/bin/activate
python test_gemini.py

echo ""
read -p "Press Enter to close..."
