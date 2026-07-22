"""
File Search Tools
"""
import os

def search_files(query: str, directory: str = '~', file_type: str = '') -> str:
    """Search for files matching a query.
    
    Args:
        query: The search query (filename or part of it).
        directory: The directory to search in. Defaults to '~'.
        file_type: Optional file extension to filter by (e.g., '.py', '.txt').
        
    Returns:
        Formatted string of matching files with paths and sizes.
    """
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        return f"Directory not found: {directory}"
        
    matches = []
    limit = 20
    
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                if query.lower() in file.lower():
                    if file_type and not file.endswith(file_type):
                        continue
                    
                    full_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(full_path)
                        matches.append((full_path, size))
                    except OSError:
                        pass
                        
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
                
        if not matches:
            return "No matching files found."
            
        result = [f"Found {len(matches)} files (limited to {limit}):"]
        for path, size in matches:
            # Format size nicely
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
                
            result.append(f"- {path} ({size_str})")
            
        return "\n".join(result)
        
    except Exception as e:
        return f"Error searching files: {e}"

def read_file_content(file_path: str, max_lines: int = 50) -> str:
    """Read and return the content of a text file.
    
    Args:
        file_path: Path to the file.
        max_lines: Maximum number of lines to return.
        
    Returns:
        File content or error message.
    """
    expanded_path = os.path.expanduser(file_path)
    
    if not os.path.isfile(expanded_path):
        return f"File not found: {file_path}"
        
    # Attempt to read as text
    try:
        with open(expanded_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated after {max_lines} lines)")
                    break
                lines.append(line.rstrip("\\n"))
                
        return "\n".join(lines)
    except UnicodeDecodeError:
        return f"Error: Cannot read binary file '{file_path}' as text."
    except Exception as e:
        return f"Error reading file: {e}"
