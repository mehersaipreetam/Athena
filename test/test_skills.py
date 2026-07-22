import pytest
from pathlib import Path
from unittest.mock import MagicMock
from athena.skills import SkillEngine, SkillSandbox, ValidationResult, SkillInfo

def test_sandbox_validation():
    sandbox = SkillSandbox()
    
    # Valid code
    valid_code = '''
SKILL_METADATA = {"name": "test"}

def valid_func(a: int) -> str:
    """Test function.
    Args: a
    Returns: string
    """
    return str(a)
'''
    result = sandbox.validate_source(valid_code)
    assert result.is_valid
    assert "valid_func" in result.functions_found
    
    # Invalid imports
    invalid_code = '''
import subprocess

def bad_func(a: int) -> str:
    """Test."""
    return ""
'''
    result = sandbox.validate_source(invalid_code)
    assert not result.is_valid
    assert any("subprocess" in e for e in result.errors)
    
    # Missing annotations
    no_ann_code = '''
SKILL_METADATA = {"name": "test"}

def no_ann(a):
    """Test."""
    return ""
'''
    result = sandbox.validate_source(no_ann_code)
    assert not result.is_valid
    assert any("annotation" in e for e in result.errors)

def test_sandbox_execution():
    sandbox = SkillSandbox()
    source = '''
def add(a: int, b: int) -> str:
    """Add two numbers."""
    return str(a + b)
'''
    test_code = sandbox.generate_basic_test(source)
    success, output = sandbox.execute_with_timeout(source, test_code)
    assert success, output

def test_skill_engine_discovery(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    # Create a valid skill file
    skill_file = skills_dir / "math_skills.py"
    skill_file.write_text('''
SKILL_METADATA = {"name": "math_skills", "description": "Math."}

def multiply(a: int, b: int) -> str:
    """Multiply a and b.
    Args: a, b
    Returns: result
    """
    return str(a * b)
''')
    
    memory = MagicMock()
    engine = SkillEngine(llm_generate_fn=lambda x: "", memory=memory, skills_dir=str(skills_dir))
    
    skills = engine.list_all()
    assert len(skills) == 1
    assert skills[0].function_name == "multiply"
    
    tools = engine.get_tool_definitions()
    assert len(tools) == 1
    assert tools[0]["name"] == "multiply"

def test_skill_engine_execute(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_file = skills_dir / "test_skill.py"
    skill_file.write_text('''
SKILL_METADATA = {"name": "test"}
def echo(msg: str) -> str:
    """Echo msg."""
    return msg
''')
    
    memory = MagicMock()
    engine = SkillEngine(llm_generate_fn=lambda x: "", memory=memory, skills_dir=str(skills_dir))
    
    # Execute skill
    result = engine.execute("echo", msg="hello")
    assert result == "hello"
    
    # Memory should track usage
    memory.record_skill_usage.assert_called_once()

def test_skill_engine_forge(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    memory = MagicMock()
    
    # Mock LLM returning valid skill code
    def mock_llm(prompt):
        return '''
SKILL_METADATA = {"name": "hello_skill", "description": "Say hello"}
def say_hello(name: str) -> str:
    """Say hello to name."""
    return "Hello " + name
'''
    
    engine = SkillEngine(llm_generate_fn=mock_llm, memory=memory, skills_dir=str(skills_dir))
    success, msg = engine.forge("write a skill to say hello")
    
    assert success, msg
    assert "say_hello" in msg
    
    # Verify file was created
    assert len(list(skills_dir.glob("*.py"))) == 1
    
    # Verify skill loaded
    assert engine.get("say_hello") is not None
