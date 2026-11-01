# Main Rating Calculator - Core OSR calculation logic
#
# OSR is the player's Round Swing per round: the round win probability they
# added or cost their team, in percentage points of a round per round played,
# with 0 = average. The ledger accounts for every change in win probability,
# so a team's ratings add up to its round results relative to where each round
# started. Ratings for a map, a series or a season are the same quantity over
# more rounds.

import math
import warnings
from pathlib import Path
from statistics import NormalDist
from typing import Dict, List, Any, Optional, Union

from .component_registry import get_component, list_components
from .game_content import agent_name, agent_role
from .rounds import parse_match
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
    'HoldSwing': 'hold',
}

# Maps of one series: the same two rosters (4 of 5 players each) starting within this long of the previous map.
SERIES_GAP_MS = 3 * 60 * 60 * 1000
SERIES_MIN_OVERLAP = 4


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
            warnings.warn(f"'{legacy}' is no longer used: OSR 2 is Round Swing per round and "
                          "needs no weights or normalization.", DeprecationWarning, stacklevel=3)
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
    info = match['matchInfo']
    match_id = info['matchId']

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
        results[f"{puuid}_{match_id}"] = {
            'player': player, 'match_id': match_id, 'ledger': entry, 'components': components,
            'team': player['teamId'], 'map_id': info.get('mapId'), 'game_start': info.get('gameStartMillis'),
        }
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
    rounds = entry['rounds']
    swing = {name: 100.0 * entry[kind] / rounds for name, kind in SWING_COMPONENTS.items()}
    rating = sum(swing.values())
    character_id = row['player'].get('characterId')
    role = agent_role(character_id)
    role_baseline = params['role_baselines'].get(role, 0.0) if role else 0.0
    return {
        'rating': rating,
        'role_adjusted_rating': rating - role_baseline,
        'rounds_added': rating * rounds / 100.0,
        'swing_per_round': swing,
        'components': row['components'],
        'rounds_played': rounds,
        'kills': entry['kills'],
        'deaths': entry['deaths'],
        'assists': entry['assists'],
        'traded_deaths': entry['traded_deaths'],
        'first_kills': entry['first_kills'],
        'first_deaths': entry['first_deaths'],
        'plants': entry['plants'],
        'defuses': entry['defuses'],
        'kast': entry['kast'] / rounds,
        'adr': entry['damage_dealt'] / rounds,
        'agent': agent_name(character_id),
        'role': role,
        'puuid': row['player']['puuid'],
        'team': row['team'],
        'match_id': row['match_id'],
        'map_id': row['map_id'],
        'game_start': row['game_start'],
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


def find_series(ratings: Dict[str, Any]) -> Dict[str, str]:
    """
    Group maps into series: {match_id: series_id}.

    Two maps belong to the same series when both rosters match (at least 4 of
    5 players on each side) and the later map starts within 3 hours of the
    previous one. The series id is the match id of its first map.
    """
    rosters: Dict[str, Dict[str, Any]] = {}
    for result in ratings.values():
        m = rosters.setdefault(result['match_id'], {'start': result.get('game_start') or 0, 'teams': {}})
        m['teams'].setdefault(result['team'], set()).add(result['puuid'])

    def same_rosters(a, b):
        teams_b = list(b['teams'].values())
        return all(any(len(roster & other) >= SERIES_MIN_OVERLAP for other in teams_b) for roster in a['teams'].values())

    series: Dict[str, str] = {}
    open_series: List[tuple] = []  # (series_id, last map)
    for match_id, m in sorted(rosters.items(), key=lambda kv: kv[1]['start']):
        open_series = [(sid, last) for sid, last in open_series if m['start'] - last['start'] <= SERIES_GAP_MS]
        for i, (sid, last) in enumerate(open_series):
            if same_rosters(m, last):
                series[match_id] = sid
                open_series[i] = (sid, m)
                break
        else:
            series[match_id] = match_id
            open_series.append((match_id, m))
    return series


def aggregate_ratings(ratings: Dict[str, Any], by: Optional[Union[str, Dict[str, str]]] = None,
                      config_path: Optional[Union[str, Path]] = None, role_adjusted: bool = False,
                      interval: float = 0.9, shrink: bool = False) -> Dict[str, Any]:
    """
    Combine per-map ratings over more rounds: a season, a series or any grouping.

    by=None       one entry per player over everything given (e.g. a season)
    by='series'   one entry per player per series (see find_series)
    by={match_id: group}  one entry per player per custom group (event, split, ...)

    The rating is the player's Round Swing per round over all those rounds, and
    rounds_added is the total in rounds. rating_low/rating_high show how far
    that could move from round-to-round luck alone. With shrink=True the rating
    is instead pulled toward average in proportion to how few rounds there are,
    an estimate of the player's level rather than a record of what happened.
    """
    params = _resolve_config(config_path, {})['rating_params']
    sigma2 = params['shrinkage']['round_variance']
    tau2 = params['shrinkage']['true_variance']
    z = NormalDist().inv_cdf(0.5 + interval / 2)
    groups = find_series(ratings) if by == 'series' else by

    totals: Dict[tuple, Dict[str, Any]] = {}
    for result in ratings.values():
        group = groups.get(result['match_id']) if isinstance(groups, dict) else None
        value = result['role_adjusted_rating'] if role_adjusted else result['rating']
        t = totals.setdefault((result['puuid'], group), {'rounds': 0, 'weighted': 0.0, 'maps': 0, 'roles': {},
                                                         'teams': set(), 'name': None})
        t['rounds'] += result['rounds_played']
        t['weighted'] += value * result['rounds_played']
        t['maps'] += 1
        t['teams'].add(result['team'])
        if result.get('role'):
            t['roles'][result['role']] = t['roles'].get(result['role'], 0) + result['rounds_played']
        if 'player_info' in result:
            t['name'] = f"{result['player_info']['name']}#{result['player_info']['tagline']}"

    out = {}
    for (puuid, group), t in totals.items():
        n = t['rounds']
        mean = t['weighted'] / n if n else 0.0
        entry = {
            'puuid': puuid,
            'name': t['name'],
            'maps': t['maps'],
            'rounds_played': n,
            'rating': mean,
            'rounds_added': t['weighted'] / 100.0,
            'rating_low': mean - z * math.sqrt(sigma2 / n) if n else 0.0,
            'rating_high': mean + z * math.sqrt(sigma2 / n) if n else 0.0,
            'main_role': max(t['roles'], key=t['roles'].get) if t['roles'] else None,
        }
        if shrink:
            precision = n / sigma2 + 1.0 / tau2
            entry['rating'] = (t['weighted'] / sigma2) / precision
            entry['rating_low'] = entry['rating'] - z * math.sqrt(1.0 / precision)
            entry['rating_high'] = entry['rating'] + z * math.sqrt(1.0 / precision)
        if group is not None:
            entry['group'] = group
        out[puuid if groups is None else f"{puuid}_{group}"] = entry
    return out


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
