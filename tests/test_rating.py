"""Behaviour tests for round parsing, Round Swing and the rating, on hand-built matches."""

import pytest

import open_soup_rating as osr
from open_soup_rating.core.rounds import determine_attackers, parse_match
from open_soup_rating.core.swing import compute_match_swing, SWING_KINDS
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


def make_match(rounds, match_id='m1', start=0, extra=()):
    """extra: puuids replacing the last players of Blue (a different opponent)."""
    blue = BLUE[:5 - len(extra)] + list(extra)
    players = [{'puuid': p, 'teamId': 'Red' if p in RED else 'Blue', 'characterId': JETT, 'gameName': p,
                'tagLine': 'T', 'stats': {'kills': 0, 'deaths': 0, 'assists': 0, 'roundsPlayed': len(rounds), 'score': 0}}
               for p in RED + blue]
    players.append({'puuid': 'obs', 'teamId': 'Neutral', 'isObserver': True, 'stats': {}})
    return {'matchInfo': {'matchId': match_id, 'mapId': '/Game/Maps/Ascent/Ascent', 'gameStartMillis': start},
            'players': players, 'teams': [{'teamId': 'Red', 'won': True}, {'teamId': 'Blue', 'won': False}],
            'roundResults': rounds}


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


def test_every_round_is_fully_accounted_for():
    """Each team's credits add up to (round result - win probability at round start)."""
    rounds = [
        make_round(0, 'Red', kills=[(10_000, 'r0', 'b0'), (12_000, 'b1', 'r1')], plant=(30_000, 'r2'),
                   code='Detonate'),
        make_round(1, 'Blue', kills=[(15_000, 'b0', 'r0'), (16_000, 'r3', 'b0', ['r4'])]),
        make_round(2, 'Blue', kills=[(5_000, 'r0', 'b4')], plant=(40_000, 'r1'), defuse=(70_000, 'b2'), code='Defuse'),
    ]
    model = RecordingModel()
    ledger = compute_match_swing(make_match(rounds), model)
    start = model.attack_win_probability({'atk_alive': 5, 'def_alive': 5, 'planted': False})
    red_attacking_result = sum([1, 0, 0]) - 3 * start
    red = sum(sum(e[k] for k in SWING_KINDS) for p, e in ledger.items() if p in RED)
    blue = sum(sum(e[k] for k in SWING_KINDS) for p, e in ledger.items() if p in BLUE)
    assert red == pytest.approx(red_attacking_result)
    assert red + blue == pytest.approx(0.0)


def test_holding_a_planted_spike_earns_hold_credit():
    kills = [(10_000, 'r0', 'b0')]
    match = make_match([make_round(0, 'Red', kills=kills, plant=(30_000, 'r1'), code='Detonate')])
    ledger = compute_match_swing(match, RecordingModel())
    assert all(ledger[p]['hold'] > 0 for p in RED)
    assert all(ledger[p]['hold'] < 0 for p in BLUE if p != 'b0')
    # the plant is conceded by the defenders still alive
    assert ledger['b1']['objective'] < 0 and ledger['b0']['objective'] == 0


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
    # attackers alive at the defuse share the conceded defuse; the planter also has the plant
    assert ledger['r1']['objective'] > ledger['r0']['objective']
    assert ledger['r0']['objective'] < 0
    assert ledger['b2']['objective'] > 0
    assert ledger['r1']['plants'] == 1 and ledger['b2']['defuses'] == 1


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
    assert set(top['swing_per_round']) == {'KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing', 'HoldSwing'}
    assert top['rating'] > 0 > ratings['b0_m1']['rating']
    # the components add up exactly to the rating, and ratings to rounds added
    assert sum(top['swing_per_round'].values()) == pytest.approx(top['rating'])
    assert top['rounds_added'] == pytest.approx(top['rating'] * 6 / 100)
    assert top['role'] == 'Duelist' and top['agent'] == 'Jett'
    # the average player is 0
    assert sum(r['rating'] for r in ratings.values()) == pytest.approx(0.0, abs=1e-9)

    season = osr.aggregate_ratings(ratings)
    # descriptive by default: exactly the player's rating over these rounds
    assert season['r0']['rating'] == pytest.approx(top['rating'])
    assert season['r0']['rating_low'] < season['r0']['rating'] < season['r0']['rating_high']
    shrunk = osr.aggregate_ratings(ratings, shrink=True)
    assert 0 < shrunk['r0']['rating'] < season['r0']['rating']


def test_series_grouping():
    rounds = [make_round(i, 'Red', kills=wipe(RED, BLUE)) for i in range(3)]
    hour = 60 * 60 * 1000
    matches = [
        make_match(rounds, 'map1', start=0),
        make_match(rounds, 'map2', start=hour),
        make_match(rounds, 'map3', start=2 * hour, extra=['sub']),     # one substitute: same series
        make_match(rounds, 'other', start=2 * hour, extra=['x1', 'x2', 'x3']),  # a different opponent
        make_match(rounds, 'map4', start=9 * hour),                      # next day's series
    ]
    ratings = osr.calculate_rating(matches)
    series = osr.find_series(ratings)
    assert series['map1'] == series['map2'] == series['map3'] == 'map1'
    assert series['other'] == 'other' and series['map4'] == 'map4'
    per_series = osr.aggregate_ratings(ratings, by='series')
    assert per_series['r0_map1']['maps'] == 3 and per_series['r0_map1']['group'] == 'map1'


def test_legacy_weights_argument_warns():
    rounds = [make_round(0, 'Red', kills=wipe(RED, BLUE))]
    with pytest.warns(DeprecationWarning):
        osr.calculate_rating(make_match(rounds), weights={'KillContrib': 1.0})
