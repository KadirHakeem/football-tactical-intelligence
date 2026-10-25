"""Tests for building minute-by-minute survival rows."""
import pandas as pd

from fti.survival import block_label, final_points, minute_rows

MATCHES = pd.DataFrame({"match_id": [1], "home_team": ["A"], "away_team": ["B"],
                        "home_score": [1], "away_score": [0]})
SUB_COLS = ["match_id", "team", "period", "minute", "second", "outcome", "event_index"]


def _timeline(extra=()):
    rows = [(1, "goal", "A", 2, 60.5), (1, "end", None, 2, 94.0), *extra]
    return pd.DataFrame(rows, columns=["match_id", "kind", "team", "period", "clock"])


def test_final_points():
    pts = final_points(pd.DataFrame({"home_team": ["A", "B"], "away_team": ["B", "A"],
                                     "home_score": [2, 1], "away_score": [0, 1]}))
    assert pts["A"] == 4 and pts["B"] == 1


def test_block_labels():
    assert block_label(45) == "45-49" and block_label(88) == "85-89" and block_label(93) == "90+"


def test_event_minute_and_score_state_update_after_goal():
    subs = pd.DataFrame([(1, "A", 2, 70, 15, "Tactical", 10)], columns=SUB_COLS)
    r = minute_rows(subs, _timeline(), MATCHES)
    a = r[r["team"] == "A"].set_index("minute")
    assert a.index.min() == 45 and a.index.max() == 70          # rows stop at the first change
    assert a.loc[70, "event"] == 1 and a["event"].sum() == 1
    assert a.loc[60, "winning"] == 0 and a.loc[61, "winning"] == 1   # goal at 60:30 counts from minute 61
    assert a.loc[45, "half_time"] == 1 and a.loc[46, "half_time"] == 0


def test_team_without_change_is_followed_to_the_end_and_never_has_an_event():
    subs = pd.DataFrame([(1, "A", 2, 70, 15, "Tactical", 10)], columns=SUB_COLS)
    b = minute_rows(subs, _timeline(), MATCHES).query("team == 'B'")
    assert b["event"].sum() == 0 and b["minute"].max() == 93   # match ends 94:00 -> minute 93 is the last full minute
    assert b.set_index("minute").loc[61, "losing"] == 1


def test_red_card_stops_rows_and_first_half_change_excludes_team():
    subs = pd.DataFrame([(1, "A", 1, 30, 0, "Tactical", 5)], columns=SUB_COLS)   # A changed in first half
    r = minute_rows(subs, _timeline([(1, "red", "B", 2, 75.5)]), MATCHES)
    assert (r["team"] == "A").sum() == 0                          # excluded
    assert r[r["team"] == "B"]["minute"].max() == 74              # stops before the red-card minute
