# Average Damage per Round Adjusted (ADRa) Component Calculator

from typing import Dict, Any, List

def calculate_adra(
    player: Dict[str, Any],
    match: Dict[str, Any],
    damage_data: Dict[str, int],
    economic_data: Dict[str, Any],
    xvx_data: Dict[str, Any],
    **kwargs
) -> float:
    # Calculate Average Damage per Round Adjusted for a player in a match.
    # This matches the exact logic from OpenSoupRatingOLD/src/rating_calculator.py
    # ADRa is calculated as: (total_damage - expected_damage) / rounds_played
    # where expected_damage is calculated from kills based on victim's armor.
    # Args:
    #     player: Player data dictionary
    #     match: Match data dictionary
    #     damage_data: Damage data for all players
    #     economic_data: Economic data (unused for ADRa)
    #     xvx_data: XvX impact data (unused for ADRa)
    #     **kwargs: Additional parameters
    # Returns:
    #     ADRa value

    puuid = player['puuid']
    stats = player.get('stats')

    if stats is None:
        return 0.0

    rounds_played = stats.get('roundsPlayed', 0)
    if rounds_played == 0:
        return 0.0

    # Get total damage for this player (by puuid, not by match_id->puuid)
    total_damage = damage_data.get(puuid, 0)

    # Calculate expected damage from kills (exactly like old system)
    expected_damage = 0
    match_players = match['players']
    rounds = match.get('roundResults', [])

    # For each round, calculate xvx impacts to get kill information
    for round_data in rounds:
        impacts = _calculate_xvx_impacts(match, round_data, match_players, xvx_data)
        
        for (killer, victim), data in impacts.items():
            if killer == puuid:
                # Calculate expected damage for this kill based on victim's armor
                victim_armor = next((ps['economy'].get('armor', 'None') for ps in round_data['playerStats'] if ps['puuid'] == victim), 'None')
                armor_value = {'Light': 25, 'Heavy': 50, 'Regen': 25}.get(victim_armor, 0)
                expected = 100 + armor_value
                expected_damage += expected

    # ADRa = (total_damage - expected_damage) / rounds_played
    adra = (total_damage - expected_damage) / rounds_played
    
    # Ensure non-negative (old system behavior)
    return max(0, adra)

def _calculate_xvx_impacts(match: Dict, round_data: Dict, players: List[Dict], xvx_data: Dict) -> Dict:
    # Calculate XvX impacts for a round using proper win probability calculations.
    impacts = {}
    
    # Get spike planted status
    spike_planted = 'plantRoundTime' in round_data
    
    # Determine attacker and defender teams
    atk_team, def_team = _determine_sides(match, round_data, players)
    
    # Get all kills in the round
    all_kills = []
    for player_stat in round_data.get('playerStats', []):
        for kill in player_stat.get('kills', []):
            all_kills.append({
                'killer': kill.get('killer'),
                'victim': kill.get('victim'), 
                'time': kill.get('timeSinceRoundStartMillis', 0),
                'assistants': kill.get('assistants', [])
            })
    
    # Sort kills by time
    all_kills.sort(key=lambda k: k['time'])
    
    # Initial alive counts
    alive = {'atk': 5, 'def': 5}
    
    for kill in all_kills:
        killer = kill['killer']
        victim = kill['victim']
        
        # Determine teams
        killer_team = _get_team_from_puuid(killer, players, atk_team, def_team)
        victim_team = _get_team_from_puuid(victim, players, atk_team, def_team)
        
        if not killer_team or not victim_team:
            continue
            
        # Skip if victim team has no one left
        if alive[victim_team] == 0:
            continue
            
        # Skip if killer team has no one left  
        if alive[killer_team] == 0:
            continue
        
        # Current XvX state
        xvx_key = _get_xvx_key(alive[killer_team], alive['atk' if killer_team == 'def' else 'def'])
        old_win_prob = _get_win_prob(xvx_key, killer_team, spike_planted, xvx_data)
        
        # Update alive count for kill
        alive[victim_team] -= 1
        new_xvx_key = _get_xvx_key(alive[killer_team], alive['atk' if killer_team == 'def' else 'def'])
        
        # Calculate new win probability
        new_win_prob = _get_win_prob(new_xvx_key, killer_team, spike_planted, xvx_data)
        
        # Adjust for round outcome if needed
        winning_team = round_data.get('winningTeam')
        adjusted_win = _adjust_win_for_outcome(new_xvx_key, killer_team, winning_team, atk_team, def_team)
        if adjusted_win is not None:
            new_win_prob = adjusted_win
        
        # Calculate impact
        impact = new_win_prob - old_win_prob
        
        # Apply post-round modifier based on kill timing
        impact = _apply_post_round_modifier(impact, kill['time'])
        
        impacts[(killer, victim)] = {'impact': impact}
    
    return impacts

