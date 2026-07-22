# Athena Rewrite Plan: Lean Jarvis-like Autonomous Assistant

## Vision
Transform Athena into a lean, Jarvis-like assistant with:
- **Lean Architecture**: Single-file skills, hot-reloadable, minimal memory footprint
- **Autonomous Skill Loop**: Auto-discover, generate, test, register skills on-demand
- **Jarvis Persona**: Respectful, capable, proactive, context-aware
- **Resource Efficient**: Runs on consumer hardware (CPU + optional GPU)
- **Plug-and-Play Skills**: Single-file Python modules, hot-reloadable, zero-config

---

## Current Architecture Analysis

### Problems Identified
1. **File Explosion**: 40+ Python files, 20+ tool files, separate skill files
2. **Memory Heavy**: Multiple LLM instances, heavy dependencies (NeMo, torch, torchaudio)
3. **Skill Fragmentation**: 20+ separate tool files + skill files + registry + sandbox
4. **Heavy Dependencies**: torch, torchaudio, nemo_toolkit, fastmcp, rich, etc.
5. **No Autonomous Loop**: Skills must be manually created, no auto-forge loop
6. **Heavy Voice Stack**: Nemotron + Silero VAD + Kokoro TTS = heavy
5. **No Autonomous Dev Loop**: No continuous self-improvement cycle

### Core Assets to Preserve
- SkillForge (auto-generation + validation + sandbox) - **KEEP & CONSOLIDATE**
- SkillRegistry (hot-reload, dynamic discovery) - **KEEP & CONSOLIDATE**  
- SkillSandbox (AST validation, safe execution) - **KEEP & CONSOLIDATE**
- VectorMemory (SQLite + keyword search) - **KEEP & CONSOLIDATE**
- ConversationManager - **CONSOLIDATE**
- MoodEngine / JarvisPersona - **CONSOLIDATE into Persona Engine**
- RelationshipMemory - **CONSOLIDATE into Persona Engine**
- TUI (rich TUI) - **CONSOLIDATE to lightweight version**

---

## Target Lean Architecture

### Directory Structure (Target)
```
athena/
├── main.py                    # Entry point (~50 lines)
├── athena.py                  # Core orchestrator (~200 lines)
├── persona.py                 # Jarvis persona + mood + memory (~200 lines)
├── skills.py                  # Unified SkillEngine: forge + registry + sandbox (~300 lines)
├── memory.py                  # Unified Memory: vector + conversation + relationship (~200 lines)
├── voice.py                   # Lean voice: VAD + ASR + TTS (~200 lines)
├── tui.py                     # Lean TUI (~150 lines)
├── llm.py                     # LLM router (Gemini + local fallback) (~150 lines)
├── skills/                    # Auto-generated skills directory (single-file skills)
│   └── __init__.py            # Auto-loader
├── config.py                  # Config (~50 lines)
└── requirements.txt           # Minimal dependencies
```

### Dependency Reduction Target
| Current | Target | Replacement |
|---------|--------|-------------|
| torch + torchaudio + nemo_toolkit | whisper.cpp / faster-whisper | CPU-friendly ASR |
| kokoro + edge-tts | piper / kokoro-onnx | Lightweight TTS |
| fastmcp + mcp | Built-in MCP server | Built-in stdlib HTTP |
| rich + pynput | textual / curses | Lightweight TUI |
| pydantic | msgspec / pydantic v2 | Lighter validation |
| Multiple LLM libs | litellm only | Unified LLM router |

---

## Autonomous Development Loop Architecture

### The "Endless Dev Loop" - Core Innovation

