#!/usr/bin/env python3
"""Unit tests for the opt-in `scope = "sentence"` mechanism on `all` items (grader_v2.rule_met()).

Timeboxed experiment (docs/grader-known-issues.md #2): a prior attempt at sentence-scoped `all`/`any` changed
shared matching internals and broke affirms()'s own negation detection. This version is deliberately additive -
`item.get("scope") == "sentence"` is checked before the existing whole-document `all` path even runs, so an
item without `scope` set (every item except the ones that opt in) takes the exact same code path as before,
byte for byte. Adversarial negation cases are tested first, per the stop-rule plan, before applying this to
any real rubric item.

Synthetic rubric dicts only. Run directly: python3 test_sentence_scope.py
"""
from __future__ import annotations

import grader_v2 as G


def _rubric(items: list[dict]) -> dict:
    return {"version": "test", "items": items}


def _item(id_: str, *, kind="must", severity="important", points=6, **extra) -> dict:
    it = {"id": id_, "domain": "test", "kind": kind, "severity": severity, "points": points, "text": id_}
    it.update(extra)
    return it


def _met(result: dict, item_id: str) -> bool:
    return next(i["met"] for i in result["items"] if i["id"] == item_id)


# --- core mechanism ---

def test_sentence_scope_same_sentence_matches() -> None:
    rubric = _rubric([_item("a", all=["alpha", "bravo"], scope="sentence")])
    result = G.score("the plan mentions alpha and bravo together in one line.", rubric)
    assert _met(result, "a") is True


def test_sentence_scope_cross_sentence_does_not_match() -> None:
    """The exact contamination bug this mechanism exists to fix: two conditions, each true, but in different,
    unrelated sentences - must NOT count under scope="sentence" (it would count under plain whole-document all)."""
    rubric = _rubric([_item("a", all=["alpha", "bravo"], scope="sentence")])
    text = "The plan discusses alpha for one reason. A different, unrelated sentence later mentions bravo."
    result = G.score(text, rubric)
    assert _met(result, "a") is False


def test_plain_all_unaffected_by_new_code_path() -> None:
    """An item with no `scope` key must behave exactly as before - cross-sentence combination still counts."""
    rubric = _rubric([_item("a", all=["alpha", "bravo"])])
    text = "The plan discusses alpha for one reason. A different, unrelated sentence later mentions bravo."
    result = G.score(text, rubric)
    assert _met(result, "a") is True


# --- adversarial negation cases (per the review: test these before touching anything else) ---

def test_adversarial_negated_clause_in_same_sentence() -> None:
    """'repeat biopsy is not appropriate' - if an item's `all` conditions are generic enough to match inside a
    negated clause, sentence-scoping alone does not fix that (it only fixes CROSS-sentence contamination, not
    in-sentence negation) - this failure mode is intentionally still possible and must be documented, not
    silently assumed away."""
    rubric = _rubric([_item("a", all=["biops", "not (?:sufficient|appropriate|needed)"], scope="sentence")])
    text = "A repeat biopsy is not appropriate given the family's refusal."
    result = G.score(text, rubric)
    # documents the real limitation: both conditions co-occur in one sentence, so this still reads as "met"
    # even though the sentence is actually making the OPPOSITE point (biopsy is declined, not insufficient).
    assert _met(result, "a") is True, "known limitation: sentence-scoping fixes cross-sentence contamination, not in-sentence negation"


def test_adversarial_contrastive_not_x_but_y() -> None:
    """'not X, but Y' - a condition looking for X and a condition looking for Y both literally appear in one
    sentence, even though the sentence explicitly rejects X. Same limitation as above, documented not assumed."""
    rubric = _rubric([_item("a", all=["alpha", "bravo"], scope="sentence")])
    text = "This is not alpha, but bravo instead."
    result = G.score(text, rubric)
    assert _met(result, "a") is True, "known limitation: same-sentence negation of one condition is not detected"


def test_sentence_scope_any_untouched() -> None:
    """scope="sentence" only changes `all` handling; an `any` list on the same item is unaffected either way,
    since a single matching alternative is equally true whether or not sentence-scoping is considered."""
    rubric = _rubric([_item("a", any=["alpha"], all=["bravo", "charlie"], scope="sentence")])
    # "alpha" present satisfies `any` regardless of sentence; `all` needs bravo+charlie together, which they are.
    result = G.score("alpha is mentioned here. bravo and charlie appear together in this other sentence.", rubric)
    assert _met(result, "a") is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("ALL PASSED")
