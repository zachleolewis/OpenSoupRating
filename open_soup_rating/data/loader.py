# Data Loading Utilities

import gzip
import json
from pathlib import Path
from typing import Dict, List, Any, Union


def _read_json(file_path: Path) -> Any:
    opener = gzip.open if file_path.name.endswith('.gz') else open
    with opener(file_path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def load_match_data(data_path: Union[str, Path], max_matches: int = None) -> List[Dict[str, Any]]:
    # Load match data from JSON files (.json or .json.gz).
    # Args:
    #     data_path: Path to directory containing match JSON files or single file
    #     max_matches: Maximum number of matches to load (optional)
    # Returns:
    #     List of match dictionaries
    data_path = Path(data_path)

    if data_path.is_file():
        return [_read_json(data_path)]
    elif data_path.is_dir():
        # Directory of files (search recursively)
        matches = []
        files = sorted(p for p in data_path.rglob('*') if p.name.endswith(('.json', '.json.gz')))
        for file_path in files:
            if max_matches and len(matches) >= max_matches:
                break
            try:
                matches.append(_read_json(file_path))
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
        return matches
    else:
        raise ValueError(f"Path {data_path} does not exist")


def load_config_data(config_path: Union[str, Path]) -> Dict[str, Any]:
    # Load configuration data from JSON files.
    # Args:
    #     config_path: Path to config directory or file
    # Returns:
    #     Configuration dictionary
    config_path = Path(config_path)
    config = {}

    if config_path.is_file():
        config.update(_read_json(config_path))
    elif config_path.is_dir():
        # Load all JSON files in directory
        for file_path in config_path.glob('*.json'):
            try:
                config.update(_read_json(file_path))
            except Exception as e:
                print(f"Warning: Failed to load config {file_path}: {e}")
    else:
        raise ValueError(f"Config path {config_path} does not exist")

    return config


def save_data(data: Any, file_path: Union[str, Path], indent: int = 2) -> None:
    # Save data to JSON file.
    # Args:
    #     data: Data to save
    #     file_path: Path to save file
    #     indent: JSON indentation level
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
