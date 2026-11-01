# Average Damage per Round Adjusted (ADRa) Component Calculator
#
# Damage dealt beyond what the player's own kills required, per round.
# Informational only: OSR 2 credits damage directly through AssistSwing, so
# ADRa is reported but not part of the rating.

from typing import Dict, Any

from ..core.rounds import match_players
from ..core.game_content import game_content

HEALTH = 100


def calculate_adra(
    player: Dict[str, Any],
    match: Dict[str, Any],
    damage_data: Dict[str, int],
    economic_data: Dict[str, Any] = None,
    xvx_data: Dict[str, Any] = None,
    **kwargs
) -> float:
    # ADRa = (total damage - damage needed for own kills) / rounds played, floored at zero.
    # A kill needs 100 health plus the victim's shield (Riot reports armor as an item UUID).
    puuid = player['puuid']
    stats = player.get('stats') or {}
    rounds_played = stats.get('roundsPlayed', 0)
    if rounds_played == 0:
        return 0.0

    armor = game_content()['armor']
    real_players = match_players(match)
    expected_damage = 0
    for round_data in match.get('roundResults', []) or []:
        shields = {ps['puuid']: armor.get(((ps.get('economy') or {}).get('armor') or '').lower(), {}).get('shield', 0)
                   for ps in round_data.get('playerStats', []) or []}
        for ps in round_data.get('playerStats', []) or []:
            if ps['puuid'] != puuid:
                continue
            for kill in ps.get('kills', []) or []:
                victim = kill.get('victim')
                if victim in real_players and real_players[victim]['teamId'] != player['teamId']:
                    expected_damage += HEALTH + shields.get(victim, 0)

    total_damage = damage_data.get(puuid, 0)
    return max(0.0, (total_damage - expected_damage) / rounds_played)
