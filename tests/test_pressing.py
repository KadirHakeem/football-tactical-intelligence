"""Tests for pressing height before vs while leading."""
import numpy as np
import pandas as pd

from fti.pressing import lead_phase_pressing

COLS = ["index", "type", "team", "period", "minute", "second", "location",
        "shot_outcome", "foul_committed_card", "player"]


def _press(start, n, team, x):
    return [(start + i, "Pressure", team, 1, 10, 0, [x, 40], None, None, "p") for i in range(n)]


def _goal(idx, team, minute=30):
    return [(idx, "Shot", team, 1, minute, 0, [110, 40], "Goal", None, "s")]


def test_change_is_leading_minus_before():
    rows = _press(1, 10, "A", 60) + _goal(50, "A") + _press(51, 10, "A", 50)
    ev = pd.DataFrame(rows, columns=COLS)
    out = lead_phase_pressing(ev, "A", "B", match_id=1)
    assert len(out) == 1 and out[0]["team"] == "A"
    assert out[0]["x_before"] == 60 and out[0]["x_leading"] == 50 and out[0]["change"] == -10


def test_leading_phase_ends_when_lead_is_lost():
    rows = (_press(1, 10, "A", 60) + _goal(50, "A") + _press(51, 10, "A", 50)
            + _goal(70, "B") + _press(71, 10, "A", 90))           # after equaliser: not 'leading'
    out = lead_phase_pressing(pd.DataFrame(rows, columns=COLS), "A", "B", match_id=1)
    assert out[0]["x_leading"] == 50 and out[0]["n_leading"] == 10


def test_too_few_pressures_in_a_phase_excludes_the_match():
    rows = _press(1, 9, "A", 60) + _goal(50, "A") + _press(51, 10, "A", 50)   # only 9 before
    assert lead_phase_pressing(pd.DataFrame(rows, columns=COLS), "A", "B", match_id=1) == []


def test_events_after_a_red_card_are_ignored():
    rows = (_press(1, 10, "A", 60) + _goal(50, "A") + _press(51, 10, "A", 50)
            + [(61, "Foul Committed", "B", 1, 40, 0, [50, 40], None, "Red Card", "b4")]
            + _press(62, 10, "A", 99))
    out = lead_phase_pressing(pd.DataFrame(rows, columns=COLS), "A", "B", match_id=1)
    assert out[0]["n_leading"] == 10 and out[0]["x_leading"] == 50
