"""Tests for the league-wide survival scan helpers."""
import pandas as pd

from fti.survival_league import matches_in_state, survival_league_title


def test_matches_in_state_counts_distinct_matches_per_state():
    rows = pd.DataFrame({
        "team":     ["A", "A", "A", "A", "B"],
        "match_id": [1,   1,   2,   3,   1],
        "winning":  [0,   1,   1,   0,   0],
        "losing":   [0,   0,   0,   1,   1],
    })
    c = matches_in_state(rows)
    assert c.loc["A", "winning"] == 2 and c.loc["A", "drawing"] == 1 and c.loc["A", "losing"] == 1
    assert c.loc["B", "losing"] == 1 and c.loc["B", "winning"] == 0


def test_title_is_honest_when_nothing_survives():
    t = pd.DataFrame({"tested": [True, True], "fdr_significant": [False, False]})
    assert survival_league_title(t).startswith("After controls, no team")
