"""
Athena Web Server - FastAPI backend for the web interface.
Serves the web UI and provides WebSocket/REST API for voice/text interaction.
"""
import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from athena.config import config
from athena.core import AthenaAssistant
from athena.voice import ShutdownRequested

logger = logging.getLogger(__name__)

# Global Athena instance
athena: Optional[AthenaAssistant] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global athena

    # Initialize Athena
    logger.info("[WEB] Initializing Athena...")

    # Use text I/O for web mode
    athena = AthenaAssistant(
        stt_fn=lambda: (_ for _ in ()).throw(ShutdownRequested()),
        tts_fn=lambda text: None,
        headphones_mode=config.headphones_mode,
    )

    # Set up event handlers for WebSocket broadcasting
    setup_athena_events(athena)

    # Start Athena in background
    asyncio.create_task(run_athena_loop())

    yield

    # Shutdown
    logger.info("[WEB] Shutting down Athena...")
    if athena:
        athena.state.shutdown_requested = True


app = FastAPI(
    title="Athena Voice Assistant",
    description="Lean Jarvis-like AI Assistant with Web Interface",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==================== Request/Response Models ====================

class TextInput(BaseModel):
    text: str
    session_id: Optional[str] = None


class SkillForgeRequest(BaseModel):
    description: str


class MemoryQuery(BaseModel):
    query: str
    limit: int = 5


class SkillExecute(BaseModel):
    name: str
    args: Dict[str, Any] = {}


# ==================== WebSocket Manager ====================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"[WS] Client {client_id} connected. Total: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"[WS] Client {client_id} disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


# ==================== Athena Event Integration ====================

def setup_athena_events(athena_instance):
    """Set up event handlers to broadcast via WebSocket."""

    # Store the main event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    def broadcast(event_type: str, data: dict):
        """Broadcast to all connected WebSocket clients."""
        message = {'type': event_type, **data}
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

    # Wire up events
    if hasattr(athena_instance, 'events'):
        athena_instance.events.on('thinking_start', lambda d: broadcast('thinking', {'status': 'started', **d}))
        athena_instance.events.on('thinking_end', lambda d: broadcast('thinking', {'status': 'completed', **d}))
        athena_instance.events.on('assistant_response', lambda d: broadcast('assistant_response', d))
        athena_instance.events.on('interaction_complete', lambda d: broadcast('interaction_complete', d))
        athena_instance.events.on('thinking_start', lambda d: broadcast('status', {'message': 'Thinking... 🤔'}))
        athena_instance.events.on('thinking_end', lambda d: broadcast('status', {'message': 'Speaking... 🗣️'}))
        athena_instance.events.on('interaction_complete', lambda d: broadcast('status', {'message': 'Listening... 🎙️'}))


async def run_athena_loop():
    """Run Athena's main loop in background."""
    global athena
    if athena:
        try:
            await asyncio.get_event_loop().run_in_executor(None, athena.run)
        except Exception as e:
            logger.error(f"[ATHENA] Loop error: {e}")


# ==================== REST API Endpoints ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main web UI."""
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("""
    <html><body style="font-family: monospace; background: #0a0a0a; color: #00ff88; padding: 2rem;">
        <h1>🟣 ATHENA WEB INTERFACE</h1>
        <p>Web UI template not found. Create <code>web/templates/index.html</code></p>
        <p>API available at <a href="/docs">/docs</a></p>
    </body></html>
    """)


@app.post("/api/chat")
async def chat(input: TextInput):
    """Send text to Athena and get response."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")

    try:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        def on_interaction(data):
            if not future.done():
                response = data.get('response', '')
                loop.call_soon_threadsafe(future.set_result, response)
                
        athena.events.on('interaction_complete', on_interaction)
        
        try:
            # Process input without blocking the main event loop
            await loop.run_in_executor(None, athena.inject_text, input.text)
            
            # Wait for response (timeout after 30s just in case)
            response_text = await asyncio.wait_for(future, timeout=30.0)
            return {"status": "ok", "message": str(response_text)}
        finally:
            athena.events.off('interaction_complete', on_interaction)
            
    except asyncio.TimeoutError:
        raise HTTPException(504, "Athena took too long to respond")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/skills/forge")
async def forge_skill(request: SkillForgeRequest):
    """Create a new skill via SkillForge."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")

    try:
        success, msg = athena.skills.forge(request.description)
        return {"success": success, "message": msg}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/skills")
