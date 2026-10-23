#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$(dirname /app/answers/L3_second_line.json)"
cp "$script_dir/final_answer.json" /app/answers/L3_second_line.json
