"""
Memory Tools for Athena LLM.

Exposes tools for the assistant to save and retrieve long-term user memories.
"""
try:
    from src.memory.vector_memory import MemoryManager
except ImportError:
    from memory.vector_memory import MemoryManager


_memory_manager = MemoryManager()


def save_memory(fact: str, category: str = "general") -> str:
    """Save a user fact or preference into long-term persistent memory.
    
    Use this tool whenever the user tells you personal details, preferences, or key information to remember.
    
    Args:
        fact: The statement or detail to remember (e.g. "User prefers dark mode and codes in Python").
        category: Category classification (e.g., preference, personal, project).
        
    Returns:
        Confirmation message string.
    """
    mem_id = _memory_manager.add_memory(content=fact, category=category)
    return f"Successfully saved memory (ID {mem_id}): '{fact}'."


def retrieve_memory(query: str) -> str:
    """Retrieve relevant memories matching a query string.
    
    Use this tool when you need to recall past context, preferences, or details about the user.
    
    Args:
        query: Keywords or question to search memories for.
        
    Returns:
        Formatted summary of retrieved memory entries.
    """
    memories = _memory_manager.search_memories(query=query, limit=3)
    if not memories:
        return f"No memories found matching query '{query}'."

    items = [f"• [{m.category.upper()}] {m.content}" for m in memories]
    return "Retrieved Memories:\n" + "\n".join(items)
