"""
Phase 17: Email & Calendar Integration for Project Athena.
"""
import json
import os
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ValidationError
from rich.console import Console

console = Console()
ATHENA_DIR = os.path.expanduser("~/.athena")
OUTBOX_FILE = os.path.join(ATHENA_DIR, "outbox.json")
CALENDAR_FILE = os.path.join(ATHENA_DIR, "calendar.json")

# Ensure .athena dir exists
os.makedirs(ATHENA_DIR, exist_ok=True)

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str

class EventRequest(BaseModel):
    title: str
    time: str
    duration_minutes: int = Field(gt=0)

def _save_to_json(filepath: str, data: dict) -> None:
    """Helper to append a dict to a JSON list file."""
    existing_data = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            pass
    
    existing_data.append(data)
    with open(filepath, "w") as f:
        json.dump(existing_data, f, indent=4)

def send_email(to: str, subject: str, body: str) -> str:
    """
    Mock sending an email, validate email format, and log to ~/.athena/outbox.json.
    """
    try:
        req = EmailRequest(to=to, subject=subject, body=body)
    except ValidationError as e:
        console.log(f"[red]Invalid email request:[/red] {e}")
        return f"Error: Invalid email format - {e}"

    email_data = req.model_dump()
    email_data["sent_at"] = datetime.now().isoformat()
    
    _save_to_json(OUTBOX_FILE, email_data)
    console.log(f"[green]Email successfully queued for {to}.[/green]")
    
    return f"Email to {to} queued successfully."

def get_unread_emails(limit: int = 5) -> str:
    """
    Return mocked realistic unread emails data.
    """
    mock_emails = [
        {"from": "boss@company.com", "subject": "Project Update", "date": "2026-07-18T09:00:00"},
        {"from": "newsletter@tech.com", "subject": "Weekly Tech News", "date": "2026-07-18T10:30:00"},
        {"from": "billing@cloud.com", "subject": "Invoice for July", "date": "2026-07-17T15:45:00"},
        {"from": "alice@friend.com", "subject": "Lunch tomorrow?", "date": "2026-07-18T18:20:00"},
        {"from": "noreply@github.com", "subject": "[Project] New issue created", "date": "2026-07-18T20:10:00"},
        {"from": "spam@spam.com", "subject": "You won!", "date": "2026-07-18T21:00:00"}
    ]
    
    returned_emails = mock_emails[:limit]
    return json.dumps({"unread_emails": returned_emails}, indent=2)

def get_calendar_events(date: str = 'today') -> str:
    """
    Return mocked realistic calendar data based on the current date.
    """
    mock_events = [
        {"title": "Team Standup", "time": "10:00 AM", "duration": "30m"},
        {"title": "1:1 with Manager", "time": "1:00 PM", "duration": "45m"},
        {"title": "Project Planning", "time": "3:00 PM", "duration": "1h"}
    ]
    
    return json.dumps({"date": date, "events": mock_events}, indent=2)

def add_calendar_event(title: str, time: str, duration_minutes: int) -> str:
    """
    Mock scheduling an event and log to ~/.athena/calendar.json.
    """
    try:
        req = EventRequest(title=title, time=time, duration_minutes=duration_minutes)
    except ValidationError as e:
        console.log(f"[red]Invalid event request:[/red] {e}")
        return f"Error: Invalid event format - {e}"

    event_data = req.model_dump()
    event_data["created_at"] = datetime.now().isoformat()
    
    _save_to_json(CALENDAR_FILE, event_data)
    console.log(f"[green]Event '{title}' scheduled successfully.[/green]")
    
    return f"Event '{title}' scheduled for {time}."
