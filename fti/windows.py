"""Late and simultaneous changes: double/triple substitutions and the share of changes after 60'.

Run from the project root (after python -m fti.substitutions):
    python -m fti.windows

Pre-registered in docs/analysis_plan.md (section A):
- window = substitutions by the same team, same half, within WINDOW_SECONDS of each other
- main measure = share of a team's matches with at least one double or triple change
- secondary (descriptive) = share of matches with a triple change; share of changes after 60'
Tactical changes only, excluding any made after a red card in the match. Writes results/league/.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.halftime import permutation_test_share_diff, wilson_ci
from fti.ingest import load_matches
from fti.league import FDR_Q, LEAGUE_DIR, benjamini_hochberg, bh_adjusted
from fti.substitutions import PROCESSED_DIR

WINDOW_SECONDS = 60
LATE_MINUTE = 60


def eligible_subs(subs: pd.DataFrame) -> pd.DataFrame:
    """Tactical changes made with no red card earlier in the match."""
    no_red = (subs["red_cards_for"] + subs["red_cards_against"]) == 0
    return subs[(subs["outcome"] == "Tactical") & no_red].copy()


def assign_windows(subs: pd.DataFrame, window_seconds: int = WINDOW_SECONDS) -> pd.DataFrame:
    """Add `window_id` and `window_size`: changes by one team, in one half, each within
    `window_seconds` of the previous change, form one window (one stoppage)."""
    s = subs.sort_values(["match_id", "team", "period", "event_index"]).copy()
    seconds = s["minute"] * 60 + s["second"]
    same_group = ((s["match_id"] == s["match_id"].shift()) & (s["team"] == s["team"].shift())
                  & (s["period"] == s["period"].shift()))
    new_window = ~same_group | ((seconds - seconds.shift()) > window_seconds)
    s["window_id"] = new_window.cumsum()
    s["window_size"] = s.groupby("window_id")["window_id"].transform("size")
    return s


def team_match_flags(windows: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match (all 760): did the team make a double+ / triple change?"""
    all_tm = pd.concat([matches[["match_id", "home_team"]].rename(columns={"home_team": "team"}),
                        matches[["match_id", "away_team"]].rename(columns={"away_team": "team"})])
    biggest = windows.groupby(["match_id", "team"])["window_size"].max().rename("max_window")
    flags = all_tm.merge(biggest, on=["match_id", "team"], how="left").fillna({"max_window": 0})
    flags["multi"] = (flags["max_window"] >= 2).astype(int)
    flags["triple"] = (flags["max_window"] >= 3).astype(int)
    return flags


