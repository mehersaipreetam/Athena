"""
System Telemetry Panel for Athena Rich TUI.

Renders real-time telemetry metrics (CPU/RAM, active LLM provider, VAD state, active background tasks).
"""
import platform
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False



def generate_telemetry_panel(active_provider: str = "Gemini", vad_status: str = "Listening", active_tasks: int = 0) -> Panel:
    """Generate a Rich Panel widget containing system telemetry information.
    
    Args:
        active_provider: Active LLM provider name (e.g. Gemini, Local Ollama).
        vad_status: Current audio/VAD state string.
        active_tasks: Count of active background swarm tasks.
        
    Returns:
        Panel: Rich Panel object.
    """
    table = Table.grid(expand=True)
    table.add_column(style="bold #ff00ff", justify="left")
    table.add_column(style="bold #ffffff", justify="right")

    table.add_row("OS Platform:", f"{platform.system()} {platform.machine()}")
    table.add_row("LLM Provider:", active_provider)
    table.add_row("Voice State:", vad_status)
    table.add_row("Background Tasks:", str(active_tasks))

    if HAS_PSUTIL:
        import psutil
        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory().percent
        table.add_row("CPU Load:", f"{cpu:.1f}%")
        table.add_row("RAM Usage:", f"{mem:.1f}%")
    else:
        table.add_row("Telemetry:", "Basic Mode")

    return Panel(table, title="[bold #00ffff]Telemetry Monitor[/bold #00ffff]", border_style="#ff00ff")
