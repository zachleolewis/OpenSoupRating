from typing import Dict

def calculate_apr(stats: Dict) -> float:
    # Calculate Assists Per Round.
    assists = stats.get('assists', 0)
    rounds = stats.get('roundsPlayed', 1)
    return assists / rounds
