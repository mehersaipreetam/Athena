from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from datetime import datetime

class TUIManager:
    def __init__(self):
        self.console = Console()
        self.layout = self._create_layout()

        # Dynamic data
        self.status = "Initializing..."
        self.partial_text = ""
        self.final_text = ""
        self.response = ""

    def _create_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        layout["body"].split_row(
            Layout(name="stt"),
            Layout(name="llm")
        )
        return layout

    def render(self):
        self.layout["header"].update(
            Panel(f"[bold blue]Athena Assistant[/bold blue]\nStatus: {self.status}")
        )
        self.layout["stt"].update(
            Panel(
                f"[bold cyan]Listening[/bold cyan]\n"
                f"[dim]Partial:[/dim] {self.partial_text}\n\n"
                f"[bold white]Final:[/bold white] {self.final_text}"
            )
        )
        self.layout["llm"].update(
            Panel(f"[bold magenta]Response:[/bold magenta]\n{self.response}")
        )
        self.layout["footer"].update(
            Panel(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] — Athena is active.")
        )
        return self.layout

    def update_status(self, text: str):
        self.status = text

    def update_partial(self, text: str):
        self.partial_text = text

    def update_final(self, text: str):
        self.final_text = text

    def update_response(self, text: str):
        self.response = text

    def run_live(self, runner):
        """runner = callable that updates TUI"""
        with Live(self.render(), console=self.console, refresh_per_second=5) as live:
            runner(live, self)