```
┌─────────────────────────────────────────────────────────────────┐
│                    ATHENA AUTONOMOUS LOOP                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   OBSERVE   │───▶│   DECIDE    │───▶│    ACT      │        │
│  │  (Listen +  │    │  (LLM +     │    │  (Execute   │        │
│  │   Context)  │    │   Persona)  │    │   + Forge)  │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│        ▲                                    │                  │
│        │                                    ▼                  │
│        │                            ┌─────────────────┐        │
│        └───────────────────────────│    REFLECT      │        │
│                                    │  (Learn +       │        │
│                                    │   Optimize)     │        │
│                                    └─────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Loop Components

1. **OBSERVE** - Continuous listening + context gathering
   - Voice input (VAD + ASR streaming)
   - Context: conversation history, user prefs, time, system state
   - Skill registry state (what skills exist)

2. **DECIDE** - LLM + Persona reasoning
   - Jarvis persona: respectful, proactive, capable
   - Tool selection: existing skill vs forge new skill
   - Task planning for complex requests

3. **ACT** - Execute + Auto-Forge
   - Execute existing skills (MCP tools)
   - If no skill exists → **AUTO-FORGE**: Generate → Validate → Test → Register → Execute
   - Stream results to TTS + TUI

4. **REFLECT** - Learn + Optimize
   - Store interaction in memory (vector + relational)
   - Update user model / preferences
   - Track skill performance (success/failure/latency)
   - Prune unused skills, optimize hot skills
   - Self-heal: detect and fix broken skills

---

## Unified SkillEngine Design

### Single File: `skills.py` (~300 lines)

Combines:
- **SkillForge**: Code generation + validation + testing
- **SkillRegistry**: Discovery + hot-reload + registration  
- **SkillSandbox**: AST validation + safe execution
- **MCP Server**: Built-in FastMCP registration

### Skill File Format (Single File per Skill)
```python
# skills/weather_skill.py
SKILL_METADATA = {"name": "weather", "description": "Get weather", "version": "1.0.0"}

def get_weather(city: str, units: str = "metric") -> str:
    """Get current weather for a city."""
    # ... implementation
    return f"Weather in {city}: ..."

def get_forecast(city: str, days: int = 3) -> str:
    """Get multi-day forecast."""
    return f"Forecast for {city}..."
```

### SkillEngine API
```python
class SkillEngine:
    def __init__(self, llm_generate_fn, skills_dir="skills"):
        self.llm_generate = llm_generate_fn
        self.skills_dir = Path(skills_dir)
        self.registry = {}  # name -> (func, metadata)
        
    def discover(self) -> List[SkillInfo]      # Scan + load skills
    def get(self, name: str) -> Callable       # Get callable
    def list_all(self) -> List[SkillInfo]      # List available
    def forge(self, request: str) -> SkillInfo # Generate + validate + register
    def execute(self, name: str, **kwargs) -> str  # Execute skill
    def hot_reload(self) -> List[SkillInfo]    # Reload changed
    def prune_unused(self, max_age_days=30)    # Remove unused skills
```

---

## Unified Memory Engine Design

### Single File: `memory.py` (~200 lines)

Combines:
- **VectorMemory**: SQLite + keyword search (keep)
- **ConversationManager**: Session history
- **RelationshipMemory**: User preferences, personalization
- **MoodEngine**: Time-aware personality

### Memory Schema (SQLite)
```sql
-- Unified memories table
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    type TEXT,              -- 'fact' | 'preference' | 'conversation' | 'skill_usage'
    content TEXT,
    tags TEXT,              -- JSON array
    metadata TEXT,          -- JSON (session_id, sentiment, etc)
    created_at REAL,
    updated_at REAL,
    access_count INTEGER DEFAULT 0,
    last_accessed REAL
);

-- Indexes for fast search
CREATE INDEX idx_type ON memories(type);
CREATE INDEX idx_created ON memories(created_at);
CREATE INDEX idx_accessed ON memories(last_accessed);
```

### MemoryEngine API
```python
class MemoryEngine:
    def remember(self, content: str, type: str, tags: List[str], metadata: dict) -> int
    def recall(self, query: str, types: List[str]=None, limit=5) -> List[Memory]
    def get_context(self, query: str, max_tokens=2000) -> str  # For LLM context
    def record_interaction(self, user_input: str, assistant_response: str, sentiment: str)
    def get_user_profile(self) -> UserProfile
    def update_preference(self, key: str, value: str)
