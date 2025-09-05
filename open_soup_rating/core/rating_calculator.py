# Main Rating Calculator - Core OSR calculation logic

import json
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from .component_registry import get_component, list_components
from ..data.loader import load_config_data
from ..utils.config import get_default_config
from ..utils.validation import validate_match_data

def calculate_rating(
    match_data: Union[str, Path, Dict, List[Dict]],
    weights: Optional[Dict[str, float]] = None,
    normalization_params: Optional[Dict[str, Dict[str, float]]] = None,
    components_to_use: Optional[List[str]] = None,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs
) -> Dict[str, Any]:
    # Calculate Open Soup Rating for players in match data.
    # Args:
    #     match_data: Path to match data file/directory, or loaded match data
    #     weights: Custom weights for components (optional)
    #     normalization_params: Custom normalization parameters (optional)
    #     components_to_use: List of components to include (optional)
    #     config_path: Path to custom config directory (optional)
    #     **kwargs: Additional parameters for component calculations
    # Returns:
    #     Dict containing ratings and component data for each player-match

    # Load configuration
    config = get_default_config()
    if config_path:
        config.update(load_config_data(config_path))

    # Load match data
    if isinstance(match_data, (str, Path)):
        from ..data.loader import load_match_data
        matches = load_match_data(match_data)
    elif isinstance(match_data, dict):
        matches = [match_data]
    elif isinstance(match_data, list):
        matches = match_data
    else:
        raise ValueError("match_data must be a file path, directory path, dict, or list of dicts")

    # Validate match data
    for match in matches:
        validate_match_data(match)

    # Load weights and normalization params
    if weights is None:
        weights = config.get('weights', {})
    if normalization_params is None:
        normalization_params = config.get('normalization_params', {})

    # Determine components to use
    if components_to_use is None:
        components_to_use = list_components()

    # Calculate components for all players
    components_data = get_components(match_data, components_to_use, **kwargs)

    # Calculate final ratings
    ratings = {}

    for player_key, player_components in components_data.items():
        # Apply normalization
        normalized_components = {}
        weighted_components = {}

        # Special handling for KillContrib and DeathContrib as a balanced pair
        if 'KillContrib' in player_components and 'DeathContrib' in player_components:
            kill_raw = player_components['KillContrib']
            death_raw = player_components['DeathContrib']
            
            # Combine into net impact
            net_impact = kill_raw + death_raw
            
            # Use KillContrib's normalization parameters for the net impact
            if 'KillContrib' in normalization_params:
                kill_mean = normalization_params['KillContrib']['mean']
                kill_std = normalization_params['KillContrib']['std']
                death_mean = normalization_params['DeathContrib']['mean']
                
                # Normalize the net impact
                net_normalized = (net_impact - (kill_mean + death_mean)) / kill_std
                normalized_components['KillContrib_norm'] = net_normalized / 2
                normalized_components['DeathContrib_norm'] = net_normalized / 2
                
                # Apply weighting
                if 'KillContrib' in weights:
                    weighted_components['KillContrib_weighted'] = weights['KillContrib'] * normalized_components['KillContrib_norm']
                if 'DeathContrib' in weights:
                    weighted_components['DeathContrib_weighted'] = weights['DeathContrib'] * normalized_components['DeathContrib_norm']
                
                print(f"DEBUG: {player_key} - Kill: {kill_raw:.3f}, Death: {death_raw:.3f}, Net: {net_impact:.3f}, Net_norm: {net_normalized:.3f}")
        
        # Handle other components normally
        for comp_name in components_to_use:
            if comp_name not in ['KillContrib', 'DeathContrib']:  # Skip if already handled
                if comp_name in player_components and comp_name in normalization_params:
                    raw_value = player_components[comp_name]
                    mean = normalization_params[comp_name]['mean']
                    std = normalization_params[comp_name]['std']

                    # Z-score normalization
                    normalized = (raw_value - mean) / std
                    normalized_components[f'{comp_name}_norm'] = normalized

                    # Apply weighting
                    if comp_name in weights:
                        weighted = weights[comp_name] * normalized
                        weighted_components[f'{comp_name}_weighted'] = weighted

        # Calculate weighted sum
        weighted_sum = sum(weighted_components.values())

        # Apply scaling using values from normalization_params
        final_rating_params = normalization_params.get('final_rating', {})
        scaling_factor = final_rating_params.get('scaling_factor', 1.0)
        base_rating = final_rating_params.get('base_rating', 0.0)
        pre_normalized_rating = base_rating + scaling_factor * weighted_sum

        # Apply final normalization to achieve mean=0, std=1
        current_mean = final_rating_params.get('mean', 0.0)
        current_std = final_rating_params.get('std', 1.0)
        rating = (pre_normalized_rating - current_mean) / current_std

        # Store results
        ratings[player_key] = {
            'rating': rating,
            'components': player_components,
            'normalized_components': normalized_components,
            'weighted_components': weighted_components,
            'weighted_sum': weighted_sum,
            'pre_normalized_rating': pre_normalized_rating,
            'scaling_factor': scaling_factor,
            'base_rating': base_rating
        }

    return ratings

