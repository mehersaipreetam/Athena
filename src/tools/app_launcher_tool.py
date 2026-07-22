"""
Application Launcher Tools
"""
import os
import glob
import shlex
import subprocess
import difflib
import logging
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

COMMON_APPS = {
    "chrome": ["google-chrome", "google-chrome-stable", "chrome"],
    "firefox": ["firefox"],
    "code": ["code"],
    "vscode": ["code"],
    "terminal": ["gnome-terminal", "konsole", "alacritty", "terminator", "xterm"],
    "nautilus": ["nautilus"],
    "files": ["nautilus", "thunar", "dolphin"],
    "spotify": ["spotify"],
    "vlc": ["vlc"],
    "calendar": ["gnome-calendar", "calendar"],
    "calculator": ["gnome-calculator", "calculator", "kcalc"]
}

def _find_executable(app_name: str) -> str | None:
    """Find the executable path for a given app name."""
    try:
        result = subprocess.run(["which", app_name], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def _find_app_from_desktop_files(app_name: str) -> str | None:
    """Search .desktop files to map a human-readable name to its execution command."""
    app_name_lower = app_name.lower()
    desktop_files = []
    
    for path in ['/usr/share/applications', os.path.expanduser('~/.local/share/applications')]:
        if os.path.exists(path):
            desktop_files.extend(glob.glob(os.path.join(path, '*.desktop')))
            
    app_map = {}
    
    for df in desktop_files:
        try:
            with open(df, 'r', encoding='utf-8') as f:
                name = None
                exec_cmd = None
                for line in f:
                    line = line.strip()
                    if line.startswith('Name=') and not name:
                        name = line[5:].strip().lower()
                    elif line.startswith('Exec=') and not exec_cmd:
                        exec_cmd = line[5:].strip()
                if name and exec_cmd:
                    clean_exec = ' '.join([p for p in shlex.split(exec_cmd) if not p.startswith('%')])
                    app_map[name] = clean_exec
        except Exception:
            pass
            
    if app_name_lower in app_map:
        return app_map[app_name_lower]
        
    for name, exec_cmd in app_map.items():
        if app_name_lower in name or name in app_name_lower:
            return exec_cmd
            
    matches = difflib.get_close_matches(app_name_lower, app_map.keys(), n=1, cutoff=0.6)
    if matches:
        return app_map[matches[0]]
        
    return None

def launch_application(app_name: str) -> str:
    """Launch an application by name.
    
    Args:
        app_name: The name of the application to launch.
        
    Returns:
        A string indicating success or failure.
    """
    app_name_lower = app_name.lower()
    
    # Try dynamic desktop file search first
    desktop_cmd = _find_app_from_desktop_files(app_name_lower)
    if desktop_cmd:
        try:
            cmd_parts = shlex.split(desktop_cmd)
            subprocess.Popen(cmd_parts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            console.print(f"[green]Successfully launched {app_name} via desktop mapping[/green]")
            return f"Successfully launched {app_name}"
        except Exception as e:
            logger.error(f"Failed to launch via desktop mapping: {e}")
            # Fall through to common apps / which
    
    # Fallback to hardcoded COMMON_APPS and `which`
    executables_to_try = []
    if app_name_lower in COMMON_APPS:
        executables_to_try = COMMON_APPS[app_name_lower]
    else:
        matches = difflib.get_close_matches(app_name_lower, COMMON_APPS.keys(), n=1, cutoff=0.6)
        if matches:
            executables_to_try = COMMON_APPS[matches[0]]
        else:
            executables_to_try = [app_name_lower]
            
    for exe in executables_to_try:
        path = _find_executable(exe)
        if path:
            try:
                subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                console.print(f"[green]Successfully launched {exe}[/green]")
                return f"Successfully launched {exe}"
            except Exception as e:
                logger.error(f"Failed to launch {exe}: {e}")
                return f"Failed to launch {exe}: {str(e)}"
                
    return f"Could not find executable for application: {app_name}"

def list_open_windows() -> str:
    """List currently open windows using wmctrl.
    
    Returns:
        Formatted list of window titles or error message.
    """
    try:
        result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")
        windows = []
        for line in lines:
            if not line:
                continue
            # Format: 0x01800003  0 meher-desktop Window Title
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                windows.append(parts[3])
        if not windows:
            return "No open windows found."
        
        return "Open windows:\n" + "\n".join(f"- {w}" for w in windows)
    except FileNotFoundError:
        return "wmctrl is not installed. Please install it to list windows."
    except subprocess.CalledProcessError as e:
        return f"Failed to list windows: {e}"

def focus_window(window_title: str) -> str:
    """Focus a window by title using wmctrl.
    
    Args:
        window_title: The title of the window to focus.
        
    Returns:
        String indicating success or failure.
    """
    try:
        result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")
        
        # Extract window titles
        windows = []
        window_map = {} # map title to window ID
        for line in lines:
            if not line:
                continue
            parts = line.split(maxsplit=3)
            if len(parts) >= 4:
                win_id = parts[0]
                title = parts[3]
                windows.append(title)
                window_map[title] = win_id
                
        if not windows:
            return "No open windows found."
            
        # Fuzzy match window title
        matches = difflib.get_close_matches(window_title, windows, n=1, cutoff=0.3)
        if not matches:
            # Try case-insensitive substring match
            for title in windows:
                if window_title.lower() in title.lower():
                    matches = [title]
                    break
                    
        if matches:
            best_match = matches[0]
            win_id = window_map[best_match]
            subprocess.run(["wmctrl", "-i", "-a", win_id], check=True)
            return f"Focused window: {best_match}"
        else:
            return f"Could not find a window matching: {window_title}"
            
    except FileNotFoundError:
        return "wmctrl is not installed. Please install it to focus windows."
    except subprocess.CalledProcessError as e:
        return f"Failed to focus window: {e}"
