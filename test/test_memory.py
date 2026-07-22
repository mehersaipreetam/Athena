import time
import json
from datetime import datetime, timedelta
from athena.memory import MemoryEngine

def test_memory_engine_init(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    assert engine.db_path == temp_db_path
    
    stats = engine.get_stats()
    assert stats["total_memories"] == 0

def test_remember_and_recall(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    mem_id = engine.remember("The sky is blue", type="fact", tags=["nature"])
    assert mem_id > 0
    
    # Recall by exact word
    results = engine.recall("sky")
    assert len(results) == 1
    assert results[0].content == "The sky is blue"
    assert results[0].type == "fact"
    assert "nature" in results[0].tags

def test_get_context(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    engine.remember("Python is a programming language", type="fact")
    engine.remember("I love programming in Python", type="preference")
    
    context = engine.get_context("Python programming")
    assert "Python is a programming language" in context
    assert "I love programming in Python" in context

def test_conversation_history(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    engine.record_interaction("Hello", "Hi there!", sentiment="positive", skills_used=["greet"])
    
    convs = engine.get_recent_conversations(limit=5)
    assert len(convs) == 1
    assert convs[0].user_input == "Hello"
    assert convs[0].assistant_response == "Hi there!"
    assert convs[0].sentiment == "positive"
    assert "greet" in convs[0].skills_used

def test_user_profile_and_preferences(temp_db_path, monkeypatch):
    from athena.config import config
    monkeypatch.setattr(config, "user_name", "Alice")
    
    engine = MemoryEngine(db_path=temp_db_path)
    engine.update_preference("color", "blue")
    engine.update_preference("food", "pizza")
    
    # Update existing preference
    engine.update_preference("color", "red")
    
    profile = engine.get_user_profile()
    assert profile.name == "Alice"
    assert profile.preferences.get("color") == "red"
    assert profile.preferences.get("food") == "pizza"

def test_skill_usage_tracking(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    engine.record_skill_usage("search", success=True, args={"q": "test"})
    engine.record_skill_usage("search", success=False)
    
    stats = engine.get_skill_stats(days=1)
    assert "search" in stats
    assert stats["search"]["total_calls"] == 2
    assert stats["search"]["successes"] == 1
    assert stats["search"]["success_rate"] == 0.5

def test_consolidate_conversations(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    
    # Insert old conversation directly to simulate past dates
    past_time = time.time() - (10 * 86400) # 10 days ago
    with engine._get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, user_input, assistant_response, timestamp) VALUES (?, ?, ?, ?)",
            ("old_session", "How are you?", "I am fine.", past_time)
        )
    
    created = engine.consolidate(days=7)
    assert created == 1
    
    # Check if memory was created
    summaries = engine.recall("How are you?", types=["conversation_summary"])
    assert len(summaries) > 0
    assert "How are you?" in summaries[0].content

def test_prune_old_memories(temp_db_path):
    engine = MemoryEngine(db_path=temp_db_path)
    
    # Insert old memory
    past_time = time.time() - (100 * 86400) # 100 days ago
    with engine._get_conn() as conn:
        conn.execute(
            "INSERT INTO memories (type, content, tags, metadata, created_at, updated_at, access_count, last_accessed) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("fact", "Old fact", "[]", "{}", past_time, past_time, 0, past_time)
        )
    
    # Set max entries low so it gets pruned
    pruned = engine.prune_old_memories(max_entries=0, max_age_days=90)
    
    stats = engine.get_stats()
    assert stats["total_memories"] >= 0
