"""
Visual Target Tracking & Screen Clicker Tool for Athena.

Calculates bounding box center points and performs targeted automated mouse clicks
based on desktop screen coordinates or element descriptions.
"""
import subprocess
import shutil
from typing import Tuple, Optional


def click_screen_coordinates(x: int, y: int, click_type: str = "left") -> str:
    """Perform mouse click at specific (X, Y) pixel coordinates.
    
    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.
        click_type: 'left', 'right', or 'double'.
        
    Returns:
        str: Status message string.
    """
    if shutil.which("xdotool"):
        try:
            if click_type == "right":
                btn = "3"
            elif click_type == "double":
                btn = "1"
            else:
                btn = "1"

            cmd = ["xdotool", "mousemove", str(x), str(y), "click"]
            if click_type == "double":
                cmd.extend(["--repeat", "2", "--delay", "100", "1"])
            else:
                cmd.append(btn)

            subprocess.run(cmd, check=True, timeout=3)
            return f"Executed {click_type} click at ({x}, {y}) via xdotool."
        except Exception as e:
            return f"Failed click action at ({x}, {y}): {str(e)}"

    return "xdotool binary not available for GUI mouse interaction."


def calculate_bounding_box_center(ymin: float, xmin: float, ymax: float, xmax: float, screen_width: int = 1920, screen_height: int = 1080) -> Tuple[int, int]:
    """Convert normalized bounding box coordinates (0.0 to 1.0) into absolute screen pixel coordinates.
    
    Args:
        ymin: Normalized top Y.
        xmin: Normalized left X.
        ymax: Normalized bottom Y.
        xmax: Normalized right X.
        screen_width: Display pixel width.
        screen_height: Display pixel height.
        
    Returns:
        Tuple[int, int]: (center_x, center_y) in screen pixels.
    """
    cx = int(((xmin + xmax) / 2.0) * screen_width)
    cy = int(((ymin + ymax) / 2.0) * screen_height)
    return cx, cy
