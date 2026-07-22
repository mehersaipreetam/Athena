"""
Athena - Lean Jarvis-like AI Assistant
Unified package for all core subsystems.
"""
from .config import config
from .core import AthenaAssistant
from .memory import MemoryEngine
from .persona import PersonaEngine
from .skills import SkillEngine
from .llm import LLMRouter
from .voice import create_stt, create_tts

__version__ = "0.2.0"
__all__ = [
    "config",
    "AthenaAssistant",
    "MemoryEngine",
    "PersonaEngine",
    "SkillEngine",
    "LLMRouter",
    "create_stt",
    "create_tts",
]