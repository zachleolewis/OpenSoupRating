# Round Parsing - turns a Riot match JSON into ordered round events
#
# Everything the rating needs is derived here once per match: which team was
# attacking in each round, the alive players and their loadouts, and the
# ordered kill / plant / defuse events up to the moment the round was decided.

from typing import Dict, List, Any, Optional, Tuple

ROUND_TIME_MS = 100_000
SPIKE_TIME_MS = 45_000
REGULATION_HALF = 12
REGULATION_ROUNDS = 24
TEAMS = ('Red', 'Blue')


def other_team(team: str) -> str:
    return 'Blue' if team == 'Red' else 'Red'


def match_players(match: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return {puuid: player} for the ten real players (observers and coaches removed)."""
    return {
        p['puuid']: p for p in match.get('players', [])
        if not p.get('isObserver', False) and p.get('teamId') in TEAMS
    }


def _side_block(round_num: int) -> Any:
    """Rounds that share an attacking team: each regulation half, then every overtime round alone."""
    if round_num < REGULATION_HALF:
        return 'h1'
    if round_num < REGULATION_ROUNDS:
        return 'h2'
    return round_num


def determine_attackers(match: Dict[str, Any]) -> Dict[int, str]:
    """
    Return {roundNum: attacking teamId}.

    Whoever plants the spike is always the attacker, so plants are the primary
    evidence. Rounds without a plant take their side from the rest of their half.
    If a half has no plants at all, it is the opposite of the other half. Overtime
    rounds alternate, starting with the team that attacked the first half.
    Riot's convention (Red attacks first) is only used when there are no plants
    anywhere in regulation.
    """
    players = match_players(match)
    rounds = match.get('roundResults', []) or []

    evidence: Dict[Any, str] = {}
    for r in rounds:
        planter = r.get('bombPlanter')
        if planter and planter in players:
            evidence.setdefault(_side_block(r['roundNum']), players[planter]['teamId'])

    if 'h1' in evidence:
        first_half = evidence['h1']
    elif 'h2' in evidence:
        first_half = other_team(evidence['h2'])
    else:
        first_half = 'Red'
    second_half = evidence.get('h2', other_team(first_half))

    attackers = {}
    for r in rounds:
        n = r['roundNum']
        block = _side_block(n)
        if block in evidence:
            attackers[n] = evidence[block]
        elif block == 'h1':
            attackers[n] = first_half
        elif block == 'h2':
            attackers[n] = second_half
        else:
            attackers[n] = first_half if (n - REGULATION_ROUNDS) % 2 == 0 else other_team(first_half)
    return attackers


def round_end_time(round_data: Dict[str, Any], kill_times: List[int]) -> int:
    """Time (ms since round start) at which the round outcome was decided."""
    code = round_data.get('roundResultCode')
    plant = round_data.get('plantRoundTime') if round_data.get('bombPlanter') else None
    if code == 'Defuse' and round_data.get('defuseRoundTime'):
        return int(round_data['defuseRoundTime'])
    if code == 'Detonate' and plant is not None:
        return int(plant) + SPIKE_TIME_MS
    if code == 'Elimination' and kill_times:
        return max(kill_times)
    # Timer expiry or unknown codes: last relevant moment of the round.
    return max([ROUND_TIME_MS] + kill_times)


def parse_round(round_data: Dict[str, Any], attacker_team: str,
                players: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Collect the events of one round in time order, cut at the moment it was decided."""
    loadout: Dict[str, int] = {}
    damage: Dict[Tuple[str, str], int] = {}
    kills = []
    for ps in round_data.get('playerStats', []) or []:
        puuid = ps.get('puuid')
        if puuid not in players:
            continue
        loadout[puuid] = int((ps.get('economy') or {}).get('loadoutValue', 0) or 0)
        for d in ps.get('damage', []) or []:
            if isinstance(d, dict) and d.get('receiver'):
                key = (puuid, d['receiver'])
                damage[key] = damage.get(key, 0) + int(d.get('damage', 0) or 0)
        for k in ps.get('kills', []) or []:
            kills.append({
                'time': int(k.get('timeSinceRoundStartMillis', 0) or 0),
                'killer': k.get('killer'),
                'victim': k.get('victim'),
                'assistants': list(k.get('assistants') or []),
                'damage_type': (k.get('finishingDamage') or {}).get('damageType'),
            })
    kills.sort(key=lambda k: k['time'])

    end = round_end_time(round_data, [k['time'] for k in kills])
    planted = bool(round_data.get('bombPlanter'))
    plant = None
    if planted:
        plant = {'time': int(round_data.get('plantRoundTime') or 0), 'player': round_data['bombPlanter']}
    defuse = None
    if round_data.get('bombDefuser') and round_data.get('defuseRoundTime'):
        defuse = {'time': int(round_data['defuseRoundTime']), 'player': round_data['bombDefuser']}

    # Kills after the outcome was decided (exit frags after a detonation, etc.) change nothing.
    kills = [k for k in kills if k['time'] <= end and k['damage_type'] != 'Bomb']

    winner = round_data.get('winningTeam')
    return {
        'num': round_data['roundNum'],
        'attackers': attacker_team,
        'defenders': other_team(attacker_team),
        'attackers_won': None if winner not in TEAMS else winner == attacker_team,
        'result_code': round_data.get('roundResultCode'),
        'loadout': loadout,
        'damage': damage,
        'kills': kills,
        'plant': plant,
        'defuse': defuse,
        'end_time': end,
        'participants': set(loadout),
    }


def parse_match(match: Dict[str, Any]) -> Dict[str, Any]:
    """Parse every round of a match. Returns players, map and the ordered rounds."""
    players = match_players(match)
    attackers = determine_attackers(match)
    rounds = [
        parse_round(r, attackers[r['roundNum']], players)
        for r in match.get('roundResults', []) or []
    ]
    return {
        'match_id': match.get('matchInfo', {}).get('matchId'),
        'map_id': match.get('matchInfo', {}).get('mapId'),
        'players': players,
        'rounds': rounds,
    }


class RoundState:
    """Alive players, spike status and clock of a round at one moment."""

    def __init__(self, parsed_round: Dict[str, Any], players: Dict[str, Dict[str, Any]], map_id: Optional[str]):
        self.round = parsed_round
        self.map_id = map_id
        team_of = {p: players[p]['teamId'] for p in parsed_round['participants']}
        self.side_of = {p: ('atk' if t == parsed_round['attackers'] else 'def') for p, t in team_of.items()}
        self.alive = {'atk': set(), 'def': set()}
        for p, side in self.side_of.items():
            self.alive[side].add(p)
        self.time = 0
        self.plant_time: Optional[int] = None

    @property
    def planted(self) -> bool:
        return self.plant_time is not None

    def time_left(self) -> float:
        """Fraction of the relevant clock left: round timer before the plant, spike timer after."""
        if self.planted:
            left = SPIKE_TIME_MS - (self.time - self.plant_time)
            return max(0.0, min(1.0, left / SPIKE_TIME_MS))
        return max(0.0, min(1.0, (ROUND_TIME_MS - self.time) / ROUND_TIME_MS))

    def loadout(self, side: str) -> int:
        return sum(self.round['loadout'].get(p, 0) for p in self.alive[side])

    def features(self) -> Dict[str, Any]:
        return {
            'atk_alive': len(self.alive['atk']),
            'def_alive': len(self.alive['def']),
            'planted': self.planted,
            'time_left': self.time_left(),
            'atk_loadout': self.loadout('atk'),
            'def_loadout': self.loadout('def'),
            'map_id': self.map_id,
        }
