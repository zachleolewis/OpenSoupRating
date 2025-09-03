# Changelog

All notable changes to **Open Soup Rating** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release of Open Soup Rating system
- Complete Valorant rating algorithm implementation
- Component-based rating system with four main components:
  - Adjusted Damage per Round (ADRA)
  - Assists Per Round (APR)
  - Kill Contributions (with XvX impact analysis)
  - Death Contributions (with XvX impact analysis)
- Economic modifier system for kill/death scaling
- Post-round modifier for timing-based adjustments
- Pre-computed XvX win probability data
- Library function for single match rating calculations
- Full system for processing multiple matches
- Data loading and processing utilities
- Professional documentation and README
- GitHub repository setup with proper licensing
- Python 3.8+ compatibility
- AGPLv3 license implementation
- Trademark protection setup

### Technical Details
- **Rating Formula**: `rating = w1 × KillContrib + w2 × DeathContrib + w3 × APR + w4 × ADRA`
- **Current Weights**: [0.431, 0.431, 0.052, 0.085]
- **Data Requirements**: Riot API match data, economic analysis, XvX probabilities
- **Output Formats**: JSON components file, CSV comparison data

### Files Added
- `main.py` - Main processing script for multiple matches
- `open_soup_rating_lib.py` - Library for single match calculations
- `src/` directory with modular components:
  - `rating_calculator.py` - Core calculation logic
  - `data_loader.py` - Data loading utilities
  - `adra.py` - ADRA calculations
  - `apr.py` - APR calculations
  - `xvx_impact.py` - XvX impact analysis
  - `economic_impact.py` - Economic modifiers
  - `post_round_modifier.py` - Timing adjustments
- Data files:
  - `weights.json` - Rating formula weights
  - `loadout_cost_analysis.json` - Economic matchup data
  - `xvx_breakdown_data.json` - XvX win probabilities
- Documentation:
  - `README.md` - Comprehensive project documentation
  - `LICENSE.md` - AGPLv3 license text
  - `TRADEMARK.md` - Trademark usage guidelines
- Development files:
  - `.gitignore` - Git ignore rules
  - `.gitattributes` - Git attributes configuration

---

## Types of Changes
- `Added` for new features
- `Changed` for changes in existing functionality
- `Deprecated` for soon-to-be removed features
- `Removed` for now removed features
- `Fixed` for any bug fixes
- `Security` in case of vulnerabilities

## Version Format
This project uses [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., 1.0.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

---

*For the latest updates and contributions, see the [GitHub repository](https://github.com/zachleolewis/OpenSoupRating).*</content>
