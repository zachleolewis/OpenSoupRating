from typing import Dict

def calculate_adra(total_damage: int, expected_total: float, rounds: int) -> float:
    # Calculate Adjusted Damage per Round by subtracting expected damage from kills.
    # expected_total is the sum of expected damage for each kill based on victim's armor.
    if rounds == 0:
        return 0
    adra = (total_damage - expected_total) / rounds
    return max(0, adra)  # Ensure non-negative
