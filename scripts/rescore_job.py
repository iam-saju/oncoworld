#!/usr/bin/env python3
"""Re-grade a finished Harbor job with the current v2 grader, without rerunning the models.

Usage: python3 scripts/rescore_job.py jobs/<job> [-j 8]   (regex rules; ONCOWORLD_GRADER=judge for the optional judge)

The answer for each trial comes from <trial>/verifier/final_answer.json when the verifier saved one (tasks built
after 2026-10-22), otherwise it is rebuilt from the agent's own file writes:
  Claude Code  sessions/*.jsonl  Write then Edit calls on /app/final_answer.json, replayed in order
  OpenCode     agent/opencode.txt  write/edit calls; answers built only through bash are replayed in a throwaway
               container (docker, --network none) running the same python:3.11-slim base image
Writes <trial>/verifier/rescored_review.json with the current grader and prints old vs new. Use it after every rule
change: it re-grades saved answers in seconds without rerunning any model.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
import grader_v2  # noqa: E402

ANSWER = "/app/final_answer.json"


def task_dir(path: str) -> Path:
    """A job's task path; narrative tasks moved to harbor_cases_narrative/ on 2026-10-22, so old jobs are remapped."""
    p = ROOT / path
    moved = ROOT / "harbor_cases_narrative" / Path(path).name
    return p if p.exists() or not moved.exists() else moved


def _claude_calls(trial: Path):
    for f in sorted((trial / "agent" / "sessions" / "projects").glob("*/*.jsonl")):
        for line in f.read_text().splitlines():
            e = json.loads(line)
            content = (e.get("message") or {}).get("content")
            if e.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_use":
                        yield b.get("name", "").lower(), b.get("input") or {}


def _opencode_calls(trial: Path):
    log = trial / "agent" / "opencode.txt"
    if not log.exists():
        return
    for line in log.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = e.get("part") or {}
        if e.get("type") == "tool_use" and (part.get("state") or {}).get("status") == "completed":
            yield part.get("tool", "").lower(), part["state"].get("input") or {}


def _replay_bash(commands: list[str]) -> str | None:
    """Run the agent's bash commands in an isolated container and return the resulting answer file."""
    with tempfile.TemporaryDirectory() as d:
        script = Path(d) / "replay.sh"
        script.write_text("mkdir -p /app && cd /app\n" + "\n".join(f"( {c}\n) >/dev/null 2>&1 || true" for c in commands)
                          + f"\ncat {ANSWER}\n")
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{d}:/replay:ro",
                            "python:3.11-slim", "bash", "/replay/replay.sh"], capture_output=True, text=True, timeout=300)
        return r.stdout if r.returncode == 0 and r.stdout.strip() else None


