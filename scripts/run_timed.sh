#!/usr/bin/env bash
# Run a Harbor config with debug logging, a timestamp on every console line, and a full timeline afterwards.
# Usage: scripts/run_timed.sh <config.json> <job-name>
set -uo pipefail
cfg="${1:?config path}"; name="${2:?job name}"
# API keys (OPENCODE_API_KEY, ANTHROPIC_API_KEY, ...) come from the config's env block; Harbor exits if one is missing.
mkdir -p jobs
log="jobs/$name.console.log"  # outside the job dir so Harbor does not treat it as a resume

echo "[run_timed] start $(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat())") config=$cfg job=$name" | tee -a "$log"
# --yes: Harbor's env-var "Proceed? (Y/n)" prompt has no trailing newline, so it would hang unseen behind the timestamp filter.
harbor run -c "$cfg" --job-name "$name" --debug --yes 2>&1 | python3 -u -c '
import sys, datetime
for line in sys.stdin:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    sys.stdout.write(f"[{ts}] {line}"); sys.stdout.flush()
' | tee -a "$log"
rc=${PIPESTATUS[0]}
echo "[run_timed] end $(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat())") exit=$rc" | tee -a "$log"
if [ -f "jobs/$name/result.json" ]; then
  python3 scripts/job_timeline.py "jobs/$name"
else
  echo "[run_timed] no jobs/$name/result.json, skipping timeline"
fi
