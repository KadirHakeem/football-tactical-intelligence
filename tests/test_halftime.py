"""Tests for the half-time change analysis."""
import pandas as pd

from fti.halftime import halftime_table, is_half_time, permutation_test_share_diff, wilson_ci


def test_half_time_means_second_period_at_exactly_45_00():
    first = pd.DataFrame({"period": [2, 2, 1, 2], "clock": [45.0, 45.5, 45.0, 62.0]})
    assert is_half_time(first).tolist() == [True, False, False, False]


def test_wilson_interval_known_value_and_edges():
    low, high = wilson_ci(5, 10)
    assert round(low, 3) == 0.237 and round(high, 3) == 0.763
    low0, high0 = wilson_ci(0, 10)
    assert low0 == 0.0 and 0 < high0 < 0.35   # never negative; still a sensible upper bound at 0/10


def test_share_permutation_detects_clear_gap_and_not_identical_groups():
    assert permutation_test_share_diff([1] * 9 + [0], [1] * 2 + [0] * 38) < 0.01
    assert permutation_test_share_diff([1, 0, 1, 0], [1, 0, 1, 0]) > 0.5


def test_halftime_table_counts_and_minimum_sample():
    rows = [("A", "drawing", 2, 45.0)] * 6 + [("A", "drawing", 2, 70.0)] * 4          # 6 of 10 at HT
    rows += [("B", "drawing", 2, 45.0)] * 2 + [("B", "drawing", 2, 65.0)] * 28        # 2 of 30
    rows += [("C", "drawing", 2, 45.0)] * 3                                            # n=3: not tested
    first = pd.DataFrame(rows, columns=["team", "score_state", "period", "clock"])
    t = halftime_table(first, min_n=8).set_index(["team", "score_state"])
    assert t.loc[("A", "drawing"), "ht_team"] == 6 and t.loc[("A", "drawing"), "share_team"] == 0.6
    assert bool(t.loc[("C", "drawing"), "tested"]) is False
