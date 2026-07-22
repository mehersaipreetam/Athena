"""
Athena Core - Main orchestrator integrating all subsystems.
Single entry point: AthenaAssistant.run()
"""
import re
import json
import time
import threading
import logging
import sys
from typing import Callable, Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path

from athena.config import config
from athena.memory import MemoryEngine
from athena.persona import PersonaEngine
from athena.skills import SkillEngine, SkillSandbox
from athena.llm import LLMRouter, ToolDefinition, LLMResponse, ToolCall
from athena.voice import ShutdownRequested
from tools.mcp_client import get_mcp_tools, call_mcp_tool

logger = logging.getLogger(__name__)


# ANSI colors
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'


# Spinner frames
SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class Spinner:
    """Animated spinner for CLI."""
    def __init__(self, message: str = ""):
        self.message = message
        self.running = False
        self.thread = None
        self.idx = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self, message: str = ""):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        if message:
            print(f"\r{Colors.GREEN}✓{Colors.RESET} {message}")
        else:
            print(f"\r{' ' * 40}\r", end='')

    def _spin(self):
        while self.running:
            frame = SPINNER[self.idx % len(SPINNER)]
            print(f"\r{Colors.CYAN}{frame}{Colors.RESET} {self.message}", end='', flush=True)
            self.idx += 1
            time.sleep(0.1)


@dataclass
class AssistantState:
    """Runtime state for the assistant."""
    listening: bool = True
    speaking: bool = False
    interrupted: bool = False
    thinking: bool = False
    shutdown_requested: bool = False
    current_session_id: str = field(default_factory=lambda: time.strftime("%Y%m%d_%H%M%S"))
    last_spoken: str = ""
    last_skills_used: List[str] = field(default_factory=list)


class EventEmitter:
    """Simple event emitter for callbacks."""
    def __init__(self):
        self._handlers = {}

    def on(self, event: str, handler: Callable):
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Callable):
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    def emit(self, event: str, *args, **kwargs):
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[EVENT] Handler error for {event}: {e}")


