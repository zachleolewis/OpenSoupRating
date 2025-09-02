import json
from typing import Dict, List, Any
from data_loader import load_match_data, extract_damage_data
from economic_impact import load_economic_data, get_economic_modifier
from xvx_impact import load_xvx_data, calculate_xvx_impact
from apr import calculate_apr
from adra import calculate_adra

def calculate_components(matches: List[Dict], economic_data: Dict, xvx_data: Dict, damage_data: Dict) -> List[Dict]:
    # Calculate the components for each player in each match.
    # Returns list of dicts with puuid, matchId, KillContrib, DeathContrib, APR, ADRa, target
    components = []
    for match in matches:
        match_id = match['matchInfo']['matchId']
        match_players = match['players']
        rounds = match.get('roundResults', [])
        
        # For each round, calculate xvx impacts
        round_impacts = {}
        for round_data in rounds:
            impacts = calculate_xvx_impact(match, round_data, match_players, xvx_data)
            round_impacts[round_data['roundNum']] = impacts
            
            # Calculate team loadouts
            team_loadouts = {'Blue': 0, 'Red': 0}
            for player_stat in round_data.get('playerStats', []):
                puuid = player_stat['puuid']
                loadout = player_stat.get('economy', {}).get('loadoutValue', 0)
                team = None
                for player in match_players:
                    if player['puuid'] == puuid:
                        team = player['teamId']
                        break
                if team:
                    team_loadouts[team] += loadout
        
        # Now, for each player, sum contributions
        player_contribs = {}
        expected_damage = {}
        for player in match_players:
            puuid = player['puuid']
            player_contribs[puuid] = {'kill': 0, 'death': 0}
            expected_damage[puuid] = 0
        
        for round_data in rounds:
            round_num = round_data['roundNum']
            impacts = round_impacts[round_num]
            blue_loadout = team_loadouts['Blue']
            red_loadout = team_loadouts['Red']
            
            for (killer, victim), data in impacts.items():
                impact = data['impact']
                # Get teams
                killer_team = None
                victim_team = None
                for player in match_players:
                    if player['puuid'] == killer:
                        killer_team = player['teamId']
                    if player['puuid'] == victim:
                        victim_team = player['teamId']
                
                if killer_team == 'Blue':
                    killer_loadout = blue_loadout
                    victim_loadout = red_loadout
                else:
                    killer_loadout = red_loadout
                    victim_loadout = blue_loadout
                
                # Calculate expected damage for this kill based on victim's armor
                victim_armor = next((ps['economy'].get('armor', 'None') for ps in round_data['playerStats'] if ps['puuid'] == victim), 'None')
                armor_value = {'Light': 25, 'Heavy': 50, 'Regen': 25}.get(victim_armor, 0)
                expected = 100 + armor_value
                expected_damage[killer] += expected
                
                econ_mod_kill = get_economic_modifier(killer_loadout, victim_loadout, economic_data)
                econ_mod_death = econ_mod_kill
                
                player_contribs[killer]['kill'] += 0.5 * impact + 0.5 * (impact * econ_mod_kill)
                player_contribs[victim]['death'] += 0.5 * (-impact) + 0.5 * ((-impact) * econ_mod_death)
        
        # Now, for each player, calculate APR, ADRa
        for player in match_players:
            puuid = player['puuid']
            stats = player['stats']
            rounds_played = stats['roundsPlayed']
            kills = stats['kills']
            deaths = stats['deaths']
            assists = stats['assists']
            total_damage = damage_data.get(match_id, {}).get(puuid, 0)
            
            apr = calculate_apr(stats)
            expected_total = expected_damage[puuid]
            adra = calculate_adra(total_damage, expected_total, rounds_played)
            
            kill_contrib = player_contribs[puuid]['kill']
            death_contrib = player_contribs[puuid]['death']
            
            target = stats['vlrRating2']
            
            components.append({
                'puuid': puuid,
                'matchId': match_id,
                'KillContrib': kill_contrib,
                'DeathContrib': death_contrib,
                'APR': apr,
                'ADRa': adra,
                'target': target,
                'kills': kills,
                'deaths': deaths,
                'assists': assists
            })
    
    return components

if __name__ == "__main__":
    # Load data
    matches = load_match_data('../sample_data')
    economic_data = load_economic_data('../loadout_cost_analysis.json')
    xvx_data = load_xvx_data('../xvx_breakdown_data.json')
    damage_data = extract_damage_data(matches)
    
    components = calculate_components(matches, economic_data, xvx_data, damage_data)
    
    # Save to json or something
    with open('components.json', 'w') as f:
        json.dump(components, f)
