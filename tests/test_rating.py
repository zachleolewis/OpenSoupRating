"""Behaviour tests for round parsing, Round Swing and the rating, on hand-built matches."""

import pytest

import open_soup_rating as osr
from open_soup_rating.core.rounds import determine_attackers, parse_match
from open_soup_rating.core.swing import compute_match_swing
from open_soup_rating.components.adra import calculate_adra

RED = [f'r{i}' for i in range(5)]
BLUE = [f'b{i}' for i in range(5)]
HEAVY = '822BCAB2-40A2-324E-C137-E09195AD7692'
JETT = 'add6443a-41bd-e414-f6ad-e58d267f4e95'


def make_round(num, winner, kills=(), plant=None, defuse=None, damage=(), code='Elimination', loadout=3900):
    """kills: (time_ms, killer, victim[, assistants]); damage: (attacker, receiver, amount)."""
    stats = []
    for p in RED + BLUE:
        stats.append({
            'puuid': p,
            'kills': [{'timeSinceRoundStartMillis': k[0], 'killer': k[1], 'victim': k[2],
                       'assistants': list(k[3]) if len(k) > 3 else [], 'finishingDamage': {'damageType': 'Weapon'}}
                      for k in kills if k[1] == p],
            'damage': [{'receiver': d[1], 'damage': d[2]} for d in damage if d[0] == p],
            'economy': {'loadoutValue': loadout, 'armor': HEAVY},
        })
    r = {'roundNum': num, 'winningTeam': winner, 'roundResultCode': code, 'playerStats': stats,
         'bombPlanter': None, 'plantRoundTime': 0, 'bombDefuser': None, 'defuseRoundTime': 0}
    if plant:
        r['bombPlanter'], r['plantRoundTime'] = plant[1], plant[0]
    if defuse:
        r['bombDefuser'], r['defuseRoundTime'] = defuse[1], defuse[0]
    return r


def make_match(rounds):
    players = [{'puuid': p, 'teamId': 'Red' if p in RED else 'Blue', 'characterId': JETT, 'gameName': p,
                'tagLine': 'T', 'stats': {'kills': 0, 'deaths': 0, 'assists': 0, 'roundsPlayed': len(rounds), 'score': 0}}
               for p in RED + BLUE]
    players.append({'puuid': 'obs', 'teamId': 'Neutral', 'isObserver': True, 'stats': {}})
    return {'matchInfo': {'matchId': 'm1', 'mapId': '/Game/Maps/Ascent/Ascent'}, 'players': players,
            'teams': [{'teamId': 'Red', 'won': True}, {'teamId': 'Blue', 'won': False}], 'roundResults': rounds}


def wipe(killers, victims, start=10_000):
    """One team kills the other in order, a second apart."""
    return [(start + 1000 * i, k, v) for i, (k, v) in enumerate(zip(killers, victims))]


class RecordingModel:
    """Stand-in win probability model that records the states it was asked about."""

    def __init__(self):
        self.states = []

    def attack_win_probability(self, state):
        self.states.append(dict(state))
        if state['def_alive'] == 0:
            return 1.0
        if state['atk_alive'] == 0:
            return 0.0
        return 0.5 + 0.08 * (state['atk_alive'] - state['def_alive']) + (0.1 if state['planted'] else 0.0)


def test_sides_follow_the_planter_in_every_half():
    rounds = [
        make_round(0, 'Red', plant=(30_000, 'r1'), code='Detonate'),
        make_round(1, 'Blue', kills=wipe(BLUE, RED)),
        make_round(12, 'Blue', plant=(30_000, 'b2'), code='Detonate'),
        make_round(13, 'Red', kills=wipe(RED, BLUE)),
        make_round(24, 'Red', kills=wipe(RED, BLUE)),
        make_round(25, 'Blue', kills=wipe(BLUE, RED)),
    ]
    attackers = determine_attackers(make_match(rounds))
    assert attackers == {0: 'Red', 1: 'Red', 12: 'Blue', 13: 'Blue', 24: 'Red', 25: 'Blue'}


def test_half_without_plants_is_opposite_of_other_half():
    rounds = [make_round(0, 'Blue', kills=wipe(BLUE, RED)),
              make_round(12, 'Red', plant=(30_000, 'r0'), code='Detonate')]
    assert determine_attackers(make_match(rounds)) == {0: 'Blue', 12: 'Red'}


def test_spike_counts_as_planted_only_after_the_plant():
    kills = [(20_000, 'r0', 'b0'), (40_000, 'r1', 'b1')]
    match = make_match([make_round(0, 'Red', kills=kills, plant=(30_000, 'r2'), code='Detonate')])
    model = RecordingModel()
    compute_match_swing(match, model)
    kill_states = [s for s in model.states if s['atk_alive'] + s['def_alive'] in (10, 9, 8)]
    before_plant = [s for s in kill_states if s['def_alive'] in (5, 4) and not s['planted']]
    after_plant = [s for s in kill_states if s['def_alive'] in (4, 3) and s['planted']]
    assert before_plant and after_plant
    # A round with no plant never uses post-plant states
    model = RecordingModel()
    compute_match_swing(make_match([make_round(0, 'Red', kills=wipe(RED, BLUE))]), model)
    assert not any(s['planted'] for s in model.states)


