# Corrected Death Contribution Component Calculator
# Implements simplified methodology using only XvX probability change and economic modifiers

from typing import Dict, Any, List
import json
import os

def calculate_death_contrib(
    player: Dict[str, Any],
    match: Dict[str, Any],
    damage_data: Dict[str, int],
    economic_data: Dict[str, Any],
    xvx_data: Dict[str, Any],
    **kwargs
) -> float:
    """
    Calculate death contribution component for a player in a match.
    
    Args:
        player: Player data (should contain puuid)
        match: Match data containing rounds and player stats
        damage_data: Damage tracking data (currently unused in simplified version)
        economic_data: Economic impact data for loadout calculations
        xvx_data: XvX win probability data
        **kwargs: Additional parameters (currently unused)
    
    Returns:
        Death contribution value (negative for deaths that hurt team win probability)
    """
    puuid = player['puuid']
    match_players = match['players']
    rounds = match.get('roundResults', [])
    
    # Load actual data files if not provided
    if not xvx_data or not economic_data:
        xvx_data, economic_data = _load_data_files()
    
    total_death_contrib = 0.0
    
    # Process each round
    for round_data in rounds:
        round_num = round_data['roundNum']
        
        # Get spike planted status
        spike_planted = 'plantRoundTime' in round_data
        
        # Determine attacker and defender teams
        atk_team, def_team = _determine_sides(match, round_data, match_players)
        
        # Determine when round outcome was effectively decided
        effective_round_end_time = _get_effective_round_end_time(round_data)
        
        # Get all kills in the round that occurred before round outcome was decided
        all_kills = []
        for player_stat in round_data.get('playerStats', []):
            player_puuid = player_stat['puuid']
            for kill in player_stat.get('kills', []):
                kill_time = kill.get('timeSinceRoundStartMillis', 0)
                # Only include kills that happened before round outcome was decided
                if effective_round_end_time is None or kill_time <= effective_round_end_time:
                    all_kills.append({
                        'killer': kill.get('killer'),
                        'victim': kill.get('victim'),
                        'time': kill_time,
                        'finishingDamage': kill.get('finishingDamage', {})
                    })
        
        # Sort kills by time
        all_kills.sort(key=lambda k: k['time'])
        
        # Initial alive counts
        alive = {'atk': 5, 'def': 5}
        
        # Process each kill in chronological order
        for kill in all_kills:
            killer_puuid = kill['killer']
            victim_puuid = kill['victim']
            
            # Skip spike deaths
            if kill.get('finishingDamage', {}).get('damageType') == 'Bomb':
                # Update alive counts for spike deaths
                victim_team = _get_team_from_puuid(victim_puuid, match_players, atk_team, def_team)
                if victim_team and alive[victim_team] > 0:
                    alive[victim_team] -= 1
                continue
            
            # Only process deaths of this player
            if victim_puuid != puuid:
                # Still need to update alive counts for kills involving other players
                victim_team = _get_team_from_puuid(victim_puuid, match_players, atk_team, def_team)
                if victim_team and alive[victim_team] > 0:
                    alive[victim_team] -= 1
                continue
            
            # Determine teams
            killer_team = _get_team_from_puuid(killer_puuid, match_players, atk_team, def_team)
            victim_team = _get_team_from_puuid(victim_puuid, match_players, atk_team, def_team)
            
            if not killer_team or not victim_team or killer_team == victim_team:
                continue
            
            # Skip if victim team has no one left or killer team has no one left
            if alive[victim_team] == 0 or alive[killer_team] == 0:
                continue
            
            # Determine if victim is on attacking team (for victim's perspective)
            victim_is_attacker = (victim_team == atk_team)
            
            # Construct XvX as {victim_team_count}v{killer_team_count} (from victim's perspective)
            # Left side = victim's team count, Right side = killer's team count
            victim_team_count = alive[victim_team]
            killer_team_count = alive[killer_team]
            xvx_before = _get_xvx_key(victim_team_count, killer_team_count)
            
            # Calculate win probability before death (use dataset based on victim's role)
            win_prob_before = _get_win_probability_killer_perspective(xvx_before, spike_planted, xvx_data, victim_is_attacker)
            
            # Update alive count for death (victim team loses one)
            alive[victim_team] -= 1
            
            # Construct XvX after death (still from victim's perspective)
            victim_team_count_after = alive[victim_team]
            killer_team_count_after = alive[killer_team]
            xvx_after = _get_xvx_key(victim_team_count_after, killer_team_count_after)
            
            # Calculate win probability after death (from victim's perspective)
            win_prob_after = _get_win_probability_killer_perspective(xvx_after, spike_planted, xvx_data, victim_is_attacker)
            
            # Adjust for round outcome if elimination scenario (X v 0)
            adjusted_win = _adjust_win_for_outcome(xvx_after, victim_is_attacker, round_data)
            if adjusted_win is not None:
                win_prob_after = adjusted_win
            
            # Calculate base impact (will be negative since victim's win probability decreased)
            base_impact = win_prob_after - win_prob_before
            
            # Calculate economic modifier based on individual loadouts
            killer_loadout = _get_player_loadout(killer_puuid, round_data)
            victim_loadout = _get_player_loadout(victim_puuid, round_data)
            economic_modifier = _calculate_economic_modifier(
                killer_loadout, 
                victim_loadout, 
                economic_data
            )
            
            # Final death impact: difference in win probability modified by economic factor
            death_impact = base_impact * economic_modifier
            
            # Force negative for deaths (deaths hurt team win probability)
            death_impact = -abs(death_impact)
            
            total_death_contrib += death_impact
    
    return total_death_contrib

