"""Run the full pipeline in order with one command.

From the project root:
    python -m fti                                   # all steps for Arsenal (first run downloads ~1.2 GB)
    python -m fti --skip-ingest                     # reuse the existing local cache
    python -m fti --skip-ingest --team "Leicester City"
    python -m fti --list-teams                      # the 20 valid team names
    python -m fti --skip-ingest --rebuild           # force rebuilding the substitutions table
    python -m fti --skip-ingest --league            # all 20 teams: timing, half-time, double/triple, halves, pressing

Steps: ingest -> substitutions -> first_sub -> robustness -> charts.
Results for each team go to results/<team>/. Stops at the first failing step.
"""
from __future__ import annotations

import argparse
import time

from fti import (charts, first_sub, halftime, halves, ingest, league, pressing, robustness,
                 substitutions, windows)
from fti.teams import DEFAULT_TEAM, list_teams, resolve_team, team_results_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full analysis pipeline.")
    parser.add_argument("--skip-ingest", action="store_true", help="use the existing data cache")
    parser.add_argument("--team", default=DEFAULT_TEAM, help=f"team to analyse (default: {DEFAULT_TEAM})")
    parser.add_argument("--list-teams", action="store_true", help="print the valid team names and exit")
    parser.add_argument("--league", action="store_true",
                        help="run the league-wide comparison of all teams instead of a single-team analysis")
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild the substitutions table even if it is up to date")
    args = parser.parse_args()

    if args.list_teams:
        print("\n".join(list_teams()))
        return
    try:
        team = resolve_team(args.team)
    except ValueError as exc:
        raise SystemExit(str(exc))

    def substitutions_step() -> None:
        if not args.rebuild and substitutions.table_is_current():
            print("substitutions.csv is up to date - skipped (use --rebuild to force)")
        else:
            substitutions.main()

    steps = [
        ("substitutions: score at every substitution (all teams)", substitutions_step),
        (f"first_sub: timing by score state + sensitivity ({team})", lambda: first_sub.main(team)),
        (f"robustness: margin split + permutation tests ({team})", lambda: robustness.main(team)),
        (f"charts: figures ({team})", lambda: charts.main(team)),
    ]
    if args.league:
        steps = [steps[0], ("league: first-sub timing, all teams vs league, FDR-corrected", league.main),
                 ("halftime: half-time change rate, all teams vs league, FDR-corrected", halftime.main),
                 ("windows: double/triple changes, all teams vs league, FDR-corrected", windows.main),
                 ("halves: second-half share of xG, all teams vs league, FDR-corrected", halves.main),
                 ("pressing: pressing height after taking the lead, FDR-corrected", pressing.main)]
    if not args.skip_ingest:
        steps.insert(0, ("ingest: download/cache match data", lambda: ingest.main([])))

    start = time.perf_counter()
    for i, (name, step) in enumerate(steps, start=1):
        print(f"\n=== [{i}/{len(steps)}] {name} ===")
        t0 = time.perf_counter()
        step()
        print(f"--- done in {time.perf_counter() - t0:.1f}s")
    where = league.LEAGUE_DIR if args.league else team_results_dir(team)
    print(f"\nPipeline complete in {time.perf_counter() - start:.1f}s. Results in {where}")


if __name__ == "__main__":
    main()
