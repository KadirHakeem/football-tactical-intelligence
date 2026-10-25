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

## 2026-10-24 - Phase 1: robustness checks (variant D as main definition)

**Done** - `fti/robustness.py` + 3 tests (13 total).
- Margin: when winning, Arsenal were ahead by 2+ more often (53% vs 42%), and league teams sub later
  with bigger leads (67.9 vs 64.2). But within each lead size Arsenal were still later:
  +7.1 min (1 goal, n=8, CI -1.8 to 12.2) and +6.2 min (2+, n=9, CI -2.1 to 13.4).
  -> margin does not explain the gap; each subgroup is too small for its own CI to exclude zero.
- Permutation test (10,000 shuffles): winning p = 0.010, drawing p = 0.22, losing p = 0.83.
  Winning still below 0.05/3 = 0.017 (Bonferroni for 3 states); drawing "finding" from variant D not supported.

**Current best statement**
> In 2015/16, when Arsenal were winning, their first tactical substitution came about 6-8 minutes later
> than other Premier League teams' in the same situation (median 71-74' vs 64-68'). The pattern holds after
> removing red-card cases and suspected mislabelled injuries, and within both 1-goal and 2+-goal leads
> (permutation p = 0.01). Single season, 17 Arsenal matches: suggestive, not conclusive. No claim about intent.

## 2026-10-24 - Phase 1 complete (tag v0.1.0)

**Done**
- Charts (`fti/charts.py`): first tactical sub by score state (league box plot + Arsenal dots), sensitivity forest plot -> results/figures/.
- README: key finding, method, limitations, embedded charts.
- One-command pipeline: `python -m fti` (ingest -> substitutions -> first_sub -> robustness -> charts), ~57 s from cache.
- Fresh pipeline run reproduced identical results (winning gap +8.0, CI +0.2 to +10.2, permutation p = 0.0101). 15 tests pass.

**Learned in Phase 1**
- Caching and resumable ingestion; package structure; unit vs integration vs smoke tests.
- Validating derived data against ground truth (official scores); inspecting individual rows behind a summary.
- Bootstrap CIs (single median and difference), permutation tests, Bonferroni, sensitivity analysis, forking paths.
- Separating observed facts, statistical associations and hypotheses in writing and chart titles.

## 2026-10-25 - Phase 2 step 1: any-team support

**Done**
- `fti/teams.py`: list/resolve team names (any capitalisation, common aliases e.g. "Spurs",
  suggestions for misspellings); per-team output folders results/<team-slug>/.
- `--team` and `--list-teams` on the pipeline (`python -m fti`) and on each module; Arsenal default.
- Evidence-based chart titles: a directional headline only if the bootstrap CI excludes zero AND
  permutation p < 0.05/3; otherwise "No clear difference". Sensitivity title claims robustness only
  if all variants agree.
- Pipeline skips rebuilding substitutions.csv when it is newer than its inputs (`--rebuild` forces).
- Arsenal results moved to results/arsenal/ and reproduced identically; README links updated.

**Leicester City (2015/16) - first run**
- Winning +2.1 min (p = 0.51), drawing -0.5 (p = 0.88): no difference from the league.
- Losing -13.2 min: CI excludes zero in all variants but n = 6, p = 0.064 -> rule correctly says
  "No clear difference". Median exactly 45.0: tied half-time values make percentile bootstrap CIs
  unreliably tight with tiny n - the permutation requirement guards against this.

