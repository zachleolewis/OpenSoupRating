# Open Soup Rating: Open-Source Valorant Rating System

<p align="center">
  <a href="https://github.com/zachleolewis/OpenSoupRating/blob/main/LICENSE.md">
    <img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License: AGPL v3">
  </a>
  <a href="https://github.com/zachleolewis/OpenSoupRating">
    <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  </a>
  </a>
</p>

<p align="center">
  <em>Licensed under <a href="LICENSE.md">GNU AGPLv3</a> • <a href="TRADEMARK.md">Trademark Policy</a></em>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Data Requirements](#data-requirements)
- [Component Calculations](#component-calculations)
- [Rating Formula](#rating-formula)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Customization](#customization)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Open Soup Rating is an open-source implementation of a Valorant rating system inspired by Riot's VLR (Valorant Leaderboard Rating). It calculates player ratings based on match performance, considering factors like kills, deaths, assists, damage, economic advantages, and situational impacts (XvX scenarios).

The system breaks down player performance into components and combines them using fixed weights to calculate ratings that align with official VLR scores.


## Data Requirements

The system requires match data from Riot's API, including:
- Player stats (kills, deaths, assists, rounds played)
- Damage events per player (extracted into `damage_data`: match_id → player_puuid → total_damage_dealt)
- Round results (winning team, plant/defuse times)
- Economic data (loadout values)
- XvX win probabilities (pre-computed from historical data)

### Required Data Files

#### `loadout_cost_analysis.json`
Contains win rates for different economic matchups between teams. Each entry represents a comparison like "Force Buy vs Eco Round" with:
- `win_rate`: Probability of the first team winning
- `total_engagements`: Number of rounds with this matchup
- `wins`/`losses`: Raw counts
This data is used to scale kill/death impacts based on economic advantage.

#### `xvx_breakdown_data.json`
Contains pre-computed win probabilities for different player count scenarios in various game situations. Includes data for:
- Attacker vs Defender scenarios (with/without spike planted)
- Different player counts (5v5, 4v4, 3v3, etc.)
- Win probabilities like `atk_no_spike > 5v4`: 0.71 (attackers with 5 players vs defenders with 4 have 71% win chance when no spike planted)
This data quantifies the situational importance of kills based on current game state and player advantage.

#### `weights.json`
Contains the four weights used in the rating formula as an array: [KillContrib_weight, DeathContrib_weight, APR_weight, ADRA_weight].
- Current values: [0.431, 0.431, 0.052, 0.085]
- KillContrib and DeathContrib have equal weights (43.1% each)
- APR and ADRA have lower weights (5.2% and 8.5% respectively)
- **Important:** Modifying these values will change how the rating system weights different performance aspects. The system will automatically use updated weights from this file.

---

## Component Calculations

The rating system combines four main components, each measuring different aspects of player performance:

### 1. Adjusted Damage per Round (ADRA)

**Formula:** `ADRA = (total_damage - expected_kill_damage) / rounds_played`

**Logic:**
- `total_damage`: Sum of all damage dealt by the player in the match
- `expected_kill_damage`: Sum of expected damage for each kill based on victim's armor at the time of kill
  - Base damage per kill: 100
  - Armor bonus: Light/Regen armor adds 25, Heavy armor adds 50, No armor adds 0
  - Each kill has its own expected damage value based on the specific victim's armor in that round
- The result is the average non-kill damage per round
- Ensures non-negative values (minimum 0)

**Purpose:** Measures a player's ability to deal damage beyond what's expected from kills, indicating skill in trading, area control, and utility usage. Uses only data from the specific match.

### 2. Assists Per Round (APR)

**Formula:** `APR = assists / rounds_played`

**Logic:**
- Simple ratio of assists to rounds played
- Captures a player's contribution through supportive actions

**Purpose:** Quantifies a player's ability to set up kills for teammates.

### 3. Kill Contributions

**Formula:** `KillContrib = Σ(kill_impacts × economic_modifier × post_round_modifier)`

Kill contributions measure the positive impact of eliminating enemy players, scaled by game context.

#### XvX Impact (Situational Importance)
- For each kill, calculates change in team win probability
- Uses pre-computed probabilities for different player counts (5v5, 4v4, 3v3, etc.)
- Considers spike plant status and attacker/defender roles
- **Formula:** `impact = new_win_probability - old_win_probability`

#### Economic Modifier (Resource Context)
- Scales kill value based on economic advantage/disadvantage
- **Formula:** `modifier = 2 × (1 - win_rate)`
- `win_rate`: Pre-computed win rate for the economic matchup
- Economic categories: Save Round, Eco Round, Force Buy, Anti-Eco, Full Buy, Operator Buy

#### Post-Round Modifier (Timing)
- Reduces impact by 50% if kill occurs after round end (~100 seconds)
- Prevents overvaluing kills that don't affect round outcome

### 4. Death Contributions

**Formula:** `DeathContrib = Σ(death_impacts × economic_modifier × post_round_modifier)`

Death contributions measure the negative impact of being eliminated, scaled by game context.

#### XvX Impact (Situational Importance)
- Same calculation as kills but with negative impact
- Measures how much the death hurt the team's win probability

#### Economic Modifier (Resource Context)
- Same scaling as kills but applied to death impact
- Accounts for how economic disadvantage amplifies death cost

#### Post-Round Modifier (Timing)
- Same timing adjustment as kills
- Deaths after round end have reduced impact

---

## Rating Formula

**Components:**
- Kill Contributions: Sum of all kill impacts (with XvX, economic, and timing modifiers)
- Death Contributions: Sum of all death impacts (with XvX, economic, and timing modifiers)
- APR: Assists per round
- ADRA: Adjusted damage per round

**Weighted Sum:** `rating = w1 × KillContrib + w2 × DeathContrib + w3 × APR + w4 × ADRA`

### Current Weight Rules
- Kill Contributions and Death Contributions have equal weights (0.431 each)
- These weights are higher than APR (0.052) and ADRA (0.085)
- This reflects the greater importance of kills and deaths compared to assists and damage in determining player rating
- Weights are fixed and based on historical analysis of VLR ratings

---

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Ensure you have match data in JSON format (from Riot API)

---

## Usage

### Data Preparation

1. **Match Data:** JSON files containing match info, player stats, and round results
2. **Economic Data:** `loadout_cost_analysis.json` with win rates for economic matchups
3. **XvX Data:** `xvx_breakdown_data.json` with win probabilities for different scenarios
4. **Weights Data:** `weights.json` with the rating formula weights

### Running the System

```python
from main import *

# Load data
matches = load_match_data('sample_data')
economic_data = load_economic_data('loadout_cost_analysis.json')
xvx_data = load_xvx_data('xvx_breakdown_data.json')

# Extract damage data from matches
# This creates a dictionary: match_id -> player_puuid -> total_damage_dealt
damage_data = extract_damage_data(matches)

# Calculate components
components = calculate_components(matches, economic_data, xvx_data, damage_data)

# Components are saved to components.json for analysis
```

### Simple Library Usage

For quick rating calculations on individual matches, use the `open_soup_rating_lib.py` library:

```python
from open_soup_rating_lib import calculate_open_soup_ratings

# Calculate ratings for a single match
ratings = calculate_open_soup_ratings("path/to/match.json")

# Print results
for puuid, rating in ratings.items():
    print(f"Player {puuid}: {rating:.4f}")
```

**Requirements for Library Usage:**
- Match JSON file (from Riot API)
- `loadout_cost_analysis.json` (economic data)
- `xvx_breakdown_data.json` (XvX probabilities)
- `weights.json` (rating formula weights)

**Note:** Library ratings use fixed weights and are relative within the match. They provide consistent scoring based on the established formula.

---

## API Reference

### Key Functions

- `calculate_open_soup_ratings(match_json_path)`: Calculate ratings for all players in a single match (library function)
- `load_match_data(path)`: Load match JSON files from directory
- `extract_damage_data(matches)`: Extract damage data from matches (returns match_id → player_puuid → total_damage)
- `calculate_adra(total_damage, expected_total, rounds)`: Compute ADRA
- `calculate_apr(stats)`: Compute APR
- `calculate_xvx_impact(match_data, round_data, match_players, xvx_data)`: Calculate kill impacts
- `get_economic_modifier(killer_loadout, victim_loadout, economic_data)`: Get economic scaling

---

## Customization

- **Weights:** Modify `weights.json` to change the importance of different rating components (kills/deaths vs assists/damage)
- **Economic Data:** Update `loadout_cost_analysis.json` with new win rates
- **XvX Data:** Modify `xvx_breakdown_data.json` for different maps or patches
- **Modifiers:** Extend `apply_post_round_modifier` for new rules

---

## Contributing

- Keep the codebase organized and simple
- Add to the CHANGELOG.md with all updates to the codebase
- Update the README.md with any new components or formula changes

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. See [LICENSE.md](LICENSE.md) for full license text.

### Key Points
- You can freely use, modify, and distribute this software
- Any modifications must also be licensed under AGPLv3
- Any changes to the rating logic (weighting, normalization, formula structure) must be made publicly available under AGPLv3
- You are not required to share unrelated backend code, UI components, or integrations
- Contact: zachleolewis@gmail.com

For trademark usage guidelines, see [TRADEMARK.md](TRADEMARK.md).

---

## Trademark Notice

**Open Soup Rating®** is a registered trademark of Zachary Lewis.

You are welcome to use, modify, and redistribute this software under the AGPLv3 license. However, any public distribution—original or modified—must continue to use the name **Open Soup Rating** (minor suffixes like **Open Soup Rating-Next** or **Open Soup Rating v2** are permitted).

To rebrand or rename this software in a public fork, you must obtain prior written permission from the trademark holder at zachleolewis@gmail.com.
