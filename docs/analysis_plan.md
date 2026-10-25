# Analysis plan (pre-registered)

**Written and committed on 2026-10-25, before any of the analyses below were run.**
Purpose: fix each analysis's main measure in advance, so results cannot be cherry-picked after seeing
the data. Anything reported beyond these main measures is labelled exploratory.

Common rules (unless stated otherwise)
- Data: StatsBomb Open Data, Premier League 2015/16, all 20 teams.
- Substitutions: tactical only, excluding changes made after a red card in the match (as variant D).
- Comparison: each team vs the rest of the league; Wilson 95% intervals for proportions;
  permutation tests (10,000 shuffles, seed 42); Benjamini-Hochberg correction (FDR 5%) across teams
  for the main measure only. Secondary measures are descriptive.
- Minimum sample: 8 matches per team-situation where a split by situation is used.

## A. Late and simultaneous changes ("fresh legs")
- **Window:** substitutions by the same team, in the same half, within 60 seconds of each other.
- **Main measure:** share of a team's matches with at least one double or triple change (window of 2+).
- Secondary: share of matches with a triple change; share of tactical changes made after the 60th minute.

## B. First vs second half intensity ("45-minute bursts")
- **Main measure:** per match, the team's second-half share of its own expected goals (xG),
  averaged over its matches; compared with the rest of the league.
- Secondary: the same for shots and for pressing (pressure) events.
- Caveat to report: score effects (teams that lead often attack less later).

## C. Pressing height after taking the lead
- **Main measure:** within each match where a team took the lead, the change in the median pitch
  position (x-coordinate) of its pressure events from before going ahead to while leading;
  team average vs rest of league.
- Requires a data check that pressure events with coordinates exist in this release.

## D. Rotation
- **Main measure:** share of the team's total league minutes played by its 11 most-used players.
- Secondary: number of players used; evenness of minutes (Gini coefficient).
- Descriptive ranking (one value per team; no per-team significance test).

## E. Survival model with controls
- Discrete-time (minute-by-minute) hazard model for the first tactical substitution, with score state
  updated every minute, plus home/away and opponent strength (opponent's final points from the 380 results).
- **Main question:** does Arsenal's first-change timing when winning differ from the league after these
  controls (team x winning interaction)?
