"""Half-time change rate: how often is a team's first tactical substitution made at the interval?

Run from the project root (after python -m fti.substitutions):
    python -m fti.halftime

StatsBomb records half-time changes at the start of the second half (period 2, 45:00).
For every team and score state (variant D definition) we compare the team's half-time share
with the rest of the league's: Wilson 95% interval for the team's share, permutation p-value for
the difference, Benjamini-Hochberg correction across all tested team-states. Writes results/league/.

Caveat: a first-half injury replaced at the interval also appears as a half-time change.
"""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.first_sub import STATES, VARIANTS, apply_variant
from fti.league import FDR_Q, LEAGUE_DIR, MIN_N, benjamini_hochberg, bh_adjusted
from fti.substitutions import PROCESSED_DIR


def is_half_time(first: pd.DataFrame) -> pd.Series:
    """True where the change was made at the interval (second period, clock exactly 45:00)."""
    return (first["period"] == 2) & np.isclose(first["clock"], 45.0)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n (well-behaved for small n and shares near 0 or 1)."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half_width = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return max(0.0, centre - half_width), min(1.0, centre + half_width)  # clamp float round-off


def permutation_test_share_diff(a, b, n_perm: int = 10_000, seed: int = 42) -> float:
    """Two-sided permutation p-value for a difference in proportions (a, b are 0/1 arrays)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    observed = abs(a.mean() - b.mean())
    pooled = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(pooled)
        if abs(shuffled[:a.size].mean() - shuffled[a.size:].mean()) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def halftime_table(first: pd.DataFrame, min_n: int = MIN_N, q: float = FDR_Q) -> pd.DataFrame:
    """One row per team x score state: half-time share vs rest of league, with corrections."""
    first = first.assign(half_time=is_half_time(first).astype(int))
    rows = []
    for team in sorted(first["team"].unique()):
        is_team = first["team"] == team
        for state in STATES:
            in_state = first["score_state"] == state
            a = first.loc[is_team & in_state, "half_time"]
            b = first.loc[~is_team & in_state, "half_time"]
            low, high = wilson_ci(int(a.sum()), len(a))
            row = {"team": team, "score_state": state, "n_team": len(a), "ht_team": int(a.sum()),
                   "share_team": round(a.mean(), 3) if len(a) else np.nan,
                   "ci95_low": round(low, 3), "ci95_high": round(high, 3),
                   "share_league": round(b.mean(), 3) if len(b) else np.nan,
                   "tested": len(a) >= min_n}
            row["diff_pp"] = round(100 * (row["share_team"] - row["share_league"]), 1)
            row["permutation_p"] = permutation_test_share_diff(a, b) if row["tested"] else np.nan
            rows.append(row)
    table = pd.DataFrame(rows)
    table["bh_adjusted_p"] = bh_adjusted(table["permutation_p"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["permutation_p"], q)
    table["permutation_p"] = table["permutation_p"].round(4)
    return table


def halftime_title(table: pd.DataFrame) -> str:
    n_tests, n_sig = int(table["tested"].sum()), int(table["fdr_significant"].sum())
    if n_sig == 0:
        return f"No team's half-time change rate stands out after correcting for {n_tests} comparisons"
    return f"{n_sig} of {n_tests} team-situations stand out for half-time changes after correction"


def plot_halftime(table: pd.DataFrame, league_share: dict, path) -> None:
    teams = sorted(table["team"].unique())
    fig, axes = plt.subplots(1, len(STATES), figsize=(14, 8), sharey=True)
    for ax, state in zip(axes, STATES):
        rows = table[table["score_state"] == state].set_index("team").reindex(teams)
        ax.axvline(100 * league_share[state], color="#333333", linestyle="--", linewidth=1)
        for y, (team, r) in enumerate(rows.iterrows()):
            if not r["tested"]:
                ax.text(100 * league_share[state], y, f"n={int(r['n_team'])} (<{MIN_N})", ha="center",
                        va="center", fontsize=7, color="#999999", zorder=3,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
                continue
            colour = "#DB0007" if r["fdr_significant"] else "#555555"
            share = 100 * r["share_team"]
            ax.errorbar(share, y, xerr=[[share - 100 * r["ci95_low"]], [100 * r["ci95_high"] - share]],
                        fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
        ax.set_title(f"{state.capitalize()}  (league: {league_share[state]:.0%})", fontsize=11)
        ax.set_xlim(0, 100)
        ax.set_xlabel("First tactical changes made at half-time (%)")
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(range(len(teams)), teams)
    axes[0].invert_yaxis()
    fig.suptitle(halftime_title(table), x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16 (StatsBomb Open Data). Dot = team share with Wilson 95% interval; "
             f"dashed line = all teams. Red = significant after Benjamini-Hochberg (FDR {FDR_Q:.0%}). "
             f"Half-time changes may include first-half injuries.", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    name, *flags = VARIANTS[-1]
    first = apply_variant(subs, *flags)
    ht = is_half_time(first)
    league_share = {s: float(ht[first["score_state"] == s].mean()) for s in STATES}

    print(f"Definition: {name}")
    print(f"First tactical changes made at half-time, all teams: {ht.mean():.0%} "
          f"({int(ht.sum())} of {len(first)})")
    print("By score state:", {s: f"{v:.0%}" for s, v in league_share.items()})

    table = halftime_table(first)
    n_tests = int(table["tested"].sum())
    print(f"\nComparisons tested: {n_tests} of {len(table)} (min {MIN_N} matches)")
    cols = ["team", "score_state", "n_team", "ht_team", "share_team", "share_league", "diff_pp",
            "permutation_p", "bh_adjusted_p", "fdr_significant"]
    print("\nTen smallest p-values:")
    print(table[table["tested"]].sort_values("permutation_p")[cols].head(10).to_string(index=False))

    print("\nHighest half-time share per team, all score states pooled (descriptive, not tested):")
    pooled = (first.assign(half_time=ht).groupby("team")["half_time"].agg(["sum", "count", "mean"])
              .sort_values("mean", ascending=False).head(5))
    print(pooled.rename(columns={"sum": "half_time", "count": "first_subs", "mean": "share"})
          .round(3).to_string())

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "halftime_share_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "halftime_overview.png"
    plot_halftime(table, league_share, out_fig)
    print(f"\nHeadline: {halftime_title(table)}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
