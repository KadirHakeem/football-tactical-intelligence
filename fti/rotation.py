"""Rotation: how evenly does each team spread league minutes across its squad?

Run from the project root (after python -m fti.ingest):
    python -m fti.rotation

Pre-registered in docs/analysis_plan.md (section D). Minutes per player per match from the event data:
starters play from kick-off (Starting XI event) until substituted, sent off, or the end of the match
(last event of the second half); substitutes from the moment they come on. Approximate: first-half
stoppage time is not added separately.
- main measure = share of the team's total league minutes played by its 11 most-used players
- secondary = number of players used; Gini coefficient of minutes (0 = perfectly even)
Descriptive ranking only (one value per team, no per-team test).
Caveat: league matches only - cup and European rotation is invisible; injuries also force rotation.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fti.ingest import EVENTS_DIR, load_events, load_matches
from fti.league import LEAGUE_DIR
from fti.substitutions import PROCESSED_DIR, extract_red_cards, table_is_current

PLAYER_MINUTES = PROCESSED_DIR / "player_minutes.csv"
PM_COLUMNS = ["match_id", "team", "player", "started", "minutes"]


def _clock(row) -> float:
    return float(row["minute"]) + float(row["second"]) / 60


def lineup_names(tactics) -> list[str]:
    """Player names from a Starting XI event's tactics field."""
    names = []
    for p in tactics["lineup"]:
        player = p["player"]
        names.append(player["name"] if isinstance(player, dict) else player)
    return names


def match_minutes(events: pd.DataFrame, match_id: int) -> pd.DataFrame:
    """Minutes played by every player who appeared, for both teams in one match."""
    ev = events[events["period"].isin([1, 2])]
    end = max(_clock(r) for _, r in ev[ev["period"] == 2].iterrows()) if (ev["period"] == 2).any() else 90.0
    on, off, started = {}, {}, {}
    for _, r in events[events["type"] == "Starting XI"].iterrows():
        for name in lineup_names(r["tactics"]):
            on[(r["team"], name)], started[(r["team"], name)] = 0.0, True
    for _, r in events[events["type"] == "Substitution"].iterrows():
        t = _clock(r)
        off[(r["team"], r["player"])] = t
        on[(r["team"], r["substitution_replacement"])] = t
        started.setdefault((r["team"], r["substitution_replacement"]), False)
    for _, r in extract_red_cards(events).iterrows():
        key = (r["team"], r["player"])
        off[key] = min(off.get(key, np.inf), _clock(r))
    rows = [{"match_id": match_id, "team": team, "player": player, "started": started[(team, player)],
             "minutes": round(max(0.0, min(off.get((team, player), end), end) - start), 2)}
            for (team, player), start in on.items()]
    return pd.DataFrame(rows, columns=PM_COLUMNS)


def check_lineups(events: pd.DataFrame) -> None:
    xi = events[events["type"] == "Starting XI"]
    if "tactics" not in events.columns or len(xi) != 2 or any(len(lineup_names(t)) != 11 for t in xi["tactics"]):
        raise SystemExit("Data check failed: expected two Starting XI events with 11 players each")


def build_player_minutes() -> pd.DataFrame:
    matches = load_matches().sort_values(["match_date", "match_id"])
    tables = []
    for i, m in enumerate(matches.itertuples()):
        events = load_events(int(m.match_id))
        if i == 0:
            check_lineups(events)
        tables.append(match_minutes(events, int(m.match_id)))
    table = pd.concat(tables, ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(PLAYER_MINUTES, index=False)
    return table


def load_player_minutes() -> pd.DataFrame:
    from fti import substitutions
    sources = [Path(__file__), Path(substitutions.__file__), *EVENTS_DIR.glob("*.pkl")]
    if table_is_current(PLAYER_MINUTES, sources=sources, columns=PM_COLUMNS):
        return pd.read_csv(PLAYER_MINUTES)
    print("Building player-minutes table from cached events (one-off, ~30-60 s)...")
    return build_player_minutes()


def gini(values) -> float:
    """Gini coefficient: 0 = everyone equal, approaching 1 = one player has everything."""
    x = np.sort(np.asarray(values, dtype=float))
    n, total = x.size, x.sum()
    if n == 0 or total == 0:
        return float("nan")
    return float(2 * np.sum(np.arange(1, n + 1) * x) / (n * total) - (n + 1) / n)


def team_rotation(pm: pd.DataFrame) -> pd.DataFrame:
    season = pm.groupby(["team", "player"])["minutes"].sum().reset_index()
    rows = []
    for team, g in season.groupby("team"):
        mins = g["minutes"].sort_values(ascending=False)
        rows.append({"team": team, "players_used": int((mins > 0).sum()),
                     "total_minutes": round(mins.sum()), "top11_share": round(mins.head(11).sum() / mins.sum(), 3),
                     "gini": round(gini(mins[mins > 0]), 3)})
    return pd.DataFrame(rows).sort_values("top11_share", ascending=False).reset_index(drop=True)


def plot_rotation(table: pd.DataFrame, path) -> None:
    t = table.sort_values("top11_share")
    fig, ax = plt.subplots(figsize=(10, 8))
    y = np.arange(len(t))
    ax.barh(y, 100 * t["top11_share"], color="#8C8C8C")
    median = 100 * table["top11_share"].median()
    ax.axvline(median, color="#333333", linestyle="--", linewidth=1)
    for yi, (_, r) in zip(y, t.iterrows()):
        ax.text(100 * r["top11_share"] + 0.3, yi, f"{r['players_used']} players", va="center", fontsize=8, color="#444444")
    ax.set_yticks(y, list(t["team"]))
    lo = max(0, 100 * t["top11_share"].min() - 8)
    ax.set_xlim(lo, 100)
    ax.set_xlabel("Share of team's league minutes played by its 11 most-used players (%)")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    top = table.iloc[0]
    fig.suptitle(f"{top['team']} relied most on a settled core ({top['top11_share']:.0%} of minutes to 11 players)",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, f"Premier League 2015/16, league matches only (StatsBomb Open Data). Dashed = league median "
             f"({median:.0f}%). Descriptive; cup/European rotation not included; injuries also force rotation.",
             fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    pm = load_player_minutes()
    per_tm = pm.groupby(["match_id", "team"])["minutes"].sum()
    print(f"Sanity check: team-matches {len(per_tm)} (expect 760); minutes per team-match "
          f"median {per_tm.median():.0f} (expect ~11 x 93), min {per_tm.min():.0f}, max {per_tm.max():.0f}")
    starters = pm[pm["started"]].groupby(["match_id", "team"]).size()
    print(f"Starters per team-match: min {starters.min()}, max {starters.max()} (expect 11)")

    table = team_rotation(pm)
    print("\nTeams ranked by share of minutes played by their 11 most-used players:")
    print(table.to_string(index=False))

    LEAGUE_DIR.mkdir(parents=True, exist_ok=True)
    out_table = LEAGUE_DIR / "rotation_all_teams.csv"
    table.to_csv(out_table, index=False)
    out_fig = LEAGUE_DIR / "figures" / "rotation_overview.png"
    plot_rotation(table, out_fig)
    print(f"\nSaved:\n  {out_table}\n  {out_fig}")


if __name__ == "__main__":
    main()
