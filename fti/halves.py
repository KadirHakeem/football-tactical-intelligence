"""First vs second half intensity ("45-minute bursts").

Run from the project root (after python -m fti.ingest):
    python -m fti.halves

Pre-registered in docs/analysis_plan.md (section B):
- main measure = per match, the team's second-half share of its own xG, averaged over its matches,
  compared with the rest of the league (bootstrap CI for the difference in means, permutation test,
  Benjamini-Hochberg across 20 teams)
- secondary (descriptive) = the same share for shots and for pressure events
Matches where a team had zero xG (or zero shots/pressures) are left out of that measure.
Caveat: score effects - teams that lead often attack less in the second half.

Per-match half totals are cached in data/processed/half_stats.csv (rebuilt when inputs change).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.halftime import permutation_test_share_diff
from fti.ingest import EVENTS_DIR, load_events, load_matches
from fti.league import FDR_Q, LEAGUE_DIR, benjamini_hochberg, bh_adjusted
from fti.substitutions import PROCESSED_DIR, table_is_current

HALF_STATS = PROCESSED_DIR / "half_stats.csv"
HALF_COLUMNS = ["match_id", "team", "period", "xg", "shots", "pressures"]
MEASURES = {"xg": "xG", "shots": "shots", "pressures": "pressure events"}


def half_stats_for_match(events: pd.DataFrame, match_id: int) -> pd.DataFrame:
    """xG, shots and pressure events per team per half (periods 1 and 2) for one match."""
    ev = events[events["period"].isin([1, 2])]
    teams = sorted(ev["team"].dropna().unique())
    grid = pd.MultiIndex.from_product([teams, [1, 2]], names=["team", "period"])
    shots = ev[ev["type"] == "Shot"]
    xg = shots.groupby(["team", "period"])["shot_statsbomb_xg"].sum() if len(shots) else pd.Series(dtype=float)
    out = pd.DataFrame({
        "xg": xg.reindex(grid, fill_value=0.0),
        "shots": shots.groupby(["team", "period"]).size().reindex(grid, fill_value=0),
        "pressures": ev[ev["type"] == "Pressure"].groupby(["team", "period"]).size().reindex(grid, fill_value=0),
    }).reset_index()
    out.insert(0, "match_id", match_id)
    return out[HALF_COLUMNS]


def check_fields(events: pd.DataFrame) -> None:
    """Stop with a clear message if this data release lacks the fields Step B needs."""
    problems = []
    if not (events["type"] == "Shot").any() or "shot_statsbomb_xg" not in events.columns:
        problems.append("no shots with StatsBomb xG (column shot_statsbomb_xg)")
    if not (events["type"] == "Pressure").any():
        problems.append("no Pressure events")
    if problems:
        raise SystemExit("Data check failed: " + "; ".join(problems))


def build_half_stats() -> pd.DataFrame:
    matches = load_matches().sort_values(["match_date", "match_id"])
    tables = []
    for i, m in enumerate(matches.itertuples()):
        events = load_events(int(m.match_id))
        if i == 0:
            check_fields(events)
        tables.append(half_stats_for_match(events, int(m.match_id)))
    table = pd.concat(tables, ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(HALF_STATS, index=False)
    return table


def load_half_stats() -> pd.DataFrame:
    sources = [Path(__file__), *EVENTS_DIR.glob("*.pkl")]
    if table_is_current(HALF_STATS, sources=sources, columns=HALF_COLUMNS):
        return pd.read_csv(HALF_STATS)
    print("Building per-half totals from cached events (one-off, ~30 s)...")
    return build_half_stats()


def second_half_shares(half: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match: second-half share of each measure (NaN when the match total is 0)."""
    wide = half.pivot_table(index=["match_id", "team"], columns="period", values=list(MEASURES), aggfunc="sum")
    out = pd.DataFrame(index=wide.index)
    for m in MEASURES:
        first, second = wide[(m, 1)], wide[(m, 2)]
        total = first + second
        out[f"{m}_share_2h"] = (second / total).where(total > 0)
    return out.reset_index()


