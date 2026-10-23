#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$(dirname /app/answers/L5_goals_of_care.json)"
cp "$script_dir/final_answer.json" /app/answers/L5_goals_of_care.json
