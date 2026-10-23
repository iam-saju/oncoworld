#!/usr/bin/env python3
"""Unit tests for hybrid-mode's tie-break: regex is the grader of record, the judge's verdict is recorded but
never overrides - including on dangerous/must_not items, which is the behavior this changed (2026-10-24).
Run directly: python3 test_hybrid_tiebreak.py
"""
from __future__ import annotations

import os

import grader_v2 as G


def _rubric(items: list[dict]) -> dict:
    return {"version": "test", "items": items}


def _item(id_: str, *, kind="should", severity="important", points=8, pattern=None) -> dict:
    it = {"id": id_, "domain": "test", "kind": kind, "severity": severity, "points": points, "text": id_}
    if pattern is not None:
        it["any"] = [pattern]
    return it


def _with_mode(mode, fn):
    old = os.environ.get("ONCOWORLD_GRADER")
    os.environ["ONCOWORLD_GRADER"] = mode
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop("ONCOWORLD_GRADER", None)
        else:
            os.environ["ONCOWORLD_GRADER"] = old


def _detail(result: dict, item_id: str) -> dict:
    return next(i for i in result["items"] if i["id"] == item_id)


def test_hybrid_regex_wins_when_judge_disagrees_regex_true() -> None:
    rubric = _rubric([_item("a", pattern="alpha")])
    verdicts = {"a": {"met": False, "evidence": ""}}

    def run():
        return G.score("the answer says alpha", rubric, verdicts)

    result = _with_mode("hybrid", run)
    d = _detail(result, "a")
    assert d["met"] is True, d  # regex said met=True; judge said False - regex wins
    assert d["judge_met"] is False, d
    assert d["source"] == "hybrid_flagged", d
    assert {"id": "a", "judge": False, "regex": True} in result["judge_regex_disagreements"]


def test_hybrid_regex_wins_when_judge_disagrees_regex_false() -> None:
    rubric = _rubric([_item("a", pattern="zzz_no_match_zzz")])
    verdicts = {"a": {"met": True, "evidence": "alpha"}}

    def run():
        return G.score("the answer says alpha, which the judge (wrongly) credits", rubric, verdicts)

    result = _with_mode("hybrid", run)
    d = _detail(result, "a")
    assert d["met"] is False, d  # regex said met=False; judge said True - regex still wins
    assert d["judge_met"] is True, d
    assert d["source"] == "hybrid_flagged", d


def test_hybrid_agreement_no_disagreement_recorded() -> None:
    rubric = _rubric([_item("a", pattern="alpha")])
    verdicts = {"a": {"met": True, "evidence": "alpha"}}

    def run():
        return G.score("the answer says alpha", rubric, verdicts)

    result = _with_mode("hybrid", run)
    d = _detail(result, "a")
    assert d["met"] is True, d
    assert d["source"] == "hybrid_agree", d
    assert result["judge_regex_disagreements"] == []


def test_hybrid_dangerous_must_not_regex_still_wins() -> None:
    # this is the behavior that changed: before 2026-10-24, a dangerous/must_not disagreement let the stricter
    # (worse-for-the-model) verdict win, which meant the judge could still move the score here. Now regex alone
    # decides, same as any other severity.
    rubric = _rubric([_item("ok", pattern="fine", points=5),
                       _item("a", kind="must_not", severity="dangerous", points=10, pattern="zzz_no_match_zzz")])
    verdicts = {"a": {"met": True, "evidence": "danger"}}  # judge wrongly claims the error was committed

    def run():
        return G.score("the answer is actually fine and says danger only as part of a safe discussion", rubric, verdicts)

    result = _with_mode("hybrid", run)
    d = _detail(result, "a")
    assert d["met"] is False, d  # regex (no match) wins - not forced true by the judge's dangerous claim
    assert result["dangerous_errors"] == [], result["dangerous_errors"]
    assert result["reward"] != 0.0, result["reward"]


def test_hybrid_no_regex_rule_falls_back_to_judge() -> None:
    rubric = _rubric([{"id": "a", "domain": "test", "kind": "should", "severity": "important", "points": 8,
                        "text": "a"}])  # no any/all/affirm/recommend/check at all -> rule_met returns None
    verdicts = {"a": {"met": True, "evidence": "whatever"}}

    def run():
        return G.score("whatever", rubric, verdicts)

    result = _with_mode("hybrid", run)
    d = _detail(result, "a")
    assert d["met"] is True, d  # nothing for regex to decide - judge is the only signal available
    assert result["judge_regex_disagreements"] == []  # rx is None, so there's nothing to compare against


def test_pure_judge_mode_judge_is_authoritative() -> None:
    # unchanged behavior: ONCOWORLD_GRADER=judge (not hybrid) means the judge decides, regex is recorded only.
    rubric = _rubric([_item("a", pattern="zzz_no_match_zzz")])
    verdicts = {"a": {"met": True, "evidence": "alpha"}}

    def run():
        return G.score("the answer says alpha", rubric, verdicts)

    result = _with_mode("judge", run)
    d = _detail(result, "a")
    assert d["met"] is True, d  # judge wins outright in pure judge mode
    assert d["regex"] is False, d
    assert {"id": "a", "judge": True, "regex": False} in result["judge_regex_disagreements"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("ALL PASSED")
