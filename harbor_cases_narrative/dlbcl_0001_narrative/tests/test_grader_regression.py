#!/usr/bin/env python3
from __future__ import annotations

from grader import score


def criterion(result: dict, domain: str, name: str) -> bool:
    return result["metrics"][domain]["criteria"][name]["matched"]


def test_double_hit_excluded_is_not_penalized() -> None:
    result = score(
        "DLBCL double-expressor lymphoma. Double-hit lymphoma excluded because FISH "
        "rearrangements are negative."
    )

    assert result["critical_errors"] == []
    assert criterion(result, "molecular_classification", "identifies_not_double_hit")


def test_positive_double_hit_assertion_is_penalized() -> None:
    result = score("This patient is double-hit lymphoma despite negative FISH.")

    assert result["critical_errors"] == [
        {
            "name": "double_expressor_called_double_hit_despite_negative_FISH",
            "penalty_points": -20,
        }
    ]


def test_valid_first_line_regimen_gets_treatment_intent_credit() -> None:
    result = score("Recommend first-line systemic pola-R-CHP for 6 cycles. R-CHOP is acceptable.")

    assert criterion(result, "first_line_treatment", "curative_immunochemotherapy")
    assert criterion(result, "first_line_treatment", "recognizes_pola_R_CHP")
    assert criterion(result, "first_line_treatment", "accepts_R_CHOP_alternative")


def test_cns_prophylaxis_equivalent_wording_gets_credit() -> None:
    result = score(
        "Use CNS-IPI and review kidney, adrenal, testicular, breast, and other high-risk "
        "sites. Double-expressor status does not mandate CNS prophylaxis."
    )

    assert criterion(result, "CNS_management", "no_automatic_prophylaxis_for_DEL")


def test_stage_iv_assertion_blocks_stage_iii_credit() -> None:
    result = score("Lugano stage III is possible, but final stage is stage IV.")

    assert not criterion(result, "staging", "correct_Lugano_stage_III")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
