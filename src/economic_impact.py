import json
from typing import Dict, Tuple

def load_economic_data(economic_json_path: str) -> Dict[str, Dict[str, float]]:
    # Load the economic win rates from the JSON.
    # Returns a dict of category matchup to win_rate.
    with open(economic_json_path, 'r') as f:
        data = json.load(f)
    return data['economy_categories']

def categorize_economy(total_loadout: int) -> str:
    # Categorize the total team loadout into economy categories.
    if total_loadout <= 1500:
        return "Save Round"
    elif total_loadout <= 4000:
        return "Eco Round"
    elif total_loadout <= 7500:
        return "Force Buy"
    elif total_loadout <= 10000:
        return "Anti-Eco"
    elif total_loadout <= 15000:
        return "Full Buy"
    else:
        return "Operator Buy"

def get_economic_modifier(killer_team_loadout: int, victim_team_loadout: int, economic_data: Dict[str, Dict[str, float]]) -> float:
    # Get the economic modifier for a kill.
    # Returns the modifier to multiply the kill impact by.
    killer_cat = categorize_economy(killer_team_loadout)
    victim_cat = categorize_economy(victim_team_loadout)
    matchup = f"{killer_cat} vs {victim_cat}"
    if matchup in economic_data:
        win_rate = economic_data[matchup]['win_rate']
    else:
        raise ValueError(f"Win rate not found for matchup: {matchup}. Check economic data.")
    
    # Modifier: 2 * (1 - win_rate)
    # If win_rate = 0.5, modifier = 1 (no change)
    # If win_rate < 0.5, modifier > 1 (killer disadvantage, bonus)
    # If win_rate > 0.5, modifier < 1 (killer advantage, penalty)
    modifier = 2 * (1 - win_rate)
    return modifier

def get_death_economic_modifier(victim_team_loadout: int, killer_team_loadout: int, economic_data: Dict[str, Dict[str, float]]) -> float:
    # Get the economic modifier for a death.
    # For death, it's the same as kill but swapped.
    return get_economic_modifier(killer_team_loadout, victim_team_loadout, economic_data)
