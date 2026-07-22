"""
Media Control Tool for Project Athena.

Controls system media playback using playerctl (Linux MPRIS) and
provides Spotify integration for music queries.
Enables commands like "Play my music", "Pause", "Next track", "What's playing?"
"""
import subprocess
import shutil
from typing import Optional


def _run_cmd(cmd: list[str], timeout: int = 5) -> tuple[bool, str]:
    """Execute a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def _has_playerctl() -> bool:
    """Check if playerctl is available on the system."""
    return shutil.which("playerctl") is not None


def control_media(action: str) -> str:
    """Control system media playback (play, pause, next, previous, stop).

    Uses playerctl to interact with any MPRIS-compatible media player
    (Spotify, VLC, Firefox, Chrome, etc.).

    Args:
        action: One of 'play', 'pause', 'play-pause', 'next', 'previous', 'stop'.

    Returns:
        str: Status message confirming the action taken.
    """
    if not _has_playerctl():
        return (
            "Media control requires playerctl. "
            "Install with: sudo apt install playerctl"
        )

    valid_actions = ["play", "pause", "play-pause", "next", "previous", "stop"]
    action_lower = action.lower().strip()

    # Map common synonyms
    action_map = {
        "resume": "play",
        "skip": "next",
        "back": "previous",
        "prev": "previous",
        "toggle": "play-pause",
    }
    action_lower = action_map.get(action_lower, action_lower)

    if action_lower not in valid_actions:
        return (
            f"Unknown media action '{action}'. "
            f"Valid actions: {', '.join(valid_actions)}"
        )

    success, output = _run_cmd(["playerctl", action_lower])

    if success:
        action_messages = {
            "play": "Resuming playback now, sir.",
            "pause": "Playback paused, sir.",
            "play-pause": "Toggled playback, sir.",
            "next": "Skipping to the next track, sir.",
            "previous": "Going back to the previous track, sir.",
            "stop": "Stopping playback entirely, sir.",
        }
        return action_messages.get(action_lower, f"Media action '{action_lower}' executed successfully.")
    else:
        if "No players found" in output or "No player could" in output:
            return "No active media players detected, sir. Please start a media application first."
        return f"Media control issue: {output}"


def get_now_playing() -> str:
    """Get information about the currently playing media track.

    Retrieves artist, title, album, and playback status from
    any active MPRIS-compatible media player.

    Returns:
        str: Formatted string with current track information.
    """
    if not _has_playerctl():
        return (
            "Media control requires playerctl. "
            "Install with: sudo apt install playerctl"
        )

    # Get player status
    success, status = _run_cmd(["playerctl", "status"])
    if not success:
        return "No active media players detected, sir."

    # Get metadata
    metadata_fields = {
        "title": "xesam:title",
        "artist": "xesam:artist",
        "album": "xesam:album",
    }

    info = {"status": status}
    for key, field in metadata_fields.items():
        ok, value = _run_cmd(["playerctl", "metadata", field])
        info[key] = value if ok and value else "Unknown"

    # Get player name
    ok, player_name = _run_cmd(["playerctl", "metadata", "mpris:trackid"])
    if ok and player_name:
        # Extract player name from trackid (e.g., "/org/mpris/MediaPlayer2/spotify")
        parts = player_name.split("/")
        info["player"] = parts[-1] if parts else "Unknown"

    # Get active player name directly
    ok, player = _run_cmd(["playerctl", "--list-all"])
    info["player"] = player.split("\n")[0] if ok and player else "Unknown"

    # Format response
    status_emoji = {"Playing": "▶️", "Paused": "⏸️", "Stopped": "⏹️"}
    emoji = status_emoji.get(info["status"], "🎵")

    return (
        f"{emoji} Now {info['status']}:\n"
        f"  Track: {info['title']}\n"
        f"  Artist: {info['artist']}\n"
        f"  Album: {info['album']}\n"
        f"  Player: {info['player']}"
    )


def set_volume(level: int) -> str:
    """Set the system audio volume to a specific percentage.

    Args:
        level: Volume percentage (0-100).

    Returns:
        str: Confirmation of volume level set.
    """
    level = max(0, min(100, level))

    # Try pactl first (PulseAudio/PipeWire)
    if shutil.which("pactl"):
        success, _ = _run_cmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        if success:
            return f"Volume set to {level}%, sir."

    # Fallback to amixer (ALSA)
    if shutil.which("amixer"):
        success, _ = _run_cmd(["amixer", "sset", "Master", f"{level}%"])
        if success:
            return f"Volume set to {level}%, sir."

    return "Unable to set volume. Neither pactl nor amixer is available."
