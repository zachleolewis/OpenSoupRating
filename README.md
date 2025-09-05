# Open Soup Rating (OSR)

A comprehensive, open-source rating system for Valorant player performance analysis. OSR provides accurate player ratings based on situational impact, economic factors, and statistical performance in competitive matches.

## Table of Contents

- [Overview](#overview)
- [The Rating Formula](#the-rating-formula)
- [Normalization and Weights](#normalization-and-weights)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Understanding the Components](#understanding-the-components)
- [Project Structure](#project-structure)
- [Library Usage](#library-usage)
- [Data Requirements](#data-requirements)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Contributing](#contributing)
- [License](#license)

## Overview

Open Soup Rating is designed to evaluate Valorant player performance beyond simple kill/death statistics. The system considers:

- **Situational Impact**: How kills and deaths affect round outcomes based on player counts (XvX situations)
- **Economic Factors**: The relative value of eliminations based on equipment loadouts
- **Performance Consistency**: Individual performance metrics like damage efficiency and assist rates
- **Round Context**: Whether the spike is planted and team positioning

### Key Features

- **Modular Design**: Easy to customize and extend with new components
- **Data-Driven**: Built using analysis of 44,080 player-match performances from North American Premier competitive play
- **Comprehensive**: Accounts for situational context that traditional stats miss
- **Open Source**: Fully transparent methodology and implementation

## The Rating Formula

The Open Soup Rating combines four main components through a weighted formula:

```
Final Rating = Σ(Component_i × Weight_i × Normalization_i) × Scaling_Factor
```

### Core Components

1. **Kill Contribution (KillContrib)** - Weight: 43.14%
   - Measures positive impact from eliminations
   - Based on XvX win probability changes and economic modifiers
   - Accounts for situational context (spike planted, player counts)

2. **Death Contribution (DeathContrib)** - Weight: 43.14%  
   - Measures negative impact from deaths
   - Uses same XvX methodology as kills but inverted
   - Balanced with kill contribution for net impact assessment

3. **Average Performance Rating (APR)** - Weight: 5.20%
   - Assists per round played
   - Measures teamwork and supporting play

4. **Average Damage per Round Adjusted (ADRa)** - Weight: 8.51%
   - Damage dealt above expected damage from kills
   - Accounts for armor values when calculating expected damage
   - Measures damage efficiency beyond securing eliminations

### XvX Impact Methodology

The core innovation of OSR is using actual win probabilities for different player count scenarios:

- **5v5 (no spike)**: 49.5% attacker win rate
- **5v4 (no spike)**: 71.0% attacker win rate  
- **4v4 (spike planted)**: 62.1% attacker win rate
- **3v2 (spike planted)**: 84.4% attacker win rate

When a player gets a kill, the system:
1. Determines the before/after XvX situation
2. Calculates the win probability change for their team
3. Applies economic modifiers based on equipment values
4. Weights the impact by the specific round context

## Normalization and Weights

### Statistical Foundation

The Open Soup Rating system was calibrated using comprehensive data from North American Premier competitive matches spanning Episode 9 Act 1 through Episode V25 Act 4. This dataset includes:

- **Total Matches**: 4,408 competitive matches
- **Player Performances**: 44,080 individual player-match combinations  
- **Competition Levels**: Contender (East/West) and Invite divisions
- **Time Period**: Multiple competitive seasons ensuring diverse meta representation

### Component Weights

The component weights were derived through statistical analysis to optimize rating accuracy:

```json
{
  "KillContrib": 0.4314443970577043,    // 43.14%
  "DeathContrib": 0.4314443970577043,   // 43.14%  
  "APR": 0.05202608006591386,           // 5.20%
  "ADRa": 0.08508512581867748           // 8.51%
}
```

**Weight Rationale:**
- **Kill/Death Contribution (86.28% combined)**: These components capture the most impactful moments in rounds - eliminations that directly change win probabilities
- **APR (5.20%)**: Supporting play through assists, while valuable, has less direct impact on round outcomes
- **ADRa (8.51%)**: Damage efficiency beyond kills provides context for consistent performance but is secondary to actual eliminations

### Normalization Parameters

All components are normalized to achieve a standard distribution (mean = 0, standard deviation = 1) based on the competitive dataset:

```json
{
  "KillContrib": {"mean": 2.916, "std": 3.614},
  "DeathContrib": {"mean": -2.916, "std": 2.129},
  "APR": {"mean": 0.282, "std": 0.517},
  "ADRa": {"mean": 66.121, "std": 69.760}
}
```

**Normalization Process:**
1. Calculate each component's raw value
2. Apply Z-score normalization: `(value - mean) / std`
3. Apply component weights to normalized values
4. Sum weighted components and apply final scaling

### Final Rating Scaling

The final rating undergoes additional scaling to produce interpretable values:

```json
{
  "base_rating": 1.0,
  "scaling_factor": 0.56,
  "mean": 1.0354,
  "std": 0.0898
}
```

This ensures that:
- **Average performance equals 0.0** (by Z-score normalization design)
- **Standard deviation equals 1.0** for meaningful statistical interpretation
- **Exceptional performances achieve positive ratings** (typically +1.5 to +6.4 range)
- **Poor performances receive negative ratings** (typically -1.5 to -3.3 range)
- **68% of players fall within ±1.0** (one standard deviation)
- **95% of players fall within ±2.0** (two standard deviations)

## Installation

### Requirements
- Python 3.8+
- JSON match data from Riot Games API

### Setup

1. Clone the repository:
```bash
git clone https://github.com/zachleolewis/OpenSoupRating.git
cd OpenSoupRating
```

2. Install as a package:
```bash
pip install -e .
```

3. Test the installation:
```bash
python main.py
```

## Quick Start

### Command Line Interface

Run the interactive calculator:
```bash
python main.py
```

Options include:
- Calculate ratings from match directories
- Extract individual components  
- List available components
- Save results to JSON files

### Python Library Usage

```python
import open_soup_rating as osr

# Calculate ratings for a single match
ratings = osr.calculate_rating("path/to/match.json")

# Calculate ratings with player information
detailed_ratings = osr.calculate_rating_with_player_info("path/to/match_directory/")

# Get individual component values
components = osr.get_components("path/to/match.json", ["KillContrib", "DeathContrib"])

print(f"Available components: {osr.list_components()}")
```

### Example Output

```python
{
  "player_puuid_match_id": {
    "rating": 0.845,
    "player_info": {
      "name": "PlayerName",
      "tagline": "TAG",
      "kills": 18,
      "deaths": 12,
      "assists": 7,
      "rounds_played": 24
    },
    "components": {
      "KillContrib": 3.24,
      "DeathContrib": -2.18,
      "APR": 0.29,
      "ADRa": 74.5
    },
    "normalized_components": {
      "KillContrib_norm": 0.492,
      "DeathContrib_norm": 0.492,
      "APR_norm": 0.015,
      "ADRa_norm": 0.120
    }
  }
}
```

## Understanding the Components

The Open Soup Rating system evaluates player performance through four distinct components, each capturing different aspects of competitive play. These components work together to provide a comprehensive assessment that goes far beyond traditional kill/death ratios.

### Kill Contribution (KillContrib)

**Purpose**: Measures the positive impact of eliminations based on situational context and economic factors.

**Methodology**: 
The system evaluates each kill by analyzing how it changes the round's win probability for the player's team. This goes beyond simply counting kills to assess their actual value in winning rounds.

**Calculation Process**:

1. **Pre-Kill Analysis**:
   - Determine alive player counts for both teams (e.g., 4v3, 5v2)
   - Check if spike is planted
   - Record round timing and context

2. **XvX Impact Calculation**:
   - Look up win probability for the pre-kill situation
   - Look up win probability for the post-kill situation
   - Calculate the probability change for the killer's team
   
   Example: A kill that changes 3v3 (49% win rate) to 3v2 (74.6% win rate) provides +25.6% win probability

3. **Economic Modifiers**:
   - Calculate the loadout value difference between killer and victim
   - Apply economic multipliers based on relative equipment investment
   - Higher-value eliminations (killing an expensive loadout with a cheap one) receive bonuses

4. **Final Component Value**:
   ```
   KillContrib = base_impact × economic_modifier
   ```

**Key Insights**:
- Eliminating an enemy with superior equipment provides additional value
- Spike planted status significantly affects the impact calculation

**Example Values**:
- Typical range: 0.0-9.1 points
- Median performance: ~2.8 points
- 75th percentile: ~3.7 points

### Death Contribution (DeathContrib)

**Purpose**: Measures the negative impact when a player dies, using the same sophisticated methodology as kill contribution.

**Methodology**:
Death Contribution is essentially the inverse of Kill Contribution, calculating how much a player's death hurts their team's chances of winning the round.

**Calculation Process**:

1. **Pre-Death Analysis**:
   - Record the XvX situation before the player dies
   - Note spike planted status and round timing
   - Assess the player's equipment loadout

2. **XvX Impact Calculation**:
   - Calculate win probability before death (e.g., 4v4 = 50.5%)
   - Calculate win probability after death (e.g., 3v4 = 27.0%)  
   - Determine probability loss for the player's team (-23.5%)

3. **Economic Impact**:
   - Factor in the value of equipment lost upon death
   - Consider the relative investment compared to the killer
   - Losing expensive equipment while the enemy has cheap gear increases the negative impact

4. **Final Component Value**:
   ```
   DeathContrib = -(base_impact × economic_modifier)
   ```

**Key Characteristics**:
**Key Characteristics**:
- Always produces negative values (deaths always hurt your team)
- Deaths with expensive equipment carry additional negative weight
- Balanced with KillContrib to show net round impact

**Example Values**:
- Typical range: -5.6 to 0.0 points
- Median performance: ~-2.3 points
- 25th percentile: ~-2.8 points

### Average Performance Rating (APR)

**Purpose**: Captures supporting play and teamwork through assist contributions.

**Simple but Meaningful**:
While APR appears straightforward, it provides crucial context about a player's role and impact beyond direct eliminations.

**Calculation**:
```python
APR = total_assists / rounds_played
```

**Why Assists Matter**:
- **Team Play Indicator**: High assist rates suggest good positioning and team coordination
- **Support Role Recognition**: Players who enable teammates get appropriate credit
- **Consistency Metric**: Shows reliable contribution across all rounds

**Important Notes**:
- Assists include both damage contributions and ability assists within the elimination time window
- Normalized across all competitive data to ensure fair weighting
- Lower weight (5.20%) reflects supportive rather than primary impact

**Example Values**:
- Typical range: 0.0-1.4 assists per round
- Median performance: ~0.2 assists per round
- 75th percentile: ~0.4 assists per round

### Average Damage per Round Adjusted (ADRa)

**Purpose**: Measures damage efficiency beyond what's expected from kills, indicating consistent performance and finishing ability.

**The Problem with Raw ADR**:
Traditional Average Damage per Round doesn't account for the fact that players with more kills naturally deal more damage. ADRa solves this by calculating damage efficiency relative to eliminations achieved.

**Calculation Process**:

1. **Expected Damage Calculation**:
   For each kill a player achieves, calculate expected damage based on victim's armor:
   ```python
   expected_damage_per_kill = {
       'No Armor': 100,
       'Light Armor': 125,  # 100 + 25
       'Heavy Armor': 150,  # 100 + 50
       'Regen Armor': 125   # 100 + 25
   }
   ```

2. **Total Expected Damage**:
   ```python
   total_expected = sum(expected_damage for each kill)
   ```

3. **ADRa Calculation**:
   ```python
   ADRa = max(0, (total_damage_dealt - total_expected) / rounds_played)
   ```

4. **Floor at Zero**: Negative values are set to 0 to ensure ADRa only measures positive damage efficiency

**What ADRa Reveals**:

- **High ADRa**: Player consistently damages multiple enemies, weakens targets for teammates, or finishes wounded opponents efficiently
- **Low ADRa**: Player tends to secure kills with minimal excess damage, potentially indicating good target selection or cleanup kills
- **Consistent High ADRa**: Indicates strong aim, positioning, and ability to apply pressure beyond just securing eliminations

**Example Values**:
- Typical range: 0.0-272.6 points
- Median performance: ~63.5 points
- 75th percentile: ~79.1 points

### Component Synergy

**Balanced Assessment**: The four components work together to provide a complete picture:

- **Kill/Death Contribution**: Measures round impact through eliminations
- **APR**: Recognizes teamwork and supporting play  
- **ADRa**: Assesses consistent damage pressure and efficiency

This multi-faceted approach ensures that different playstyles and roles are fairly evaluated within the competitive context.

## Project Structure

The Open Soup Rating system is organized into a clean, modular architecture that separates concerns and makes the codebase easy to understand and extend.

```
OpenSoupRating/
├── main.py                          # Command-line interface and entry point
├── README.md                        # This documentation
├── 
├── open_soup_rating/                # Main package directory
│   ├── __init__.py                  # Package initialization and public API
│   │
│   ├── core/                        # Core calculation engine
│   │   ├── __init__.py
│   │   ├── rating_calculator.py     # Main rating calculation logic
│   │   └── component_registry.py    # Component management system
│   │
│   ├── components/                  # Individual rating components
│   │   ├── __init__.py
│   │   ├── kill_contrib.py          # Kill contribution calculator
│   │   ├── death_contrib.py         # Death contribution calculator
│   │   ├── apr.py                   # Average Performance Rating
│   │   └── adra.py                  # Average Damage per Round Adjusted
│   │
│   ├── data/                        # Data loading and management
│   │   ├── __init__.py
│   │   └── loader.py                # Data loading utilities
│   │
│   └── utils/                       # Utility functions
│       ├── __init__.py
│       ├── config.py                # Configuration management
│       └── validation.py            # Data validation functions
│
├── data/                            # Configuration and reference data
│   ├── weights.json                 # Component weights
│   ├── normalization_params.json    # Statistical parameters
│   ├── xvx_data.json               # XvX win probabilities
│   └── loadout_cost_analysis.json  # Economic data
│
└── docs/                           # Additional documentation
    ├── LICENSE.md                  # Full license text
    └── TRADEMARK.md               # Trademark policy

```

### Key Directories Explained

#### `open_soup_rating/` - Main Package
The core library that can be imported and used in other projects. Contains all the calculation logic and utilities needed to compute ratings.

#### `open_soup_rating/core/` - Calculation Engine
- **`rating_calculator.py`**: Contains the main functions (`calculate_rating`, `get_components`) that orchestrate the rating calculation process
- **`component_registry.py`**: Manages the available rating components, handles dynamic loading and registration

#### `open_soup_rating/components/` - Rating Components
Each file contains the calculation logic for one rating component:
- **`kill_contrib.py`**: XvX-based kill impact calculation with economic modifiers
- **`death_contrib.py`**: XvX-based death impact calculation (inverse of kills)
- **`apr.py`**: Simple assists-per-round calculation  
- **`adra.py`**: Damage efficiency calculation with expected damage adjustment

#### `open_soup_rating/data/` - Data Management
- **`loader.py`**: Functions to load match data from files, directories, or data structures

#### `open_soup_rating/utils/` - Utilities
- **`config.py`**: Configuration loading and default values
- **`validation.py`**: Match data format validation

#### `data/` - Configuration Files
Contains the calibrated parameters derived from competitive match analysis:
- **`weights.json`**: The optimized weights for each component
- **`normalization_params.json`**: Statistical parameters for standardization
- **`xvx_data.json`**: Win probability data for all player count scenarios
- **`loadout_cost_analysis.json`**: Economic impact data for equipment valuations

### Architecture Benefits

**Modularity**: Each component is self-contained and can be easily modified or replaced
**Extensibility**: New components can be added without changing existing code
**Testability**: Individual components can be tested in isolation
**Maintainability**: Clear separation of concerns makes the codebase easy to understand
**Reusability**: Core library can be imported and used in other projects

### Adding Custom Components

The modular architecture makes it easy to add new rating components:

1. Create a new file in `open_soup_rating/components/`
2. Implement a function following the standard signature
3. The component will be automatically discovered and registered
4. Use in calculations by including it in the `components_to_use` parameter

This structure ensures that the Open Soup Rating system remains flexible and extensible while maintaining clean, understandable code.

Shows consistent damage output and finishing ability.

## Library Usage

### Core Functions

#### `calculate_rating(match_data, **kwargs)`
Calculates OSR ratings from match data.

**Parameters:**
- `match_data`: File path, directory path, or loaded match data
- `weights`: Custom component weights (optional)
- `normalization_params`: Custom normalization parameters (optional)
- `components_to_use`: List of components to include (optional)

#### `calculate_rating_with_player_info(match_data, **kwargs)`
Same as above but includes detailed player information in output.

#### `get_components(match_data, component_names=None, **kwargs)`
Extract individual component values without final rating calculation.

### Custom Components

Add your own rating components:

```python
def calculate_headshot_rate(player, match, damage_data, economic_data, xvx_data, **kwargs):
    """Calculate headshot percentage component."""
    stats = player.get('stats', {})
    total_kills = stats.get('kills', 0)
    headshots = stats.get('headshotKills', 0)
    
    if total_kills == 0:
        return 0.0
    
    return headshots / total_kills

# Register the component
osr.add_component('HeadshotRate', calculate_headshot_rate)

# Use in calculations  
ratings = osr.calculate_rating("match.json", components_to_use=['KillContrib', 'HeadshotRate'])
```

## Data Requirements

### Match Data Format

OSR requires JSON match data from the Riot Games API v2. Key required fields:

```json
{
  "matchInfo": {
    "matchId": "uuid",
    "mapId": "/Game/Maps/...",
    "gameVersion": "..."
  },
  "players": [
    {
      "puuid": "player_uuid", 
      "gameName": "PlayerName",
      "tagLine": "TAG",
      "teamId": "Blue",
      "stats": {
        "kills": 18,
        "deaths": 12, 
        "assists": 7,
        "roundsPlayed": 24
      }
    }
  ],
  "roundResults": [
    {
      "roundNum": 1,
      "playerStats": [
        {
          "puuid": "player_uuid",
          "kills": [{"victim": "victim_puuid", "timeSinceRoundStartMillis": 15000}],
          "damage": [{"receiver": "victim_puuid", "damage": 150}],
          "economy": {"loadoutValue": 4500, "armor": "Heavy"}
        }
      ]
    }
  ]
}
```

### Data Sources

The system works with:
- **Riot Games API**: Official tournament match data
- **Community APIs**: Third-party match data providers
- **Local Files**: Saved match data in JSON format

## Configuration

### Default Configuration

The system uses optimized weights and normalization parameters derived from tournament data:

```json
{
  "weights": {
    "KillContrib": 0.4314,
    "DeathContrib": 0.4314, 
    "APR": 0.0520,
    "ADRa": 0.0851
  },
  "normalization_params": {
    "KillContrib": {"mean": 2.889, "std": 3.614},
    "DeathContrib": {"mean": -2.360, "std": 2.129},
    "APR": {"mean": 0.282, "std": 0.517},
    "ADRa": {"mean": 66.121, "std": 69.760}
  }
}
```

### Custom Configuration

Override defaults by providing custom parameters:

```python
custom_weights = {
    'KillContrib': 0.40,
    'DeathContrib': 0.40,
    'APR': 0.10, 
    'ADRa': 0.10
}

ratings = osr.calculate_rating("match.json", weights=custom_weights)
```

## Advanced Features

### Batch Processing

Process multiple matches efficiently:

```python
# Directory of match files
ratings = osr.calculate_rating("tournament_matches/")

# List of match data
matches = [match1_data, match2_data, match3_data]
ratings = osr.calculate_rating(matches)
```

### Component Analysis

Analyze individual performance aspects:

```python
# Get only kill/death impact
kd_components = osr.get_components("match.json", ["KillContrib", "DeathContrib"])

# Analyze damage efficiency
damage_components = osr.get_components("match_dir/", "ADRa")

# Get all components
all_components = osr.get_components("match.json")
```

### Tournament Analysis

Example workflow for tournament evaluation:

```python
import open_soup_rating as osr

# Calculate all player ratings
tournament_ratings = osr.calculate_rating_with_player_info("tournament_data/")

# Find top performers
top_players = sorted(tournament_ratings.items(), 
                    key=lambda x: x[1]['rating'], reverse=True)

print("Top 10 Players:")
for i, (player_key, data) in enumerate(top_players[:10]):
    player_info = data['player_info']
    print(f"{i+1}. {player_info['name']}#{player_info['tagline']}: {data['rating']:.3f}")

# Save results
with open("tournament_results.json", "w") as f:
    json.dump(tournament_ratings, f, indent=2)
```

## Contributing

We welcome contributions to improve the Open Soup Rating system!

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass
5. Submit a pull request

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Write docstrings for all functions
- Include unit tests for new features

### Adding Components

To add a new rating component:

1. Create a function following the component interface
2. Place it in `open_soup_rating/components/`
3. Add tests in the `tests/` directory
4. Update documentation

Component function signature:
```python
def calculate_component_name(
    player: Dict[str, Any],
    match: Dict[str, Any], 
    damage_data: Dict[str, int],
    economic_data: Dict[str, Any],
    xvx_data: Dict[str, Any],
    **kwargs
) -> float:
    """Component calculation logic here"""
    return component_value
```

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). 

The AGPL-3.0 license ensures that:
- The source code remains open and free
- Any modifications or improvements must be shared back to the community  
- Network use of the software requires providing source code to users
- Commercial use is allowed with proper attribution and source code sharing

See [LICENSE.md](docs/LICENSE.md) for the full license text.

## Acknowledgments

- Built using match data from North American Premier Contender and Invite divisions
- Tournament data spanning Episode 9 Act 1 through Episode V25 Act 4
- XvX probability data derived from 44,080 competitive match performances
- Normalization parameters trained on comprehensive competitive tournament statistics

---

**Open Soup Rating** - Transparent, data-driven Valorant performance analysis.
