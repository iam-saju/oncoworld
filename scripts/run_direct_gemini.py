#!/usr/bin/env python3
"""One-request-per-task Gemini eval for the v2 OncoWorld cases (no Harbor, no agent loop).

The Harbor gemini-cli agent spends several API requests per task (listing the chart, reading files in
batches, writing the answer, plus CLI-internal calls), which exhausts free-tier daily quotas after a
task or two. This runner puts the task instruction and the whole chart into a single prompt, asks for
the final_answer.json object directly, and grades it with the task's own grader and rubric.

Usage:
  export GEMINI_API_KEY=...
  python3 scripts/run_direct_gemini.py                                   # all tasks in the v2 config
  python3 scripts/run_direct_gemini.py --model gemini-3.6-flash \
      --task harbor_cases/dlbcl_0001_bulky_stage_iii_hbv_v2_fhir     # one task (repeatable)

Output: jobs/direct_<model>_<timestamp>/<task>/{prompt.txt,response.json,final_answer.json,reward.json,review.json}
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def build_prompt(task_dir: Path) -> str:
    instruction = (task_dir / "instruction.md").read_text()
    case_dir = task_dir / "environment" / "case"
    parts = [
        instruction,
        "\nIn this setting you have no tools. The full contents of every file under `/app/case/` are "
        "included below. Respond with ONLY the JSON object that you would have written to "
        "`/app/final_answer.json`.\n",
    ]
    for f in sorted(p for p in case_dir.rglob("*") if p.is_file()):
        parts.append(f"\n===== /app/case/{f.relative_to(case_dir)} =====\n{f.read_text()}")
    return "\n".join(parts)


def call_gemini(model: str, prompt: str, api_key: str, retries: int, timeout: int) -> dict:
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(API.format(model=model), data=body, headers={
            "Content-Type": "application/json", "x-goog-api-key": api_key})
        cause = None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code == 429:
                sys.exit(f"429 quota/rate limit for {model}; stopping.\n{msg[:600]}")
            if e.code not in (500, 503) or attempt == retries:
                raise RuntimeError(f"HTTP {e.code}: {msg[:600]}")
            cause = f"HTTP {e.code}: {msg[:200].strip()}"
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt == retries:
                raise RuntimeError(f"request failed: {e}")
            cause = f"{type(e).__name__}: {e}"
        wait = 30 * (attempt + 1)
        print(f"  {cause}, retrying in {wait}s ({attempt + 1}/{retries})")
        time.sleep(wait)


def extract_answer(resp: dict) -> dict:
    text = "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--config", type=Path, default=ROOT / "configs/harbor-gemini-v2-eval.json",
                    help="Harbor config to take the task list from")
    ap.add_argument("--task", action="append", type=Path, help="task dir (overrides --config); repeatable")
    ap.add_argument("--delay", type=float, default=15, help="seconds between requests (per-minute limits)")
    ap.add_argument("--retries", type=int, default=3, help="retries on 500/503/timeout")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("Set GEMINI_API_KEY or GOOGLE_API_KEY.")
    tasks = args.task or [Path(t["path"]) for t in json.loads(args.config.read_text())["tasks"]]
    tasks = [t if t.is_absolute() else ROOT / t for t in tasks]

    out_root = ROOT / "jobs" / f"direct_{args.model}_{datetime.now():%Y%m%d_%H%M%S}"
    rows = []
    for i, task in enumerate(tasks):
        if i:
            time.sleep(args.delay)
        out = out_root / task.name
        out.mkdir(parents=True)
        print(f"[{i + 1}/{len(tasks)}] {task.name}")
        prompt = build_prompt(task)
        (out / "prompt.txt").write_text(prompt)
        try:
            resp = call_gemini(args.model, prompt, api_key, args.retries, args.timeout)
            (out / "response.json").write_text(json.dumps(resp, indent=2))
            (out / "final_answer.json").write_text(json.dumps(extract_answer(resp), indent=2))
        except (RuntimeError, KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"  failed: {e}")
            rows.append((task.name, None, None, f"agent error: {str(e)[:60]}"))
            continue
        subprocess.run([sys.executable, str(task / "tests/grader_v2.py"),
                        "--response", str(out / "final_answer.json"),
                        "--output", str(out / "reward.json"),
                        "--rubric", str(task / "tests/rubric_v2.toml")], check=True, stdout=subprocess.DEVNULL)
        review = json.loads((out / "review.json").read_text())
        rows.append((task.name, review["reward"], f"{review['raw_points']}/{review['max_points']}",
                     ", ".join(review["dangerous_errors"]) or "-"))
        print(f"  reward={review['reward']} points={rows[-1][2]} dangerous={rows[-1][3]}")

    print(f"\nResults in {out_root}\n")
    print(f"{'task':<55} {'reward':>6} {'points':>8}  dangerous errors")
    for name, reward, pts, dang in rows:
        print(f"{name:<55} {'-' if reward is None else reward:>6} {pts or '-':>8}  {dang}")


if __name__ == "__main__":
    main()