def bootstrap_mean_diff_ci(a, b, n_boot: int = 10_000, ci: float = 0.95, seed: int = 42):
    """Difference in means (a - b) with a percentile-bootstrap CI."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    diffs = (rng.choice(a, size=(n_boot, a.size)).mean(axis=1) - rng.choice(b, size=(n_boot, b.size)).mean(axis=1))
    low, high = np.quantile(diffs, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(a.mean() - b.mean()), float(low), float(high)


def team_table(shares: pd.DataFrame, q: float = FDR_Q) -> pd.DataFrame:
    rows = []
    for team in sorted(shares["team"].unique()):
        is_team = shares["team"] == team
        a = shares.loc[is_team, "xg_share_2h"].dropna()
        b = shares.loc[~is_team, "xg_share_2h"].dropna()
        diff, low, high = bootstrap_mean_diff_ci(a, b)
        rows.append({
            "team": team, "n_matches": len(a),
            "xg_share_2h": round(a.mean(), 3), "xg_share_2h_league": round(b.mean(), 3),
            "diff_pp": round(100 * diff, 1), "ci95_low_pp": round(100 * low, 1), "ci95_high_pp": round(100 * high, 1),
            "permutation_p": permutation_test_share_diff(a, b),  # same mean-difference permutation test
            "shots_share_2h": round(shares.loc[is_team, "shots_share_2h"].mean(), 3),
            "pressures_share_2h": round(shares.loc[is_team, "pressures_share_2h"].mean(), 3),
        })
    table = pd.DataFrame(rows)
    table["bh_adjusted_p"] = bh_adjusted(table["permutation_p"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["permutation_p"], q)
    table["permutation_p"] = table["permutation_p"].round(4)
    return table


def halves_title(table: pd.DataFrame) -> str:
    n_sig = int(table["fdr_significant"].sum())
    if n_sig == 0:
        return "No team's second-half share of its xG stands out after correcting for 20 comparisons"
    return f"{n_sig} of 20 teams stand out for second-half share of xG after correction"


def plot_halves(table: pd.DataFrame, league: dict, path) -> None:
    t = table.sort_values("team")
    y = np.arange(len(t))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 8), sharey=True)
    for yi, (_, r) in zip(y, t.iterrows()):
        colour = "#DB0007" if r["fdr_significant"] else "#555555"
        centre = 100 * r["xg_share_2h"]
        ax1.errorbar(centre, yi, xerr=[[-r["ci95_low_pp"] + r["diff_pp"]], [r["ci95_high_pp"] - r["diff_pp"]]],
                     fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
    ax1.axvline(100 * league["xg"], color="#333333", linestyle="--", linewidth=1)
    ax1.axvline(50, color="#BBBBBB", linestyle=":", linewidth=1)
    ax1.set_title(f"Second-half share of own xG (league: {league['xg']:.0%})", fontsize=11)
    ax1.set_xlabel("% of team's match xG created after half-time (CI of gap vs league)")
    ax2.scatter(100 * t["pressures_share_2h"], y, color="#555555", s=30)
    ax2.axvline(100 * league["pressures"], color="#333333", linestyle="--", linewidth=1)
    ax2.axvline(50, color="#BBBBBB", linestyle=":", linewidth=1)
    ax2.set_title(f"Second-half share of pressure events (league: {league['pressures']:.0%}) - descriptive",
                  fontsize=11)
    ax2.set_xlabel("% of team's pressure events after half-time")
    for ax in (ax1, ax2):
        ax.set_xlim(25, 75)
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    ax1.set_yticks(y, list(t["team"]))
    ax1.invert_yaxis()
    fig.suptitle(halves_title(table), x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16 (StatsBomb Open Data). Dotted line = 50/50. Red = significant after "
             f"Benjamini-Hochberg (FDR {FDR_Q:.0%}). Score effects not controlled.", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    half = load_half_stats()
    print(f"Data check: {int(half['shots'].sum())} shots, total xG {half['xg'].sum():.1f}, "
          f"{int(half['pressures'].sum())} pressure events across {half['match_id'].nunique()} matches")
    by_half = half.groupby("period")[list(MEASURES)].sum()
    league = {m: float(by_half.loc[2, m] / by_half[m].sum()) for m in MEASURES}
    print("League totals, second-half share:", {MEASURES[m]: f"{v:.1%}" for m, v in league.items()})

    shares = second_half_shares(half)
    excluded = int(shares["xg_share_2h"].isna().sum())
    print(f"Team-matches with zero xG (left out of main measure): {excluded}")
    league_mean = {m: float(shares[f"{m}_share_2h"].mean()) for m in MEASURES}

    table = team_table(shares)
    cols = ["team", "n_matches", "xg_share_2h", "xg_share_2h_league", "diff_pp", "ci95_low_pp", "ci95_high_pp",
            "permutation_p", "bh_adjusted_p", "fdr_significant", "shots_share_2h", "pressures_share_2h"]
    print("\nAll teams, sorted by second-half share of own xG:")
    print(table.sort_values("xg_share_2h", ascending=False)[cols].to_string(index=False))

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "second_half_share_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "second_half_share_overview.png"
    plot_halves(table, league_mean, out_fig)
    print(f"\nHeadline: {halves_title(table)}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
