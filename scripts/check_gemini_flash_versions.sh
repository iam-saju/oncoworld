#!/usr/bin/env bash
# Check which Gemini 3.7 / 3.8 flash-family models (flash and flash-lite) your key can
# currently use: lists every matching model from the live API, then probes each one with
# scripts/check_gemini_access.sh (OK / overloaded-503 / quota-429 / other).
#
# Usage:
#   export GEMINI_API_KEY=... (or GOOGLE_API_KEY)
#   scripts/check_gemini_flash_versions.sh                 # versions 3.7 3.8 (default)
#   scripts/check_gemini_flash_versions.sh 3.6 3.7 3.8      # custom version list
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
api_key="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
if [ -z "$api_key" ]; then
  echo "Set GEMINI_API_KEY or GOOGLE_API_KEY before running this check." >&2
  exit 2
fi

if [ "$#" -gt 0 ]; then versions=("$@"); else versions=(3.7 3.8); fi

echo "Fetching model list..."
models_json="$(curl -sS --max-time 30 "https://generativelanguage.googleapis.com/v1beta/models?key=${api_key}&pageSize=200")"

# Build a regex like: gemini-(3\.7|3\.8)-flash(-lite)?$  — flash and flash-lite only,
# excludes -tts/-image/-preview/-customtools/-embedding variants that can't take this prompt.
version_alt="$(IFS='|'; v="${versions[*]}"; echo "${v//./\\.}")"
pattern="models/gemini-(${version_alt})-flash(-lite)?\$"

candidates=()
while IFS= read -r line; do
  [ -n "$line" ] && candidates+=("$line")
done < <(
  echo "$models_json" \
    | grep -o '"name": *"[^"]*"' \
    | sed -E 's/"name": *"([^"]*)"/\1/' \
    | grep -E "^${pattern}" \
    | sed 's#^models/##' \
    | sort -u
)

if [ "${#candidates[@]}" -eq 0 ]; then
  echo "No flash/flash-lite models found for version(s): ${versions[*]}" >&2
  echo "Your key's full model list may use different names; run:" >&2
  echo "  curl -s \"https://generativelanguage.googleapis.com/v1beta/models?key=\$GEMINI_API_KEY\" | grep '\"name\"'" >&2
  exit 1
fi

echo "Checking ${#candidates[@]} model(s): ${candidates[*]}"
echo
printf "%-28s %s\n" "MODEL" "STATUS"
ok_models=()
for m in "${candidates[@]}"; do
  if out="$("$script_dir/check_gemini_access.sh" "$m" 2>&1)"; then
    printf "%-28s %s\n" "$m" "OK"
    ok_models+=("$m")
  else
    reason="$(echo "$out" | grep -m1 "with HTTP" | sed -E 's/.*with HTTP ([0-9]+)\..*/\1/')"
    case "$reason" in
      429) printf "%-28s %s\n" "$m" "QUOTA (429)" ;;
      503) printf "%-28s %s\n" "$m" "OVERLOADED (503)" ;;
      000|"") printf "%-28s %s\n" "$m" "TIMEOUT" ;;
      *) printf "%-28s %s\n" "$m" "FAILED (HTTP $reason)" ;;
    esac
  fi
done

echo
if [ "${#ok_models[@]}" -gt 0 ]; then
  echo "Available now: ${ok_models[*]}"
else
  echo "None of these are available right now."
fi
