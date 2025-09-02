import json
import os
from typing import Dict, List, Any

def load_match_data(sample_data_path: str, max_matches: int = None) -> List[Dict[str, Any]]:
    # Load all match data from the sample_data directory.
    # Returns a list of match dictionaries.
    matches = []
    for root, dirs, files in os.walk(sample_data_path):
        for file in files:
            if file.endswith('.json'):
                if max_matches and len(matches) >= max_matches:
                    break
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r') as f:
                        match_data = json.load(f)
                        matches.append(match_data)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        if max_matches and len(matches) >= max_matches:
            break
    return matches

def extract_player_stats(matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    # Extract overall player stats from matches.
    # Returns a dict of puuid to stats.
    player_stats = {}
    for match in matches:
        for player in match.get('players', []):
            puuid = player['puuid']
            if puuid not in player_stats:
                player_stats[puuid] = {
                    'gameName': player['gameName'],
                    'tagLine': player['tagLine'],
                    'stats': player['stats'],
                    'matches': []
                }
            player_stats[puuid]['matches'].append(match['matchInfo']['matchId'])
    return player_stats

def extract_round_data(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Extract round-level data from matches.
    # Returns a list of round dictionaries with match info.
    rounds = []
    for match in matches:
        match_info = match['matchInfo']
        for round_result in match.get('roundResults', []):
            round_data = {
                'matchId': match_info['matchId'],
                'mapId': match_info['mapId'],
                'roundNum': round_result['roundNum'],
                'roundResult': round_result['roundResult'],
                'winningTeam': round_result['winningTeam'],
                'playerStats': round_result.get('playerStats', []),
                'plantRoundTime': round_result.get('plantRoundTime'),
                'defuseRoundTime': round_result.get('defuseRoundTime'),
                'bombPlanter': round_result.get('bombPlanter'),
                'bombDefuser': round_result.get('bombDefuser'),
                'plantSite': round_result.get('plantSite')
            }
            rounds.append(round_data)
    return rounds

def extract_damage_data(matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    # Extract total damage per player per match.
    # Returns dict of matchId -> puuid -> total_damage
    damage_data = {}
    for match in matches:
        match_id = match['matchInfo']['matchId']
        damage_data[match_id] = {}
        for round_result in match.get('roundResults', []):
            for player_stat in round_result.get('playerStats', []):
                puuid = player_stat['puuid']
                if puuid not in damage_data[match_id]:
                    damage_data[match_id][puuid] = 0
                for damage_event in player_stat.get('damage', []):
                    damage_data[match_id][puuid] += damage_event['damage']
    return damage_data
