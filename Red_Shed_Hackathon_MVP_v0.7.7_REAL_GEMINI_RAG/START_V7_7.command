#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "IS ROWING FOR ME? — RED SHED MVP V7.7 (GEMINI)"
echo "================================================"
echo ""
echo "IMPORTANT:"
echo "V7.7 runs on port 8007 so an older V6/V7 server on port 8000 cannot be mistaken for this version."
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found on this Mac."
  read -p "Press Enter to close..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating local Python environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ -f ".venv/.demo_dependencies_ready" ]; then
  echo "Required packages: READY (using the prepared local environment)"
else
  echo "Installing required packages for the first run..."
  python -m pip install -q --upgrade pip
  if python -m pip install -q --upgrade -r requirements.txt; then
    touch .venv/.demo_dependencies_ready
    echo "Required packages: READY"
  else
    echo ""
    echo "Package installation could not finish."
    echo "If this is the first run, connect to the internet and run START_V7_7.command again."
    echo "If you prepared this demo earlier, do not delete the .venv folder."
    read -p "Press Enter to close..."
    exit 1
  fi
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

echo ""
if grep -Eq '^GEMINI_API_KEY=.+$' .env; then
  echo "Gemini API key: CONFIGURED"
else
  echo "Gemini API key: NOT CONFIGURED"
  echo "AI chat REQUIRES Gemini in V7.7 — no fake local AI fallback is used."
  echo "Run CONFIGURE_GEMINI.command and add a fresh key before testing the chatbot."
fi

echo ""
echo "Starting V7.7 at http://127.0.0.1:8007"
echo "If you still have an old http://127.0.0.1:8000 tab open, CLOSE IT."
echo "Leave this Terminal window open."
echo ""

(sleep 2; open "http://127.0.0.1:8007") &
PORT=8007 python server.py
