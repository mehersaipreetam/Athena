"""
Example skill file - Athena SkillEngine auto-discovers and loads this.
Place in src/tools/skills/ or the configured skills directory.
"""

SKILL_METADATA = {
    "name": "calculator",
    "description": "Basic arithmetic calculator",
    "version": "1.0.0",
    "author": "Athena SkillForge",
}


def add(a: float, b: float) -> str:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        str: Sum as string.
    """
    return f"{a} + {b} = {a + b}"


def subtract(a: float, b: float) -> str:
    """Subtract b from a.

    Args:
        a: Minuend.
        b: Subtrahend.

    Returns:
        str: Difference as string.
    """
    return f"{a} - {b} = {a - b}"


def multiply(a: float, b: float) -> str:
    """Multiply two numbers.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        str: Product as string.
    """
    return f"{a} × {b} = {a * b}"


def divide(a: float, b: float) -> str:
    """Divide a by b.

    Args:
        a: Dividend.
        b: Divisor.

    Returns:
        str: Quotient as string, or error message.
    """
    if b == 0:
        return "Error: Division by zero"
    return f"{a} ÷ {b} = {a / b}"


def calculate(expression: str) -> str:
    """Evaluate a simple arithmetic expression.

    Supports: +, -, *, /, parentheses

    Args:
        expression: Arithmetic expression (e.g., "2 + 3 * 4").

    Returns:
        str: Result or error message.
    """
    try:
        # Safe evaluation - only allow basic math
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "Error: Invalid characters in expression"

        result = eval(expression)  # Safe due to character filter
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {e}"