def get_components(
    match_data: Union[str, Path, Dict, List[Dict]],
    component_names: Optional[Union[str, List[str]]] = None,
    **kwargs
) -> Dict[str, Dict[str, Any]]:
    # Get individual component values for players in match data.
    # Args:
    #     match_data: Path to match data file/directory, or loaded match data
    #     component_names: Name(s) of components to calculate (optional)
    #     **kwargs: Additional parameters for component calculations
    # Returns:
    #     Dict of player-match keys to component values

    # Load match data
    if isinstance(match_data, (str, Path)):
        from ..data.loader import load_match_data
        matches = load_match_data(match_data)
    elif isinstance(match_data, dict):
        matches = [match_data]
    elif isinstance(match_data, list):
        matches = match_data
    else:
        raise ValueError("match_data must be a file path, directory path, dict, or list of dicts")

    # Determine components to calculate
    if component_names is None:
        component_names = list_components()
    elif isinstance(component_names, str):
        component_names = [component_names]

    # Validate components exist
    available_components = list_components()
    for comp_name in component_names:
        if comp_name not in available_components:
            raise ValueError(f"Component '{comp_name}' not available. Available: {available_components}")

    # Calculate components
    results = {}

    for match in matches:
        match_id = match['matchInfo']['matchId']

        # Calculate required data (damage, economic, xvx)
        damage_data = _extract_damage_data(match)
        economic_data = _load_economic_data()
        xvx_data = _load_xvx_data()

        for player in match.get('players', []):
            if player.get('isObserver', False):
                continue

            puuid = player['puuid']
            player_key = f"{puuid}_{match_id}"

            player_components = {}

            for comp_name in component_names:
                try:
                    calculator = get_component(comp_name)
                    component_value = calculator(
                        player=player,
                        match=match,
                        damage_data=damage_data,
                        economic_data=economic_data,
                        xvx_data=xvx_data,
                        **kwargs
                    )
                    player_components[comp_name] = component_value
                except Exception as e:
                    print(f"Warning: Failed to calculate {comp_name} for {player_key}: {e}")
                    player_components[comp_name] = 0.0

            results[player_key] = player_components

    return results

def _extract_damage_data(match: Dict) -> Dict[str, int]:
    # Extract damage data from match.
    damage_data = {}
    for player in match.get('players', []):
        puuid = player['puuid']
        total_damage = 0

        # Sum damage from all rounds
        for round_result in match.get('roundResults', []):
            for player_stat in round_result.get('playerStats', []):
                if player_stat['puuid'] == puuid:
                    damage_events = player_stat.get('damage', [])
                    if isinstance(damage_events, list):
                        # Sum all damage amounts from the list
                        for damage_event in damage_events:
                            if isinstance(damage_event, dict) and 'damage' in damage_event:
                                total_damage += damage_event['damage']
                    elif isinstance(damage_events, (int, float)):
                        # Handle case where damage is already a number
                        total_damage += damage_events

        damage_data[puuid] = total_damage
    return damage_data

def _load_economic_data() -> Dict:
    # Load economic data.
    try:
        import json
        from pathlib import Path
        data_path = Path(__file__).parent.parent.parent / 'data' / 'loadout_cost_analysis.json'
        with open(data_path, 'r') as f:
            data = json.load(f)
        return data  # Return full data structure for components
    except FileNotFoundError:
        print(f"Warning: Could not load economic data from {data_path}")
        return {}

def _load_xvx_data() -> Dict:
    # Load XvX data.
    try:
        import json
        from pathlib import Path
        data_path = Path(__file__).parent.parent.parent / 'data' / 'xvx_data.json'
        with open(data_path, 'r') as f:
            data = json.load(f)
        return data  # Return full data structure for components
    except FileNotFoundError:
        # Fallback to old location
        data_path = Path(__file__).parent.parent.parent / 'xvx_breakdown_data.json'
        with open(data_path, 'r') as f:
            data = json.load(f)
        return data  # Return full data structure for components

