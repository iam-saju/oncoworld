#!/usr/bin/env python3
"""Measure regex-grader vs. blind oncologist-label agreement on one or more filled-in worksheets.

Per the revised validation plan's step 3: "score once and report agreement, whatever it is" - with Cohen's
kappa (not raw percent, which is misleadingly high whenever most items are clean "not met"), an FP/FN split,
and safety-item (severity=dangerous) disagreements broken out separately from minor ones, since one missed
dangerous item matters more than ten minor ones.

Usage: python3 scripts/grader_oncologist_agreement.py <rubric.toml> <filled_worksheet.json> [<filled_worksheet.json> ...]

Each worksheet must have every item's "label" filled in (true/false, not null) - this refuses to score a
worksheet with any item still unlabeled, rather than silently skipping it.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path


def cohens_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """pairs: list of (regex_met, oncologist_label). None if too few observations or undefined (no variance)."""
    n = len(pairs)
    if n == 0:
        return None
    both_true = sum(1 for r, o in pairs if r and o)
    both_false = sum(1 for r, o in pairs if not r and not o)
    po = (both_true + both_false) / n
    p_regex_true = sum(1 for r, _ in pairs if r) / n
    p_oncologist_true = sum(1 for _, o in pairs if o) / n
    pe = p_regex_true * p_oncologist_true + (1 - p_regex_true) * (1 - p_oncologist_true)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else None  # undefined: no variance in either rater, but they still agree/disagree
    return (po - pe) / (1 - pe)


def rule_met_for(rubric: dict, response: dict, item_id: str, G) -> bool | None:
    item = next((it for it in rubric["items"] if it["id"] == item_id), None)
    if item is None:
        return None
    text = json.dumps(response, ensure_ascii=False, indent=1).lower()
    return G.rule_met(item, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rubric", type=Path)
    ap.add_argument("worksheets", type=Path, nargs="+")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "graders" / "oncoworld_grader"))
    import grader_v2 as G  # noqa: E402

    rubric = tomllib.loads(args.rubric.read_text())

    pairs: list[tuple[bool, bool]] = []
    safety_disagreements = []
    per_item: dict[str, list[tuple[bool, bool]]] = {}

    for ws_path in args.worksheets:
        ws = json.loads(ws_path.read_text())
        unlabeled = [it["id"] for it in ws["items"] if it.get("label") is None]
        if unlabeled:
            print(f"REFUSING to score {ws_path}: unlabeled items {unlabeled}", file=sys.stderr)
            sys.exit(1)
        for it in ws["items"]:
            regex_met = rule_met_for(rubric, ws["response"], it["id"], G)
            if regex_met is None:
                continue  # item has no regex rule at all (judge-only); nothing to compare here
            oncologist = bool(it["label"])
            pairs.append((bool(regex_met), oncologist))
            per_item.setdefault(it["id"], []).append((bool(regex_met), oncologist))
            if regex_met != oncologist and it["severity"] == "dangerous":
                safety_disagreements.append({
                    "worksheet": str(ws_path), "item": it["id"],
                    "regex": bool(regex_met), "oncologist": oncologist,
                })

    if not pairs:
        print("No labeled, regex-rule-backed items found across the given worksheets.", file=sys.stderr)
        return

    agree = sum(1 for r, o in pairs if r == o)
    fp = sum(1 for r, o in pairs if r and not o)  # regex says met, oncologist says not - regex over-credits
    fn = sum(1 for r, o in pairs if not r and o)  # regex says not met, oncologist says met - regex under-credits
    kappa = cohens_kappa(pairs)

    print(f"{len(pairs)} item-judgments across {len(args.worksheets)} worksheet(s)")
    print(f"raw agreement: {agree}/{len(pairs)} ({agree/len(pairs):.1%})")
    print(f"Cohen's kappa: {kappa:.4f}" if kappa is not None else "Cohen's kappa: undefined (no variance)")
    print(f"false positives (regex met, oncologist not): {fp}")
    print(f"false negatives (regex not met, oncologist met): {fn}")

    print()
    print("per-item (sorted by disagreement count):")
    rows = sorted(per_item.items(), key=lambda kv: -sum(1 for r, o in kv[1] if r != o))
    width = max(len(iid) for iid in per_item)
    for iid, ps in rows:
        dis = sum(1 for r, o in ps if r != o)
        k = cohens_kappa(ps)
        kstr = f"{k:.2f}" if k is not None else "n/a"
        print(f"  {iid:<{width}}  n={len(ps):>3}  disagree={dis:>2}  kappa={kstr}")

    print()
    if safety_disagreements:
        print(f"SAFETY-ITEM DISAGREEMENTS ({len(safety_disagreements)}) - report these separately, each matters "
              f"more than any number of minor disagreements:")
        for d in safety_disagreements:
            print(f"  {d['item']}: regex={d['regex']} oncologist={d['oncologist']}  ({d['worksheet']})")
    else:
        print("No safety-item (severity=dangerous) disagreements in this batch.")


if __name__ == "__main__":
    main()
