import pytest
from fastapi.testclient import TestClient
import asyncio
from unittest.mock import MagicMock, patch

# Need to set up sys.path in server if not already handled
from web.server import app
import web.server as server_module

client = TestClient(app)

from athena.core import EventEmitter
@pytest.fixture
def mock_athena():
    athena_mock = MagicMock()
    athena_mock.skills.list_all.return_value = []
    athena_mock.memory.get_stats.return_value = {"total_memories": 0}
    athena_mock.get_stats.return_value = {"session": "test"}
    athena_mock.events = EventEmitter()
    
    with patch.object(server_module, "athena", athena_mock):
        yield athena_mock

def test_health_check(mock_athena):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "athena": True}

def test_get_stats(mock_athena):
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert response.json()["session"] == "test"

def test_memory_stats(mock_athena):
    response = client.get("/api/memory/stats")
    assert response.status_code == 200
    assert response.json()["total_memories"] == 0

def test_list_skills(mock_athena):
    skill1 = MagicMock()
    skill1.name = "test_skill"
    skill1.description = "test"
    skill1.version = "1.0"
    skill1.use_count = 1
    skill1.success_count = 1
    
    mock_athena.skills.list_all.return_value = [skill1]
    
    response = client.get("/api/skills")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "test_skill"

def test_chat(mock_athena):
    def fake_inject(text):
        mock_athena.events.emit('interaction_complete', {'response': 'test response'})
    mock_athena.inject_text.side_effect = fake_inject
    
    response = client.post("/api/chat", json={"text": "hello"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "test response"}
    mock_athena.inject_text.assert_called_with("hello")
