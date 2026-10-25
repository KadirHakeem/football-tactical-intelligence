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

## 2026-10-24 - Phase 1: first tactical substitution timing by score state

**Done**
- `fti/first_sub.py`: first Tactical sub per team-match (injury changes skipped, flagged), median minute
  with 95% percentile-bootstrap CI (10,000 resamples, seed 42) -> results/first_sub_timing_by_state.csv.
- Tests: 6 passed (3 new: injury skipping, bootstrap reproducibility, zero-width edge case).
- Coverage: 758 of 760 team-matches had a tactical sub (Arsenal 38/38); 65 preceded by an injury change (Arsenal 2).

**Result (descriptive, 2015/16)** - median first tactical sub minute (95% CI):
| State | Arsenal | Rest of league |
|---|---|---|
| Winning | 71.6 (67.4-74.8), n=18 | 66.1 (64.4-68.1), n=217 |
| Drawing | 58.3 (22.6-69.1), n=12 | 61.8 (59.8-63.4), n=258 |
| Losing | 59.1 (45.0-63.2), n=8 | 57.5 (55.0-59.4), n=245 |

- Winning: CIs do not overlap -> candidate finding (Arsenal ~5-6 min later). Not yet tested formally; no controls.
- Drawing / losing: too uncertain to distinguish from the league.
- Caveat: score state and timing are entangled (all matches start drawing); within-state comparison
  partly controls this. Survival/time-to-event model is a later, more rigorous option.

## 2026-10-24 - Phase 1: difference test, data-quality discovery, sensitivity analysis

**Done**
- Bootstrap CI for the difference in medians (Arsenal - rest of league) per score state.
- Inspected Arsenal's early "drawing" first subs: StatsBomb labels some injuries as "Tactical"
  (Koscielny 11' v Norwich, 29 Nov 2015 - confirmed injury), and red cards force changes.
- Red-card detection (foul_committed_card / bad_behaviour_card = Red Card or Second Yellow);
  191 of 2,109 subs came after a red card in the match. Still 0 goal mismatches.
- Sensitivity variants A-D (exclude red-card cases; first-half "Tactical" = suspected injury;
  exclude earlier injury change) -> results/first_sub_sensitivity.csv.

**Result** - winning-state gap (Arsenal later than league), 95% bootstrap CI:
| Variant | Gap (min) | CI |
|---|---|---|
| A | +5.5 | +0.5 to +9.5 |
| B | +8.2 | +0.2 to +10.2 |
| C | +7.9 | +0.1 to +10.2 |
| D | +8.0 | +0.2 to +10.2 |
- Direction consistent and slightly larger after cleaning; lower bound always near zero -> consistent but fragile.
- Drawing D (n=6) excludes zero only after several filters: treat as noise (forking paths), not a finding.
- Losing: no evidence of difference in any variant.
- Caution: 12 comparisons (4 variants x 3 states) - some "significant" results expected by chance.

## Next steps (Phase 1)
1. Winning margin check (ahead by 1 vs 2+): is Arsenal's later timing explained by how far ahead they were?
2. A rank-based check (permutation or Mann-Whitney) to complement the bootstrap for small n.
3. First charts (distribution of first-sub minute, Arsenal vs league, by state).
4. Arsenal findings + limitations section in the README.
