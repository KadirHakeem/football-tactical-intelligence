"""Tests for the league-wide comparison: Benjamini-Hochberg and the minimum-sample rule."""
import numpy as np
import pandas as pd

from fti.league import benjamini_hochberg, bh_adjusted, league_table, overview_title


def test_bh_rejects_all_when_every_p_is_under_its_threshold():
    # thresholds for m=4, q=0.05: 0.0125, 0.025, 0.0375, 0.05
    assert benjamini_hochberg([0.01, 0.04, 0.03, 0.005]).tolist() == [True, True, True, True]


def test_bh_keeps_a_large_p_value():
    assert benjamini_hochberg([0.01, 0.02, 0.03, 0.5]).tolist() == [True, True, True, False]


def test_bh_is_step_up():
    # 0.03 misses its own threshold (0.025), but 0.035 passes its threshold (0.0375),
    # so everything up to rank 3 is rejected - including 0.03.
    assert benjamini_hochberg([0.001, 0.03, 0.035, 0.6]).tolist() == [True, True, True, False]


def test_bh_ignores_untested_nan():
    assert benjamini_hochberg([0.001, np.nan]).tolist() == [True, False]


def test_bh_adjusted_values():
    assert np.allclose(bh_adjusted([0.01, 0.02, 0.03, 0.5]), [0.04, 0.04, 0.04, 0.5])


def test_teams_below_minimum_sample_are_not_tested():
    rng = np.random.default_rng(0)
    rows = [("A", "winning", 70.0)] * 3                                   # only 3 matches: skip
    rows += [("B", "winning", float(v)) for v in rng.normal(65, 8, 10)]   # 10 matches: test
    rows += [("C", "winning", float(v)) for v in rng.normal(65, 8, 30)]
    first = pd.DataFrame(rows, columns=["team", "score_state", "clock"])
    table = league_table(first, min_n=8).set_index(["team", "score_state"])

    assert bool(table.loc[("A", "winning"), "tested"]) is False
    assert np.isnan(table.loc[("A", "winning"), "permutation_p"])
    assert bool(table.loc[("B", "winning"), "tested"]) is True
    assert not table.loc[("A", "winning"), "fdr_significant"]


def test_overview_title_reports_no_standouts_honestly():
    table = pd.DataFrame({"tested": [True, True, False], "fdr_significant": [False, False, False]})
    assert overview_title(table).startswith("No team's first-substitution timing stands out")
