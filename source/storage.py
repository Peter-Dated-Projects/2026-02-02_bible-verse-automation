"""
JSON storage helper functions for user preferences.

Uses a centralized in-memory data manager that is loaded once on startup.
All reads come from memory; all writes flush back to persist.json.
"""

import json
import os
from typing import Dict, Optional

PERSIST_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "assets", "persist.json"
)

# ---------------------------------------------------------------------------
# In-memory data store – single source of truth at runtime
# ---------------------------------------------------------------------------

_data: Dict = {}

EMPTY_STORE = {"users": {}, "greeted": {}}


def _ensure_file() -> None:
    """Create persist.json with an empty structure if it doesn't exist."""
    os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
    if not os.path.exists(PERSIST_FILE):
        with open(PERSIST_FILE, "w") as f:
            json.dump(EMPTY_STORE, f, indent=2)
        print(f"Created new persist.json at {PERSIST_FILE}")


def _flush() -> None:
    """Write the current in-memory store to disk."""
    os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
    with open(PERSIST_FILE, "w") as f:
        json.dump(_data, f, indent=2)


def init() -> None:
    """
    Load (or create) persist.json into memory.
    Must be called once at bot startup before any other storage functions.
    """
    global _data
    _ensure_file()
    try:
        with open(PERSIST_FILE, "r") as f:
            loaded = json.load(f)
        # Merge in any keys missing from an older file format
        _data = {**EMPTY_STORE, **loaded}
        print(f"Loaded persist.json — {len(_data.get('users', {}))} user(s), "
              f"{len(_data.get('greeted', {}))} greeted")
    except Exception as e:
        print(f"Error loading persist.json, starting fresh: {e}")
        _data = dict(EMPTY_STORE)
        _flush()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_users() -> Dict:
    """Return the users dict from the in-memory store."""
    return _data.get("users", {})


def get_user_settings(user_id: str) -> Optional[Dict]:
    """Retrieve configuration for a single user."""
    return _data.get("users", {}).get(str(user_id))


def save_user_settings(
    user_id: str,
    bible_version: str,
    scheduled_time: str,
    timezone: str = "America/New_York",
) -> bool:
    """Update user preferences in memory and persist to disk."""
    try:
        _data.setdefault("users", {})[str(user_id)] = {
            "bible_version": bible_version,
            "scheduled_time": scheduled_time,
            "timezone": timezone,
        }
        _flush()
        return True
    except Exception as e:
        print(f"Error saving user settings: {e}")
        return False


def has_been_greeted(user_id: str) -> bool:
    """Return True if the user has already received the welcome DM."""
    return str(user_id) in _data.get("greeted", {})


def mark_greeted(user_id: str) -> None:
    """Record that the welcome DM has been sent to this user."""
    try:
        _data.setdefault("greeted", {})[str(user_id)] = True
        _flush()
    except Exception as e:
        print(f"Error marking user as greeted: {e}")


def get_all_users() -> Dict:
    """Return all users (alias for load_users)."""
    return load_users()