async def list_skills():
    """List all available skills."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")

    skills = athena.skills.list_all()
    return [
        {
            "name": s.name,
            "description": s.description,
            "version": s.version,
            "use_count": s.use_count,
            "success_rate": s.success_count / s.use_count if s.use_count > 0 else 0
        }
        for s in skills
    ]


@app.post("/api/skills/execute")
async def execute_skill(request: SkillExecute):
    """Execute a skill directly."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")

    try:
        result = athena.skills.execute(request.name, **request.args)
        return {"result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/memory/query")
async def query_memory(request: MemoryQuery):
    """Search memory."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")

    memories = athena.memory.recall(request.query, limit=request.limit)
    return [
        {
            "id": m.id,
            "type": m.type,
            "content": m.content,
            "tags": m.tags,
            "created_at": m.created_at
        }
        for m in memories
    ]


@app.get("/api/memory/stats")
async def memory_stats():
    """Get memory statistics."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")
    return athena.memory.get_stats()


@app.get("/api/stats")
async def get_stats():
    """Get comprehensive system stats."""
    global athena
    if not athena:
        raise HTTPException(503, "Athena not initialized")
    return athena.get_stats()


@app.get("/api/health")
async def health():
    """Health check."""
    global athena
    return {"status": "ok", "athena": athena is not None}


# ==================== WebSocket Endpoint ====================

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket for real-time chat."""
    await manager.connect(websocket, client_id)

    try:
        # Send welcome
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to Athena",
            "client_id": client_id
        })

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                text = data.get("text", "")
                if text and athena:
                    await websocket.send_json({
                        "type": "status",
                        "message": "Processing..."
                    })
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, athena.inject_text, text)

            elif data.get("type") == "get_skills":
                if athena:
                    skills = athena.skills.list_all()
                    await websocket.send_json({
                        "type": "skills",
                        "skills": [
                            {
                                "name": s.name,
                                "description": s.description,
                                "version": s.version,
                                "use_count": s.use_count,
                                "success_rate": s.success_count / s.use_count if s.use_count > 0 else 0
                            }
                            for s in athena.skills.list_all()
                        ]
                    })

            elif data.get("type") == "forge_skill":
                description = data.get("description", "").strip()
                if description and athena:
                    success, msg = athena.skills.forge(description)
                    await websocket.send_json({
                        "type": "skill_forged",
                        "success": success,
                        "message": msg
                    })
                    if success:
                        # Refresh skills list
                        skills = athena.skills.list_all()
                        await websocket.send_json({
                            "type": "skills",
                            "skills": [
                                {
                                    "name": s.name,
                                    "description": s.description,
                                    "version": s.version,
                                    "use_count": s.use_count,
                                    "success_rate": s.success_count / s.use_count if s.use_count > 0 else 0
                                }
                                for s in skills
                            ]
                        })

            elif data.get("type") == "query_memory":
                query = data.get("query", "").strip()
                limit = data.get("limit", 5)
                if query and athena:
                    memories = athena.memory.recall(query, limit=limit)
                    await websocket.send_json({
                        "type": "memory",
                        "results": [
                            {"id": m.id, "type": m.type, "content": m.content, "tags": m.tags, "created_at": m.created_at}
                            for m in memories
                        ]
                    })

            elif data.get("type") == "get_stats":
                if athena:
                    await websocket.send_json({
                        "type": "stats",
                        "stats": athena.get_stats()
                    })

            elif data.get("type") == "execute_skill":
                name = data.get("name")
                args = data.get("args", {})
                if name and athena:
                    try:
                        result = athena.skills.execute(name, **args)
                        await websocket.send_json({
                            "type": "skill_result",
                            "name": name,
                            "result": result
                        })
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": str(e)})

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"[WS] Error: {e}")
        manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)