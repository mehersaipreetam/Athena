"""
Example Skill for Athena's Dynamic Skill Framework.

This file serves as a reference implementation showing the exact format
that dynamically-created skills must follow to be auto-discovered and
registered as MCP tools by the SkillRegistry.

SKILL CONTRACT:
    1. Each skill file MUST contain one or more top-level async or sync functions.
    2. Each function MUST have a Google-style docstring with Args/Returns.
    3. Each function MUST have type annotations on all parameters and return type.
    4. The module MUST define SKILL_METADATA (dict) with at minimum 'name' and 'description'.
    5. Functions whose names start with '_' are considered private and will NOT be registered.
"""

SKILL_METADATA = {
    "name": "example_skill",
    "description": "A reference skill demonstrating the Athena skill format.",
    "version": "1.0.0",
    "author": "Athena SkillForge",
}


def convert_temperature(value: float, from_unit: str, to_unit: str) -> str:
    """Convert temperature between Celsius, Fahrenheit, and Kelvin.

    Use this tool when the user asks to convert temperatures between units.

    Args:
        value: The temperature value to convert.
        from_unit: Source unit — one of 'celsius', 'fahrenheit', or 'kelvin'.
        to_unit: Target unit — one of 'celsius', 'fahrenheit', or 'kelvin'.

    Returns:
        str: A human-readable string with the conversion result.
    """
    units = {"celsius": "C", "fahrenheit": "F", "kelvin": "K"}
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    if from_unit not in units or to_unit not in units:
        return f"Error: Units must be one of: {', '.join(units.keys())}"

    # Convert to Celsius first as intermediate
    if from_unit == "celsius":
        celsius = value
    elif from_unit == "fahrenheit":
        celsius = (value - 32) * 5 / 9
    else:  # kelvin
        celsius = value - 273.15

    # Convert from Celsius to target
    if to_unit == "celsius":
        result = celsius
    elif to_unit == "fahrenheit":
        result = celsius * 9 / 5 + 32
    else:  # kelvin
        result = celsius + 273.15

    return f"{value}°{units[from_unit]} = {result:.2f}°{units[to_unit]}"
