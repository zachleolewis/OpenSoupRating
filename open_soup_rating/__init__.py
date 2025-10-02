# Open Soup Rating (OSR) - Open-Source Valorant Rating System
# A modular, extensible rating system for Valorant player performance analysis.

__version__ = "1.1.1"
__author__ = "Zach Lewis"
__license__ = "AGPL-3.0"
__description__ = "A comprehensive, open-source rating system for Valorant player performance analysis"

# Core imports - these should always be available
from .core.rating_calculator import calculate_rating, calculate_rating_with_player_info, get_components
from .core.component_registry import add_component, remove_component, list_components
from .data.loader import load_match_data, load_config_data

# Optional imports that might fail with missing dependencies
try:
    from . import components
except ImportError:
    components = None

try:
    from . import utils
except ImportError:
    utils = None

__all__ = [
    # Core functionality
    'calculate_rating',
    'calculate_rating_with_player_info',
    'get_components',
    # Component management
    'add_component',
    'remove_component', 
    'list_components',
    # Data loading
    'load_match_data',
    'load_config_data',
    # Package metadata
    '__version__',
    '__author__',
    '__license__',
    '__description__'
]
