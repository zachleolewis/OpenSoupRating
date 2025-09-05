# Average Performance Rating (APR) Component Calculator

from typing import Dict, Any

def calculate_apr(
    player: Dict[str, Any],
    match: Dict[str, Any],
    damage_data: Dict[str, int],
    economic_data: Dict[str, Any],
    xvx_data: Dict[str, Any],
    **kwargs
) -> float:
    # Calculate Average Performance Rating for a player in a match.
    # APR is calculated as: assists / rounds_played (not kills + assists)
    # Args:
    #     player: Player data dictionary
    #     match: Match data dictionary
    #     damage_data: Damage data for all players (unused for APR)
    #     economic_data: Economic data (unused for APR)
    #     xvx_data: XvX impact data (unused for APR)
    #     **kwargs: Additional parameters
    # Returns:
    #     APR value

    stats = player.get('stats')
    if stats is None:
        return 0.0

    rounds_played = stats.get('roundsPlayed', 0)
    if rounds_played == 0:
        return 0.0

    assists = stats.get('assists', 0)

    apr = assists / rounds_played
    return apr
