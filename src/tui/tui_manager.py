from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from datetime import datetime

class TUIManager:
    def __init__(self):
        self.console = Console()
        self.layout = self._create_layout()
        self.chat_history = []  # Stores conversation lines
        self.status = "Initializing..."
        self.partial_text = ""
        self.final_text = ""
        self.thinking = False

    def _create_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=10),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        return layout

    def render(self):
        # Header with big bold Athena
        header_text = Text()
        header_text.append(" █████╗ ████████╗██╔══██╗███████╗███╗   ██╗ █████╗ \n", style="bold magenta")
        header_text.append("██╔══██╗╚══██╔══╝██║  ██║██╔════╝████╗  ██║██╔══██╗\n", style="bold magenta")
        header_text.append("███████║   ██║   ███████║█████╗  ██╔██╗ ██║███████║\n", style="bold magenta")
        header_text.append("██╔══██║   ██║   ██╔══██║██╔══╝  ██║╚██╗██║██╔══██║\n", style="bold magenta")
        header_text.append("██║  ██║   ██║   ██║  ██║███████╗██║ ╚████║██║  ██║\n", style="bold magenta")
        header_text.append("╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝\n", style="bold magenta")
        header_text.append(f"Status: {self.status}", style="bold yellow")
        self.layout["header"].update(Panel(Align.center(header_text)))

        # Body with scrollable chat
        body_text = Text()
        for role, line in self.chat_history:
            if role == "You":
                body_text.append("\n")
                body_text.append("You: ", style="green")
                body_text.append(f"{line}\n", style="cyan")
            else:  # Athena
                body_text.append("Athena: ", style="red")
                body_text.append(f"{line}\n", style="cyan")
        # Show thinking if active
        if self.thinking:
            body_text.append("Athena: ", style="red")
            body_text.append("...thinking\n", style="cyan")
        self.layout["body"].update(Panel(body_text, title="Conversation", border_style="blue"))

        # Footer with time
        self.layout["footer"].update(
            Panel(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] — Athena is active.")
        )
        return self.layout
    
    def add_partial(self, role, text: str):
        if self.chat_history[-1][0] == role:
            self.chat_history[-1][1] = self.chat_history[-1][1] + text # Update last entry

    def add_message(self, role, message):
        self.chat_history.append([role, message])

    def set_status(self, text):
        self.status = text

    def set_thinking(self, thinking: bool):
        self.thinking = thinking

    def run_live(self, runner):
        with Live(self.render(), console=self.console, refresh_per_second=5) as live:
            runner(live, self)
