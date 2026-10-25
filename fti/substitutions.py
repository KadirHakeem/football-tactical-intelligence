"""Substitutions with the match score at the moment each change was made.

Run from the project root:
    python -m fti.substitutions

Reads the cached events (see fti.ingest) and writes data/processed/substitutions.csv
(git-ignored: derived from StatsBomb data, which is not redistributed).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fti.ingest import CACHE_DIR, EVENTS_DIR, PROJECT_ROOT, load_events, load_matches

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

COLUMNS = [
    "match_id", "team", "opponent", "venue", "period", "minute", "second", "event_index",
    "player_off", "position_off", "player_on", "outcome",
    "goals_for", "goals_against", "score_diff", "score_state",
    "red_cards_for", "red_cards_against",
]

RED_CARD_TYPES = {"Red Card", "Second Yellow"}


def extract_goals(events: pd.DataFrame) -> pd.DataFrame:
    """One row per goal, in event order, with the team credited with the goal.

    Normal goals: Shot events with shot_outcome == "Goal".
    Own goals: "Own Goal For" events, recorded for the team that benefits.
    """
    shot_outcome = events["shot_outcome"] if "shot_outcome" in events.columns else pd.Series(None, index=events.index)
    is_goal = ((events["type"] == "Shot") & (shot_outcome == "Goal")) | (events["type"] == "Own Goal For")
    goals = events.loc[is_goal, ["index", "period", "minute", "second", "team", "type"]]
    return goals.sort_values("index").reset_index(drop=True)


def extract_red_cards(events: pd.DataFrame) -> pd.DataFrame:
    """One row per sending-off (straight red or second yellow), in event order.

    StatsBomb records cards on Foul Committed events (foul_committed_card) or on
    Bad Behaviour events (bad_behaviour_card); `team` is the team that lost the player.
    """
    is_red = pd.Series(False, index=events.index)
    for col in ("foul_committed_card", "bad_behaviour_card"):
        if col in events.columns:
            is_red |= events[col].isin(RED_CARD_TYPES)
    reds = events.loc[is_red, ["index", "period", "minute", "second", "team", "player"]]
    return reds.sort_values("index").reset_index(drop=True)


def score_state(score_diff: int) -> str:
    """Label a goal difference from the substituting team's point of view."""
    if score_diff > 0:
        return "winning"
    if score_diff < 0:
        return "losing"
    return "drawing"


def substitutions_with_score(events: pd.DataFrame, home_team: str, away_team: str,
                             match_id: int) -> pd.DataFrame:
    """Every substitution in one match, with the score just before it was made."""
    goals = extract_goals(events)
    reds = extract_red_cards(events)
    subs = events[events["type"] == "Substitution"].sort_values("index")

    rows = []
    for _, sub in subs.iterrows():
        team = sub["team"]
        if team not in (home_team, away_team):
            raise ValueError(f"match {match_id}: unexpected team {team!r}")
        opponent = away_team if team == home_team else home_team
        before = goals[goals["index"] < sub["index"]]  # strictly earlier events only
        goals_for = int((before["team"] == team).sum())
        goals_against = int((before["team"] == opponent).sum())
        reds_before = reds[reds["index"] < sub["index"]]
        rows.append({
            "match_id": match_id,
            "team": team,
            "opponent": opponent,
            "venue": "home" if team == home_team else "away",
            "period": sub["period"],
            "minute": sub["minute"],
            "second": sub["second"],
            "event_index": sub["index"],
            "player_off": sub["player"],
            "position_off": sub["position"],
            "player_on": sub["substitution_replacement"],
            "outcome": sub["substitution_outcome"],
            "goals_for": goals_for,
            "goals_against": goals_against,
            "score_diff": goals_for - goals_against,
            "score_state": score_state(goals_for - goals_against),
            "red_cards_for": int((reds_before["team"] == team).sum()),       # own players sent off
            "red_cards_against": int((reds_before["team"] == opponent).sum()),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def build_substitutions_table() -> tuple[pd.DataFrame, list[str]]:
    """Substitutions for every cached match, plus a list of goal-count mismatches."""
    matches = load_matches().sort_values(["match_date", "match_id"])
    tables, mismatches = [], []
    for m in matches.itertuples():
        events = load_events(int(m.match_id))

        # Data-quality check: our goal logic must reproduce the official final score.
        goals = extract_goals(events)
        found = (int((goals["team"] == m.home_team).sum()), int((goals["team"] == m.away_team).sum()))
        if found != (m.home_score, m.away_score):
            mismatches.append(f"{m.match_id} {m.home_team} v {m.away_team}: "
                              f"official {m.home_score}-{m.away_score}, found {found[0]}-{found[1]}")

        subs = substitutions_with_score(events, m.home_team, m.away_team, int(m.match_id))
        subs.insert(1, "match_date", m.match_date)
        tables.append(subs)

    table = pd.concat(tables, ignore_index=True)
    table["sub_number"] = table.groupby(["match_id", "team"]).cumcount() + 1  # 1st, 2nd, 3rd change
    return table, mismatches


def table_is_current(out: Path | None = None, sources: list[Path] | None = None,
                     columns: list[str] | None = None) -> bool:
    """True if substitutions.csv exists, has the current columns, and is newer than its inputs.

    Inputs = this module's code + the cached match data. If any of them changed after the table
    was written, the table is stale and must be rebuilt.
    """
    out = out or PROCESSED_DIR / "substitutions.csv"
    if not out.exists():
        return False
    with open(out, encoding="utf-8") as f:
        if not set(columns or COLUMNS) <= set(f.readline().strip().split(",")):
            return False
    if sources is None:
        sources = [Path(__file__), CACHE_DIR / "matches.pkl", *EVENTS_DIR.glob("*.pkl")]
    newest_input = max((p.stat().st_mtime for p in sources if p.exists()), default=0.0)
    return out.stat().st_mtime >= newest_input


def main() -> None:
    table, mismatches = build_substitutions_table()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "substitutions.csv"
    table.to_csv(out, index=False)

    print(f"Substitutions: {len(table)} across {table['match_id'].nunique()} matches -> {out}")
    print(f"Goal-count check vs official scores: {len(mismatches)} mismatches")
    for line in mismatches:
        print("  ", line)
    after_red = ((table["red_cards_for"] + table["red_cards_against"]) > 0).sum()
    print(f"Substitutions made after a red card in the match: {after_red}")
    print("\nOutcome counts (all teams):")
    print(table["outcome"].value_counts(dropna=False).to_string())

    arsenal = table[table["team"] == "Arsenal"]
    print(f"\nArsenal: {len(arsenal)} substitutions in {arsenal['match_id'].nunique()} matches")
    print("Arsenal first substitutions by score state:")
    print(arsenal[arsenal["sub_number"] == 1]["score_state"].value_counts().to_string())


if __name__ == "__main__":
    main()
