"""Charts for the first-substitution analysis, saved as PNGs in results/figures/.

Run from the project root (after python -m fti.substitutions):
    python -m fti.charts
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files; no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from fti.first_sub import RESULTS_DIR, STATES, TEAM, VARIANTS, apply_variant, sensitivity
from fti.substitutions import PROCESSED_DIR

FIG_DIR = RESULTS_DIR / "figures"
TEAM_COLOUR = "#DB0007"
LEAGUE_COLOUR = "#8C8C8C"
LEAGUE_FILL = "#E9E9E9"
SOURCE_NOTE = ("Data: StatsBomb Open Data, Premier League 2015/16. Excludes changes after a red card, "
               "suspected injury changes, and matches where an injury change came first.")


def plot_first_sub_by_state(first: pd.DataFrame, path: Path, team: str = TEAM) -> None:
    """League box plot vs individual team matches (dots) for each score state."""
    fig, ax = plt.subplots(figsize=(10, 5.8))
    rng = np.random.default_rng(0)  # fixed jitter -> identical image every run
    labels = []
    for i, state in enumerate(STATES):
        in_state = first["score_state"] == state
        league = first.loc[in_state & (first["team"] != team), "clock"]
        team_vals = first.loc[in_state & (first["team"] == team), "clock"]

        ax.boxplot(league, positions=[i], widths=0.5, orientation="horizontal", showfliers=False,
                   patch_artist=True, boxprops={"facecolor": LEAGUE_FILL, "color": LEAGUE_COLOUR},
                   medianprops={"color": LEAGUE_COLOUR, "linewidth": 2.5},
                   whiskerprops={"color": LEAGUE_COLOUR}, capprops={"color": LEAGUE_COLOUR})
        ax.scatter(team_vals, i + rng.uniform(-0.13, 0.13, len(team_vals)), color=TEAM_COLOUR,
                   s=38, alpha=0.85, zorder=3)
        if len(team_vals):
            ax.plot([np.median(team_vals)] * 2, [i - 0.32, i + 0.32], color=TEAM_COLOUR,
                    linewidth=3, zorder=4)
        labels.append(f"{state.capitalize()}\n{team} n={len(team_vals)}  |  league n={len(league)}")

    ax.set_yticks(range(len(STATES)), labels)
    ax.invert_yaxis()  # winning on top
    ax.set_xlim(0, 95)
    ax.set_xlabel("Match minute of first tactical substitution")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(handles=[
        Patch(facecolor=LEAGUE_FILL, edgecolor=LEAGUE_COLOUR, label="Other 19 teams (box = middle 50%, line = median)"),
        plt.Line2D([], [], marker="o", linestyle="", color=TEAM_COLOUR, label=f"{team}: one dot per match"),
        plt.Line2D([], [], color=TEAM_COLOUR, linewidth=3, label=f"{team} median"),
    ], loc="upper left", fontsize=9, frameon=False)
    fig.suptitle(f"When winning, {team}'s first tactical change came later than the league's",
                 x=0.01, ha="left", fontsize=14, fontweight="bold")
    ax.set_title("Score state at the moment of each team's first tactical substitution",
                 loc="left", fontsize=10, color="#444444")
    fig.text(0.01, 0.01, SOURCE_NOTE, fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_sensitivity(sens: pd.DataFrame, path: Path, state: str = "winning", team: str = TEAM) -> None:
    """Forest plot: team-minus-league gap with 95% CI under each data-cleaning variant."""
    rows = sens[sens["score_state"] == state].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    y = np.arange(len(rows))
    ax.errorbar(rows["diff_minutes"], y,
                xerr=[rows["diff_minutes"] - rows["ci95_low"], rows["ci95_high"] - rows["diff_minutes"]],
                fmt="o", color=TEAM_COLOUR, ecolor=TEAM_COLOUR, elinewidth=2, capsize=5, markersize=8)
    ax.axvline(0, color="#333333", linewidth=1, linestyle="--")
    ax.set_yticks(y, [f"{v}  (n={n})" for v, n in zip(rows["variant"], rows["n_team"])])
    ax.set_ylim(len(rows) - 0.5, -0.9)  # inverted axis (top row first), with headroom for the label
    ax.text(0.15, -0.6, "\u2190 no difference", fontsize=8.5, color="#333333", va="center")
    ax.set_xlabel(f"{team} median minus league median (minutes), with 95% bootstrap interval")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"The '{state}' gap stays above zero under every data-cleaning definition",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, "Data: StatsBomb Open Data, Premier League 2015/16.", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    subs = pd.read_csv(PROCESSED_DIR / "substitutions.csv")
    first = apply_variant(subs, *VARIANTS[-1][1:])

    out1 = FIG_DIR / "first_sub_by_score_state.png"
    plot_first_sub_by_state(first, out1)
    out2 = FIG_DIR / "winning_gap_sensitivity.png"
    plot_sensitivity(sensitivity(subs), out2)
    print(f"Saved:\n  {out1}\n  {out2}")


if __name__ == "__main__":
    main()
