# Open Soup Rating (OSR) - Open-Source Valorant Rating System
# A modular, extensible rating system for Valorant player performance analysis.

__version__ = "1.1.0"
__author__ = "Zach Lewis"
__license__ = "AGPL-3.0"

# Conditional imports to handle missing dependencies gracefully
try:
    from .core.rating_calculator import calculate_rating, calculate_rating_with_player_info, get_components
except ImportError:
    calculate_rating = None
    calculate_rating_with_player_info = None
    get_components = None

try:
    from .core.component_registry import add_component, remove_component, list_components
except ImportError:
    add_component = None
    remove_component = None
    list_components = None

try:
    from .data.loader import load_match_data, load_config_data
except ImportError:
    load_match_data = None
    load_config_data = None

__all__ = [
    'calculate_rating',
    'calculate_rating_with_player_info',
    'get_components',
    'add_component',
    'remove_component',
    'list_components',
    'load_match_data',
    'load_config_data'
]
