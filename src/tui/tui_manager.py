from collections import deque
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from datetime import datetime
import sys
import threading
import select
try:
    from src.tui.telemetry_panel import generate_telemetry_panel
except ImportError:
    from tui.telemetry_panel import generate_telemetry_panel

# Try to import pynput for key handling
try:
    from pynput import keyboard as kb
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class TUIManager:
    def __init__(self):
        self.console = Console()
        self.layout = self._create_layout()
        self.chat_history = deque(maxlen=200)  # Auto-evicts oldest messages
        self.status = "Initializing..."
        self.partial_text = ""
        self.final_text = ""
        self.thinking = False

        # Scrolling support
        self.scroll_offset = 0
        self._input_thread = threading.Thread(target=self._read_stdin, daemon=True)
        self._input_thread.start()

        # Start pynput listener if available
        self._key_listener = None
        if HAS_PYNPUT:
            self._start_key_listener()

    def _start_key_listener(self):
        """Start pynput keyboard listener for space key interrupt."""
        def on_press(key):
            if key == kb.Key.space:
                if hasattr(self, 'key_press_hook') and self.key_press_hook:
                    try:
                        self.key_press_hook(key)
                    except Exception:
                        pass

        self._key_listener = kb.Listener(on_press=on_press)
        self._key_listener.start()

    def _read_stdin(self):
        """Read standard input in a background thread to handle scrolling and interrupts."""
        try:
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while True:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        char = sys.stdin.read(1)
                        if char == '\x1b':  # Escape sequence
                            next1, next2 = sys.stdin.read(1), sys.stdin.read(1)
                            if next1 == '[':
                                if next2 == 'A':  # Up arrow
                                    self._on_key_press("up")
                                elif next2 == 'B':  # Down arrow
                                    self._on_key_press("down")
                        elif char == ' ':  # Spacebar
                            self._on_key_press("space")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass  # Fail gracefully if not a tty

    def _on_key_press(self, key_name: str):
        if hasattr(self, 'key_press_hook') and self.key_press_hook:
            try:
                # Mock a key object for the hook
                class MockKey:
                    def __init__(self, name):
                        self.name = name
                        self.char = name if name == ' ' else None
                        self.value = name if name == ' ' else None
                        
                if self.key_press_hook(MockKey(' ' if key_name == 'space' else key_name)):
                    return
            except Exception:
                pass

        changed = False
        if key_name == "up":
            self.scroll_offset = max(0, self.scroll_offset - 1)
            changed = True
        elif key_name == "down":
            self.scroll_offset += 1
            changed = True
            
        if changed and hasattr(self, '_live'):
            self._live.update(self.render())

    def _create_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=10),
            Layout(name="main_split"),
            Layout(name="footer", size=3)
        )
        layout["main_split"].split_row(
            Layout(name="body", ratio=3),
            Layout(name="telemetry", ratio=1, minimum_size=30)
        )
        return layout

    def render(self):
        # Header with Project Athena ASCII Banner
        header_text = Text()
        header_text.append("    ___ _____ _   _ _____ _   _  ___\n", style="bold #00ffff")
        header_text.append("   / _ \\_   _| | | |  ___| \\ | |/ _ \\\n", style="bold #00ffff")
        header_text.append("  / /_\\ \\| | | |_| | |__ |  \\| / /_\\ \\\n", style="bold #00dddd")
        header_text.append("  |  _  || | |  _  |  __|| . ` |  _  |\n", style="bold #00bbbb")
        header_text.append("  | | | || | | | | | |___| |\\  | | | |\n", style="bold #009999")
        header_text.append("  \\_| |_/\\_/ \\_| |_/\\____/\\_| \\_/\\_| |_/\n", style="bold #007777")
        header_text.append(" ── COGNITIVE CORE v5.0 ── ", style="bold #ff00ff")
        header_text.append(f"[● ONLINE] {self.status}", style="bold #00ff00")

        self.layout["header"].update(Panel(Align.center(header_text), title="[bold #00ffff]PROJECT ATHENA HUD[/bold #00ffff]", border_style="#ff00ff"))

        # Body with scrollable chat history
        body_text = Text()
        for role, line in self.chat_history:
            if role in ("You", "Sir"):
                body_text.append("\n")
                body_text.append("Sir: ", style="bold #00ffff")
                body_text.append(f"{line}\n", style="#dddddd")
            else:  # Athena
                body_text.append("Athena: ", style="bold #ff00ff")
                body_text.append(f"{line}\n", style="#ffb3ff")

        # Show thinking state if active
        if self.thinking:
            body_text.append("Athena: ", style="bold #ff00ff")
            body_text.append("...processing live feeds ⚡\n", style="bold #ffff00")

        # Calculate display dimensions
        body_width = max(10, self.console.size.width - 4)
        body_height = max(5, self.console.size.height - 10 - 3 - 2)

        capture_console = Console(width=body_width, color_system=self.console.color_system, force_terminal=True)
        with capture_console.capture() as capture:
            capture_console.print(body_text)

        all_lines = capture.get().splitlines()
        max_scroll = max(0, len(all_lines) - body_height)

        if self.scroll_offset > max_scroll:
            self.scroll_offset = max_scroll
        if self.scroll_offset < 0:
            self.scroll_offset = 0

        if len(all_lines) > body_height:
            start_idx = len(all_lines) - body_height - self.scroll_offset
            end_idx = start_idx + body_height
            visible_lines = all_lines[start_idx:end_idx]
            
            visible_text = "\n".join(visible_lines)
            final_text = Text.from_ansi(visible_text)
            title = f"[bold #00ffff]COMMUNICATION FEED (Scrolled {self.scroll_offset}/{max_scroll})[/bold #00ffff]" if self.scroll_offset > 0 else "[bold #00ffff]COMMUNICATION FEED[/bold #00ffff]"
        else:
            final_text = body_text
            title = "[bold #00ffff]COMMUNICATION FEED[/bold #00ffff]"

        self.layout["body"].update(Panel(final_text, title=title, border_style="#ff00ff"))
        
        # Telemetry panel
        telemetry = generate_telemetry_panel(vad_status="Listening" if not self.thinking else "Processing")
        self.layout["telemetry"].update(telemetry)

        # Footer with clock and controls help
        self.layout["footer"].update(
            Panel(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] — [bold #00ffff]Athena Core Active[/bold #00ffff] | Up/Down: Scroll | Space: Interrupt", border_style="#ff00ff")
        )
        return self.layout


    def add_partial(self, role: str, text: str):
        """Append partial text to the latest message of matching role."""
        if self.chat_history and self.chat_history[-1][0] == role:
            self.chat_history[-1][1] = self.chat_history[-1][1] + text
        else:
            # Create new entry if no matching role at end
            self.chat_history.append([role, text])

    def add_message(self, role: str, message: str, overwrite: bool = False):
        """Add or overwrite a message in chat history."""
        if overwrite and self.chat_history and self.chat_history[-1][0] == role:
            self.chat_history[-1][1] = message
        else:
            self.chat_history.append([role, message])
            # Reset scroll offset to bottom on new message if user was near bottom
            if self.scroll_offset <= 1:
                self.scroll_offset = 0

    def set_status(self, text: str):
        """Update active status text."""
        self.status = text

    def set_thinking(self, thinking: bool):
        """Set thinking state boolean."""
        self.thinking = thinking

    def run_live(self, runner):
        """Run the main UI live loop."""
        with Live(self.render(), console=self.console, refresh_per_second=10, screen=True) as live:
            self._live = live
            runner(live, self)