def calculate_rating_with_player_info(
    match_data: Union[str, Path, Dict, List[Dict]],
    weights: Optional[Dict[str, float]] = None,
    normalization_params: Optional[Dict[str, Dict[str, float]]] = None,
    components_to_use: Optional[List[str]] = None,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs
) -> Dict[str, Any]:
    # Calculate Open Soup Rating with detailed player information.
    # Args:
    #     match_data: Path to match data file/directory, or loaded match data
    #     weights: Custom weights for components (optional)
    #     normalization_params: Custom normalization parameters (optional)
    #     components_to_use: List of components to include (optional)
    #     config_path: Path to custom config directory (optional)
    #     **kwargs: Additional parameters for component calculations
    # Returns:
    #     Dict containing ratings, component data, and player info for each player-match

    # Load configuration
    config = get_default_config()
    if config_path:
        config.update(load_config_data(config_path))

    # Load match data
    if isinstance(match_data, (str, Path)):
        from ..data.loader import load_match_data
        matches = load_match_data(match_data)
    elif isinstance(match_data, dict):
        matches = [match_data]
    elif isinstance(match_data, list):
        matches = match_data
    else:
        raise ValueError("match_data must be a file path, directory path, dict, or list of dicts")

    # Validate match data
    for match in matches:
        validate_match_data(match)

    # Load weights and normalization params
    if weights is None:
        weights = config.get('weights', {})
    if normalization_params is None:
        normalization_params = config.get('normalization_params', {})

    # Determine components to use
    if components_to_use is None:
        components_to_use = list_components()

    # Calculate components for all players
    components_data = get_components(match_data, components_to_use, **kwargs)

    # Calculate final ratings with player info
    ratings = {}

    for match in matches:
        match_id = match['matchInfo']['matchId']

        for player in match.get('players', []):
            if player.get('isObserver', False):
                continue

            puuid = player['puuid']
            player_key = f"{puuid}_{match_id}"

            if player_key not in components_data:
                continue

            player_components = components_data[player_key]

            # Apply normalization
            normalized_components = {}
            weighted_components = {}

            # Special handling for KillContrib and DeathContrib as a balanced pair
            if 'KillContrib' in player_components and 'DeathContrib' in player_components:
                kill_raw = player_components['KillContrib']
                death_raw = player_components['DeathContrib']
                
                # Combine into net impact
                net_impact = kill_raw + death_raw
                
                # Use KillContrib's normalization parameters for the net impact
                if 'KillContrib' in normalization_params:
                    kill_mean = normalization_params['KillContrib']['mean']
                    kill_std = normalization_params['KillContrib']['std']
                    death_mean = normalization_params['DeathContrib']['mean']
                    
                    # Normalize the net impact
                    net_normalized = (net_impact - (kill_mean + death_mean)) / kill_std
                    normalized_components['KillContrib_norm'] = net_normalized / 2
                    normalized_components['DeathContrib_norm'] = net_normalized / 2
                    
                    # Apply weighting
                    if 'KillContrib' in weights:
                        weighted_components['KillContrib_weighted'] = weights['KillContrib'] * normalized_components['KillContrib_norm']
                    if 'DeathContrib' in weights:
                        weighted_components['DeathContrib_weighted'] = weights['DeathContrib'] * normalized_components['DeathContrib_norm']
            
            # Handle other components normally
            for comp_name in components_to_use:
                if comp_name not in ['KillContrib', 'DeathContrib']:  # Skip if already handled
                    if comp_name in player_components and comp_name in normalization_params:
                        raw_value = player_components[comp_name]
                        mean = normalization_params[comp_name]['mean']
                        std = normalization_params[comp_name]['std']

                        # Z-score normalization
                        normalized = (raw_value - mean) / std
                        normalized_components[f'{comp_name}_norm'] = normalized

                        # Apply weighting
                        if comp_name in weights:
                            weighted = weights[comp_name] * normalized
                            weighted_components[f'{comp_name}_weighted'] = weighted

            # Calculate weighted sum
            weighted_sum = sum(weighted_components.values())

            # Apply scaling using values from normalization_params
            final_rating_params = normalization_params.get('final_rating', {})
            scaling_factor = final_rating_params.get('scaling_factor', 1.0)
            base_rating = final_rating_params.get('base_rating', 0.0)
            pre_normalized_rating = base_rating + scaling_factor * weighted_sum

            # Apply final normalization to achieve mean=0, std=1
            current_mean = final_rating_params.get('mean', 0.0)
            current_std = final_rating_params.get('std', 1.0)
            rating = (pre_normalized_rating - current_mean) / current_std

            # Extract player information
            player_stats = player.get('stats', {})
            player_info = {
                'name': player.get('gameName', 'Unknown'),
                'tagline': player.get('tagLine', 'Unknown'),
                'kills': player_stats.get('kills', 0),
                'deaths': player_stats.get('deaths', 0),
                'assists': player_stats.get('assists', 0),
                'rounds_played': player_stats.get('roundsPlayed', 0)
            }

            # Store results with player info
            ratings[player_key] = {
                'rating': rating,
                'player_info': player_info,
                'components': player_components,
                'normalized_components': normalized_components,
                'weighted_components': weighted_components,
                'weighted_sum': weighted_sum,
                'pre_normalized_rating': pre_normalized_rating,
                'scaling_factor': scaling_factor,
                'base_rating': base_rating,
                'match_id': match_id
            }

    return ratings
