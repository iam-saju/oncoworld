#!/usr/bin/env python3
"""Gate for regex rule changes: calibration answers + oncologist probes, straight from cases_src (no rebuild needed).

Usage: python3 scripts/check_rules.py [dlbcl_0002 | journey_L3 ...] [-v]

For each rubric: the gold answer must meet every must/should item and no must_not item; every calibration answer in
selftest/ must reach its expected verdict; every probe sentence must fire (or not) as labelled. -v lists each failure.
Exit code 1 on any calibration failure (probe disagreements are reported but do not fail the gate, so the gate can
be tightened probe by probe). Held-out probes (sentences written by agents who never saw the rules) are a
generalisation benchmark and never gate.
"""
import argparse
import glob
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
sys.path.insert(0, str(ROOT / "scripts"))
import grader_v2 as G  # noqa: E402
import probe_rules as P  # noqa: E402

CASES = ["dlbcl_0001", "dlbcl_0002", "dlbcl_0003", "dlbcl_0004", "dlbcl_0005"]
LAYERS = ["L2", "L3", "L4", "L5"]


def rubric_sets():
    for c in CASES:
        d = ROOT / "cases_src" / c
        yield (c, d / "rubric_v2.toml", d / "gold.json", d / "selftest" / "answers", d / "selftest" / "probes.json",
               d / "selftest" / "heldout_probes.json")
    # hand-built cases that live directly under harbor_cases/ (no cases_src/ source, built once, edited in place):
    # rubric/gold/calibration come from the narrative task; the fhir task's own rubric copy is kept byte-identical
    # to it (checked separately, not duplicated here) rather than re-run against the same calibration set twice.
    m = ROOT / "harbor_cases" / "intracranial_mesenchymal_0001_narrative"
    yield ("intracranial_mesenchymal_0001", m / "tests" / "rubric_v2.toml", m / "solution" / "final_answer.json",
           m / "selftest" / "answers", m / "selftest" / "probes.json", m / "selftest" / "heldout_probes.json")
    j = ROOT / "cases_src" / "dlbcl_0003_journey"
    for L in LAYERS:
        yield (f"journey_{L}", j / f"{L}_rubric.toml", j / f"{L}_gold.json", j / "selftest" / L,
               j / "selftest" / "probes" / f"{L}.json", j / "selftest" / "probes" / f"{L}_heldout.json")


def calibration(rubric, gold, answer_dir):
    docs = [("gold", dict(gold, _expect={"passed": True, "dangerous": [], "all_met": True}))]
    docs += [(Path(f).name, json.loads(Path(f).read_text())) for f in sorted(glob.glob(str(answer_dir / "*.json")))]
    bad = []
    for name, doc in docs:
        doc = dict(doc)
        e = doc.pop("_expect")
        r = G.score(json.dumps(doc, ensure_ascii=False, indent=1), rubric)
        met = {i["id"] for i in r["items"] if i["met"]}
        pr = []
        if "passed" in e and r["passed"] != e["passed"]:
            pr.append(f"passed={r['passed']}")
        if "dangerous" in e and sorted(r["dangerous_errors"]) != sorted(e["dangerous"]):
            pr.append(f"dangerous={r['dangerous_errors']} expected {e['dangerous']}")
        pr += [f"should meet {i}" for i in e.get("must_met", []) if i not in met]
        pr += [f"should NOT meet {i}" for i in e.get("must_unmet", []) if i in met]
        if e.get("all_met"):
            pr += [f"unmet {i['id']}" for i in r["items"] if i["kind"] != "must_not" and not i["met"]]
        if pr:
            bad.append((name, pr))
    return len(docs), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="*")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    tc = tcb = tp = tpb = th = thb = 0
    for name, rp, gp, ad, pp, hp in rubric_sets():
        if args.only and name not in args.only:
            continue
        rubric = tomllib.loads(rp.read_text())
        n, bad = calibration(rubric, json.loads(gp.read_text()), ad)
        probes = json.loads(pp.read_text()) if pp.exists() else []
        wrong = P.run_probes(rubric, probes, quiet=True)
        tc, tcb, tp, tpb = tc + n, tcb + len(bad), tp + len(probes), tpb + len(wrong)
        fa = sum(1 for w in wrong if not w["fire"])
        held = json.loads(hp.read_text()) if hp.exists() else []
        hwrong = P.run_probes(rubric, held, quiet=True)
        th, thb = th + len(held), thb + len(hwrong)
        print(f"{name:12} calibration {n - len(bad)}/{n}   probes {len(probes) - len(wrong)}/{len(probes)} "
              f"({fa} false alarms, {len(wrong) - fa} misses)   held-out {len(held) - len(hwrong)}/{len(held)}")
        for b in bad:
            print(f"   CALIBRATION FAIL {b[0]}: {'; '.join(b[1])}")
        if args.verbose:
            for w in wrong:
                kind = "FALSE ALARM" if not w["fire"] else "MISS"
                print(f"   {kind:11} {w['item']:34} [{w['field']}] ({w['category']}) {w['text']}")
    print(f"TOTAL calibration {tc - tcb}/{tc}   probes {tp - tpb}/{tp}   held-out {th - thb}/{th} (benchmark, not gating)")
    sys.exit(1 if tcb else 0)


if __name__ == "__main__":
    main()