def _get_win_probability_killer_perspective(xvx_key, spike_planted, xvx_data, killer_is_attacker):
    """
    Get win probability from killer's perspective.
    
    Args:
        xvx_key: XvX situation (e.g., "5v4")
        spike_planted: Whether spike is planted
        xvx_data: XvX probability data
        killer_is_attacker: True if killer is on attacking team, False if defender
    """
    if not xvx_data or not isinstance(xvx_data, dict):
        return 0.5  # Default fallback
    
    win_probabilities = xvx_data.get('win_probabilities', {})
    if not isinstance(win_probabilities, dict):
        return 0.5  # Default fallback
    
    if killer_is_attacker:
        # Killer is attacker - use attacker perspective data
        if spike_planted:
            atk_spike = win_probabilities.get('atk_spike', {})
            return atk_spike.get(xvx_key, 0.5) if isinstance(atk_spike, dict) else 0.5
        else:
            atk_no_spike = win_probabilities.get('atk_no_spike', {})
            return atk_no_spike.get(xvx_key, 0.5) if isinstance(atk_no_spike, dict) else 0.5
    else:
        # Killer is defender - use complementary probability from attacker's perspective
        inverse_key = _get_inverse_xvx_key(xvx_key)
        if spike_planted:
            atk_spike = win_probabilities.get('atk_spike', {})
            atk_prob = atk_spike.get(inverse_key, 0.5) if isinstance(atk_spike, dict) else 0.5
        else:
            atk_no_spike = win_probabilities.get('atk_no_spike', {})
            atk_prob = atk_no_spike.get(inverse_key, 0.5) if isinstance(atk_no_spike, dict) else 0.5
        return 1 - atk_prob

def _get_inverse_xvx_key(xvx_key):
    """Get the inverse XvX key (e.g., '4v5' -> '5v4')"""
    left, right = xvx_key.split('v')
    return f"{right}v{left}"

def _adjust_win_for_outcome(xvx_key, killer_is_attacker, round_outcome):
    """
    Adjust win probability for X v 0 scenarios based on round outcome.
    
    Args:
        xvx_key: XvX key (e.g., "1v0", "0v1") 
        killer_is_attacker: True if killer is on attacking team
        round_outcome: Round outcome data containing winner info
    
    Returns:
        Adjusted win probability if needed, None if no adjustment
    """
    if '0' not in xvx_key:
        return None  # No adjustment needed
    
    # Get round winner info
    winning_team = round_outcome.get('winningTeam')
    if not winning_team:
        return None
    
    # Determine if winner was attacking or defending team
    # This requires checking plant data to know which team was attacking
    plant_data = round_outcome.get('plantRoundTime')
    winner_was_attacker = None
    
    if plant_data is not None:
        # If spike was planted, attackers planted it
        # If round was won by elimination/defuse, we can infer from spike state
        round_end_reason = round_outcome.get('roundEndReason', '')
        if 'Elimination' in round_end_reason:
            # Winner was the team that eliminated the other
            if killer_is_attacker:
                winner_was_attacker = True  # Attacker got final elimination
            else:
                winner_was_attacker = False  # Defender got final elimination
        elif 'Defuse' in round_end_reason:
            winner_was_attacker = False  # Defenders defused
        elif 'Detonate' in round_end_reason:
            winner_was_attacker = True  # Attackers' spike detonated
    
    # If we can't determine winner's side, don't adjust
    if winner_was_attacker is None:
        return None
    
    # For X v 0 scenarios, adjust based on actual round outcome
    left, right = xvx_key.split('v')
    left_alive = int(left)
    right_alive = int(right)
    
    if right_alive == 0:  # Defender team eliminated
        if winner_was_attacker:
            return 1.0 if killer_is_attacker else 0.0
        else:
            return 0.0 if killer_is_attacker else 1.0
    elif left_alive == 0:  # Attacker team eliminated
        if winner_was_attacker:
            return 1.0 if killer_is_attacker else 0.0
        else:
            return 0.0 if killer_is_attacker else 1.0
    
    return None

