# Round Win Probability Model
#
# A logistic model of P(attackers win the round) given the live round state:
# players alive on each side, spike status, time left on the relevant clock,
# the loadout value still alive on each side, and the map. Coefficients are
# fitted by tools/calibrate.py and shipped as open_soup_rating/data/wp_model.json.

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .rounds import SPIKE_TIME_MS

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
DEFAULT_MODEL_PATH = DATA_DIR / 'wp_model.json'

# Defusing takes 7 seconds; with less spike time than that left the attackers win.
DEFUSE_MS = 7_000
DEFUSE_SAFE_MS = 10_000


def wp_feature_names(maps) -> list:
    names = []
    for planted in (0, 1):
        for a in range(1, 6):
            for d in range(1, 6):
                cell = f'c{planted}{a}{d}'
                names += [cell, f'{cell}_t', f'{cell}_t2']
    for planted in (0, 1):
        names += [f'loadout_diff{planted}', f'loadout_diff{planted}_t']
    for k in range(len(maps)):
        names += [f'map{k}_{planted}' for planted in (0, 1)]
    return names


def wp_features(state: Dict[str, Any], map_index: Dict[str, int]) -> Dict[str, float]:
    """
    Sparse feature vector for one round state.

    Each (attackers alive, defenders alive, spike planted) cell gets its own
    intercept and its own quadratic curve in time left, so e.g. a 2v1 can drift
    toward the defenders as the round clock runs down while a post-plant 2v1
    drifts toward the attackers. Loadout enters as the difference in total
    loadout value (thousands of credits) still alive on each side, so a death
    can never raise the dying player's team's chances.
    """
    a, d = state['atk_alive'], state['def_alive']
    planted = 1 if state['planted'] else 0
    t = state['time_left']
    cell = f'c{planted}{a}{d}'
    diff = (state['atk_loadout'] - state['def_loadout']) / 1000.0
    features = {
        cell: 1.0,
        f'{cell}_t': t,
        f'{cell}_t2': t * t,
        f'loadout_diff{planted}': diff,
        f'loadout_diff{planted}_t': diff * t,
    }
    k = map_index.get(state.get('map_id'))
    if k is not None:
        features[f'map{k}_{planted}'] = 1.0
    return features


class WinProbabilityModel:
    """Attacker round-win probability for a live round state."""

    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.coefficients: Dict[str, float] = params['coefficients']
        self.maps = params.get('maps', [])
        self.map_index = {m: i for i, m in enumerate(self.maps)}

    @classmethod
    def load(cls, path: Optional[Union[str, Path]] = None) -> 'WinProbabilityModel':
        with open(path or DEFAULT_MODEL_PATH, 'r', encoding='utf-8') as f:
            return cls(json.load(f))

    def attack_win_probability(self, state: Dict[str, Any]) -> float:
        a, d = state['atk_alive'], state['def_alive']
        if d == 0:
            return 1.0
        if a == 0:
            if not state['planted']:
                return 0.0
            # Attackers are dead but the spike is down: defenders still need time to defuse.
            spike_left_ms = state['time_left'] * SPIKE_TIME_MS
            if spike_left_ms >= DEFUSE_SAFE_MS:
                return 0.0
            if spike_left_ms < DEFUSE_MS:
                return 1.0
            return (DEFUSE_SAFE_MS - spike_left_ms) / (DEFUSE_SAFE_MS - DEFUSE_MS)
        z = sum(self.coefficients.get(name, 0.0) * value
                for name, value in wp_features(state, self.map_index).items())
        return 1.0 / (1.0 + math.exp(-z))


_default_model: Optional[WinProbabilityModel] = None


def default_model() -> WinProbabilityModel:
    global _default_model
    if _default_model is None:
        _default_model = WinProbabilityModel.load()
    return _default_model
