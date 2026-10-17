#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case_dir="$(cd "$script_dir/.." && pwd)"
response_file="${RESPONSE_FILE:-/app/final_answer.json}"
output_file="${REWARD_OUTPUT:-/logs/verifier/reward.json}"

# Outside the Harbor container (no /app), grade the reference answer locally.
if [ ! -f "$response_file" ] && [ ! -d /app ]; then
  response_file="$case_dir/solution/final_answer.json"
  output_file="$case_dir/results/reward.json"
fi

mkdir -p "$(dirname "$output_file")"
# grader.py handles a missing or malformed answer itself and flags infra_failure / invalid_json in review.json.
python3 "$script_dir/grader.py" --response "$response_file" --output "$output_file"
cat "$output_file"