def _get_effective_round_end_time(round_data):
    """
    Determine when the round outcome was effectively decided.
    
    Returns the timestamp after which kills/deaths should not count
    toward round impact because the round outcome is already determined.
    """
    round_result_code = round_data.get('roundResultCode')
    
    if round_result_code == "Defuse":
        # Round ends when spike is defused
        return round_data.get('defuseRoundTime')
    elif round_result_code == "Elimination":
        # Round ends when last enemy is eliminated
        # Find the time of the last kill in the round
        last_kill_time = 0
        for player_stat in round_data.get('playerStats', []):
            for kill in player_stat.get('kills', []):
                kill_time = kill.get('timeSinceRoundStartMillis', 0)
                last_kill_time = max(last_kill_time, kill_time)
        return last_kill_time if last_kill_time > 0 else None
    elif round_result_code == "Detonate":
        # Round ends when spike explodes (45 seconds after plant)
        plant_time = round_data.get('plantRoundTime')
        if plant_time is not None:
            return plant_time + 45000  # 45 seconds in milliseconds
        else:
            return None
    else:
        # Unknown result code, include all kills
        return None

def _load_data_files():
    """Load XvX and economic data from JSON files."""
    
    # Get the directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    xvx_file = os.path.join(project_root, 'data', 'xvx_data.json')
    economic_file = os.path.join(project_root, 'data', 'loadout_cost_analysis.json')
    
    xvx_data = {}
    economic_data = {}
    
    try:
        with open(xvx_file, 'r') as f:
            xvx_data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load XvX data from {xvx_file}: {e}")
    
    try:
        with open(economic_file, 'r') as f:
            economic_data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load economic data from {economic_file}: {e}")
    
    return xvx_data, economic_data

def _get_player_loadout(puuid, round_data):
    """Get individual player's loadout value for this round."""
    if not round_data or not isinstance(round_data, dict):
        return 0
    
    player_stats = round_data.get('playerStats', [])
    if not isinstance(player_stats, list):
        return 0
    
    for player_stat in player_stats:
        if isinstance(player_stat, dict) and player_stat.get('puuid') == puuid:
            economy = player_stat.get('economy', {})
            if isinstance(economy, dict):
                return economy.get('loadoutValue', 0)
    return 0

def _get_team_loadouts(killer_puuid, victim_puuid, round_data, match_players):
    """Get total team loadouts for killer and victim teams."""
    # Get team IDs for killer and victim
    killer_team = None
    victim_team = None
    
    for player in match_players:
        if player['puuid'] == killer_puuid:
            killer_team = player['teamId']
        elif player['puuid'] == victim_puuid:
            victim_team = player['teamId']
    
    if not killer_team or not victim_team:
        return 0, 0
    
    # Calculate team loadouts
    killer_team_total = 0
    victim_team_total = 0
    
    for player_stat in round_data.get('playerStats', []):
        puuid = player_stat['puuid']
        loadout = player_stat.get('economy', {}).get('loadoutValue', 0)
        
        # Find which team this player belongs to
        for player in match_players:
            if player['puuid'] == puuid:
                if player['teamId'] == killer_team:
                    killer_team_total += loadout
                elif player['teamId'] == victim_team:
                    victim_team_total += loadout
                break
    
    return killer_team_total, victim_team_total

