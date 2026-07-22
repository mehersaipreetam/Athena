"""
System Tools for Athena Assistant.

Provides system monitoring, clipboard interaction, and OS control capabilities.
"""
import platform
import subprocess
import shutil
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_system_status() -> str:
    """Get system health metrics including CPU usage, memory utilization, and platform details.
    
    Returns:
        Formatted summary string of system status.
    """
    system_info = f"System: {platform.system()} {platform.release()} ({platform.machine()})"
    
    if HAS_PSUTIL:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        metrics = (
            f"CPU Utilization: {cpu_percent}%\n"
            f"Memory Usage: {memory.percent}% ({memory.used // (1024**2)}MB / {memory.total // (1024**2)}MB)\n"
            f"Disk Usage: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB free)"
        )
    else:
        metrics = "Detailed RAM/CPU metrics unavailable (psutil module missing)."
        
    return f"{system_info}\n{metrics}"


def read_clipboard() -> str:
    """Read plain text contents from the system clipboard.
    
    Returns:
        Clipboard content or error string.
    """
    for tool in ["xclip", "xsel", "wl-paste", "pbpaste"]:
        if shutil.which(tool):
            try:
                cmd = [tool, "-selection", "clipboard", "-o"] if "xclip" in tool else [tool]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout:
                    return result.stdout.strip()
            except Exception as e:
                return f"Error reading clipboard via {tool}: {str(e)}"
    return "Clipboard tools (xclip/xsel/wl-paste) not available."


def search_running_processes(process_name: str) -> str:
    """Search active running processes by name.
    
    Args:
        process_name: Name or partial name of the process to search.
        
    Returns:
        Summary of matching running processes.
    """
    if not HAS_PSUTIL:
        return "Process listing unavailable (psutil module missing)."
        
    matches = []
    target = process_name.lower()
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            if pinfo['name'] and target in pinfo['name'].lower():
                matches.append(f"PID {pinfo['pid']}: {pinfo['name']} (CPU: {pinfo['cpu_percent']}%, RAM: {pinfo['memory_percent']:.1f}%)")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not matches:
        return f"No active processes found matching '{process_name}'."
    return "\n".join(matches[:10])

