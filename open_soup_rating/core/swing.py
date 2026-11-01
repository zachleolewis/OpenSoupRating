# Round Swing Ledger
#
# Walks every round event in time order and books the change in round win
# probability it caused:
#   - kill:   the killing team's gain is split between the killer, teammates who
#             damaged the victim, utility-only assisters and traded teammates
#   - death:  the victim is charged the full loss for their team
#   - plant:  the planter gets the attackers' gain from getting the spike down
#   - defuse: the defuser gets the defenders' remaining gain
# Every kill is zero-sum: what one team gains, the other loses.

from typing import Dict, Any, Optional

from .rounds import parse_match, RoundState
from .win_probability import WinProbabilityModel, default_model

DEFAULT_CREDIT = {
    # Credit weights when splitting a kill's swing among the killing team.
    'killer_base': 50.0,       # added to the killer's own damage on the victim
    'utility_assist': 30.0,    # assisters who did no damage (flashes, stuns, reveals)
    'traded_teammate': 30.0,   # teammates the victim killed shortly before this kill
    'trade_window_ms': 3000,
}

SWING_KINDS = ('kill', 'assist', 'death', 'objective')

# Per-round counting stats kept alongside the swing (used by the rating weights).
BOX_STATS = ('kills', 'deaths', 'assists', 'traded_deaths', 'damage_dealt', 'damage_taken',
             'first_kills', 'first_deaths', 'survived', 'kast', 'multi_kills', 'plants', 'defuses')


def _empty_entry() -> Dict[str, Any]:
    entry = {kind: 0.0 for kind in SWING_KINDS}
    entry.update({stat: 0 for stat in BOX_STATS})
    entry['rounds'] = 0
    return entry


def _box_stats(parsed_round: Dict[str, Any], state: RoundState, ledger: Dict[str, Dict[str, Any]],
               round_kills: Dict[str, int], round_assists: set, traded: set, first: Optional[tuple]) -> None:
    """Book the counting stats of one finished round."""
    for (attacker, receiver), amount in parsed_round['damage'].items():
        a_side, r_side = state.side_of.get(attacker), state.side_of.get(receiver)
        if a_side and r_side and a_side != r_side:
            ledger[attacker]['damage_dealt'] += amount
            ledger[receiver]['damage_taken'] += amount
    if first:
        ledger[first[0]]['first_kills'] += 1
        ledger[first[1]]['first_deaths'] += 1
    for player in parsed_round['participants']:
        alive = player in state.alive[state.side_of[player]]
        kills = round_kills.get(player, 0)
        ledger[player]['survived'] += alive
        ledger[player]['multi_kills'] += kills >= 2
        ledger[player]['kast'] += bool(kills or player in round_assists or alive or player in traded)


def _team_wp(model: WinProbabilityModel, state: RoundState, side: str) -> float:
    p = model.attack_win_probability(state.features())
    return p if side == 'atk' else 1.0 - p


def _kill_shares(kill: Dict[str, Any], state: RoundState, parsed_round: Dict[str, Any],
                 recent_deaths: list, credit: Dict[str, Any]) -> Dict[str, float]:
    """Split weights for one kill among the killing side."""
    killer, victim = kill['killer'], kill['victim']
    side = state.side_of[killer]
    damage = parsed_round['damage']
    weights: Dict[str, float] = {}
    for player, player_side in state.side_of.items():
        if player_side != side:
            continue
        dealt = float(damage.get((player, victim), 0))
        if player == killer:
            weights[player] = credit['killer_base'] + dealt
        elif dealt > 0:
            weights[player] = dealt
    for player in kill['assistants']:
        if state.side_of.get(player) == side and player not in weights:
            weights[player] = credit['utility_assist']
    for death_time, dead, dead_killer in recent_deaths:
        if (dead_killer == victim and state.side_of.get(dead) == side
                and kill['time'] - death_time <= credit['trade_window_ms']):
            weights[dead] = weights.get(dead, 0.0) + credit['traded_teammate']
    total = sum(weights.values())
    return {p: w / total for p, w in weights.items()}


