"""
Athena Configuration - Centralized settings with environment variable overrides.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class Config:
    """All Athena configuration in one place."""

    # ==================== LLM ====================
    # Default to Ollama if no API keys are set
    llm_primary_model: str = os.getenv("ATHENA_LLM_PRIMARY", "ollama/llama3.2:latest")
    llm_fallback_model: str = os.getenv("ATHENA_LLM_FALLBACK", "gemini/gemini-2.5-flash")
    llm_temperature: float = float(os.getenv("ATHENA_LLM_TEMP", "0.7"))
    llm_max_tokens: int = int(os.getenv("ATHENA_LLM_MAX_TOKENS", "4096"))

    # API Keys
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # ==================== Voice ====================
    stt_engine: str = os.getenv("ATHENA_STT_ENGINE", "whisper")  # whisper, nemotron
    stt_model: str = os.getenv("ATHENA_STT_MODEL", "base.en")
    stt_device: str = os.getenv("ATHENA_STT_DEVICE", "cpu")  # cpu, cuda
    stt_compute_type: str = os.getenv("ATHENA_STT_COMPUTE", "int8")

    tts_engine: str = os.getenv("ATHENA_TTS_ENGINE", "piper")  # piper, kokoro
    tts_voice: str = os.getenv("ATHENA_TTS_VOICE", "en_US-lessac-medium")

    # Audio
    sample_rate: int = 16000
    block_size: int = 512
    headphones_mode: bool = os.getenv("ATHENA_HEADPHONES", "0") == "1"

    # ==================== Memory ====================
    memory_db: str = os.getenv("ATHENA_MEMORY_DB", str(PROJECT_ROOT / "athena_memory.db"))
    memory_max_entries: int = int(os.getenv("ATHENA_MEMORY_MAX", "10000"))
    memory_consolidate_days: int = int(os.getenv("ATHENA_MEMORY_CONSOLIDATE", "7"))

    # ==================== Skills ====================
    skills_dir: str = os.getenv("ATHENA_SKILLS_DIR", str(PROJECT_ROOT / "src" / "tools" / "skills"))
    skill_timeout_seconds: int = int(os.getenv("ATHENA_SKILL_TIMEOUT", "10"))
    skill_max_retries: int = int(os.getenv("ATHENA_SKILL_RETRIES", "2"))
    skill_prune_days: int = int(os.getenv("ATHENA_SKILL_PRUNE_DAYS", "30"))

    # ==================== Persona ====================
    user_name: str = os.getenv("ATHENA_USER_NAME", "Sir")

    # ==================== Paths ====================
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    logs_dir: Path = PROJECT_ROOT / "logs"

    def __post_init__(self):
        """Override fields from environment variables on instantiation."""
        self.llm_primary_model = os.getenv("ATHENA_LLM_PRIMARY", self.llm_primary_model)
        self.llm_fallback_model = os.getenv("ATHENA_LLM_FALLBACK", self.llm_fallback_model)
        self.llm_temperature = float(os.getenv("ATHENA_LLM_TEMP", str(self.llm_temperature)))
        self.llm_max_tokens = int(os.getenv("ATHENA_LLM_MAX_TOKENS", str(self.llm_max_tokens)))
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", self.gemini_api_key)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.stt_engine = os.getenv("ATHENA_STT_ENGINE", self.stt_engine)
        self.stt_model = os.getenv("ATHENA_STT_MODEL", self.stt_model)
        self.stt_device = os.getenv("ATHENA_STT_DEVICE", self.stt_device)
        self.stt_compute_type = os.getenv("ATHENA_STT_COMPUTE", self.stt_compute_type)
        self.tts_engine = os.getenv("ATHENA_TTS_ENGINE", self.tts_engine)
        self.tts_voice = os.getenv("ATHENA_TTS_VOICE", self.tts_voice)
        self.headphones_mode = os.getenv("ATHENA_HEADPHONES", "1" if self.headphones_mode else "0") == "1"
        self.memory_db = os.getenv("ATHENA_MEMORY_DB", self.memory_db)
        self.memory_max_entries = int(os.getenv("ATHENA_MEMORY_MAX", str(self.memory_max_entries)))
        self.memory_consolidate_days = int(os.getenv("ATHENA_MEMORY_CONSOLIDATE", str(self.memory_consolidate_days)))
        self.skills_dir = os.getenv("ATHENA_SKILLS_DIR", self.skills_dir)
        self.skill_timeout_seconds = int(os.getenv("ATHENA_SKILL_TIMEOUT", str(self.skill_timeout_seconds)))
        self.skill_max_retries = int(os.getenv("ATHENA_SKILL_RETRIES", str(self.skill_max_retries)))
        self.skill_prune_days = int(os.getenv("ATHENA_SKILL_PRUNE_DAYS", str(self.skill_prune_days)))
        self.user_name = os.getenv("ATHENA_USER_NAME", self.user_name)


config = Config()

# Ensure directories exist
config.data_dir.mkdir(exist_ok=True)
config.logs_dir.mkdir(exist_ok=True)
Path(config.skills_dir).mkdir(parents=True, exist_ok=True)