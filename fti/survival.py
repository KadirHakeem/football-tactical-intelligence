"""Survival (time-to-first-change) model with controls.

Run from the project root (after python -m fti.substitutions):
    python -m fti.survival                    # Arsenal (default)
    python -m fti.survival --team "Leicester City"

Pre-registered in docs/analysis_plan.md (section E). A discrete-time hazard model: each team-match
becomes one row per second-half minute, from half-time until the team's first tactical change
(event = 1) or until it stops being "at risk". A logistic regression on these rows estimates how the
chance of a first change in any given minute depends on:
- the score state at the start of that minute (updated as goals go in)
- match minute (5-minute blocks) and a half-time indicator (the interval spike)
- home/away, team strength and opponent strength (final league points, standardised)
- the chosen team vs the rest of the league, separately by score state
Main question: the team's odds of a first change per minute *while winning*, relative to the league
(odds ratio < 1 = the team waited longer). Standard errors clustered by match.

Rules (consistent with variant D): team-matches with any first-half substitution or any first-half red
card are excluded; rows stop at a second-half red card (either team) or an injury change.
Approximation: score state is taken at the start of each minute.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from fti.ingest import EVENTS_DIR, load_events, load_matches
from fti.substitutions import PROCESSED_DIR, extract_goals, extract_red_cards, table_is_current
from fti.teams import DEFAULT_TEAM, team_from_command_line, team_results_dir

TIMELINE = PROCESSED_DIR / "match_timeline.csv"
TL_COLUMNS = ["match_id", "kind", "team", "period", "clock"]
BLOCK_EDGES = list(range(45, 95, 5))   # 45-49, 50-54, ..., 85-89, 90+


# ---------- data preparation ----------
def match_timeline(events: pd.DataFrame, match_id: int) -> pd.DataFrame:
    """Goals, red cards and the end of the match, each with period and match clock."""
    rows = []
    for kind, table in (("goal", extract_goals(events)), ("red", extract_red_cards(events))):
        for _, r in table.iterrows():
            rows.append({"match_id": match_id, "kind": kind, "team": r["team"], "period": int(r["period"]),
                         "clock": float(r["minute"]) + float(r["second"]) / 60})
    second = events[events["period"] == 2]
    end = float((second["minute"] + second["second"] / 60).max()) if len(second) else 90.0
    rows.append({"match_id": match_id, "kind": "end", "team": None, "period": 2, "clock": end})
    return pd.DataFrame(rows, columns=TL_COLUMNS)


def load_timeline() -> pd.DataFrame:
    from fti import substitutions
    sources = [Path(__file__), Path(substitutions.__file__), *EVENTS_DIR.glob("*.pkl")]
    if table_is_current(TIMELINE, sources=sources, columns=TL_COLUMNS):
        return pd.read_csv(TIMELINE)
    print("Building match timeline (goals, red cards, end) from cached events (one-off, ~30-60 s)...")
    matches = load_matches()
    table = pd.concat([match_timeline(load_events(int(m)), int(m)) for m in matches["match_id"]], ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(TIMELINE, index=False)
    return table


def final_points(matches: pd.DataFrame) -> pd.Series:
    """League points per team from the match results (3 win, 1 draw, 0 loss)."""
    pts: dict[str, int] = {}
    for m in matches.itertuples():
        h, a = int(m.home_score), int(m.away_score)
        pts[m.home_team] = pts.get(m.home_team, 0) + (3 if h > a else 1 if h == a else 0)
        pts[m.away_team] = pts.get(m.away_team, 0) + (3 if a > h else 1 if h == a else 0)
    return pd.Series(pts, name="points")


def block_label(minute: int) -> str:
    if minute >= 90:
        return "90+"
    start = max(e for e in BLOCK_EDGES if e <= minute)
    return f"{start}-{start + 4}"


def minute_rows(subs: pd.DataFrame, timeline: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team-match per second-half minute at risk of a first tactical change."""
    pts = final_points(matches)
    z = (pts - pts.mean()) / pts.std()
    subs = subs.assign(clock=subs["minute"] + subs["second"] / 60)
    subs_by_tm = {k: g for k, g in subs.groupby(["match_id", "team"])}
    tl_by_match = {k: g for k, g in timeline.groupby("match_id")}
    rows = []
    for m in matches.itertuples():
        tl = tl_by_match.get(m.match_id, timeline.iloc[0:0])
        goals, reds = tl[tl["kind"] == "goal"], tl[tl["kind"] == "red"]
        end_rows = tl.loc[tl["kind"] == "end", "clock"]
        end = float(end_rows.iloc[0]) if len(end_rows) else 90.0
        if (reds["period"] == 1).any():
            continue                                             # first-half red card: excluded
        red2 = reds.loc[reds["period"] == 2, "clock"].min() if len(reds) else math.inf
        for team, opponent, home in ((m.home_team, m.away_team, 1), (m.away_team, m.home_team, 0)):
            s = subs_by_tm.get((m.match_id, team), subs.iloc[0:0])
            if (s["period"] == 1).any():
                continue                                         # first-half change: excluded (variant D)
            injury = s.loc[s["outcome"] == "Injury", "clock"].min() if len(s) else math.inf
            stop = min(end, red2 if not pd.isna(red2) else math.inf, injury if not pd.isna(injury) else math.inf)
            tactical = s.loc[s["outcome"] == "Tactical", "clock"]
            first = tactical.min() if len(tactical) else math.inf
            event_minute = math.floor(first) if first < stop else None
            # censored: keep only minutes fully at risk, i.e. minute + 1 <= stop
            last_minute = event_minute if event_minute is not None else math.floor(stop - 1)
            for minute in range(45, last_minute + 1):
                gf = int(((goals["team"] == team) & ((goals["period"] == 1) | (goals["clock"] < minute))).sum())
                ga = int(((goals["team"] == opponent) & ((goals["period"] == 1) | (goals["clock"] < minute))).sum())
                rows.append({"match_id": m.match_id, "team": team, "minute": minute,
                             "event": int(minute == event_minute),
                             "winning": int(gf > ga), "losing": int(gf < ga),
                             "half_time": int(minute == 45), "block": block_label(minute), "home": home,
                             "team_pts_z": float(z[team]), "opp_pts_z": float(z[opponent])})
    return pd.DataFrame(rows)


