"""
OS GUI Intent Automation & Macro Tool for Athena.

Enables automated GUI actions such as launching apps, opening URLs, 
typing text, and sending keyboard shortcuts.
"""
import subprocess
import shutil
import webbrowser
import os
from typing import Optional


def execute_gui_macro(action: str, target: str = "", text: str = "") -> str:
    """Execute desktop GUI automation action.
    
    Args:
        action: Action type ('open_url', 'launch_app', 'type_text', 'press_key').
        target: Target URL, application executable name, or key combination (e.g. 'ctrl+c').
        text: Text string to type if action is 'type_text'.
        
    Returns:
        str: Status or error message.
    """
    act = action.lower().strip()

    if act == "open_url":
        if not target.startswith(("http://", "https://")):
            url = "https://" + target
        else:
            url = target
        try:
            webbrowser.open(url)
            return f"Opened URL: {url}"
        except Exception as e:
            return f"Failed to open URL: {str(e)}"

    elif act == "launch_app":
        if not target:
            return "No target application specified."
        
        # Check executable availability
        if shutil.which(target):
            try:
                subprocess.Popen([target], start_new_session=True)
                return f"Launched application: {target}"
            except Exception as e:
                return f"Failed to launch application '{target}': {str(e)}"
        elif shutil.which("gtk-launch") and target.endswith(".desktop"):
            try:
                subprocess.Popen(["gtk-launch", target], start_new_session=True)
                return f"Launched application via desktop launcher: {target}"
            except Exception as e:
                return f"Failed to launch desktop app '{target}': {str(e)}"
        else:
            return f"Application '{target}' not found in system PATH."

    elif act == "type_text":
        type_str = text or target
        if not type_str:
            return "No text provided to type."

        # Try xdotool
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "type", "--delay", "12", type_str], check=True, timeout=3)
                return f"Typed text via xdotool: '{type_str}'"
            except Exception as e:
                return f"Failed to type text via xdotool: {str(e)}"

        return "xdotool utility not installed for automated typing."

    elif act == "press_key":
        key_str = target
        if not key_str:
            return "No key combination provided."

        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "key", key_str], check=True, timeout=3)
                return f"Pressed hotkey via xdotool: '{key_str}'"
            except Exception as e:
                return f"Failed to press key via xdotool: {str(e)}"

        return "xdotool utility not installed for hotkey execution."

    return f"Unknown GUI action type: '{action}'."
