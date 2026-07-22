"""
Live Web Search & Real-Time Financial/Information Tool for Athena (JARVIS).

Enables real-time retrieval of stock quotes, news, weather, and current web data.
"""
import re
from typing import Optional
from duckduckgo_search import DDGS


def search_web_live(query: str) -> str:
    """Perform real-time web search for stock prices, news, facts, and live information.
    
    Use this tool whenever the user asks about current stock prices, weather, news,
    sports scores, or any real-time real-world event.
    
    Args:
        query: Search topic or question (e.g., "stock price of ADM today", "current weather in London").
        
    Returns:
        str: Concise real-time information text or summary.
    """
    clean_query = query.strip()
    
    try:
        ddgs = DDGS()
        results = []
        
        # Determine if we should prioritize news
        if "news" in clean_query.lower() or "today" in clean_query.lower():
            news_res = list(ddgs.news(clean_query, max_results=3))
            for item in news_res:
                results.append(f"• {item.get('title', '')}: {item.get('body', '')}")
                
        # Get standard web results
        web_res = list(ddgs.text(clean_query, max_results=3))
        for item in web_res:
            results.append(f"• {item.get('title', '')}: {item.get('body', '')}")
            
        if results:
            # Return max 5 items to keep it concise
            return f"Live Search Results for '{clean_query}':\n" + "\n".join(results[:5])
            
    except Exception as e:
        return f"Real-time search connection warning: {str(e)}. Please try rephrasing the query."

    return f"Live data query for '{clean_query}' completed. No direct summary snippet returned."
