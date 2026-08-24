#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "CHECKING REAL GEMINI AI..."
echo "=========================="
echo ""

if [ ! -d ".venv" ]; then
  echo "Run START_V7_7.command first so the local environment exists."
  read -p "Press Enter to close..."
  exit 1
fi

source .venv/bin/activate
python test_gemini.py

echo ""
read -p "Press Enter to close..."
