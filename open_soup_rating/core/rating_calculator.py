# Main Rating Calculator - Core OSR calculation logic
#
# Every result carries two numbers in the same unit (percentage points of a
# round won per round, 0 = average player):
#   round_swing  what happened: the win probability the player actually added
#   rating (OSR) the player's level: Round Swing combined with kills, deaths
#                and damage, weighted by how well each predicts Round Swing
#                in other matches (see core/rating_model.py)

import math
import warnings
from pathlib import Path
from statistics import NormalDist
from typing import Dict, List, Any, Optional, Union

from .component_registry import get_component, list_components
from .game_content import agent_name, agent_role
from .rounds import parse_match
from .rating_model import rating_features, rating_terms, round_swing
from .swing import compute_match_swing
from .win_probability import WinProbabilityModel, default_model
from ..data.loader import load_config_data, load_match_data
from ..utils.config import get_default_config, load_rating_params
from ..utils.validation import validate_match_data

SWING_COMPONENTS = {
    'KillSwing': 'kill',
    'AssistSwing': 'assist',
    'DeathSwing': 'death',
    'ObjectiveSwing': 'objective',
}


def _load_matches(match_data: Union[str, Path, Dict, List[Dict]]) -> List[Dict[str, Any]]:
    if isinstance(match_data, (str, Path)):
        return load_match_data(match_data)
    if isinstance(match_data, dict):
        return [match_data]
    if isinstance(match_data, list):
        return match_data
    raise ValueError("match_data must be a file path, directory path, dict, or list of dicts")