# ---------- model ----------
def fit_model(rows: pd.DataFrame, team: str):
    """Logistic discrete-time hazard model with team-by-score-state terms; clustered by match."""
    d = rows.assign(is_team=(rows["team"] == team).astype(int))
    d["team_win"], d["team_lose"] = d["is_team"] * d["winning"], d["is_team"] * d["losing"]
    formula = ("event ~ winning + losing + half_time + C(block) + home + team_pts_z + opp_pts_z"
               " + is_team + team_win + team_lose")
    return smf.logit(formula, data=d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d["match_id"]})


def odds_ratio(result, expression: str) -> dict:
    """Odds ratio, 95% CI and p-value for a linear combination of coefficients, e.g. 'is_team + team_win'."""
    t = result.t_test(f"{expression} = 0")
    est, (low, high) = float(np.squeeze(t.effect)), np.squeeze(t.conf_int())
    return {"odds_ratio": round(math.exp(est), 3), "ci95_low": round(math.exp(low), 3),
            "ci95_high": round(math.exp(high), 3), "p_value": round(float(np.squeeze(t.pvalue)), 4)}


def results_table(result, team: str) -> pd.DataFrame:
    terms = {
        "League: winning vs drawing": "winning", "League: losing vs drawing": "losing",
        "League: half-time minute": "half_time", "League: home vs away": "home",
        "League: team strength (+1 SD points)": "team_pts_z", "League: opponent strength (+1 SD points)": "opp_pts_z",
        f"{team} vs league, while drawing": "is_team",
        f"{team} vs league, while winning": "is_team + team_win",
        f"{team} vs league, while losing": "is_team + team_lose",
    }
    return pd.DataFrame([{"term": name, **odds_ratio(result, expr)} for name, expr in terms.items()])


def survival_headline(table: pd.DataFrame, team: str) -> str:
    row = table[table["term"] == f"{team} vs league, while winning"].iloc[0]
    if row["ci95_high"] < 1:
        return f"After controls, {team} still waited longer than the league to make a first change while winning"
    if row["ci95_low"] > 1:
        return f"After controls, {team} changed sooner than the league while winning"
    return f"After controls, no clear difference between {team} and the league while winning"


def plot_odds_ratios(table: pd.DataFrame, title: str, path) -> None:
    t = table.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    y = np.arange(len(t))
    colours = ["#DB0007" if "vs league" in term else "#555555" for term in t["term"]]
    for yi, (_, r), c in zip(y, t.iterrows(), colours):
        ax.errorbar(r["odds_ratio"], yi, xerr=[[r["odds_ratio"] - r["ci95_low"]], [r["ci95_high"] - r["odds_ratio"]]],
                    fmt="o", color=c, ecolor=c, elinewidth=1.8, capsize=4, markersize=6)
    ax.axvline(1, color="#333333", linestyle="--", linewidth=1)
    ax.set_xscale("log")
    ax.set_yticks(y, list(t["term"]))
    ax.set_xlabel("Odds ratio for a first tactical change in a given minute (log scale; <1 = later, >1 = sooner)")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, "Premier League 2015/16 (StatsBomb Open Data). Discrete-time hazard model (logistic), "
             "second-half minutes, controls for minute block, half-time, home, team and opponent strength; "
             "95% CIs clustered by match.", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main(team: str = DEFAULT_TEAM) -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    rows = minute_rows(subs, load_timeline(), load_matches())
    tm = rows.groupby(["match_id", "team"])["event"].max()
    print(f"Minute rows: {len(rows)} from {len(tm)} team-matches; first changes observed: {int(tm.sum())} "
          f"({team}: {int(tm.xs(team, level='team').sum())} of {len(tm.xs(team, level='team'))})")
    result = fit_model(rows, team)
    table = results_table(result, team)
    print("\nOdds ratios (per-minute chance of a first tactical change; <1 = later, >1 = sooner):")
    print(table.to_string(index=False))

    title = survival_headline(table, team)
    out_dir = team_results_dir(team)
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "survival_model.csv", index=False)
    (out_dir / "survival_model_summary.txt").write_text(str(result.summary()), encoding="utf-8")
    out_fig = out_dir / "figures" / "survival_odds_ratios.png"
    plot_odds_ratios(table, title, out_fig)
    print(f"\nHeadline: {title}")
    print(f"Saved:\n  {out_dir / 'survival_model.csv'}\n  {out_dir / 'survival_model_summary.txt'}\n  {out_fig}")


if __name__ == "__main__":
    main(team_from_command_line("Survival model of first tactical substitution timing with controls."))
