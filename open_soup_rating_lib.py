import json
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data_loader import load_match_data, extract_damage_data
from economic_impact import load_economic_data
from xvx_impact import load_xvx_data
from rating_calculator import calculate_components
from typing import Dict

def calculate_open_soup_ratings(match_json_path: str) -> Dict[str, float]:
    # Calculate Open Soup Rating for all players in a single match.
    #
    # Args:
    #     match_json_path: Path to the match JSON file
    #
    # Returns:
    #     Dict mapping player PUUIDs to their Open Soup Rating
    #
    # Note: Requires 'loadout_cost_analysis.json', 'xvx_breakdown_data.json',
    # and 'weights.json' to be present in the project root.
    # Load the single match
    with open(match_json_path, 'r') as f:
        match_data = json.load(f)
    
    # Wrap in list for compatibility with existing functions
    matches = [match_data]
    
    # Load required data files
    economic_data = load_economic_data('loadout_cost_analysis.json')
    xvx_data = load_xvx_data('xvx_breakdown_data.json')
    damage_data = extract_damage_data(matches)
    
    # Calculate components for the match
    components = calculate_components(matches, economic_data, xvx_data, damage_data)
    
    # Load pre-fitted weights
    weights_path = 'weights.json'
    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"Weights file not found: {weights_path}. Please run the training process first.")
    
    with open(weights_path, 'r') as f:
        weights = json.load(f)
    
    # Calculate ratings for each player
    ratings = {}
    for comp in components:
        puuid = comp['puuid']
        # Raw weighted sum (not scaled to VLR distribution for single match)
        rating = (weights[0] * comp['KillContrib'] + 
                  weights[1] * comp['DeathContrib'] + 
                  weights[2] * comp['APR'] + 
                  weights[3] * comp['ADRa'])
        ratings[puuid] = rating
    
    return ratings

# Example usage
if __name__ == "__main__":
    # Example: calculate ratings for a match
    match_file = "sample_data/Invite/Stage E9A1-Premier-Invite/0022f59f-595f-4d38-a176-65aff294aa7a_na_v2_riot_match_data.json"
    if os.path.exists(match_file):
        ratings = calculate_open_soup_ratings(match_file)
        print("Player Ratings:")
        for puuid, rating in ratings.items():
            print(f"{puuid}: {rating:.4f}")
    else:
        print("Example match file not found. Please provide a valid match JSON path.")
