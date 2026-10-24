#!/usr/bin/env python3
"""Generate a blind labeling worksheet for a saved trial, for an oncologist to fill in.

Per the revised validation plan: held-out generalization is only meaningful if a human (blind to the regex
verdict) labels each item independently - "the grader produced a number on new text" is not the same claim as
"the grader was right." This script produces the worksheet; it deliberately does NOT run the grader or include
any met/unmet verdict, so the reviewer sees only the item's criterion text and the response, never the regex's
own answer.

Usage: python3 scripts/generate_blind_label_worksheet.py <rubric.toml> <final_answer.json> <output.json>
"""
from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rubric", type=Path)
    ap.add_argument("response", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--case", default=None, help="label for which case/step this is, for the worksheet header")
    args = ap.parse_args()

    rubric = tomllib.loads(args.rubric.read_text())
    response = json.loads(args.response.read_text())

    items = []
    for it in rubric["items"]:
        items.append({
            "id": it["id"],
            "kind": it["kind"],
            "severity": it["severity"],
            "text": it["text"],
            # what "label" means depends on kind, same as the grader's own convention: for must/should, true
            # means the criterion is satisfied; for must_not, true means the response commits the error.
            "label": None,
            "notes": "",
        })

    worksheet = {
        "case": args.case or str(args.rubric.parent.parent.parent if "steps" in str(args.rubric) else args.rubric),
        "rubric_path": str(args.rubric),
        "response_path": str(args.response),
        "instructions": (
            "For each item below, read the response and set \"label\" to true or false. For kind=must/should, "
            "true means the criterion is satisfied. For kind=must_not, true means the response commits the "
            "error described. Use \"notes\" for anything ambiguous or borderline - do not leave it blank if "
            "you're unsure. Do not consult the rubric_v2.toml file's own regex rules; judge from the item's "
            "text and your own clinical reading of the response only."
        ),
        "response": response,
        "items": items,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(worksheet, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(items)} items to {args.output}")


if __name__ == "__main__":
    main()
