# Open Soup Rating (OSR)

An open-source rating system for Valorant player performance. OSR measures how
much each player moved their team's chance of winning rounds. It credits the
kills, assists, trades, deaths, plants and defuses that changed the round, and
reports everything in one unit you can read directly.

> **2.0 is a rewrite.** Version 1.1.1 had bugs that corrupted most ratings
> (sides swapped in about half of all rounds, the spike always treated as
> planted, broken economy lookups, and pip installs that couldn't find their
> data). See [CHANGELOG.md](CHANGELOG.md) for what was wrong and how 2.0 was
> validated.

## Table of Contents

- [How OSR Works](#how-osr-works)
- [Reading the Numbers](#reading-the-numbers)
- [Validation](#validation)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Output](#output)
- [Recalibrating on Your Own Data](#recalibrating-on-your-own-data)
- [Project Structure](#project-structure)
- [Library Usage](#library-usage)
- [Data Requirements](#data-requirements)
- [Limitations](#limitations)
- [License](#license)

## How OSR Works

### 1. Round win probability

At any moment of a round, OSR estimates P(attackers win the round) from:

- players alive on each side (every 5v5 … 1v1 cell has its own estimate)
- whether the spike is planted
- time left on the clock that matters: the round timer before the plant, the
  spike timer after it
- the loadout value still alive on each side
- the map

It's a logistic model fitted on round states from 25,086 professional maps
(`open_soup_rating/data/wp_model.json`). On the newest 20% of maps, held out
from fitting, its log loss is 0.452. The 1.x lookup table scored 0.491 as
shipped and 0.479 even when used correctly.

### 2. Round Swing

OSR walks through every round in time order and books the change in win
probability caused by each event:

| Event | Who gets the swing |
|---|---|
| Kill | The killing team's gain is split: the killer gets 50 + their damage on the victim; teammates who damaged the victim get their damage; utility-only assisters (flashes, stuns, reveals) get 30; teammates the victim killed within the last 3 s (traded deaths) get 30. |
| Death | The victim is charged the full loss for their team. |
| Plant | The planter gets the attackers' gain from getting the spike down. |
| Defuse | The defuser gets the defenders' remaining gain. |

Kills are zero-sum: what one team gains, the other loses. Kills after the round
was decided (exit frags after a detonation, and so on) change nothing and count
for nothing.

Per player, this gives four components: **KillSwing, AssistSwing, DeathSwing
and ObjectiveSwing**. Their sum is the player's **Round Swing**, a faithful
record of what happened in that match.

### 3. OSR

Round Swing is accurate but noisy. A clutch kill and an opening kill take the
same aim, yet one carries far more win probability. Sports analytics has the
same split: baseball's win probability added describes a game, but rate stats
predict a player better. OSR therefore combines:

- the four Round Swing components
- kills and deaths per round
- damage dealt and damage taken per round

Each input is weighted by how well it predicts the player's Round Swing in
*other* matches (`rating_weights` in `open_soup_rating/data/rating_params.json`,
fitted by `tools/calibrate.py`). Inputs that are mostly leverage luck get little
weight; stable skill signals get more. The result stays in Round Swing units.

Because kills and damage move together, individual weights can shift a lot
between calibrations while the rating barely changes. Read
`rating_breakdown` as a whole rather than one weight at a time.

## Reading the Numbers

Every rating is in **percentage points of a round won per round played**, with
**0 = the average player**.

- `rating` = **+2.0**: this performance is worth about 2% more round wins per
  round than an average player would add. Over a 24-round map, that's roughly
  half a round.
- `round_swing`: the same unit, but literally what happened in this match.
- `role_adjusted_rating`: `rating` relative to the average player on the same
  role (duelist, initiator, controller, sentinel).

A single map is mostly noise: the spread of single-map ratings is several times
the spread of true player levels. When rating players, aggregate across matches
with `aggregate_ratings()` (or `osr calculate DIR --aggregate`). It shrinks each
player toward average according to how many rounds they've played: about 200
rounds count as much as the prior. It also returns a 90% interval.

## Validation

All of these numbers come from fitting on maps before 2026-04-06 and testing on
the 5,018 maps after it.

| | 1.1.1 | 2.0 OSR | 2.0 Round Swing | (K−D)/round |
|---|---|---|---|---|
| Split-half reliability (1,597 players with 40+ maps) | 0.676 | **0.733** | 0.593 | 0.750 |
| Predicting held-out map winners from earlier ratings (AUC) | 0.610 | **0.619** | 0.594 | 0.626 |
| Team average vs same-map round differential (r) | 0.909 | **0.940** | 0.922 | 0.949 |

OSR 2.0 is better than 1.1.1 on every measure. The reliability gain is clear:
+0.057, 95% CI [+0.037, +0.078]. Plain (K−D)/round remains slightly more
stable and slightly more predictive of future results (−0.018 reliability,
−0.007 AUC). OSR's added value is attribution: it shows *where* a player's
impact came from (opening kills vs. clean-up, assists, trades, objectives) in
a unit you can read, not raw predictive power. Adjusting for opponent strength
is the most promising next step.

## Installation

### Requirements
- Python 3.9+
- JSON match data from the Riot Games API

### Quick Installation (Recommended)

```bash
pip install open-soup-rating
```

### Development Setup

```bash
git clone https://github.com/zachleolewis/OpenSoupRating.git
cd OpenSoupRating
pip install -e .[dev]
pytest
```

## Quick Start

### Command Line Interface

```bash
# Rate every player in one match
osr calculate match.json --pretty

# Rate a folder of matches (.json or .json.gz) and save per-match results
osr calculate matches/ --output ratings.json

# One shrunk rating per player across all matches, best first
osr calculate matches/ --aggregate --pretty

# Same, relative to each player's role
osr calculate matches/ --aggregate --role-adjusted

# List components / version
osr list-components
osr version
```

### Python

```python
import open_soup_rating as osr

# Per-match ratings with names and box scores
ratings = osr.calculate_rating_with_player_info("matches/")

# One rating per player across all matches
players = osr.aggregate_ratings(ratings)
for puuid, p in sorted(players.items(), key=lambda kv: -kv[1]['rating'])[:10]:
    print(f"{p['name']:24s} {p['rating']:+.2f}  [{p['rating_low']:+.2f}, {p['rating_high']:+.2f}]  {p['maps']} maps")
```

## Output

`calculate_rating` returns one entry per player per match, keyed
`"{puuid}_{matchId}"`:

```python
{
  "rating": 1.84,                  # OSR, percentage points of a round won per round (0 = average)
  "role_adjusted_rating": 1.91,    # relative to the player's role
  "round_swing": 3.10,             # what actually happened, same unit
  "swing_per_round": {             # the four Round Swing components
    "KillSwing": 12.4, "AssistSwing": 1.6, "DeathSwing": -10.2, "ObjectiveSwing": 0.2
  },
  "rating_breakdown": {...},       # each input's contribution; sums exactly to "rating"
  "components": {...},             # every registered component, incl. APR and ADRa
  "rounds_played": 22, "kills": 19, "deaths": 14, "assists": 5,
  "traded_deaths": 4, "first_kills": 4, "first_deaths": 2, "kast": 0.77, "adr": 151.2,
  "agent": "Jett", "role": "Duelist",
  "puuid": "...", "match_id": "..."
}
```

`calculate_rating_with_player_info` adds a `player_info` block (name, tag and
Riot box score).

`aggregate_ratings` returns one entry per player:

```python
{
  "name": "Player#TAG", "maps": 14, "rounds_played": 312, "main_role": "Initiator",
  "raw_rating": 2.71,              # rounds-weighted average of per-match ratings
  "rating": 1.65,                  # shrunk toward average by sample size
  "rating_low": 0.53, "rating_high": 2.77   # 90% interval
}
```

### Components

| Component | Meaning | In the rating? |
|---|---|---|
| `KillSwing` | Killer's share of the win probability gained by their kills | yes |
| `AssistSwing` | Share of teammates' kills earned through damage, utility assists and being traded | yes |
| `DeathSwing` | Win probability the team lost when the player died (negative) | yes |
| `ObjectiveSwing` | Win probability gained by planting or defusing | yes |
| `APR` | Assists per round | reported only |
| `ADRa` | Damage beyond what the player's own kills needed, per round | reported only |

## Recalibrating on Your Own Data

The shipped calibration comes from professional matches (VCT, Challengers,
Game Changers; patches 8.00–13.08). To rate a different population, such as
Premier or ranked, refit on matches from that population:

```bash
pip install -e .[calibrate]
python tools/calibrate.py path/to/matches --holdout 0.2 --workers 8
```

This rewrites `open_soup_rating/data/wp_model.json` and `rating_params.json`.
Options:
- `--min-patch` sets the oldest patch to use (default 8.0).
- `--before YYYY-MM-DD` fits only on older maps, for backtests.
- `--out DIR` writes somewhere else.

You can then pass that directory as `config_path` to use it without
overwriting the defaults:

```python
osr.calculate_rating("matches/", config_path="my_calibration/")
```

## Project Structure

```
OpenSoupRating/
├── main.py                          # Interactive entry point
├── CHANGELOG.md                     # Release notes
├── tools/
│   └── calibrate.py                 # Fits the win probability model and rating constants
├── open_soup_rating/
│   ├── core/
│   │   ├── rounds.py                # Match parsing: sides, events, round end
│   │   ├── win_probability.py       # Round win probability model
│   │   ├── swing.py                 # Round Swing ledger and kill-credit split
│   │   ├── rating_model.py          # Rating inputs and weights
│   │   ├── rating_calculator.py     # calculate_rating, aggregate_ratings, get_components
│   │   ├── game_content.py          # Agent roles and armor values
│   │   └── component_registry.py    # Component registration
│   ├── components/                  # KillSwing, AssistSwing, DeathSwing, ObjectiveSwing, APR, ADRa
│   ├── data/
│   │   ├── wp_model.json            # Win probability coefficients
│   │   ├── rating_params.json       # Rating weights, centring, role baselines, shrinkage
│   │   ├── game_content.json        # Agent → role, armor UUID → shield value
│   │   └── loader.py                # Match loading (.json / .json.gz)
│   └── utils/                       # Configuration and validation
└── tests/
```

## Library Usage

### Core Functions

- `calculate_rating(match_data, components_to_use=None, config_path=None, wp_model=None)` returns per-match ratings.
- `calculate_rating_with_player_info(...)` does the same, plus name, tag and box score.
- `aggregate_ratings(ratings, role_adjusted=False, interval=0.9)` returns one shrunk rating per player.
- `get_components(match_data, component_names=None)` returns raw component values only.
- `compute_match_swing(match)` returns the raw Round Swing ledger for one match.
- `WinProbabilityModel.load(path=None)` loads the win probability model, for your own analysis.

`match_data` can be a file, a directory, a match dict or a list of match dicts.

### Custom Components

Custom components are calculated and reported alongside the rating. They do
not change the rating itself.

```python
def calculate_headshot_rate(player, match, damage_data, economic_data, xvx_data, **kwargs):
    """Headshots as a share of all hits."""
    heads = hits = 0
    for rnd in match["roundResults"]:
        for ps in rnd["playerStats"]:
            if ps["puuid"] == player["puuid"]:
                for d in ps.get("damage", []):
                    heads += d.get("headshots", 0)
                    hits += d.get("headshots", 0) + d.get("bodyshots", 0) + d.get("legshots", 0)
    return heads / hits if hits else 0.0

osr.add_component("HeadshotRate", calculate_headshot_rate)
ratings = osr.calculate_rating("match.json")   # components now include HeadshotRate
```

Components also receive `swing` (the match's Round Swing ledger) and `parsed`
(the parsed rounds) as keyword arguments.

## Data Requirements

OSR reads Riot Games API match JSON. It uses:

- `matchInfo.matchId` and `matchInfo.mapId`
- `players[]`: `puuid`, `teamId`, `characterId`, `stats`; observers are ignored
- `roundResults[]`:
  - `roundNum`, `winningTeam`, `roundResultCode`
  - `bombPlanter`, `plantRoundTime`, `bombDefuser`, `defuseRoundTime`
  - `playerStats[].kills[]`: `timeSinceRoundStartMillis`, `killer`, `victim`, `assistants`, `finishingDamage`
  - `playerStats[].damage[]`: `receiver`, `damage`
  - `playerStats[].economy`: `loadoutValue`, `armor`

## Limitations

- **No opponent adjustment.** A player who farms weaker teams looks better than
  they are. Compare players who faced similar opposition.
- **Position isn't used.** Kill and plant locations are in the data, but the
  win probability model doesn't use them yet.
- **Ultimates and utility aren't observed** beyond utility assists.
- **Calibration population matters.** The default constants come from pro play.
  Recalibrate for other levels.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests (`pytest`)
4. Submit a pull request

## License

This project is licensed under the GNU Affero General Public License v3.0
(AGPL-3.0). See [LICENSE.md](docs/LICENSE.md) for the full text.

---

**Open Soup Rating**: transparent, data-driven Valorant performance analysis.
