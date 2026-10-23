#!/usr/bin/env bash
# OncoWorld-style verifier entrypoint: shared grader_v2.py, rubric_v2.toml.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
task_dir="$(cd "$script_dir/.." && pwd)"
response_file="${RESPONSE_FILE:-/app/final_answer.json}"
output_file="${REWARD_OUTPUT:-/logs/verifier/reward.json}"

if [ ! -f "$response_file" ] && [ ! -d /app ]; then
  # local smoke test outside the container: grade the reference answer
  response_file="$task_dir/solution/final_answer.json"
  output_file="$task_dir/results/reward.json"
fi

mkdir -p "$(dirname "$output_file")"
if [ ! -f "$response_file" ]; then
  # no answer is a real model failure, not a grading gap: scored, reward 0
  printf '{"status": "no_answer", "reward": 0.0, "passed": false, "dangerous_errors": ["missing_final_answer"], "judge": "none", "items": []}\n' \
    > "$(dirname "$output_file")/review.json"
  printf '{"reward": 0.0, "passed": 0.0, "dangerous_errors": 1.0, "scored": 1.0}\n' > "$output_file"
  cat "$output_file"
  exit 0
fi

# keep the graded answer next to review.json so the job can be re-scored later
cp "$response_file" "$(dirname "$output_file")/final_answer.json" 2>/dev/null || true
python3 "$script_dir/grader_v2.py" --response "$response_file" --output "$output_file" --rubric "$script_dir/rubric_v2.toml"
cat "$output_file"
