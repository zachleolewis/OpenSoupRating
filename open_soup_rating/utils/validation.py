# Data Validation Utilities

from typing import Dict, Any, List

def validate_match_data(match: Dict[str, Any]) -> None:
    # Validate match data structure.
    # Args:
    #     match: Match data dictionary
    # Raises:
    #     ValueError: If match data is invalid
    required_keys = ['matchInfo', 'players', 'roundResults']
    for key in required_keys:
        if key not in match:
            raise ValueError(f"Match data missing required key: {key}")

    # Validate matchInfo
    match_info = match['matchInfo']
    if 'matchId' not in match_info:
        raise ValueError("matchInfo missing matchId")

    # Validate players
    players = match['players']
    if not isinstance(players, list):
        raise ValueError("players must be a list")

    for i, player in enumerate(players):
        required_player_keys = ['puuid', 'teamId', 'stats']
        for key in required_player_keys:
            if key not in player:
                raise ValueError(f"Player {i} missing required key: {key}")

    # Validate roundResults
    round_results = match['roundResults']
    if not isinstance(round_results, list):
        raise ValueError("roundResults must be a list")

def validate_component_data(component_data: Dict[str, Any]) -> None:
    # Validate component calculation data.
    # Args:
    #     component_data: Component data dictionary
    # Raises:
    #     ValueError: If component data is invalid
    if not isinstance(component_data, dict):
        raise ValueError("Component data must be a dictionary")

    # Check for required component keys
    expected_components = ['KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing', 'HoldSwing']
    for comp in expected_components:
        if comp not in component_data:
            print(f"Warning: Missing component {comp}")
