"""Phase 0 check: what does a StatsBomb substitution record look like?

Inspects Arsenal's first 2015/16 league match (v West Ham, 2015-08-09):
prints its substitutions and goals so we can verify them against a public match report.
"""
from statsbombpy import sb

# Find the 2015/16 Premier League season (looked up, not hard-coded)
comps = sb.competitions()
season = comps[(comps["competition_name"] == "Premier League")
               & (comps["season_name"] == "2015/2016")].iloc[0]
matches = sb.matches(competition_id=season["competition_id"], season_id=season["season_id"])
arsenal = matches[(matches["home_team"] == "Arsenal") | (matches["away_team"] == "Arsenal")]
match = arsenal.sort_values("match_date").iloc[0]
print(f"Match {match['match_id']}: {match['home_team']} {match['home_score']}-"
      f"{match['away_score']} {match['away_team']} ({match['match_date']})")

# Download every event in that match (passes, shots, substitutions, ...)
events = sb.events(match_id=int(match["match_id"]))
print(f"\nEvents in this match: {len(events)}  |  columns: {len(events.columns)}")
order = ["period", "minute", "second"]

# Substitutions
subs = events[events["type"] == "Substitution"].sort_values(order)
sub_cols = [c for c in order + ["team", "player", "position",
            "substitution_replacement", "substitution_outcome"] if c in events.columns]
print(f"\nSubstitutions ({len(subs)}):")
print(subs[sub_cols].to_string(index=False))

# Goals: normal goals are shots with outcome 'Goal'; own goals are separate event types
goals = events[(events.get("shot_outcome") == "Goal") | (events["type"] == "Own Goal For")]
print(f"\nGoals ({len(goals)}):")
print(goals.sort_values(order)[order + ["team", "player", "type"]].to_string(index=False))

# One full substitution record, for the data dictionary
print("\nOne complete substitution record (non-empty fields only):")
for field, value in subs.iloc[0].dropna().items():
    print(f"  {field}: {value}")
