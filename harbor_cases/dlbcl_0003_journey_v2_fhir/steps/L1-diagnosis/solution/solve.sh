#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$(dirname /app/answers/L1_diagnosis.json)"
cp "$script_dir/final_answer.json" /app/answers/L1_diagnosis.json
