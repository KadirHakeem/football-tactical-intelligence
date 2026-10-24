"""First tactical substitution timing by score state: one team vs the rest of the league.

Run from the project root (after python -m fti.substitutions):
    python -m fti.first_sub

Writes the aggregate summary to results/first_sub_timing_by_state.csv (aggregates only,
no raw StatsBomb data, so it can be committed).
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


def first_tactical_subs(subs: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match: that team's first Tactical substitution.

    `clock` is elapsed match time in decimal minutes (57:40 -> 57.67).
    `injury_before` is True if the team had already made an Injury change earlier.
    Team-matches with no Tactical substitution do not appear.
    """
    s = subs.sort_values(["match_id", "team", "event_index"]).copy()
    s["clock"] = s["minute"] + s["second"] / 60
    s["is_injury"] = s["outcome"] == "Injury"
    s["injuries_so_far"] = s.groupby(["match_id", "team"])["is_injury"].cumsum()

    tactical = s[s["outcome"] == "Tactical"]
    first = tactical.drop_duplicates(subset=["match_id", "team"], keep="first").copy()
    first["injury_before"] = first["injuries_so_far"] > 0
    cols = ["match_id", "match_date", "team", "opponent", "venue", "clock",
            "goals_for", "goals_against", "score_diff", "score_state", "injury_before"]
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


def main() -> None:
    path = PROCESSED_DIR / "substitutions.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found - run: python -m fti.substitutions")
    subs = pd.read_csv(path)

    first = first_tactical_subs(subs)
    arsenal = first[first["team"] == TEAM]
    print(f"Team-matches with a tactical sub: {len(first)} of {TEAM_MATCHES_IN_SEASON} "
          f"({TEAM}: {len(arsenal)} of 38)")
    print(f"First tactical sub preceded by an injury change: {int(first['injury_before'].sum())} "
          f"({TEAM}: {int(arsenal['injury_before'].sum())})")

    summary = summarise(first)
    print("\nFirst tactical substitution: median minute (95% bootstrap CI)")
    print(summary.to_string(index=False))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "first_sub_timing_by_state.csv"
    summary.to_csv(out, index=False)
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
