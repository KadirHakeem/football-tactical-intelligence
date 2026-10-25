"""Robustness checks for the first-substitution findings, using the strict variant D definition.

Run from the project root (after python -m fti.substitutions):
    python -m fti.robustness

1. Winning margin: is the team's later timing when ahead explained by how far ahead it was?
2. Permutation test: a second, label-shuffling opinion on each team-vs-league gap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fti.first_sub import RESULTS_DIR, STATES, TEAM, VARIANTS, apply_variant, bootstrap_median_diff_ci
from fti.substitutions import PROCESSED_DIR


def permutation_test_median_diff(a, b, n_perm: int = 10_000, seed: int = 42) -> float:
    """Two-sided permutation p-value for a difference in medians.

    Pools both groups, randomly reassigns the group labels n_perm times, and counts how often
    the shuffled median gap is at least as large as the observed one. (+1 correction so the
    p-value is never exactly 0.)
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    observed = abs(np.median(a) - np.median(b))
    pooled = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(pooled)
        if abs(np.median(shuffled[:a.size]) - np.median(shuffled[a.size:])) >= observed:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def margin_table(first: pd.DataFrame, team: str = TEAM) -> pd.DataFrame:
    """Within the winning state: team vs league, split by lead size (1 goal vs 2+ goals)."""
    winning = first[first["score_state"] == "winning"].copy()
    winning["margin"] = np.where(winning["score_diff"] >= 2, "2+ goals", "1 goal")
    rows = []
    for margin in ["1 goal", "2+ goals"]:
        m = winning[winning["margin"] == margin]
        is_team = m["team"] == team
        team_vals, league_vals = m.loc[is_team, "clock"], m.loc[~is_team, "clock"]
        diff, low, high = bootstrap_median_diff_ci(team_vals, league_vals)
        rows.append({"lead": margin, "n_team": len(team_vals), "n_league": len(league_vals),
                     "team_median": round(float(np.median(team_vals)), 1) if len(team_vals) else np.nan,
                     "league_median": round(float(np.median(league_vals)), 1) if len(league_vals) else np.nan,
                     "diff_minutes": round(diff, 1), "ci95_low": round(low, 1), "ci95_high": round(high, 1)})
    return pd.DataFrame(rows)


def permutation_table(first: pd.DataFrame, team: str = TEAM) -> pd.DataFrame:
    """Observed median gap and permutation p-value per score state."""
    is_team = first["team"] == team
    rows = []
    for state in STATES:
        in_state = first["score_state"] == state
        a, b = first.loc[is_team & in_state, "clock"], first.loc[~is_team & in_state, "clock"]
        diff = float(np.median(a) - np.median(b)) if len(a) and len(b) else np.nan
        rows.append({"score_state": state, "n_team": len(a), "n_league": len(b),
                     "diff_minutes": round(diff, 1),
                     "permutation_p": round(permutation_test_median_diff(a, b), 4)})
    return pd.DataFrame(rows)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    name, *flags = VARIANTS[-1]
    first = apply_variant(subs, *flags)
    print(f"Definition: {name}")

    winning = first[first["score_state"] == "winning"]
    is_team = winning["team"] == TEAM
    share_team = (winning.loc[is_team, "score_diff"] >= 2).mean()
    share_league = (winning.loc[~is_team, "score_diff"] >= 2).mean()
    print(f"\nWhen winning at the first tactical sub, share ahead by 2+ goals: "
          f"{TEAM} {share_team:.0%}  |  rest of league {share_league:.0%}")

    margins = margin_table(first)
    print(f"\nWinning state split by lead size ({TEAM} minus league, minutes, 95% bootstrap CI)")
    print(margins.to_string(index=False))

    perms = permutation_table(first)
    print(f"\nPermutation test, {TEAM} vs league (10,000 label shuffles)")
    print(perms.to_string(index=False))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    margins.to_csv(RESULTS_DIR / "robustness_winning_margin.csv", index=False)
    perms.to_csv(RESULTS_DIR / "robustness_permutation.csv", index=False)
    print(f"\nSaved 2 result tables -> {RESULTS_DIR}")


if __name__ == "__main__":
    main()
