# Data Loading Utilities

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Union

def load_match_data(data_path: Union[str, Path], max_matches: int = None) -> List[Dict[str, Any]]:
    # Load match data from JSON files.
    # Args:
    #     data_path: Path to directory containing match JSON files or single file
    #     max_matches: Maximum number of matches to load (optional)
    # Returns:
    #     List of match dictionaries
    data_path = Path(data_path)

    if data_path.is_file():
        # Single file
        with open(data_path, 'r') as f:
            return [json.load(f)]
    elif data_path.is_dir():
        # Directory of files (search recursively)
        matches = []
        for file_path in data_path.rglob('*.json'):  # Use rglob for recursive search
            if max_matches and len(matches) >= max_matches:
                break
            try:
                with open(file_path, 'r') as f:
                    match_data = json.load(f)
                    matches.append(match_data)
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
        with open(config_path, 'r') as f:
            config.update(json.load(f))
    elif config_path.is_dir():
        # Load all JSON files in directory
        for file_path in config_path.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    file_config = json.load(f)
                    config.update(file_config)
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

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=indent)