```

---

## Lean Voice Stack

### Single File: `voice.py` (~200 lines)

**ASR**: `faster-whisper` (CPU-optimized, no torch dependency at runtime)
- Model: `base.en` (~74MB) or `small.en` (~244MB)
- Streaming support via VAD chunks

**VAD**: `silero-vad` (ONNX, ~1MB, CPU-friendly)

**TTS**: `piper-tts` (ONNX, ~50MB models, CPU) or `kokoro-onnx` (~80MB)
- Pre-download model at setup

**Audio**: `sounddevice` (minimal)

### VoiceEngine API
```python
class VoiceEngine:
    def __init__(self, asr_model="base.en", tts_voice="en_US-lessac-medium"):
        self.vad = SileroVAD()
        self.asr = WhisperModel(asr_model)
        self.tts = PiperTTS(tts_voice)
        
    def listen(self) -> Generator[Tuple[str, bool], None, None]:  # (text, is_final)
        # VAD + streaming ASR
        
    def speak(self, text: str, streaming=True) -> Generator[bytes, None, None]:
        # Streaming TTS
        
    def interrupt(self):
        # Stop TTS immediately
```

---

## Lean TUI

### Single File: `tui.py` (~150 lines)

Use `textual` (lighter than rich + custom) or pure `curses` for ultra-lean.

### TUI Features
- Live transcript (scrollable)
- Status bar: Listening/Thinking/Speaking
- Skill registry view (toggle)
- Memory browser (toggle)
- Resource monitor (CPU/RAM/GPU)

---

## LLM Router

### Single File: `llm.py` (~150 lines)

```python
class LLMRouter:
    def __init__(self):
        self.primary = LiteLLM(model="gemini-2.5-pro")  # or configured
        self.fallback = LiteLLM(model="ollama/llama3.1:8b")  # Local
        
    async def generate(self, prompt: str, tools: List[Tool]=None, stream=True) -> AsyncGenerator[str]:
        try:
            async for chunk in self.primary.generate(prompt, tools, stream):
                yield chunk
        except Exception:
            async for chunk in self.fallback.generate(prompt, tools, stream):
                yield chunk
                
    def generate_sync(self, prompt: str, tools: List[Tool]=None) -> str:
        # Sync wrapper
