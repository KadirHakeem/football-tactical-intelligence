# Progress log

## 2026-10-24 - Phase 0: feasibility and setup (complete)

**Decisions**
- Data: StatsBomb Open Data, Premier League 2015/16 (free; full season, all 20 clubs). Budget: $0.
- MVP question: Arsenal first-substitution timing by score state vs. league-wide distribution (see README).
- Environment: Python 3.12.2, `.venv`, project folder outside OneDrive.

**Done**
- Verified coverage: 380 matches, 38 Arsenal matches (`scripts/check_data_coverage.py`).
- Inspected substitution and goal records for Arsenal v West Ham, 2015-08-09; verified against a match report (`scripts/inspect_substitutions.py`).
- Data dictionary, README, pinned requirements, .gitignore.

**Learned**
- StatsBomb separates Tactical vs Injury substitutions.
- Minute convention: elapsed clock vs. report minute (+1).
- Goals and substitutions can be seconds apart, so ordering matters for "score at substitution".

## 2026-10-24 - Phase 1: ingestion and score state

**Done**
- `fti/ingest.py`: cached download of all 380 matches (data/cache, ~1.2 GB, git-ignored; resumable).
- `fti/substitutions.py`: score at every substitution via StatsBomb event `index` ordering -> data/processed/substitutions.csv.
- Data-quality check: goals found reproduce all 380 official final scores (0 mismatches).
- Tests: synthetic unit test + integration test on verified West Ham match (3 passed).

**Findings so far (descriptive only)**
- 2,109 substitutions (2,001 Tactical, 108 Injury), ~2.8 per team per match.
- Arsenal: 107 subs in 38 matches; first sub score state: winning 18, drawing 13, losing 7.
  Caution: these counts mainly reflect how often Arsenal were ahead, not a manager preference.

## Next steps (Phase 1)
1. First-substitution timing by score state (Tactical only), Arsenal vs league, with uncertainty intervals.
2. Data-quality checks: red cards, missing positions, simultaneous changes.
3. First charts and a short Arsenal findings section in the README.
