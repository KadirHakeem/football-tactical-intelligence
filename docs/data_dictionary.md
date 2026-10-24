# Data dictionary

Source: StatsBomb Open Data, Premier League 2015/16 (competition and season IDs are looked up at runtime by name, not hard-coded).
Coverage verified 2026-10-24: **380 matches**, **38 Arsenal matches**.

## Substitution events (`type == "Substitution"`)

| Field | Example | Meaning / notes |
|---|---|---|
| `match_id` | 3754141 | StatsBomb match identifier |
| `team` / `team_id` | Arsenal / 1 | Team **making** the substitution |
| `period` | 2 | 1 = first half, 2 = second half (extra time not used in league play) |
| `minute`, `second` | 57, 40 | **Elapsed** match clock (period 2 continues from 45:00). See conventions below |
| `timestamp` | 00:12:40.261 | Time since the **start of the period** (here 45:00 + 12:40 = 57:40) |
| `player` / `player_id` | Francis Joseph Coquelin / 3437 | Player going **off** (full legal name) |
| `position` | Left Defensive Midfield | Position of the player going off at that moment |
| `substitution_replacement` / `_id` | Theo Walcott / 3668 | Player coming **on** |
| `substitution_outcome` | Tactical | `Tactical` or `Injury` - used to separate manager choices from forced changes |
| `possession_team` | West Ham United | Team in possession when the change happened |
| `index` | 2184 | Event order within the match; used to break ties |

## Goal events (used to rebuild the score at any moment)

| Source | Rule |
|---|---|
| Normal goals | `type == "Shot"` and `shot_outcome == "Goal"`, credited to `team` |
| Own goals | `type == "Own Goal For"` (credited to the benefiting team) |

## Conventions

- **Minute convention:** StatsBomb `minute` is elapsed time (42:50 means minute 42). Match reports use the minute being played (43'). Report minute = `minute + 1`. Charts will state which convention is used.
- **Score at substitution:** computed from all goals with an earlier (`period`, `minute`, `second`, `index`) than the substitution. Close goal-substitution pairs are checked explicitly.
- **Names:** event data uses full legal names; display names will come from lineup data (`player_nickname`) where available.

## Verified sample records

Arsenal 0-2 West Ham United, 2015-08-09 (match 3754141), checked against a public match report on 2026-10-24:

| Clock | Event | Report |
|---|---|---|
| 42:50 | Goal - Kouyaté (West Ham) | 43' |
| 56:27 | Goal - Zárate (West Ham) | 57' |
| 57:40 | Arsenal sub - Coquelin off, Walcott on (Tactical) | 58' |
| 62:14 | West Ham sub - Zárate off, Jarvis on (Tactical) | 63' |
| 66:34 | Arsenal sub - Debuchy off, Alexis Sánchez on (Tactical) | 67' |
| 78:44 | West Ham sub - Oxford off, Nolan on (Tactical) | 79' |
| 89:10 | West Ham sub - Sakho off, Maïga on (Tactical) | 90' |
