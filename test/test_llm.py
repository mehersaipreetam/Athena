import pytest
from unittest.mock import patch, MagicMock
from athena.llm import LiteLLMProvider, LLMRouter, ToolDefinition, LLMResponse

def test_litellm_provider_sync(mock_litellm):
    mock_comp, _ = mock_litellm
    # Mocking completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"
    mock_comp.return_value = mock_response
    
    provider = LiteLLMProvider(model="ollama/test-model", api_key="fake-key")
    response = provider.generate("Hello", stream=False)
    
    assert isinstance(response, LLMResponse)
    assert response.content == "Test response"
    assert len(response.tool_calls) == 0

@pytest.mark.asyncio
async def test_litellm_provider_async(mock_litellm):
    _, mock_acomp = mock_litellm
    
    # Mocking async generator
    async def mock_generator():
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Async "
        mock_chunk.choices[0].delta.tool_calls = None
        yield mock_chunk
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = "response"
        mock_chunk2.choices[0].delta.tool_calls = None
        yield mock_chunk2
        
    mock_acomp.return_value = mock_generator()
    
    provider = LiteLLMProvider(model="ollama/test-model", api_key="fake-key")
    gen = provider.generate("Hello", stream=True)
    
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        
    assert "".join(chunks) == "Async response"

def test_llm_router_fallback(mock_litellm):
    mock_comp, _ = mock_litellm
    
    router = LLMRouter()
    primary_model = router.primary.model
    
    # Setup primary to fail
    def failing_comp(**kwargs):
        if kwargs.get("model") == primary_model:
            raise Exception("Primary API Error")
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Fallback response"
        mock_resp.choices[0].message.tool_calls = None
        mock_resp.choices[0].finish_reason = "stop"
        return mock_resp
        
    mock_comp.side_effect = failing_comp
    
    response = router.generate_sync("Hello")
    
    assert response.content == "Fallback response"