def _determine_sides(match, round_data, players):
    """Determine which team is attacking and defending based on spike planter."""
    current_round = round_data.get('roundNum', 0)
    
    # Check current round for planter first
    planter = round_data.get('bombPlanter')
    if planter:
        for player in players:
            if player['puuid'] == planter:
                if current_round < 12:
                    # First half - planter's team is attacker
                    atk_team = player['teamId']
                    def_team = 'Blue' if atk_team == 'Red' else 'Red'
                else:
                    # Second half - planter's team is defender (sides switched)
                    def_team = player['teamId']
                    atk_team = 'Blue' if def_team == 'Red' else 'Red'
                return atk_team, def_team
    
    # If no planter in current round, check other rounds in the same half
    rounds = match.get('roundResults', [])
    
    if current_round < 12:
        # First half - check rounds 0-11
        search_rounds = range(0, min(12, len(rounds)))
    else:
        # Second half - check rounds 12+
        search_rounds = range(12, len(rounds))
    
    for round_num in search_rounds:
        if round_num < len(rounds):
            round_info = rounds[round_num]
            planter = round_info.get('bombPlanter')
            if planter:
                for player in players:
                    if player['puuid'] == planter:
                        if current_round < 12:
                            # First half - planter's team is attacker
                            atk_team = player['teamId']
                            def_team = 'Blue' if atk_team == 'Red' else 'Red'
                        else:
                            # Second half - planter's team is defender (sides switched)
                            def_team = player['teamId']
                            atk_team = 'Blue' if def_team == 'Red' else 'Red'
                        return atk_team, def_team
                    atk_team = player['teamId']
                    def_team = 'Blue' if atk_team == 'Red' else 'Red'
                    return atk_team, def_team
    
    # Default assumption
    return 'Blue', 'Red'

def _get_team_from_puuid(puuid, players, atk_team, def_team):
    """Get team designation (atk/def) from puuid."""
    for player in players:
        if player['puuid'] == puuid:
            if player['teamId'] == atk_team:
                return 'atk'
            elif player['teamId'] == def_team:
                return 'def'
    return None

def _get_xvx_key(alive_atk, alive_def):
    """Get XvX key like '5v5', '4v5', etc."""
    return f"{alive_atk}v{alive_def}"

def _get_win_probability(xvx_key, side, spike_planted, xvx_data):
    """Get win probability from XvX data."""
    if not xvx_data or 'win_probabilities' not in xvx_data:
        return 0.5  # Default fallback
    
    win_probs = xvx_data['win_probabilities']
    
    # Determine the correct data key based on side and spike status
    if spike_planted:
        if side == 'atk':
            prob_dict = win_probs.get('atk_spike', {})
        else:
            prob_dict = win_probs.get('def_spike', {})
    else:
        if side == 'atk':
            prob_dict = win_probs.get('atk_no_spike', {})
        else:
            prob_dict = win_probs.get('def_no_spike', {})
    
    return prob_dict.get(xvx_key, 0.5)

def _get_economy_category(individual_loadout):
    """Categorize individual player loadout into economy categories."""
    if individual_loadout <= 1500:
        return "Save Round"
    elif individual_loadout <= 4000:
        return "Eco Round"
    elif individual_loadout <= 7500:
        return "Force Buy"
    elif individual_loadout <= 10000:
        return "Anti-Eco"
    elif individual_loadout <= 15000:
        return "Full Buy"
    else:
        return "Operator Buy"

def _calculate_economic_modifier(killer_loadout, victim_loadout, economic_data):
    """
    Calculate economic modifier based on individual loadouts.
    
    Uses the formula: 2 * (1 - win_rate)
    - If win_rate = 0.5, modifier = 1 (no change)
    - If win_rate < 0.5, modifier > 1 (killer disadvantage, bonus)
    - If win_rate > 0.5, modifier < 1 (killer advantage, penalty)
    """
    if not economic_data or not isinstance(economic_data, dict):
        return 1.0  # Default fallback
    
    economy_categories = economic_data.get('economy_categories', {})
    if not isinstance(economy_categories, dict):
        return 1.0  # Default fallback
    
    killer_category = _get_economy_category(killer_loadout)
    victim_category = _get_economy_category(victim_loadout)
    matchup = f"{killer_category} vs {victim_category}"
    
    if matchup in economy_categories and isinstance(economy_categories[matchup], dict):
        win_rate = economy_categories[matchup].get('win_rate', 0.5)
        # Use the exact formula from old implementation: 2 * (1 - win_rate)
        modifier = 2 * (1 - win_rate)
        return modifier
    else:
        return 1.0  # Default fallback if matchup not found
