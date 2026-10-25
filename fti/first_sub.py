"""First tactical substitution timing by score state: one team vs the rest of the league.

Run from the project root (after python -m fti.substitutions):
    python -m fti.first_sub

Writes aggregate results to results/ (aggregates only, no raw StatsBomb data, so they
can be committed).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fti.ingest import PROJECT_ROOT
from fti.substitutions import PROCESSED_DIR

RESULTS_DIR = PROJECT_ROOT / "results"
TEAM = "Arsenal"
STATES = ["winning", "drawing", "losing"]
TEAM_MATCHES_IN_SEASON = 380 * 2

# Sensitivity variants: (name, first_half_tactical_as_injury, exclude_red_before, exclude_injury_before)
VARIANTS = [
    ("A: all first tactical subs", False, False, False),
    ("B: A + exclude red card before", False, True, False),
    ("C: B + 1st-half 'Tactical' = suspected injury", True, True, False),
    ("D: C + exclude earlier injury change", True, True, True),
]


def first_tactical_subs(subs: pd.DataFrame, first_half_tactical_as_injury: bool = False) -> pd.DataFrame:
    """One row per team-match: that team's first Tactical substitution.

    `clock` is elapsed match time in decimal minutes (57:40 -> 57.67).
    `injury_before` is True if the team had already made an injury change earlier.
    If `first_half_tactical_as_injury`, a first-half change labelled Tactical with no red card
    for that team before it is treated as a suspected (mislabelled) injury, not a tactical choice.
    Team-matches with no qualifying Tactical substitution do not appear.
    """
    s = subs.sort_values(["match_id", "team", "event_index"]).copy()
    s["clock"] = s["minute"] + s["second"] / 60
    s["is_injury"] = s["outcome"] == "Injury"
    if first_half_tactical_as_injury:
        suspected = (s["outcome"] == "Tactical") & (s["period"] == 1) & (s["red_cards_for"] == 0)
        s["is_injury"] = s["is_injury"] | suspected
    s["injuries_so_far"] = s.groupby(["match_id", "team"])["is_injury"].cumsum()

    tactical = s[(s["outcome"] == "Tactical") & ~s["is_injury"]]
    first = tactical.drop_duplicates(subset=["match_id", "team"], keep="first").copy()
    first["injury_before"] = first["injuries_so_far"] > 0
    cols = ["match_id", "match_date", "team", "opponent", "venue", "period", "clock",
            "goals_for", "goals_against", "score_diff", "score_state", "injury_before",
            "red_cards_for", "red_cards_against", "player_off", "position_off", "player_on"]
    return first[[c for c in cols if c in first.columns]].reset_index(drop=True)


def bootstrap_median_ci(values, n_boot: int = 10_000, ci: float = 0.95,
                        seed: int = 42) -> tuple[float, float, float]:
    """Median and a percentile-bootstrap confidence interval for it.

    Resamples the values with replacement n_boot times; the CI is the middle `ci`
    share of the resampled medians. Fixed seed -> identical results on every run.
    """
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    medians = np.median(rng.choice(v, size=(n_boot, v.size), replace=True), axis=1)
    low, high = np.quantile(medians, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(np.median(v)), float(low), float(high)


def bootstrap_median_diff_ci(a, b, n_boot: int = 10_000, ci: float = 0.95,
                             seed: int = 42) -> tuple[float, float, float]:
    """Difference in medians (a - b) and a percentile-bootstrap CI for that difference.

    Each bootstrap round resamples a and b independently (with replacement) and records
    median(a*) - median(b*). If the CI excludes 0, the data support a real difference.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    med_a = np.median(rng.choice(a, size=(n_boot, a.size), replace=True), axis=1)
    med_b = np.median(rng.choice(b, size=(n_boot, b.size), replace=True), axis=1)
    low, high = np.quantile(med_a - med_b, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(np.median(a) - np.median(b)), float(low), float(high)


def summarise(first: pd.DataFrame, team: str = TEAM) -> pd.DataFrame:
    """Median first-sub minute with 95% CI, by group (team vs rest of league) and score state."""
    group = np.where(first["team"] == team, team, "Rest of league")
    rows = []
    for g in [team, "Rest of league"]:
        for state in STATES:
            values = first.loc[(group == g) & (first["score_state"] == state), "clock"]
            median, low, high = bootstrap_median_ci(values)
            rows.append({"group": g, "score_state": state, "n": len(values),
                         "median_minute": round(median, 1),
                         "ci95_low": round(low, 1), "ci95_high": round(high, 1)})
    return pd.DataFrame(rows)


def compare_to_league(first: pd.DataFrame, team: str = TEAM) -> pd.DataFrame:
    """Team median minus rest-of-league median, per score state, with 95% bootstrap CI."""
    is_team = first["team"] == team
    rows = []
    for state in STATES:
        in_state = first["score_state"] == state
        team_vals = first.loc[is_team & in_state, "clock"]
        league_vals = first.loc[~is_team & in_state, "clock"]
        diff, low, high = bootstrap_median_diff_ci(team_vals, league_vals)
        rows.append({"score_state": state, "n_team": len(team_vals), "n_league": len(league_vals),
                     "diff_minutes": round(diff, 1), "ci95_low": round(low, 1),
                     "ci95_high": round(high, 1), "ci_excludes_zero": bool(low > 0 or high < 0)})
    return pd.DataFrame(rows)


def apply_variant(subs: pd.DataFrame, first_half_as_injury: bool, exclude_red: bool,
                  exclude_injury_before: bool) -> pd.DataFrame:
    """First tactical subs under one sensitivity definition."""
    first = first_tactical_subs(subs, first_half_tactical_as_injury=first_half_as_injury)
    if exclude_red:
        first = first[(first["red_cards_for"] + first["red_cards_against"]) == 0]
    if exclude_injury_before:
        first = first[~first["injury_before"]]
    return first


def sensitivity(subs: pd.DataFrame, team: str = TEAM) -> pd.DataFrame:
    """Team-vs-league comparison re-run under each definition in VARIANTS."""
    tables = []
    for name, fh, red, inj in VARIANTS:
        comparison = compare_to_league(apply_variant(subs, fh, red, inj), team)
        comparison.insert(0, "variant", name)
        tables.append(comparison)
    return pd.concat(tables, ignore_index=True)


def main() -> None:
    path = PROCESSED_DIR / "substitutions.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found - run: python -m fti.substitutions")
    subs = pd.read_csv(path)
    if "red_cards_for" not in subs.columns:
        raise SystemExit("substitutions.csv is out of date - re-run: python -m fti.substitutions")

    first = first_tactical_subs(subs)
    arsenal = first[first["team"] == TEAM]
    print(f"Team-matches with a tactical sub: {len(first)} of {TEAM_MATCHES_IN_SEASON} "
          f"({TEAM}: {len(arsenal)} of 38)")

    summary = summarise(first)
    print("\nVariant A - first tactical substitution: median minute (95% bootstrap CI)")
    print(summary.to_string(index=False))

    sens = sensitivity(subs)
    print(f"\nSensitivity: {TEAM} median minus rest-of-league median (minutes, 95% CI)")
    for state in STATES:
        print(f"\n  {state.upper()}")
        print(sens[sens["score_state"] == state].drop(columns="score_state").to_string(index=False))

    strict = apply_variant(subs, *VARIANTS[-1][1:])
    drawing = strict[(strict["team"] == TEAM) & (strict["score_state"] == "drawing")].sort_values("clock")
    print(f"\n{TEAM} first tactical subs while drawing under variant D ({len(drawing)}):")
    cols = ["match_date", "opponent", "period", "clock", "player_off", "position_off", "player_on"]
    print(drawing[cols].round({"clock": 1}).to_string(index=False))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(RESULTS_DIR / "first_sub_timing_by_state.csv", index=False)
    compare_to_league(first).to_csv(RESULTS_DIR / "first_sub_difference_by_state.csv", index=False)
    sens.to_csv(RESULTS_DIR / "first_sub_sensitivity.csv", index=False)
    print(f"\nSaved 3 result tables -> {RESULTS_DIR}")


if __name__ == "__main__":
    main()
