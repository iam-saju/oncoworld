#!/usr/bin/env python3
"""Measure graders against the grading truth set (cases_src/truth_set).

Usage: python3 scripts/truth_report.py [--grader regex|judge|both] [--show N]

For every packet with a label file, re-grades the saved answer with the CURRENT grader and compares item verdicts with
the truth labels. Reports overall and per-severity agreement, error direction (false credit = grader says met/not
committed but truth disagrees in the model's favour, etc.), and lists disagreements and borderline (low/medium
confidence) labels for oncologist review. `judge` needs the ONCOWORLD_JUDGE_* variables (see grader_v2.py).
"""
import argparse
import json
import os
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
import grader_v2 as G  # noqa: E402

TS = ROOT / "cases_src" / "truth_set"


def verdicts(packet: dict, mode: str, refresh: bool = False) -> dict[str, bool]:
    rubric = tomllib.loads((ROOT / packet["rubric"]).read_text())
    text = G.read_response_text(json.dumps(packet["answer"], ensure_ascii=False))
    if mode == "regex":
        return {i["id"]: bool(G.rule_met(i, text.lower())) for i in rubric["items"]}
    cache = TS / "judge_cache" / G.judge_model() / f"{packet['id']}.json"
    if cache.exists() and not refresh:
        return {k: v["met"] for k, v in json.loads(cache.read_text()).items()}
    os.environ["ONCOWORLD_GRADER"] = "judge"
    rp = ROOT / packet["rubric"]
    probes = rp.parent / "selftest" / ("probes.json" if rp.name == "rubric_v2.toml" else f"probes/{rp.name[:2]}.json")
    probes = json.loads(probes.read_text()) if probes.exists() else []
    r = G.grade(text, rubric, packet.get("context", ""), probes)
    if r.get("judge_error"):
        raise SystemExit(f"judge failed on {packet['id']}: {r['judge_error']}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({i["id"]: {"met": bool(i["met"]), "quote": i.get("evidence", ""), "source": i["source"]}
                                 for i in r["items"]}, indent=1, ensure_ascii=False))
    return {i["id"]: bool(i["met"]) for i in r["items"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grader", default="regex", choices=["regex", "judge", "both"])
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--refresh", action="store_true", help="ignore cached judge verdicts and call the judge again")
    args = ap.parse_args()
    modes = ["regex", "judge"] if args.grader == "both" else [args.grader]
    packets = {p.stem: json.loads(p.read_text()) for p in sorted((TS / "packets").glob("*.json"))}
    labels = {p.stem: json.loads(p.read_text())["labels"] for p in sorted((TS / "labels").glob("*.json"))}
    common = [k for k in packets if k in labels]
    print(f"{len(common)} labelled answers of {len(packets)} packets")
    borderline, all_v = [], {}
    for mode in modes:
        stats = defaultdict(lambda: [0, 0])     # severity -> [agree, total]
        errs = defaultdict(int)
        dis = []
        for k in common:
            pk, lab = packets[k], labels[k]
            v = verdicts(pk, mode, args.refresh)
            all_v.setdefault(k, {})[mode] = v
            for it in pk["items"]:
                t = lab.get(it["id"])
                if t is None:
                    continue
                g, truth = v.get(it["id"], False), bool(t["met"])
                for sev in (it["severity"], "ALL"):
                    stats[sev][1] += 1
                    stats[sev][0] += g == truth
                if g != truth:
                    bad_for_model = (g and it["kind"] == "must_not") or (not g and it["kind"] != "must_not")
                    errs["too harsh (model penalised wrongly)" if bad_for_model else "too lenient (error or miss let through)"] += 1
                    dis.append((it["severity"], k, it["id"], it["kind"], g, truth, t.get("quote", "")[:110]))
                if mode == modes[0] and t.get("confidence") in ("low", "medium"):
                    borderline.append((k, it["id"], it["severity"], t["met"], t.get("note", "")))
        print(f"\n=== {mode} grader vs truth")
        for sev in ("ALL", "dangerous", "important", "minor"):
            a, n = stats[sev]
            if n:
                print(f"  {sev:10} {a}/{n} = {100 * a / n:.1f}%")
        for e, c in errs.items():
            print(f"  {e}: {c}")
        order = {"dangerous": 0, "important": 1, "minor": 2}
        print(f"  disagreements (dangerous first, up to {args.show}):")
        for sev, k, iid, kind, g, truth, q in sorted(dis, key=lambda d: order[d[0]])[: args.show]:
            print(f"    [{sev[:4]}] {k} {iid} ({kind}) grader={g} truth={truth} | {q}")
    if len(modes) == 2:   # hybrid: accept where regex and judge agree, send disagreements to review
        agree = review = wrong = 0
        sev_stats = defaultdict(lambda: [0, 0, 0])   # agreed-correct, agreed-total, review
        missed_dangerous = []
        for k in common:
            for it in packets[k]["items"]:
                t = labels[k].get(it["id"])
                if t is None:
                    continue
                r, j = all_v[k]["regex"].get(it["id"], False), all_v[k]["judge"].get(it["id"], False)
                if r == j:
                    agree += 1; sev_stats[it["severity"]][1] += 1
                    if r == bool(t["met"]):
                        sev_stats[it["severity"]][0] += 1
                    else:
                        wrong += 1
                        if it["severity"] == "dangerous":
                            missed_dangerous.append((k, it["id"], r, t["met"]))
                else:
                    review += 1; sev_stats[it["severity"]][2] += 1
        n = agree + review
        print(f"\n=== hybrid (accept agreement, review disagreement)")
        print(f"  auto-decided {agree}/{n} ({100 * agree / n:.1f}%), correct {agree - wrong}/{agree} = {100 * (agree - wrong) / agree:.1f}%")
        for sev in ("dangerous", "important", "minor"):
            c, a, rv = sev_stats[sev]
            if a:
                print(f"  {sev:10} auto {c}/{a} = {100 * c / a:.1f}% correct, {rv} sent to review")
        print(f"  review queue: {review} items over {len(common)} answers ({review / len(common):.1f} per answer)")
        print(f"  dangerous errors BOTH graders missed: {missed_dangerous or 'none'}")
    print(f"\nborderline truth labels for the oncologist ({len(borderline)}):")
    for k, iid, sev, met, note in borderline[: args.show]:
        print(f"  [{sev[:4]}] {k} {iid} truth={met}: {note}")


if __name__ == "__main__":
    main()
