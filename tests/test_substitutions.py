"""Tests for score-at-substitution logic. Run from the project root: python -m pytest"""
import pandas as pd
import pytest

from fti.ingest import EVENTS_DIR, load_events
from fti.substitutions import score_state, substitutions_with_score

EVENT_COLUMNS = ["index", "period", "minute", "second", "type", "team", "player", "position",
                 "substitution_replacement", "substitution_outcome", "shot_outcome"]


def make_events(rows):
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def test_score_state_labels():
    assert score_state(2) == "winning"
    assert score_state(0) == "drawing"
    assert score_state(-1) == "losing"


def test_only_goals_before_a_substitution_count():
    """Synthetic match: home team A v away team B. No real data needed."""
    events = make_events([
        (1, 1, 10, 0, "Shot", "A", "a9", None, None, None, "Goal"),        # A 1-0
        (2, 2, 59, 50, "Own Goal For", "B", None, None, None, None, None),  # own goal for B: 1-1
        (3, 2, 60, 5, "Substitution", "A", "a2", "Right Back", "a12", "Tactical", None),
        (4, 2, 61, 0, "Shot", "B", "b9", None, None, None, "Goal"),        # B lead 1-2 (after A's sub)
        (5, 2, 70, 0, "Substitution", "B", "b7", "Right Wing", "b14", "Injury", None),
        (6, 2, 75, 0, "Shot", "A", "a10", None, None, None, "Saved"),      # not a goal
    ])
    subs = substitutions_with_score(events, home_team="A", away_team="B", match_id=1)

    a_sub, b_sub = subs.iloc[0], subs.iloc[1]
    # A's sub came 15 seconds after the own goal: it must count; the 61' goal must not.
    assert (a_sub.goals_for, a_sub.goals_against, a_sub.score_state) == (1, 1, "drawing")
    assert a_sub.venue == "home"
    assert (b_sub.goals_for, b_sub.goals_against, b_sub.score_state) == (2, 1, "winning")
    assert (b_sub.venue, b_sub.outcome) == ("away", "Injury")


WEST_HAM_MATCH = 3754141  # Arsenal 0-2 West Ham, 2015-08-09, verified by hand in Phase 0


@pytest.mark.skipif(not (EVENTS_DIR / f"{WEST_HAM_MATCH}.pkl").exists(),
                    reason="match not cached; run python -m fti.ingest first")
def test_verified_arsenal_west_ham_match():
    events = load_events(WEST_HAM_MATCH)
    subs = substitutions_with_score(events, "Arsenal", "West Ham United", WEST_HAM_MATCH)

    arsenal = subs[subs["team"] == "Arsenal"]
    assert list(arsenal["player_on"]) == ["Theo Walcott", "Alexis Alejandro Sánchez Sánchez"]
    assert list(arsenal["score_state"]) == ["losing", "losing"]
    assert list(arsenal["goals_against"]) == [2, 2]  # Walcott came on 73 s after the 2nd goal

    west_ham_first = subs[subs["team"] == "West Ham United"].iloc[0]
    assert west_ham_first["player_on"] == "Matt Jarvis"
    assert west_ham_first["score_state"] == "winning"
