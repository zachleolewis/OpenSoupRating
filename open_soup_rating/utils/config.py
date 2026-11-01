# Configuration Management

import json
from pathlib import Path
from typing import Dict, Any

from ..core.swing import DEFAULT_CREDIT

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def get_default_config() -> Dict[str, Any]:
    """Default configuration: calibrated rating constants and kill-credit weights."""
    return {
        'rating_params': load_rating_params(DATA_DIR / 'rating_params.json'),
        'credit': dict(DEFAULT_CREDIT),
        'components': ['KillSwing', 'AssistSwing', 'DeathSwing', 'ObjectiveSwing', 'APR', 'ADRa'],
    }


def load_rating_params(params_path: Path) -> Dict[str, Any]:
    """Load centring, role baselines and shrinkage constants from JSON."""
    if not params_path.exists():
        raise FileNotFoundError(f"Rating parameters file not found: {params_path}")
    try:
        with open(params_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in rating parameters file {params_path}: {e}")


def load_config_file(config_path: Path) -> Dict[str, Any]:
    # Load configuration from a specific file.
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config_file(config: Dict[str, Any], config_path: Path) -> None:
    # Save configuration to a file.
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