**Hypotheses noted (not findings)**
- Half-time changes are a distinct decision moment (4 of Leicester's 12 drawing first changes at 45:00);
  "share of first changes at half-time" per manager links to the "45-minute bursts" idea.
- Lead size: Leicester slightly earlier when 1 up (-3.0, CI crosses 0), later when 2+ up
  (+5.8, CI +1.9 to +11.0, n = 8) - post-hoc subgroup, hypothesis only.
- Data quirk: some names contain doubled apostrophes (e.g. "N''Golo Kanté"); use lineup display names later.

## 2026-10-25 - Phase 2 step 2: league-wide comparison

**Done** - `fti/league.py` (+7 tests, 36 total); `python -m fti --league`.
- All 20 teams x 3 score states, variant D; min 8 matches per team-state (pre-specified); 42 of 60 tested.
- Benjamini-Hochberg (FDR 5%) implemented by hand, Bonferroni alongside.
- Skips: weaker teams rarely winning, stronger teams rarely losing (my prediction of mostly losing-state
  skips was wrong - generalised from top clubs).

**Results**
- Crystal Palace, drawing: -18.2 min, p = 0.0006, BH-adjusted 0.025 (also Bonferroni). Only survivor.
  Inspection: first tactical change at half-time in 10 of 18 drawn situations, Aug-Apr (a habit, not a
  late-season shift); mostly attacking changes, some like-for-like (possible half-time injuries).
- Arsenal, winning: 2nd smallest p (0.010) but BH-adjusted 0.21 - not a league-wide standout, as the
  README stated before the run.
- New limitation: half-time injury replacements look like tactical half-time changes (recorded in period 2).
- Better framing for Palace: a proportion ("10 of 18 at half-time") rather than "18 minutes earlier".

## 2026-10-25 - Phase 2 step 3: half-time change rate

**Done** - `fti/halftime.py` (+4 tests, 40 total); `python -m fti --league` now runs timing + half-time.
- Half-time change = first tactical sub at period 2, clock exactly 45:00.
- Per team x state: share at half-time, Wilson 95% CI, permutation test on difference in shares,
  Benjamini-Hochberg (FDR 5%), min 8 matches. Chart: results/league/figures/halftime_overview.png.
- README: league-wide section + half-time subsection; overview chart labels fixed (white background).

**Results**
- League: 23% of first tactical changes at half-time (138 of 608); winning 10%, drawing 22%, losing 35%.
  Losing managers ~3.5x as likely to change at the interval as winning ones. Descriptive, not yet tested.
- Crystal Palace, drawing: 10 of 18 (56% vs 19%), adjusted p = 0.025 - same evidence as the timing
  result (identical p), not a second confirmation. Pooled: 16 of 35 (46%), highest in league (descriptive).
- No other team survives correction (next: Man Utd drawing 46%, adjusted p = 0.79).
  Spurs (0/10) and Norwich (0/9) never changed first at half-time while drawing - not significant.

## 2026-10-25 - Phase 2 step A: double/triple changes (pre-registered)

**Done**
- `docs/analysis_plan.md` committed (c243403) BEFORE running analyses A-E: main measures fixed in advance.
- `fti/windows.py` (+5 tests, 45 total); included in `python -m fti --league`.
- Window = same team, same half, each change within 60 s of the previous; tactical, no red card before.

**Results**
- 1,816 eligible changes in 1,673 windows: 1,531 single, 141 double, 1 triple.
- 19% of team-matches had a double change; doubles earlier than singles (65.8' vs 73.4'); 78% of changes after 60'.
- Norwich City: 16 of 38 matches (42% vs 17.5%), adjusted p = 0.004 - only standout. Inspected: pairs mostly
  seconds apart, Aug-May, 9 losing / 4 drawing / 3 winning; season's only triple (v Chelsea, 72', losing).
  3 of 16 pairs 35-37 s apart; ~13 would remain under a 30 s window.
- Near-misses: Tottenham, Aston Villa 1/38 (adjusted p = 0.057). After-60' share highest: Spurs 92%, Arsenal 90%.
- Era note: 3-sub rule makes triple changes costly; modern frequency likely partly a rule effect (5 subs).
- Pending: user spot-check of one Arsenal double change (e.g. Everton, 19 Mar 2016, 74') against a match report.

## 2026-10-25 - Phase 2 step B: first vs second half intensity (pre-registered)

**Done** - `fti/halves.py` (+3 tests, 48 total); per-half totals cached in data/processed/half_stats.csv;
built-in data check; included in `python -m fti --league`.

**Results**
- Data: 9,908 shots, 971.4 xG, 115,402 pressure events, 380 matches; 0 team-matches with zero xG.
- League second-half share: xG 56.5%, shots 54.7%, pressures 49.9%. Caveat: longer second-half stoppage
  time; flat pressing implies slightly lower pressing per minute after half-time (exploratory follow-up:
  per-minute rates).
- No team stands out (adjusted p ~0.88 for all; range Southampton 50% to Sunderland 60%; Arsenal 53%).
  Pre-registered null result.

## 2026-10-25 - Phase 2 step C: pressing height after taking the lead (pre-registered)

**Done** - `fti/pressing.py` (+4 tests, 52 total); per-match results cached in data/processed/lead_pressing.csv;
coordinate + orientation checks (median shot x 107, pressure x 44); included in `python -m fti --league`.

**Results**
- 310 qualifying team-matches. League: pressing x 56.1 before lead -> 50.8 while leading;
  mean change -5.24 units (95% CI -6.66 to -3.86), ~4-5 m deeper. Robust league-wide effect.
- No team stands out (all adjusted p >= 0.82); range Newcastle -10.8 to Norwich -0.5; Arsenal -4.0.
- Caveat: score effect vs fatigue/clock not separated. Exploratory follow-up: compare pressing at the same
  minutes in matches still level.
- Link to motivating post: "retreat 5-8 metres" matches the 2015/16 typical behaviour (~4-5 m).

## Next steps (Phase 2 - in progress)
1. ~~Any-team support~~ (done 2026-10-25).
2. ~~League-wide comparison~~ (done 2026-10-25).
3. Hypotheses from the motivating post (Bop Daddy, @awoyemijoshua61), tested on 2015/16:
   - ~~final-30-minute and simultaneous (double/triple) changes~~ (step A, done 2026-10-25)
   - ~~first vs second half intensity~~ (step B, done 2026-10-25; null result)
   - ~~pressing height before vs after taking the lead~~ (step C, done 2026-10-25)
   - player-minute rotation
   - ~~half-time changes per team~~ (done 2026-10-25); possible follow-up: formal test of the
     league-wide winning/drawing/losing half-time trend
4. Survival (time-to-first-sub) model with time-varying score state.
5. Controls (opponent strength, home/away); MIT code licence; StatsBomb logo attribution.
