"""
Time Tool - Provides current time functionality.

This is a standalone tool that can be imported into the MCP server.
"""
from datetime import datetime
import pytz


def get_current_time(timezone: str = "Asia/Kolkata") -> str:
    """Get the current time in the specified timezone.
    
    Use this tool when the user asks about the current time, what time it is,
    or anything related to knowing the time.
    
    Args:
        timezone: IANA timezone name (e.g., "Asia/Kolkata", "UTC", "America/New_York").
                  Defaults to Asia/Kolkata (IST).
    
    Returns:
        Human-readable current time string suitable for voice output.
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone("Asia/Kolkata")
    
    now = datetime.now(tz)
    return now.strftime("%I:%M %p on %A, %B %d, %Y")
