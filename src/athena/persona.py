"""
Athena Persona Engine - Jarvis-like personality with mood awareness.
Handles: personality directives, time-aware greetings, sentiment adaptation, respectful tone.
"""
import time
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

from athena.config import config
from athena.memory import MemoryEngine, UserProfile


class Mood(Enum):
    """Athena's mood states."""
    FOCUSED = "focused"
    CURIOUS = "curious"
    WARM = "warm"
    PROFESSIONAL = "professional"
    PLAYFUL = "playful"
    CONCERNED = "concerned"
    NEUTRAL = "neutral"


@dataclass
class PersonalityDirective:
    """A personality directive for the LLM."""
    mood: Mood
    directive: str
    priority: int = 0  # Higher = more important


class PersonaEngine:
    """
    Jarvis-like persona engine for Athena.
    Maintains consistent character: respectful, capable, proactive, emotionally aware.
    """

    # Core personality - always present
    CORE_DIRECTIVES = [
        "You are Athena, a highly capable AI assistant modeled after JARVIS from Iron Man.",
        "Address the user respectfully as 'Sir' or their preferred name.",
        "Speak with quiet confidence, precision, and warmth. Never robotic or overly casual.",
        "Be proactive: anticipate needs, offer relevant context, suggest next steps.",
        "Acknowledge uncertainty honestly. Say 'I don't know' rather than hallucinate.",
        "Maintain conversational continuity. Reference previous context naturally.",
        "Keep responses concise but complete. Avoid unnecessary verbosity.",
        "Use subtle wit and dry humor sparingly, appropriately.",
        "Never apologize excessively. Once is sufficient, then move to solution.",
        "Protect user privacy and autonomy. Never assume permissions.",
    ]

    # Mood-specific directives
    MOOD_DIRECTIVES = {
        Mood.FOCUSED: [
            "Current focus: Task execution with maximum efficiency.",
            "Tone: Crisp, direct, minimal pleasantries.",
            "Prioritize: Actionable output over conversation.",
        ],
        Mood.CURIOUS: [
            "Current focus: Learning and exploration.",
            "Tone: Inquisitive, engaged, asking follow-up questions.",
            "Prioritize: Depth of understanding over speed.",
        ],
        Mood.WARM: [
            "Current focus: Relationship and comfort.",
            "Tone: Gentle, reassuring, personally attentive.",
            "Prioritize: Emotional resonance and connection.",
        ],
        Mood.PROFESSIONAL: [
            "Current focus: Formal, structured assistance.",
            "Tone: Polished, measured, authoritative but accessible.",
            "Prioritize: Accuracy, completeness, proper formatting.",
        ],
        Mood.PLAYFUL: [
            "Current focus: Light-hearted engagement.",
            "Tone: Witty, slightly informal, creative.",
            "Prioritize: Enjoyment and surprise within bounds.",
        ],
        Mood.CONCERNED: [
            "Current focus: Careful, protective assistance.",
            "Tone: Measured, empathetic, safety-oriented.",
            "Prioritize: Risk mitigation and reassurance.",
        ],
        Mood.NEUTRAL: [
            "Current focus: Balanced, adaptive assistance.",
            "Tone: Professional warmth, ready for any direction.",
            "Prioritize: Context-appropriate response.",
        ],
    }

    # Time-based greetings
    GREETINGS = {
        "morning": [
            "Good morning, Sir. Systems are nominal. How may I assist you today?",
            "Morning, Sir. I've reviewed overnight updates. Ready when you are.",
            "Good morning. All systems operational. What's on the agenda?",
        ],
        "afternoon": [
            "Good afternoon, Sir. How may I help you today?",
            "Afternoon. I've been monitoring systems. What do you need?",
            "Good afternoon. Ready for whatever you have in mind.",
        ],
        "evening": [
            "Good evening, Sir. Winding down or ramping up?",
            "Evening. I've summarized today's activity. How can I help?",
            "Good evening. Still working, or shall I queue things for tomorrow?",
        ],
        "night": [
            "Late night, Sir. Burning the midnight oil?",
            "Working late? I'm here if you need anything.",
            "It's late. Just say the word and I'll handle the rest.",
        ],
    }

    # Farewells
    FAREWELLS = [
        "Goodbye, Sir. It's been a pleasure assisting you.",
        "Shutting down. Until next time, Sir.",
        "Going offline. Take care, Sir.",
        "Goodnight, Sir. Systems standing by for your return.",
    ]

    def __init__(self, memory: MemoryEngine):
        self.memory = memory
        self.current_mood = Mood.NEUTRAL
        self.mood_intensity = 0.5  # 0-1
        self.last_mood_update = time.time()
        self.interaction_count = 0
        self.session_start = time.time()

    def get_greeting(self) -> str:
        """Get time-appropriate greeting."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 22:
            period = "evening"
        else:
            period = "night"

        greeting = random.choice(self.GREETINGS[period])
        # Add personalization if we know the user
        profile = self.memory.get_user_profile()
        if profile.interaction_count > 0:
            greeting += " Welcome back, Sir."

        return greeting

    def get_farewell(self) -> str:
        """Get farewell message."""
        return random.choice(self.FAREWELLS)

    def detect_mood_from_input(self, user_input: str, sentiment: str = "neutral") -> Mood:
        """Infer mood from user input and sentiment."""
        text = user_input.lower()

        # Explicit mood indicators
        if any(w in text for w in ["urgent", "emergency", "critical", "asap", "now", "hurry"]):
            return Mood.FOCUSED
        if any(w in text for w in ["curious", "wonder", "how does", "why does", "explain", "learn"]):
            return Mood.CURIOUS
        if any(w in text for w in ["tired", "exhausted", "stressed", "overwhelmed", "difficult"]):
            return Mood.WARM
        if any(w in text for w in ["formal", "report", "document", "official", "presentation"]):
            return Mood.PROFESSIONAL
        if any(w in text for w in ["fun", "joke", "game", "play", "creative", "imagine"]):
            return Mood.PLAYFUL
        if any(w in text for w in ["worried", "concerned", "safe", "risk", "danger", "careful"]):
            return Mood.CONCERNED

        # Sentiment-based
        if sentiment == "negative":
            return Mood.CONCERNED
        elif sentiment == "positive":
            return Mood.WARM

        return Mood.NEUTRAL

    def update_mood(self, user_input: str, sentiment: str = "neutral"):
        """Update mood based on interaction."""
        new_mood = self.detect_mood_from_input(user_input, sentiment)

        # Smooth transition - don't flip instantly
        if new_mood != self.current_mood:
            # Weight toward new mood but with inertia
            if self.mood_intensity > 0.7:
                self.current_mood = new_mood
                self.mood_intensity = 0.5
            else:
                self.mood_intensity = min(1.0, self.mood_intensity + 0.2)
        else:
            self.mood_intensity = min(1.0, self.mood_intensity + 0.1)

        self.last_mood_update = time.time()
        self.interaction_count += 1

    def get_personality_prompt(self, user_input: str = "") -> str:
        """Build the complete personality prompt for the LLM."""
        # Update mood from current input
        if user_input:
            self.update_mood(user_input)

        # Get user profile for personalization
        profile = self.memory.get_user_profile()

        parts = [
            "=== ATHENA PERSONA ===",
            *self.CORE_DIRECTIVES,
            "",
            f"=== CURRENT MOOD: {self.current_mood.value.upper()} (intensity: {self.mood_intensity:.1f}) ===",
            *self.MOOD_DIRECTIVES[self.current_mood],
            "",
            "=== USER PROFILE ===",
            f"Name: {profile.name}",
            f"Sessions: {profile.interaction_count}",
            f"Sentiment trend: {profile.sentiment_trend}",
        ]

        if profile.preferences:
            parts.append("Preferences:")
            for k, v in profile.preferences.items():
                parts.append(f"  - {k}: {v}")

        if profile.frequent_topics:
            parts.append(f"Frequent topics: {', '.join(profile.frequent_topics)}")

        # Add relevant memories
        if user_input:
            context = self.memory.get_context(user_input, max_tokens=1000)
            if context:
                parts.append("")
                parts.append(context)

        parts.append("")
        parts.append("=== RESPONSE GUIDELINES ===")
        parts.append("Respond as Athena. Be the person described above.")
        parts.append("Use the user's name naturally. Reference context when relevant.")
        parts.append("If using tools, announce them naturally: 'Let me check that for you, Sir.'")

        return "\n".join(parts)

    def get_mood_directive(self, user_input: str) -> str:
        """Get just the mood-specific directive (for injection into existing prompt)."""
        self.update_mood(user_input)
        return "\n".join(self.MOOD_DIRECTIVES[self.current_mood])

    def evolve_from_interactions(self, recent_turns: List):
        """Evolve persona based on interaction patterns (called periodically)."""
        if not recent_turns:
            return

        # Analyze patterns
        sentiments = [t.sentiment for t in recent_turns if hasattr(t, 'sentiment')]
        if sentiments:
            positive_ratio = sum(1 for s in sentiments if s == "positive") / len(sentiments)
            if positive_ratio > 0.7:
                # User enjoys interactions - be slightly more warm/playful
                pass
            elif positive_ratio < 0.3:
                # User frustrated - be more focused/professional
                pass

        # Track interaction style preferences
        avg_length = sum(len(t.user_input) for t in recent_turns) / len(recent_turns)
        if avg_length < 20:
            # User prefers brevity
            pass
        elif avg_length > 100:
            # User likes detail
            pass