class AthenaAssistant:
    """
    Main Athena assistant orchestrator.
    Integrates: STT → LLM(+Tools) → TTS with Memory, Persona, Skills, Proactive engine.
    """

    def __init__(
        self,
        stt_fn: Optional[Callable[[], str]] = None,
        tts_fn: Optional[Callable[[str], None]] = None,
        llm_generate_fn: Optional[Callable[[str], str]] = None,
        tui: Optional[Any] = None,
        headphones_mode: bool = False,
    ):
        """
        Initialize Athena with pluggable components.

        Args:
            stt_fn: Callable that returns recognized text (blocking). None = use default.
            tts_fn: Callable(text) that speaks text. None = use default.
            llm_generate_fn: Callable(prompt) -> response. None = use LLMRouter.
            tui: Optional TUI manager for visual interface.
            headphones_mode: If True, mic stays active during TTS for interruption.
        """
        self.stt = stt_fn or self._default_stt
        self.tts = tts_fn or self._default_tts
        self.llm_generate = llm_generate_fn
        self.tui = tui
        self.headphones_mode = headphones_mode

        # Core subsystems
        self.memory = MemoryEngine()
        self.persona = PersonaEngine(self.memory)
        self.skills = SkillEngine(
            llm_generate_fn=self._llm_generate_wrapper,
            memory=self.memory,
        )
        # Use custom LLM if provided, otherwise use LLMRouter
        self.llm = LLMRouter() if llm_generate_fn is None else None

        # State
        self.state = AssistantState()
        self._speak_lock = threading.Lock()
        self._hotkey_listener = None

        # Event emitter for callbacks
        self.events = EventEmitter()

        # MCP tool integration
        self._mcp_tools_cache = None

        logger.info("[ATHENA] Core systems initialized")

    def _default_stt(self) -> str:
        """Placeholder STT - override with real implementation."""
        return input("You: ").strip()

    def _default_tts(self, text: str):
        """Placeholder TTS - override with real implementation."""
        print(f"Athena: {text}")

    def _llm_generate_wrapper(self, prompt: str) -> str:
        """Wrapper for skill forge to use LLM."""
        if self.llm_generate:
            return self.llm_generate(prompt)
        return self.llm.generate_sync(prompt)

    def run(self):
        """Main event loop: listen → think → speak."""
        # Startup greeting
        greeting = self.persona.get_greeting()
        self._speak(greeting)

        if self.tui:
            self.tui.set_status("Listening... 🎙️")

        logger.info("[ATHENA] Main loop started")

        while not self.state.shutdown_requested:
            try:
                # Listen for user input
                self.state.listening = True

                # Handle both generator-based and direct STT functions
                user_input = None
                if hasattr(self.stt, '__call__'):
                    result = self.stt()
                    # If it's a generator, get the first result
                    if hasattr(result, '__iter__') and not isinstance(result, str):
                        for text, is_final in result:
                            if is_final:
                                user_input = text
                                break
                    else:
                        user_input = result
                else:
                    user_input = self.stt()

                self.state.listening = False

                if not user_input:
                    continue

                # Process input
                self._process_user_input(user_input)

            except ShutdownRequested:
                logger.info("[ATHENA] Shutdown requested by user")
                self._shutdown_gracefully()
                break
            except KeyboardInterrupt:
                logger.info("[ATHENA] Keyboard interrupt")
                self._shutdown_gracefully()
                break
            except Exception as e:
                logger.error(f"[ATHENA] Loop error: {e}")
                self._speak("I encountered an issue, Sir. Let me recover.")

        self._cleanup()

    def _process_user_input(self, user_input: str):
        """Process a single user input through the full pipeline."""
        # Check for shutdown
        if self._is_shutdown_command(user_input):
            self._shutdown_gracefully()
            return

        # Emit user input event
        self.events.emit('user_input', {'text': user_input, 'timestamp': time.time()})

        # Display user input
        if self.tui:
            self.tui.add_message("You", user_input)
            self.tui.set_status("Thinking... 🤔")
            self.tui.live.update(self.tui.render())

        # Build prompt with persona + memory context
        persona_prompt = self.persona.get_personality_prompt(user_input)
        memory_context = self.memory.get_context(user_input)

        # Get available tools - use smart tool selection
        available_tools = self._get_relevant_tools(user_input)

        # Combine prompt
        full_prompt = f"{persona_prompt}\n\n{memory_context}\n\nUser: {user_input}"

        # Generate response (with tool calling)
        self.state.thinking = True
        self.events.emit('thinking_start', {'prompt': full_prompt})
        response = self._generate_with_tools(full_prompt, available_tools)
        self.state.thinking = False
        self.events.emit('thinking_end', {'response': response})

        # Extract skills used
        skills_used = self._extract_skills_used(response)

        # Speak response
        if self.tui:
            self.tui.set_status("Speaking... 🗣️")
            self.tui.live.update(self.tui.render())

        self.events.emit('assistant_response', {'text': response, 'skills_used': skills_used})
        self._speak_streaming(response)

        # Record interaction
        self.memory.record_interaction(
            user_input=user_input,
            assistant_response=response,
            sentiment=self._analyze_sentiment(user_input),
            skills_used=skills_used
        )

        # Check if auto-forge is needed
        self._maybe_auto_forge(user_input, available_tools)

        # Periodic maintenance
        self._maybe_maintain()

        # Reset status
        if self.tui:
            self.tui.set_status("Listening... 🎙️")
            self.tui.live.update(self.tui.render())

        self.events.emit('interaction_complete', {
            'user_input': user_input,
            'response': response,
            'skills_used': skills_used
        })

    def _generate_with_tools(self, prompt: str, tools: List[Dict]) -> str:
        """Generate LLM response with tool calling loop."""
        max_iterations = 3
        current_prompt = prompt
        pseudo_keywords = {"greet", "greeting", "say_hello", "respond", "respond_to_greeting", "reply", "speak", "answer", "say", "message", "chat", "talk", "ask"}

        for iteration in range(max_iterations):
            # Use custom LLM if provided, otherwise use LLMRouter
            if self.llm_generate:
                response_text = self.llm_generate(current_prompt)
                response = LLMResponse(content=response_text)
            else:
                # Convert tool dicts to ToolDefinition objects
                tool_defs = [ToolDefinition(**t) for t in tools] if tools else None
                response = self.llm.generate_sync(current_prompt, tools=tool_defs)

            # Check for tool calls
            tool_calls = self._parse_tool_calls(response)
            if not tool_calls:
                return response.content

            # Execute tool calls
            for tool_name, tool_args in tool_calls:
                if self._is_builtin_tool(tool_name):
                    result = self._execute_builtin_tool(tool_name, tool_args)
                elif self._is_skill_tool(tool_name):
                    result = self.skills.execute(tool_name, **tool_args)
                elif any(kw in tool_name.lower() for kw in ["greet", "welcome", "respond", "reply", "speak", "answer", "say", "message", "chat", "talk", "ask"]):
                    if isinstance(tool_args, dict):
                        for k in ["greeting", "response", "message", "text", "content", "answer", "user_greeting"]:
                            if k in tool_args and isinstance(tool_args[k], str) and tool_args[k].strip():
                                return tool_args[k].strip()
                        if "arguments" in tool_args and isinstance(tool_args["arguments"], dict):
                            for k in ["greeting", "response", "message", "text", "content", "answer", "user_greeting"]:
                                if k in tool_args["arguments"] and isinstance(tool_args["arguments"][k], str) and tool_args["arguments"][k].strip():
                                    return tool_args["arguments"][k].strip()
                    content = response.content if isinstance(response, LLMResponse) else str(response)
                    return content
                else:
                    mcp_tools = [t['name'] for t in self._get_mcp_tools()]
                    if tool_name in mcp_tools:
                        result = call_mcp_tool(tool_name, tool_args)
                    else:
                        logger.warning(f"[ATHENA] Unknown tool call '{tool_name}' ignored")
                        return response.content if isinstance(response, LLMResponse) else str(response)

                # Add result to prompt for next iteration
                current_prompt += f"\n\nTool Result ({tool_name}): {result}"

        # After tool results, try once WITHOUT tools to get final natural response
        try:
            if self.llm_generate:
                final_response = self.llm_generate(
                    current_prompt + "\n\nNow provide a final natural language response to the user."
                )
            else:
                final_response = self.llm.generate_sync(
                    current_prompt + "\n\nNow provide a final natural language response to the user.",
                    tools=None
                )
            if not self._parse_tool_calls(final_response):
                return final_response.content if isinstance(final_response, LLMResponse) else final_response
        except Exception as e:
            logger.warning(f"[ATHENA] Final response generation failed: {e}")

        return "I've completed the task, Sir."

    def _parse_tool_calls(self, response: Any) -> List[Tuple[str, Dict]]:
        """Parse tool calls from LLM response or mock objects."""
        calls = []
        if response is None:
            return calls

        # 1. Structured tool_calls (LLMResponse or OpenAI/Mock object)
        tool_calls = None
        if hasattr(response, 'tool_calls') and isinstance(getattr(response, 'tool_calls'), (list, tuple)):
            tool_calls = response.tool_calls
        elif hasattr(response, 'choices') and response.choices:
            msg = getattr(response.choices[0], 'message', None)
            if msg and hasattr(msg, 'tool_calls') and isinstance(getattr(msg, 'tool_calls'), (list, tuple)):
                tool_calls = msg.tool_calls

        if tool_calls and isinstance(tool_calls, (list, tuple)):
            for tc in tool_calls:
                fn = getattr(tc, 'function', None)
                name = getattr(fn, 'name', None) if fn else getattr(tc, 'name', None)
                args = getattr(fn, 'arguments', None) if fn else getattr(tc, 'arguments', {})
                if isinstance(name, str) and name:
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    calls.append((name, args if isinstance(args, dict) else {}))
            if calls:
                return calls

        # 2. String content (JSON / Regex pattern fallback)
        content = response if isinstance(response, str) else getattr(response, 'content', None)
        if not isinstance(content, str) and hasattr(response, 'choices') and response.choices:
            msg = getattr(response.choices[0], 'message', None)
            if msg:
                content = getattr(msg, 'content', None)

        if isinstance(content, str) and content.strip():
            calls.extend(self._extract_json_tool_calls(content))

        return calls

    def _extract_json_tool_calls(self, text: str) -> List[Tuple[str, Dict]]:
        """Extract tool calls from JSON in text (for models without native function calling)."""
        calls = []

        # Try multiple patterns for JSON function calls
        patterns = [
            # Pattern 1: {"name": "func", "arguments": {...}} or {"function": "func", "parameters": {...}}
            r'\{[^{}]*"(?:name|function)"\s*:\s*"(\w+)"[^{}]*"(?:arguments|parameters)"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})[^{}]*\}',
            # Pattern 2: {"name": "func", "arguments": {...}} - simpler
            r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]+\})\s*\}',
            # Pattern 3: Raw JSON objects that look like function calls (the issue we're seeing)
            r'\{\s*"__metadata"\s*:\s*\{[^}]*"type"\s*:\s*"Function"[^}]*\}\s*,\s*"name"\s*:\s*"(\w+)"\s*,\s*"parameters"\s*:\s*(\{[^}]+\})\s*\}',
            # Pattern 4: Generic function call format with "params" or "params"
            r'\{\s*"(?:name|function)"\s*:\s*"(\w+)"\s*,\s*"(?:parameters|params|arguments)"\s*:\s*(\{.*?\})\s*\}',
            # Pattern 5: Any JSON with "name" and "parameters" fields
            r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"parameters"\s*:\s*(\{.*?\})\s*\}',
        ]

        seen_spans = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                span = match.span()
                if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                    continue
                func_name = match.group(1)
                try:
                    args = json.loads(match.group(2))
                    calls.append((func_name, args))
                    seen_spans.add(span)
                except json.JSONDecodeError:
                    pass

        return calls

    def _is_builtin_tool(self, name: str) -> bool:
        return name in ("save_memory", "recall_memory", "get_memory_stats", "list_skills", "forge_skill")

    def _is_skill_tool(self, name: str) -> bool:
        return self.skills.get(name) is not None

    def _execute_builtin_tool(self, name: str, args: Dict) -> str:
        if name == "recall_memory":
            memories = self.memory.recall(args["query"], limit=args.get("limit", 5))
            if not memories:
                return "No relevant memories found."
            return "\n".join(f"- [{m.type}] {m.content}" for m in memories)
        elif name == "save_memory":
            mid = self.memory.remember(
                args["content"],
                type=args.get("type", "fact"),
                tags=args.get("tags", [])
            )
            return f"Memory saved (ID: {mid})."
        return f"Unknown built-in tool: {name}"

    def _get_builtin_tools(self) -> List[Dict]:
        return [
            {
                "name": "recall_memory",
                "description": "Search long-term memory for relevant information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "save_memory",
                "description": "Store a fact, preference, or note in long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "What to remember"},
                        "type": {"type": "string", "default": "fact"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["content"]
                }
            },
        ]

    def _get_mcp_tools(self) -> List[Dict]:
        """Get MCP tool definitions (cached and deduplicated)."""
        if self._mcp_tools_cache is None:
            try:
                raw_tools = get_mcp_tools()
                # Deduplicate by name - prefer skill tools over MCP duplicates
                seen = set()
                deduped = []
                for tool in raw_tools:
                    if tool['name'] not in seen:
                        seen.add(tool['name'])
                        deduped.append(tool)
                self._mcp_tools_cache = deduped
            except Exception as e:
                logger.warning(f"[MCP] Failed to get tools: {e}")
                self._mcp_tools_cache = []
        return self._mcp_tools_cache

    def _get_relevant_tools(self, user_input: str) -> List[Dict]:
        """Get available tool definitions (builtin + dynamic skills + active MCP tools)."""
        all_tools = self._get_builtin_tools() + self.skills.get_tool_definitions() + self._get_mcp_tools()
        return all_tools[:15]  # Limit to 15 tools max

    def _extract_skills_used(self, response: Union[LLMResponse, str]) -> List[str]:
        """Extract skill names from tool calls in response."""
        skills = []
        if isinstance(response, LLMResponse):
            for tc in response.tool_calls:
                skills.append(tc.name)
        else:
            text = response if isinstance(response, str) else response.content
            for match in re.finditer(r'TOOL_CALL:\s*(\w+)', text):
                skills.append(match.group(1))
        return skills

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis."""
        text = text.lower()
        positive = ["good", "great", "thanks", "thank you", "awesome", "love", "happy", "please"]
        negative = ["bad", "terrible", "hate", "angry", "frustrated", "wrong", "error", "problem"]
        pos_score = sum(1 for w in positive if w in text)
        neg_score = sum(1 for w in negative if w in text)
        if pos_score > neg_score:
            return "positive"
        elif neg_score > pos_score:
            return "negative"
        return "neutral"

    def _maybe_auto_forge(self, user_input: str, existing_tools: List[Dict]):
        """Check if user request needs a new skill and forge it."""
        tool_names = [t["name"] for t in existing_tools]
        if self.skills.can_forge(user_input, tool_names):
            self._speak("I'll create a new tool for that, Sir. One moment.")
            success, msg = self.skills.forge(user_input)
            self._speak(msg)

    def _is_shutdown_command(self, text: str) -> bool:
        shutdown_patterns = [
            r"\b(bye|goodbye|shutdown|stop listening|good night|see you|quit|exit)\b"
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in shutdown_patterns)

    def _shutdown_gracefully(self):
        self.state.shutdown_requested = True
        farewell = self.persona.get_farewell()
        self._speak(farewell)
        self.memory.record_interaction(
            user_input="",
            assistant_response=farewell,
            sentiment="neutral",
            skills_used=[]
        )
        logger.info("[ATHENA] Shutdown complete")



    def _maybe_maintain(self):
        """Periodic maintenance: consolidate, prune, optimize."""
        stats = self.memory.get_stats()
        if stats["total_conversations"] % 20 == 0:
            threading.Thread(target=self._maintenance_task, daemon=True).start()

    def _maintenance_task(self):
        """Background maintenance."""
        try:
            self.memory.consolidate()
            self.memory.prune_old_memories()
            self.skills.prune_unused()
            self.skills.optimize_hot_skills()
        except Exception as e:
            logger.warning(f"[MAINTENANCE] Error: {e}")

    def _cleanup(self):
        """Cleanup on exit."""
        self.memory.vacuum()

    # ==================== TTS ====================

    def _speak(self, text: str):
        """Blocking TTS with interruption support."""
        with self._speak_lock:
            self.state.speaking = True
            self.state.interrupted = False
            self.state.last_spoken = text

            if self.tui:
                self.tui.add_message("Athena", text)
                self.tui.set_status("Speaking... 🗣️")
                self.tui.live.update(self.tui.render())

            try:
                self.tts(text)
            except Exception as e:
                logger.error(f"[TTS] Error: {e}")
            finally:
                self.state.speaking = False
                if self.tui:
                    self.tui.set_status("Listening... 🎙️")
                    self.tui.live.update(self.tui.render())

    def _speak_streaming(self, text: str):
        """Stream TTS sentence by sentence for responsiveness."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sentence in sentences:
            if self.state.interrupted:
                break
            if sentence.strip():
                self._speak(sentence.strip())

    def _interrupt(self):
        """Interrupt current speech."""
        self.state.interrupted = True
        if hasattr(self.tts, 'interrupt'):
            self.tts.interrupt()

    # ==================== Manual Controls ====================

    def inject_text(self, text: str):
        """Programmatically inject text as if spoken."""
        self._process_user_input(text)

    def speak_text(self, text: str):
        """Programmatically speak text."""
        self._speak(text)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive system stats."""
        return {
            "memory": self.memory.get_stats(),
            "skills": self.skills.get_stats(),
            "persona": {
                "mood": self.persona.current_mood.value,
                "interactions": self.persona.interaction_count,
            },
            "session": self.state.current_session_id,
        }

    # ==================== WebSocket Callbacks ====================

    async def handle_websocket_message(self, msg: dict) -> dict:
        """Handle incoming WebSocket messages and return response."""
        msg_type = msg.get('type')

        if msg_type == 'chat':
            text = msg.get('text', '').strip()
            if text:
                self._process_user_input(text)
                return {'type': 'status', 'message': 'Processing...'}
            return {'type': 'error', 'message': 'Empty message'}

        elif msg_type == 'get_skills':
            skills = self.skills.list_all()
            return {
                'type': 'skills',
                'skills': [
                    {
                        'name': s.name,
                        'description': s.description,
                        'version': s.version,
                        'use_count': s.use_count,
                        'success_rate': s.success_count / s.use_count if s.use_count > 0 else 0
                    }
                    for s in skills
                ]
            }

        elif msg_type == 'forge_skill':
            description = msg.get('description', '').strip()
            if description:
                success, msg_text = self.skills.forge(description)
                return {'type': 'skill_forged', 'success': success, 'message': msg_text}
            return {'type': 'error', 'message': 'Empty description'}

        elif msg_type == 'query_memory':
            query = msg.get('query', '').strip()
            limit = msg.get('limit', 5)
            if query:
                memories = self.memory.recall(query, limit=limit)
                return {
                    'type': 'memory',
                    'results': [
                        {'id': m.id, 'type': m.type, 'content': m.content, 'tags': m.tags, 'created_at': m.created_at}
                        for m in memories
                    ]
                }
            return {'type': 'memory', 'results': []}

        elif msg_type == 'get_stats':
            return {'type': 'stats', 'stats': self.get_stats()}

        elif msg_type == 'execute_skill':
            name = msg.get('name')
            args = msg.get('args', {})
            if name:
                try:
                    result = self.skills.execute(name, **args)
                    return {'type': 'skill_result', 'name': name, 'result': result}
                except Exception as e:
                    return {'type': 'error', 'message': str(e)}
            return {'type': 'error', 'message': 'Skill name required'}

        elif msg_type == 'ping':
            return {'type': 'pong'}

        return {'type': 'error', 'message': f'Unknown message type: {msg_type}'}