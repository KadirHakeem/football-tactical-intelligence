"""Tests for first vs second half intensity."""
import numpy as np
import pandas as pd

from fti.halves import bootstrap_mean_diff_ci, half_stats_for_match, second_half_shares


def _events():
    return pd.DataFrame([
        # type, team, period, xg
        ("Shot", "A", 1, 0.1), ("Shot", "A", 2, 0.3), ("Shot", "A", 2, 0.1),
        ("Pressure", "A", 1, np.nan), ("Pressure", "A", 2, np.nan), ("Pressure", "B", 1, np.nan),
        ("Pass", "B", 2, np.nan), ("Shot", "A", 5, 0.9),             # period 5 (shoot-out) ignored
    ], columns=["type", "team", "period", "shot_statsbomb_xg"])


def test_half_stats_count_per_team_and_half_and_fill_zeros():
    h = half_stats_for_match(_events(), match_id=7).set_index(["team", "period"])
    assert np.isclose(h.loc[("A", 1), "xg"], 0.1) and np.isclose(h.loc[("A", 2), "xg"], 0.4)
    assert h.loc[("A", 2), "shots"] == 2 and h.loc[("A", 1), "pressures"] == 1
    assert h.loc[("B", 2), "shots"] == 0 and h.loc[("B", 2), "xg"] == 0   # team with no shots still present


def test_second_half_share_and_zero_total_is_missing():
    shares = second_half_shares(half_stats_for_match(_events(), match_id=7)).set_index("team")
    assert np.isclose(shares.loc["A", "xg_share_2h"], 0.8)   # 0.4 of 0.5
    assert np.isnan(shares.loc["B", "xg_share_2h"])          # B had no xG at all


def test_bootstrap_mean_diff_ci_sign_and_reproducibility():
    a, b = [0.7, 0.72, 0.68, 0.71, 0.69], [0.5, 0.52, 0.48, 0.51, 0.49]
    diff, low, high = bootstrap_mean_diff_ci(a, b)
    assert np.isclose(diff, 0.2) and 0 < low <= diff <= high
    assert bootstrap_mean_diff_ci(a, b) == (diff, low, high)
