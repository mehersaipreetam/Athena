"""
Autonomous Code Refactoring Tool for Athena.

Allows the assistant to inspect local source code files, check Python AST syntax,
and perform automated code quality checks.
"""
import ast
import os
from typing import Optional


def analyze_and_refactor_code(file_path: str, instruction: str = "Analyze code quality") -> str:
    """Inspect local Python source file and validate syntax structure.
    
    Args:
        file_path: Absolute or relative path to target Python file.
        instruction: Contextual goal or instruction for code analysis.
        
    Returns:
        str: Analysis report including AST parsing status and line count.
    """
    if not os.path.exists(file_path):
        return f"Error: Target file '{file_path}' does not exist."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code_content = f.read()

        # Parse AST syntax
        tree = ast.parse(code_content, filename=file_path)
        
        func_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
        class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        line_count = len(code_content.splitlines())

        return (
            f"[CODE ANALYSIS COMPLETE: '{file_path}']\n"
            f"Instruction: {instruction}\n"
            f"Status: Syntax Valid (AST Parsed Successfully)\n"
            f"Metrics: {line_count} Lines, {func_count} Functions, {class_count} Classes"
        )
    except SyntaxError as e:
        return f"Syntax Error in '{file_path}' at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Error analyzing '{file_path}': {str(e)}"
