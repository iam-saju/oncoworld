#!/usr/bin/env python3
"""Check the optional LLM judge (ONCOWORLD_GRADER=judge) against answers with known verdicts before trusting it as the grader.

Usage: ONCOWORLD_JUDGE_API_KEY=... ONCOWORLD_JUDGE_MODEL=... python3 scripts/calibrate_judge.py [--case dlbcl_0002] [-j 8]

Runs every task's tests/selftest/answers/*.json (gold reference, hand-written bad answers, and real model answers
that the old keyword grader got wrong) through the judge, once per rubric (fhir task; the narrative rendering shares the rubric), and
reports agreement. Each answer costs one judge call; calls run in parallel (-j, default 8; lower it if the provider
rate-limits). A judge worth trusting passes all the dangerous-error cases; inspect every FAIL line before using it.
"""
import argparse
import json
import os
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
os.environ["ONCOWORLD_GRADER"] = "judge"   # this script always evaluates the optional judge
import grader_v2 as G  # noqa: E402


def preflight():
    """One tiny judge call so a wrong key, model id or endpoint fails in seconds, not after minutes of retries."""
    if not G.judge_available():
        sys.exit("set ONCOWORLD_JUDGE_API_KEY and ONCOWORLD_JUDGE_MODEL first")
    print(f"judge: {G.judge_model()} at {os.environ.get('ONCOWORLD_JUDGE_BASE_URL') or 'https://openrouter.ai/api/v1'}")
    print("preflight: one tiny judge call (gives up after 30 s) ...", flush=True)
    t0 = time.time()
    try:
        G.call_judge([{"id": "t1", "text": "The response says hello."}], "hello there", timeout=30)
    except Exception as e:
        body = e.read().decode(errors="replace")[:300] if hasattr(e, "read") else ""
        hint = (" - free models are queued and capped (~50 requests/day without credits); use a paid or stronger model"
                if ":free" in G.judge_model() else "")
        sys.exit(f"preflight judge call failed after {time.time() - t0:.0f}s: {type(e).__name__}: {e} {body}{hint}")
    print(f"preflight ok ({time.time() - t0:.1f}s)", flush=True)


def problems(r: dict, expect: dict) -> list[str]:
    """Same comparison as tests/selftest/run_selftest.py."""
    if r.get("status") != "scored":
        return [f"unscored: {r.get('reason')}"]
    out, met = [], {i["id"] for i in r["items"] if i["met"]}
    if "passed" in expect and r["passed"] != expect["passed"]:
        out.append(f"passed={r['passed']} expected {expect['passed']}")
    if "dangerous" in expect and sorted(r["dangerous_errors"]) != sorted(expect["dangerous"]):
        out.append(f"dangerous={r['dangerous_errors']} expected {expect['dangerous']}")
    out += [f"should meet {i}" for i in expect.get("must_met", []) if i not in met]
    out += [f"should NOT meet {i}" for i in expect.get("must_unmet", []) if i in met]
    if expect.get("all_met") is True:
        out += [f"unmet {i['id']}" for i in r["items"] if i["kind"] != "must_not" and not i["met"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="only tasks whose name contains this")
    ap.add_argument("-j", "--jobs", type=int, default=8, help="parallel judge calls (default 8)")
    args = ap.parse_args()
    tests = sorted((ROOT / "harbor_cases").glob("*_v2_fhir/tests"))
    tests += sorted((ROOT / "harbor_cases_narrative").glob("*_journey_v2/steps/*/tests"))
    if args.case:
        tests = [t for t in tests if args.case in str(t)]
    work = []
    for t in tests:
        name = str(t.relative_to(ROOT)).split("/tests")[0]
        rubric = tomllib.loads((t / "rubric_v2.toml").read_text())
        for f in sorted((t / "selftest" / "answers").glob("*.json")):
            doc = json.loads(f.read_text())
            expect = doc.pop("_expect")
            work.append((name, f.name, rubric, json.dumps(doc, ensure_ascii=False, indent=1), expect))

    preflight()
    print(f"{len(work)} calibration answers in {len(tests)} rubrics, {args.jobs} judge calls at a time\n", flush=True)
    t0, results = time.time(), []

    def run(w):
        name, fname, rubric, answer, expect = w
        s = time.time()
        return name, fname, problems(G.grade(answer, rubric), expect), time.time() - s

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, fut in enumerate(as_completed(pool.submit(run, w) for w in work), 1):
            name, fname, probs, secs = fut.result()
            results.append((name, fname, probs))
            tag = "ok  " if not probs else "FAIL"
            print(f"[{i:>3}/{len(work)}] {tag} {name[:40]:40} {fname[:42]:42} {secs:5.1f}s  {'; '.join(probs)}", flush=True)

    ok = sum(not p for _, _, p in results)
    print(f"\njudge agreement: {ok}/{len(results)} calibration answers ({ok / max(1, len(results)):.0%}) "
          f"in {(time.time() - t0) / 60:.1f} min")
    fails = [(n, f, p) for n, f, p in results if p]
    if fails:
        print("\nFAILs (check whether the judge or the expected label is wrong):")
        for n, f, p in sorted(fails):
            print(f"  {n} / {f}: {'; '.join(p)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