def test_kills_are_zero_sum():
    kills = [(10_000, 'r0', 'b0'), (12_000, 'b1', 'r1'), (15_000, 'r2', 'b1'), (20_000, 'r3', 'b2'),
             (21_000, 'r3', 'b3'), (25_000, 'r4', 'b4')]
    ledger = compute_match_swing(make_match([make_round(0, 'Red', kills=kills)]), RecordingModel())
    gained = sum(e['kill'] + e['assist'] for e in ledger.values())
    lost = sum(e['death'] for e in ledger.values())
    assert gained == pytest.approx(-lost)
    assert ledger['r0']['kills'] == 1 and ledger['b0']['deaths'] == 1


def test_kill_credit_is_split_by_damage():
    kills = [(10_000, 'r0', 'b0')]
    damage = [('r1', 'b0', 120), ('r0', 'b0', 30)]
    ledger = compute_match_swing(make_match([make_round(0, 'Red', kills=kills, damage=damage)]), RecordingModel())
    total = ledger['r0']['kill'] + ledger['r1']['assist']
    # killer weight 50 + 30 damage = 80, teammate 120 damage: 40% / 60%
    assert ledger['r0']['kill'] / total == pytest.approx(0.4)
    assert ledger['r1']['assist'] / total == pytest.approx(0.6)


def test_utility_assist_gets_credit():
    kills = [(10_000, 'r0', 'b0', ['r4'])]
    ledger = compute_match_swing(make_match([make_round(0, 'Red', kills=kills)]), RecordingModel())
    assert ledger['r4']['assist'] > 0


def test_traded_death_earns_a_share_of_the_trade():
    kills = [(10_000, 'b0', 'r0'), (11_500, 'r1', 'b0'), (40_000, 'b1', 'r2'), (50_000, 'r3', 'b1')]
    ledger = compute_match_swing(make_match([make_round(0, 'Red', kills=kills)]), RecordingModel())
    assert ledger['r0']['assist'] > 0 and ledger['r0']['traded_deaths'] == 1
    # Too slow to be a trade
    assert ledger['r2']['assist'] == 0 and ledger['r2']['traded_deaths'] == 0


def test_plant_and_defuse_are_credited():
    kills = [(10_000, 'r0', 'b0')]
    match = make_match([make_round(0, 'Blue', kills=kills, plant=(30_000, 'r1'), defuse=(60_000, 'b2'),
                                   code='Defuse')])
    ledger = compute_match_swing(match, RecordingModel())
    assert ledger['r1']['objective'] > 0
    assert ledger['b2']['objective'] > 0


def test_kills_after_the_round_is_decided_are_ignored():
    kills = wipe(RED, BLUE) + [(60_000, 'b0', 'r0')]
    rounds = [make_round(0, 'Red', kills=kills[:5]), make_round(1, 'Red', plant=(30_000, 'r0'),
                                                                kills=[(80_000, 'b0', 'r0')], code='Detonate')]
    parsed = parse_match(make_match(rounds))
    assert all(k['time'] <= parsed['rounds'][1]['end_time'] for k in parsed['rounds'][1]['kills'])
    assert parsed['rounds'][1]['kills'] == []


def test_adra_uses_armor_uuids():
    kills = [(10_000, 'r0', 'b0')]
    match = make_match([make_round(0, 'Red', kills=kills, damage=[('r0', 'b0', 150), ('r0', 'b1', 40)])])
    damage_data = {'r0': 190}
    red0 = match['players'][0]
    red0['stats']['roundsPlayed'] = 1
    # heavy shield: a kill needs 150, so 40 damage is beyond the kill
    assert calculate_adra(red0, match, damage_data) == pytest.approx(40.0)


def test_rating_end_to_end_and_aggregation():
    rounds = [make_round(i, 'Red', kills=wipe(RED, BLUE)) for i in range(6)]
    ratings = osr.calculate_rating_with_player_info(make_match(rounds))
    assert len(ratings) == 10  # observers excluded
    top = ratings['r0_m1']
    assert set(top['swing_per_round']) == {'KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing'}
    assert top['rating'] > 0 > ratings['b0_m1']['rating']
    assert top['round_swing'] > 0 > ratings['b0_m1']['round_swing']
    # the breakdown adds up exactly to the rating
    assert sum(top['rating_breakdown'].values()) == pytest.approx(top['rating'])
    assert top['role'] == 'Duelist' and top['agent'] == 'Jett'
    agg = osr.aggregate_ratings(ratings)
    # six rounds of evidence: heavily shrunk toward zero but same sign
    assert 0 < agg['r0']['rating'] < agg['r0']['raw_rating']
    assert agg['r0']['rating_low'] < agg['r0']['rating'] < agg['r0']['rating_high']


def test_legacy_weights_argument_warns():
    rounds = [make_round(0, 'Red', kills=wipe(RED, BLUE))]
    with pytest.warns(DeprecationWarning):
        osr.calculate_rating(make_match(rounds), weights={'KillContrib': 1.0})