def _resolve_config(config_path: Optional[Union[str, Path]], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    config = get_default_config()
    if config_path:
        path = Path(config_path)
        if path.is_dir() and (path / 'rating_params.json').exists():
            # A calibration output directory (tools/calibrate.py --out)
            config['rating_params'] = load_rating_params(path / 'rating_params.json')
            if (path / 'wp_model.json').exists():
                config['wp_model_path'] = path / 'wp_model.json'
        else:
            config.update(load_config_data(path))
    for legacy in ('weights', 'normalization_params'):
        if kwargs.pop(legacy, None) is not None:
            warnings.warn(f"'{legacy}' is no longer used: OSR 2 weights are fitted by tools/calibrate.py "
                          "and need no normalization.", DeprecationWarning, stacklevel=3)
    return config


def _resolve_model(config: Dict[str, Any], wp_model: Optional[WinProbabilityModel]) -> WinProbabilityModel:
    if wp_model is not None:
        return wp_model
    if config.get('wp_model_path'):
        return WinProbabilityModel.load(config['wp_model_path'])
    return default_model()


def _match_components(match: Dict[str, Any], component_names: List[str], wp_model: WinProbabilityModel,
                      credit: Dict[str, Any], **kwargs) -> Dict[str, Dict[str, Any]]:
    """Compute the swing ledger once, then every requested component for each player."""
    validate_match_data(match)
    parsed = parse_match(match)
    ledger = compute_match_swing(match, wp_model, credit, parsed=parsed)
    damage_data = _extract_damage_data(match)
    match_id = match['matchInfo']['matchId']

    results = {}
    for puuid, player in parsed['players'].items():
        entry = ledger[puuid]
        if entry['rounds'] == 0:
            continue
        components = {}
        for name in component_names:
            try:
                calculator = get_component(name)
                components[name] = calculator(
                    player=player,
                    match=match,
                    damage_data=damage_data,
                    economic_data={},
                    xvx_data={},
                    swing=ledger,
                    parsed=parsed,
                    **kwargs
                )
            except Exception as e:
                warnings.warn(f"Failed to calculate {name} for {puuid}_{match_id}: {e}")
                components[name] = 0.0
        results[f"{puuid}_{match_id}"] = {'player': player, 'match_id': match_id, 'ledger': entry,
                                          'components': components}
    return results


def get_components(
    match_data: Union[str, Path, Dict, List[Dict]],
    component_names: Optional[Union[str, List[str]]] = None,
    wp_model: Optional[WinProbabilityModel] = None,
    **kwargs
) -> Dict[str, Dict[str, Any]]:
    # Get individual component values for players in match data.
    # Args:
    #     match_data: Path to match data file/directory, or loaded match data
    #     component_names: Name(s) of components to calculate (optional)
    #     wp_model: Custom win probability model (optional)
    #     **kwargs: Additional parameters for component calculations
    # Returns:
    #     Dict of player-match keys to component values
    if component_names is None:
        component_names = list_components()
    elif isinstance(component_names, str):
        component_names = [component_names]
    available = list_components()
    for name in component_names:
        if name not in available:
            raise ValueError(f"Component '{name}' not available. Available: {available}")

    config = _resolve_config(kwargs.pop('config_path', None), kwargs)
    wp_model = _resolve_model(config, wp_model)
    results = {}
    for match in _load_matches(match_data):
        for key, row in _match_components(match, component_names, wp_model, config['credit'], **kwargs).items():
            results[key] = row['components']
    return results


def _rate(row: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    entry = row['ledger']
    features = rating_features(entry)
    terms = rating_terms(features, params)
    rating = params['intercept'] + sum(terms.values())
    character_id = row['player'].get('characterId')
    role = agent_role(character_id)
    role_baseline = params['role_baselines'].get(role, 0.0) if role else 0.0
    return {
        'rating': rating,
        'role_adjusted_rating': rating - role_baseline,
        'round_swing': round_swing(entry) - params['swing_center'],
        'swing_per_round': {name: features[name] for name in SWING_COMPONENTS},
        'rating_breakdown': dict(terms, intercept=params['intercept']),
        'components': row['components'],
        'rounds_played': entry['rounds'],
        'kills': entry['kills'],
        'deaths': entry['deaths'],
        'assists': entry['assists'],
        'traded_deaths': entry['traded_deaths'],
        'first_kills': entry['first_kills'],
        'first_deaths': entry['first_deaths'],
        'kast': entry['kast'] / entry['rounds'],
        'adr': entry['damage_dealt'] / entry['rounds'],
        'agent': agent_name(character_id),
        'role': role,
        'puuid': row['player']['puuid'],
        'match_id': row['match_id'],
    }


def calculate_rating(
    match_data: Union[str, Path, Dict, List[Dict]],
    components_to_use: Optional[List[str]] = None,
    config_path: Optional[Union[str, Path]] = None,
    wp_model: Optional[WinProbabilityModel] = None,
    **kwargs
) -> Dict[str, Any]:
    # Calculate Open Soup Rating for players in match data.
    # Args:
    #     match_data: Path to match data file/directory, or loaded match data
    #     components_to_use: Components to report alongside the rating (optional)
    #     config_path: Path to custom config directory or file (optional)
    #     wp_model: Custom win probability model (optional)
    #     **kwargs: Additional parameters for component calculations
    # Returns:
    #     Dict of player-match keys to rating, swing breakdown and components
    config = _resolve_config(config_path, kwargs)
    if components_to_use is None:
        components_to_use = list_components()
    wp_model = _resolve_model(config, wp_model)

    ratings = {}
    for match in _load_matches(match_data):
        for key, row in _match_components(match, components_to_use, wp_model, config['credit'], **kwargs).items():
            ratings[key] = _rate(row, config['rating_params'])
    return ratings


def calculate_rating_with_player_info(
    match_data: Union[str, Path, Dict, List[Dict]],
    components_to_use: Optional[List[str]] = None,
    config_path: Optional[Union[str, Path]] = None,
    wp_model: Optional[WinProbabilityModel] = None,
    **kwargs
) -> Dict[str, Any]:
    # Same as calculate_rating, plus name, tag and box-score stats for each player.
    matches = _load_matches(match_data)
    ratings = calculate_rating(matches, components_to_use, config_path, wp_model, **kwargs)
    players = {}
    for match in matches:
        match_id = match['matchInfo']['matchId']
        for player in match.get('players', []):
            players[f"{player['puuid']}_{match_id}"] = player
    for key, result in ratings.items():
        player = players[key]
        stats = player.get('stats', {}) or {}
        result['player_info'] = {
            'name': player.get('gameName', 'Unknown'),
            'tagline': player.get('tagLine', 'Unknown'),
            'kills': stats.get('kills', 0),
            'deaths': stats.get('deaths', 0),
            'assists': stats.get('assists', 0),
            'rounds_played': stats.get('roundsPlayed', 0),
        }
    return ratings


def aggregate_ratings(ratings: Dict[str, Any], config_path: Optional[Union[str, Path]] = None,
                      role_adjusted: bool = False, interval: float = 0.9) -> Dict[str, Any]:
    """
    Combine per-match ratings into one rating per player, shrunk toward the
    average in proportion to how few rounds they have played.

    A single map is mostly noise; the shrinkage constant (prior_rounds) is the
    number of rounds at which a player's own record and the population average
    get equal weight. Returns {puuid: {...}} with the raw per-round average,
    the shrunk rating and a credible interval.
    """
    params = _resolve_config(config_path, {})['rating_params']
    sigma2 = params['shrinkage']['round_variance']
    tau2 = params['shrinkage']['true_variance']
    z = _normal_quantile(0.5 + interval / 2)

    totals: Dict[str, Dict[str, Any]] = {}
    for result in ratings.values():
        value = result['role_adjusted_rating'] if role_adjusted else result['rating']
        t = totals.setdefault(result['puuid'], {'rounds': 0, 'weighted': 0.0, 'maps': 0, 'roles': {}})
        t['rounds'] += result['rounds_played']
        t['weighted'] += value * result['rounds_played']
        t['maps'] += 1
        if result.get('role'):
            t['roles'][result['role']] = t['roles'].get(result['role'], 0) + result['rounds_played']
        if 'player_info' in result:
            t['name'] = f"{result['player_info']['name']}#{result['player_info']['tagline']}"

    out = {}
    for puuid, t in totals.items():
        n = t['rounds']
        precision = n / sigma2 + 1.0 / tau2
        shrunk = (t['weighted'] / sigma2) / precision
        sd = math.sqrt(1.0 / precision)
        out[puuid] = {
            'name': t.get('name'),
            'maps': t['maps'],
            'rounds_played': n,
            'raw_rating': t['weighted'] / n if n else 0.0,
            'rating': shrunk,
            'rating_low': shrunk - z * sd,
            'rating_high': shrunk + z * sd,
            'main_role': max(t['roles'], key=t['roles'].get) if t['roles'] else None,
        }
    return out


def _normal_quantile(p: float) -> float:
    return NormalDist().inv_cdf(p)


def _extract_damage_data(match: Dict) -> Dict[str, int]:
    # Total damage dealt by each player over the match.
    damage_data: Dict[str, int] = {}
    for round_result in match.get('roundResults', []) or []:
        for player_stat in round_result.get('playerStats', []) or []:
            puuid = player_stat['puuid']
            for event in player_stat.get('damage', []) or []:
                if isinstance(event, dict) and 'damage' in event:
                    damage_data[puuid] = damage_data.get(puuid, 0) + event['damage']
    return damage_data
