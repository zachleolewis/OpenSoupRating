# Open Soup Rating (OSR)

An open-source rating system for Valorant player performance. OSR measures how
much each player moved their team's chance of winning rounds. It credits the
kills, assists, trades, deaths, plants, defuses and holds that changed each
round, and reports everything in one unit that reads the same for a map, a
series or a season.

> **2.x is a rewrite.** Version 1.1.1 had bugs that corrupted most ratings
> (sides swapped in about half of all rounds, the spike always treated as
> planted, broken economy lookups, and pip installs that couldn't find their
> data). See [CHANGELOG.md](CHANGELOG.md) for what was wrong and how the new
> version was validated.

## Table of Contents

- [How OSR Works](#how-osr-works)
- [Reading the Numbers](#reading-the-numbers)
- [Maps, Series and Seasons](#maps-series-and-seasons)
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

### 2. Round Swing: every change in win probability goes to someone

OSR walks through every round in time order and credits each change in win
probability to the players responsible:

| Component | What it credits |
|---|---|
| **KillSwing** | The killer's share of the win probability a kill gained. |
| **AssistSwing** | Teammates' shares of that kill. Credit is split by: the killer gets 50 + their damage on the victim; teammates who damaged the victim get their damage; utility-only assisters (flashes, stuns, reveals) get 30; a teammate the victim killed within the last 3 s (a traded death) gets 30. |
| **DeathSwing** | The full loss the player's team took when they died. |
| **ObjectiveSwing** | The planter's or defuser's gain; the other side's alive players share the plant or defuse they conceded. |
| **HoldSwing** | Win probability that moved while nobody got a kill or objective, shared by each side's alive players. This covers defenders holding as the round clock runs, attackers sitting on a planted spike, and the final resolution of the round (a spike holding to detonation, a failed retake, time running out). |

**The rating is the sum of these five components, per round.** Nothing is
weighted or rescaled.

Everything is zero-sum. In every round, a team's credits add up exactly to its
result minus its win probability when the round started. Kills after the round
was decided (exit frags after a detonation, and so on) change nothing and
count for nothing.

Because the round starts from each team's actual economy, winning an eco round
is worth a lot and beating an eco is worth little. Killing a player with a
rifle and heavy shields moves the round more than killing one on a pistol.

## Reading the Numbers

Every rating is in **percentage points of a round won per round played**, with
**0 = the average player**.

- `rating` = **+5.0**: over these rounds, the player added 5% of a round-win
  per round. Over a 24-round map, that's 1.2 rounds.
- `rounds_added`: the same thing as a total, in rounds.
- `role_adjusted_rating`: `rating` relative to the average player on the same
  role. Role averages are close together: the spread between them is about
  0.3 points, against a single-map spread of about 4.8.

The five components always add up to `rating`, and a team's `rounds_added`
add up to how many more rounds it won than its round-start chances predicted.

## Maps, Series and Seasons

OSR is the same quantity at every level, just over more rounds:

```python
ratings = osr.calculate_rating_with_player_info("matches/")    # one entry per player per map

season  = osr.aggregate_ratings(ratings)                        # one entry per player
series  = osr.aggregate_ratings(ratings, by="series")           # one entry per player per series
events  = osr.aggregate_ratings(ratings, by={match_id: "Masters", ...})  # any grouping you like
```

- **Series** are found automatically. Maps belong together when both rosters
  match (at least 4 of 5 players on each side) and each map starts within
  3 hours of the previous one. `osr.find_series(ratings)` returns the grouping.
- **Luck band.** `rating_low` and `rating_high` show how far the rating could
  move from round-to-round luck alone (90% by default). On one map that band is
  wide; over a season it narrows.
- **What happened vs. how good.** The rating describes what happened.
  `shrink=True` (or `--shrink` on the CLI) instead estimates the player's
  underlying level, pulling small samples toward average. Use it for
  questions like "who is better", not "who played better".

## Validation

The table compares how well each rating reflects the maps it describes, and
how well it carries over to other maps. Ratings use the win probability model
fitted on maps before 2026-04-06. Stability and prediction are scored on the
5,018 maps after that date.

| | 1.1.1 | 2.1 | (K−D)/round |
|---|---|---|---|
| Team average vs. that map's round differential (r) | 0.909 | **0.975** | 0.949 |
| Map winner has the higher team average | 92.8% | **98.6%** | — |
| Gap between best and worst role average (fraction of map SD) | 0.171 | **0.063** | 0.245 |
| Split-half stability (1,597 players with 40+ maps) | **0.676** | 0.598 | 0.750 |
| Predicting held-out map winners from earlier ratings (AUC) | 0.610 | 0.610 | 0.626 |

**How to read this:**

- 2.1 is built to describe what happened, and it does that best.
- It is the most role-balanced of the three. Among the top 100 season ratings
  (players with 40+ maps), 40 are duelists against 28% of players overall. With
  1.1.1 it was 50, with K−D 64, and with ACS 94. The bottom 100 roughly match
  the population.
- It is less stable from one set of maps to the next than 1.1.1 or K−D. That
  follows directly from describing what happened: clutches and late-round
  plays really are worth more, and they don't repeat evenly. For an estimate of
  player level, use `shrink=True` over many maps.

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
# Rate every player in one map
osr calculate match.json --pretty

# Rate a folder of maps (.json or .json.gz) and save per-map results
osr calculate matches/ --output ratings.json

# One rating per player per series
osr calculate matches/ --series --pretty

# One rating per player over everything given (e.g. a season), best first
osr calculate matches/ --aggregate --pretty

# Relative to role, or as a level estimate
osr calculate matches/ --aggregate --role-adjusted
osr calculate matches/ --aggregate --shrink

# List components / version
osr list-components
osr version
```

### Python

```python
import open_soup_rating as osr

ratings = osr.calculate_rating_with_player_info("matches/")
season = osr.aggregate_ratings(ratings)
for p in sorted(season.values(), key=lambda p: -p['rating'])[:10]:
    print(f"{p['name']:24s} {p['rating']:+.2f}  ({p['rounds_added']:+.1f} rounds over {p['maps']} maps)")
```

## Output

`calculate_rating` returns one entry per player per map, keyed
`"{puuid}_{matchId}"`:

```python
{
  "rating": 4.21,                  # Round Swing per round, % of a round won (0 = average)
  "role_adjusted_rating": 4.31,    # relative to the player's role
  "rounds_added": 0.93,            # the same as a total, in rounds
  "swing_per_round": {             # the five components; they sum to "rating"
    "KillSwing": 12.4, "AssistSwing": 1.6, "DeathSwing": -10.2,
    "ObjectiveSwing": 0.3, "HoldSwing": 0.1
  },
  "components": {...},             # every registered component, incl. APR and ADRa
  "rounds_played": 22, "kills": 19, "deaths": 14, "assists": 5,
  "traded_deaths": 4, "first_kills": 4, "first_deaths": 2, "plants": 1, "defuses": 0,
  "kast": 0.77, "adr": 151.2,
  "agent": "Jett", "role": "Duelist", "team": "Red",
  "puuid": "...", "match_id": "...", "map_id": "/Game/Maps/Ascent/Ascent", "game_start": 1730000000000
}
```

`calculate_rating_with_player_info` adds a `player_info` block (name, tag and
Riot box score).

`aggregate_ratings` returns one entry per player (and per group, when grouped):

```python
{
  "name": "Player#TAG", "maps": 3, "rounds_played": 68, "main_role": "Initiator",
  "rating": 2.71,                  # Round Swing per round over these rounds
  "rounds_added": 1.84,
  "rating_low": -1.31, "rating_high": 6.73,   # 90% luck band
  "group": "<series id>"           # when grouped
}
```

### Components

| Component | Meaning | In the rating? |
|---|---|---|
| `KillSwing` | Killer's share of the win probability gained by their kills | yes |
| `AssistSwing` | Share of teammates' kills earned through damage, utility assists and being traded | yes |
| `DeathSwing` | Win probability the team lost when the player died (negative) | yes |
| `ObjectiveSwing` | Plants and defuses made, less a share of those conceded | yes |
| `HoldSwing` | Share of win probability that moved while alive with no kill or objective | yes |
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

This rewrites `open_soup_rating/data/wp_model.json` (the win probability model)
and `rating_params.json` (role averages and the variance behind luck bands and
shrinkage). Options:
- `--min-patch` sets the oldest patch to use (default 8.0).
- `--before YYYY-MM-DD` fits only on older maps, for backtests.
- `--out DIR` writes somewhere else.

To use a calibration without overwriting the defaults:

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
│   │   ├── rating_calculator.py     # calculate_rating, aggregate_ratings, find_series, get_components
│   │   ├── game_content.py          # Agent roles and armor values
│   │   └── component_registry.py    # Component registration
│   ├── components/                  # Swing components, APR, ADRa
│   ├── data/
│   │   ├── wp_model.json            # Win probability coefficients
│   │   ├── rating_params.json       # Role averages and variance constants
│   │   ├── game_content.json        # Agent → role, armor UUID → shield value
│   │   └── loader.py                # Match loading (.json / .json.gz)
│   └── utils/                       # Configuration and validation
└── tests/
```

## Library Usage

### Core Functions

- `calculate_rating(match_data, components_to_use=None, config_path=None, wp_model=None)` returns per-map ratings.
- `calculate_rating_with_player_info(...)` does the same, plus name, tag and box score.
- `aggregate_ratings(ratings, by=None, role_adjusted=False, interval=0.9, shrink=False)` combines maps into series, seasons or any grouping.
- `find_series(ratings)` returns `{match_id: series_id}`.
- `get_components(match_data, component_names=None)` returns raw component values only.
- `compute_match_swing(match)` returns the raw Round Swing ledger for one map.
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

Components also receive `swing` (the map's Round Swing ledger) and `parsed`
(the parsed rounds) as keyword arguments.

## Data Requirements

OSR reads Riot Games API match JSON. It uses:

- `matchInfo.matchId`, `matchInfo.mapId` and `matchInfo.gameStartMillis`
- `players[]`: `puuid`, `teamId`, `characterId`, `stats`; observers are ignored
- `roundResults[]`:
  - `roundNum`, `winningTeam`, `roundResultCode`
  - `bombPlanter`, `plantRoundTime`, `bombDefuser`, `defuseRoundTime`
  - `playerStats[].kills[]`: `timeSinceRoundStartMillis`, `killer`, `victim`, `assistants`, `finishingDamage`
  - `playerStats[].damage[]`: `receiver`, `damage`
  - `playerStats[].economy`: `loadoutValue`, `armor`

## Limitations

- **Utility is only partly visible.** Riot's data shows utility through
  assists and damage, not smokes, walls or information. Controller and
  sentinel value that never touches a kill shows up only through HoldSwing
  (their team's chances while they're alive). This is the main reason
  controllers are under-represented at the very top of season rankings.
- **HoldSwing is shared equally** among alive players. It credits being alive
  while your side's chances improve; it can't tell which alive player made that
  happen.
- **No opponent adjustment.** Rating well against weaker teams counts the same
  as against stronger ones.
- **Position isn't used.** Kill and plant locations are in the data, but the
  win probability model doesn't use them yet.
- **Calibration population matters.** The default constants come from pro
  play. Recalibrate for other levels.

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
