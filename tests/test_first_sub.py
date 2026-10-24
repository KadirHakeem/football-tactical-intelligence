"""Tests for first-tactical-substitution selection and the bootstrap CI."""
import pandas as pd

from fti.first_sub import bootstrap_median_ci, first_tactical_subs


def test_first_tactical_sub_skips_injury_changes():
    subs = pd.DataFrame([
        # match, team, event_index, minute, second, outcome, score_state, score_diff
        (1, "A", 10, 30, 0, "Injury", "drawing", 0),
        (1, "A", 20, 60, 30, "Tactical", "losing", -1),
        (1, "A", 30, 70, 0, "Tactical", "losing", -1),
        (1, "B", 15, 55, 0, "Tactical", "winning", 1),
    ], columns=["match_id", "team", "event_index", "minute", "second", "outcome",
                "score_state", "score_diff"])
    first = first_tactical_subs(subs).set_index("team")

    assert first.loc["A", "clock"] == 60.5            # the 60:30 change, not the injury at 30:00
    assert first.loc["A", "score_state"] == "losing"
    assert bool(first.loc["A", "injury_before"]) is True
    assert first.loc["B", "clock"] == 55.0
    assert bool(first.loc["B", "injury_before"]) is False


def test_bootstrap_ci_contains_median_and_is_reproducible():
    values = [50, 55, 58, 60, 62, 65, 70, 75, 80]
    median, low, high = bootstrap_median_ci(values)
    assert median == 62
    assert low <= median <= high
    assert bootstrap_median_ci(values) == (median, low, high)  # same seed -> same answer


def test_bootstrap_ci_of_constant_values_has_zero_width():
    assert bootstrap_median_ci([60, 60, 60]) == (60.0, 60.0, 60.0)
