#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

echo ""
echo "V7.7 Gemini configuration"
echo "-----------------------"
echo "TextEdit will open your LOCAL .env file."
echo ""
echo "1. Create/use a FRESH Gemini API key."
echo "2. Paste it only after GEMINI_API_KEY="
echo "3. Save the file."
echo "4. Do not send the key in chat or screenshots."
echo ""

open -e ".env"

echo "V7.7 uses this key for REAL Gemini-generated RAG answers grounded in Red Shed website excerpts."
