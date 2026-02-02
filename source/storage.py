"""
JSON storage helper functions for user preferences.
"""
import json
import os
from typing import Dict, Optional

PERSIST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'persist.json')

def load_users() -> Dict:
    """Load user data from persist.json into memory."""
    try:
        if os.path.exists(PERSIST_FILE):
            with open(PERSIST_FILE, 'r') as f:
                data = json.load(f)
                return data.get('users', {})
        return {}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_user_settings(user_id: str, bible_version: str, scheduled_time: str, timezone: str = "America/New_York") -> bool:
    """Update and persist user preferences."""
    try:
        # Load current data
        data = {'users': {}}
        if os.path.exists(PERSIST_FILE):
            with open(PERSIST_FILE, 'r') as f:
                data = json.load(f)
        
        # Update user settings
        if 'users' not in data:
            data['users'] = {}
        
        data['users'][str(user_id)] = {
            'bible_version': bible_version,
            'scheduled_time': scheduled_time,
            'timezone': timezone
        }
        
        # Save to file
        os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
        with open(PERSIST_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving user settings: {e}")
        return False

def get_user_settings(user_id: str) -> Optional[Dict]:
    """Retrieve user configuration."""
    users = load_users()
    return users.get(str(user_id))

def get_all_users() -> Dict:
    """Returns all users for scheduling."""
    return load_users()
