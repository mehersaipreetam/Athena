from unittest.mock import MagicMock
from athena.persona import PersonaEngine, Mood
from athena.memory import MemoryEngine, UserProfile

def test_persona_engine_init():
    memory = MagicMock(spec=MemoryEngine)
    engine = PersonaEngine(memory=memory)
    assert engine.current_mood == Mood.NEUTRAL

def test_get_greeting_and_farewell():
    memory = MagicMock(spec=MemoryEngine)
    memory.get_user_profile.return_value = UserProfile(name="TestUser", interaction_count=5)
    
    engine = PersonaEngine(memory=memory)
    greeting = engine.get_greeting()
    assert isinstance(greeting, str)
    assert len(greeting) > 0
    
    farewell = engine.get_farewell()
    assert isinstance(farewell, str)
    assert len(farewell) > 0

def test_detect_mood_from_input():
    engine = PersonaEngine(memory=MagicMock())
    
    assert engine.detect_mood_from_input("emergency help now!") == Mood.FOCUSED
    assert engine.detect_mood_from_input("how does this work?") == Mood.CURIOUS
    assert engine.detect_mood_from_input("I am feeling tired") == Mood.WARM
    assert engine.detect_mood_from_input("generate a formal report") == Mood.PROFESSIONAL
    assert engine.detect_mood_from_input("let's play a game") == Mood.PLAYFUL
    assert engine.detect_mood_from_input("be careful, there is danger") == Mood.CONCERNED
    assert engine.detect_mood_from_input("just a normal message") == Mood.NEUTRAL

def test_update_mood():
    engine = PersonaEngine(memory=MagicMock())
    initial_mood = engine.current_mood
    
    # Send a curious message
    engine.update_mood("how does this work?")
    # Intensity should increase, mood might change if intensity high enough
    assert engine.current_mood in [Mood.NEUTRAL, Mood.CURIOUS]

def test_get_personality_prompt():
    memory = MagicMock(spec=MemoryEngine)
    profile = UserProfile(name="TestUser", preferences={"theme": "dark"}, frequent_topics=["python"])
    memory.get_user_profile.return_value = profile
    memory.get_context.return_value = "[RELEVANT MEMORIES]\n- [fact] Python is great"
    
    engine = PersonaEngine(memory=memory)
    prompt = engine.get_personality_prompt("Tell me about Python")
    
    assert "ATHENA PERSONA" in prompt
    assert "TestUser" in prompt
    assert "theme: dark" in prompt
    assert "python" in prompt
    assert "[RELEVANT MEMORIES]" in prompt
    assert "Python is great" in prompt
