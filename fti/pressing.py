"""Pressing height before vs after taking the lead.

Run from the project root (after python -m fti.ingest):
    python -m fti.pressing

Pre-registered in docs/analysis_plan.md (section C). For every match in which a team took the lead:
- "before" = the team's pressure events before it first went ahead
- "leading" = its pressure events from going ahead until the lead was lost (or full time)
- change = median x of "leading" minus median x of "before" (negative = pressed deeper once ahead)
StatsBomb coordinates are from the acting team's point of view: x runs 0 (own goal line) to 120
(opponent's goal line). Rules fixed before running: events after any red card are excluded; a match
counts only with at least MIN_EVENTS pressures in each phase; a team is tested only with at least
MIN_N qualifying matches. Team vs rest of league: bootstrap CI, permutation test, Benjamini-Hochberg.
Caveat: "before" includes the fresh early minutes, so some deepening may be fatigue, not choice.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.halftime import permutation_test_share_diff
from fti.halves import bootstrap_mean_diff_ci
from fti.ingest import EVENTS_DIR, load_events, load_matches
from fti.league import FDR_Q, LEAGUE_DIR, MIN_N, benjamini_hochberg, bh_adjusted
from fti.substitutions import PROCESSED_DIR, extract_goals, extract_red_cards, table_is_current

MIN_EVENTS = 10
LEAD_PRESSING = PROCESSED_DIR / "lead_pressing.csv"
LP_COLUMNS = ["match_id", "team", "opponent", "lead_minute", "n_before", "n_leading",
              "x_before", "x_leading", "change"]


def _x(locations: pd.Series) -> np.ndarray:
    return np.array([loc[0] for loc in locations], dtype=float)


def lead_phase_pressing(events: pd.DataFrame, home: str, away: str, match_id: int,
                        min_events: int = MIN_EVENTS) -> list[dict]:
    """Median pressing x before vs while leading, for each team that took the lead in this match."""
    reds = extract_red_cards(events)
    cutoff = reds["index"].min() if len(reds) else np.inf          # ignore everything after a red card
    goals = extract_goals(events)
    press = events[(events["type"] == "Pressure") & events["period"].isin([1, 2])
                   & (events["index"] < cutoff) & events["location"].notna()]
    rows = []
    for team, opponent in ((home, away), (away, home)):
        diff, lead_start, lead_end = 0, None, np.inf
        for g_index, g_team, g_minute in zip(goals["index"], goals["team"], goals["minute"]):
            diff += 1 if g_team == team else -1
            if lead_start is None and diff > 0:
                lead_start, lead_minute = g_index, g_minute
            elif lead_start is not None and diff <= 0:
                lead_end = g_index
                break
        if lead_start is None or lead_start >= cutoff:
            continue
        own = press[press["team"] == team]
        before = own[own["index"] < lead_start]
        leading = own[(own["index"] > lead_start) & (own["index"] < lead_end)]
        if len(before) < min_events or len(leading) < min_events:
            continue
        xb, xl = float(np.median(_x(before["location"]))), float(np.median(_x(leading["location"])))
        rows.append({"match_id": match_id, "team": team, "opponent": opponent, "lead_minute": lead_minute,
                     "n_before": len(before), "n_leading": len(leading),
                     "x_before": round(xb, 2), "x_leading": round(xl, 2), "change": round(xl - xb, 2)})
    return rows


def check_coordinates(events: pd.DataFrame) -> None:
    """Stop unless pressure events carry pitch coordinates in the acting team's frame."""
    press = events[events["type"] == "Pressure"]
    if "location" not in events.columns or press.empty or press["location"].notna().mean() < 0.9:
        raise SystemExit("Data check failed: pressure events lack pitch coordinates (location)")


def build_lead_pressing() -> pd.DataFrame:
    matches = load_matches().sort_values(["match_date", "match_id"])
    rows = []
    for i, m in enumerate(matches.itertuples()):
        events = load_events(int(m.match_id))
        if i == 0:
            check_coordinates(events)
        rows += lead_phase_pressing(events, m.home_team, m.away_team, int(m.match_id))
    table = pd.DataFrame(rows, columns=LP_COLUMNS)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(LEAD_PRESSING, index=False)
    return table


def load_lead_pressing() -> pd.DataFrame:
    from fti import substitutions
    sources = [Path(__file__), Path(substitutions.__file__), *EVENTS_DIR.glob("*.pkl")]
    if table_is_current(LEAD_PRESSING, sources=sources, columns=LP_COLUMNS):
        return pd.read_csv(LEAD_PRESSING)
    print("Building lead-phase pressing table from cached events (one-off, ~30-60 s)...")
    return build_lead_pressing()


def orientation_check() -> tuple[float, float]:
    """Median x of shots and of pressures in one cached match: shots should sit near the opponent goal."""
    m = load_matches().sort_values("match_date").iloc[0]
    ev = load_events(int(m["match_id"]))
    shots = ev[(ev["type"] == "Shot") & ev["location"].notna()]
    press = ev[(ev["type"] == "Pressure") & ev["location"].notna()]
    return float(np.median(_x(shots["location"]))), float(np.median(_x(press["location"])))


