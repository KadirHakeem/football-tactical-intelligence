"""Download and locally cache StatsBomb Open Data for the 2015/16 Premier League.

Run from the project root:
    python -m fti.ingest --limit 3   # quick test on the first 3 matches
    python -m fti.ingest             # all 380 matches (first run takes a while)

Cached files live in data/cache/ (git-ignored: raw StatsBomb data is not redistributed).
Re-running is safe: matches already cached are read from disk, not downloaded again.
"""
from __future__ import annotations

import argparse
import time
import warnings
from pathlib import Path

import pandas as pd
from statsbombpy import sb

# statsbombpy warns on every call when no paid credentials are given; open data needs none.
warnings.filterwarnings("ignore", message="credentials were not supplied")

COMPETITION = "Premier League"
SEASON = "2015/2016"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
EVENTS_DIR = CACHE_DIR / "events"


def get_season_ids(competition: str = COMPETITION, season: str = SEASON) -> tuple[int, int]:
    """Look up StatsBomb's competition_id and season_id by name."""
    comps = sb.competitions()
    row = comps[(comps["competition_name"] == competition) & (comps["season_name"] == season)]
    if row.empty:
        raise ValueError(f"{competition} {season} not found in StatsBomb Open Data")
    return int(row.iloc[0]["competition_id"]), int(row.iloc[0]["season_id"])


def load_matches(refresh: bool = False) -> pd.DataFrame:
    """Return the season's fixture list, from cache if available."""
    path = CACHE_DIR / "matches.pkl"
    if path.exists() and not refresh:
        return pd.read_pickle(path)
    competition_id, season_id = get_season_ids()
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    matches.to_pickle(path)
    return matches


def load_events(match_id: int, refresh: bool = False) -> pd.DataFrame:
    """Return every event for one match, from cache if available."""
    path = EVENTS_DIR / f"{match_id}.pkl"
    if path.exists() and not refresh:
        return pd.read_pickle(path)
    events = sb.events(match_id=match_id)
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    events.to_pickle(path)
    return events


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cache StatsBomb 2015/16 Premier League events.")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N matches")
    parser.add_argument("--refresh", action="store_true", help="re-download even if cached")
    args = parser.parse_args(argv)  # argv=None -> read the command line

    matches = load_matches(refresh=args.refresh).sort_values("match_date")
    match_ids = [int(m) for m in matches["match_id"]][: args.limit]
    print(f"{len(matches)} matches in season; processing {len(match_ids)}")

    failures: list[int] = []
    for i, match_id in enumerate(match_ids, start=1):
        was_cached = (EVENTS_DIR / f"{match_id}.pkl").exists() and not args.refresh
        try:
            events = load_events(match_id, refresh=args.refresh)
        except Exception as exc:  # keep going; report failures at the end
            failures.append(match_id)
            print(f"[{i}/{len(match_ids)}] match {match_id}: FAILED ({exc})")
            continue
        source = "cache" if was_cached else "downloaded"
        print(f"[{i}/{len(match_ids)}] match {match_id}: {len(events)} events ({source})")
        if not was_cached:
            time.sleep(0.5)  # be polite to the data host

    print(f"\nDone. Cached: {len(match_ids) - len(failures)}  Failed: {len(failures)}")
    if failures:
        print("Failed match IDs (re-run to retry):", failures)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
