# Athena Web App - Lean Jarvis-like AI Assistant

## Overview
A complete web-based interface for Athena with real-time chat, skill management, memory browsing, and system monitoring.

## Features Implemented

### 1. Real-time Chat Interface
- WebSocket-based real-time communication
- Streaming responses with typing indicator
- Message history with timestamps
- Keyboard shortcuts (Enter to send, Shift+Enter for newline, Ctrl+K to focus input)

### 2. Skill Management
- **Browse Skills**: List all available skills with descriptions, versions, usage stats
- **Forge New Skills**: Natural language skill creation via SkillForge
- **Execute Skills**: Direct skill execution with arguments
- Hot-reload of skills

### 3. Memory Browser
- Search long-term memory by query
- View memory items with type, tags, timestamps
- Memory statistics

### 4. System Monitoring
- **Memory Stats**: Total entries, conversations, DB size, breakdown by type
- **Skill Stats**: Total skills, sync/async breakdown, usage metrics
- **Persona**: Current mood, interaction count
- **System**: Uptime, model info, mode

### 5. Jarvis-inspired UI Design
- Dark theme with cyan/magenta accents
- Monospace font (JetBrains Mono) for technical feel
- Space Grotesk for UI elements
- Smooth animations and transitions
- Responsive layout (collapsible sidebar on mobile)
- Status indicator with pulsing animation

## Architecture

### Frontend (`web/`)
```
web/
├── server.py              # FastAPI backend with WebSocket
├── start_web.sh           # Startup script
├── templates/
│   └── index.html         # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css      # Complete styling
│   └── js/
│       └── app.js         # Frontend application
```

### Backend Integration
- **FastAPI** for REST API + WebSocket
- **Athena Core** integration via event system
- **WebSocket** for real-time chat and updates
- **Event Emitter** in Athena Core broadcasts:
  - `thinking_start` / `thinking_end`
  - `assistant_response`
  - `interaction_complete`
  - `status` updates

## API Endpoints

### REST
- `GET /` - Web UI
- `GET /api/health` - Health check
- `GET /api/skills` - List skills
- `POST /api/skills/forge` - Create skill
- `POST /api/skills/execute` - Execute skill
- `POST /api/memory/query` - Search memory
- `GET /api/memory/stats` - Memory stats
- `GET /api/stats` - Full system stats
- `POST /api/chat` - Send text (HTTP fallback)

### WebSocket (`/ws/{client_id}`)
**Messages:**
- `{type: "chat", text: "..."}` - Send message
- `{type: "get_skills"}` - Refresh skills
- `{type: "forge_skill", description: "..."}` - Create skill
- `{type: "query_memory", query: "...", limit: 5}` - Search memory
- `{type: "get_stats"}` - Get system stats
- `{type: "execute_skill", name: "...", args: {...}}` - Run skill
- `{type: "ping"}` - Keepalive

**Server Events:**
- `welcome` - Connection established
- `status` - Status updates
- `thinking` - Processing state
- `assistant_response` - Athena's response
- `skills` - Skills list
- `skill_forged` - Forge result
- `memory` - Search results
- `stats` - System stats
- `skill_result` - Skill execution result
- `interaction_complete` - Turn complete
- `error` - Errors

## Running the Web App

```bash
# Quick start
./start_web.sh

# Or manually
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 8080
```

Then open: **http://localhost:8080**

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `ATHENA_HOST` | `0.0.0.0` | Server bind address |
| `ATHENA_PORT` | `8080` | Server port |
| `ATHENA_WORKERS` | `1` | Uvicorn workers |
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `ATHENA_HEADPHONES` | `0` | Headphones mode (1=on) |
| `ATHENA_STT_ENGINE` | `whisper` | STT engine |
| `ATHENA_TTS_ENGINE` | `piper` | TTS engine |

## WebSocket Integration with Athena Core

The web server wires Athena's event system to WebSocket broadcasting:

```python
# In server.py lifespan:
def setup_athena_events(athena_instance):
    def broadcast(event_type, data):
        for ws in manager.active_connections.values():
            ws.send_json({'type': event_type, **data})

    athena_instance.events.on('thinking_start', lambda d: broadcast('thinking', {'status': 'started', **d}))
    athena_instance.events.on('assistant_response', lambda d: broadcast('assistant_response', d))
    athena_instance.events.on('interaction_complete', lambda d: broadcast('interaction_complete', d))
    athena_instance.events.on('thinking_start', lambda d: broadcast('status', {'message': 'Thinking... 🤔'}))
    # ...
```

## Testing

```bash
# Run tests
python3 -m pytest test/test_lean_architecture.py -v

# Test WebSocket manually
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8080/ws/test') as ws:
        print(await ws.recv())
        await ws.send(json.dumps({'type': 'chat', 'text': 'hello'}))
        for _ in range(3): print(json.loads(await ws.recv()))
asyncio.run(test())
"
```

## Dependencies Added
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `websockets` - WebSocket client (for testing)
- `pydantic` - Request validation

All core Athena dependencies remain the same (faster-whisper, piper-tts, litellm, etc.)