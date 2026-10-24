"""Phase 0 check: does StatsBomb Open Data cover Arsenal's 2015/16 Premier League season?"""
from statsbombpy import sb

# 1. Which Premier League seasons are in the open data?
comps = sb.competitions()
epl = comps[comps["competition_name"] == "Premier League"]
print("Premier League seasons in StatsBomb Open Data:")
print(epl[["competition_id", "season_id", "season_name"]].to_string(index=False))

# 2. Load every 2015/16 match and keep Arsenal's
season = epl[epl["season_name"] == "2015/2016"].iloc[0]
matches = sb.matches(competition_id=season["competition_id"], season_id=season["season_id"])
arsenal = matches[(matches["home_team"] == "Arsenal") | (matches["away_team"] == "Arsenal")]

print(f"\nTotal 2015/16 matches: {len(matches)}")
print(f"Arsenal matches: {len(arsenal)}")
print("\nFirst five Arsenal matches:")
cols = ["match_date", "home_team", "away_team", "home_score", "away_score"]
print(arsenal[cols].sort_values("match_date").head().to_string(index=False))
