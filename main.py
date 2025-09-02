import os
import sys
sys.path.append('src')

from rating_calculator import calculate_components
from data_loader import load_match_data, extract_damage_data
from economic_impact import load_economic_data
from xvx_impact import load_xvx_data
import json

if __name__ == "__main__":
    # Load data
    print("Loading data...")
    matches = load_match_data('sample_data')
    economic_data = load_economic_data('loadout_cost_analysis.json')
    xvx_data = load_xvx_data('xvx_breakdown_data.json')
    damage_data = extract_damage_data(matches)
    
    print(f"Loaded {len(matches)} matches")
    
    # Calculate components
    print("Calculating components...")
    components = calculate_components(matches, economic_data, xvx_data, damage_data)
    
    # Save components
    with open('components.json', 'w') as f:
        json.dump(components, f)
    
    print(f"Calculated components for {len(components)} player-matches")
    
    print("Done!")
