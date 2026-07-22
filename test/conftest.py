import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from athena.config import config

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("ATHENA_LLM_PRIMARY", "test/primary")
    monkeypatch.setenv("ATHENA_LLM_FALLBACK", "test/fallback")
    monkeypatch.setenv("ATHENA_USER_NAME", "TestUser")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(config, "llm_primary_model", "test/primary")
    monkeypatch.setattr(config, "llm_fallback_model", "test/fallback")

@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path for MemoryEngine."""
    db_file = tmp_path / "test_memory.db"
    return str(db_file)

@pytest.fixture(autouse=True)
def override_config_db(temp_db_path, monkeypatch):
    """Override config database path to use temp_db_path."""
    monkeypatch.setattr(config, "memory_db", temp_db_path)
    monkeypatch.setattr(config, "skills_dir", str(Path(temp_db_path).parent / "test_skills"))

@pytest.fixture
def mock_litellm():
    """Mock litellm completion calls."""
    with patch("litellm.completion") as mock_comp, \
         patch("litellm.acompletion", new_callable=AsyncMock) as mock_acomp:
        yield mock_comp, mock_acomp

@pytest.fixture
def mock_stt_tts():
    """Mock STT and TTS engines."""
    with patch("athena.voice.WhisperSTT") as mock_whisper, \
         patch("athena.voice.PiperTTS") as mock_piper:
        yield mock_whisper, mock_piper
