#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "PREPARE RED SHED DEMO — V7.7"
echo "============================"
echo ""
echo "This prepares the local Python environment now, so the live demo does not"
echo "need to reinstall packages later."
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found."
  read -p "Press Enter to close..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -q --upgrade pip

if python -m pip install -q --upgrade -r requirements.txt; then
  touch .venv/.demo_dependencies_ready
  echo ""
  echo "DEMO DEPENDENCIES: READY"
  echo "You can now use START_V7_7.command later without reinstalling packages."
else
  echo ""
  echo "Preparation failed. Check your internet connection and try again."
fi

echo ""
read -p "Press Enter to close..."
