"""Team names and per-team output folders.

list_teams()      -> the 20 exact StatsBomb team names in the season
resolve_team(x)   -> exact name for user input (any capitalisation), or a helpful error
team_results_dir  -> results/<team-slug>/  e.g. results/leicester-city/
"""
from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

from fti.ingest import PROJECT_ROOT, load_matches

RESULTS_ROOT = PROJECT_ROOT / "results"
DEFAULT_TEAM = "Arsenal"

# Common names fans actually type -> exact StatsBomb names (lower-case keys).
ALIASES = {
    "spurs": "Tottenham Hotspur", "tottenham": "Tottenham Hotspur",
    "man utd": "Manchester United", "man united": "Manchester United", "man u": "Manchester United",
    "man city": "Manchester City",
    "west brom": "West Bromwich Albion", "wba": "West Bromwich Albion",
    "palace": "Crystal Palace", "villa": "Aston Villa", "bournemouth": "AFC Bournemouth",
    "west ham": "West Ham United", "leicester": "Leicester City", "newcastle": "Newcastle United",
    "norwich": "Norwich City", "stoke": "Stoke City", "swansea": "Swansea City",
}


def list_teams() -> list[str]:
    """All teams appearing in the season's fixture list, alphabetically."""
    matches = load_matches()
    return sorted(set(matches["home_team"]) | set(matches["away_team"]))


def resolve_team(name: str, teams: list[str] | None = None) -> str:
    """Return the exact team name for `name` (case-insensitive or a common alias), or raise with suggestions."""
    teams = list_teams() if teams is None else teams
    lookup = {t.lower(): t for t in teams}
    key = " ".join(name.strip().lower().split())
    if key in lookup:
        return lookup[key]
    if key in ALIASES and ALIASES[key] in teams:
        return ALIASES[key]
    partial = [k for k in lookup if key and key in k]                       # "leicester" -> "leicester city"
    similar = difflib.get_close_matches(key, list(lookup), n=3, cutoff=0.5)  # "arsnal" -> "arsenal"
    candidates = list(dict.fromkeys(partial + similar))
    hint = f" Did you mean: {', '.join(lookup[c] for c in candidates)}?" if candidates else ""
    raise ValueError(f"Unknown team {name!r}.{hint} Run: python -m fti --list-teams")


def team_slug(team: str) -> str:
    """Folder-safe name: 'Leicester City' -> 'leicester-city'."""
    return re.sub(r"[^a-z0-9]+", "-", team.lower()).strip("-")


def team_results_dir(team: str) -> Path:
    return RESULTS_ROOT / team_slug(team)


def team_from_command_line(description: str) -> str:
    """Parse --team for running a single module directly; exits with a clear message on a bad name."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--team", default=DEFAULT_TEAM, help=f"team name (default: {DEFAULT_TEAM})")
    try:
        return resolve_team(parser.parse_args().team)
    except ValueError as exc:
        raise SystemExit(str(exc))
