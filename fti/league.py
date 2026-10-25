"""League-wide comparison: every team vs the rest of the league, by score state, with FDR correction.

Run from the project root (after python -m fti.substitutions):
    python -m fti.league

For each of the 20 teams and each score state (variant D definition), compares the team's first
tactical substitution minutes with all other teams': median gap, 95% bootstrap CI, permutation p.
Because this asks up to 60 questions at once, p-values are corrected with Benjamini-Hochberg
(false discovery rate). Writes results/league/.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.first_sub import STATES, VARIANTS, apply_variant, bootstrap_median_diff_ci
from fti.robustness import permutation_test_median_diff
from fti.substitutions import PROCESSED_DIR
from fti.teams import RESULTS_ROOT

MIN_N = 8      # pre-specified on 2026-10-25, before seeing any league-wide results
FDR_Q = 0.05   # false discovery rate
LEAGUE_DIR = RESULTS_ROOT / "league"


def benjamini_hochberg(pvalues, q: float = FDR_Q) -> np.ndarray:
    """Which hypotheses to reject while controlling the false discovery rate at q.

    Step-up procedure: sort the m p-values ascending, find the largest rank k with
    p_(k) <= (k / m) * q, and reject the k smallest. NaN = not tested (ignored, never rejected).
    """
    p = np.asarray(pvalues, dtype=float)
    reject = np.zeros(p.size, dtype=bool)
    tested = np.flatnonzero(~np.isnan(p))
    m = tested.size
    if m == 0:
        return reject
    order = np.argsort(p[tested])
    below = p[tested][order] <= q * np.arange(1, m + 1) / m
    if below.any():
        k = np.max(np.nonzero(below)[0])           # largest rank that passes (0-based)
        reject[tested[order[: k + 1]]] = True      # reject it and every smaller p-value
    return reject


def bh_adjusted(pvalues) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values: reject where adjusted p <= q. NaN stays NaN."""
    p = np.asarray(pvalues, dtype=float)
    adjusted = np.full(p.size, np.nan)
    tested = np.flatnonzero(~np.isnan(p))
    m = tested.size
    if m == 0:
        return adjusted
    order = np.argsort(p[tested])
    scaled = p[tested][order] * m / np.arange(1, m + 1)
    monotone = np.minimum.accumulate(scaled[::-1])[::-1]   # adjusted p can't decrease with rank
    adjusted[tested[order]] = np.minimum(monotone, 1.0)
    return adjusted


def league_table(first: pd.DataFrame, min_n: int = MIN_N, q: float = FDR_Q) -> pd.DataFrame:
    """One row per team x score state: gap vs rest of league, CI, permutation p, corrections."""
    rows = []
    for team in sorted(first["team"].unique()):
        is_team = first["team"] == team
        for state in STATES:
            in_state = first["score_state"] == state
            a = first.loc[is_team & in_state, "clock"]
            b = first.loc[~is_team & in_state, "clock"]
            row = {"team": team, "score_state": state, "n_team": len(a), "n_league": len(b),
                   "team_median": round(float(np.median(a)), 1) if len(a) else np.nan,
                   "tested": len(a) >= min_n}
            if row["tested"]:
                diff, low, high = bootstrap_median_diff_ci(a, b)
                row.update(diff_minutes=round(diff, 1), ci95_low=round(low, 1), ci95_high=round(high, 1),
                           permutation_p=permutation_test_median_diff(a, b))
            else:
                row.update(diff_minutes=np.nan, ci95_low=np.nan, ci95_high=np.nan, permutation_p=np.nan)
            rows.append(row)
    table = pd.DataFrame(rows)
    n_tests = int(table["tested"].sum())
    table["bh_adjusted_p"] = bh_adjusted(table["permutation_p"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["permutation_p"], q)
    table["bonferroni_significant"] = (table["permutation_p"] < 0.05 / max(n_tests, 1)).fillna(False)
    table["permutation_p"] = table["permutation_p"].round(4)
    return table


def overview_title(table: pd.DataFrame) -> str:
    n_tests, n_sig = int(table["tested"].sum()), int(table["fdr_significant"].sum())
    if n_sig == 0:
        return f"No team's first-substitution timing stands out after correcting for {n_tests} comparisons"
    return f"{n_sig} of {n_tests} team-situations stand out after correcting for multiple comparisons"


def plot_overview(table: pd.DataFrame, path) -> None:
    """One panel per score state: each team's gap vs the league, with 95% CI."""
    teams = sorted(table["team"].unique())
    fig, axes = plt.subplots(1, len(STATES), figsize=(14, 8), sharey=True)
    for ax, state in zip(axes, STATES):
        rows = table[table["score_state"] == state].set_index("team").reindex(teams)
        for y, (team, r) in enumerate(rows.iterrows()):
            if not r["tested"]:
                ax.text(0, y, f"n={int(r['n_team'])} (<{MIN_N})", ha="center", va="center",
                        fontsize=7, color="#999999")
                continue
            colour = "#DB0007" if r["fdr_significant"] else "#555555"
            ax.errorbar(r["diff_minutes"], y,
                        xerr=[[r["diff_minutes"] - r["ci95_low"]], [r["ci95_high"] - r["diff_minutes"]]],
                        fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
        ax.axvline(0, color="#333333", linewidth=1, linestyle="--")
        ax.set_title(state.capitalize(), fontsize=11)
        ax.set_xlabel("Team median minus league median (min)")
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(range(len(teams)), teams)
    axes[0].invert_yaxis()
    fig.suptitle(overview_title(table), x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"First tactical substitution, Premier League 2015/16 (StatsBomb Open Data). "
             f"Red = significant after Benjamini-Hochberg correction (FDR {FDR_Q:.0%}). "
             f"Grey text = fewer than {MIN_N} matches, not tested.", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    name, *flags = VARIANTS[-1]
    first = apply_variant(subs, *flags)
    table = league_table(first)

    n_tests = int(table["tested"].sum())
    print(f"Definition: {name}")
    print(f"Comparisons tested: {n_tests} of {len(table)} "
          f"({len(table) - n_tests} skipped: fewer than {MIN_N} matches)")
    print("Skipped per score state:",
          table[~table["tested"]]["score_state"].value_counts().reindex(STATES, fill_value=0).to_dict())

    cols = ["team", "score_state", "n_team", "diff_minutes", "ci95_low", "ci95_high",
            "permutation_p", "bh_adjusted_p", "fdr_significant", "bonferroni_significant"]
    print("\nTen smallest p-values:")
    print(table[table["tested"]].sort_values("permutation_p")[cols].head(10).to_string(index=False))
    print(f"\nSignificant after Benjamini-Hochberg (FDR {FDR_Q:.0%}): {int(table['fdr_significant'].sum())}")
    print(f"Significant after Bonferroni (0.05/{n_tests}): {int(table['bonferroni_significant'].sum())}")

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "first_sub_gaps_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "league_overview.png"
    plot_overview(table, out_fig)
    print(f"\nHeadline: {overview_title(table)}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
