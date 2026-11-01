#!/usr/bin/env python3
"""
Fit the OSR win probability model and rating constants from a directory of
Riot match JSON files (.json or .json.gz, searched recursively).

    pip install -e .[calibrate]
    python tools/calibrate.py path/to/matches --out open_soup_rating/data

Writes:
  wp_model.json       logistic coefficients for P(attackers win round | state)
  rating_params.json  role baselines and variance constants (luck bands, optional shrinkage)

With --holdout 0.2 the newest 20% of maps (by game start) are held out, the
model is scored on them, and then refitted on everything.
"""

import argparse
import datetime
import gzip
import json
import random
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from open_soup_rating.core.rounds import parse_match, RoundState, match_players  # noqa: E402
from open_soup_rating.core.swing import compute_match_swing, SWING_KINDS  # noqa: E402
from open_soup_rating.core.win_probability import WinProbabilityModel, wp_features, wp_feature_names  # noqa: E402
from open_soup_rating.core.game_content import agent_role  # noqa: E402


def load_json(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def patch_of(match):
    found = re.search(r'release-(\d+)\.(\d+)', match.get('matchInfo', {}).get('gameVersion', ''))
    return (int(found.group(1)), int(found.group(2))) if found else (0, 0)


def usable(match, min_patch):
    return patch_of(match) >= min_patch and len(match_players(match)) == 10 and match.get('roundResults')


def scan(args):
    path, min_patch, before_ms = args
    try:
        match = load_json(path)
    except Exception:
        return None
    if not usable(match, min_patch):
        return None
    info = match['matchInfo']
    if before_ms and info.get('gameStartMillis', 0) >= before_ms:
        return None
    return str(path), info.get('gameStartMillis', 0), info.get('mapId'), patch_of(match)


def round_states(args):
    """All states of every round in a map, after each kill/plant and right before each one."""
    path, sample, seed = args
    match = load_json(path)
    rng = random.Random(seed)
    parsed = parse_match(match)
    rows = []
    for r in parsed['rounds']:
        if r['attackers_won'] is None or len(r['participants']) != 10:
            continue
        state = RoundState(r, parsed['players'], parsed['map_id'])

        def keep():
            if rng.random() < sample:
                rows.append((state.features(), int(r['attackers_won'])))

        keep()
        events = [('kill', k['time'], k) for k in r['kills']]
        if r['plant'] and r['plant']['time'] <= r['end_time']:
            events.append(('plant', r['plant']['time'], r['plant']))
        events.sort(key=lambda e: (e[1], e[0] != 'plant'))
        for kind, time, event in events:
            state.time = time
            if not state.alive['atk'] or not state.alive['def']:
                break
            keep()
            if kind == 'plant':
                state.plant_time = time
            else:
                for side in ('atk', 'def'):
                    state.alive[side].discard(event['victim'])
            if state.alive['atk'] and state.alive['def']:
                keep()
    return rows


def fit_model(paths, maps, sample, workers, c_value):
    with Pool(workers) as pool:
        chunks = pool.map(round_states, [(p, sample, i) for i, p in enumerate(paths)], chunksize=50)
    states = [s for chunk in chunks for s in chunk]
    map_index = {m: i for i, m in enumerate(maps)}
    vec = DictVectorizer(sparse=True)
    vec.fit([{n: 0.0 for n in wp_feature_names(maps)}])
    X = vec.transform([wp_features(f, map_index) for f, _ in states])
    y = np.array([label for _, label in states])
    lr = LogisticRegression(C=c_value, max_iter=5000, fit_intercept=False)
    lr.fit(X, y)
    coefficients = {name: float(c) for name, c in zip(vec.get_feature_names_out(), lr.coef_[0]) if c != 0.0}
    return {'coefficients': coefficients, 'maps': maps}, len(states)


def score_model(params, paths, workers):
    with Pool(workers) as pool:
        chunks = pool.map(round_states, [(p, 1.0, i) for i, p in enumerate(paths)], chunksize=50)
    model = WinProbabilityModel(params)
    states = [s for chunk in chunks for s in chunk]
    p = np.array([model.attack_win_probability(f) for f, _ in states])
    y = np.array([label for _, label in states])
    return {'states': len(states), 'log_loss': round(float(log_loss(y, p)), 4),
            'brier': round(float(brier_score_loss(y, p)), 4)}


def player_maps(args):
    path, params = args
    match = load_json(path)
    ledger = compute_match_swing(match, WinProbabilityModel(params))
    players = match_players(match)
    out = []
    for puuid, entry in ledger.items():
        if entry['rounds'] == 0:
            continue
        rating = 100.0 * sum(entry[k] for k in SWING_KINDS) / entry['rounds']
        out.append((puuid, entry['rounds'], rating, agent_role(players[puuid].get('characterId'))))
    return out


def rating_constants(params, paths, workers):
    """Role baselines and variance constants from every player-map."""
    with Pool(workers) as pool:
        chunks = pool.map(player_maps, [(p, params) for p in paths], chunksize=50)
    rows = [r for chunk in chunks for r in chunk]
    rounds = np.array([r[1] for r in rows], dtype=float)
    value = np.array([r[2] for r in rows])

    roles = {}
    for role in sorted({r[3] for r in rows if r[3]}):
        mask = np.array([r[3] == role for r in rows])
        roles[role] = round(float(np.average(value[mask], weights=rounds[mask])), 4)

    # Variance components: a map rating = player level + noise with variance sigma2 / rounds.
    by_player = {}
    for (puuid, n, v, _) in rows:
        by_player.setdefault(puuid, []).append((n, v))
    within, between_means, between_noise = [], [], []
    for maps_played in by_player.values():
        if len(maps_played) < 10:
            continue
        n = np.array([m[0] for m in maps_played], dtype=float)
        v = np.array([m[1] for m in maps_played])
        mean = np.average(v, weights=n)
        within.append(np.sum(n * (v - mean) ** 2) / (len(v) - 1))
        between_means.append(mean)
        between_noise.append(1.0 / np.sum(n))
    sigma2 = float(np.mean(within))
    tau2 = float(max(np.var(between_means) - sigma2 * np.mean(between_noise), 1e-6))
    return {
        'mean': round(float(np.average(value, weights=rounds)), 4),
        'role_baselines': roles,
        'shrinkage': {
            'round_variance': round(sigma2, 2),
            'true_variance': round(tau2, 4),
            'prior_rounds': round(sigma2 / tau2, 1),
        },
        'player_maps': len(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('data_dir')
    parser.add_argument('--out', default=str(Path(__file__).resolve().parent.parent / 'open_soup_rating' / 'data'))
    parser.add_argument('--min-patch', default='8.0', help='oldest game version to use, e.g. 8.0')
    parser.add_argument('--sample', type=float, default=0.25, help='fraction of round states used for fitting')
    parser.add_argument('--holdout', type=float, default=0.0, help='fraction of newest maps to score on before refitting')
    parser.add_argument('--C', type=float, default=10.0, help='inverse L2 strength of the logistic fit')
    parser.add_argument('--before', help='only use maps played before this date (YYYY-MM-DD), for backtests')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()

    major, minor = (int(x) for x in args.min_patch.split('.'))
    before_ms = None
    if args.before:
        before = datetime.datetime.strptime(args.before, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
        before_ms = int(before.timestamp() * 1000)
    files = sorted(p for p in Path(args.data_dir).rglob('*') if p.name.endswith(('.json', '.json.gz')))
    with Pool(args.workers) as pool:
        found = [r for r in pool.map(scan, [(p, (major, minor), before_ms) for p in files], chunksize=100) if r]
    found.sort(key=lambda r: r[1])
    paths = [r[0] for r in found]
    maps = sorted({r[2] for r in found if r[2]})
    print(f'{len(paths)} usable maps of {len(files)} files')

    holdout = None
    if args.holdout > 0:
        split = int(len(paths) * (1 - args.holdout))
        params, n = fit_model(paths[:split], maps, args.sample, args.workers, args.C)
        holdout = score_model(params, paths[split:], args.workers)
        holdout['maps'] = len(paths) - split
        print('holdout', holdout)

    params, n_states = fit_model(paths, maps, args.sample, args.workers, args.C)
    first = datetime.datetime.fromtimestamp(found[0][1] / 1000, datetime.timezone.utc).date().isoformat()
    last = datetime.datetime.fromtimestamp(found[-1][1] / 1000, datetime.timezone.utc).date().isoformat()
    patches = sorted({r[3] for r in found})
    params['metadata'] = {
        'description': 'Logistic model of P(attackers win round | alive, spike, time left, loadout, map)',
        'maps': len(paths),
        'states_fitted': n_states,
        'game_dates': [first, last],
        'patches': [f'{patches[0][0]}.{patches[0][1]:02d}', f'{patches[-1][0]}.{patches[-1][1]:02d}'],
        'holdout': holdout,
        'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'wp_model.json', 'w', encoding='utf-8') as f:
        json.dump(params, f, indent=1)

    constants = rating_constants(params, paths, args.workers)
    constants['metadata'] = dict(params['metadata'], description='Role baselines and variance constants')
    with open(out / 'rating_params.json', 'w', encoding='utf-8') as f:
        json.dump(constants, f, indent=2)
    print(json.dumps({k: v for k, v in constants.items() if k != 'metadata'}, indent=2))


if __name__ == '__main__':
    main()
