#!/usr/bin/env bash
set -euo pipefail

model="${1:-gemini-3.8-flash}"
api_key="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"

if [ -z "$api_key" ]; then
  echo "Set GEMINI_API_KEY or GOOGLE_API_KEY before running this check." >&2
  exit 2
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

status="$(
  curl -sS \
    -o "$tmp" \
    -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -X POST \
    "https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${api_key}" \
    -d '{"contents":[{"parts":[{"text":"Reply with OK."}]}]}'
)"

if [ "$status" = "200" ]; then
  echo "Gemini API access OK for ${model}."
  exit 0
fi

echo "Gemini API check failed for ${model} with HTTP ${status}." >&2
if command -v jq >/dev/null 2>&1; then
  jq -r '.error.message // .error.status // . // empty' "$tmp" >&2 || cat "$tmp" >&2
else
  cat "$tmp" >&2
fi

case "$status" in
  403)
    echo "403 means the API key's Google project is not allowed to call this API/model. Use a different enabled Gemini API key/project, or resolve the project access issue in Google AI Studio/Google Cloud." >&2
    ;;
  429)
    echo "429 means quota/rate limit. Wait for quota reset, reduce runs, or use a key/project with quota." >&2
    ;;
esac

exit 1
