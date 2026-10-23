#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$(dirname /app/answers/L4_acute_admission.json)"
cp "$script_dir/final_answer.json" /app/answers/L4_acute_admission.json
