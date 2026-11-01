# Component Registry - Manages available rating components

from typing import Dict, Callable, List

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
    from ..components.swing_components import (
        calculate_kill_swing, calculate_assist_swing, calculate_death_swing, calculate_objective_swing,
    )
    from ..components.apr import calculate_apr
    from ..components.adra import calculate_adra

    # Round Swing components: these sum to the rating
    register_component('KillSwing', calculate_kill_swing)
    register_component('AssistSwing', calculate_assist_swing)
    register_component('DeathSwing', calculate_death_swing)
    register_component('ObjectiveSwing', calculate_objective_swing)

    # Informational components: reported, not part of the rating
    register_component('APR', calculate_apr)
    register_component('ADRa', calculate_adra)

    return _COMPONENTS


load_builtin_components()
