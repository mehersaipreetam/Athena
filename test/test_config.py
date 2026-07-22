import os
from athena.config import Config

def test_config_defaults(monkeypatch):
    # Clear env vars that might affect defaults
    monkeypatch.delenv("ATHENA_LLM_PRIMARY", raising=False)
    monkeypatch.delenv("ATHENA_LLM_FALLBACK", raising=False)
    monkeypatch.delenv("ATHENA_LLM_TEMP", raising=False)
    
    config = Config()
    assert config.llm_primary_model == "ollama/llama3.2:latest"
    assert config.llm_fallback_model == "gemini/gemini-2.5-flash"
    assert config.llm_temperature == 0.7

def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("ATHENA_LLM_PRIMARY", "custom/primary")
    monkeypatch.setenv("ATHENA_LLM_TEMP", "0.5")
    monkeypatch.setenv("ATHENA_SKILL_TIMEOUT", "20")
    
    config = Config()
    assert config.llm_primary_model == "custom/primary"
    assert config.llm_temperature == 0.5
    assert config.skill_timeout_seconds == 20