def bootstrap_mean_ci(values, n_boot: int = 10_000, ci: float = 0.95, seed: int = 42):
    v = np.asarray(values, dtype=float)
    means = np.random.default_rng(seed).choice(v, size=(n_boot, v.size)).mean(axis=1)
    low, high = np.quantile(means, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(v.mean()), float(low), float(high)


def team_table(lp: pd.DataFrame, min_n: int = MIN_N, q: float = FDR_Q) -> pd.DataFrame:
    rows = []
    for team in sorted(lp["team"].unique()):
        is_team = lp["team"] == team
        a, b = lp.loc[is_team, "change"], lp.loc[~is_team, "change"]
        row = {"team": team, "n_matches": len(a), "tested": len(a) >= min_n,
               "mean_change": round(a.mean(), 2), "mean_change_league": round(b.mean(), 2),
               "x_before": round(lp.loc[is_team, "x_before"].mean(), 1),
               "x_leading": round(lp.loc[is_team, "x_leading"].mean(), 1)}
        if row["tested"]:
            _, low, high = bootstrap_mean_ci(a)
            diff, dlow, dhigh = bootstrap_mean_diff_ci(a, b)
            row.update(ci95_low=round(low, 2), ci95_high=round(high, 2), diff_vs_league=round(diff, 2),
                       diff_ci95_low=round(dlow, 2), diff_ci95_high=round(dhigh, 2),
                       permutation_p=permutation_test_share_diff(a, b))   # mean-difference permutation test
        else:
            row.update(ci95_low=np.nan, ci95_high=np.nan, diff_vs_league=np.nan,
                       diff_ci95_low=np.nan, diff_ci95_high=np.nan, permutation_p=np.nan)
        rows.append(row)
    table = pd.DataFrame(rows)
    table["bh_adjusted_p"] = bh_adjusted(table["permutation_p"]).round(4)
    table["fdr_significant"] = benjamini_hochberg(table["permutation_p"], q)
    table["permutation_p"] = table["permutation_p"].round(4)
    return table


def pressing_title(table: pd.DataFrame, league_mean: float, league_ci: tuple[float, float]) -> str:
    n_tests, n_sig = int(table["tested"].sum()), int(table["fdr_significant"].sum())
    if league_ci[1] < 0:
        league = "Teams pressed deeper after taking the lead"
    elif league_ci[0] > 0:
        league = "Teams pressed higher after taking the lead"
    else:
        league = "No clear league-wide change in pressing height after taking the lead"
    teams = "no team stands out" if n_sig == 0 else f"{n_sig} of {n_tests} teams stand out"
    return f"{league}; {teams} after correction"


def plot_pressing(table: pd.DataFrame, league_mean: float, title: str, path) -> None:
    t = table.sort_values("team")
    y = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(10, 8))
    for yi, (_, r) in zip(y, t.iterrows()):
        if not r["tested"]:
            ax.text(0, yi, f"n={int(r['n_matches'])} (<{MIN_N})", ha="center", va="center", fontsize=7,
                    color="#999999", zorder=3, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
            continue
        colour = "#DB0007" if r["fdr_significant"] else "#555555"
        ax.errorbar(r["mean_change"], yi, xerr=[[r["mean_change"] - r["ci95_low"]], [r["ci95_high"] - r["mean_change"]]],
                    fmt="o", color=colour, ecolor=colour, elinewidth=1.5, capsize=3, markersize=5)
    ax.axvline(0, color="#BBBBBB", linestyle=":", linewidth=1)
    ax.axvline(league_mean, color="#333333", linestyle="--", linewidth=1)
    ax.set_yticks(y, list(t["team"]))
    ax.invert_yaxis()
    ax.set_xlabel("Change in median pressing position after going ahead (pitch units; negative = deeper)")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16 (StatsBomb Open Data; pitch length 120 units). Dashed = league mean, "
             f"dotted = no change. Matches with >= {MIN_EVENTS} pressures in each phase, no red card. "
             f"Red = significant after Benjamini-Hochberg (FDR {FDR_Q:.0%}).", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    shot_x, press_x = orientation_check()
    print(f"Orientation check (one match): median shot x = {shot_x:.0f}, median pressure x = {press_x:.0f} "
          f"(shots near 100+ means coordinates are in the acting team's frame)")
    lp = load_lead_pressing()
    print(f"Qualifying team-matches (took the lead, >= {MIN_EVENTS} pressures in each phase, no red card): {len(lp)}")
    mean, low, high = bootstrap_mean_ci(lp["change"])
    print(f"League: median pressing x before lead {lp['x_before'].mean():.1f}, while leading {lp['x_leading'].mean():.1f}; "
          f"mean change {mean:+.2f} (95% CI {low:+.2f} to {high:+.2f})")

    table = team_table(lp)
    cols = ["team", "n_matches", "mean_change", "ci95_low", "ci95_high", "diff_vs_league",
            "permutation_p", "bh_adjusted_p", "fdr_significant", "x_before", "x_leading"]
    print("\nAll teams, sorted by mean change (most deepening first):")
    print(table.sort_values("mean_change")[cols].to_string(index=False))

    title = pressing_title(table, mean, (low, high))
    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "pressing_after_lead_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "pressing_after_lead_overview.png"
    plot_pressing(table, mean, title, out_fig)
    print(f"\nHeadline: {title}")
    print(f"Saved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
