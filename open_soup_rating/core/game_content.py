# Game Content - agent roles and armor values keyed by Riot item UUIDs

import json
from pathlib import Path
from typing import Dict, Any, Optional

_GAME_CONTENT_PATH = Path(__file__).resolve().parent.parent / 'data' / 'game_content.json'
_game_content: Optional[Dict[str, Any]] = None


def game_content() -> Dict[str, Any]:
    global _game_content
    if _game_content is None:
        with open(_GAME_CONTENT_PATH, 'r', encoding='utf-8') as f:
            _game_content = json.load(f)
    return _game_content


def agent_role(character_id: Optional[str]) -> Optional[str]:
    agent = game_content()['agents'].get((character_id or '').lower())
    return agent['role'] if agent else None


def agent_name(character_id: Optional[str]) -> Optional[str]:
    agent = game_content()['agents'].get((character_id or '').lower())
    return agent['name'] if agent else None
