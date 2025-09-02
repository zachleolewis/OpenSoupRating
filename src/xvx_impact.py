import json
from typing import Dict, List, Tuple
from post_round_modifier import apply_post_round_modifier

def load_xvx_data(xvx_json_path: str) -> Dict[str, Dict[str, float]]:
    # Load the XvX win probabilities from the JSON.
    with open(xvx_json_path, 'r') as f:
        data = json.load(f)
    return data['win_probabilities']

def get_team_from_puuid(puuid: str, player_stats: List[Dict]) -> str:
    # Get the team of a player from puuid.
    for stat in player_stats:
        if stat['puuid'] == puuid:
            # Need to get team from match players, but since not here, assume we have a dict
            # For now, return 'atk' or 'def' based on planter
            pass
    # Placeholder
    return 'atk'

def determine_sides(match_data: Dict, round_data: Dict, match_players: List[Dict]) -> Tuple[str, str]:
    # Determine which team is atk and def.
    # Returns (atk_team, def_team)
    planter = round_data.get('bombPlanter')
    if planter:
        for player in match_players:
            if player['puuid'] == planter:
                atk_team = player['teamId']
                def_team = 'Blue' if atk_team == 'Red' else 'Red'
                return atk_team, def_team
    # If no planter in this round, check other rounds in the first half (rounds 0-11)
    for r in match_data.get('roundResults', [])[:12]:
        planter = r.get('bombPlanter')
        if planter:
            for player in match_players:
                if player['puuid'] == planter:
                    atk_team = player['teamId']
                    def_team = 'Blue' if atk_team == 'Red' else 'Red'
                    return atk_team, def_team
    # If still no planter, assume Blue is atk
    return 'Blue', 'Red'

def get_xvx_key(alive_atk: int, alive_def: int) -> str:
    # Get the XvX key, like '5v5', '5v4', etc.
    return f"{alive_atk}v{alive_def}"

def get_win_prob(xvx_key: str, side: str, spike_planted: bool, xvx_data: Dict) -> float:
    # Get the win probability for the given XvX, side, spike.
    if spike_planted:
        prob_dict = xvx_data[f'{side}_spike']
    else:
        prob_dict = xvx_data[f'{side}_no_spike']
    return prob_dict.get(xvx_key, 0.5)  # Default to 0.5 if not found

def adjust_win_for_outcome(new_xvx_key: str, side: str, winning_team: str, atk_team: str, def_team: str) -> float:
    # Adjust the win probability based on round outcome for Xv0 states.
    if '0' not in new_xvx_key:
        return None  # No adjustment needed
    
    if new_xvx_key == '1v0':
        if winning_team == atk_team:
            return 1.0 if side == 'atk' else 0.0
        elif winning_team == def_team:
            return 0.0 if side == 'atk' else 1.0
    elif new_xvx_key == '0v1':
        if winning_team == atk_team:
            return 1.0 if side == 'atk' else 0.0
        elif winning_team == def_team:
            return 0.0 if side == 'atk' else 1.0
    else:
        # For other Xv0
        left, right = new_xvx_key.split('v')
        left_alive = int(left)
        right_alive = int(right)
        if left_alive == 0:
            # atk has 0
            if winning_team == atk_team:
                return 1.0 if side == 'atk' else 0.0
            elif winning_team == def_team:
                return 0.0 if side == 'atk' else 1.0
        elif right_alive == 0:
            # def has 0
            if winning_team == atk_team:
                return 1.0 if side == 'atk' else 0.0
            elif winning_team == def_team:
                return 0.0 if side == 'atk' else 1.0
    return None  # If no adjustment

def calculate_xvx_impact(match_data: Dict, round_data: Dict, match_players: List[Dict], xvx_data: Dict) -> Dict[Tuple[str, str], Dict]:
    # Calculate the XvX impact for each kill in the round.
    # Returns a dict of (killer, victim) to detailed impact data.
    spike_planted = 'plantRoundTime' in round_data
    atk_team, def_team = determine_sides(match_data, round_data, match_players)
    
    # Get all kills in the round
    all_kills = []
    for player_stat in round_data['playerStats']:
        for kill in player_stat.get('kills', []):
            all_kills.append({
                'killer': kill['killer'],
                'victim': kill['victim'],
                'time': kill['timeSinceRoundStartMillis'],
                'assistants': kill.get('assistants', [])
            })
    
    # Sort kills by time
    all_kills.sort(key=lambda k: k['time'])
    
    # Initial alive
    alive = {'atk': 5, 'def': 5}
    impacts = {}
    
    for i, kill in enumerate(all_kills):
        killer = kill['killer']
        victim = kill['victim']
        
        # Determine teams
        killer_team = None
        victim_team = None
        for player in match_players:
            if player['puuid'] == killer:
                killer_team = 'atk' if player['teamId'] == atk_team else 'def'
            if player['puuid'] == victim:
                victim_team = 'atk' if player['teamId'] == atk_team else 'def'
        
        if not killer_team or not victim_team:
            continue
        
        # Skip if victim team has no one left
        if alive[victim_team] == 0:
            continue
        
        # Skip if killer team has no one left
        if alive[killer_team] == 0:
            continue
        
        # Current XvX
        xvx_key = f"{alive[killer_team]}v{alive['atk' if killer_team == 'def' else 'def']}"
        old_win_killer = get_win_prob(xvx_key, killer_team, spike_planted, xvx_data)
        
        # Update alive for kill
        alive[victim_team] -= 1
        new_xvx_key = f"{alive[killer_team]}v{alive['atk' if killer_team == 'def' else 'def']}"
        
        # Calculate impact
        new_win_killer = get_win_prob(new_xvx_key, killer_team, spike_planted, xvx_data)
        
        # Adjust for round outcome if 1v0 or 0v1
        winning_team = round_data.get('winningTeam')
        adjusted_win = adjust_win_for_outcome(new_xvx_key, killer_team, winning_team, atk_team, def_team)
        if adjusted_win is not None:
            new_win_killer = adjusted_win
        
        impact = new_win_killer - old_win_killer
        
        # Apply modifiers
        impact = apply_post_round_modifier(impact, kill['time'])
        
        impacts[(killer, victim)] = {
            'impact': impact,
            'xvx_before': xvx_key,
            'xvx_after': new_xvx_key,
            'win_before': old_win_killer,
            'win_after': new_win_killer,
            'killer_team': killer_team,
            'victim_team': victim_team
        }
        
    return impacts
