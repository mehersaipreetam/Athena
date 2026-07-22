"""
Python Interpreter Tool for Athena.

Allows Athena to write, execute, and evaluate Python code dynamically.
This acts as a "Code Interpreter" giving her the ability to calculate dates, 
solve math problems, and run custom scripts on the fly.
"""
import sys
import io
import contextlib
import traceback

def run_python(code: str) -> str:
    """Execute Python code and return its stdout and result.
    
    Use this tool to calculate dates (e.g. what day is July 26th), perform complex math,
    or write and execute dynamic scripts when you need to figure something out programmatically.
    
    Args:
        code: A valid Python script string to execute. Use print() to output results.
        
    Returns:
        str: The standard output and any errors produced by the script.
    """
    output_buffer = io.StringIO()
    
    # Define a restricted global namespace
    safe_globals = {
        "__builtins__": __builtins__,
    }
    
    try:
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            # Execute the code
            exec(code, safe_globals)
            
        output = output_buffer.getvalue().strip()
        if not output:
            return "Code executed successfully but produced no output. Did you forget to use print()?"
        return f"Output:\n{output}"
        
    except Exception as e:
        error_msg = traceback.format_exc()
        return f"Error executing code:\n{error_msg}"