def _determine_sides(match: Dict, round_data: Dict, players: List[Dict]) -> tuple[str, str]:
    # Determine which team is attacking and defending.
    planter = round_data.get('bombPlanter')
    if planter:
        for player in players:
            if player['puuid'] == planter:
                atk_team = player['teamId']
                def_team = 'Blue' if atk_team == 'Red' else 'Red'
                return atk_team, def_team
    
    # If no planter in this round, check other rounds in first half
    for r in match.get('roundResults', [])[:12]:
        planter = r.get('bombPlanter')
        if planter:
            for player in players:
                if player['puuid'] == planter:
                    atk_team = player['teamId']
                    def_team = 'Blue' if atk_team == 'Red' else 'Red'
                    return atk_team, def_team
    
    # Default assumption
    return 'Blue', 'Red'

def _get_team_from_puuid(puuid: str, players: List[Dict], atk_team: str, def_team: str) -> str:
    # Get team designation (atk/def) from puuid.
    for player in players:
        if player['puuid'] == puuid:
            if player['teamId'] == atk_team:
                return 'atk'
            elif player['teamId'] == def_team:
                return 'def'
    return None

def _get_xvx_key(alive_atk: int, alive_def: int) -> str:
    # Get XvX key like '5v5', '4v5', etc.
    return f"{alive_atk}v{alive_def}"

def _get_win_prob(xvx_key: str, side: str, spike_planted: bool, xvx_data: Dict) -> float:
    # Get win probability from XvX data.
    if not xvx_data:
        return 0.5  # Default fallback
    
    prob_data = xvx_data
    
    if spike_planted:
        prob_dict = prob_data.get(f'{side}_spike', {})
    else:
        prob_dict = prob_data.get(f'{side}_no_spike', {})
    
    return prob_dict.get(xvx_key, 0.5)

def _adjust_win_for_outcome(xvx_key: str, side: str, winning_team: str, atk_team: str, def_team: str) -> float:
    # Adjust win probability for Xv0 states based on round outcome.
    if '0' not in xvx_key:
        return None
    
    if xvx_key in ['1v0', '0v1']:
        if winning_team == atk_team:
            return 1.0 if side == 'atk' else 0.0
        elif winning_team == def_team:
            return 0.0 if side == 'atk' else 1.0
    
    # For other Xv0 states
    left, right = xvx_key.split('v')
    left_alive = int(left)
    right_alive = int(right)
    
    if left_alive == 0:  # atk has 0
        if winning_team == atk_team:
            return 1.0 if side == 'atk' else 0.0
        elif winning_team == def_team:
            return 0.0 if side == 'atk' else 1.0
    elif right_alive == 0:  # def has 0
        if winning_team == atk_team:
            return 1.0 if side == 'atk' else 0.0
        elif winning_team == def_team:
            return 0.0 if side == 'atk' else 1.0
    
    return None

def _apply_post_round_modifier(impact: float, kill_time: int) -> float:
    # Apply post-round modifier based on kill timing.
    # If kill after round end (~100s), lessen impact by 50%
    if kill_time > 100000:  # 100 seconds in milliseconds
        return impact * 0.5
    return impact