def compute_match_swing(match: Dict[str, Any], model: Optional[WinProbabilityModel] = None,
                        credit: Optional[Dict[str, Any]] = None,
                        parsed: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Return {puuid: ledger} where ledger holds the summed win-probability swing
    (in rounds, i.e. 1.0 = one whole round) for kills, assists, deaths and
    objectives, plus rounds played and the counting stats in BOX_STATS.
    """
    model = model or default_model()
    credit = {**DEFAULT_CREDIT, **(credit or {})}
    parsed = parsed or parse_match(match)
    ledger = {p: _empty_entry() for p in parsed['players']}

    for parsed_round in parsed['rounds']:
        state = RoundState(parsed_round, parsed['players'], parsed['map_id'])
        if not state.alive['atk'] or not state.alive['def']:
            continue
        for p in parsed_round['participants']:
            ledger[p]['rounds'] += 1

        events = [('kill', k['time'], k) for k in parsed_round['kills']]
        if parsed_round['plant'] and parsed_round['plant']['time'] <= parsed_round['end_time']:
            events.append(('plant', parsed_round['plant']['time'], parsed_round['plant']))
        if parsed_round['defuse']:
            events.append(('defuse', parsed_round['defuse']['time'], parsed_round['defuse']))
        order = {'plant': 0, 'kill': 1, 'defuse': 2}
        events.sort(key=lambda e: (e[1], order[e[0]]))

        recent_deaths = []
        round_kills: Dict[str, int] = {}
        round_assists: set = set()
        traded: set = set()
        first = None
        for kind, time, event in events:
            if not state.alive['atk'] or not state.alive['def']:
                if kind != 'defuse':
                    continue
            state.time = time

            if kind == 'plant':
                planter = event['player']
                before = _team_wp(model, state, 'atk')
                state.plant_time = time
                gain = _team_wp(model, state, 'atk') - before
                if planter in ledger:
                    ledger[planter]['objective'] += gain
                    ledger[planter]['plants'] += 1
                continue

            if kind == 'defuse':
                defuser = event['player']
                gain = 1.0 - _team_wp(model, state, 'def')
                if defuser in ledger:
                    ledger[defuser]['objective'] += gain
                    ledger[defuser]['defuses'] += 1
                continue

            victim, killer = event['victim'], event['killer']
            victim_side = state.side_of.get(victim)
            if victim_side is None or victim not in state.alive[victim_side]:
                continue
            victim_before = _team_wp(model, state, victim_side)
            state.alive[victim_side].discard(victim)
            # Never negative: e.g. the last attacker dying once the spike can no longer be defused.
            loss = max(0.0, victim_before - _team_wp(model, state, victim_side))

            ledger[victim]['deaths'] += 1
            ledger[victim]['death'] -= loss

            # Suicides, team kills and environmental deaths give nobody kill credit.
            if killer in state.side_of and state.side_of[killer] != victim_side:
                ledger[killer]['kills'] += 1
                round_kills[killer] = round_kills.get(killer, 0) + 1
                if first is None:
                    first = (killer, victim)
                for player in event['assistants']:
                    if state.side_of.get(player) == state.side_of[killer] and player != killer:
                        ledger[player]['assists'] += 1
                        round_assists.add(player)
                for player, share in _kill_shares(event, state, parsed_round, recent_deaths, credit).items():
                    ledger[player]['kill' if player == killer else 'assist'] += loss * share
                for death_time, dead, dead_killer in recent_deaths:
                    if (dead_killer == victim and state.side_of.get(dead) == state.side_of[killer]
                            and time - death_time <= credit['trade_window_ms']):
                        ledger[dead]['traded_deaths'] += 1
                        traded.add(dead)
            recent_deaths.append((time, victim, killer))

        _box_stats(parsed_round, state, ledger, round_kills, round_assists, traded, first)

    return ledger
