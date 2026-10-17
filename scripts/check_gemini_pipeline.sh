#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

live_api=false
model="${GEMINI_MODEL:-gemini-3.8-flash}"

if [ "${1:-}" = "--live-api" ]; then
  live_api=true
  if [ -n "${2:-}" ]; then
    model="$2"
  fi
elif [ -n "${1:-}" ]; then
  echo "Usage: $0 [--live-api [model]]" >&2
  exit 2
fi

section() {
  printf '\n== %s ==\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

section "Toolchain"
require_command python3
require_command harbor
require_command docker
harbor --version || harbor --help >/dev/null
docker --version

section "Gemini-only config validation"
python3 - <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(".")
configs = [
    root / "configs/harbor-gemini-real-eval.json",
    root / "configs/harbor-gemini-3task-eval.json",
    root / "configs/harbor-gemini-5case-eval.json",
    root / "configs/harbor-gemini-breast-eval.json",
    root / "configs/harbor-gemini-dlbcl-fhir-eval.json",
]
required_task_files = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "tests/test.sh",
    "tests/grader.py",
    "tests/rubric.yaml",
    "solution/final_answer.json",
    "solution/gold_answer.md",
]

errors: list[str] = []
for config_path in configs:
    if not config_path.exists():
        errors.append(f"missing config: {config_path}")
        continue
    try:
        config = json.loads(config_path.read_text())
    except Exception as exc:
        errors.append(f"{config_path}: invalid JSON: {exc}")
        continue

    agents = config.get("agents")
    if not isinstance(agents, list) or len(agents) != 1:
        errors.append(f"{config_path}: expected exactly one Gemini agent")
        continue
    agent = agents[0]
    if agent.get("name") != "gemini-cli":
        errors.append(f"{config_path}: agent name must be gemini-cli")
    model_name = agent.get("model_name", "")
    if not model_name.startswith("google/gemini-"):
        errors.append(f"{config_path}: model_name must be google/gemini-*, got {model_name!r}")
    if agent.get("kwargs", {}).get("disable_web_search") is not True:
        errors.append(f"{config_path}: disable_web_search must be true")

    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append(f"{config_path}: tasks must be a non-empty list")
        continue
    for task in tasks:
        task_path = pathlib.Path(task.get("path", ""))
        if not task_path.is_dir():
            errors.append(f"{config_path}: missing task directory {task_path}")
            continue
        for rel in required_task_files:
            candidate = task_path / rel
            if not candidate.exists():
                errors.append(f"{config_path}: {task_path} missing {rel}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

print("Gemini configs and task structure look consistent.")
PY

section "Local verifier smoke tests"
while IFS= read -r test_script; do
  printf 'Running %s\n' "$test_script"
  "$test_script" >/tmp/oncoworld-reward.json
  python3 - <<'PY'
import json
import pathlib
import sys

reward = json.loads(pathlib.Path("/tmp/oncoworld-reward.json").read_text())
if reward.get("reward") != 1.0:
    print(json.dumps(reward, indent=2), file=sys.stderr)
    sys.exit("reference solution did not score reward 1.0")
PY
done < <(find harbor_cases -mindepth 2 -maxdepth 3 -path '*/tests/test.sh' | sort)
rm -f /tmp/oncoworld-reward.json
echo "All checked-in reference answers scored reward 1.0."

section "Resolved Harbor configs"
harbor run -c ./configs/harbor-gemini-real-eval.json --print-config
harbor run -c ./configs/harbor-gemini-5case-eval.json --print-config

if [ "$live_api" = true ]; then
  section "Live Gemini API preflight"
  scripts/check_gemini_access.sh "$model"
else
  section "Live Gemini API preflight"
  echo "Skipped. Run '$0 --live-api ${model}' after setting GEMINI_API_KEY or GOOGLE_API_KEY."
fi

section "Ready"
echo "Pipeline checks completed."
