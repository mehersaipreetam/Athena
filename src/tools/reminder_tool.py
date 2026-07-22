try:
    from src.core.proactive_engine import engine
except ImportError:
    from core.proactive_engine import engine

def set_reminder(message: str, minutes: int) -> str:
    """
    Sets a time-based reminder that will trigger a notification in the future.
    
    Args:
        message (str): The reminder message to display
        minutes (int): How many minutes from now to trigger the reminder
        
    Returns:
        str: Confirmation message
    """
    delay_seconds = minutes * 60
    engine.add_reminder(message, delay_seconds)
    
    # Ensure the engine is running
    if not engine.running:
        engine.start()
        
    return f"Successfully scheduled reminder: '{message}' in {minutes} minutes."