```

---

## Autonomous Development Loop Implementation

### Main Loop (`athena.py`)

```python
class Athena:
    def __init__(self):
        self.persona = PersonaEngine()      # Jarvis personality + mood
        self.skills = SkillEngine(self.llm.generate)  # Auto-forge skills
        self.memory = MemoryEngine()         # Unified memory
        self.voice = VoiceEngine()           # Lean voice
        self.tui = TUI()                     # Lean TUI
        self.llm = LLMRouter()               # LLM router
        self.running = True
        
    async def run_loop(self):
        """The endless autonomous development loop"""
        self.skills.discover()  # Load existing skills
        
        # Start background reflection task
        asyncio.create_task(self.reflection_loop())
        
        while self.running:
            # OBSERVE
            async for text, is_final in self.voice.listen():
                if not is_final:
                    self.tui.update_partial(text)
                    continue
                    
                # DECIDE + ACT
                response = await self.process_request(text)
                
                # SPEAK
                async for audio_chunk in self.voice.speak(response):
                    self.voice.play(audio_chunk)
                    
                # REFLECT (async, non-blocking)
                asyncio.create_task(self.reflect_on_interaction(text, response))
                
    async def process_request(self, user_input: str) -> str:
        # 1. Get context from memory
        context = self.memory.get_context(user_input)
        user_profile = self.memory.get_user_profile()
        
        # 2. Build prompt with persona + context + available skills
        skills_info = self.skills.list_all()
        prompt = self.persona.build_prompt(user_input, context, user_profile, skills_info)
        
        # 3. LLM decides: use existing tool or forge new?
        response = ""
        async for chunk in self.llm.generate(prompt, tools=self.skills.get_tool_definitions()):
            response += chunk
            # Check for tool calls
            if tool_call := self.parse_tool_call(chunk):
                result = await self.execute_tool(tool_call)
                response += f"\n[Tool Result: {result}]"
                
        return response
        
    async def execute_tool(self, tool_call: ToolCall) -> str:
        # Try existing skill first
        if skill := self.skills.get(tool_call.name):
            return skill(**tool_call.args)
            
        # AUTO-FORGE: No skill exists, create it!
        if self.skills.can_forge(tool_call.name, tool_call.description):
            success, msg = self.skills.forge(f"Create a tool that {tool_call.description}")
            if success:
                # Retry execution with new skill
                skill = self.skills.get(tool_call.name)
                return skill(**tool_call.args)
            return f"Failed to forge skill: {msg}"
            
        return f"No skill available for {tool_call.name}"
        
    async def reflection_loop(self):
        """Background task: runs every 5 minutes"""
        while self.running:
            await asyncio.sleep(300)
            await self.reflect_and_optimize()
            
    async def reflect_and_optimize(self):
        # 1. Prune unused skills (>30 days no use)
        self.skills.prune_unused(max_age_days=30)
        
        # 2. Optimize hot skills (compile, cache)
        self.skills.optimize_hot_skills()
        
        # 3. Consolidate memories (summarize old conversations)
        self.memory.consolidate()
        
        # 4. Self-heal: re-validate skills, fix broken ones
        self.skills.self_heal(self.llm.generate)
        
        # 5. Update persona based on interaction patterns
        self.persona.evolve(self.memory.get_recent_interactions())
```

---

## Resource Requirements (Target)

| Resource | Target | Current |
|----------|--------|---------|
| RAM (idle) | < 500 MB | ~2-3 GB |
| RAM (active) | < 1.5 GB | ~4-6 GB |
| Disk (code) | < 5 MB | ~50 MB |
| Disk (models) | ~500 MB | ~3 GB |
| CPU (idle) | < 5% | ~15% |
| Startup time | < 3 sec | ~15 sec |

---

## Implementation Phases

### Phase 1: Core Consolidation (Week 1)
- [ ] Create `config.py` - unified config
- [ ] Create `memory.py` - unified memory engine
- [ ] Create `persona.py` - Jarvis persona + mood
- [ ] Create `skills.py` - unified SkillEngine (forge + registry + sandbox)
- [ ] Create `llm.py` - LLM router with LiteLLM

### Phase 2: Voice + TUI (Week 2)
- [ ] Create `voice.py` - faster-whisper + silero-vad + piper
- [ ] Create `tui.py` - textual-based lean TUI
- [ ] Create `athena.py` - main orchestrator with autonomous loop

### Phase 3: Integration & Testing (Week 3)
- [ ] Create `main.py` - entry point
- [ ] Write `requirements.txt` - minimal deps
- [ ] Test autonomous skill forging
- [ ] Test memory persistence
- [ ] Test voice loop

### Phase 4: Optimization (Week 4)
- [ ] Profile memory/CPU
- [ ] Optimize hot paths
- [ ] Add skill pre-compilation
- [ ] Add model quantization
- [ ] Stress test 24h run

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| faster-whisper not streaming well | Use VAD chunks + batch transcription |
| piper TTS latency | Pre-generate common phrases, stream chunks |
| SkillForge LLM failures | Retry with error feedback, fallback templates |
| Memory growth | Auto-prune, consolidate, SQLite WAL mode |
| Skill conflicts | Namespace skills, validate signatures |

---

## Success Criteria

- [ ] Cold start < 3 seconds
- [ ] Idle RAM < 500 MB
- [ ] Voice latency < 800ms (speech to first token)
- [ ] Skill forge success rate > 80%
- [ ] 24h continuous run without memory leak
- [ ] Zero manual skill files - all auto-generated
- [ ] Jarvis persona consistently respectful & capable