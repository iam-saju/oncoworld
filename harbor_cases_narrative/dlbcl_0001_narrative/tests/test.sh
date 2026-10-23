#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case_dir="$(cd "$script_dir/.." && pwd)"
response_file="${RESPONSE_FILE:-/app/final_answer.json}"
output_file="${REWARD_OUTPUT:-/logs/verifier/reward.json}"

if [ ! -f "$response_file" ]; then
  if [ -d /app ]; then
    mkdir -p "$(dirname "$output_file")"
    review_file="$(dirname "$output_file")/review.json"
    cat > "$review_file" <<'JSON'
{
  "reward": 0.0,
  "score": 0,
  "max_score": 100,
  "passed": false,
  "raw_score": 0,
  "penalty": 0,
  "metrics": {},
  "critical_errors": [
    {
      "name": "missing_final_answer",
      "penalty_points": 0
    }
  ]
}
JSON
    cat > "$output_file" <<'JSON'
{
  "reward": 0.0,
  "clinical_correctness": 0.0,
  "staging": 0.0,
  "molecular_classification": 0.0,
  "prognosis": 0.0,
  "first_line_treatment": 0.0,
  "cns_management": 0.0,
  "response_assessment": 0.0
}
JSON
    cat "$output_file"
    exit 0
  else
    response_file="$case_dir/solution/final_answer.json"
    output_file="$case_dir/results/reward.json"
  fi
fi

mkdir -p "$(dirname "$output_file")"
python3 "$script_dir/grader.py" --response "$response_file" --output "$output_file"
cat "$output_file"
