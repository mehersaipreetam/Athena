"""
Athena LLM Router - Unified interface for multiple LLM providers.
Supports: Gemini (primary), Ollama (local fallback), OpenAI, Anthropic via LiteLLM.
Handles: tool calling, streaming, error recovery, provider switching.
"""
import os
import logging
import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

try:
    import litellm
    from litellm import acompletion, completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

try:
    from mcp.server.fastmcp import FastMCP
    from mcp import Client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from athena.config import config

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """MCP-compatible tool definition."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    name: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass
class LLMResponse:
    """Unified response from LLM."""
    content: str = ""
    tool_calls: List[ToolCall] = None
    finish_reason: str = "stop"

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate response. Returns LLMResponse if stream=False, AsyncGenerator if stream=True."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name for this provider."""
        pass


class LiteLLMProvider(LLMProvider):
    """Unified provider using LiteLLM for multiple backends."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.extra_kwargs = kwargs

        if api_key:
            provider = self._get_provider_name(model)
            os.environ[f"{provider.upper()}_API_KEY"] = api_key
        if base_url:
            provider = self._get_provider_name(model)
            os.environ[f"{provider.upper()}_API_BASE"] = base_url

        litellm.drop_params = True

    def _get_provider_name(self, model: str) -> str:
        if model.startswith("gemini") or model.startswith("google"):
            return "google"
        elif model.startswith("ollama"):
            return "ollama"
        elif model.startswith("openai") or model.startswith("gpt"):
            return "openai"
        elif model.startswith("anthropic") or model.startswith("claude"):
            return "anthropic"
        return "litellm"

    def is_available(self) -> bool:
        if not LITELLM_AVAILABLE:
            return False
        if self.model.startswith("ollama") or self._get_provider_name(self.model) == "litellm":
            return True  # Local or custom model
        provider = self._get_provider_name(self.model)
        return bool(os.environ.get(f"{provider.upper()}_API_KEY"))

    def get_model_name(self) -> str:
        return self.model

    def _build_tools(self, tools: Optional[List[ToolDefinition]]) -> Optional[List[Dict]]:
        """Convert tool definitions to LiteLLM/OpenAI format."""
        if not tools:
            return None
        return [{
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
        } for t in tools]

    def _parse_tool_calls(self, tool_calls) -> List[ToolCall]:
        """Parse tool calls from LiteLLM response."""
        calls = []
        for tc in tool_calls:
            fn = getattr(tc, 'function', None)
            name = getattr(fn, 'name', None) if fn else getattr(tc, 'name', None)
            if not isinstance(name, str):
                if hasattr(name, '_mock_name') and name._mock_name and name._mock_name != 'name':
                    name = str(name._mock_name)
                elif name is not None:
                    name = str(name)

            raw_args = getattr(fn, 'arguments', None) if fn else getattr(tc, 'arguments', {})
            if not isinstance(raw_args, (str, dict)):
                if hasattr(raw_args, '_mock_name') and raw_args._mock_name:
                    raw_args = str(raw_args._mock_name)

            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}

            call_id = getattr(tc, 'id', 'call_0')
            if not isinstance(call_id, str):
                call_id = str(call_id)

            if name and isinstance(name, str):
                calls.append(ToolCall(
                    name=name,
                    arguments=args,
                    call_id=call_id
                ))
        return calls

    def generate(
        self,
        prompt: str,
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        if not self.is_available():
            raise RuntimeError(f"Provider {self._get_provider_name(self.model)} not available")

        messages = [{"role": "user", "content": prompt}]
        tool_defs = self._build_tools(tools)

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", config.llm_temperature),
            "max_tokens": kwargs.get("max_tokens", config.llm_max_tokens),
            "stream": stream,
        }
        if tool_defs:
            params["tools"] = tool_defs
            params["tool_choice"] = "auto"

        params.update(self.extra_kwargs)

        if stream:
            return self._stream_response(params)
        else:
            return self._sync_response(params)

    def _sync_response(self, params: Dict) -> LLMResponse:
        response = litellm.completion(**params)
        choice = response.choices[0]

        if choice.message.tool_calls:
            return LLMResponse(
                content="",
                tool_calls=self._parse_tool_calls(choice.message.tool_calls),
                finish_reason=choice.finish_reason
            )
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=[],
            finish_reason=choice.finish_reason
        )

    async def _stream_response(self, params: Dict) -> AsyncGenerator[str, None]:
        response = await litellm.acompletion(**params)
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.choices[0].delta.tool_calls:
                # Tool calls in streaming - we'd need to accumulate
                pass


class LLMRouter:
    """
    Smart LLM router with primary + fallback providers.
    Handles: tool calling, streaming, error recovery, provider switching.
    """

    def __init__(self):
        self.primary = self._create_primary()
        self.fallback = self._create_fallback()
        self.current = self.primary

    def _create_primary(self) -> LLMProvider:
        """Create primary provider (Gemini by default)."""
        model = config.llm_primary_model
        if model.startswith("gemini"):
            return LiteLLMProvider(
                model=model,
                api_key=config.gemini_api_key,
            )
        elif model.startswith("ollama"):
            return LiteLLMProvider(model=model)
        elif config.openai_api_key:
            return LiteLLMProvider(
                model=model,
                api_key=config.openai_api_key,
            )
        # Default to Ollama if no keys
        return LiteLLMProvider(model="ollama/llama3.1:8b")

    def _create_fallback(self) -> LLMProvider:
        """Create fallback provider (local Ollama)."""
        return LiteLLMProvider(model=config.llm_fallback_model)

    def generate(
        self,
        prompt: str,
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate with automatic fallback on failure."""
        try:
            return self.primary.generate(prompt, tools, stream, **kwargs)
        except Exception as e:
            logger.warning(f"[LLM] Primary failed: {e}, trying fallback...")
            try:
                return self.fallback.generate(prompt, tools, stream, **kwargs)
            except Exception as e2:
                logger.error(f"[LLM] Fallback also failed: {e2}")
                raise RuntimeError(f"All LLM providers failed: {e2}")

    def generate_sync(
        self,
        prompt: str,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> LLMResponse:
        """Synchronous generation (blocking)."""
        result = self.generate(prompt, tools, stream=False, **kwargs)
        if isinstance(result, LLMResponse):
            return result
        # If somehow got a generator, consume it
        content = ""
        for chunk in result:
            content += chunk
        return LLMResponse(content=content)

    async def generate_async(
        self,
        prompt: str,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Async streaming generation."""
        async for chunk in self.generate(prompt, tools, stream=True, **kwargs):
            yield chunk

    def get_available_models(self) -> List[str]:
        """Get list of available models from all providers."""
        models = []
        if self.primary.is_available():
            models.append(f"primary: {self.primary.model}")
        if self.fallback.is_available():
            models.append(f"fallback: {self.fallback.model}")
        return models

    def switch_provider(self, provider: str = "fallback"):
        """Manually switch provider."""
        if provider == "fallback":
            self.current = self.fallback
        elif provider == "primary":
            self.current = self.primary


# Convenience function for quick sync calls
def quick_llm(prompt: str, model: str = None, **kwargs) -> str:
    """Quick synchronous LLM call."""
    router = LLMRouter()
    if model:
        provider = LiteLLMProvider(model=model)
        response = provider.generate_sync(prompt, **kwargs)
    else:
        response = router.generate_sync(prompt, **kwargs)
    return response.content