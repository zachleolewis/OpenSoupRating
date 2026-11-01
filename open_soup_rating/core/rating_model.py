# Rating Model - turns a player's swing ledger into OSR
#
# Round Swing on its own says exactly what happened, but a lot of it is
# leverage luck (a clutch kill and an opening kill take the same aim). OSR
# therefore combines the four Round Swing components with kills, deaths and
# damage dealt/taken, each weighted by how well it predicts the player's Round
# Swing in *other* matches (fitted by tools/calibrate.py). The result is still
# measured in Round Swing units: percentage points of a round won per round.

from typing import Dict, Any

RATING_FEATURES = (
    'KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing',
    'kills', 'deaths', 'damage_dealt', 'damage_taken',
)

_SWING_KIND = {'KillSwing': 'kill', 'AssistSwing': 'assist', 'DeathSwing': 'death', 'ObjectiveSwing': 'objective'}


def rating_features(entry: Dict[str, Any]) -> Dict[str, float]:
    """Per-round inputs of the rating: swing in percentage points, counts per round, damage in hundreds."""
    rounds = entry['rounds']
    features = {name: 100.0 * entry[kind] / rounds for name, kind in _SWING_KIND.items()}
    features['kills'] = entry['kills'] / rounds
    features['deaths'] = entry['deaths'] / rounds
    features['damage_dealt'] = entry['damage_dealt'] / 100.0 / rounds
    features['damage_taken'] = entry['damage_taken'] / 100.0 / rounds
    return features


def round_swing(entry: Dict[str, Any]) -> float:
    """Realised Round Swing per round, in percentage points (uncentred)."""
    return sum(100.0 * entry[kind] / entry['rounds'] for kind in _SWING_KIND.values())


def rating_terms(features: Dict[str, float], params: Dict[str, Any]) -> Dict[str, float]:
    """Each input's contribution to the rating (weight x value)."""
    weights = params['rating_weights']
    return {name: weights[name] * features[name] for name in RATING_FEATURES}


def osr_value(entry: Dict[str, Any], params: Dict[str, Any]) -> float:
    """Uncentred OSR for one ledger entry."""
    return params['intercept'] + sum(rating_terms(rating_features(entry), params).values())
