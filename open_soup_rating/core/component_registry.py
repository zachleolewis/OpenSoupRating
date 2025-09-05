# Component Registry - Manages available rating components
# Now uses corrected impact methodology as the standard implementation

from typing import Dict, Callable, Any, List
import importlib
import os

# Component registry
_COMPONENTS: Dict[str, Callable] = {}

def register_component(name: str, calculator: Callable) -> None:
    """Register a new component calculator."""
    _COMPONENTS[name] = calculator

def unregister_component(name: str) -> None:
    """Remove a component from the registry."""
    if name in _COMPONENTS:
        del _COMPONENTS[name]

def get_component(name: str) -> Callable:
    """Get a component calculator by name."""
    if name not in _COMPONENTS:
        raise ValueError(f"Component '{name}' not found. Available: {list(_COMPONENTS.keys())}")
    return _COMPONENTS[name]

def list_components() -> List[str]:
    """List all registered components."""
    return list(_COMPONENTS.keys())

def add_component(name: str, calculator_func: Callable) -> None:
    """Add a new component to the system."""
    register_component(name, calculator_func)

def remove_component(name: str) -> None:
    """Remove a component from the system."""
    unregister_component(name)

def load_builtin_components():
    """Load all built-in components."""
    
    # Load standard components (now using corrected methodology)
    try:
        from ..components.kill_contrib import calculate_kill_contrib
        register_component('KillContrib', calculate_kill_contrib)
        print("Loaded KillContrib component (corrected methodology)")
    except ImportError as e:
        print(f"Warning: Could not load KillContrib component: {e}")

    try:
        from ..components.death_contrib import calculate_death_contrib
        register_component('DeathContrib', calculate_death_contrib)
        print("Loaded DeathContrib component (corrected methodology)")
    except ImportError as e:
        print(f"Warning: Could not load DeathContrib component: {e}")

    # Load other components (unchanged)
    try:
        from ..components.apr import calculate_apr
        register_component('APR', calculate_apr)
    except ImportError:
        print("Warning: Could not load APR component")

    try:
        from ..components.adra import calculate_adra
        register_component('ADRa', calculate_adra)
    except ImportError:
        print("Warning: Could not load ADRa component")
    
    return _COMPONENTS

# Load built-in components on import (now using corrected methodology as standard)
load_builtin_components()
