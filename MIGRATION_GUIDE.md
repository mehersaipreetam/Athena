# Athena Lean Architecture Migration Guide

## Overview

This guide documents the transition from the old monolithic Athena architecture (40+ files, heavy dependencies) to the new lean architecture (8 core files, minimal dependencies).

---

## Old vs New Architecture

### Old Architecture (Deprecated)
```
src/
├── core/                 # 8 files
│   ├── base_assistant.py    # Main orchestrator (400+ lines)
│   ├── skill_forge.py       # Skill generation
│   ├── skill_registry.py    # Skill registry
│   ├── skill_sandbox.py     # Skill validation
│   ├── conversation_manager.py
│   ├── mood_engine.py
│   ├── relationship_memory.py
│   └── ... (7 more files)
├── llm/                  # 4 files
├── memory/               # 1 file
├── tools/                # 20+ skill files
├── voice/                # 8 files
└── tui/                  # 2 files
```
**Problems:**
- 40+ Python files
- Heavy dependencies (torch, torchaudio, nemo_toolkit, kokoro, fastmcp)
- No autonomous skill loop
- Memory scattered across multiple systems
- Complex startup sequence
- ~2-3GB RAM idle

### New Architecture (Lean)
```
src/athena/
├── __init__.py           # Package exports
├── config.py             # Centralized config (1 file)
├── core.py               # Main orchestrator (1 file, ~300 lines)
├── memory.py             # Unified memory engine (1 file)
├── persona.py            # Jarvis persona + mood (1 file)
├── skills.py             # Skill engine: forge + registry + sandbox (1 file)
├── llm.py                # LLM router (1 file)
├── voice.py              # STT + TTS (1 file)
└── main.py               # Entry point
```
**Benefits:**
- 8 core files (95% reduction)
- Minimal dependencies (~200MB vs ~3GB)
- Built-in autonomous skill development loop
- Unified memory with auto-consolidation
- Lean startup (< 3 seconds)
- ~300-500MB RAM idle

---

## Migration Steps

### 1. Install New Dependencies
```bash
# Lean install (recommended)
pip install -r requirements-lean.txt

# Or full install with optional GPU features
pip install -e .[gpu-voice,local-llm,web-search]
```

### 2. Run New Architecture
```bash
# Default: faster-whisper + piper TTS
python main.py

# With specific engines
python main.py --stt whisper --tts piper

# Text-only mode (no voice)
python main.py --no-tui

# Debug mode
python main.py --debug
```

### 3. Migrate Existing Skills
Old skill format → New skill format:

**Old (multiple files):**
```
src/tools/weather_tool.py
src/tools/calendar_tool.py
src/core/skill_forge.py
src/core/skill_registry.py
```

**New (single file per skill):**
```
src/tools/skills/weather_skill.py
src/tools/skills/calculator_skill.py
```

Each skill is a single Python file with:
```python
SKILL_METADATA = {
    "name": "skill_name",
    "description": "What it does",
    "version": "1.0.0",
}

def function_name(param: type) -> str:
    """Docstring becomes tool description."""
    return "result"
```

**Auto-migration:** The new SkillEngine will auto-discover and register any valid skill files in the skills directory.

### 4. Memory Migration
Old databases are compatible - the new MemoryEngine uses the same SQLite schema with additional tables. Run:
```python
from athena.memory import MemoryEngine
memory = MemoryEngine("athena_memory.db")
memory.consolidate()  # Migrate old conversations to summaries
```

### 5. Configuration
New config is in `src/athena/config.py` with environment variable overrides:
```bash
export ATHENA_LLM_PRIMARY=gemini/gemini-2.5-flash
export ATHENA_STT_ENGINE=whisper
export ATHENA_TTS_ENGINE=piper
export ATHENA_HEADPHONES=1
```

---

## Key Feature Mapping

