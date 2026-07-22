"""
URL Content Extraction & Document Analysis Tool for Project Athena.

Enables Athena to read and summarize web pages, PDFs, and documents
when given a URL or file path. Supports multi-modal input analysis.
"""
import urllib.request
import urllib.parse
import re
import os
from typing import Optional


def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """Fetch and extract readable text content from a web URL.

    Strips HTML tags and returns clean text suitable for LLM analysis.
    Useful for answering questions about web pages, articles, and documentation.

    Args:
        url: The web URL to fetch content from.
        max_chars: Maximum characters to return (default 4000).

    Returns:
        str: Extracted text content from the URL.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "No title"

        # Remove script and style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Convert block elements to newlines
        html = re.sub(r"<(?:p|div|br|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)

        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")

        # Clean whitespace
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if len(line) > 2]
        text = "\n".join(lines)

        # Truncate
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [Content truncated]"

        return f"Page Title: {title}\nURL: {url}\n\n{text}"

    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code} when fetching {url}: {e.reason}"
    except urllib.error.URLError as e:
        return f"URL Error fetching {url}: {e.reason}"
    except Exception as e:
        return f"Error fetching URL content: {str(e)}"


def read_document(file_path: str, max_lines: int = 100) -> str:
    """Read and return the content of a local text document.

    Supports common text formats: .txt, .py, .md, .json, .yaml, .yml,
    .csv, .log, .xml, .html, .css, .js, .ts, .toml, .ini, .cfg, .sh, .bash.

    Args:
        file_path: Absolute or relative path to the file.
        max_lines: Maximum number of lines to return (default 100).

    Returns:
        str: File content or error message.
    """
    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    if not os.path.isfile(file_path):
        return f"Path is not a file: {file_path}"

    # Check file extension
    text_extensions = {
        ".txt", ".py", ".md", ".json", ".yaml", ".yml", ".csv", ".log",
        ".xml", ".html", ".css", ".js", ".ts", ".toml", ".ini", ".cfg",
        ".sh", ".bash", ".zsh", ".fish", ".conf", ".env", ".gitignore",
        ".dockerfile", ".makefile", ".rst", ".tex", ".sql", ".r", ".go",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".rb", ".php",
    }
    _, ext = os.path.splitext(file_path)
    basename = os.path.basename(file_path).lower()

    # Allow extensionless files like Makefile, Dockerfile
    known_basenames = {"makefile", "dockerfile", "readme", "license", "changelog"}
    if ext.lower() not in text_extensions and basename not in known_basenames:
        # Try reading anyway but warn
        pass

    try:
        file_size = os.path.getsize(file_path)
        if file_size > 1_000_000:  # 1MB limit
            return f"File too large ({file_size:,} bytes). Maximum supported size is 1MB."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"\n... [Truncated at {max_lines} lines. File has more content.]")
                    break
                lines.append(line.rstrip())

        content = "\n".join(lines)
        return f"File: {file_path} ({file_size:,} bytes)\n\n{content}"

    except UnicodeDecodeError:
        return f"Cannot read {file_path}: appears to be a binary file."
    except PermissionError:
        return f"Permission denied: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"
