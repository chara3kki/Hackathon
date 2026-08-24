#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "Run START_V7_7.command first."
  read -p "Press Enter to close..."
  exit 1
fi
source .venv/bin/activate
python red_shed_crawler.py
echo ""
read -p "Finished. Press Enter to close..."
