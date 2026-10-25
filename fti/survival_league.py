"""Survival model for every team: does any team's first-change timing stand out after controls?

Run from the project root (after python -m fti.substitutions):
    python -m fti.survival_league

Fits the fti.survival model once per team (20 fits). Each gives the team-vs-league odds ratio for a
first tactical change per minute while winning, drawing and losing. Rules fixed before running:
a team-state is tested only if at least MIN_N of the team's matches contribute minutes in that state;
Benjamini-Hochberg (FDR 5%) across all tested team-states; fits that fail are reported, not dropped.
Writes results/league/survival_all_teams.csv and a chart.
"""
from __future__ import annotations

import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.ingest import load_matches
from fti.league import FDR_Q, LEAGUE_DIR, MIN_N, benjamini_hochberg, bh_adjusted
from fti.substitutions import PROCESSED_DIR
from fti.survival import fit_model, load_timeline, minute_rows, odds_ratio

STATES = {"winning": "is_team + team_win", "drawing": "is_team", "losing": "is_team + team_lose"}


def matches_in_state(rows: pd.DataFrame) -> pd.DataFrame:
    """Per team: number of team-matches contributing at least one minute in each score state."""
    r = rows.assign(drawing=1 - rows["winning"] - rows["losing"])
    out = {s: r[r[s] == 1].groupby("team")["match_id"].nunique() for s in STATES}
    return pd.DataFrame(out).fillna(0).astype(int)


def league_survival_table(rows: pd.DataFrame, min_n: int = MIN_N, q: float = FDR_Q) -> pd.DataFrame:
    counts = matches_in_state(rows)
    records = []
    for team in sorted(rows["team"].unique()):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = fit_model(rows, team)
            fit_ok = bool(result.mle_retvals.get("converged", True))
        except Exception:                      # e.g. perfect separation for a rarely seen state
            result, fit_ok = None, False
        for state, expr in STATES.items():
            n = int(counts.loc[team, state]) if team in counts.index else 0
            rec = {"team": team, "score_state": state, "n_matches_in_state": n,
                   "tested": bool(fit_ok and n >= min_n), "estimable": fit_ok}
            if rec["tested"]:
                rec.update(odds_ratio(result, expr))
            else:
                rec.update(odds_ratio=np.nan, ci95_low=np.nan, ci95_high=np.nan, p_value=np.nan)
            records.append(rec)
    table = pd.DataFrame(records)
    table["bh_adjusted_p"] = bh_adjusted(table["p_value"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["p_value"], q)
    return table


def survival_league_title(table: pd.DataFrame) -> str:
    n_tests, n_sig = int(table["tested"].sum()), int(table["fdr_significant"].sum())
    if n_sig == 0:
        return f"After controls, no team's first-change timing stands out across {n_tests} comparisons"
    return f"After controls, {n_sig} of {n_tests} team-situations stand out for first-change timing"


def plot_survival_league(table: pd.DataFrame, path) -> None:
    teams = sorted(table["team"].unique())
    fig, axes = plt.subplots(1, len(STATES), figsize=(14, 8), sharey=True)
    for ax, state in zip(axes, STATES):
        rows = table[table["score_state"] == state].set_index("team").reindex(teams)
        for y, (team, r) in enumerate(rows.iterrows()):
            if not r["tested"]:
                label = f"n={int(r['n_matches_in_state'])}" if r["estimable"] else "not estimable"
                ax.text(1, y, label, ha="center", va="center", fontsize=7, color="#999999", zorder=3,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
                continue
            colour = "#DB0007" if r["fdr_significant"] else "#555555"
            ax.errorbar(r["odds_ratio"], y, xerr=[[r["odds_ratio"] - r["ci95_low"]], [r["ci95_high"] - r["odds_ratio"]]],
                        fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
        ax.axvline(1, color="#333333", linestyle="--", linewidth=1)
        ax.set_xscale("log")
        ax.set_title(f"While {state}", fontsize=11)
        ax.set_xlabel("Odds ratio vs league (log; <1 = later)")
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(range(len(teams)), teams)
    axes[0].invert_yaxis()
    fig.suptitle(survival_league_title(table), x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16 (StatsBomb Open Data). One survival model per team (controls: minute, "
             f"half-time, home, team and opponent strength). Red = significant after Benjamini-Hochberg "
             f"(FDR {FDR_Q:.0%}); grey text = fewer than {MIN_N} matches in that state or model not estimable.",
             fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    rows = minute_rows(subs, load_timeline(), load_matches())
    print(f"Minute rows: {len(rows)}; fitting one model per team (20 fits)...")
    table = league_survival_table(rows)
    n_tests = int(table["tested"].sum())
    print(f"Tested: {n_tests} of {len(table)} team-states; not estimable fits: "
          f"{table.loc[~table['estimable'], 'team'].nunique()} team(s)")

    cols = ["team", "score_state", "n_matches_in_state", "odds_ratio", "ci95_low", "ci95_high",
            "p_value", "bh_adjusted_p", "fdr_significant"]
    print("\nTen smallest p-values:")
    print(table[table["tested"]].sort_values("p_value")[cols].head(10).to_string(index=False))
    print("\nArsenal rows:")
    print(table[table["team"] == "Arsenal"][cols].to_string(index=False))

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "survival_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "survival_all_teams.png"
    plot_survival_league(table, out_fig)
    print(f"\nHeadline: {survival_league_title(table)}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
