"""Tests for minutes played and rotation measures."""
import numpy as np
import pandas as pd

from fti.rotation import gini, match_minutes

COLS = ["index", "type", "team", "period", "minute", "second", "player", "tactics",
        "substitution_replacement", "foul_committed_card"]


def _xi(team, names):
    return (0, "Starting XI", team, 1, 0, 0, None, {"formation": 442, "lineup": [{"player": {"name": n}} for n in names]},
            None, None)


def _events():
    a = [f"A{i}" for i in range(11)]
    b = [f"B{i}" for i in range(11)]
    rows = [_xi("A", a), _xi("B", b),
            (10, "Substitution", "A", 2, 60, 0, "A1", None, "A12", None),        # A1 off at 60, A12 on
            (20, "Foul Committed", "B", 2, 70, 30, "B2", None, None, "Red Card"),  # B2 sent off 70:30
            (30, "Pass", "A", 2, 93, 0, "A3", None, None, None)]                  # last event: end = 93
    return pd.DataFrame(rows, columns=COLS)


def test_minutes_for_starter_sub_red_card_and_full_match():
    m = match_minutes(_events(), match_id=1).set_index(["team", "player"])["minutes"]
    assert m[("A", "A0")] == 93          # played the whole match
    assert m[("A", "A1")] == 60          # substituted at 60'
    assert m[("A", "A12")] == 33         # came on at 60', end at 93'
    assert m[("B", "B2")] == 70.5        # sent off at 70:30


def test_started_flag():
    s = match_minutes(_events(), match_id=1).set_index(["team", "player"])["started"]
    assert bool(s[("A", "A0")]) and not bool(s[("A", "A12")])


def test_gini_known_values():
    assert gini([5, 5, 5, 5]) == 0
    assert np.isclose(gini([0, 0, 0, 1]), 0.75)