def rebuild_answer(trial: Path) -> tuple[str | None, str]:
    saved = trial / "verifier" / "final_answer.json"
    if saved.exists():
        return saved.read_text(), "saved"
    calls = list(_claude_calls(trial)) or list(_opencode_calls(trial))
    text, bash, edited_by_bash = None, [], False
    for name, inp in calls:
        path = str(inp.get("file_path") or inp.get("filePath") or "")
        if name == "write" and path.endswith("final_answer.json"):
            text = inp.get("content")
        elif name == "edit" and path.endswith("final_answer.json") and text is not None:
            old, new = inp.get("old_string", inp.get("oldString")), inp.get("new_string", inp.get("newString"))
            if inp.get("replace_all") or inp.get("replaceAll"):
                text = text.replace(old, new)
            elif old in text:
                text = text.replace(old, new, 1)
        elif name == "bash":
            cmd = inp.get("command", "")
            bash.append(cmd)
            if "final_answer" in cmd and any(k in cmd for k in ("open(", "json.dump", ">", "tee", "sed -i")):
                edited_by_bash = True
    if text is not None and not edited_by_bash:
        return text, "rebuilt"
    if bash:
        if text is not None:  # a write followed by bash edits: seed the file, then replay
            bash.insert(0, f"cat > {ANSWER} <<'__ONCOWORLD_EOF__'\n{text}\n__ONCOWORLD_EOF__")
        out = _replay_bash(bash)
        if out:
            return out, "replayed"
    return text, "rebuilt" if text is not None else "missing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", type=Path)
    ap.add_argument("-j", "--jobs", type=int, default=8, help="parallel judge calls (default 8)")
    args = ap.parse_args()

    def one(trial: Path) -> str:
        cfg = json.loads((trial / "config.json").read_text())
        task = task_dir(cfg["task"]["path"])
        old = json.loads((trial / "verifier" / "review.json").read_text())
        model = cfg["agent"].get("model_name", "?").split("/")[-1]
        answer, source = rebuild_answer(trial)
        if answer is None:
            return f"{trial.name:44} {model:28} {'missing':9} {old.get('reward', 0):>5}        -  no answer to re-score"
        rubric = tomllib.loads((task / "tests" / "rubric_v2.toml").read_text())
        new = grader_v2.grade(grader_v2.read_response_text(answer), rubric, *grader_v2.judge_inputs(task / "tests" / "rubric_v2.toml"))
        new["answer_source"] = source
        (trial / "verifier" / "rescored_review.json").write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
        shown = new["reward"] if new["status"] == "scored" else "unscored"
        return (f"{trial.name:44} {model:28} {source:9} {old.get('reward', 0):>5} {shown:>8}  "
                f"{','.join(new['dangerous_errors']) or new.get('reason', '-')}")

    def one_journey(trial: Path) -> list[str]:
        """Multi-step journey: each step's saved answer against that step's current rubric (steps/<L>/tests)."""
        cfg = json.loads((trial / "result.json").read_text())["config"]   # trial config.json omits default agent fields
        task = task_dir(cfg["task"]["path"])
        agent = cfg.get("agent") or {}
        model = (agent.get("model_name") or agent.get("name") or "?").split("/")[-1]
        out = []
        for step in sorted(p for p in (trial / "steps").iterdir() if (p / "verifier" / "review.json").exists()):
            old = json.loads((step / "verifier" / "review.json").read_text())
            saved = step / "verifier" / "final_answer.json"
            label = f"{trial.name[:30]}/{step.name.split('-')[0]}"
            if not saved.exists():
                out.append(f"{label:44} {model:28} {'missing':9} {old.get('reward', 0):>5}        -  no answer to re-score")
                continue
            rubric = tomllib.loads((task / "steps" / step.name / "tests" / "rubric_v2.toml").read_text())
            rpath = task / "steps" / step.name / "tests" / "rubric_v2.toml"
            new = grader_v2.grade(grader_v2.read_response_text(saved.read_text()), rubric, *grader_v2.judge_inputs(rpath))
            new["answer_source"] = "saved"
            (step / "verifier" / "rescored_review.json").write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
            shown = new["reward"] if new["status"] == "scored" else "unscored"
            judge_note = f"  JUDGE FAILED, regex used: {new['judge_error'][:160]}" if new.get("judge_error") else ""
            out.append(f"{label:44} {model:28} {'saved':9} {old.get('reward', 0):>5} {shown:>8}  "
                       f"{','.join(new['dangerous_errors']) or new.get('reason', '-')}{judge_note}")
        return out

    journeys = sorted(p for p in args.job.iterdir() if (p / "steps").is_dir())
    trials = sorted(p for p in args.job.iterdir() if (p / "verifier" / "review.json").exists())
    print(f"{len(trials)} trials, {len(journeys)} journey trials, grader: {'judge ' + grader_v2.judge_model() if grader_v2.judge_available() else 'regex rules'}\n")
    print(f"{'trial':44} {'model':28} {'source':9} {'old':>5} {'new':>8}  dangerous (new)", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for fut in as_completed(pool.submit(one, t) for t in trials):
            print(fut.result(), flush=True)
    for trial in journeys:
        for line in one_journey(trial):
            print(line, flush=True)
    print(f"\ndone in {(time.time() - t0) / 60:.1f} min; rebuild the report: python3 scripts/build_report.py {args.job}"
          + (f"; journeys: python3 scripts/summarize_job.py {args.job}" if journeys else ""))


if __name__ == "__main__":
    main()
