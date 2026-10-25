"""Tests for team-name resolution and folder names (no real data needed)."""
import pytest

from fti.teams import resolve_team, team_slug

TEAMS = ["Arsenal", "Leicester City", "Manchester United", "Tottenham Hotspur", "West Ham United"]


def test_exact_and_case_insensitive_names_resolve():
    assert resolve_team("Arsenal", TEAMS) == "Arsenal"
    assert resolve_team("  leicester CITY ", TEAMS) == "Leicester City"


def test_common_aliases_resolve():
    assert resolve_team("Spurs", TEAMS) == "Tottenham Hotspur"
    assert resolve_team("man  utd", TEAMS) == "Manchester United"
    assert resolve_team("Leicester", TEAMS) == "Leicester City"


def test_partial_name_without_alias_gives_a_suggestion():
    with pytest.raises(ValueError, match="Did you mean: Tottenham Hotspur"):
        resolve_team("Hotspur", TEAMS)


def test_misspelling_gives_a_suggestion():
    with pytest.raises(ValueError, match="Did you mean: Arsenal"):
        resolve_team("Arsnal", TEAMS)


def test_unknown_team_points_to_list_teams():
    with pytest.raises(ValueError, match="--list-teams"):
        resolve_team("Real Madrid", TEAMS)


def test_team_slug_is_folder_safe():
    assert team_slug("Leicester City") == "leicester-city"
    assert team_slug("AFC Bournemouth") == "afc-bournemouth"
