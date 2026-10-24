# Football Tactical Intelligence

Identifying, quantifying and comparing football managers' **observable** tactical decisions, starting with substitutions, using public event data, transparent statistics and (later) carefully validated machine learning.

> **Status:** Phase 0 (feasibility) complete. Phase 1 (reproducible substitution analytics) next. See [PROGRESS.md](PROGRESS.md).

## Research question (MVP)

> In the 2015/16 Premier League, how did the timing of Arsenal's first substitution vary by score state (winning / drawing / losing) at the moment of the change, and how does that compare with the league-wide distribution?

Scope and principles:
- **Sample:** all 38 Arsenal league matches of 2015/16 (Arsène Wenger), benchmarked against all 380 matches of the same season.
- **Observed facts vs. interpretation:** the project reports what the data shows (who, when, at what score). It does not claim to know a manager's intentions, and makes no causal claims ("this substitution won the game") without a defensible causal design.
- **Tactical vs. injury substitutions** are analysed separately where the data distinguishes them.
- Small samples are reported with uncertainty intervals, not as precise facts.

## Data

Data: **StatsBomb Open Data** (Hudl StatsBomb), 2015/16 Premier League, accessed via the official [`statsbombpy`](https://github.com/statsbomb/statsbombpy) package.

- Use is subject to the [StatsBomb Open Data user agreement](https://github.com/statsbomb/open-data). Raw StatsBomb data is **not** redistributed in this repository; it is downloaded at runtime.
- Field definitions and conventions: [docs/data_dictionary.md](docs/data_dictionary.md).

<!-- TODO: add the StatsBomb logo from their media pack, as the open-data terms request. -->

## Reproduce

Requires Python 3.12 (Windows commands shown).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Phase 0 checks
python scripts\check_data_coverage.py      # confirms 380 matches / 38 Arsenal matches
python scripts\inspect_substitutions.py    # sample substitution + goal records
```

## Project structure

```
football-tactical-intelligence/
├── docs/data_dictionary.md   # fields, definitions, conventions
├── scripts/                  # Phase 0 feasibility checks
├── PROGRESS.md               # progress log and next steps
├── requirements.txt          # pinned dependencies
└── README.md
```

## Roadmap

0. Feasibility & setup (done)
1. Reproducible Arsenal substitution analytics
2. Manager comparisons across the league; careful ML only where justified
3. Automated short analysis videos from the same pipeline
4. Portfolio polish