| Old Feature | New Implementation |
|-------------|-------------------|
| `SkillForge` | `SkillEngine.forge()` in `skills.py` |
| `SkillRegistry` | `SkillEngine.discover()/get()/list_all()` |
| `SkillSandbox` | `SkillSandbox` class in `skills.py` |
| `ConversationManager` | `MemoryEngine.record_interaction()/get_recent_conversations()` |
| `MoodEngine` | `PersonaEngine` with `Mood` enum in `persona.py` |
| `RelationshipMemory` | `MemoryEngine.get_user_profile()/update_preference()` |
| `VectorMemory` | `MemoryEngine.recall()/get_context()` (keyword-based) |
| `SelfHealing` | `SkillEngine.self_heal()` + `SkillEngine.prune_unused()` |
| `SwarmManager` | Removed (use async tasks in main loop) |
| `TaskPlanner` | Removed (LLM handles planning via tool calls) |

---

## Running the Autonomous Loop

The new architecture includes a built-in autonomous development loop:

```python
from athena.core import AthenaAssistant

# The main loop automatically:
# 1. Listens for voice input
# 2. Builds context from memory + persona
# 3. LLM decides: use existing skill OR forge new skill
# 4. Executes tool(s)
# 5. Speaks response
# 6. Records to memory
# 7. Periodically: consolidates memory, prunes unused skills, optimizes hot skills

assistant = AthenaAssistant()
assistant.run()  # Runs forever until shutdown command
```

### Skill Auto-Forge
When user requests something without an existing skill:
```
User: "Create a tool to track my crypto portfolio"
Athena: "I'll create a new tool for that, Sir."
[Generates Python code → Validates in sandbox → Tests → Registers → Executes]
Athena: "Successfully forged 'crypto_tracker' skill with functions: get_price, get_portfolio_value"
```

---

## Performance Targets

| Metric | Old | New Target |
|--------|-----|------------|
| Startup time | ~15s | < 3s |
| Idle RAM | ~2-3 GB | < 500 MB |
| Active RAM | ~4-6 GB | < 1.5 GB |
| Voice latency | ~1-2s | < 800ms |
| Skill forge time | N/A | < 10s |
| Disk (code) | ~50 MB | < 5 MB |
| Disk (models) | ~3 GB | ~500 MB |

---

## Troubleshooting

### STT Not Working
```bash
# Install faster-whisper
pip install faster-whisper

# Test
python -c "from faster_whisper import WhisperModel; print('OK')"
```

### TTS Not Working
```bash
# Install piper
pip install piper-tts

# Download voice model
piper --model en_US-lessac-medium --download
```

### LLM Errors
```bash
# Check API key
export GEMINI_API_KEY=your_key

# Test
python -c "import litellm; print(litellm.completion(model='gemini/gemini-2.5-flash', messages=[{'role':'user','content':'hi'}]))"
```

### Skills Not Loading
```bash
# Check skills directory
ls src/tools/skills/

# Files must:
# 1. End in .py (not __init__.py)
# 2. Have SKILL_METADATA dict
# 3. Have at least one public function with docstring + type hints
```

---

## Development Workflow

### Adding a New Skill Manually
1. Create `src/tools/skills/my_skill.py`
2. Follow skill format (see `calculator_skill.py`)
3. Restart Athena or call `skills.hot_reload()`

### Testing Skill Forge
```python
from athena.skills import SkillEngine
from athena.memory import MemoryEngine

memory = MemoryEngine()
skills = SkillEngine(llm_generate_fn=my_llm, memory=memory)
success, msg = skills.forge("Create a tool that fetches weather from OpenWeatherMap")
print(msg)
```

### Running Tests
```bash
pytest test/test_lean_architecture.py -v
```

---

## Rollback Plan

If issues arise, the old architecture is preserved in git history:
```bash
git checkout feat/mcp-tool  # Old branch
# Or check specific commit
git log --oneline | head -20
```

The old entry point was `main.py` → `core.base_assistant:run_assistant`.

---

## Future Enhancements

- [ ] Vector embeddings for semantic memory search
- [ ] Skill marketplace / sharing
- [ ] Multi-user support
- [ ] Plugin system for STT/TTS engines
- [ ] Web UI dashboard
- [ ] Mobile companion app