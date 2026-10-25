"""Tests for grouping substitutions into windows (simultaneous changes)."""
import pandas as pd

from fti.windows import assign_windows, eligible_subs, team_match_flags

COLS = ["match_id", "team", "period", "event_index", "minute", "second"]


def _subs(rows):
    return pd.DataFrame(rows, columns=COLS)


def test_changes_exactly_60s_apart_share_a_window_but_61s_do_not():
    w = assign_windows(_subs([(1, "A", 2, 10, 60, 0), (1, "A", 2, 11, 61, 0),     # 60 s apart
                              (1, "A", 2, 12, 75, 0), (1, "A", 2, 13, 76, 1)]))   # 61 s apart
    assert w["window_size"].tolist() == [2, 2, 1, 1]


def test_halves_and_teams_are_never_merged():
    w = assign_windows(_subs([(1, "A", 1, 10, 44, 50), (1, "A", 2, 11, 45, 0),    # different halves
                              (1, "B", 2, 12, 45, 10)]))                          # other team
    assert w["window_size"].tolist() == [1, 1, 1]


def test_triple_change_is_one_window():
    w = assign_windows(_subs([(1, "A", 2, 10, 70, 0), (1, "A", 2, 11, 70, 20), (1, "A", 2, 12, 70, 45)]))
    assert w["window_size"].tolist() == [3, 3, 3]


def test_eligible_subs_drops_injuries_and_post_red_card_changes():
    subs = pd.DataFrame({"outcome": ["Tactical", "Injury", "Tactical"],
                         "red_cards_for": [0, 0, 1], "red_cards_against": [0, 0, 0]})
    assert len(eligible_subs(subs)) == 1


def test_team_match_flags_cover_every_team_match():
    matches = pd.DataFrame({"match_id": [1], "home_team": ["A"], "away_team": ["B"]})
    w = assign_windows(_subs([(1, "A", 2, 10, 70, 0), (1, "A", 2, 11, 70, 30)]))
    flags = team_match_flags(w, matches).set_index("team")
    assert flags.loc["A", "multi"] == 1 and flags.loc["B", "multi"] == 0   # B made no eligible change
