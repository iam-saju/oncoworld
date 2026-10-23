#!/usr/bin/env python3
"""Probe the regex rules with single sentences, the way a reviewer would test "would this wording fire?".

One sentence:
  python3 scripts/probe_rules.py cases_src/dlbcl_0002/rubric_v2.toml mn_calls_double_hit biology \
      "FISH shows no MYC, BCL2 or BCL6 rearrangement, so this is not double-hit."
A probe set (JSON list of {"item", "field", "text", "fire", "why"}; see cases_src/<case>/selftest/probes.json):
  python3 scripts/probe_rules.py cases_src/dlbcl_0002/rubric_v2.toml --probes cases_src/dlbcl_0002/selftest/probes.json

Each sentence is placed alone in the named answer field, serialised exactly as grader_v2 serialises a real answer,
and run through rule_met for that item. Exit code 1 if any probe disagrees with its "fire" label.
"""
import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
import grader_v2 as G  # noqa: E402


def fires(item: dict, field: str, text: str) -> bool | None:
    answer = json.dumps({field: text}, ensure_ascii=False)
    return G.rule_met(item, G.read_response_text(answer).lower())


def run_probes(rubric: dict, probes: list[dict], quiet: bool = False) -> list[dict]:
    items = {i["id"]: i for i in rubric["items"]}
    wrong = []
    for p in probes:
        it = items.get(p["item"])
        if it is None:
            wrong.append(dict(p, got="unknown item"))
            continue
        got = fires(it, p.get("field", "biology"), p["text"])
        if bool(got) != bool(p["fire"]) and not p.get("known_limitation"):
            wrong.append(dict(p, got=got))
    if not quiet:
        by_item = {}
        for p in probes:
            by_item.setdefault(p["item"], [0, 0])[0] += 1
        for w in wrong:
            by_item.setdefault(w["item"], [0, 0])[1] += 1
        for w in wrong:
            kind = "FALSE ALARM (fires, should not)" if w["got"] and not w["fire"] else "MISS (should fire, does not)"
            print(f"  {kind:32} {w['item']:34} [{w.get('field')}] {w['text'][:150]}")
        print(f"{len(probes) - len(wrong)}/{len(probes)} probes agree with their label "
              f"({sum(1 for w in wrong if w['got'] and not w['fire'])} false alarms, "
              f"{sum(1 for w in wrong if not w['got'] and w['fire'])} misses)")
    return wrong


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rubric", type=Path)
    ap.add_argument("item", nargs="?")
    ap.add_argument("field", nargs="?")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--probes", type=Path)
    args = ap.parse_args()
    rubric = tomllib.loads(args.rubric.read_text())
    if args.probes:
        sys.exit(1 if run_probes(rubric, json.loads(args.probes.read_text())) else 0)
    if not (args.item and args.field and args.text):
        ap.error("give item, field and text, or --probes")
    it = next((i for i in rubric["items"] if i["id"] == args.item), None)
    if it is None:
        sys.exit(f"no item {args.item}; items: {', '.join(i['id'] for i in rubric['items'])}")
    got = fires(it, args.field, args.text)
    print(f"{args.item}: {'FIRES (met)' if got else 'does not fire (not met)' if got is False else 'no rule'}")


if __name__ == "__main__":
    main()
