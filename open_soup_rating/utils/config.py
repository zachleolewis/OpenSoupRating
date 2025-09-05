# Configuration Management

import json
from pathlib import Path
from typing import Dict, Any

# Configuration Management

import json
from pathlib import Path
from typing import Dict, Any

def get_default_config() -> Dict[str, Any]:
    """Get default configuration values loaded from external JSON files."""
    # Load weights from data/weights.json
    weights_path = Path(__file__).parent.parent.parent / 'data' / 'weights.json'
    weights = load_weights_from_json(weights_path)

    # Load normalization parameters from data/normalization_params.json
    norm_params_path = Path(__file__).parent.parent.parent / 'data' / 'normalization_params.json'
    norm_params = load_normalization_params_from_json(norm_params_path)

    return {
        'weights': weights,
        'normalization_params': norm_params,
        'components': ['KillContrib', 'DeathContrib', 'APR', 'ADRa']
    }

def load_weights_from_json(weights_path: Path) -> Dict[str, float]:
    """Load component weights from JSON file."""
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights file not found: {weights_path}")
    
    try:
        with open(weights_path, 'r') as f:
            weights_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in weights file {weights_path}: {e}")
    
    # Handle both old list format and new dict format
    if isinstance(weights_data, list):
        components = ['KillContrib', 'DeathContrib', 'APR', 'ADRa']
        return dict(zip(components, weights_data))
    elif isinstance(weights_data, dict):
        return weights_data
    else:
        raise ValueError("Weights file must contain either a list or dictionary")

def load_normalization_params_from_json(norm_params_path: Path) -> Dict[str, Dict[str, float]]:
    """Load normalization parameters from JSON file."""
    if not norm_params_path.exists():
        raise FileNotFoundError(f"Normalization parameters file not found: {norm_params_path}")
    
    try:
        with open(norm_params_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in normalization parameters file {norm_params_path}: {e}")

def load_config_file(config_path: Path) -> Dict[str, Any]:
    # Load configuration from a specific file.
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def save_config_file(config: Dict[str, Any], config_path: Path) -> None:
    # Save configuration to a file.
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
