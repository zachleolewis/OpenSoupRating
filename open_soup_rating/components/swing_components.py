# Round Swing Components
#
# Each component is the player's share of round win probability swing for one
# kind of event, in percentage points of a round per round played. Together
# they sum to the rating.

from typing import Dict, Any

from ..core.swing import compute_match_swing


def _swing_per_round(kind: str, player: Dict[str, Any], match: Dict[str, Any], **kwargs) -> float:
    ledger = kwargs.get('swing') or compute_match_swing(match, parsed=kwargs.get('parsed'))
    entry = ledger.get(player['puuid'])
    if not entry or entry['rounds'] == 0:
        return 0.0
    return 100.0 * entry[kind] / entry['rounds']


def calculate_kill_swing(player, match, damage_data=None, economic_data=None, xvx_data=None, **kwargs) -> float:
    """Killer's share of the win probability gained by their kills."""
    return _swing_per_round('kill', player, match, **kwargs)


def calculate_assist_swing(player, match, damage_data=None, economic_data=None, xvx_data=None, **kwargs) -> float:
    """Share of teammates' kills earned through damage, utility assists and being traded."""
    return _swing_per_round('assist', player, match, **kwargs)


def calculate_death_swing(player, match, damage_data=None, economic_data=None, xvx_data=None, **kwargs) -> float:
    """Win probability the player's team lost when they died (negative)."""
    return _swing_per_round('death', player, match, **kwargs)


def calculate_objective_swing(player, match, damage_data=None, economic_data=None, xvx_data=None, **kwargs) -> float:
    """Win probability gained by planting or defusing, less a share of plants/defuses conceded."""
    return _swing_per_round('objective', player, match, **kwargs)


def calculate_hold_swing(player, match, damage_data=None, economic_data=None, xvx_data=None, **kwargs) -> float:
    """Share of win probability that moved while the player was alive with no kill or objective:
    holding a site as the clock runs, sitting on a planted spike, closing out the round."""
    return _swing_per_round('hold', player, match, **kwargs)