def team_table(flags: pd.DataFrame, windows: pd.DataFrame, q: float = FDR_Q) -> pd.DataFrame:
    """Per team: share of matches with a double/triple change vs rest of league, plus descriptives."""
    late = windows.assign(late=((windows["minute"] + windows["second"] / 60) >= LATE_MINUTE).astype(int))
    rows = []
    for team in sorted(flags["team"].unique()):
        is_team = flags["team"] == team
        a, b = flags.loc[is_team, "multi"], flags.loc[~is_team, "multi"]
        low, high = wilson_ci(int(a.sum()), len(a))
        team_late = late.loc[late["team"] == team, "late"]
        rows.append({
            "team": team, "matches": len(a), "multi_matches": int(a.sum()),
            "share_multi": round(a.mean(), 3), "ci95_low": round(low, 3), "ci95_high": round(high, 3),
            "share_multi_league": round(b.mean(), 3), "diff_pp": round(100 * (a.mean() - b.mean()), 1),
            "permutation_p": permutation_test_share_diff(a, b),
            "share_triple": round(flags.loc[is_team, "triple"].mean(), 3),
            "share_changes_after_60": round(team_late.mean(), 3) if len(team_late) else np.nan,
        })
    table = pd.DataFrame(rows)
    table["bh_adjusted_p"] = bh_adjusted(table["permutation_p"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["permutation_p"], q)
    table["permutation_p"] = table["permutation_p"].round(4)
    return table


def windows_title(table: pd.DataFrame) -> str:
    n_sig = int(table["fdr_significant"].sum())
    if n_sig == 0:
        return "No team's use of double/triple changes stands out after correcting for 20 comparisons"
    return f"{n_sig} of 20 teams stand out for double/triple changes after correction"


def plot_windows(table: pd.DataFrame, league_multi: float, league_late: float, path) -> None:
    t = table.sort_values("team")
    teams = list(t["team"])
    y = np.arange(len(teams))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 8), sharey=True)
    for yi, (_, r) in zip(y, t.iterrows()):
        colour = "#DB0007" if r["fdr_significant"] else "#555555"
        share = 100 * r["share_multi"]
        ax1.errorbar(share, yi, xerr=[[share - 100 * r["ci95_low"]], [100 * r["ci95_high"] - share]],
                     fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
    ax1.axvline(100 * league_multi, color="#333333", linestyle="--", linewidth=1)
    ax1.set_title(f"Matches with a double/triple change (league: {league_multi:.0%})", fontsize=11)
    ax1.set_xlabel("% of team's matches (Wilson 95% interval)")
    ax1.set_xlim(0, 100)
    ax2.scatter(100 * t["share_changes_after_60"], y, color="#555555", s=30)
    ax2.axvline(100 * league_late, color="#333333", linestyle="--", linewidth=1)
    ax2.set_title(f"Tactical changes made after 60' (league: {league_late:.0%}) - descriptive", fontsize=11)
    ax2.set_xlabel("% of team's tactical changes")
    ax2.set_xlim(0, 100)
    for ax in (ax1, ax2):
        ax.grid(axis="x", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    ax1.set_yticks(y, teams)
    ax1.invert_yaxis()
    fig.suptitle(windows_title(table), x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16 (StatsBomb Open Data). Tactical changes, excluding those after a "
             f"red card. Double/triple = changes within {WINDOW_SECONDS}s in the same half. Red = significant "
             f"after Benjamini-Hochberg (FDR {FDR_Q:.0%}).", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    windows = assign_windows(eligible_subs(subs))
    flags = team_match_flags(windows, load_matches())

    per_window = windows.drop_duplicates("window_id")
    print(f"Eligible tactical changes: {len(windows)} in {len(per_window)} windows")
    print("Window sizes (number of windows):", per_window["window_size"].value_counts().sort_index().to_dict())
    league_multi, league_late = flags["multi"].mean(), (
        (windows["minute"] + windows["second"] / 60) >= LATE_MINUTE).mean()
    print(f"Team-matches with a double/triple change: {league_multi:.0%}  |  with a triple: "
          f"{flags['triple'].mean():.0%}  |  changes after 60': {league_late:.0%}")
    multi_clock = per_window.loc[per_window["window_size"] >= 2, ["minute", "second"]]
    single_clock = per_window.loc[per_window["window_size"] == 1, ["minute", "second"]]
    print(f"Median minute of double/triple windows: {(multi_clock['minute'] + multi_clock['second'] / 60).median():.1f}"
          f"  |  single changes: {(single_clock['minute'] + single_clock['second'] / 60).median():.1f}")

    print("\nSanity check - Arsenal double/triple changes (verify one against a match report):")
    ars = windows[(windows["team"] == "Arsenal") & (windows["window_size"] >= 2)]
    cols = ["match_date", "opponent", "period", "minute", "second", "player_off", "player_on"]
    print(ars[cols].head(9).to_string(index=False))

    table = team_table(flags, windows)
    cols = ["team", "multi_matches", "share_multi", "share_multi_league", "diff_pp", "permutation_p",
            "bh_adjusted_p", "fdr_significant", "share_triple", "share_changes_after_60"]
    print("\nAll teams, sorted by share of matches with a double/triple change:")
    print(table.sort_values("share_multi", ascending=False)[cols].to_string(index=False))

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "simultaneous_changes_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "simultaneous_changes_overview.png"
    plot_windows(table, league_multi, league_late, out_fig)
    print(f"\nHeadline: {windows_title(table)}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
