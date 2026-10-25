"""Tests for first-tactical-substitution selection and the bootstrap CI."""
import pandas as pd

from fti.first_sub import bootstrap_median_ci, bootstrap_median_diff_ci, first_tactical_subs


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


def test_diff_ci_detects_a_clear_gap_and_its_sign():
    later = [70, 71, 72, 73, 74, 75, 76, 77]
    earlier = [55, 56, 57, 58, 59, 60, 61, 62]
    diff, low, high = bootstrap_median_diff_ci(later, earlier)
    assert diff == 15
    assert 0 < low <= diff <= high          # clearly positive: interval excludes zero


def test_diff_ci_of_identical_groups_includes_zero():
    values = [50, 55, 60, 65, 70, 75]
    diff, low, high = bootstrap_median_diff_ci(values, values)
    assert diff == 0
    assert low <= 0 <= high


def test_first_half_tactical_can_be_treated_as_suspected_injury():
    subs = pd.DataFrame([
        # match, team, event_index, period, minute, second, outcome, score_state, red_for, red_against
        (1, "A", 10, 1, 11, 0, "Tactical", "drawing", 0, 0),   # like Koscielny at 11': suspected injury
        (1, "A", 20, 2, 65, 0, "Tactical", "winning", 0, 0),
        (1, "B", 15, 1, 40, 0, "Tactical", "drawing", 1, 0),   # after own red card: kept as tactical
    ], columns=["match_id", "team", "event_index", "period", "minute", "second", "outcome",
                "score_state", "red_cards_for", "red_cards_against"])

    default = first_tactical_subs(subs).set_index("team")
    assert default.loc["A", "clock"] == 11.0

    strict = first_tactical_subs(subs, first_half_tactical_as_injury=True).set_index("team")
    assert strict.loc["A", "clock"] == 65.0
    assert bool(strict.loc["A", "injury_before"]) is True
    assert strict.loc["B", "clock"] == 40.0
