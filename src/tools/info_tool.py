"""
User Info Tool for Project Athena.

Provides information about the user from a local config file.
Falls back to environment variables or defaults if no config exists.
"""
import os
import json
from pathlib import Path


_CONFIG_DIR = Path(os.path.expanduser("~/.athena"))
_USER_PROFILE_PATH = _CONFIG_DIR / "user_profile.json"

# Default profile — overridden by user_profile.json if it exists
_DEFAULT_PROFILE = {
    "name": "Sir",
    "profession": "",
    "preferences": {},
}


def _load_profile() -> dict:
    """Load user profile from disk or return defaults."""
    if _USER_PROFILE_PATH.exists():
        try:
            with open(_USER_PROFILE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT_PROFILE.copy()


def _save_profile(profile: dict) -> None:
    """Persist user profile to disk."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_USER_PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)


def get_info() -> str:
    """Get information about the user.

    Reads from ~/.athena/user_profile.json if available,
    otherwise returns defaults. Can be updated via update_user_info().

    Returns:
        str: Formatted user profile information.
    """
    profile = _load_profile()
    parts = []
    for key, value in profile.items():
        if value and key != "preferences":
            parts.append(f"{key.replace('_', ' ').title()}: {value}")
    if profile.get("preferences"):
        prefs = ", ".join(f"{k}={v}" for k, v in profile["preferences"].items())
        parts.append(f"Preferences: {prefs}")
    return ", ".join(parts) if parts else "No user profile configured."


def update_user_info(field: str, value: str) -> str:
    """Update a field in the user profile.

    Persists the change to ~/.athena/user_profile.json.

    Args:
        field: Profile field name (e.g., 'name', 'profession', 'location').
        value: New value for the field.

    Returns:
        str: Confirmation message.
    """
    profile = _load_profile()
    field_lower = field.lower().strip().replace(" ", "_")
    profile[field_lower] = value
    _save_profile(profile)
    return f"Updated {field} to '{value}', sir. I'll remember that."