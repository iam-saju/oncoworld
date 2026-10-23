#!/usr/bin/env python3
"""Unit tests for the alt_group / applies_if scoring mechanisms (grader_v2.score()).

Synthetic rubric dicts only, deliberately separate from any case's real calibration answers - these test the
shared mechanism itself, not a specific rubric's wording. Run directly: python3 test_alt_group_scoring.py
"""
from __future__ import annotations

import grader_v2 as G


def _rubric(items: list[dict]) -> dict:
    return {"version": "test", "items": items}


def _item(id_: str, *, kind="should", severity="important", points=8, pattern=None, **extra) -> dict:
    it = {"id": id_, "domain": "test", "kind": kind, "severity": severity, "points": points, "text": id_}
    if pattern is not None:
        it["any"] = [pattern]
    it.update(extra)
    return it


def _met(result: dict, item_id: str) -> bool:
    return next(i["met"] for i in result["items"] if i["id"] == item_id)


# --- alt_group ---

def test_alt_group_one_member_met_equal_points() -> None:
    rubric = _rubric([
        _item("a", points=8, pattern="alpha", alt_group="g"),
        _item("b", points=8, pattern="bravo", alt_group="g"),
    ])
    result = G.score("the answer says alpha only", rubric)
    assert result["max_points"] == 8, result["max_points"]
    assert result["raw_points"] == 8, result["raw_points"]
    assert result["reward"] == 1.0, result["reward"]


def test_alt_group_both_met_equal_points_not_summed() -> None:
    rubric = _rubric([
        _item("a", points=8, pattern="alpha", alt_group="g"),
        _item("b", points=8, pattern="bravo", alt_group="g"),
    ])
    result = G.score("the answer says alpha and also bravo", rubric)
    assert result["max_points"] == 8, result["max_points"]
    assert result["raw_points"] == 8, result["raw_points"]  # max(8, 8), not 8 + 8
    assert result["reward"] == 1.0, result["reward"]
    # the domain breakdown must show the same uncapped ratio, not the old structurally-capped one
    assert result["domains"]["test"]["max_points"] == 8, result["domains"]["test"]
    assert result["domains"]["test"]["score"] == 1.0, result["domains"]["test"]


def test_alt_group_neither_met_total_still_counted_once() -> None:
    rubric = _rubric([
        _item("a", points=8, pattern="alpha", alt_group="g"),
        _item("b", points=8, pattern="bravo", alt_group="g"),
    ])
    result = G.score("the answer says neither of the group's trigger words", rubric)
    assert result["max_points"] == 8, result["max_points"]
    assert result["raw_points"] == 0, result["raw_points"]
    assert result["reward"] == 0.0, result["reward"]


def test_alt_group_disallowed_on_must_not() -> None:
    rubric = _rubric([_item("a", kind="must_not", severity="important", points=6, pattern="x", alt_group="g")])
    try:
        G.score("x", rubric)
    except ValueError as e:
        assert "alt_group" in str(e)
    else:
        raise AssertionError("expected ValueError for alt_group on a must_not item")


def test_alt_group_disallowed_on_dangerous() -> None:
    rubric = _rubric([_item("a", kind="must", severity="dangerous", points=10, pattern="x", alt_group="g")])
    try:
        G.score("x", rubric)
    except ValueError as e:
        assert "alt_group" in str(e)
    else:
        raise AssertionError("expected ValueError for alt_group on a dangerous item")


def test_alt_group_unequal_points_cheaper_path_capped() -> None:
    # a and b are a genuine, intentional preference (a is "better"), not equal alternatives - the plan's own
    # worked example (chemo_escalation_irinotecan/defer_reasoned) is the equal-weight case; this is the contrast.
    rubric = _rubric([
        _item("a", points=8, pattern="alpha", alt_group="g"),
        _item("b", points=4, pattern="bravo", alt_group="g"),
    ])
    cheaper_only = G.score("the answer says bravo only", rubric)
    assert cheaper_only["max_points"] == 8, cheaper_only["max_points"]
    assert cheaper_only["raw_points"] == 4, cheaper_only["raw_points"]
    assert cheaper_only["reward"] == 0.5, cheaper_only["reward"]  # capped below 100% - intentional, not a bug

    better_only = G.score("the answer says alpha only", rubric)
    assert better_only["raw_points"] == 8, better_only["raw_points"]
    assert better_only["reward"] == 1.0, better_only["reward"]


# --- applies_if ---

def test_applies_if_condition_met_and_this_item_met() -> None:
    rubric = _rubric([
        _item("cond", points=8, pattern="alpha"),
        _item("dep", points=3, pattern="monitor", applies_if="cond"),
    ])
    result = G.score("the answer says alpha and will monitor closely", rubric)
    assert result["max_points"] == 11, result["max_points"]  # 8 + 3, dep counts normally
    assert result["raw_points"] == 11, result["raw_points"]
    assert _met(result, "dep")


def test_applies_if_condition_met_and_this_item_missed() -> None:
    rubric = _rubric([
        _item("cond", points=8, pattern="alpha"),
        _item("dep", points=3, pattern="monitor", applies_if="cond"),
    ])
    result = G.score("the answer says alpha only, nothing else", rubric)
    assert result["max_points"] == 11, result["max_points"]  # dep still counts in the denominator
    assert result["raw_points"] == 8, result["raw_points"]  # but not in earned - a normal miss
    assert not _met(result, "dep")


def test_applies_if_condition_not_met_item_excluded_from_both() -> None:
    rubric = _rubric([
        _item("cond", points=8, pattern="alpha"),
        _item("dep", points=3, pattern="monitor", applies_if="cond"),
    ])
    result = G.score("the answer says something else entirely", rubric)
    assert result["max_points"] == 8, result["max_points"]  # dep excluded entirely, not just unmet
    assert result["raw_points"] == 0, result["raw_points"]
    assert result["reward"] == 0.0, result["reward"]
    assert result["domains"]["test"]["max_points"] == 8, result["domains"]["test"]


def test_applies_if_disallowed_on_must_not() -> None:
    rubric = _rubric([
        _item("cond", points=8, pattern="alpha"),
        _item("dep", kind="must_not", severity="important", points=3, pattern="x", applies_if="cond"),
    ])
    try:
        G.score("x", rubric)
    except ValueError as e:
        assert "applies_if" in str(e)
    else:
        raise AssertionError("expected ValueError for applies_if on a must_not item")


def test_applies_if_unknown_reference_rejected() -> None:
    rubric = _rubric([_item("dep", points=3, pattern="x", applies_if="does_not_exist")])
    try:
        G.score("x", rubric)
    except ValueError as e:
        assert "does_not_exist" in str(e)
    else:
        raise AssertionError("expected ValueError for an applies_if reference to a nonexistent item")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("ALL PASSED")
