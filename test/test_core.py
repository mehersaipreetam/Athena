import pytest
from unittest.mock import MagicMock, patch
from athena.core import AthenaAssistant, AssistantState

@pytest.fixture
def mock_mcp():
    with patch("athena.core.get_mcp_tools") as mock_get, \
         patch("athena.core.call_mcp_tool") as mock_call:
        mock_get.return_value = []
        yield mock_get, mock_call

def test_athena_assistant_init(mock_mcp):
    # Pass mock stt and tts
    assistant = AthenaAssistant(stt_fn=lambda: "hello", tts_fn=lambda x: None)
    assert assistant.state.listening == True
    assert assistant.memory is not None
    assert assistant.persona is not None
    assert assistant.skills is not None

def test_is_shutdown_command(mock_mcp):
    assistant = AthenaAssistant(stt_fn=lambda: "", tts_fn=lambda x: None)
    assert assistant._is_shutdown_command("goodbye athena")
    assert assistant._is_shutdown_command("shutdown now")
    assert assistant._is_shutdown_command("exit")
    assert not assistant._is_shutdown_command("hello there")
    assert not assistant._is_shutdown_command("what is the weather")

def test_process_user_input(mock_mcp, mock_litellm):
    mock_comp, _ = mock_litellm
    
    # Mock LLM generation to just return a simple message
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello, Sir."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"
    mock_comp.return_value = mock_response
    
    tts_mock = MagicMock()
    assistant = AthenaAssistant(stt_fn=lambda: "hi", tts_fn=tts_mock)
    
    assistant._process_user_input("hello")
    
    # Verify tts was called
    assert tts_mock.call_count > 0
    # Verify memory was recorded
    conversations = assistant.memory.get_recent_conversations(1)
    assert len(conversations) == 1
    assert conversations[0].user_input == "hello"

def test_generate_with_tools_builtin(mock_mcp, mock_litellm):
    mock_comp, _ = mock_litellm
    
    # First response asks for a tool call (save_memory)
    # Second response gives final answer
    
    def side_effect(*args, **kwargs):
        if "Tool Result" not in kwargs.get("messages", [{}])[-1].get("content", ""):
            resp = MagicMock()
            tc = MagicMock()
            tc.function = MagicMock()
            tc.function.name = "save_memory"
            tc.function.arguments = '{"content": "test memory"}'
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = ""
            resp.choices[0].message.tool_calls = [tc]
            return resp
        else:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "Memory saved."
            resp.choices[0].message.tool_calls = None
            return resp
            
    mock_comp.side_effect = side_effect
    
    assistant = AthenaAssistant(stt_fn=lambda: "", tts_fn=lambda x: None)
    
    # We pass the builtin tools
    tools = assistant._get_builtin_tools()
    
    response = assistant._generate_with_tools("Please remember this", tools)
    
    assert "Memory saved" in response
    # Verify memory was actually saved
    memories = assistant.memory.recall("test")
    assert len(memories) > 0
    assert "test memory" in memories[0].content

def test_extract_json_tool_calls(mock_mcp):
    assistant = AthenaAssistant(stt_fn=lambda: "", tts_fn=lambda x: None)
    text = 'Here is the tool call: {"name": "test_tool", "arguments": {"arg1": "val1"}}'
    
    calls = assistant._extract_json_tool_calls(text)
    assert len(calls) > 0
    assert calls[0][0] == "test_tool"
    assert calls[0][1] == {"arg1": "val1"}
