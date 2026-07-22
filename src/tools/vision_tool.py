"""
Contextual Screen Awareness Module for Athena.

Provides desktop screenshot capture and multimodal vision analysis integration.
"""
import os
import shutil
import subprocess
from typing import Optional


def capture_screen(save_path: str = "assets/screen_latest.png") -> str:
    """Capture a screenshot of the primary display.
    
    Args:
        save_path: File path to save the screenshot image.
        
    Returns:
        str: Absolute file path of saved screenshot or status message.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    abs_path = os.path.abspath(save_path)

    # Try PIL ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(abs_path)
        return abs_path
    except Exception:
        pass

    # Try Linux CLI utilities
    for tool in ["scrot", "import", "maim", "gnome-screenshot"]:
        if shutil.which(tool):
            try:
                if tool == "gnome-screenshot":
                    subprocess.run([tool, "-f", abs_path], check=True, timeout=3)
                elif tool == "import":
                    subprocess.run([tool, "-window", "root", abs_path], check=True, timeout=3)
                else:
                    subprocess.run([tool, abs_path], check=True, timeout=3)
                return abs_path
            except Exception as e:
                return f"Screenshot failed via {tool}: {str(e)}"

    return "Screen capture tools (PIL/scrot/import/maim) not available in current environment."


def analyze_current_screen(prompt: str = "Describe what is currently visible on the user's screen.") -> str:
    """Take a screenshot and prepare description prompt for Gemini Vision.
    
    Args:
        prompt: Question or instruction for screen analysis.
        
    Returns:
        str: Summary report string containing screen capture result.
    """
    screen_path = capture_screen()
    if os.path.exists(screen_path):
        return f"[SCREENSHOT CAPTURED: {screen_path}] Prompt: '{prompt}'."
    return f"Failed to capture screen: {screen_path}"
