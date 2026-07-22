"""
Phase 13: Smart Home & IoT Control tool for Athena.
"""
import os
import json
from pathlib import Path
from typing import Optional

STATE_FILE = Path.home() / ".athena" / "smart_home_state.json"

def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def _resolve_aliases(device_name: str) -> list[str]:
    device_name = device_name.lower().strip()
    if device_name == "all lights":
        return ["living room light", "bedroom light", "kitchen light"]
    elif device_name in ("ac", "air conditioner"):
        return ["thermostat"]
    return [device_name]

def control_device(device_name: str, state: str) -> str:
    """
    Control a smart home device.
    
    Args:
        device_name: Name of the device or alias (e.g., "living room light", "all lights", "AC")
        state: State to set (e.g., "on", "off", "72", "lock")
    """
    devices = _resolve_aliases(device_name)
    current_state = _load_state()
    
    for dev in devices:
        current_state[dev] = state
        
    _save_state(current_state)
    
    if len(devices) == 1:
        return f"Device '{devices[0]}' set to '{state}'."
    else:
        return f"Devices {devices} set to '{state}'."

def get_device_status(device_name: Optional[str] = None) -> str:
    """
    Get the status of a smart home device.
    
    Args:
        device_name: Optional device name or alias. If None, returns all devices.
    """
    current_state = _load_state()
    if not current_state:
        return "No devices found."
        
    if device_name is None:
        return "\n".join(f"{k}: {v}" for k, v in current_state.items())
        
    devices = _resolve_aliases(device_name)
    results = []
    for dev in devices:
        if dev in current_state:
            results.append(f"{dev}: {current_state[dev]}")
        else:
            results.append(f"{dev}: unknown")
            
    return "\n".join(results)
