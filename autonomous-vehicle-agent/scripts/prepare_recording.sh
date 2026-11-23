#!/usr/bin/env bash
# Get the app into a clean, ready-to-record state. Run it before every take.
#   ./scripts/prepare_recording.sh
# It resets memory to the 20 seed incidents (no browser confirm box), clears the playground,
# loads the local model onto the GPU, and checks that everything is healthy.
set -u
API="${API:-http://localhost:8000}"

echo "1. Backend"
curl -sf "$API/api/state" >/dev/null || { echo "   Backend is not running. Start it with: uvicorn backend.main:app --port 8000"; exit 1; }
echo "   ok"

echo "2. Reset memory and playground"
curl -s -X POST "$API/api/playground/reset" >/dev/null
curl -s -X POST "$API/api/simulation/reset?full=true" >/dev/null
echo "   done (20 incidents, no hazards, no alerts)"

echo "3. Local model (Ollama)"
if curl -sf localhost:11434/api/version >/dev/null; then
  # A throwaway question loads qwen2.5:7b onto the GPU so the first answer on camera is fast.
  curl -s -X POST "$API/api/research" -H 'content-type: application/json' \
       -d '{"question":"What has long-term memory learned from feedback?"}' >/dev/null
  ollama ps 2>/dev/null | tail -n +2 | awk '{print "   loaded: "$1"  "$5" "$6}'
else
  echo "   Ollama is not running. Start it with: ollama serve   (the app would use rule-based answers)"
fi

echo "4. Check the sidebar says: LLM: ollama local (qwen2.5:7b)"
echo "   Reload the browser page (Cmd+R), then start recording."
